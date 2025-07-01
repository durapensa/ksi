#!/usr/bin/env python3
"""
Plugin utilities for KSI plugins.

Provides helper functions, decorators, and auto-discovery patterns
for self-describing plugins.
"""

import inspect
import re
import asyncio
from functools import wraps
from typing import Dict, Any, Optional, Callable, List, get_type_hints
import functools

# Import structured logging
from ksi_common.logging import get_bound_logger

# Simple plugin registry for metadata
plugin_registry: Dict[str, Dict[str, Any]] = {}

# Store decorated event handlers for discovery
_event_handlers: Dict[str, Dict[str, Any]] = {}


def plugin_metadata(name: str, version: str = "1.0.0", 
                   description: str = "", **kwargs):
    """
    Decorator to register plugin metadata.
    
    Usage:
        @plugin_metadata("my_plugin", version="1.0.0", description="Does things")
        def my_plugin_module():
            pass
    """
    def decorator(func_or_module):
        plugin_registry[name] = {
            "name": name,
            "version": version,
            "description": description,
            **kwargs
        }
        return func_or_module
    return decorator


# get_logger removed - use get_bound_logger from ksi_common.logging instead


def event_handler(event_name: str):
    """
    Decorator for marking event handler functions.
    
    Automatically extracts metadata from the function signature and docstring
    to build event descriptions for discovery.
    
    Usage:
        @event_handler("permission:list_profiles")
        def handle_list_profiles(data: Dict[str, Any]) -> Dict[str, Any]:
            '''List available permission profiles.
            
            Returns:
                profiles: Dictionary containing all permission profiles
            '''
            return {"profiles": {...}}
    
    The decorator extracts:
    - Event name from decorator argument
    - Summary from first line of docstring
    - Parameters from function signature and type hints
    - Return info from docstring Returns section
    """
    def decorator(func: Callable) -> Callable:
        # Extract metadata
        metadata = _extract_metadata(func, event_name)
        
        # Store for discovery
        _event_handlers[event_name] = metadata
        
        # Mark the function with event info
        func._ksi_event_name = event_name
        func._ksi_event_metadata = metadata
        
        # Keep backward compatibility with event patterns
        func._event_patterns = [event_name]
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def service_provider(service_name: str):
    """
    Decorator to mark a function as providing a service.
    
    Usage:
        @service_provider("completion")
        async def provide_completion_service():
            return CompletionService()
    """
    def decorator(func):
        func._provides_service = service_name
        return func
    return decorator


def matches_pattern(event_name: str, pattern: str) -> bool:
    """Check if an event name matches a pattern."""
    if "*" not in pattern:
        return event_name == pattern
    
    # Simple wildcard matching
    import fnmatch
    return fnmatch.fnmatch(event_name, pattern)


def extract_namespace(event_name: str) -> Optional[str]:
    """Extract namespace from event name."""
    if ":" in event_name:
        return event_name.split(":", 1)[0]
    return None


