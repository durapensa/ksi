#!/usr/bin/env python3
"""
Plugin Migration Helpers

Provides compatibility layer and migration utilities for converting
pluggy-based plugins to the pure event system.
"""

import inspect
from typing import Dict, Any, Callable, Optional, List
from functools import wraps

from .event_system import event_handler, EventPriority, get_router


class PluggyCompat:
    """Compatibility layer for pluggy patterns."""
    
    def __init__(self, plugin_name: str):
        self.plugin_name = plugin_name
        self._markers = {}
        
    def HookimplMarker(self, project_name: str):
        """Create hookimpl marker compatible with pluggy syntax."""
        def hookimpl(function=None, hookwrapper=False, optionalhook=False,
                    tryfirst=False, trylast=False, specname=None):
            
            if function is None:
                # Decorator with arguments
                def decorator(func):
                    return self._convert_hook(func, tryfirst, trylast, specname)
                return decorator
            else:
                # Decorator without arguments
                return self._convert_hook(function, False, False, None)
                
        return hookimpl
    
    def _convert_hook(self, func: Callable, tryfirst: bool, trylast: bool, 
                     specname: Optional[str]) -> Callable:
        """Convert a pluggy hook to event handler."""
        # Determine priority
        priority = EventPriority.NORMAL
        if tryfirst:
            priority = EventPriority.HIGH
        elif trylast:
            priority = EventPriority.LOW
            
        # Get hook name
        hook_name = specname or func.__name__
        
        # Special handling for different hooks
        if hook_name == "ksi_startup":
            @event_handler("system:startup", priority=priority)
            async def startup_handler(config: Dict[str, Any]) -> Dict[str, Any]:
                # Call original sync function
                result = func(config)
                return result or {"status": "ready"}
            return startup_handler
            
        elif hook_name == "ksi_ready":
            @event_handler("system:ready", priority=priority) 
            async def ready_handler(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
                # Call original function
                result = func()
                return result
            return ready_handler
            
        elif hook_name == "ksi_handle_event":
            # This needs special handling - register a general handler
            async def handle_event_wrapper(event_name: str, data: Dict[str, Any], 
                                         context: Dict[str, Any]) -> Any:
                # Call original handler
                result = func(event_name, data, context)
                
                # Handle async results
                if inspect.iscoroutine(result):
                    return await result
                return result
                
            # Store for manual registration later
            func._handle_event_wrapper = handle_event_wrapper
            return func
            
        elif hook_name == "ksi_shutdown":
            @event_handler("system:shutdown", priority=priority)
            async def shutdown_handler(data: Dict[str, Any]) -> None:
                # Call original function
                func()
            return shutdown_handler
            
        elif hook_name == "ksi_plugin_context":
            @event_handler("system:context", priority=priority)
            async def context_handler(context: Dict[str, Any]) -> None:
                # Call original function
                func(context)
            return context_handler
            
        elif hook_name == "ksi_create_transport":
            @event_handler("transport:create", priority=priority)
            async def transport_handler(data: Dict[str, Any]) -> Any:
                transport_type = data.get("transport_type")
                config = data.get("config", {})
                return func(transport_type, config)
            return transport_handler
            
        elif hook_name == "ksi_describe_events":
            @event_handler("discovery:events", priority=priority)
            async def describe_handler(data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
                return func()
            return describe_handler
            
        else:
            # Generic conversion for other hooks
            event_map = {
                "ksi_plugin_loaded": "system:plugin_loaded",
                "ksi_pre_event": "event:pre",
                "ksi_post_event": "event:post",
                "ksi_event_error": "event:error",
                "ksi_handle_connection": "transport:connection",
                "ksi_serialize_event": "transport:serialize",
                "ksi_deserialize_event": "transport:deserialize",
                "ksi_provide_service": "service:provide",
                "ksi_service_dependencies": "service:dependencies",
                "ksi_register_namespace": "namespace:register",
                "ksi_register_commands": "extension:commands",
                "ksi_register_validators": "extension:validators",
                "ksi_metrics_collected": "metrics:collected",
            }
            
            if hook_name in event_map:
                event_name = event_map[hook_name]
                
                @event_handler(event_name, priority=priority)
                async def generic_handler(data: Dict[str, Any]) -> Any:
                    # Map data to hook arguments
                    result = func(**data)
                    if inspect.iscoroutine(result):
                        return await result
                    return result
                    
                return generic_handler
                
        # If no mapping found, return original
        return func


def migrate_plugin(module_path: str) -> str:
    """
    Helper to show how to migrate a plugin.
    Returns the migrated code as a string.
    """
    # This would analyze the plugin and suggest migrations
    # For now, return a template
    return '''#!/usr/bin/env python3
"""
Plugin migrated to pure event system.

Migration checklist:
[ ] Replace "import pluggy" with "from ksi_daemon.event_system import event_handler"
[ ] Replace "hookimpl = pluggy.HookimplMarker('ksi')" with event decorators
[ ] Convert @hookimpl functions to @event_handler
[ ] Update ksi_handle_event to use individual handlers
[ ] Convert ksi_ready to return task specifications
[ ] Test all functionality
"""

from typing import Dict, Any, List, Optional
from ksi_daemon.event_system import event_handler, emit_event
from ksi_common.logging import get_bound_logger

logger = get_bound_logger(__name__)

# Example migrations:

# Before: @hookimpl
# After:
@event_handler("system:startup")
async def handle_startup(config: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize plugin."""
    logger.info("Plugin starting up")
    return {"status": "ready"}

# Before: @hookimpl / def ksi_handle_event(event_name, data, context):
# After: Individual handlers for each event
@event_handler("mymodule:action")
async def handle_my_action(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle specific action."""
    result = process_action(data)
    return {"result": result}

# Background tasks via system:ready
@event_handler("system:ready")
async def handle_ready(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return background task specifications."""
    return {
        "service": "my_service",
        "tasks": [{
            "name": "monitor",
            "coroutine": monitor_task()
        }]
    }

# Module marker (keep this)
ksi_plugin = True
'''


def create_migration_report(plugin_path: str) -> Dict[str, Any]:
    """Analyze a plugin and create migration report."""
    # This would analyze the plugin code and identify:
    # - Which hooks are used
    # - What events are handled
    # - What services are provided
    # - What background tasks exist
    
    return {
        "plugin": plugin_path,
        "hooks_used": [],
        "events_handled": [],
        "migration_complexity": "medium",
        "estimated_effort": "1-2 hours",
        "notes": []
    }