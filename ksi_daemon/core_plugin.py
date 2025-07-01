#!/usr/bin/env python3
"""
Simplified KSI Daemon Core Plugin

Main daemon orchestration without complex inheritance and event layers.
"""

import asyncio
import signal
from pathlib import Path
from typing import Dict, Any, Optional

import pluggy
from ksi_common.logging import get_bound_logger

from ksi_common.config import config
from .plugin_loader_simple import SimplePluginLoader
from .event_router import SimpleEventRouter

# Import infrastructure modules
from .infrastructure.state import session_state, async_state
from .infrastructure.composition import index as composition_index

logger = get_bound_logger("core_plugin", version="2.0.0")

# Global KSI context cache for agent spawning
_global_ksi_context_cache = {}
_daemon_core_instance = None


class SimpleDaemonCore:
    """
    Simplified daemon core that directly manages plugins and routing.
    """
    
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        """Initialize the daemon core."""
        # Use provided config or default
        if config_dict:
            # Update config from dict if needed (future enhancement)
            self.config = config
        else:
            self.config = config
        self.running = False
        self.event_router = None
        
        # Initialize plugin system
        self.plugin_loader = SimplePluginLoader(
            plugin_dirs=[Path(__file__).parent / "plugins"]
        )
        
        # Track async coroutines for asyncio structured concurrency
        self.async_coroutines = []
        
        # Shutdown event for graceful termination
        self.shutdown_event = asyncio.Event()
        
        # Infrastructure instances
        self.state_manager = None
        self.composition_index = None
        
        # KSI context cache for agent spawning
        self.ksi_context_cache = {}
    
    async def initialize(self) -> None:
        """Initialize the daemon."""
        logger.info("Initializing plugin daemon")
        
        # Initialize infrastructure before plugins
        logger.info("Initializing infrastructure...")
        
        # Initialize state infrastructure
        self.state_manager = session_state.SessionAndSharedStateManager()
        
        # Initialize async state
        async_state.initialize()  # Uses config.async_state_db_path
        
        # Initialize composition index
        composition_index.initialize()  # Uses config.db_path
        
        logger.info("Infrastructure initialized")
        
        # Load plugins
        plugins = self.plugin_loader.load_all_plugins()
        logger.info(f"Loaded {len(plugins)} plugins", plugins=plugins)
        
        # Create simplified event router
        self.event_router = SimpleEventRouter(self.plugin_loader)
        
        # Call startup hooks
        startup_results = self.plugin_loader.pm.hook.ksi_startup(
            config=self.config  # Pass the actual config object
        )
        
        for result in startup_results:
            if result:
                logger.info("Startup result", result=result)
        
        # Pass context to plugins (minimal, following pluggy best practices)
        plugin_context = {
            "event_router": self.event_router,  # For monitoring plugins
            "emit_event": self.event_router.route_event,  # Standardized event emission
            "plugin_manager": self.plugin_loader.pm,  # Pluggy plugin manager (single source)
            "shutdown_event": self.shutdown_event,  # Allow plugins to trigger shutdown
            # Infrastructure services
            "state_manager": self.state_manager,
            "async_state": async_state,  # Module with functional interface
            "composition_index": composition_index  # Module with functional interface
        }
        
        try:
            self.plugin_loader.pm.hook.ksi_plugin_context(
                context=plugin_context
            )
            logger.info("Plugin context passed to all plugins")
        except (AttributeError, TypeError) as e:
            logger.warning(f"Failed to pass plugin context: {e}")
            # Don't fail startup - this is optional
        
        # Cache KSI context for agent spawning after all plugins initialized
        await self._cache_ksi_context()
        
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
        
        # Store instance globally for context access
        global _daemon_core_instance
        _daemon_core_instance = self
    
    async def run(self) -> None:
        """Run the daemon main loop with proper sync/async separation."""
        self.running = True
        logger.info("Plugin daemon starting")
        
        try:
            # PHASE 1: SYNC OPERATIONS (pluggy best practices)
            # Setup signal handlers - set shutdown event directly for fast response
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig, 
                    lambda s=sig: self._handle_signal_sync(s)
                )
            
            # Call ksi_ready hooks - plugins return coroutines to start
            try:
                logger.info("Calling ksi_ready hooks...")
                ready_results = self.plugin_loader.pm.hook.ksi_ready()
                logger.info(f"Got {len(ready_results)} results from ksi_ready hooks")
                
                # Collect coroutines from plugins
                self.async_coroutines = []
                for result in ready_results:
                    if result and isinstance(result, dict) and "tasks" in result:
                        service_name = result.get("service", "unknown")
                        logger.info(f"Service {service_name} returned {len(result['tasks'])} tasks")
                        for task_spec in result["tasks"]:
                            task_name = task_spec.get("name", "unnamed")
                            coroutine = task_spec.get("coroutine")
                            if coroutine:
                                self.async_coroutines.append({
                                    "coroutine": coroutine,
                                    "service": service_name,
                                    "name": task_name
                                })
                                logger.info(f"Added task {task_name} from service {service_name}")
                
                logger.info(f"Plugin daemon ready - collected {len(self.async_coroutines)} async tasks")
                    
            except (AttributeError, TypeError, ValueError) as e:
                logger.error(f"Error calling ksi_ready hooks: {e}", exc_info=True)
            
            # Start service tasks with asyncio structured concurrency
            if self.async_coroutines:
                async with asyncio.TaskGroup() as tg:
                    # Start all service coroutines concurrently
                    for coro_spec in self.async_coroutines:
                        coroutine = coro_spec["coroutine"]
                        
                        # Create the task
                        tg.create_task(coroutine)
                    
                    # Add shutdown monitor as another service task
                    async def shutdown_monitor():
                        await self.shutdown_event.wait()
                        logger.info("Shutdown event received, cancelling services")
                        # In asyncio.TaskGroup, we cancel all tasks by raising CancelledError
                        for task in asyncio.all_tasks():
                            if task is not asyncio.current_task():
                                task.cancel()
                    
                    tg.create_task(shutdown_monitor())
                    
                    logger.info("Daemon services running")
                    # Task group runs until services complete or shutdown cancels them
            else:
                logger.warning("No async services to run, waiting for shutdown")
                await self.shutdown_event.wait()
            
        except* asyncio.CancelledError:
            # This is expected during shutdown - don't log as error
            logger.info("Services cancelled during shutdown")
        except* Exception as eg:
            # TaskGroup can raise ExceptionGroup when tasks fail
            logger.error("Daemon task group error", error=str(eg), exc_info=True)
        finally:
            await self.shutdown()
    
    def _handle_signal_sync(self, signum: int) -> None:
        """Handle system signals synchronously - called from signal handler."""
        logger.info(f"Received signal {signum}, setting shutdown event directly")
        self.shutdown_event.set()
    
    async def _cache_ksi_context(self) -> None:
        """Cache KSI context for agent spawning after all plugins are initialized."""
        try:
            logger.info("Caching KSI context for agent spawning...")
            
            # Get full event discovery
            discovery_result = await self.event_router.route_event("system:discover", {})
            
            if discovery_result and "events" in discovery_result:
                events = discovery_result["events"]
                
                # Cache raw events
                self.ksi_context_cache["daemon_events"] = events
                
                # Extract and cache capabilities
                capabilities = set()
                for namespace_events in events.values():
                    for event in namespace_events:
                        # Extract capabilities from event metadata
                        if event_caps := event.get("capabilities"):
                            capabilities.update(event_caps)
                
                self.ksi_context_cache["ksi_capabilities"] = list(capabilities)
                
                # Format daemon commands for markdown component
                self.ksi_context_cache["daemon_commands"] = self._format_daemon_commands(events)
                
                # Cache summary for logging
                total_events = sum(len(namespace_events) for namespace_events in events.values())
                
                logger.info(f"Cached KSI context: {total_events} events across {len(events)} namespaces")
                
                # Update global cache
                _global_ksi_context_cache.update(self.ksi_context_cache)
                
            else:
                logger.warning("Failed to discover events for KSI context cache")
                # Initialize empty cache
                self.ksi_context_cache = {
                    "daemon_events": {},
                    "ksi_capabilities": [],
                    "daemon_commands": "No events discovered"
                }
                
        except Exception as e:
            logger.error(f"Failed to cache KSI context: {e}", exc_info=True)
            # Initialize empty cache on error
            self.ksi_context_cache = {
                "daemon_events": {},
                "ksi_capabilities": [],
                "daemon_commands": "Error loading events"
            }
    
    def _format_daemon_commands(self, events: Dict[str, Any]) -> str:
        """Format events as markdown for daemon_commands component."""
        lines = ["# Available KSI Daemon Events\n"]
        
        for namespace, namespace_events in events.items():
            lines.append(f"## {namespace.title()} Events\n")
            
            for event in namespace_events:
                event_name = event.get("event", "unknown")
                summary = event.get("summary", "No description")
                
                lines.append(f"**{event_name}**: {summary}")
                
                # Add parameters if available
                if params := event.get("parameters"):
                    lines.append("  - Parameters:")
                    for param_name, param_info in params.items():
                        req = "required" if param_info.get("required") else "optional"
                        desc = param_info.get("description", "")
                        lines.append(f"    - `{param_name}` ({req}): {desc}")
                
                lines.append("")  # Empty line between events
            
            lines.append("")  # Empty line between namespaces
        
        return "\n".join(lines)
    
    async def shutdown(self) -> None:
        """Shutdown the daemon."""
        if not self.running:
            return
        
        self.running = False
        logger.info("Plugin daemon shutting down")
        
        try:
            # asyncio TaskGroup handles service cancellation automatically
            
            # Call sync shutdown hooks  
            shutdown_results = self.plugin_loader.pm.hook.ksi_shutdown()
            for result in shutdown_results:
                if result:
                    logger.info("Shutdown result", result=result)
            
            # Shutdown event router
            if self.event_router:
                await self.event_router.shutdown()
            
            logger.info("Plugin daemon stopped")
            
        except (OSError, RuntimeError) as e:
            logger.error("Error during shutdown", error=str(e), exc_info=True)


def get_ksi_context_cache() -> Dict[str, Any]:
    """Get the global KSI context cache for agent spawning."""
    return _global_ksi_context_cache.copy()


def get_ksi_context_variable(var_name: str) -> Any:
    """Get a specific KSI context variable."""
    return _global_ksi_context_cache.get(var_name)


async def run_daemon():
    """Run the simplified daemon."""
    # Ensure directories exist
    config.ensure_directories()
    
    # Logging is already configured by daemon entry point
    # Do NOT add any handlers here - they cause OSError in daemon mode
    
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