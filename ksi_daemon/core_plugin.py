#!/usr/bin/env python3
"""
Simplified KSI Daemon Core Plugin

Main daemon orchestration without complex inheritance and event layers.
"""

import asyncio
import signal
import logging
from pathlib import Path
from typing import Dict, Any, Optional

import pluggy
import structlog

from .config import config
from .plugin_loader import PluginLoader
from .event_router import SimpleEventRouter

logger = structlog.get_logger(__name__)


class SimpleDaemonCore:
    """
    Simplified daemon core that directly manages plugins and routing.
    """
    
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        """Initialize the daemon core."""
        # Use provided config or default
        if config_dict:
            # TODO: Update config from dict if needed
            self.config = config
        else:
            self.config = config
        self.running = False
        self.event_router = None
        
        # Initialize plugin system
        self.plugin_loader = PluginLoader(
            plugin_dirs=[Path(__file__).parent / "plugins"]
        )
        
        # Shutdown event for graceful termination
        self.shutdown_event = asyncio.Event()
    
    async def initialize(self) -> None:
        """Initialize the daemon."""
        logger.info("Initializing plugin daemon")
        
        # Load plugins
        plugins = self.plugin_loader.load_all_plugins()
        logger.info(f"Loaded {len(plugins)} plugins", plugins=plugins)
        
        # Create simplified event router
        self.event_router = SimpleEventRouter(self.plugin_loader)
        
        # Call startup hooks
        startup_results = self.plugin_loader.pm.hook.ksi_startup(
            config={}  # Use empty dict for now since config is not a model
        )
        
        for result in startup_results:
            if result:
                logger.info("Startup result", result=result)
        
        # Pass context to plugins (including event_router for monitoring)
        plugin_context = {
            "event_router": self.event_router,
            "emit_event": None  # Could be added later for real-time events
        }
        
        try:
            self.plugin_loader.pm.hook.ksi_plugin_context(
                context=plugin_context
            )
            logger.info("Plugin context passed to all plugins")
        except Exception as e:
            logger.warning(f"Failed to pass plugin context: {e}")
            # Don't fail startup - this is optional
        
        # Initialize transports
        await self.event_router.initialize_transports({
            "transports": {
                "unix": {
                    "enabled": True,
                    "socket_dir": str(self.config.socket_path.parent)
                }
            }
        })
        
        logger.info("Plugin daemon initialized")
    
    async def run(self) -> None:
        """Run the daemon main loop."""
        self.running = True
        logger.info("Plugin daemon starting")
        
        try:
            # Setup signal handlers
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig, lambda s=sig: asyncio.create_task(self._handle_signal(s))
                )
            
            # Wait for shutdown
            await self.shutdown_event.wait()
            
        except Exception as e:
            logger.error("Daemon error", error=str(e), exc_info=True)
        finally:
            await self.shutdown()
    
    async def _handle_signal(self, signum: int) -> None:
        """Handle system signals."""
        logger.info(f"Received signal {signum}")
        self.shutdown_event.set()
    
    async def shutdown(self) -> None:
        """Shutdown the daemon."""
        if not self.running:
            return
        
        self.running = False
        logger.info("Plugin daemon shutting down")
        
        try:
            # Call shutdown hooks
            shutdown_results = self.plugin_loader.pm.hook.ksi_shutdown()
            for result in shutdown_results:
                if result:
                    logger.info("Shutdown result", result=result)
            
            # Shutdown event router
            if self.event_router:
                await self.event_router.shutdown()
            
            logger.info("Plugin daemon stopped")
            
        except Exception as e:
            logger.error("Error during shutdown", error=str(e), exc_info=True)


async def run_daemon():
    """Run the simplified daemon."""
    # Ensure directories exist
    config.ensure_directories()
    
    # Configure logging
    logging.basicConfig(
        level=config.get_log_level(),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.get_log_file_path()),
            logging.StreamHandler()
        ]
    )
    
    # Create and run daemon
    daemon = SimpleDaemonCore()
    await daemon.initialize()
    await daemon.run()


# Direct event routing hook
hookimpl = pluggy.HookimplMarker("ksi")

@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Handle core daemon events."""
    
    # System shutdown
    if event_name == "system:shutdown":
        logger.info("Shutdown requested via event")
        # Get the daemon instance if available
        if hasattr(SimpleDaemonCore, '_instance') and SimpleDaemonCore._instance:
            SimpleDaemonCore._instance.shutdown_event.set()
        return {"status": "shutdown_initiated"}
    
    # Daemon status
    elif event_name == "daemon:status":
        return {
            "status": "running",
            "version": "2.0.0",
            "simplified": True
        }
    
    return None