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
from typing import Dict, Any, List, Callable, Optional, Set, Union, TypeVar, Tuple, Type
from functools import wraps
import sys
from collections import defaultdict
from pathlib import Path

from ksi_common.logging import get_bound_logger

logger = get_bound_logger("event_system", version="2.0.0")

T = TypeVar('T')



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
        
    async def __call__(self, data: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """Execute the handler."""
        # Apply filter if present
        if self.filter_func and not self.filter_func(self.event, data, context):
            return None
        
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
    """Pure async event router - the heart of the new plugin system."""
    
    def __init__(self):
        import time
        
        # Track router start time for uptime calculation
        self._start_time = time.time()
        
        # Event handlers organized by event name and priority
        self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        
        # Pattern handlers for wildcard matching (e.g., "state:*")
        self._pattern_handlers: List[Tuple[str, EventHandler]] = []
        
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
        
    async def emit(self, event: str, data: Any = None, 
                   context: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Emit an event to all matching handlers."""
        # During shutdown, only allow shutdown-related events
        if self._shutdown_in_progress:
            allowed_events = {"system:shutdown", "shutdown:acknowledge", "system:shutdown_complete",
                            "event:error", "log:*"}  # Allow logging during shutdown
            if not any(event == allowed or (allowed.endswith('*') and event.startswith(allowed[:-1])) 
                      for allowed in allowed_events):
                logger.debug(f"Blocking event {event} during shutdown")
                return []
        
        if data is None:
            data = {}
            
        # Create context if not provided
        if context is None:
            context = {
                "event": event,
                "router": self
            }
        else:
            context["event"] = event
            context["router"] = self
        
        # Log event to event log if available
        if hasattr(self, 'event_log') and self.event_log:
            # Strip large payloads and file references
            log_data = self._prepare_log_data(event, data)
            
            # Extract metadata for logging
            client_id = context.get("client_id") or context.get("agent_id")
            correlation_id = context.get("correlation_id")
            event_id = context.get("event_id") or data.get("request_id")
            
            # Log the event
            self.event_log.log_event(
                event_name=event,
                data=log_data,
                client_id=client_id,
                correlation_id=correlation_id,
                event_id=event_id
            )
        
        # Check for observation - extract source agent from context or data
        source_agent = context.get("agent_id") or context.get("source_agent") or data.get("agent_id")
        observation_id = None
        matching_subscriptions = []
        
        # Don't observe observation events to prevent loops
        if source_agent and not event.startswith("observe:") and not event.startswith("observation:"):
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
            return []
            
        # Execute handlers concurrently
        results = await asyncio.gather(
            *[handler(data, context) for handler in handlers],
            return_exceptions=True
        )
        
        # Filter results
        valid_results = []
        errors = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Handler {handlers[i].name} failed for {event}: {result}")
                errors.append({
                    "handler": handlers[i].name,
                    "error": str(result)
                })
                # Emit error event
                await self.emit("event:error", {
                    "event": event,
                    "handler": handlers[i].name,
                    "error": str(result)
                })
            elif result is not None:
                valid_results.append(result)
        
        # Notify observers of event completion
        if matching_subscriptions:
            observation_result = {
                "results": valid_results,
                "errors": errors,
                "handler_count": len(handlers)
            }
            await notify_observers_async(matching_subscriptions, "end", event, 
                                       observation_result, source_agent)
                
        return valid_results
        
    async def emit_first(self, event: str, data: Any = None,
                        context: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """Emit event and return first non-None result."""
        results = await self.emit(event, data, context)
        return results[0] if results else None
        
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
                
        task = asyncio.create_task(task_wrapper())
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
            # Emit completion event
            await self.emit("system:shutdown_complete", {
                "services": list(self._shutdown_acknowledgments)
            })
    
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
            
        source = context.get("agent_id") or context.get("client_id") or data.get("agent_id")
        
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