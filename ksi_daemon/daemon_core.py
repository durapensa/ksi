#!/usr/bin/env python3
"""
Event-Based Daemon Core

Pure module import system with event-driven architecture.
Modules auto-register their handlers at import time via decorators.
"""

import asyncio
from typing import Dict, Any, Optional

from ksi_common.logging import get_bound_logger
from .event_system import EventRouter, get_router
from ksi_daemon.core.reference_event_log import ReferenceEventLog

# Core state management
from ksi_daemon.core.state import initialize_state, get_state_manager

logger = get_bound_logger("daemon_core", version="1.0.0")


class EventDaemonCore:
    """
    Event-based daemon core that uses module imports.
    
    Clean architecture: no complex discovery, no runtime loading - just Pythonic imports.
    Modules auto-register via @event_handler decorators at import time.
    """
    
    def __init__(self):
        self.router = get_router()
        self.running = False
        self.shutdown_event = asyncio.Event()
        
        # State infrastructure - will be initialized in initialize()
        self.state_manager = None
        
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize the daemon by importing all modules."""
        try:
            logger.info("Initializing event daemon core")
            
            # Store reference to daemon core in router for shutdown handling
            self.router._daemon_core = self
            
            # Initialize reference-based event log and attach to router
            logger.info("Initializing reference event log...")
            self.router.reference_event_log = ReferenceEventLog()
            await self.router.reference_event_log.initialize()
            logger.info("Event log initialized and started")
            
            # Initialize state infrastructure first (core dependency)
            logger.info("Initializing core state infrastructure...")
            self.state_manager = initialize_state()
            logger.info("Core state infrastructure initialized")
            
            # Import all modules - handlers auto-register at import time!
            await self._import_all_modules()
            
            # Emit startup event for module initialization
            await self.router.emit("system:startup", config)
            
            # Distribute context to modules with proper async interfaces
            context = {
                "config": config,
                "event_router": self.router,
                "daemon_core": self,
                "emit_event": self.router.emit,  # Proper async event emitter
                "shutdown_event": self.shutdown_event,  # Shutdown coordination
                "state_manager": self.state_manager,  # Core state management
                "async_state": self.state_manager  # Async state operations via same manager
            }
            # Pass infrastructure context to modules
            # Note: We don't pass router or daemon_core to avoid JSON serialization issues in event log
            safe_context = {
                "config": config,
                "emit_event": self.router.emit,  # Proper async event emitter
                "shutdown_event": self.shutdown_event,  # Shutdown coordination
                "state_manager": self.state_manager,  # Core state management
                "async_state": self.state_manager  # Async state operations via same manager
            }
            await self.router.emit("system:context", safe_context)
            
            # Collect background tasks from modules
            logger.info("Collecting background tasks from modules...")
            ready_responses = await self.router.emit("system:ready", {})
            
            # Start all collected background tasks
            for response in ready_responses:
                if isinstance(response, dict) and "tasks" in response:
                    service_name = response.get("service", "unknown")
                    for task_spec in response["tasks"]:
                        task_name = task_spec["name"]
                        coroutine = task_spec["coroutine"]
                        
                        full_task_name = f"{service_name}:{task_name}"
                        logger.info(f"Starting background task: {full_task_name}")
                        
                        # Start the background task
                        await self.router.start_task(full_task_name, coroutine)
            
            logger.info(f"Started {len(self.router._tasks)} background tasks")
            
            self.running = True
            logger.info(f"Daemon core initialized with {len(self.router.get_modules())} modules")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize daemon core: {e}")
            return False
    
    async def _import_all_modules(self):
        """Import all modules - they self-register via decorators."""
        logger.info("Importing all modules...")
        
        # Core modules (dependency order: state first, then others)
        import ksi_daemon.core.state        # Core dependency - other modules use state
        import ksi_daemon.core.health
        import ksi_daemon.core.correlation  
        import ksi_daemon.core.discovery
        import ksi_daemon.core.monitor
        import ksi_daemon.core.checkpoint   # Dev mode checkpoint/restore
        import ksi_daemon.core.event_log_handlers  # Event log query handlers
        
        # Transport modules
        import ksi_daemon.transport.unix_socket
        
        # Completion modules
        import ksi_daemon.completion.completion_service
        import ksi_daemon.completion.claude_cli_litellm_provider
        import ksi_daemon.completion.litellm
        
        # Permission modules
        import ksi_daemon.permissions.permission_service
        
        # Agent modules
        import ksi_daemon.agent.agent_service
        
        # Observation modules
        import ksi_daemon.observation.observation_manager
        import ksi_daemon.observation.replay
        import ksi_daemon.observation.historical
        
        # Messaging modules
        import ksi_daemon.messaging.message_bus
        
        # Transformer management (extends event system)
        import ksi_daemon.transformer.transformer_service
        
        # Orchestration modules
        import ksi_daemon.orchestration.orchestration_service
        
        # Composition modules
        import ksi_daemon.composition.composition_service
        
        # Conversation modules
        import ksi_daemon.conversation.conversation_service
        import ksi_daemon.conversation.conversation_lock
        
        # Injection modules
        import ksi_daemon.injection.injection_router
        
        # Config modules
        import ksi_daemon.config.config_service
        
        # MCP modules
        import ksi_daemon.mcp.mcp_service
        
        # Evaluation modules
        import ksi_daemon.evaluation.prompt_evaluation
        import ksi_daemon.evaluation.tournament_bootstrap_integration
        
        logger.info("All modules imported and auto-registered")
    
    async def handle_event(self, event_name: str, data: dict, context: dict) -> Any:
        """Handle an event through the router."""
        return await self.router.emit_first(event_name, data, context)
    
    async def run(self):
        """Run the daemon until shutdown event is set."""
        logger.info("Event daemon core running...")
        
        try:
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            logger.info("Shutdown event received")
        except asyncio.CancelledError:
            logger.info("Daemon run cancelled")
            raise
    
    async def shutdown(self):
        """Shutdown the daemon cleanly using coordinated shutdown protocol."""
        if not self.running:
            return
            
        logger.info("Shutting down daemon core")
        
        try:
            # Set shutdown event to stop main loop
            self.shutdown_event.set()
            
            # Begin coordinated shutdown
            await self.router.begin_shutdown()
            
            # Emit shutdown event to all handlers (including critical ones)
            await self.router.emit("system:shutdown", {})
            
            # Wait for all critical services to acknowledge shutdown
            logger.info("Waiting for critical services to complete shutdown tasks...")
            all_acknowledged = await self.router.wait_for_shutdown_acknowledgments()
            
            if not all_acknowledged:
                logger.warning("Some services did not acknowledge shutdown in time")
            
            # Now safe to stop background tasks
            logger.info("Stopping background tasks...")
            await self.router.stop_all_tasks()
            
            # Reference event log is file-based and doesn't need explicit cleanup
            
            self.running = False
            logger.info("Daemon core shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
    
    # Discovery/Introspection API
    
    def get_modules(self) -> Dict[str, Any]:
        """Get all loaded modules."""
        return self.router.get_modules()
    
    def get_events(self) -> Dict[str, Any]:
        """Get all registered events."""
        return self.router.get_events()
    
    def get_services(self) -> Dict[str, Any]:
        """Get all registered services."""
        return self.router.get_services()
    
    def inspect_module(self, module_name: str) -> Optional[Dict[str, Any]]:
        """Inspect a specific module using direct function metadata."""
        return self.router.inspect_module(module_name)


# Add built-in discovery handlers for introspection
from .event_system import event_handler, EventPriority

@event_handler("system:shutdown", priority=EventPriority.HIGHEST)  # Use HIGHEST to run before other handlers
async def handle_shutdown_request(data: Dict[str, Any]) -> None:
    """Handle external shutdown request by setting shutdown event.
    
    This handler responds to external shutdown requests (e.g. from daemon_control)
    by setting the shutdown event. The main daemon wrapper will then call shutdown()
    which performs the coordinated shutdown sequence.
    """
    # Get the daemon core instance from the router
    router = get_router()
    if hasattr(router, '_daemon_core') and router._daemon_core:
        # Only set the event if we're not already shutting down
        # This prevents recursion when shutdown() emits system:shutdown
        if router._daemon_core.running and not router._daemon_core.shutdown_event.is_set():
            logger.info("Received system:shutdown request, setting shutdown event")
            router._daemon_core.shutdown_event.set()
        else:
            logger.debug("Ignoring system:shutdown - already shutting down")
    else:
        logger.warning("No daemon core reference available for shutdown")

@event_handler("shutdown:acknowledge")
async def handle_shutdown_acknowledge(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle shutdown acknowledgment from a service.
    
    Expected data:
        service_name: Name of the service acknowledging shutdown
    """
    service_name = data.get("service_name")
    if not service_name:
        return {"error": "Missing service_name"}
    
    router = get_router()
    await router.acknowledge_shutdown(service_name)
    return {"acknowledged": service_name}

