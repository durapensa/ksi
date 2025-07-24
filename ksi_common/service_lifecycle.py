#!/usr/bin/env python3
"""
Service Lifecycle - Standardized patterns for service startup and shutdown.

Eliminates repetitive lifecycle code across KSI services:
- Startup handlers with automatic ready responses
- Shutdown handlers with cleanup patterns  
- Async operation cleanup utilities
- Service registration patterns
"""

import asyncio
from typing import Dict, Any, Optional, Callable, List
from functools import wraps

from ksi_common.logging import get_bound_logger
from ksi_common.event_response_builder import event_response_builder
from ksi_common.response_patterns import service_ready_response
from ksi_common.service_transformer_manager import auto_load_service_transformers
from ksi_daemon.event_system import event_handler

def service_startup(
    service_name: str, 
    load_transformers: bool = True,
    additional_tasks: Optional[List[Dict[str, Any]]] = None
):
    """
    Decorator for standardized service startup handling.
    
    Args:
        service_name: Name of the service (e.g., "agent_service")
        load_transformers: Whether to auto-load service transformers
        additional_tasks: Optional list of background tasks to return
        
    Example:
        @service_startup("my_service")
        async def startup(data, context):
            # Custom initialization code here
            await initialize_database()
            return {"extra_field": "value"}  # Will be added to ready response
            
    The decorator will:
    1. Log service startup
    2. Load transformers if enabled
    3. Call your custom startup code
    4. Return standardized ready response with any extra fields
    """
    def decorator(func):
        @event_handler("system:startup")
        @wraps(func)
        async def wrapper(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            logger = get_bound_logger(service_name)
            logger.info(f"{service_name} starting...")
            
            # Load transformers if requested
            transformer_result = None
            if load_transformers:
                try:
                    # Try to get event_emitter from various sources
                    event_emitter = None
                    if hasattr(func, '__globals__'):
                        # Look for event_emitter in the function's module
                        event_emitter = func.__globals__.get('event_emitter')
                        if not event_emitter:
                            # Try getting router and using its emit method
                            from ksi_daemon.event_system import get_router
                            router = get_router()
                            if router:
                                event_emitter = router.emit
                    
                    transformer_result = await auto_load_service_transformers(service_name, event_emitter)
                    if transformer_result.get("status") == "success":
                        logger.info(f"Loaded {transformer_result.get('total_loaded', 0)} {service_name} transformers")
                    else:
                        logger.warning(f"Issue loading {service_name} transformers: {transformer_result}")
                except Exception as e:
                    logger.warning(f"Failed to load {service_name} transformers: {e}")
            
            # Call the actual startup function
            extra_fields = {}
            if asyncio.iscoroutinefunction(func):
                result = await func(data, context)
            else:
                result = func(data, context)
                
            # Extract extra fields from result
            if isinstance(result, dict):
                extra_fields = result
                
            # Add transformer result if available
            if transformer_result:
                extra_fields["transformer_result"] = transformer_result
                
            # Add background tasks if provided
            if additional_tasks:
                extra_fields["tasks"] = additional_tasks
            
            # Return standardized ready response
            return service_ready_response(service_name, context, **extra_fields)
            
        return wrapper
    return decorator

def service_shutdown(service_name: str, cleanup_async_operations: bool = False):
    """
    Decorator for standardized service shutdown handling.
    
    Args:
        service_name: Name of the service
        cleanup_async_operations: Whether to cleanup async operations
        
    Example:
        @service_shutdown("my_service", cleanup_async_operations=True)
        async def shutdown(data, context):
            # Custom cleanup code here
            await close_database()
    """
    def decorator(func):
        @event_handler("system:shutdown")
        @wraps(func)
        async def wrapper(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
            logger = get_bound_logger(service_name)
            logger.info(f"{service_name} shutting down...")
            
            # Cleanup async operations if requested
            if cleanup_async_operations:
                try:
                    from ksi_common.async_operations import active_operations, cancel_operation
                    for op_id, op_data in list(active_operations.items()):
                        if op_data.get("service") == service_name:
                            logger.info(f"Cancelling active operation {op_id}")
                            await cancel_operation(op_id)
                except Exception as e:
                    logger.error(f"Error cleaning up async operations: {e}")
            
            # Call the actual shutdown function
            if asyncio.iscoroutinefunction(func):
                await func(data, context)
            else:
                func(data, context)
                
            logger.info(f"{service_name} shutdown complete")
            
        return wrapper
    return decorator

def service_ready_handler(
    service_name: str,
    load_transformers: bool = True,
    background_tasks: Optional[Callable] = None
):
    """
    Decorator for system:ready handlers with transformer loading.
    
    Args:
        service_name: Name of the service
        load_transformers: Whether to load transformers
        background_tasks: Optional callable that returns task list
        
    Example:
        @service_ready_handler("my_service")
        async def ready(data, context):
            # Optional: Additional ready logic
            return {"agents_loaded": 5}
    """
    def decorator(func):
        @event_handler("system:ready")
        @wraps(func)
        async def wrapper(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            logger = get_bound_logger(service_name)
            
            # Load transformers if requested
            transformer_result = None
            if load_transformers:
                try:
                    # Get event_emitter
                    event_emitter = None
                    if hasattr(func, '__globals__'):
                        event_emitter = func.__globals__.get('event_emitter') or func.__globals__.get('_event_emitter')
                    
                    transformer_result = await auto_load_service_transformers(service_name, event_emitter)
                    if transformer_result.get("status") == "success":
                        logger.info(f"Loaded {transformer_result.get('total_loaded', 0)} {service_name} transformers")
                    else:
                        logger.warning(f"Issue loading {service_name} transformers: {transformer_result}")
                except Exception as e:
                    logger.warning(f"Failed to load {service_name} transformers: {e}")
            
            # Call the actual ready function
            extra_fields = {}
            if asyncio.iscoroutinefunction(func):
                result = await func(data, context)
            else:
                result = func(data, context)
                
            if isinstance(result, dict):
                extra_fields = result
                
            # Build response
            response_data = {
                "service": service_name,
                "status": "ready"
            }
            
            if transformer_result:
                response_data["transformer_result"] = transformer_result
                
            # Add background tasks if provided
            if background_tasks:
                tasks = background_tasks() if callable(background_tasks) else background_tasks
                response_data["tasks"] = tasks
                
            response_data.update(extra_fields)
            
            return event_response_builder(response_data, context)
            
        return wrapper
    return decorator

class ServiceLifecycleMixin:
    """
    Mixin class for services with standard lifecycle patterns.
    
    Example:
        class MyService(ServiceLifecycleMixin):
            def __init__(self):
                super().__init__("my_service", load_transformers=True)
                
            async def initialize(self):
                # Custom initialization
                pass
                
            async def cleanup(self):
                # Custom cleanup
                pass
    """
    
    def __init__(self, service_name: str, load_transformers: bool = True):
        self.service_name = service_name
        self.load_transformers = load_transformers
        self.logger = get_bound_logger(service_name)
        
    async def handle_startup(self, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Standard startup handler."""
        self.logger.info(f"{self.service_name} starting...")
        
        # Load transformers
        transformer_result = None
        if self.load_transformers:
            transformer_result = await auto_load_service_transformers(self.service_name)
            if transformer_result.get("status") == "success":
                self.logger.info(f"Loaded {transformer_result.get('total_loaded', 0)} transformers")
                
        # Call custom initialization
        if hasattr(self, 'initialize'):
            await self.initialize()
            
        return service_ready_response(
            self.service_name, 
            context,
            transformer_result=transformer_result
        )
        
    async def handle_shutdown(self, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
        """Standard shutdown handler."""
        self.logger.info(f"{self.service_name} shutting down...")
        
        # Call custom cleanup
        if hasattr(self, 'cleanup'):
            await self.cleanup()
            
        self.logger.info(f"{self.service_name} shutdown complete")

# Convenience decorators for common patterns
def simple_service(service_name: str):
    """
    All-in-one decorator for simple services with standard lifecycle.
    
    Applies both startup and shutdown decorators with defaults.
    
    Example:
        @simple_service("my_service")
        class MyServiceHandlers:
            @staticmethod
            async def startup(data, context):
                # Optional custom startup
                pass
                
            @staticmethod  
            async def shutdown(data, context):
                # Optional custom shutdown
                pass
    """
    def decorator(cls):
        # Apply decorators to methods if they exist
        if hasattr(cls, 'startup'):
            cls.startup = service_startup(service_name)(cls.startup)
        else:
            # Create default startup
            @service_startup(service_name)
            async def startup(data, context):
                pass
            cls.startup = startup
            
        if hasattr(cls, 'shutdown'):
            cls.shutdown = service_shutdown(service_name)(cls.shutdown)
        else:
            # Create default shutdown
            @service_shutdown(service_name)
            async def shutdown(data, context):
                pass
            cls.shutdown = shutdown
            
        return cls
    return decorator