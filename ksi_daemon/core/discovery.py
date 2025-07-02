#!/usr/bin/env python3
"""
Event Discovery and Introspection Plugin - Event-Based Version

Provides self-documentation capabilities for the KSI daemon:
- List all available events with descriptions
- Get detailed help for specific events
- Show parameter schemas and examples
- Enable agents to discover daemon capabilities autonomously

This is the equivalent of the pre-refactor GET_COMMANDS functionality.
"""

import inspect
import json
from typing import Dict, List, Any, Optional, Callable

from ksi_daemon.event_system import event_handler
from ksi_common.logging import get_bound_logger

# Plugin info
PLUGIN_INFO = {
    "name": "event_discovery",
    "version": "1.0.0",
    "description": "Event discovery and introspection service"
}

# Module state
logger = get_bound_logger("discovery", version="1.0.0")
event_registry: Dict[str, Dict[str, Any]] = {}
event_router = None


def extract_parameter_info(func: Callable) -> Dict[str, Any]:
    """Extract parameter information from a function."""
    sig = inspect.signature(func)
    params = {}
    
    for name, param in sig.parameters.items():
        if name in ['self', 'event_name', 'context', 'client_id']:
            continue  # Skip common parameters
            
        param_info = {
            'type': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'Any',
            'required': param.default == inspect.Parameter.empty,
        }
        
        if param.default != inspect.Parameter.empty:
            param_info['default'] = repr(param.default)
            
        params[name] = param_info
    
    return params


def extract_event_info_from_handler(handler_func: Callable, event_name: str) -> Dict[str, Any]:
    """Extract event information from a handler function."""
    # Get docstring
    docstring = inspect.getdoc(handler_func) or "No description available"
    
    # Extract first line as summary
    lines = docstring.split('\n')
    summary = lines[0].strip()
    
    # Extract parameter info from the data parameter structure if possible
    # This is a simplified version - could be enhanced with type annotations
    params = {}
    
    # Look for parameter documentation in docstring
    in_params = False
    for line in lines:
        line = line.strip()
        if line.lower().startswith(('args:', 'parameters:', 'params:')):
            in_params = True
            continue
        elif line.lower().startswith(('returns:', 'return:', 'example:')):
            in_params = False
            continue
        elif in_params and line:
            # Simple parameter parsing from docstring
            if ':' in line:
                param_name, param_desc = line.split(':', 1)
                param_name = param_name.strip().lstrip('-').strip()
                params[param_name] = {
                    'description': param_desc.strip(),
                    'required': 'optional' not in param_desc.lower()
                }
    
    # Look for examples in docstring
    examples = []
    in_example = False
    example_lines = []
    for line in lines:
        if line.lower().startswith('example:'):
            in_example = True
            continue
        elif in_example:
            if line and not line.startswith(' '):
                in_example = False
            else:
                example_lines.append(line)
    
    if example_lines:
        example_text = '\n'.join(example_lines).strip()
        # Try to parse as JSON
        try:
            example_data = json.loads(example_text)
            examples.append(example_data)
        except (json.JSONDecodeError, ValueError):
            # If not JSON, include as text
            if example_text:
                examples.append({'example': example_text})
    
    return {
        'event': event_name,
        'summary': summary,
        'description': docstring,
        'parameters': params,
        'examples': examples
    }


