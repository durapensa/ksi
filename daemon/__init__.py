#!/usr/bin/env python3

"""
Modular Daemon Package - Main entry point and dependency injection
Extracted from daemon_clean.py with 100% functionality preservation
"""

import asyncio
import argparse
import logging
import signal
from pathlib import Path

# Import all modules
from .core import ClaudeDaemonCore
from .state_manager import StateManager
from .claude_process import ClaudeProcessManager
from .agent_manager import AgentManager
from .utils import UtilsManager
from .hot_reload import HotReloadManager
from .command_handler import CommandHandler

def parse_args():
    """Parse command line arguments - EXACT copy from daemon_clean.py"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--socket', default='sockets/claude_daemon.sock')
    parser.add_argument('--hot-reload-from', help='Socket path to reload from')
    return parser.parse_args()

def setup_logging():
    """Set up logging - EXACT copy from daemon_clean.py"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "daemon.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger('daemon')

def setup_signal_handlers(core_daemon):
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        logging.getLogger('daemon').info(f"Received signal {signum}, shutting down...")
        core_daemon.shutdown_event.set()
        
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, signal_handler)
        except ValueError:
            # Can't set signal handler in some contexts (like threads)
            pass

async def create_daemon(socket_path: str, hot_reload_from: str = None):
    """Create and wire together all daemon modules with dependency injection"""
    
    # Create core daemon
    core_daemon = ClaudeDaemonCore(socket_path, hot_reload_from)
    
    # Create all managers
    state_manager = StateManager()
    process_manager = ClaudeProcessManager(state_manager=state_manager)
    agent_manager = AgentManager(process_manager=process_manager)
    utils_manager = UtilsManager(state_manager=state_manager)
    hot_reload_manager = HotReloadManager(core_daemon, state_manager, agent_manager)
    
    # Create command handler with all dependencies
    command_handler = CommandHandler(
        core_daemon=core_daemon,
        state_manager=state_manager,
        process_manager=process_manager,
        agent_manager=agent_manager,
        utils_manager=utils_manager,
        hot_reload_manager=hot_reload_manager
    )
    
    # Wire everything together via dependency injection
    core_daemon.set_managers(
        state_manager=state_manager,
        process_manager=process_manager,
        agent_manager=agent_manager,
        utils_manager=utils_manager,
        hot_reload_manager=hot_reload_manager,
        command_handler=command_handler
    )
    
    # Set up cross-manager dependencies
    process_manager.utils_manager = utils_manager
    
    return core_daemon

async def main():
    """Main entry point - EXACT logic from daemon_clean.py adapted for modular architecture"""
    args = parse_args()
    logger = setup_logging()
    
    # Create modular daemon with dependency injection
    daemon = await create_daemon(args.socket, args.hot_reload_from)
    
    # Setup signal handlers
    setup_signal_handlers(daemon)
    
    # Start the daemon
    logger.info("Starting modular Claude daemon")
    await daemon.start()

# Make this package executable as a module
if __name__ == '__main__':
    asyncio.run(main())