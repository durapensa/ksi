#!/usr/bin/env python3
"""
Event Discovery and Introspection Plugin

Provides self-documentation capabilities for the KSI daemon:
- List all available events with descriptions
- Get detailed help for specific events
- Show parameter schemas and examples
- Enable agents to discover daemon capabilities autonomously

This is the equivalent of the pre-refactor GET_COMMANDS functionality.
"""

import inspect
import json
import logging
from typing import Dict, List, Any, Optional, Callable
import pluggy

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Plugin info
PLUGIN_INFO = {
    "name": "event_discovery",
    "version": "1.0.0",
    "description": "Event discovery and introspection service"
}

# Module state
logger = logging.getLogger(__name__)
event_registry: Dict[str, Dict[str, Any]] = {}
plugin_manager = None


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
        except:
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


@hookimpl
def ksi_startup(config):
    """Initialize discovery service."""
    logger.info("Event discovery service started")
    return {"status": "discovery_service_ready"}


@hookimpl
def ksi_plugin_loaded(plugin_name: str, plugin_instance: Any):
    """Track loaded plugins and their events."""
    global plugin_manager
    
    # Try to discover events from the plugin
    if hasattr(plugin_instance, 'ksi_handle_event'):
        # This plugin handles events
        logger.info(f"Discovering events from plugin: {plugin_name}")
        
        # Store reference to handler
        if plugin_name not in event_registry:
            event_registry[plugin_name] = {
                'plugin_name': plugin_name,
                'handler': plugin_instance.ksi_handle_event,
                'events': {}
            }
        
        # Try to extract metadata if available
        if hasattr(plugin_instance, 'PLUGIN_INFO'):
            info = plugin_instance.PLUGIN_INFO
            event_registry[plugin_name]['description'] = info.get('description', '')
            event_registry[plugin_name]['version'] = info.get('version', '')


