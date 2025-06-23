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
from .core import KSIDaemonCore
from .session_and_shared_state_manager import SessionAndSharedStateManager
from .completion_manager import CompletionManager
from .agent_profile_registry import AgentProfileRegistry
# Utils removed - functionality moved to commands/cleanup.py and commands/reload_module.py
from .hot_reload import HotReloadManager
from .command_handler import CommandHandler
from .message_bus import MessageBus
from .agent_identity_registry import AgentIdentityRegistry

# Import commands to ensure registration
import daemon.commands

def parse_args():
    """Parse command line arguments with config system defaults"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--socket', default=str(config.socket_path), 
                       help=f'Socket path (default: {config.socket_path})')
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

async def create_daemon(socket_path: str, hot_reload_from: str = None):
    """Create and wire together all daemon modules with dependency injection"""
    
    # Create core daemon
    core_daemon = KSIDaemonCore(socket_path, hot_reload_from)
    
    # Create all managers
    state_manager = SessionAndSharedStateManager()
    completion_manager = CompletionManager(state_manager=state_manager)
    agent_manager = AgentProfileRegistry(completion_manager=completion_manager)
    hot_reload_manager = HotReloadManager(core_daemon, state_manager, agent_manager)
    message_bus = MessageBus()
    identity_manager = AgentIdentityRegistry()
    
    # Create command handler with all dependencies
    command_handler = CommandHandler(
        core_daemon=core_daemon,
        state_manager=state_manager,
        completion_manager=completion_manager,
        agent_manager=agent_manager,
        hot_reload_manager=hot_reload_manager,
        message_bus=message_bus,
        identity_manager=identity_manager
    )
    
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
    
    return core_daemon

async def main():
    """Main entry point - EXACT logic from daemon_clean.py adapted for modular architecture"""
    args = parse_args()
    logger = setup_logging()
    
    # Ensure var/ directory structure exists
    ensure_var_directories()
    
    # Create modular daemon with dependency injection
    daemon = await create_daemon(args.socket, args.hot_reload_from)
    
    # Get the current event loop
    loop = asyncio.get_running_loop()
    
    # Setup signal handlers with asyncio integration
    setup_signal_handlers(daemon, loop)
    
    # Start the daemon
    logger.info("Starting modular KSI daemon")
    try:
        await daemon.start()
    except asyncio.CancelledError:
        logger.info("Daemon cancelled, shutting down gracefully")
    finally:
        # Ensure cleanup happens
        logger.info("Final cleanup...")
        await asyncio.sleep(0.1)  # Allow final logs to flush

# Make this package executable as a module
if __name__ == '__main__':
    asyncio.run(main())