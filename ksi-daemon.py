#!/usr/bin/env python3

"""
KSI Daemon - Production-grade daemon using python-daemon
Eliminates shell script complexity with proper Unix daemonization
"""

import asyncio
import signal
import sys
import os
import argparse
import logging
from pathlib import Path

# Import python-daemon package (no conflicts now with ksi_daemon)
import daemon
import daemon.pidfile

# CRITICAL: Configure logging BEFORE any ksi imports to ensure correct format
# This prevents modules from auto-configuring with wrong format
os.environ.setdefault('KSI_LOG_FORMAT', 'json')  # Ensure JSON format by default

# Now we can safely import and configure
from ksi_common import configure_structlog
# Configure immediately before any other imports
configure_structlog(
    log_level=os.environ.get('KSI_LOG_LEVEL', 'INFO'),
    log_format='json',  # Always use JSON in daemon
    log_file=Path('var/logs/daemon/daemon.log'),
    force_disable_console=True
)

# NOW import modules that create loggers
from ksi_daemon import main as daemon_main
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

# Global shutdown coordination
shutdown_requested = False
daemon_instance = None

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested, daemon_instance
    
    logger = get_bound_logger('daemon_main', version='1.0.0')
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
    
    # Logging already configured at module level, just log that we're ready
    # No need to reconfigure - we already have JSON format
    
    # Get the configured logger and log startup
    logger = get_bound_logger('daemon_main', version='1.0.0')
    logger.info("KSI daemon logging configured")
    
    # Return file handle for daemon context preservation
    return open(config.daemon_log_file, 'a')

async def daemon_wrapper():
    """Wrapper for existing daemon with shutdown monitoring"""
    global daemon_instance, shutdown_requested
    
    # ksi_common already ensures project root is on sys.path
    
    logger = get_bound_logger('daemon_main', version='1.0.0')
    logger.info("Starting KSI daemon core")
    
    try:
        # Import and create daemon directly (avoiding argument conflicts)
        from ksi_daemon import create_event_daemon
        daemon_instance = await create_event_daemon()
        await daemon_instance.run()
        
        # After run() completes (shutdown event was set), perform coordinated shutdown
        logger.info("Daemon run completed, performing coordinated shutdown")
        await daemon_instance.shutdown()
        
    except asyncio.CancelledError:
        logger.info("Daemon cancelled due to shutdown request")
        if daemon_instance:
            await daemon_instance.shutdown()
        raise
    except Exception as e:
        logger.error(f"Daemon error: {e}", exc_info=True)
        raise
    finally:
        logger.info("Daemon wrapper cleanup complete")

def run_as_daemon():
    """Run KSI daemon in background (daemonized)"""
    # Set up logging before daemonization
    log_file_handle = setup_daemon_logging()
    logger = get_bound_logger('daemon_main', version='1.0.0')
    
    # Ensure all required directories exist
    config.ensure_directories()
    
    logger.info("Preparing to daemonize KSI daemon")
    
    context = daemon.DaemonContext(
        # Working directory - stay in project directory
        working_directory=str(Path.cwd()),
        
        # PID file for process management
        pidfile=daemon.pidfile.PIDLockFile(str(config.daemon_pid_file)),
        
        # Redirect stdout/stderr to daemon log file
        stdout=log_file_handle,
        stderr=log_file_handle,
        
        # Preserve logging file descriptors
        files_preserve=[log_file_handle],
        
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
        # Re-configure logging inside daemon context (file handles change after fork)
        # Always use JSON format in daemon mode
        configure_structlog(
            log_level=config.log_level,
            log_format='json',  # Always JSON in daemon
            log_file=config.daemon_log_file,
            force_disable_console=True
        )
        
        # Get new logger after reconfiguration
        daemon_logger = get_bound_logger('daemon_main', version='1.0.0')
        daemon_logger.info("KSI daemon started in background")
        
        try:
            # Run the async daemon
            asyncio.run(daemon_wrapper())
        except KeyboardInterrupt:
            daemon_logger.info("Daemon interrupted")
        except Exception as e:
            daemon_logger.error(f"Daemon failed: {e}", exc_info=True)
            sys.exit(1)
        finally:
            daemon_logger.info("KSI daemon stopped")

def run_in_foreground():
    """Run KSI daemon in foreground (development mode)"""
    # Set up console logging for development
    logging.basicConfig(
        level=config.get_log_level(),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    # Also configure structlog for development
    configure_structlog()
    
    logger = get_bound_logger('daemon_main', version='1.0.0')
    logger.info("Starting KSI daemon in foreground mode (development)")
    
    try:
        # Import and create daemon directly (avoiding argument conflicts)
        from ksi_daemon import create_event_daemon
        
        async def run_daemon():
            daemon_instance = await create_event_daemon()
            await daemon_instance.run()
            # Perform coordinated shutdown after run completes
            await daemon_instance.shutdown()
        
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