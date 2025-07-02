#!/usr/bin/env python3
"""
Pure Event-Based Module System for KSI

Native async event-driven architecture for modular functionality.
All modules communicate via events with clear async patterns.
"""

import asyncio
import inspect
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
        """Get detailed information about a specific module using direct function inspection."""
        if module_name not in self._modules:
            return None
        
        # Get handlers and directly inspect their stored metadata
        handlers = []
        for handler in self._handlers_by_module[module_name]:
            handler_info = {
                "event": handler.event,
                "function": handler.name,
                "priority": handler.priority,
                "async": handler.is_async,
                "filter": handler.filter_func is not None
            }
            
            # Read metadata directly from function (single source of truth)
            if hasattr(handler.func, '_event_metadata'):
                metadata = handler.func._event_metadata
                handler_info.update({
                    "summary": metadata.summary,
                    "description": metadata.description,
                    "parameters": [
                        {
                            "name": p.name,
                            "type": p.type_name,
                            "required": p.required,
                            "description": p.description,
                            "example": p.example
                        }
                        for p in metadata.parameters
                    ],
                    "returns": metadata.returns,
                    "tags": metadata.tags,
                    "performance": {
                        "typical_duration_ms": metadata.typical_duration_ms,
                        "has_side_effects": metadata.has_side_effects,
                        "has_cost": metadata.has_cost
                    },
                    "best_practices": metadata.best_practices,
                    "examples": [ex.to_dict() for ex in metadata.examples]
                })
            
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


# Decorators for the new system

def event_handler(event: str, 
                 priority: int = EventPriority.NORMAL, 
                 filter_func: Optional[Callable] = None,
                 # Rich metadata parameters
                 summary: Optional[str] = None,
                 description: Optional[str] = None,
                 data_type: Optional[Type] = None,
                 returns: Optional[str] = None,
                 tags: Optional[List[str]] = None,
                 
                 # Enhanced parameter and example definitions
                 parameters=None,  # Optional[List[EventParameter]]
                 examples=None,    # Optional[List[EventExample]] 
                 
                 # Performance characteristics
                 async_response: bool = False,
                 typical_duration_ms: Optional[int] = None,
                 has_side_effects: bool = True,
                 idempotent: bool = False,
                 
                 # Resource requirements
                 has_cost: bool = False,
                 requires_auth: bool = False,
                 rate_limited: bool = False,
                 
                 # Documentation and best practices
                 best_practices: Optional[List[str]] = None,
                 common_errors: Optional[List[str]] = None,
                 related_events: Optional[List[str]] = None):
    """
    Decorator for event handlers with optional rich metadata.
    
    Basic usage: @event_handler("event_name")
    Rich usage: @event_handler("event_name", summary="...", data_type=MyType, ...)
    """
    def decorator(func: Callable) -> Callable:
        # Create handler wrapper
        handler = EventHandler(func, event, priority, filter_func)
        
        # Store metadata on function (for inspection)
        func._event_handler = handler
        func._event_name = event
        func._event_priority = priority
        
        # AUTO-REGISTER: Register with global router immediately at import time
        router = get_router()
        router.register_handler(event, handler)
        
        # ALWAYS create and store metadata directly on function (single source of truth)
        # This enables automatic parameter discovery via direct inspection
        try:
            from ksi_daemon.metadata_registry import EventMetadata, EventParameter, EventExample, extract_parameter_info
            
            # Use explicit parameters if provided, otherwise extract from function/TypedDict
            if parameters:
                # Parameters already provided as EventParameter objects
                param_list = parameters
            else:
                # Extract parameter information from function signature and TypedDict
                param_list = extract_parameter_info(func, data_type)
            
            # Handle examples - convert dict examples to EventExample objects if needed
            example_list = []
            if examples:
                for ex in examples:
                    if isinstance(ex, dict):
                        # Convert legacy dict format to EventExample
                        example_list.append(EventExample(
                            description=ex.get("description", "Example usage"),
                            data=ex.get("data", ex),
                            context=ex.get("context"),
                            expected_result=ex.get("expected_result")
                        ))
                    else:
                        # Assume it's already an EventExample object
                        example_list.append(ex)
            
            # Create comprehensive metadata - auto-generate summary if not provided
            auto_summary = summary or f"Handle {event} event"
            auto_description = description or func.__doc__ or f"Event handler for {event}"
            
            metadata = EventMetadata(
                event_name=event,
                function_name=func.__name__,
                module_name=func.__module__,
                summary=auto_summary,
                description=auto_description,
                parameters=param_list,
                returns=returns,
                examples=example_list,
                tags=tags or [],
                
                # Performance characteristics
                async_response=async_response,
                typical_duration_ms=typical_duration_ms,
                has_side_effects=has_side_effects,
                idempotent=idempotent,
                
                # Resource requirements
                has_cost=has_cost,
                requires_auth=requires_auth,
                rate_limited=rate_limited,
                
                # Documentation and best practices
                best_practices=best_practices or [],
                common_errors=common_errors or [],
                related_events=related_events or [],
                
                # Technical metadata
                async_handler=inspect.iscoroutinefunction(func)
            )
            
            # Store metadata directly on function (ONLY source of truth)
            func._event_metadata = metadata
            
            logger.debug(f"Stored comprehensive metadata on function {func.__name__} for {event}")
            
        except ImportError:
            # Metadata system not available, continue without it
            logger.debug(f"Metadata system not available for {event}")
        
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