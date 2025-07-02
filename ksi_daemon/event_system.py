#!/usr/bin/env python3
"""
Pure Event-Based Plugin System for KSI

Replaces pluggy with a native async event-driven architecture.
All former hooks are now events with clear async patterns.
"""

import asyncio
import inspect
from typing import Dict, Any, List, Callable, Optional, Set, Union, TypeVar, Tuple
from functools import wraps
import sys
from collections import defaultdict
from pathlib import Path

from ksi_common.logging import get_bound_logger

logger = get_bound_logger("event_system", version="2.0.0")

T = TypeVar('T')

# Event type mappings from pluggy hooks
HOOK_TO_EVENT_MAP = {
    # Lifecycle hooks -> system events
    "ksi_startup": "system:startup",
    "ksi_ready": "system:ready",
    "ksi_shutdown": "system:shutdown",
    "ksi_plugin_context": "system:context",
    "ksi_plugin_loaded": "system:plugin_loaded",
    
    # Event processing hooks stay similar
    "ksi_pre_event": "event:pre",
    "ksi_handle_event": None,  # Special - stays as direct handler
    "ksi_post_event": "event:post", 
    "ksi_event_error": "event:error",
    
    # Transport hooks -> transport events
    "ksi_create_transport": "transport:create",
    "ksi_handle_connection": "transport:connection",
    "ksi_serialize_event": "transport:serialize",
    "ksi_deserialize_event": "transport:deserialize",
    
    # Service hooks -> service events
    "ksi_provide_service": "service:provide",
    "ksi_service_dependencies": "service:dependencies",
    "ksi_register_namespace": "namespace:register",
    
    # Discovery hooks -> discovery events
    "ksi_describe_events": "discovery:events",
    
    # Extension hooks -> extension events
    "ksi_register_commands": "extension:commands",
    "ksi_register_validators": "extension:validators",
    "ksi_metrics_collected": "metrics:collected",
}


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
            
        # Execute handler
        if self.is_async:
            return await self.func(data, context) if context is not None else await self.func(data)
        else:
            # Run sync handlers in thread pool
            loop = asyncio.get_event_loop()
            if context is not None:
                return await loop.run_in_executor(None, self.func, data, context)
            else:
                return await loop.run_in_executor(None, self.func, data)


class EventRouter:
    """Pure async event router - the heart of the new plugin system."""
    
    def __init__(self):
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
        
        # Plugin metadata
        self._plugins: Dict[str, Dict[str, Any]] = {}
        
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
            
        logger.debug(f"Registered handler {handler.name} for event {event} (priority={handler.priority})")
        
    def register_service(self, name: str, service: Any):
        """Register a service instance."""
        self._services[name] = service
        logger.info(f"Registered service: {name}")
        
    def get_service(self, name: str) -> Optional[Any]:
        """Get a registered service."""
        return self._services.get(name)
        
    async def emit(self, event: str, data: Any = None, 
                   context: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Emit an event to all matching handlers."""
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
            return []
            
        # Execute handlers concurrently
        results = await asyncio.gather(
            *[handler(data, context) for handler in handlers],
            return_exceptions=True
        )
        
        # Filter results
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Handler {handlers[i].name} failed for {event}: {result}")
                # Emit error event
                await self.emit("event:error", {
                    "event": event,
                    "handler": handlers[i].name,
                    "error": str(result)
                })
            elif result is not None:
                valid_results.append(result)
                
        return valid_results
        
    async def emit_first(self, event: str, data: Any = None,
                        context: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """Emit event and return first non-None result (like pluggy)."""
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
        
    async def start_task(self, name: str, coro: Callable, *args, **kwargs):
        """Start a background task."""
        if name in self._tasks:
            logger.warning(f"Task {name} already running")
            return
            
        async def task_wrapper():
            try:
                await coro(*args, **kwargs)
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
            
    def register_plugin(self, name: str, metadata: Dict[str, Any]):
        """Register plugin metadata."""
        self._plugins[name] = metadata
        
    def get_plugins(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered plugins."""
        return self._plugins.copy()


# Decorators for the new system

def event_handler(event: str, priority: int = EventPriority.NORMAL, 
                 filter_func: Optional[Callable] = None):
    """Decorator for event handlers in the new system."""
    def decorator(func: Callable) -> Callable:
        # Store metadata on function
        func._event_handler = EventHandler(func, event, priority, filter_func)
        func._event_name = event
        func._event_priority = priority
        return func
    return decorator


def service_provider(service_name: str):
    """Decorator to mark a service provider."""
    def decorator(func: Callable) -> Callable:
        func._provides_service = service_name
        return func
    return decorator


def background_task(name: str):
    """Decorator to mark a background task."""
    def decorator(func: Callable) -> Callable:
        func._background_task = name
        return func
    return decorator


# Backward compatibility helpers

def hookimpl_compat(trylast: bool = False, tryfirst: bool = False):
    """Compatibility decorator to help migration from @hookimpl."""
    priority = EventPriority.NORMAL
    if trylast:
        priority = EventPriority.LOW
    elif tryfirst:
        priority = EventPriority.HIGH
        
    def decorator(func: Callable) -> Callable:
        # Extract hook name from function name
        hook_name = func.__name__
        if hook_name in HOOK_TO_EVENT_MAP:
            event_name = HOOK_TO_EVENT_MAP[hook_name]
            if event_name:  # Some hooks don't map directly
                return event_handler(event_name, priority=priority)(func)
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