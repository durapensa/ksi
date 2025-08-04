#!/usr/bin/env python3
"""
Event-Based Daemon Core

Pure module import system with event-driven architecture.
Modules auto-register their handlers at import time via decorators.
"""

import asyncio
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, TypedDict
from typing_extensions import NotRequired, Required

from ksi_common.logging import get_bound_logger
from ksi_common.config import config
from .event_system import EventRouter, get_router
from ksi_daemon.core.reference_event_log import ReferenceEventLog
from ksi_daemon.core.context_manager import get_context_manager

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
            
            # Rotate daemon log on startup for cleaner log management
            await self._rotate_daemon_log()
            
            # Store reference to daemon core in router for shutdown handling
            self.router._daemon_core = self
            
            # Initialize context manager first (PYTHONIC CONTEXT REFACTOR)
            logger.info("Initializing context manager...")
            context_manager = get_context_manager()
            await context_manager.initialize()
            logger.info("Context manager initialized with hot and cold storage")
            
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
            
            # Load critical system transformers after modules are loaded
            await self._load_system_transformers()
            
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
            # PYTHONIC CONTEXT REFACTOR: Use minimal component registry
            from ksi_daemon.core.system_registry import SystemRegistry
            
            # Register system components in lightweight runtime registry
            SystemRegistry.set("state_manager", self.state_manager)
            SystemRegistry.set("event_emitter", self.router.emit)
            SystemRegistry.set("shutdown_event", self.shutdown_event)
            
            # Pass minimal context - just config and registry availability
            safe_context = {
                "config": config,
                "registry_available": True,
                "_skip_log": True  # Don't log this internal plumbing event
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
            
            # Start configured transports using new transport system
            if 'transports' in config:
                from ksi_daemon.transport import start_transports
                await start_transports()
                logger.info("Started configured transports")
            
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
        
        # Transport modules - import all available transports
        import ksi_daemon.transport.unix_socket
        import ksi_daemon.transport.websocket
        
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
        
        # Composition modules
        import ksi_daemon.composition.composition_service
        
        # Conversation modules
        import ksi_daemon.conversation.conversation_service
        import ksi_daemon.conversation.conversation_lock
        
        # Injection modules
        import ksi_daemon.injection.injection_router
        
        # Config modules
        import ksi_daemon.config.config_service
        import ksi_daemon.config.runtime_config
        
        # MCP modules
        import ksi_daemon.mcp.mcp_service
        
        # Evaluation modules (cleaned up - now just thin certification infrastructure)
        import ksi_daemon.evaluation
        
        # Optimization modules
        import ksi_daemon.optimization.optimization_service
        
        # Scheduler module (event scheduling and TTL)
        import ksi_daemon.scheduler.scheduler_events
        
        # Context system modules
        import ksi_daemon.core.context_service
        
        # Introspection modules
        import ksi_daemon.introspection
        
        # Routing modules (dynamic routing control)
        import ksi_daemon.routing.routing_service
        import ksi_daemon.routing.routing_events
        import ksi_daemon.routing.parent_cleanup_handlers
        
        logger.info("All modules imported and auto-registered")
    
    async def _load_system_transformers(self):
        """Load critical system transformers that must be available on startup."""
        import yaml
        from pathlib import Path
        
        logger.info("Loading system transformers...")
        
        # Define critical system transformers that must be auto-loaded
        system_transformers = [
            {
                "name": "universal_broadcast",
                "config": {
                    "source": "*",  # Match ALL events
                    "target": "monitor:broadcast_event",
                    "condition": "not (source_event.startswith('transport:') or source_event == 'monitor:subscribe' or source_event == 'monitor:broadcast_event')",
                    "mapping": {
                        "event_name": "{{_ksi_context.event}}",
                        "event_data": "{{$}}",
                        "broadcast_metadata": {
                            "originator_agent": "{{_ksi_context._agent_id|system}}",
                            "timestamp": "{{timestamp_utc()}}",
                            "subscription_required": True
                        }
                    },
                    "async": True
                }
            }
            # Additional system transformers can be added here
        ]
        
        # Load inline system transformers
        for transformer in system_transformers:
            try:
                self.router.register_transformer_from_yaml(transformer["config"])
                logger.info(f"Auto-loaded system transformer: {transformer['name']}")
            except Exception as e:
                logger.error(f"Failed to load system transformer {transformer['name']}: {e}")
        
        # Load SYSTEM-LEVEL transformer files from var/lib/transformers/system/
        # Other transformers should be loaded by their respective services
        system_transformers_dir = Path("var/lib/transformers/system")
        if system_transformers_dir.exists():
            logger.info(f"Loading system transformers from {system_transformers_dir}")
            for yaml_file in system_transformers_dir.glob("*.yaml"):
                try:
                    with open(yaml_file, 'r') as f:
                        # Use safe_load_all to handle multiple YAML documents
                        documents = list(yaml.safe_load_all(f))
                    
                    # Handle both formats: single doc with 'transformers' key or multiple docs
                    if len(documents) == 1 and isinstance(documents[0], dict) and 'transformers' in documents[0]:
                        # Traditional format: {"transformers": [...]}
                        for transformer_config in documents[0]['transformers']:
                            self.router.register_transformer_from_yaml(transformer_config)
                            logger.info(f"Loaded system transformer '{transformer_config.get('name', 'unnamed')}' from {yaml_file.name}")
                    else:
                        # Multi-document format or direct transformer definitions
                        loaded_count = 0
                        for doc in documents:
                            if isinstance(doc, dict) and 'source' in doc and 'target' in doc:
                                # This is a transformer definition
                                self.router.register_transformer_from_yaml(doc)
                                logger.info(f"Loaded system transformer '{doc.get('name', 'unnamed')}' from {yaml_file.name}")
                                loaded_count += 1
                            elif isinstance(doc, list):
                                # List of transformers
                                for transformer_config in doc:
                                    if isinstance(transformer_config, dict) and 'source' in transformer_config:
                                        self.router.register_transformer_from_yaml(transformer_config)
                                        logger.info(f"Loaded system transformer '{transformer_config.get('name', 'unnamed')}' from {yaml_file.name}")
                                        loaded_count += 1
                        
                        if loaded_count == 0:
                            logger.warning(f"No valid transformers found in {yaml_file}")
                        
                except Exception as e:
                    logger.error(f"Failed to load system transformer from {yaml_file}: {e}")
        else:
            logger.debug(f"System transformers directory {system_transformers_dir} does not exist")
        
        logger.info(f"System transformer auto-loading complete")
    
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
            
            # Stop transports first
            from ksi_daemon.transport import stop_transports
            await stop_transports()
            logger.info("Stopped all transports")
            
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
            
            # Shutdown context manager (PYTHONIC CONTEXT REFACTOR)
            logger.info("Shutting down context manager...")
            context_manager = get_context_manager()
            await context_manager.shutdown()
            
            # Reference event log is file-based and doesn't need explicit cleanup
            
            # Rotate daemon log on shutdown for cleaner log management
            await self._rotate_daemon_log()
            
            self.running = False
            logger.info("Daemon core shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
    
    async def _rotate_daemon_log(self):
        """Rotate the daemon log file on startup/shutdown or when size limit exceeded."""
        try:
            # Get current daemon log path
            daemon_log_path = config.daemon_log_file
            
            if not daemon_log_path.exists():
                logger.debug(f"No {daemon_log_path.name} file to rotate")
                return
            
            # Check file size (default 100MB limit)
            max_size = getattr(config, 'daemon_log_max_size', 100 * 1024 * 1024)  # 100MB default
            current_size = daemon_log_path.stat().st_size
            
            # Only rotate if file exists and is non-empty (or exceeds size limit)
            if current_size == 0:
                logger.debug(f"Log file is empty, no rotation needed")
                return
            
            # Log size info
            size_mb = current_size / (1024 * 1024)
            logger.info(f"Current log size: {size_mb:.2f}MB")
            
            # Create timestamp for rotated log
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Keep the same extension as the original log file
            base_name = daemon_log_path.stem  # Gets 'daemon.log' from 'daemon.log.jsonl'
            extension = daemon_log_path.suffix  # Gets '.jsonl'
            rotated_log_path = daemon_log_path.parent / f"{base_name}_{timestamp}{extension}"
            
            # Move (not copy) the current log to the rotated name
            shutil.move(str(daemon_log_path), str(rotated_log_path))
            
            logger.info(f"Rotated daemon log to {rotated_log_path} ({size_mb:.2f}MB)")
            
            # If we're rotating on startup, the logging system will create a new file
            # If we're rotating on shutdown, we don't need a new file
            
        except Exception as e:
            logger.error(f"Failed to rotate daemon log: {e}")
    
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


# TypedDict definitions for event handlers

class SystemShutdownData(TypedDict):
    """System shutdown notification."""
    # No specific fields for shutdown
    pass


class ShutdownAcknowledgeData(TypedDict):
    """Handle shutdown acknowledgment from a service."""
    service_name: Required[str]  # Name of the service acknowledging shutdown


class ModuleListData(TypedDict):
    """List all loaded modules."""
    # No specific fields - returns all modules
    pass


class ModuleEventsData(TypedDict):
    """List all registered events and patterns."""
    # No specific fields - returns all events
    pass


class ModuleInspectData(TypedDict):
    """Inspect a specific module."""
    module_name: Required[str]  # Module name to inspect


class SystemHealthData(TypedDict):
    """System health check including module status."""
    # No specific fields - returns health status
    pass

@event_handler("system:shutdown", priority=EventPriority.HIGHEST)  # Use HIGHEST to run before other handlers
async def handle_shutdown_request(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Handle external shutdown request by setting shutdown event.
    
    This handler responds to external shutdown requests (e.g. from daemon_control)
    by setting the shutdown event. The main daemon wrapper will then call shutdown()
    which performs the coordinated shutdown sequence.
    """
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder
    # Get the daemon core instance from the router
    router = get_router()
    if hasattr(router, '_daemon_core') and router._daemon_core:
        # Only set the event if we're not already shutting down
        # This prevents recursion when shutdown() emits system:shutdown
        if router._daemon_core.running and not router._daemon_core.shutdown_event.is_set():
            logger.info("Received system:shutdown request, setting shutdown event")
            router._daemon_core.shutdown_event.set()
            return event_response_builder(
                {"shutdown_initiated": True},
                context=context
            )
        else:
            logger.debug("Ignoring system:shutdown - already shutting down")
            return event_response_builder(
                {"shutdown_initiated": False, "reason": "already_shutting_down"},
                context=context
            )
    else:
        logger.warning("No daemon core reference available for shutdown")
        return event_response_builder(
            {"shutdown_initiated": False, "reason": "no_daemon_core"},
            context=context
        )

@event_handler("shutdown:acknowledge")
async def handle_shutdown_acknowledge(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Handle shutdown acknowledgment from a service."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    service_name = data.get("service_name")
    if not service_name:
        return error_response(
            "Missing service_name",
            context=context
        )
    
    router = get_router()
    await router.acknowledge_shutdown(service_name)
    return event_response_builder(
        {"acknowledged": service_name},
        context=context
    )

@event_handler("module:list")
async def handle_list_modules(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """List all loaded modules."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder
    router = get_router()
    modules = router.get_modules()
    
    return event_response_builder(
        {
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
        },
        context=context
    )


@event_handler("module:events")
async def handle_list_events(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """List all registered events and patterns."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder
    router = get_router()
    events = router.get_events()
    
    return event_response_builder(
        {
            "events": events["direct_events"],
            "patterns": events["pattern_events"], 
            "total_events": events["total_events"],
            "total_patterns": events["total_patterns"]
        },
        context=context
    )


@event_handler("module:inspect")
async def handle_inspect_module(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Inspect a specific module using direct function metadata."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    router = get_router()
    module_name = data.get("module_name")
    
    if not module_name:
        return error_response(
            "Missing module_name parameter",
            context=context
        )
    
    # Get module info with direct function inspection
    info = router.inspect_module(module_name)
    if not info:
        return error_response(
            f"Module not found: {module_name}",
            context=context
        )
    
    return event_response_builder(
        {"module": info},
        context=context
    )



@event_handler("system:health")
async def handle_system_health(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """System health check including module status."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder
    
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
    
    return event_response_builder(
        {
            "status": "healthy",
            "uptime": uptime,
            "version": "3.0.0",  # Event-based daemon version
            "modules_loaded": len(modules),
            "services_registered": services["total"],
            "events_registered": len(router._handlers),
            "background_tasks": len(router._tasks),
            "modules": list(modules.keys())
        },
        context=context
    )


class ConfigChangedData(TypedDict):
    """Configuration change notification."""
    config_type: Required[str]  # Type of config changed
    file_path: Required[str]  # Path to config file
    key: Required[str]  # Configuration key that changed
    value: Required[Any]  # New value


@event_handler("state:entity:updated")
async def handle_system_state_changed(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Handle system entity state changes by applying them immediately."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder
    
    entity_id = data.get("id")
    properties = data.get("properties", {})
    
    # Only handle system entity changes
    if entity_id != "system":
        return event_response_builder({"status": "ignored"}, context=context)
    
    logger.info(f"System state changed: {entity_id} properties updated")
    
    # Handle log_level changes immediately
    if "log_level" in properties:
        log_level = properties["log_level"]
        logger.info(f"System log level changed to: {log_level}")
        await _apply_log_level_change("log_level", log_level)
    
    return event_response_builder(
        {
            "system_state_applied": True,
            "entity_id": entity_id,
            "properties_applied": list(properties.keys())
        },
        context=context
    )


# BREAKING CHANGE: Removed deprecated config:changed handler
# Use state:entity:update or config:set events instead