@event_handler("system:startup")
async def handle_startup(config: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize discovery service."""
    logger.info("Event discovery service started")
    return {"status": "discovery_service_ready"}


@event_handler("system:context")
async def handle_context(context: Dict[str, Any]) -> None:
    """Receive the event router context."""
    global plugin_loader
    plugin_loader = context.get('plugin_manager')  # In event system, this is the loader


@event_handler("system:discover")
async def handle_discover_events(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Discover all available events in the system.
    
    Parameters:
        namespace: Optional namespace filter (e.g., "agent", "completion")
        include_internal: Include internal system events (default: False)
    
    Returns:
        Dictionary with available events grouped by namespace
    """
    namespace_filter = data.get('namespace')
    include_internal = data.get('include_internal', False)
    
    # Collect all known events from plugins dynamically
    events_by_namespace = {}
    
    # In the event system, we'll need to introspect the router
    from ksi_daemon.event_system import get_router
    router = get_router()
    
    # Get all registered handlers
    for event_name, handlers in router._handlers.items():
        if ':' in event_name:
            namespace = event_name.split(':')[0]
        else:
            namespace = 'default'
            
        if namespace not in events_by_namespace:
            events_by_namespace[namespace] = []
            
        # Extract info from handlers
        for handler in handlers:
            # Get handler info
            event_info = {
                'event': event_name,
                'summary': handler.func.__doc__.split('\n')[0] if handler.func.__doc__ else 'No description',
                'handler': handler.name,
                'module': handler.module
            }
            events_by_namespace[namespace].append(event_info)
    
    # Filter by namespace if requested
    if namespace_filter:
        filtered = {}
        for ns, events in events_by_namespace.items():
            if ns == namespace_filter or ns.startswith(namespace_filter + ':'):
                filtered[ns] = events
        events_by_namespace = filtered
    
    # Filter out internal events if requested
    if not include_internal:
        # Remove internal namespaces (could be configurable)
        internal_namespaces = ['debug', 'plugin']
        for ns in internal_namespaces:
            events_by_namespace.pop(ns, None)
    
    # Count total events
    total_events = sum(len(events) for events in events_by_namespace.values())
    
    return {
        "namespaces": list(events_by_namespace.keys()),
        "events": events_by_namespace,
        "total_events": total_events
    }


@event_handler("system:help")
async def handle_event_help(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get detailed help for a specific event.
    
    Args:
        event (str): The event name to get help for (required)
    
    Returns:
        Detailed event documentation including parameters and examples
    """
    event_name = data.get('event')
    if not event_name:
        return {"error": "event parameter required"}
    
    # Parse namespace and event
    if ':' in event_name:
        namespace, event_part = event_name.split(':', 1)
    else:
        return {"error": f"Invalid event format: {event_name}. Use namespace:event"}
    
    # Get all events including internal ones
    all_events = await handle_discover_events({"include_internal": True})
    events_in_namespace = all_events['events'].get(namespace, [])
    
    # Find the specific event
    for event_info in events_in_namespace:
        if event_info['event'] == event_name:
            # Get handler to extract more info
            from ksi_daemon.event_system import get_router
            router = get_router()
            
            handlers = router._handlers.get(event_name, [])
            if handlers:
                handler = handlers[0]  # Use first handler
                
                # Extract detailed info from handler
                detailed_info = extract_event_info_from_handler(handler.func, event_name)
                
                # Add examples if available
                examples = detailed_info.get('examples', [])
                
                # Generate example based on parameters
                if detailed_info.get('parameters'):
                    example_data = {}
                    for param, info in detailed_info['parameters'].items():
                        if info.get('required'):
                            # Provide example values based on type
                            param_type = info.get('type', 'str')
                            if 'str' in param_type:
                                example_data[param] = f"example_{param}"
                            elif 'int' in param_type:
                                example_data[param] = 123
                            elif 'bool' in param_type:
                                example_data[param] = True
                            elif 'dict' in param_type:
                                example_data[param] = {"key": "value"}
                            elif 'list' in param_type:
                                example_data[param] = ["item1", "item2"]
                            else:
                                example_data[param] = f"<{param_type}>"
                    
                    examples.append({
                        "description": "Basic example with required parameters",
                        "data": example_data
                    })
                
                return {
                    "event": event_name,
                    "namespace": namespace,
                    "summary": detailed_info.get('summary', ''),
                    "parameters": detailed_info.get('parameters', {}),
                    "examples": examples,
                    "handler": handler.name,
                    "module": handler.module
                }
    
    return {"error": f"Event not found: {event_name}"}


@event_handler("system:capabilities")
async def handle_capabilities(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get a summary of daemon capabilities."""
    # Get all events
    all_events = await handle_discover_events({'include_internal': True})
    
    # Summarize by namespace
    capabilities = {
        "version": "3.0.0",  # KSI daemon version (event-based)
        "event_based": True,
        "namespaces": {}
    }
    
    for namespace, events in all_events['events'].items():
        capabilities['namespaces'][namespace] = {
            "event_count": len(events),
            "description": get_namespace_description(namespace)
        }
    
    return capabilities


def get_namespace_description(namespace: str) -> str:
    """Get description for a namespace."""
    descriptions = {
        "system": "Core daemon functionality and health",
        "completion": "LLM completion services",
        "agent": "Agent lifecycle and management",
        "state": "Persistent state storage",
        "message": "Inter-agent messaging",
        "conversation": "Conversation history and search",
        "correlation": "Request tracing and debugging",
        "transport": "Communication transports",
        "injection": "Response injection and transformation",
        "orchestration": "Multi-agent orchestration"
    }
    return descriptions.get(namespace, f"{namespace} services")


@event_handler("system:shutdown")
async def handle_shutdown(data: Dict[str, Any]) -> None:
    """Clean up on shutdown."""
    logger.info("Event discovery service stopped")


