#!/usr/bin/env python3

"""
Modular Daemon Package - Main entry point and dependency injection
Extracted from daemon_clean.py with 100% functionality preservation
"""

import asyncio
import argparse
import logging
import signal
import os
from pathlib import Path

# CRITICAL: Configure logging BEFORE ANY ksi imports to ensure all loggers work correctly
# This must be the very first thing we do after stdlib imports
import logging as stdlib_logging
from ksi_common.logging import configure_structlog

# Get configuration from environment or defaults
log_level = os.environ.get('KSI_LOG_LEVEL', 'INFO')
log_format = os.environ.get('KSI_LOG_FORMAT', 'console')
log_file = Path(os.environ.get('KSI_LOG_DIR', 'var/logs')) / 'daemon' / 'daemon.log'

# Ensure log directory exists
log_file.parent.mkdir(parents=True, exist_ok=True)

# Configure structlog with the appropriate level
# This also configures stdlib logging internally
configure_structlog(
    log_level=log_level,
    log_format=log_format,
    log_file=log_file
)

# Debug: Print to verify log level
print(f"[ksi_daemon.__init__] Configured logging with level: {log_level}")

# NOW we can import our modules - logging is configured
from ksi_common.config import config
from ksi_daemon.core_plugin import SimpleDaemonCore as PluginDaemon

# Get logger
import structlog
logger = structlog.get_logger(__name__)

def parse_args():
    """Parse command line arguments with config system defaults"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--socket-dir', 
                       help='Override socket directory (creates all sockets in this dir)')
    return parser.parse_args()

def setup_logging():
    """
    Logging is now configured at module import time to ensure plugins get proper configuration.
    This function is kept for compatibility but just returns the logger.
    """
    return stdlib_logging.getLogger('daemon')

def ensure_var_directories():
    """Ensure all configured directories exist using config system"""
    config.ensure_directories()

def setup_signal_handlers(shutdown_event, loop):
    """Setup asyncio-compatible signal handlers for graceful shutdown"""
    
    def signal_handler(signame):
        logger.info(f"Received signal {signame}, initiating shutdown...")
        
        # Set shutdown event
        if shutdown_event:
            shutdown_event.set()
            logger.info("Shutdown event set")
        else:
            logger.error("No shutdown event available")
        
        # Cancel all running tasks to ensure clean shutdown
        tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
        logger.info(f"Cancelling {len(tasks)} running tasks...")
        for task in tasks:
            task.cancel()
    
    # Use asyncio's add_signal_handler for proper integration
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(
                sig,
                lambda s=sig: signal_handler(signal.Signals(s).name)
            )
            logger.info(f"Asyncio signal handler registered for {signal.Signals(sig).name}")
        except (ValueError, NotImplementedError) as e:
            # Fallback to traditional signal handling if asyncio method not available
            logger.warning(f"Could not register asyncio signal handler for {sig}: {e}")
            signal.signal(sig, lambda signum, frame: signal_handler(signal.Signals(signum).name))

async def create_plugin_daemon(socket_dir: str = None):
    """Create plugin-based daemon"""
    
    # Build configuration
    config_dict = {
        "daemon": {
            "plugin_dirs": [
                str(Path(__file__).parent / "plugins")
            ],
            "max_event_history": 1000
        },
        "transports": {
            "unix": {
                "enabled": True,
                "socket_dir": socket_dir if socket_dir else str(config.socket_path.parent)
            }
        }
    }
    
    # Create and initialize plugin daemon
    daemon = PluginDaemon(config_dict)
    await daemon.initialize()
    
    return daemon

async def main():
    """Main entry point for plugin-based daemon"""
    args = parse_args()
    logger = setup_logging()
    
    # Ensure var/ directory structure exists
    ensure_var_directories()
    
    # Create plugin-based daemon
    daemon = await create_plugin_daemon(args.socket_dir)
    
    # Get the current event loop
    loop = asyncio.get_running_loop()
    
    # Setup signal handlers with asyncio integration
    setup_signal_handlers(daemon.shutdown_event, loop)
    
    # Start the daemon
    logger.info("Starting plugin-based KSI daemon")
    try:
        await daemon.run()
    except asyncio.CancelledError:
        logger.info("Daemon cancelled, shutting down gracefully")
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    except Exception as e:
        logger.error(f"Daemon failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Ensure cleanup happens
        await daemon.shutdown()
        logger.info("Final cleanup...")
        await asyncio.sleep(0.1)  # Allow final logs to flush

# Make this package executable as a module
if __name__ == '__main__':
    asyncio.run(main())