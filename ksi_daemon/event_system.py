#!/usr/bin/env python3
"""
Pure Event-Based Module System for KSI

Native async event-driven architecture for modular functionality.
All modules communicate via events with clear async patterns.
"""

import asyncio
import inspect
import uuid
import time
import fnmatch
from typing import Dict, Any, List, Callable, Optional, Set, Union, TypeVar, Tuple, Type, TypedDict, Literal, get_type_hints
from typing_extensions import NotRequired, Required
from functools import wraps
import sys
from collections import defaultdict
from pathlib import Path

from ksi_common.logging import get_bound_logger
from ksi_common.error_handler import initialize_error_handler, enhance_error, handle_unknown_event
from ksi_common.config import config
from ksi_common.template_utils import apply_mapping
from ksi_common.context_utils import prepare_transformer_context
from ksi_common.task_management import create_tracked_task
from ksi_common.json_utils import parse_json_parameter

logger = get_bound_logger("event_system", version="2.0.0")

# Import context manager for reference-based context (PYTHONIC CONTEXT REFACTOR)
_context_manager = None
def get_context_manager():
    """Lazy import to avoid circular dependency."""
    global _context_manager
    if _context_manager is None:
        from ksi_daemon.core.context_manager import get_context_manager as _get_cm
        _context_manager = _get_cm()
    return _context_manager

# Import runtime config function (avoid circular import by importing lazily)
def get_runtime_config(key: str, fallback=None):
    """Lazy import to avoid circular dependency."""
    try:
        from ksi_daemon.config_manager import get_runtime_config as _get_runtime_config
        return _get_runtime_config(key, fallback)
    except ImportError:
        # Fallback to static config if runtime config not available
        return getattr(config, key, fallback)

T = TypeVar('T')


# Response builder utility moved to ksi_common.event_response_builder
# Handlers should import and use build_response() directly



class EventPriority:
    """Priority levels for event handlers."""
    HIGHEST = 0
    HIGH = 10
    NORMAL = 50
    LOW = 90
    LOWEST = 100


