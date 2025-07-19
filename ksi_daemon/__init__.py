#!/usr/bin/env python3

"""
Modular Daemon Package - Event-Based Version
Uses pure event system instead of pluggy
"""

import asyncio
import argparse
import signal
import os
from pathlib import Path

# Logging is configured by the daemon entry point (ksi-daemon.py)
# This ensures proper daemon-specific configuration (no console handlers)

# NOW we can import our modules - logging is configured
from ksi_common.config import config
from ksi_daemon.daemon_core import EventDaemonCore

# Get logger
from ksi_common.logging import get_bound_logger
logger = get_bound_logger("daemon_init", version="3.0.0")

def parse_args():
    """Parse command line arguments with config system defaults"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--socket-dir', 
                       help='Override socket directory (creates all sockets in this dir)')
    return parser.parse_args()

def setup_logging():
    """
    Logging is now configured at module import time to ensure modules get proper configuration.
    This function is kept for compatibility but just returns the logger.
    """
    return logger  # Use the already configured structlog bound logger

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

async def create_event_daemon(socket_dir: str = None):
    """Create simple module-based daemon"""
    
    # Build configuration
    config_dict = {
        "daemon": {
            "max_event_history": 1000
        },
        "transports": {
            "unix": {
                "enabled": True,
                "socket_dir": socket_dir if socket_dir else str(config.socket_path.parent)
            }
        }
    }
    
    # Add WebSocket transport if enabled
    if config.is_websocket_enabled:
        config_dict["transports"]["websocket"] = {
            "enabled": True,
            "host": config.websocket_host,
            "port": config.websocket_port,
            "cors_origins": config.websocket_cors_origins
        }
    
    # Create and initialize event-based daemon (pure module system)
    daemon = EventDaemonCore()
    success = await daemon.initialize(config_dict)
    
    if not success:
        raise RuntimeError("Failed to initialize daemon")
    
    return daemon

async def main():
    """Main entry point for event-based daemon"""
    args = parse_args()
    logger = setup_logging()
    
    # Ensure var/ directory structure exists
    ensure_var_directories()
    
    # Create event-based daemon
    daemon = await create_event_daemon(args.socket_dir)
    
    # Get the current event loop
    loop = asyncio.get_running_loop()
    
    # Setup signal handlers with asyncio integration
    setup_signal_handlers(daemon.shutdown_event, loop)
    
    # Start the daemon
    logger.info("Starting event-based KSI daemon")
    try:
        await daemon.run()
    except asyncio.CancelledError:
        logger.info("Daemon cancelled, shutting down gracefully")
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    except Exception as e:
        logger.error(f"Daemon failed: {e}", exc_info=True)
        import sys
        sys.exit(1)
    finally:
        # Ensure cleanup happens
        await daemon.shutdown()
        logger.info("Final cleanup...")
        await asyncio.sleep(0.1)  # Allow final logs to flush

# Make this package executable as a module
if __name__ == '__main__':
    asyncio.run(main())