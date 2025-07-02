#!/usr/bin/env python3
"""
Event-Based KSI Daemon Core

Main daemon orchestration using pure event system.
Replaces pluggy-based core_plugin.py.
"""

import asyncio
import signal
from pathlib import Path
from typing import Dict, Any, Optional, List

from ksi_common.logging import get_bound_logger
from ksi_common.config import config

from .event_system import EventRouter, event_handler
from .plugin_loader_events import EventPluginLoader
from .event_router import SimpleEventRouter  # Keep for transport compatibility

# Import infrastructure modules
from .infrastructure.state import session_state, async_state
from .infrastructure.composition import index as composition_index

logger = get_bound_logger("core_events", version="3.0.0")

# Global KSI context cache for agent spawning
_global_ksi_context_cache = {}
_daemon_core_instance = None


class EventDaemonCore:
    """
    Pure event-based daemon core.
    """
    
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        """Initialize the daemon core."""
        # Use provided config or default
        self.config = config
        self.running = False
        
        # Create event router
        self.event_router = EventRouter()
        
        # Create plugin loader with router
        self.plugin_loader = EventPluginLoader(
            self.event_router,
            plugin_dirs=[Path(__file__).parent / "plugins"]
        )
        
        # Compatibility: Create SimpleEventRouter wrapper for transports
        self.simple_router = SimpleEventRouter(self.plugin_loader)
        
        # Shutdown event for graceful termination
        self.shutdown_event = asyncio.Event()
        
        # Infrastructure instances
        self.state_manager = None
        self.composition_index = None
        
        # KSI context cache for agent spawning
        self.ksi_context_cache = {}
        
        # Register core event handlers
        self._register_core_handlers()
    
    def _register_core_handlers(self):
        """Register core system event handlers."""
        
        @event_handler("system:shutdown_requested")
        async def handle_shutdown_request(data: Dict[str, Any]):
            """Handle shutdown requests."""
            logger.info("Shutdown requested via event")
            self.shutdown_event.set()
            
        # Register with router
        self.event_router.register_handler(
            "system:shutdown_requested",
            handle_shutdown_request._event_handler
        )
    
    async def initialize(self) -> None:
        """Initialize the daemon."""
        logger.info("Initializing event-based daemon")
        
        # Initialize infrastructure before plugins
        logger.info("Initializing infrastructure...")
        
        # Initialize state infrastructure
        self.state_manager = session_state.SessionAndSharedStateManager()
        
        # Initialize async state
        async_state.initialize()
        
        # Initialize composition index
        composition_index.initialize()
        
        logger.info("Infrastructure initialized")
        
        # Load all plugins
        plugins = await self.plugin_loader.load_all_plugins()
        logger.info(f"Loaded {len(plugins)} plugins", plugins=plugins)
        
        # Initialize plugins (replaces ksi_startup)
        await self.plugin_loader.initialize_plugins(self.config.__dict__)
        
        # Distribute context to plugins (replaces ksi_plugin_context)
        plugin_context = {
            "event_router": self.event_router,
            "emit_event": self.event_router.emit,
            "emit_event_first": self.event_router.emit_first,
            "get_service": self.event_router.get_service,
            "shutdown_event": self.shutdown_event,
            # Infrastructure services
            "state_manager": self.state_manager,
            "async_state": async_state,
            "composition_index": composition_index,
            # Compatibility
            "plugin_manager": self.plugin_loader  # For introspection
        }
        
        await self.plugin_loader.distribute_context(plugin_context)
        
        # Cache KSI context for agent spawning
        await self._cache_ksi_context()
        
        # Initialize transports via event
        await self.event_router.emit("transport:initialize", {
            "transports": {
                "unix": {
                    "enabled": True,
                    "socket_dir": str(self.config.socket_path.parent)
                }
            }
        })
        
        # For compatibility, also initialize via simple router
        await self.simple_router.initialize_transports({
            "transports": {
                "unix": {
                    "enabled": True,
                    "socket_dir": str(self.config.socket_path.parent)
                }
            }
        })
        
        logger.info("Event daemon initialized")
        
        # Store instance globally for context access
        global _daemon_core_instance
        _daemon_core_instance = self
    
    async def run(self) -> None:
        """Run the daemon main loop."""
        self.running = True
        logger.info("Event daemon starting")
        
        try:
            # Setup signal handlers
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig, 
                    lambda s=sig: self._handle_signal(s)
                )
            
            # Start plugin background tasks (replaces ksi_ready)
            await self.plugin_loader.start_plugin_tasks()
            
            logger.info("Event daemon ready - all tasks started")
            
            # Run until shutdown
            await self.shutdown_event.wait()
            
        except Exception as e:
            logger.error(f"Error in daemon run loop: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()
    
    def _handle_signal(self, signum: int) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}")
        self.shutdown_event.set()
    
    async def shutdown(self) -> None:
        """Shutdown the daemon cleanly."""
        if not self.running:
            return
            
        logger.info("Event daemon shutting down")
        self.running = False
        
        # Shutdown plugins (stops tasks and emits shutdown event)
        await self.plugin_loader.shutdown_plugins()
        
        # Shutdown transports
        if self.simple_router:
            await self.simple_router.shutdown()
        
        # Emit final shutdown complete event
        await self.event_router.emit("system:shutdown_complete", {})
        
        logger.info("Event daemon shutdown complete")
    
    async def _cache_ksi_context(self) -> None:
        """Cache KSI context for agent spawning."""
        try:
            # Build minimal context needed for agents
            context = {
                "emit_event": self.event_router.emit,
                "get_service": self.event_router.get_service,
                "state_manager": self.state_manager,
                "async_state": async_state,
            }
            
            # Store in instance
            self.ksi_context_cache = context
            
            # Update global cache
            global _global_ksi_context_cache
            _global_ksi_context_cache = context
            
            logger.info("Cached KSI context for agent spawning")
            
        except Exception as e:
            logger.error(f"Failed to cache KSI context: {e}")
    
    # Compatibility method
    def handle_shutdown(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals (compatibility)."""
        self._handle_signal(signum)


def get_daemon_instance() -> Optional[EventDaemonCore]:
    """Get the current daemon instance."""
    return _daemon_core_instance


def get_ksi_context() -> Dict[str, Any]:
    """Get cached KSI context for agent spawning."""
    return _global_ksi_context_cache.copy()


# Main entry point
async def main(config_dict: Optional[Dict[str, Any]] = None) -> None:
    """Main entry point for the event daemon."""
    daemon = EventDaemonCore(config_dict)
    
    try:
        await daemon.initialize()
        await daemon.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Daemon error: {e}", exc_info=True)
        raise
    finally:
        await daemon.shutdown()


if __name__ == "__main__":
    import sys
    
    # Run the daemon
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception:
        sys.exit(1)