@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Handle discovery-related events."""
    
    if event_name == "system:discover":
        # List all available events
        return handle_discover_events(data)
    
    elif event_name == "system:help":
        # Get help for a specific event
        return handle_event_help(data)
    
    elif event_name == "system:capabilities":
        # Get daemon capabilities summary
        return handle_capabilities(data)
    
    return None


def handle_discover_events(data: Dict[str, Any]) -> Dict[str, Any]:
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
    
    # Collect all known events
    events_by_namespace = {}
    
    # Hardcoded core events (should be generated from actual handlers)
    core_events = {
        "system": [
            {
                "event": "system:health",
                "summary": "Check daemon health status",
                "parameters": {}
            },
            {
                "event": "system:shutdown",
                "summary": "Gracefully shutdown the daemon",
                "parameters": {
                    "force": {"type": "bool", "required": False, "default": "False"}
                }
            },
            {
                "event": "system:discover",
                "summary": "Discover available events",
                "parameters": {
                    "namespace": {"type": "str", "required": False},
                    "include_internal": {"type": "bool", "required": False, "default": "False"}
                }
            },
            {
                "event": "system:help",
                "summary": "Get detailed help for an event",
                "parameters": {
                    "event": {"type": "str", "required": True}
                }
            }
        ],
        "completion": [
            {
                "event": "completion:request",
                "summary": "Request a synchronous completion",
                "parameters": {
                    "prompt": {
                        "type": "str", 
                        "required": True,
                        "description": "The prompt text to send to the LLM",
                        "min_length": 1,
                        "max_length": 100000
                    },
                    "model": {
                        "type": "str", 
                        "required": False, 
                        "default": "sonnet",
                        "description": "The model to use for completion",
                        "allowed_values": ["sonnet", "opus", "haiku", "gpt-4", "gpt-3.5-turbo"]
                    },
                    "session_id": {
                        "type": "str", 
                        "required": False,
                        "description": "Session ID for conversation continuity",
                        "pattern": "^[a-zA-Z0-9-_]+$"
                    },
                    "temperature": {
                        "type": "float", 
                        "required": False, 
                        "default": "0.7",
                        "description": "Sampling temperature for the model",
                        "min": 0.0,
                        "max": 2.0
                    }
                }
            },
            {
                "event": "completion:async",
                "summary": "Request an asynchronous completion",
                "parameters": {
                    "prompt": {"type": "str", "required": True},
                    "model": {"type": "str", "required": False},
                    "session_id": {"type": "str", "required": False}
                }
            }
        ],
        "agent": [
            {
                "event": "agent:spawn",
                "summary": "Spawn a new agent",
                "parameters": {
                    "agent_id": {"type": "str", "required": False},
                    "profile": {"type": "str", "required": False},
                    "config": {"type": "dict", "required": False}
                }
            },
            {
                "event": "agent:terminate",
                "summary": "Terminate an agent",
                "parameters": {
                    "agent_id": {"type": "str", "required": True}
                }
            },
            {
                "event": "agent:list",
                "summary": "List active agents",
                "parameters": {}
            },
            {
                "event": "agent:send_message",
                "summary": "Send a message to an agent",
                "parameters": {
                    "agent_id": {
                        "type": "str", 
                        "required": True,
                        "description": "The ID of the agent to send the message to",
                        "pattern": "^[a-zA-Z0-9-_:]+$"
                    },
                    "message": {
                        "type": "dict", 
                        "required": True,
                        "description": "The message payload to send",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string"},
                                "metadata": {"type": "object"}
                            }
                        }
                    }
                }
            }
        ],
        "state": [
            {
                "event": "state:get",
                "summary": "Get a state value",
                "parameters": {
                    "key": {"type": "str", "required": True},
                    "namespace": {"type": "str", "required": False}
                }
            },
            {
                "event": "state:set",
                "summary": "Set a state value",
                "parameters": {
                    "key": {
                        "type": "str", 
                        "required": True,
                        "description": "The state key to set",
                        "pattern": "^[a-zA-Z0-9-_:.]+$",
                        "max_length": 255
                    },
                    "value": {
                        "type": "Any", 
                        "required": True,
                        "description": "The value to store (can be any JSON-serializable type)"
                    },
                    "namespace": {
                        "type": "str", 
                        "required": False,
                        "description": "Optional namespace for the key",
                        "pattern": "^[a-zA-Z0-9-_]+$",
                        "max_length": 100
                    }
                }
            },
            {
                "event": "state:delete",
                "summary": "Delete a state value",
                "parameters": {
                    "key": {"type": "str", "required": True},
                    "namespace": {"type": "str", "required": False}
                }
            }
        ],
        "message": [
            {
                "event": "message:subscribe",
                "summary": "Subscribe to message events",
                "parameters": {
                    "event_types": {"type": "list", "required": False}
                }
            },
            {
                "event": "message:publish",
                "summary": "Publish a message",
                "parameters": {
                    "event_type": {"type": "str", "required": True},
                    "data": {"type": "dict", "required": True},
                    "target": {"type": "str", "required": False}
                }
            }
        ],
        "conversation": [
            {
                "event": "conversation:list",
                "summary": "List available conversations",
                "parameters": {
                    "limit": {
                        "type": "int", 
                        "required": False, 
                        "default": "100",
                        "description": "Maximum number of conversations to return",
                        "min": 1,
                        "max": 1000
                    },
                    "offset": {
                        "type": "int", 
                        "required": False, 
                        "default": "0",
                        "description": "Number of conversations to skip",
                        "min": 0
                    },
                    "sort_by": {"type": "str", "required": False, "default": "last_timestamp"},
                    "start_date": {"type": "str", "required": False},
                    "end_date": {"type": "str", "required": False}
                }
            },
            {
                "event": "conversation:search",
                "summary": "Search conversations by content",
                "parameters": {
                    "query": {
                        "type": "str", 
                        "required": True,
                        "description": "Search query string",
                        "min_length": 1,
                        "max_length": 500
                    },
                    "limit": {"type": "int", "required": False, "default": "50"},
                    "search_in": {"type": "list", "required": False, "default": "['content']"}
                }
            },
            {
                "event": "conversation:get",
                "summary": "Get a specific conversation",
                "parameters": {
                    "session_id": {"type": "str", "required": True},
                    "limit": {"type": "int", "required": False, "default": "1000"},
                    "offset": {"type": "int", "required": False, "default": "0"}
                }
            },
            {
                "event": "conversation:export",
                "summary": "Export a conversation",
                "parameters": {
                    "session_id": {"type": "str", "required": True},
                    "format": {
                        "type": "str", 
                        "required": False, 
                        "default": "markdown",
                        "description": "Export format for the conversation",
                        "allowed_values": ["markdown", "json", "text", "html"]
                    }
                }
            },
            {
                "event": "conversation:stats",
                "summary": "Get conversation statistics",
                "parameters": {}
            }
        ]
    }
    
    # Filter by namespace if requested
    if namespace_filter:
        filtered = {}
        for ns, events in core_events.items():
            if ns == namespace_filter or ns.startswith(namespace_filter + ':'):
                filtered[ns] = events
        events_by_namespace = filtered
    else:
        events_by_namespace = core_events
    
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


def handle_event_help(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get detailed help for a specific event.
    
    Parameters:
        event: The event name to get help for (required)
    
    Returns:
        Detailed event documentation
    """
    event_name = data.get('event')
    if not event_name:
        return {"error": "event parameter required"}
    
    # Parse namespace and event
    if ':' in event_name:
        namespace, event_part = event_name.split(':', 1)
    else:
        return {"error": f"Invalid event format: {event_name}. Use namespace:event"}
    
    # Get all events
    all_events = handle_discover_events({})
    events_in_namespace = all_events['events'].get(namespace, [])
    
    # Find the specific event
    for event_info in events_in_namespace:
        if event_info['event'] == event_name:
            # Add examples if available
            examples = []
            
            # Generate example based on parameters
            if event_info.get('parameters'):
                example_data = {}
                for param, info in event_info['parameters'].items():
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
                "summary": event_info.get('summary', ''),
                "parameters": event_info.get('parameters', {}),
                "examples": examples,
                "plugin": event_info.get('plugin', 'core')
            }
    
    return {"error": f"Event not found: {event_name}"}


def handle_capabilities(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get a summary of daemon capabilities."""
    # Get all events
    all_events = handle_discover_events({'include_internal': True})
    
    # Summarize by namespace
    capabilities = {
        "version": "2.0.0",  # KSI daemon version
        "plugin_based": True,
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
        "conversation": "Conversation history and search"
    }
    return descriptions.get(namespace, f"{namespace} services")


@hookimpl
def ksi_shutdown():
    """Clean up on shutdown."""
    logger.info("Event discovery service stopped")


# Module-level marker for plugin discovery
ksi_plugin = True