#!/usr/bin/env python3
"""
Modular Daemon Package with Dependency Injection
Uses aioinject for proper service lifecycle management
"""

import asyncio
import argparse
import logging
import signal
import os
from pathlib import Path

# Import all modules
from .config import config
from .core import KSIDaemonCore
from .di_container import daemon_container
from .command_registry_di import CommandHandlerProxy

# Import commands to ensure registration
from . import commands

def parse_args():
    """Parse command line arguments with config system defaults"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--socket-dir', 
                       help='Override socket directory (creates all sockets in this dir)')
    parser.add_argument('--hot-reload-from', help='Socket path to reload from')
    parser.add_argument('--foreground', action='store_true', 
                       help='Run in foreground (for development)')
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

def setup_signal_handlers(core_daemon, loop):
    """Setup asyncio-compatible signal handlers for graceful shutdown"""
    logger = logging.getLogger('daemon')
    
    def signal_handler(signame):
        logger.info(f"Received signal {signame}, initiating shutdown...")
        
        # Set shutdown event
        if hasattr(core_daemon, 'shutdown_event') and core_daemon.shutdown_event:
            core_daemon.shutdown_event.set()
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

async def create_daemon(socket_dir: str = None, hot_reload_from: str = None):
    """Create daemon with dependency injection"""
    logger = logging.getLogger('daemon')
    logger.info("Creating daemon with DI container")
    
    # Create core daemon with optional socket directory override
    core_daemon = KSIDaemonCore(socket_dir=socket_dir, hot_reload_from=hot_reload_from)
    
    # Initialize services via DI container
    await daemon_container.initialize_services()
    
    # Get services from container
    state_manager = await daemon_container.get_service('StateManager')
    completion_manager = await daemon_container.get_service('CompletionManager')
    agent_manager = await daemon_container.get_service('AgentManager')
    message_bus = await daemon_container.get_service('MessageBus')
    identity_manager = await daemon_container.get_service('IdentityManager')
    hot_reload_manager = await daemon_container.get_service('HotReloadManager')
    
    # Create command handler proxy with manager references
    managers = {
        'core_daemon': core_daemon,
        'state_manager': state_manager,
        'completion_manager': completion_manager,
        'agent_manager': agent_manager,
        'hot_reload_manager': hot_reload_manager,
        'message_bus': message_bus,
        'identity_manager': identity_manager
    }
    
    command_handler = CommandHandlerProxy(managers)
    
    # Wire everything together via dependency injection
    core_daemon.set_managers(
        state_manager=state_manager,
        completion_manager=completion_manager,
        agent_manager=agent_manager,
        hot_reload_manager=hot_reload_manager,
        command_handler=command_handler,
        message_bus=message_bus,
        identity_manager=identity_manager
    )
    
    # Set up cross-manager dependencies
    completion_manager.set_message_bus(message_bus)
    completion_manager.set_agent_manager(agent_manager)
    
    logger.info("Daemon created with DI container successfully")
    return core_daemon

async def main():
    """Main entry point with DI"""
    args = parse_args()
    logger = setup_logging()
    
    # Ensure var/ directory structure exists
    ensure_var_directories()
    
    # Create modular daemon with dependency injection
    core_daemon = await create_daemon(
        socket_dir=args.socket_dir,
        hot_reload_from=args.hot_reload_from
    )
    
    # Get event loop
    loop = asyncio.get_running_loop()
    
    # Set up signal handlers
    setup_signal_handlers(core_daemon, loop)
    
    # Start the daemon
    logger.info(f"Starting KSI daemon in {'foreground' if args.foreground else 'background'} mode")
    try:
        await core_daemon.start()
    except asyncio.CancelledError:
        logger.info("Daemon main cancelled during shutdown")
    except Exception as e:
        logger.error(f"Daemon error: {e}", exc_info=True)
        raise
    finally:
        logger.info("Daemon main exiting cleanly")

def run():
    """Entry point for running daemon - compatible with existing interface"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown requested via keyboard interrupt")
    except Exception as e:
        print(f"Fatal error: {e}")
        raise

if __name__ == '__main__':
    run()