class SimpleEventEmitter:
    """Simple event emitter for plugins that need to emit events."""
    
    def __init__(self, emit_func: Callable):
        self.emit_func = emit_func
    
    async def emit(self, event_name: str, data: Dict[str, Any], 
                   correlation_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Emit an event."""
        return await self.emit_func(event_name, data, correlation_id)


# Helper functions for common plugin patterns

async def with_timeout(coro, timeout: float, error_msg: str = "Operation timed out"):
    """Run a coroutine with timeout."""
    from ksi_common import KSITimeoutError
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        raise KSITimeoutError(error_msg)


def validate_data(data: Dict[str, Any], required_fields: List[str]) -> bool:
    """Validate that required fields are present in data."""
    return all(field in data for field in required_fields)


def safe_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely get a value from a dict with a default."""
    return data.get(key, default)


# Context helpers for plugins

class PluginContext:
    """Simple context object passed to plugins."""
    
    def __init__(self, config: Dict[str, Any], emit_func: Optional[Callable] = None):
        self.config = config
        self.emitter = SimpleEventEmitter(emit_func) if emit_func else None
    
    async def emit(self, event_name: str, data: Dict[str, Any], 
                   correlation_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Emit an event if emitter is available."""
        if self.emitter:
            return await self.emitter.emit(event_name, data, correlation_id)
        return None


# Auto-discovery helpers

def _extract_metadata(func: Callable, event_name: str) -> Dict[str, Any]:
    """Extract event metadata from a function."""
    # Get docstring
    docstring = inspect.getdoc(func) or ""
    lines = docstring.split('\n')
    
    # Extract summary (first line)
    summary = lines[0].strip() if lines else "No description available"
    
    # Get type hints
    type_hints = get_type_hints(func)
    
    # Extract parameters from docstring
    params = _parse_docstring_params(docstring)
    
    # Extract examples from docstring
    examples = _parse_docstring_examples(docstring)
    
    # Build metadata
    metadata = {
        "event": event_name,
        "summary": summary,
        "parameters": params,
    }
    
    if examples:
        metadata["examples"] = examples
    
    return metadata


def _parse_docstring_params(docstring: str) -> Dict[str, Any]:
    """Parse parameter documentation from docstring."""
    params = {}
    lines = docstring.split('\n')
    
    # Regex patterns for parameter documentation
    param_section_pattern = re.compile(r'^\s*(Args|Arguments|Parameters|Params):\s*$', re.IGNORECASE)
    param_pattern = re.compile(r'^\s*(\w+)\s*(?:\(([^)]+)\))?\s*:\s*(.+)$')
    section_end_pattern = re.compile(r'^\s*(Returns?|Raises?|Example|Examples|Note|Notes):\s*$', re.IGNORECASE)
    
    in_params_section = False
    current_param = None
    
    for line in lines:
        # Check for parameter section start
        if param_section_pattern.match(line):
            in_params_section = True
            continue
        
        # Check for section end
        if section_end_pattern.match(line):
            in_params_section = False
            current_param = None
            continue
        
        if in_params_section:
            # Try to match parameter line
            param_match = param_pattern.match(line)
            if param_match:
                param_name = param_match.group(1)
                param_type = param_match.group(2)
                param_desc = param_match.group(3).strip()
                
                param_info = {
                    "description": param_desc,
                    "required": "optional" not in param_desc.lower()
                }
                
                if param_type:
                    param_info["type"] = param_type
                
                # Check for default value in description
                default_match = re.search(r'default[s]?\s*[:=]\s*([^\s,)]+)', param_desc, re.IGNORECASE)
                if default_match:
                    param_info["default"] = default_match.group(1).strip("\"'")
                    param_info["required"] = False
                
                # Check for allowed values
                allowed_match = re.search(r'(?:one of|allowed|valid values?)[:=]\s*\[([^\]]+)\]', param_desc, re.IGNORECASE)
                if allowed_match:
                    values = [v.strip().strip("\"'") for v in allowed_match.group(1).split(',')]
                    param_info["allowed_values"] = values
                
                params[param_name] = param_info
                current_param = param_name
            
            # Handle continuation lines for current parameter
            elif current_param and line.strip():
                # This is a continuation of the previous parameter's description
                params[current_param]["description"] += " " + line.strip()
    
    return params


def _parse_docstring_examples(docstring: str) -> List[Dict[str, Any]]:
    """Parse examples from docstring."""
    examples = []
    lines = docstring.split('\n')
    
    in_example = False
    example_lines = []
    example_desc = ""
    
    for i, line in enumerate(lines):
        if re.match(r'^\s*Examples?:\s*$', line, re.IGNORECASE):
            in_example = True
            continue
        elif in_example and re.match(r'^\s*(Returns?|Raises?|Note|Notes):\s*$', line, re.IGNORECASE):
            in_example = False
            
        if in_example:
            # Check if this is a new example description
            if line.strip() and not line.startswith(' ' * 8):  # Less indented
                # Save previous example if exists
                if example_lines:
                    example_text = '\n'.join(example_lines).strip()
                    try:
                        import json
                        example_data = json.loads(example_text)
                        examples.append({
                            "description": example_desc or "Example",
                            "data": example_data
                        })
                    except (json.JSONDecodeError, ValueError):
                        # Not JSON, skip
                        pass
                
                example_lines = []
                example_desc = line.strip()
            elif line.strip():
                # This is example content
                example_lines.append(line)
    
    # Don't forget the last example
    if example_lines:
        example_text = '\n'.join(example_lines).strip()
        try:
            import json
            example_data = json.loads(example_text)
            examples.append({
                "description": example_desc or "Example",
                "data": example_data
            })
        except (json.JSONDecodeError, ValueError):
            pass
    
    return examples


def collect_event_metadata(module) -> Dict[str, List[Dict[str, Any]]]:
    """
    Collect all event metadata from a module.
    
    Scans the module for functions decorated with @event_handler and
    returns their metadata organized by namespace.
    
    Args:
        module: The module to scan for event handlers
        
    Returns:
        Dictionary mapping namespace to list of event descriptions
    """
    events_by_namespace = {}
    
    # Scan module for decorated functions
    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj) and hasattr(obj, '_ksi_event_metadata'):
            metadata = obj._ksi_event_metadata
            event_name = metadata['event']
            
            # Extract namespace
            if ':' in event_name:
                namespace, _ = event_name.split(':', 1)
            else:
                namespace = 'default'
            
            # Add to namespace
            if namespace not in events_by_namespace:
                events_by_namespace[namespace] = []
            
            events_by_namespace[namespace].append(metadata)
    
    # Only collect from the specific module - no global handlers
    # This prevents duplicates when multiple plugins call this function
    
    return events_by_namespace


def create_ksi_describe_events_hook(module):
    """
    Create a ksi_describe_events hook implementation for a module.
    
    This function returns a hook implementation that automatically
    discovers all @event_handler decorated functions in the module.
    
    Usage in a plugin:
        from ksi_daemon.plugin_utils import event_handler, create_ksi_describe_events_hook
        
        # Define handlers with decorator
        @event_handler("myplugin:do_something")
        def handle_do_something(data):
            ...
        
        # Add discovery hook
        ksi_describe_events = create_ksi_describe_events_hook(__name__)
    """
    def ksi_describe_events() -> Dict[str, List[Dict[str, Any]]]:
        """Auto-generated event discovery hook."""
        import sys
        mod = sys.modules.get(module)
        if mod:
            return collect_event_metadata(mod)
        return {}
    
    return ksi_describe_events


# Type conversion helpers
def python_type_to_json_type(py_type: Any) -> str:
    """Convert Python type annotation to JSON schema type."""
    type_map = {
        str: "string",
        int: "integer", 
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        type(None): "null",
    }
    
    # Handle Optional types
    if hasattr(py_type, '__origin__'):
        if py_type.__origin__ is type(None):
            return "null"
        origin = py_type.__origin__
        if origin in type_map:
            return type_map[origin]
    
    # Direct type lookup
    if py_type in type_map:
        return type_map[py_type]
    
    # Default to string for unknown types
    return "string"


# Validation helpers
def validate_event_name(event_name: str) -> bool:
    """Validate event name format (namespace:event)."""
    if not event_name or ':' not in event_name:
        return False
    
    namespace, event = event_name.split(':', 1)
    if not namespace or not event:
        return False
    
    # Check for valid characters
    valid_pattern = re.compile(r'^[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+$')
    return bool(valid_pattern.match(event_name))


