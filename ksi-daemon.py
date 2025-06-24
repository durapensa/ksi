#!/usr/bin/env python3

"""
KSI Daemon - Production-grade daemon using python-daemon
Eliminates shell script complexity with proper Unix daemonization
"""

import asyncio
import signal
import logging
import sys
import os
import argparse
from pathlib import Path

# Import python-daemon package (no conflicts now with ksi_daemon)
import daemon
import daemon.pidfile

# Import our local daemon modules (path will be set in forked process)
from ksi_daemon import main as daemon_main
from ksi_daemon.config import config

# Global shutdown coordination
shutdown_requested = False
daemon_instance = None

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested, daemon_instance
    
    logger = logging.getLogger('ksi_daemon')
    logger.info(f"Received signal {signum}, initiating graceful shutdown")
    
    shutdown_requested = True
    
    # If we have a daemon instance with shutdown event, trigger it
    if daemon_instance and hasattr(daemon_instance, 'shutdown_event'):
        daemon_instance.shutdown_event.set()
        logger.info("Daemon shutdown event set")

def setup_daemon_logging():
    """Set up logging with file preservation for daemon mode"""
    # Ensure log directory exists
    config.log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure structlog first (from existing config system)
    config.configure_structlog()
    
    # Create file handler for daemon logs
    log_file = config.get_log_file_path()
    handler = logging.FileHandler(log_file)
    handler.setLevel(config.get_log_level())
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    # Configure root logger
    logger = logging.getLogger('ksi_daemon')
    logger.setLevel(config.get_log_level())
    logger.addHandler(handler)
    
    # Also configure the daemon package logger
    daemon_logger = logging.getLogger('daemon')
    daemon_logger.addHandler(handler)
    
    logger.info("KSI daemon logging configured")
    return handler

async def daemon_wrapper():
    """Wrapper for existing daemon with shutdown monitoring"""
    global daemon_instance, shutdown_requested
    
    # Ensure current directory is in Python path (needed in forked process)
    import sys
    sys.path.insert(0, str(Path.cwd()))
    
    logger = logging.getLogger('ksi_daemon')
    logger.info("Starting KSI daemon core")
    
    try:
        # Import and create daemon directly (avoiding argument conflicts)
        from ksi_daemon import create_plugin_daemon
        daemon_instance = await create_plugin_daemon()
        await daemon_instance.run()
        
    except asyncio.CancelledError:
        logger.info("Daemon cancelled due to shutdown request")
        raise
    except Exception as e:
        logger.error(f"Daemon error: {e}", exc_info=True)
        raise
    finally:
        logger.info("Daemon wrapper cleanup complete")

def run_as_daemon():
    """Run KSI daemon in background (daemonized)"""
    # Set up logging before daemonization
    log_handler = setup_daemon_logging()
    logger = logging.getLogger('ksi_daemon')
    
    # Ensure all required directories exist
    config.ensure_directories()
    
    logger.info("Preparing to daemonize KSI daemon")
    
    # Create daemon context (environment variables are NOT preserved by design in python-daemon)
    # Virtual environment should be handled by using venv's Python interpreter directly
    context = daemon.DaemonContext(
        # Working directory - stay in project directory
        working_directory=str(Path.cwd()),
        
        # PID file for process management
        pidfile=daemon.pidfile.PIDLockFile(str(config.pid_file)),
        
        # Preserve logging file descriptors
        files_preserve=[log_handler.stream],
        
        # Signal handling - let python-daemon handle the basic setup
        # Our daemon code will set up its own asyncio signal handlers
        signal_map={
            signal.SIGTERM: signal_handler,
            signal.SIGINT: signal_handler,
            signal.SIGHUP: signal_handler,  # Graceful restart/reload
        },
        
        # Security
        umask=0o002,
        
        # Don't detach for debugging (can be overridden)
        detach_process=True,
    )
    
    logger.info("Starting daemon context")
    
    # Run the daemon
    with context:
        logger.info("KSI daemon started in background")
        try:
            # Run the async daemon
            asyncio.run(daemon_wrapper())
        except KeyboardInterrupt:
            logger.info("Daemon interrupted")
        except Exception as e:
            logger.error(f"Daemon failed: {e}", exc_info=True)
            sys.exit(1)
        finally:
            logger.info("KSI daemon stopped")

def run_in_foreground():
    """Run KSI daemon in foreground (development mode)"""
    # Set up console logging for development
    logging.basicConfig(
        level=config.get_log_level(),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    # Also configure structlog for development
    config.configure_structlog()
    
    logger = logging.getLogger('ksi_daemon')
    logger.info("Starting KSI daemon in foreground mode (development)")
    
    try:
        # Import and create daemon directly (avoiding argument conflicts)
        from ksi_daemon import create_plugin_daemon
        
        async def run_daemon():
            daemon_instance = await create_plugin_daemon()
            await daemon_instance.run()
        
        asyncio.run(run_daemon())
    except KeyboardInterrupt:
        logger.info("Daemon interrupted by user")
    except Exception as e:
        logger.error(f"Daemon error: {e}", exc_info=True)
        sys.exit(1)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='KSI Daemon - Modular Claude daemon system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Run as background daemon
  %(prog)s --foreground       # Run in foreground (development)
  %(prog)s --socket-dir /tmp  # Override socket directory
        """
    )
    
    parser.add_argument(
        '--foreground', '--fg',
        action='store_true',
        help='Run in foreground instead of daemonizing (development mode)'
    )
    
    parser.add_argument(
        '--socket-dir',
        help='Override socket directory (creates all sockets in this dir)'
    )
    
    parser.add_argument(
        '--hot-reload-from',
        help='Socket path to reload from'
    )
    
    return parser.parse_args()

def main():
    """Main entry point"""
    args = parse_args()
    
    # Set any config overrides from args
    # (The existing daemon main function will handle socket_dir and hot_reload_from)
    
    if args.foreground:
        # Development mode - run in foreground with console output
        run_in_foreground()
    else:
        # Production mode - daemonize
        run_as_daemon()

if __name__ == '__main__':
    main()