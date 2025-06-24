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

# Import all modules
from .config import config

# Import plugin system
from .core_plugin import PluginDaemon

# Get logger
import structlog
logger = structlog.get_logger(__name__)

def parse_args():
    """Parse command line arguments with config system defaults"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--socket-dir', 
                       help='Override socket directory (creates all sockets in this dir)')
    parser.add_argument('--hot-reload-from', help='Socket path to reload from')
    return parser.parse_args()

def setup_logging():
    """Set up logging using configuration system"""
    # Ensure log directory exists
    config.log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure structlog based on config (this handles everything)
    config.configure_structlog()
    
    # Get log file path for stdlib logger
    log_file = config.get_log_file_path()
    
    # Configure stdlib logging to work with structlog
    # Note: structlog will handle the formatting
    logging.basicConfig(
        level=config.get_log_level(),
        format='%(message)s',  # Let structlog handle formatting
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger('daemon')

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

async def create_plugin_daemon(socket_dir: str = None, hot_reload_from: str = None):
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
                "socket_dir": socket_dir if socket_dir else "/tmp/ksi"
            }
        }
    }
    
    # Hot reload not yet supported in plugin architecture
    if hot_reload_from:
        logger.warning("Hot reload not yet supported in plugin architecture")
    
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
    daemon = await create_plugin_daemon(args.socket_dir, args.hot_reload_from)
    
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