class EventHandler:
    """Wrapper for event handler functions with metadata."""
    
    def __init__(self, func: Callable, event: str, priority: int = EventPriority.NORMAL,
                 filter_func: Optional[Callable] = None):
        self.func = func
        self.event = event
        self.priority = priority
        self.filter_func = filter_func
        self.is_async = inspect.iscoroutinefunction(func)
        
        # Extract metadata
        self.module = func.__module__
        self.name = func.__name__
        
        # Extract TypedDict info for JSON parameter parsing
        self._extract_typeddict_info()
        
    def _extract_typeddict_info(self):
        """Extract TypedDict information from handler signature for JSON parsing."""
        self.json_params = set()
        try:
            sig = inspect.signature(self.func)
            if sig.parameters:
                # Get the first parameter (data)
                first_param = list(sig.parameters.values())[0]
                if first_param.annotation and first_param.annotation != inspect.Parameter.empty:
                    # Check if it's a TypedDict
                    hints = get_type_hints(self.func)
                    data_type = hints.get(first_param.name)
                    if data_type and hasattr(data_type, '__annotations__'):
                        # Look for parameters that might be JSON strings
                        for field, field_type in data_type.__annotations__.items():
                            # Check if the type is Dict or contains Dict (e.g., Union[str, Dict])
                            if hasattr(field_type, '__origin__'):
                                # Handle Union types
                                if hasattr(field_type, '__args__'):
                                    for arg in field_type.__args__:
                                        if arg is dict or (hasattr(arg, '__origin__') and arg.__origin__ is dict):
                                            self.json_params.add(field)
                                            break
                            elif field_type is dict or (hasattr(field_type, '__origin__') and field_type.__origin__ is dict):
                                # Direct Dict type
                                self.json_params.add(field)
                            elif field in ['filter', 'properties', 'metadata', 'vars', 'variables',
                                         'context', 'message', 'config', 'options', 'params',
                                         'attributes', 'tags', 'labels', 'settings']:
                                # Known JSON parameters by name
                                self.json_params.add(field)
        except Exception as e:
            # If we can't extract TypedDict info, that's fine
            logger.debug(f"Could not extract TypedDict info for {self.func.__name__}: {e}")
            pass
        
        logger.debug(f"EventHandler {self.name} for {self.event} - JSON params: {self.json_params}")
        
    async def __call__(self, data: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """Execute the handler."""
        # Apply filter if present
        if self.filter_func and not self.filter_func(self.event, data, context):
            return None
        
        # Parse JSON parameters if we have TypedDict info
        if self.json_params and isinstance(data, dict):
            # Make a copy to avoid modifying the original
            data = data.copy()
            for param in self.json_params:
                if param in data:
                    parse_json_parameter(data, param)
        
        # Determine handler signature to call correctly
        sig = inspect.signature(self.func)
        params = list(sig.parameters.keys())
        
        # Execute handler with correct signature
        if self.is_async:
            if len(params) >= 2 and context is not None:
                return await self.func(data, context)
            else:
                return await self.func(data)
        else:
            # Run sync handlers in thread pool
            loop = asyncio.get_event_loop()
            if len(params) >= 2 and context is not None:
                return await loop.run_in_executor(None, self.func, data, context)
            else:
                return await loop.run_in_executor(None, self.func, data)


class EventRouter:
    """Pure async event router - the heart of the module system."""
    
    def __init__(self):
        import time
        import os
        
        # Track router start time for uptime calculation
        self._start_time = time.time()
        
        # Event handlers organized by event name and priority
        self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        
        # Pattern handlers for wildcard matching (e.g., "state:*")
        self._pattern_handlers: List[Tuple[str, EventHandler]] = []
        
        # Dynamic transformers loaded from patterns
        self._transformers: Dict[str, List[Dict[str, Any]]] = {}  # source -> list of transformer configs
        self._pattern_transformers: List[Tuple[str, Dict[str, Any]]] = []  # pattern -> transformer config
        self._async_transformers: Dict[str, str] = {}  # transform_id -> source event
        self._transform_contexts: Dict[str, Dict[str, Any]] = {}  # transform_id -> context
        
        # Global middleware
        self._middleware: List[Callable] = []
        
        # Running tasks for background services
        self._tasks: Dict[str, asyncio.Task] = {}
        
        # Services registry
        self._services: Dict[str, Any] = {}
        
        # Module metadata for discovery/introspection
        self._modules: Dict[str, Dict[str, Any]] = {}
        
        # Handler registry by module for introspection
        self._handlers_by_module: Dict[str, List[EventHandler]] = defaultdict(list)
        
        # Service providers by module
        self._services_by_module: Dict[str, List[str]] = defaultdict(list)
        
        # Background tasks by module  
        self._tasks_by_module: Dict[str, List[str]] = defaultdict(list)
        
        # Shutdown coordination
        self._shutdown_handlers: Dict[str, EventHandler] = {}  # service_name -> handler
        self._shutdown_acknowledgments: Set[str] = set()
        self._shutdown_event = asyncio.Event()
        self._shutdown_in_progress = False
        self._shutdown_timeout = 30.0  # seconds
        
        # Error propagation mode
        # When True: Programming errors in handlers are propagated to caller
        # When False: Errors are caught, logged, and event:error is emitted (default)
        self._propagate_errors = os.environ.get("KSI_PROPAGATE_ERRORS", "false").lower() == "true"
        if self._propagate_errors:
            logger.warning("ERROR PROPAGATION ENABLED - Programming errors will crash handlers")
        
        # Enhanced error handling with discovery data
        initialize_error_handler(router=self)
    
    @property 
    def error_verbosity(self) -> str:
        """Get current error verbosity (runtime override or config default)."""
        return get_runtime_config('error_verbosity', config.error_verbosity)
        
    def register_handler(self, event: str, handler: EventHandler):
        """Register an event handler."""
        if "*" in event:
            # Pattern handler
            self._pattern_handlers.append((event, handler))
        else:
            # Direct event handler
            self._handlers[event].append(handler)
            # Sort by priority
            self._handlers[event].sort(key=lambda h: h.priority)
            
        # Track by module for introspection
        module_name = handler.module
        self._handlers_by_module[module_name].append(handler)
        
        # Auto-register module if first handler from this module
        self._ensure_module_registered(module_name)
            
        logger.debug(f"Registered handler {handler.name} for event {event} (priority={handler.priority})")
    
    def register_transformer_from_yaml(self, transformer_def: Dict[str, Any]):
        """Register a transformer from YAML definition.
        
        Args:
            transformer_def: YAML transformer configuration with:
                - source: source event pattern
                - target: target event
                - mapping: field mappings
                - async: whether it's async (optional)
                - condition: conditional logic (optional)
                - response_route: response routing config (optional)
        """
        source = transformer_def.get('source')
        if not source:
            raise ValueError("Transformer missing 'source' field")
            
        if "*" in source:
            # Pattern transformer
            self._pattern_transformers.append((source, transformer_def))
        else:
            # Direct event transformer - support multiple transformers per source
            if source not in self._transformers:
                self._transformers[source] = []
            self._transformers[source].append(transformer_def)
            
        logger.info(f"Registered dynamic transformer: {source} -> {transformer_def.get('target')}")
    
    def unregister_transformer(self, source: str):
        """Remove all transformers for a source."""
        if source in self._transformers:
            count = len(self._transformers[source])
            del self._transformers[source]
            logger.info(f"Unregistered {count} transformer(s) for: {source}")
        else:
            # Check pattern transformers
            for i, (pattern, transformer_def) in enumerate(self._pattern_transformers):
                if pattern == source:
                    del self._pattern_transformers[i]
                    logger.info(f"Unregistered pattern transformer: {source}")
                    break
    
    def register_shutdown_handler(self, service_name: str, handler: EventHandler):
        """Register a critical shutdown handler that must complete before daemon exits.
        
        Args:
            service_name: Unique name for this service (used for acknowledgment)
            handler: EventHandler for system:shutdown event
        """
        self._shutdown_handlers[service_name] = handler
        # Also register as normal handler
        self.register_handler("system:shutdown", handler)
        logger.info(f"Registered critical shutdown handler for service: {service_name}")
        
    def register_service(self, name: str, service: Any, module_name: Optional[str] = None):
        """Register a service instance."""
        self._services[name] = service
        
        # Track by module if provided
        if module_name:
            self._services_by_module[module_name].append(name)
            self._ensure_module_registered(module_name)
            
        logger.info(f"Registered service: {name}")
        
    def get_service(self, name: str) -> Optional[Any]:
        """Get a registered service."""
        return self._services.get(name)
    
    def set_error_propagation(self, enabled: bool) -> bool:
        """Enable or disable error propagation mode.
        
        Args:
            enabled: True to propagate errors, False to catch and log them
            
        Returns:
            Previous setting
        """
        previous = self._propagate_errors
        self._propagate_errors = enabled
        if enabled:
            logger.warning("ERROR PROPAGATION ENABLED - Programming errors will crash handlers")
        else:
            logger.info("Error propagation disabled - errors will be caught and logged")
        return previous
        
    async def emit(self, event: str, data: Any = None, 
                   context: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Emit an event to all matching handlers."""
        # Store current event for condition evaluation
        self._current_event = event
        
        # Check for dynamic transformers first
        transformers = []
        if event in self._transformers:
            transformers.extend(self._transformers[event])
            logger.debug(f"Found {len(self._transformers[event])} direct transformers for {event}")
        
        # Also check pattern transformers
        for pattern, transformer_def in self._pattern_transformers:
            if self._matches_pattern(event, pattern):
                transformers.append(transformer_def)
                logger.debug(f"Pattern {pattern} matched event {event}")
        
        if transformers:
            logger.debug(f"Total transformers found for {event}: {len(transformers)}")
        else:
            logger.debug(f"No transformers found for {event}")
        
        # Collect transformer tasks to await their completion
        transformer_tasks = []
        
        # Process all matching transformers
        for transformer in transformers:
            target = transformer.get('target')
            logger.debug(f"Processing transformer: {event} -> {target}")
            
            # Check condition if present
            should_transform = True
            if 'condition' in transformer:
                # Evaluate condition with proper context
                if not self._evaluate_condition(transformer['condition'], data):
                    # Condition not met, skip transformation
                    logger.debug(f"Transformer condition not met for {event}")
                    should_transform = False
            
            # Transform the data if no condition or condition passed
            if should_transform:
                try:
                    # DEBUG: Log transformer details
                    logger.debug(f"Checking transformer {event} -> {target}")
                    logger.debug(f"Transformer type: {type(transformer)}")
                    logger.debug(f"Transformer keys: {list(transformer.keys()) if isinstance(transformer, dict) else 'Not a dict'}")
                    logger.debug(f"Has foreach: {'foreach' in transformer if isinstance(transformer, dict) else False}")
                    if isinstance(transformer, dict) and 'foreach' in transformer:
                        logger.debug(f"Foreach value: {transformer.get('foreach')}")
                    
                    # Check if this is a foreach transformer
                    if 'foreach' in transformer and transformer.get('foreach'):
                        # Import foreach support
                        from ksi_common.foreach_transformer import process_foreach_transformer
                        
                        # Process foreach transformer
                        async def run_foreach_transform(trans=transformer, tgt=target):
                            try:
                                logger.debug(f"Processing foreach transformer {event} -> {tgt}")
                                results = await process_foreach_transformer(
                                    transformer=trans,
                                    event=event,
                                    data=data,
                                    context=context,
                                    emit_func=self.emit,
                                    apply_mapping_func=apply_mapping,
                                    prepare_context_func=prepare_transformer_context
                                )
                                logger.debug(f"Foreach transformer completed with {len(results)} emissions")
                                return results
                            except Exception as e:
                                logger.error(f"Foreach transformer failed for {event}: {e}")
                                return []
                        
                        # Create task for foreach processing
                        task = create_tracked_task("event_system", run_foreach_transform(), task_name="foreach_transform")
                        transformer_tasks.append(task)
                        logger.debug(f"Processing foreach transformer {event} -> {target}")
                        
                    # For async transformers, spawn as background task
                    elif transformer.get('async', False):
                        # Generate transform_id for async tracking
                        transform_id = str(uuid.uuid4())
                        self._async_transformers[transform_id] = event
                        
                        # Add transform_id to data for template substitution
                        data_with_transform_id = dict(data)
                        data_with_transform_id['transform_id'] = transform_id
                        
                        # Debug logging
                        logger.debug(f"Async transformer data: {data_with_transform_id}")
                        
                        # Prepare context for transformer with standardized structure
                        prepared_data, ksi_context = prepare_transformer_context(event, data_with_transform_id, context)
                        
                        # Apply mapping with standardized context
                        transformed_data = apply_mapping(transformer.get('mapping', {}), prepared_data, ksi_context)
                        logger.debug(f"Transformed data: {transformed_data}")
                        
                        # Store context for later injection (if available)
                        if context:
                            self._transform_contexts[transform_id] = context
                        
                        # Create background task for async transformation
                        async def run_async_transform(tgt=target, tdata=transformed_data):
                            try:
                                logger.debug(f"Async transforming {event} -> {tgt} (id: {transform_id})")
                                result = await self.emit(tgt, tdata, context)
                                logger.debug(f"Async transformed event {tgt} result: {result}")
                            except Exception as e:
                                logger.error(f"Async transformer failed for {event} -> {tgt}: {e}")
                        
                        # Collect task instead of just creating it
                        task = create_tracked_task("event_system", run_async_transform(), task_name="async_transform")
                        transformer_tasks.append(task)
                        logger.debug(f"Spawned async transformer {event} -> {target} as background task")
                        
                        # Continue to normal handler execution
                        # DO NOT RETURN - let handlers run and return their responses
                    else:
                        # Synchronous transformation - but don't block handler execution
                        # Prepare context for transformer with standardized structure
                        prepared_data, ksi_context = prepare_transformer_context(event, data, context)
                        
                        # Apply mapping with standardized context
                        transformed_data = apply_mapping(transformer.get('mapping', {}), prepared_data, ksi_context)
                        logger.debug(f"Transforming {event} -> {target}")
                        
                        # Spawn transformation as task to allow multiple transformers and handlers to run
                        async def run_sync_transform(tgt=target, tdata=transformed_data):
                            try:
                                logger.debug(f"Emitting transformed event {tgt} with data: {tdata}")
                                result = await self.emit(tgt, tdata, context)
                                logger.debug(f"Transformed event {tgt} result: {result}")
                            except Exception as e:
                                logger.error(f"Sync transformer failed for {event} -> {tgt}: {e}")
                        
                        # Collect sync transformer task
                        task = create_tracked_task("event_system", run_sync_transform(), task_name="sync_transform")
                        transformer_tasks.append(task)
                except Exception as e:
                    logger.error(f"Dynamic transformer failed for {event}: {e}")
                    # Fall through to normal handling
        
        # Check for async transformer response routing
        if hasattr(self, '_handle_async_response'):
            response_result = await self._handle_async_response(event, data)
            if response_result:
                # Response was routed, return indicator
                return [response_result]
        
        # During shutdown, only allow shutdown-related events and critical state updates
        if self._shutdown_in_progress:
            allowed_events = {"system:shutdown", "shutdown:acknowledge",
                            "event:error", "log:*", "state:entity:update"}  # Allow state updates during shutdown
            if not any(event == allowed or (allowed.endswith('*') and event.startswith(allowed[:-1])) 
                      for allowed in allowed_events):
                logger.debug(f"Blocking event {event} during shutdown")
                return []
        
        if data is None:
            data = {}
            
        # Auto-silence discovery events
        SILENT_EVENT_PATTERNS = [
            "system:discover",
            "system:help",
            "module:list*",
            "module:inspect",
            "module:events"
        ]
        
        # Check if event matches silent patterns
        import fnmatch
        for pattern in SILENT_EVENT_PATTERNS:
            if fnmatch.fnmatch(event, pattern):
                data['_silent'] = True
                break
            
        # Extract and remove _silent flag if present
        # Silent events are processed normally but not logged
        silent = data.pop('_silent', False)
            
        # Create context if not provided
        if context is None:
            context = {
                "event": event,
                "router": self
            }
        else:
            context["event"] = event
            context["router"] = self
        
        # NOTE: Event logging moved after enrichment to capture proper genealogy metadata
        
        # Check for observation - use _agent_id as single source of truth
        observation_id = None
        matching_subscriptions = []
        
        # Agent origination determined solely by _agent_id presence in context
        source_agent = context.get("_agent_id") if context else None
        
        # Don't observe observation events to prevent loops
        if (source_agent and 
            not event.startswith("observe:") and not event.startswith("observation:")):
            # Import here to avoid circular dependency
            from ksi_daemon.observation import should_observe_event, notify_observers_async
            
            matching_subscriptions = should_observe_event(event, source_agent, data)
            if matching_subscriptions:
                observation_id = f"obs_{uuid.uuid4().hex[:8]}"
                # Notify observers of event begin (async - non-blocking)
                await notify_observers_async(matching_subscriptions, "begin", event, data, source_agent)
            
        # Apply middleware
        for mw in self._middleware:
            data = await mw(event, data, context)
            
        # PYTHONIC CONTEXT REFACTOR: Use reference-based context management
        # This reduces event size by 66% and enables automatic context propagation
        if context and isinstance(data, dict):
            enhanced_data = data.copy()
            
            # Get the context manager
            cm = get_context_manager()
            
            # Extract any existing _ksi_context (could be a reference or full context)
            existing_ksi_context = enhanced_data.get("_ksi_context")
            
            # If it's a reference, resolve it
            if isinstance(existing_ksi_context, str) and existing_ksi_context.startswith("ctx_"):
                # It's a reference - resolve it
                existing_ksi_context = await cm.get_context(existing_ksi_context) or {}
            elif not isinstance(existing_ksi_context, dict):
                existing_ksi_context = {}
            
            # Prepare context creation parameters
            context_params = {}
            
            # Event ID - check multiple sources
            event_id = (existing_ksi_context.get("_event_id") or 
                       enhanced_data.get("_event_id") or 
                       f"evt_{uuid.uuid4().hex[:8]}")
            context_params["event_id"] = event_id
            
            # Timestamp
            context_params["timestamp"] = time.time()
            
            # Correlation ID - check multiple sources
            if "_correlation_id" in context:
                context_params["correlation_id"] = context["_correlation_id"]
            elif "_correlation_id" in existing_ksi_context:
                context_params["correlation_id"] = existing_ksi_context["_correlation_id"]
            elif "_correlation_id" in data:
                context_params["correlation_id"] = data["_correlation_id"]
            # If none found, create_context will generate one
            
            # Add system metadata fields from context
            from ksi_common.event_parser import SYSTEM_METADATA_FIELDS
            for field in SYSTEM_METADATA_FIELDS:
                if field in context:
                    # Remove leading underscore for context_params
                    param_name = field[1:] if field.startswith("_") else field
                    context_params[param_name] = context[field]
            
            # Create or update context using context manager
            # This automatically handles parent relationships via contextvars
            ksi_context = await cm.create_context(**context_params)
            
            # Store the event with context and get back a reference
            event_for_storage = {
                "event_id": event_id,
                "event_name": event,
                "timestamp": context_params["timestamp"],
                "data": enhanced_data
            }
            
            context_ref = await cm.store_event_with_context(event_for_storage)
            
            # BREAKING CHANGE: Store only the reference, not full context
            enhanced_data["_ksi_context"] = context_ref
            
            # Update the router's context for child event propagation
            # The context manager already set contextvars, but we also update
            # the passed context dict for backward compatibility
            context.update({
                "_event_id": ksi_context["_event_id"],
                "_correlation_id": ksi_context["_correlation_id"],
                "_parent_event_id": ksi_context["_event_id"],  # This event becomes parent for children
                "_root_event_id": ksi_context.get("_root_event_id", ksi_context["_event_id"]),
                "_event_depth": ksi_context.get("_event_depth", 0),
                "_ksi_context_ref": context_ref  # Store reference for handlers that need it
            })
                
        else:
            # Non-dict data or no context - use as-is
            enhanced_data = data
            
        # Log event to reference-based event log AFTER enrichment (only if not silent)
        if not silent and hasattr(self, 'reference_event_log') and self.reference_event_log:
            # Extract metadata for logging from enhanced_data
            log_data = enhanced_data if isinstance(enhanced_data, dict) else data
            
            # Get originator_id from context (who triggered this event)
            originator_id = context.get("_agent_id") if context else None
            
            # PYTHONIC CONTEXT REFACTOR: Extract metadata from context dict
            # The enhanced_data now contains a reference, but context dict has the values
            correlation_id = context.get("_correlation_id") if context else None
            event_id = context.get("_event_id") if context else None
            parent_event_id = context.get("_parent_event_id") if context else None
            root_event_id = context.get("_root_event_id") if context else None
            event_depth = context.get("_event_depth") if context else None
            
            # Fallback to request_id if no event_id
            if not event_id and isinstance(log_data, dict):
                event_id = log_data.get("request_id")
            
            # Also check context for construct_id
            construct_id = context.get("construct_id") if context else None
            if not construct_id and isinstance(log_data, dict):
                construct_id = log_data.get("construct_id")
            
            # Log the event unless it's marked to skip
            # PYTHONIC CONTEXT REFACTOR: Skip logging internal plumbing events
            if not (isinstance(log_data, dict) and log_data.get("_skip_log")):
                create_tracked_task("event_system", self.reference_event_log.log_event(
                    event_name=event,
                    data=log_data,
                    originator_id=originator_id,
                    construct_id=construct_id,
                    correlation_id=correlation_id,
                    event_id=event_id,
                    parent_event_id=parent_event_id,
                    root_event_id=root_event_id,
                    event_depth=event_depth
                ), task_name="log_event")
            
        # Collect all matching handlers
        handlers = []
        
        # Direct handlers
        if event in self._handlers:
            handlers.extend(self._handlers[event])
            
        # Pattern matching handlers
        for pattern, handler in self._pattern_handlers:
            if self._matches_pattern(event, pattern):
                handlers.append(handler)
                
        if not handlers:
            # Still notify observers even if no handlers
            if matching_subscriptions:
                await notify_observers_async(matching_subscriptions, "end", event, 
                                           {"status": "no_handlers"}, source_agent)
            
            # Check if transformers processed this event
            if transformers:
                # Wait for transformer tasks to complete before returning
                if transformer_tasks:
                    logger.debug(f"Awaiting {len(transformer_tasks)} transformer tasks for {event}")
                    await asyncio.gather(*transformer_tasks, return_exceptions=True)
                    logger.debug(f"All transformer tasks completed for {event}")
                # Transformers handled this event, return success
                logger.info(f"Event {event} handled by {len(transformers)} transformer(s), no direct handlers")
                return [{"status": "transformed", "transformers": len(transformers)}]
            
            # Unknown event - provide discovery guidance
            unknown_event_response = await handle_unknown_event(
                event_name=event,
                provided_params=data,
                verbosity=self.error_verbosity
            )
            return [unknown_event_response]
            
        # Execute handlers concurrently with enhanced data
        if self._propagate_errors:
            # In error propagation mode, let exceptions bubble up
            results = await asyncio.gather(
                *[handler(enhanced_data, context) for handler in handlers]
            )
            # All results are valid if we get here
            valid_results = [r for r in results if r is not None]
            errors = []
        else:
            # Default mode: catch exceptions and continue
            results = await asyncio.gather(
                *[handler(enhanced_data, context) for handler in handlers],
                return_exceptions=True
            )
            
            # Filter results
            valid_results = []
            errors = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Handler {handlers[i].name} failed for {event}: {result}")
                    
                    # Generate enhanced error using discovery data
                    enhanced_error = await enhance_error(
                        event_name=event,
                        provided_params=data,
                        original_error=result,
                        verbosity=self.error_verbosity
                    )
                    
                    # Store enhanced error for return
                    error_info = {
                        "handler": handlers[i].name,
                        **enhanced_error
                    }
                    errors.append(error_info)
                    
                    # Emit enhanced error event
                    await self.emit("event:error", {
                        "event": event,
                        "handler": handlers[i].name,
                        **enhanced_error
                    })
                elif result is not None:
                    valid_results.append(result)
        
        # Wait for transformer tasks to complete even when we have handlers
        if transformer_tasks:
            logger.debug(f"Awaiting {len(transformer_tasks)} transformer tasks alongside handlers for {event}")
            await asyncio.gather(*transformer_tasks, return_exceptions=True)
            logger.debug(f"All transformer tasks completed alongside handlers for {event}")
        
        # Notify observers of event completion
        if matching_subscriptions:
            observation_result = {
                "results": valid_results,
                "errors": errors,
                "handler_count": len(handlers)
            }
            await notify_observers_async(matching_subscriptions, "end", event, 
                                       observation_result, source_agent)
        
        # Return enhanced errors if all handlers failed
        if not valid_results and errors:
            # Return the first enhanced error (without handler info for client)
            first_error = errors[0]
            error_response = {k: v for k, v in first_error.items() if k != "handler"}
            return [error_response]
                
        return valid_results
        
    async def emit_first(self, event: str, data: Any = None,
                        context: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """Emit event and return first non-None result."""
        results = await self.emit(event, data, context)
        return results[0] if results else None
        
    async def wait_for_event(self, event_name: str, 
                           filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None) -> Dict[str, Any]:
        """
        Wait for a specific event matching filter criteria.
        
        This enables request/response patterns in the event system without polling.
        The method registers a temporary handler that resolves when a matching event occurs.
        
        This method trusts the event system - it will wait indefinitely for the event.
        If timeouts are needed, they should be handled by the emitting service (e.g.,
        completion service should emit completion:result with status="timeout").
        
        Args:
            event_name: Name of the event to wait for (e.g., "completion:result")
            filter_fn: Optional filter function that receives event data and returns True for match
            
        Returns:
            Event data when matched
            
        Example:
            # Wait for specific completion
            result = await router.wait_for_event(
                "completion:result",
                lambda data: data.get("request_id") == my_request_id
            )
            
        Note: This is Pattern 2 (Request-Response) for event systems.
        Pattern 1 (Subscriptions) could be added in future for persistent event monitoring:
        - subscribe(event, handler, filter) - for ongoing event reactions
        - unsubscribe(subscription_id) - to stop monitoring
        """
        future = asyncio.Future()
        
        async def waiter(data: Dict[str, Any], context: Dict[str, Any]) -> None:
            """Temporary handler that resolves the future when matching event occurs."""
            try:
                if filter_fn is None or filter_fn(data):
                    if not future.done():
                        future.set_result(data)
            except Exception as e:
                logger.error(f"Error in wait_for_event filter: {e}")
                if not future.done():
                    future.set_exception(e)
        
        # Register temporary handler (wrap in EventHandler)
        handler = EventHandler(waiter, event_name, EventPriority.NORMAL)
        self.register_handler(event_name, handler)
        
        try:
            # Wait for the event - trust it will arrive
            result = await future
            return result
        finally:
            # Clean up temporary handler
            if event_name in self._handlers:
                self._handlers[event_name] = [h for h in self._handlers[event_name] if h != handler]
        
    def _matches_pattern(self, event: str, pattern: str) -> bool:
        """Check if event matches pattern (supports * wildcard)."""
        if pattern == "*":
            return True
            
        parts = pattern.split(":")
        event_parts = event.split(":")
        
        if len(parts) != len(event_parts):
            return False
            
        for p, e in zip(parts, event_parts):
            if p != "*" and p != e:
                return False
                
        return True
        
    def use_middleware(self, middleware: Callable):
        """Add global middleware."""
        self._middleware.append(middleware)
        
    async def start_task(self, name: str, coro_or_callable, *args, **kwargs):
        """Start a background task from either a coroutine object or callable."""
        if name in self._tasks:
            logger.warning(f"Task {name} already running")
            return
            
        async def task_wrapper():
            try:
                # Handle both coroutine objects and callables
                if asyncio.iscoroutine(coro_or_callable):
                    # It's already a coroutine object, await it directly
                    await coro_or_callable
                else:
                    # It's a callable, call it then await
                    await coro_or_callable(*args, **kwargs)
            except asyncio.CancelledError:
                logger.info(f"Task {name} cancelled")
                raise
            except Exception as e:
                logger.error(f"Task {name} failed: {e}")
                await self.emit("task:error", {"task": name, "error": str(e)})
                
        task = create_tracked_task("event_system", task_wrapper(), task_name=name)
        self._tasks[name] = task
        logger.info(f"Started task: {name}")
        
    async def stop_task(self, name: str):
        """Stop a background task."""
        if name in self._tasks:
            task = self._tasks[name]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self._tasks[name]
            logger.info(f"Stopped task: {name}")
            
    async def stop_all_tasks(self):
        """Stop all background tasks."""
        for name in list(self._tasks.keys()):
            await self.stop_task(name)
    
    # Shutdown coordination methods
    
    async def begin_shutdown(self) -> None:
        """Begin coordinated shutdown sequence."""
        if self._shutdown_in_progress:
            logger.warning("Shutdown already in progress")
            return
            
        logger.info("Beginning coordinated shutdown sequence")
        self._shutdown_in_progress = True
        self._shutdown_acknowledgments.clear()
        self._shutdown_event.clear()
        
        # Log critical services that need to acknowledge
        if self._shutdown_handlers:
            logger.info(f"Waiting for {len(self._shutdown_handlers)} critical services: "
                       f"{list(self._shutdown_handlers.keys())}")
    
    async def acknowledge_shutdown(self, service_name: str) -> None:
        """Acknowledge that a critical service has completed shutdown tasks.
        
        Args:
            service_name: Name of the service acknowledging completion
        """
        if service_name not in self._shutdown_handlers:
            logger.warning(f"Unknown service acknowledging shutdown: {service_name}")
            return
            
        self._shutdown_acknowledgments.add(service_name)
        logger.info(f"Service '{service_name}' acknowledged shutdown "
                   f"({len(self._shutdown_acknowledgments)}/{len(self._shutdown_handlers)})")
        
        # Check if all critical services have acknowledged
        if self._shutdown_acknowledgments == set(self._shutdown_handlers.keys()):
            logger.info("All critical services have acknowledged shutdown")
            self._shutdown_event.set()
    
    async def wait_for_shutdown_acknowledgments(self, timeout: Optional[float] = None) -> bool:
        """Wait for all critical services to acknowledge shutdown.
        
        Args:
            timeout: Maximum time to wait (uses self._shutdown_timeout if not specified)
            
        Returns:
            True if all services acknowledged, False if timeout
        """
        timeout = timeout or self._shutdown_timeout
        
        # If no critical services registered, return immediately
        if not self._shutdown_handlers:
            logger.debug("No critical shutdown handlers registered")
            return True
            
        try:
            await asyncio.wait_for(self._shutdown_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            pending = set(self._shutdown_handlers.keys()) - self._shutdown_acknowledgments
            logger.error(f"Shutdown timeout after {timeout}s. Pending services: {pending}")
            return False
    
    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self._shutdown_in_progress
            
    def _ensure_module_registered(self, module_name: str):
        """Ensure module is registered for discovery."""
        if module_name not in self._modules:
            self._modules[module_name] = {
                "name": module_name,
                "handlers": [],
                "services": [],
                "tasks": [],
                "loaded_at": asyncio.get_event_loop().time() if asyncio._get_running_loop() else 0
            }
            logger.debug(f"Auto-registered module: {module_name}")
    
    def register_background_task(self, task_name: str, module_name: str):
        """Register a background task for discovery."""
        self._tasks_by_module[module_name].append(task_name)
        self._ensure_module_registered(module_name)
    
    # Discovery and Introspection Methods
    
    def get_modules(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered modules with their capabilities."""
        modules = {}
        for module_name in self._modules:
            modules[module_name] = {
                "name": module_name,
                "handlers": [
                    {
                        "event": h.event,
                        "function": h.name,
                        "priority": h.priority,
                        "async": h.is_async
                    }
                    for h in self._handlers_by_module[module_name]
                ],
                "services": self._services_by_module[module_name],
                "background_tasks": self._tasks_by_module[module_name],
                "loaded_at": self._modules[module_name].get("loaded_at", 0)
            }
        return modules
    
    def get_events(self) -> Dict[str, Any]:
        """Get all registered events and their handlers."""
        events = {}
        
        # Direct event handlers
        for event, handlers in self._handlers.items():
            events[event] = [
                {
                    "function": h.name,
                    "module": h.module,
                    "priority": h.priority,
                    "async": h.is_async
                }
                for h in handlers
            ]
        
        # Pattern handlers
        patterns = {}
        for pattern, handler in self._pattern_handlers:
            if pattern not in patterns:
                patterns[pattern] = []
            patterns[pattern].append({
                "function": handler.name,
                "module": handler.module,
                "priority": handler.priority,
                "async": handler.is_async
            })
        
        return {
            "direct_events": events,
            "pattern_events": patterns,
            "total_events": len(events),
            "total_patterns": len(patterns)
        }
    
    def get_services(self) -> Dict[str, Any]:
        """Get all registered services."""
        return {
            "services": list(self._services.keys()),
            "by_module": dict(self._services_by_module),
            "total": len(self._services)
        }
    
    def inspect_module(self, module_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific module."""
        if module_name not in self._modules:
            return None
        
        # Get handlers
        handlers = []
        for handler in self._handlers_by_module[module_name]:
            handler_info = {
                "event": handler.event,
                "function": handler.name,
                "priority": handler.priority,
                "async": handler.is_async,
                "filter": handler.filter_func is not None
            }
            handlers.append(handler_info)
            
        return {
            "name": module_name,
            "handlers": handlers,
            "services": [
                {
                    "name": service_name,
                    "type": type(self._services[service_name]).__name__
                }
                for service_name in self._services_by_module[module_name]
            ],
            "background_tasks": self._tasks_by_module[module_name],
            "running_tasks": [
                name for name in self._tasks.keys() 
                if any(name.startswith(f"{module_name}:") for name in self._tasks)
            ],
            "stats": {
                "handler_count": len(self._handlers_by_module[module_name]),
                "service_count": len(self._services_by_module[module_name]),
                "task_count": len(self._tasks_by_module[module_name])
            }
        }
    
    def _prepare_log_data(self, event_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare event data for logging by stripping large payloads.
        
        Keep references to files but remove large content fields.
        """
        if not data:
            return {}
            
        # List of field names that typically contain large payloads
        large_fields = {
            "content", "response", "text", "prompt", "message",
            "file_content", "data", "payload", "body", "result"
        }
        
        # Fields that are file references and should be kept
        file_ref_fields = {
            "file_path", "response_file", "log_file", "session_id",
            "request_id", "correlation_id", "event_id"
        }
        
        log_data = {}
        
        for key, value in data.items():
            # Always keep file references and IDs
            if key in file_ref_fields:
                log_data[key] = value
            # Skip large text fields
            elif key in large_fields and isinstance(value, str) and len(value) > 1000:
                log_data[key] = f"<stripped: {len(value)} chars>"
            # Skip large lists/dicts
            elif isinstance(value, (list, dict)) and len(str(value)) > 1000:
                log_data[key] = f"<stripped: {type(value).__name__} with {len(value)} items>"
            # Keep everything else
            else:
                log_data[key] = value
                
        return log_data


# Decorators for the new system

def event_handler(event: str, 
                 priority: int = EventPriority.NORMAL, 
                 filter_func: Optional[Callable] = None):
    """
    Simple event handler decorator.
    
    Usage: @event_handler("event_name")
    """
    def decorator(func: Callable) -> Callable:
        # Create handler wrapper
        handler = EventHandler(func, event, priority, filter_func)
        
        # Store basic info on function for discovery
        func._event_handler = handler
        func._event_name = event
        func._event_priority = priority
        
        # AUTO-REGISTER: Register with global router immediately at import time
        router = get_router()
        router.register_handler(event, handler)
        
        logger.debug(f"Auto-registered handler {func.__name__} for {event} from {func.__module__}")
        
        return func
    return decorator


# Note: Template processing has been moved to ksi_common.template_utils
# Only condition evaluation remains here as it's specific to event routing

def _evaluate_condition(self, condition: str, data: Dict[str, Any]) -> bool:
    """Evaluate condition expressions for event routing."""
    from ksi_common.condition_evaluator import evaluate_condition
    
    # Prepare context with the current event name
    context = {
        'event': self._current_event if hasattr(self, '_current_event') else None,
    }
    
    return evaluate_condition(condition, data, context)

# Bind helper method to EventRouter class
EventRouter._evaluate_condition = _evaluate_condition

async def _handle_async_response(self, event: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle responses for async transformers and route them accordingly."""
    # Check if this is a response for an async transformer
    transform_id = data.get('transform_id') or data.get('request_id')
    if not transform_id or transform_id not in self._async_transformers:
        return None
    
    # Get the original source event
    source_event = self._async_transformers[transform_id]
    transformer = self._transformers.get(source_event, {})
    response_route = transformer.get('response_route', {})
    
    if not response_route:
        # No response routing configured
        del self._async_transformers[transform_id]
        return None
    
    # Check if this event matches the expected response
    if event == response_route.get('from'):
        # Apply filter if specified
        filter_expr = response_route.get('filter')
        if filter_expr:
            # Simple filter evaluation (can be enhanced)
            # Example: "request_id == {{transform_id}}"
            if '{{transform_id}}' in filter_expr:
                filter_expr = filter_expr.replace('{{transform_id}}', f'"{transform_id}"')
            
            # Very basic eval - should be replaced with safe expression evaluator
            try:
                if not eval(filter_expr, {'request_id': data.get('request_id'), 
                                         'transform_id': transform_id,
                                         'status': data.get('status')}):
                    return None
            except Exception as e:
                logger.warning(f"Failed to evaluate response filter: {e}")
        
        # Route to target event
        target_event = response_route.get('to')
        if target_event:
            # Remove transform tracking  
            del self._async_transformers[transform_id]
            
            # Option 3: Emit BOTH events
            
            # 1. Emit routed event (for pattern handlers)
            logger.debug(f"Routing async response {event} -> {target_event}")
            await self.emit(target_event, data)
            
            # 2. Emit standard transform:result (for originating agent/orchestrator)
            transform_result = {
                "transform_id": transform_id,
                "source_event": source_event,
                "target_event": target_event,
                "result": data,
                "timestamp": time.time()
            }
            await self.emit("transform:result", transform_result)
            
            # 3. Optional: Direct injection to originating agent
            # Check if we have agent context from the original transform
            if hasattr(self, '_transform_contexts') and transform_id in self._transform_contexts:
                context = self._transform_contexts[transform_id]
                agent_id = context.get('agent_id')
                
                if agent_id:
                    # Inject result directly to agent (following existing pattern)
                    await self.emit("agent:send_message", {
                        "agent_id": agent_id,
                        "message": {
                            "type": "transform:result",
                            "transform_id": transform_id,
                            "result": data,
                            "routed_to": target_event,
                            "_system_injected": True
                        }
                    })
                    logger.debug(f"Injected transform result to agent {agent_id}")
                
                # Clean up context
                del self._transform_contexts[transform_id]
            
            # Return indicator that we handled this
            return {"routed": True, "to": target_event, "transform_result_emitted": True}
    
    return None

EventRouter._handle_async_response = _handle_async_response


def service_provider(service_name: str):
    """Decorator to mark and auto-register service providers."""
    def decorator(func: Callable) -> Callable:
        func._provides_service = service_name
        
        # AUTO-REGISTER: Create and register service at import time
        router = get_router()
        try:
            # For simple service providers, call them immediately
            if not inspect.iscoroutinefunction(func):
                service = func()
                router.register_service(service_name, service, func.__module__)
                logger.debug(f"Auto-registered service {service_name} from {func.__module__}")
            else:
                # Async service providers need to be called during startup
                logger.debug(f"Deferred async service provider {service_name} from {func.__module__}")
        except Exception as e:
            logger.warning(f"Failed to auto-register service {service_name}: {e}")
            
        return func
    return decorator


def shutdown_handler(service_name: str, priority: int = EventPriority.NORMAL):
    """Decorator to register a critical shutdown handler.
    
    Services decorated with this will be tracked during shutdown and must
    acknowledge completion before the daemon exits.
    
    Args:
        service_name: Unique name for this service
        priority: Handler priority (default: NORMAL)
        
    Example:
        @shutdown_handler("checkpoint")
        async def save_checkpoint_on_shutdown(data):
            await save_state()
            await router.acknowledge_shutdown("checkpoint")
    """
    def decorator(func: Callable) -> Callable:
        # Create handler wrapper
        handler = EventHandler(func, "system:shutdown", priority)
        
        # Store info on function
        func._shutdown_handler = handler
        func._shutdown_service = service_name
        
        # AUTO-REGISTER: Register with global router as critical shutdown handler
        router = get_router()
        router.register_shutdown_handler(service_name, handler)
        
        logger.debug(f"Auto-registered critical shutdown handler {func.__name__} for service {service_name}")
        
        return func
    return decorator


def background_task(name: str):
    """Decorator to mark background tasks - registered via system:ready event."""
    def decorator(func: Callable) -> Callable:
        func._background_task = name
        
        # AUTO-REGISTER: Track background task for discovery
        router = get_router()
        router.register_background_task(name, func.__module__)
        
        logger.debug(f"Marked background task {name} from {func.__module__}")
        
        return func
    return decorator




# Global router instance
_global_router: Optional[EventRouter] = None


def get_router() -> EventRouter:
    """Get the global event router."""
    global _global_router
    if _global_router is None:
        _global_router = EventRouter()
    return _global_router


# Router management events for dynamic transformers
class RouterRegisterTransformerData(TypedDict):
    """Register a dynamic transformer."""
    transformer: Required[Dict[str, Any]]  # Transformer definition with source, target, mapping, etc.


@event_handler("router:register_transformer")
async def handle_register_transformer(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Register a dynamic transformer from pattern."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    transformer = data.get('transformer')
    if not transformer:
        return error_response(
            "Missing transformer definition",
            context=context
        )
    
    try:
        router = get_router()
        router.register_transformer_from_yaml(transformer)
        return event_response_builder(
            {
                "status": "registered",
                "source": transformer.get('source'),
                "target": transformer.get('target')
            },
            context=context
        )
    except Exception as e:
        return error_response(
            str(e),
            context=context
        )

class RouterUnregisterTransformerData(TypedDict):
    """Unregister a dynamic transformer."""
    source: Required[str]  # Source event pattern to unregister


@event_handler("router:unregister_transformer")
async def handle_unregister_transformer(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Unregister a dynamic transformer."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    source = data.get('source')
    if not source:
        return error_response(
            "Missing source event",
            context=context
        )
    
    router = get_router()
    router.unregister_transformer(source)
    return event_response_builder(
        {"status": "unregistered", "source": source},
        context=context
    )

class RouterListTransformersData(TypedDict):
    """List all registered transformers."""
    # No specific fields - returns all transformers
    pass


@event_handler("router:list_transformers")
async def handle_list_transformers(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """List all registered transformers."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, list_response
    
    router = get_router()
    transformers = []
    
    # Direct transformers
    for source, configs in router._transformers.items():
        for config in configs:
            transformers.append({
                "source": source,
                "target": config.get('target'),
                "async": config.get('async', False),
                "has_condition": 'condition' in config,
                "has_response_route": 'response_route' in config
            })
    
    # Pattern transformers
    for pattern, config in router._pattern_transformers:
        transformers.append({
            "source": pattern,
            "target": config.get('target'),
            "async": config.get('async', False),
            "has_condition": 'condition' in config,
            "has_response_route": 'response_route' in config
        })
    
    return list_response(
        transformers,
        context=context,
        count_field="count",
        items_field="transformers"
    )


class SystemErrorPropagationData(TypedDict):
    """Control error propagation mode."""
    enabled: NotRequired[bool]  # Set error propagation mode (omit to query current state)


@event_handler("system:error_propagation")
async def handle_error_propagation(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Control error propagation mode."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder
    
    router = get_router()
    
    if "enabled" in data:
        previous = router.set_error_propagation(data["enabled"])
        return event_response_builder(
            {
                "enabled": router._propagate_errors,
                "previous": previous,
                "changed": previous != router._propagate_errors
            },
            context=context
        )
    else:
        return event_response_builder(
            {
                "enabled": router._propagate_errors,
                "mode": "propagate" if router._propagate_errors else "catch"
            },
            context=context
        )


class EventEmitData(TypedDict):
    """Generic event emission data."""
    event: Required[str]  # Target event name
    data: NotRequired[Dict[str, Any]]  # Event data to pass
    delay: NotRequired[float]  # Delay in seconds before emitting
    condition: NotRequired[str]  # Only emit if condition evaluates true


@event_handler("event:emit")
async def handle_emit_event(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
    """Generic event emission - allows any module to emit any event."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    target_event = data.get('event')
    event_data = data.get('data', {})
    delay = data.get('delay', 0)
    condition = data.get('condition')
    
    if not target_event:
        return error_response(
            'Target event name required',
            context=context
        )
    
    # Check condition if provided (simple evaluation for now)
    if condition:
        # For now, just check if condition is "true" or "false" string
        # In future, could add more sophisticated condition evaluation
        if str(condition).lower() == 'false':
            return event_response_builder(
                {'status': 'skipped', 'reason': 'Condition evaluated to false'},
                context=context
            )
    
    # Handle delay if specified
    if delay > 0:
        await asyncio.sleep(delay)
    
    # Emit the event
    router = get_router()
    results = await router.emit(target_event, event_data)
    
    # Return results based on what we got back
    if not results:
        return event_response_builder(
            {'results': [], 'message': f'Event {target_event} emitted with no handlers'},
            context=context
        )
    elif len(results) == 1:
        # For single result, check if it's already a properly formatted response
        result = results[0]
        if isinstance(result, dict) and any(key in result for key in ['status', '_timestamp', '_response_id']):
            # Already formatted, return as-is
            return result
        else:
            # Wrap in response builder
            return event_response_builder(result, context=context)
    else:
        return event_response_builder(
            {'results': results, 'count': len(results)},
            context=context
        )


async def emit_event(event: str, data: Any = None) -> List[Any]:
    """Emit event through global router."""
    router = get_router()
    return await router.emit(event, data)


async def emit_event_first(event: str, data: Any = None) -> Optional[Any]:
    """Emit event and return first result."""
    router = get_router()
    return await router.emit_first(event, data)


# Filter Utilities for Event Handlers
# These provide common filtering patterns for use with @event_handler(filter_func=...)

class RateLimiter:
    """Rate limiting filter for event handlers."""
    
    def __init__(self, max_events: int = 10, window_seconds: float = 1.0):
        """
        Initialize rate limiter.
        
        Args:
            max_events: Maximum events allowed in window
            window_seconds: Time window in seconds
        """
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._event_times: Dict[str, List[float]] = defaultdict(list)
    
    def __call__(self, event: str, data: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if event should be processed based on rate limit."""
        current_time = time.time()
        
        # Get key for rate limiting (could be event name, source, etc.)
        key = event
        if context and "agent_id" in context:
            key = f"{event}:{context['agent_id']}"
        
        # Clean old events outside window
        self._event_times[key] = [
            t for t in self._event_times[key] 
            if current_time - t < self.window_seconds
        ]
        
        # Check rate limit
        if len(self._event_times[key]) >= self.max_events:
            return False
        
        # Record this event
        self._event_times[key].append(current_time)
        return True


def content_filter(field: str, pattern: str = None, value: Any = None, 
                  operator: str = "equals") -> Callable:
    """
    Filter events based on data field content.
    
    Args:
        field: Dot-separated path to field (e.g. "user.id")
        pattern: Regex or glob pattern for matching
        value: Exact value to match
        operator: Comparison operator ("equals", "contains", "gt", "lt", etc.)
    
    Returns:
        Filter function for use with @event_handler
        
    Examples:
        @event_handler("user:update", filter_func=content_filter("role", value="admin"))
        @event_handler("metric:log", filter_func=content_filter("value", value=100, operator="gt"))
    """
    def filter_func(event: str, data: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        # Navigate to field
        current = data
        for part in field.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return False
        
        # Apply comparison
        if pattern:
            if operator == "glob":
                return fnmatch.fnmatch(str(current), pattern)
            else:
                import re
                return bool(re.match(pattern, str(current)))
        elif value is not None:
            if operator == "equals":
                return current == value
            elif operator == "contains":
                return value in str(current)
            elif operator == "gt":
                return current > value
            elif operator == "lt":
                return current < value
            elif operator == "gte":
                return current >= value
            elif operator == "lte":
                return current <= value
        
        return False
    
    return filter_func


def source_filter(allowed_sources: List[str] = None, 
                 blocked_sources: List[str] = None) -> Callable:
    """
    Filter events based on source agent or client.
    
    Args:
        allowed_sources: List of allowed source IDs
        blocked_sources: List of blocked source IDs
        
    Returns:
        Filter function for use with @event_handler
    """
    def filter_func(event: str, data: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        if not context:
            return True
            
        source = context.get("agent_id") or data.get("agent_id")
        
        if blocked_sources and source in blocked_sources:
            return False
            
        if allowed_sources and source not in allowed_sources:
            return False
            
        return True
    
    return filter_func


def combine_filters(*filters: Callable, mode: str = "all") -> Callable:
    """
    Combine multiple filter functions.
    
    Args:
        *filters: Filter functions to combine
        mode: "all" (AND) or "any" (OR)
        
    Returns:
        Combined filter function
        
    Example:
        @event_handler("data:process", 
                      filter_func=combine_filters(
                          content_filter("priority", value="high"),
                          source_filter(allowed_sources=["analyzer_1"]),
                          mode="all"
                      ))
    """
    def combined_filter(event: str, data: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        results = [f(event, data, context) for f in filters]
        
        if mode == "all":
            return all(results)
        elif mode == "any":
            return any(results)
        else:
            raise ValueError(f"Unknown mode: {mode}")
    
    return combined_filter


def data_shape_filter(required_fields: List[str] = None,
                     forbidden_fields: List[str] = None) -> Callable:
    """
    Filter based on data structure/shape.
    
    Args:
        required_fields: Fields that must be present
        forbidden_fields: Fields that must not be present
        
    Returns:
        Filter function
    """
    def filter_func(event: str, data: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        if not isinstance(data, dict):
            return False
            
        if required_fields:
            for field in required_fields:
                # Support nested fields
                current = data
                for part in field.split("."):
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        return False
                        
        if forbidden_fields:
            for field in forbidden_fields:
                current = data
                parts = field.split(".")
                for i, part in enumerate(parts):
                    if isinstance(current, dict) and part in current:
                        if i == len(parts) - 1:
                            return False  # Forbidden field exists
                        current = current[part]
                    else:
                        break  # Field doesn't exist, which is ok
                        
        return True
    
    return filter_func


def context_filter(require_agent: bool = False,
                  require_session: bool = False,
                  require_capability: str = None) -> Callable:
    """
    Filter based on execution context.
    
    Args:
        require_agent: Must have agent_id in context
        require_session: Must have session_id in context  
        require_capability: Must have specific capability
        
    Returns:
        Filter function
    """
    def filter_func(event: str, data: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        if not context:
            return not (require_agent or require_session or require_capability)
            
        if require_agent and not context.get("agent_id"):
            return False
            
        if require_session and not context.get("session_id"):
            return False
            
        if require_capability:
            capabilities = context.get("capabilities", [])
            if require_capability not in capabilities:
                return False
                
        return True
    
    return filter_func


# Convenience instances
rate_limit_10_per_second = RateLimiter(10, 1.0)
rate_limit_100_per_minute = RateLimiter(100, 60.0)
rate_limit_1000_per_hour = RateLimiter(1000, 3600.0)