@event_handler("module:list")
async def handle_list_modules(data: Dict[str, Any]) -> Dict[str, Any]:
    """List all loaded modules."""
    router = get_router()
    modules = router.get_modules()
    
    return {
        "modules": [
            {
                "name": name,
                "handlers": len(info["handlers"]),
                "services": len(info["services"]),
                "tasks": len(info["background_tasks"])
            }
            for name, info in modules.items()
        ],
        "count": len(modules)
    }


@event_handler("module:events")
async def handle_list_events(data: Dict[str, Any]) -> Dict[str, Any]:
    """List all registered events and patterns."""
    router = get_router()
    events = router.get_events()
    
    return {
        "events": events["direct_events"],
        "patterns": events["pattern_events"], 
        "total_events": events["total_events"],
        "total_patterns": events["total_patterns"]
    }


@event_handler("module:inspect")
async def handle_inspect_module(data: Dict[str, Any]) -> Dict[str, Any]:
    """Inspect a specific module using direct function metadata."""
    router = get_router()
    module_name = data.get("module_name")
    
    if not module_name:
        return {"error": "Missing module_name parameter"}
    
    # Get module info with direct function inspection
    info = router.inspect_module(module_name)
    if not info:
        return {"error": f"Module not found: {module_name}"}
    
    return {"module": info}



@event_handler("system:health")
async def handle_system_health(data: Dict[str, Any]) -> Dict[str, Any]:
    """System health check including module status.""" 
    import time
    
    router = get_router()
    modules = router.get_modules()
    services = router.get_services()
    
    # Get uptime from daemon start time (stored on router if available)
    uptime = getattr(router, '_start_time', None)
    if uptime:
        uptime = time.time() - uptime
    else:
        uptime = 0
    
    return {
        "status": "healthy",
        "uptime": uptime,
        "version": "3.0.0",  # Event-based daemon version
        "modules_loaded": len(modules),
        "services_registered": services["total"],
        "events_registered": len(router._handlers),
        "background_tasks": len(router._tasks),
        "modules": list(modules.keys())
    }