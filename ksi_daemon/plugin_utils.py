#!/usr/bin/env python3
"""
Plugin utilities for KSI plugins.

Provides helper functions, decorators, and auto-discovery patterns
for self-describing plugins.
"""

import ast
import inspect
import re
import asyncio
import json
from functools import wraps
from typing import Dict, Any, Optional, Callable, List, get_type_hints, Type, TypedDict, Union
import functools
from typing_extensions import NotRequired, get_args, get_origin
from dataclasses import dataclass, field
from enum import Enum

# Import structured logging
from ksi_common.logging import get_bound_logger
from ksi_common.exceptions import KSIError

# Best practice: Use a class to encapsulate global state
class PluginRegistry:
    """Thread-safe plugin registry."""
    def __init__(self):
        self._plugins: Dict[str, Dict[str, Any]] = {}
        self._event_handlers: Dict[str, Dict[str, Any]] = {}
    
    def register_plugin(self, name: str, metadata: Dict[str, Any]):
        """Register a plugin."""
        self._plugins[name] = metadata
    
    def register_event(self, event_name: str, metadata: Dict[str, Any]):
        """Register an event handler."""
        self._event_handlers[event_name] = metadata
    
    def get_plugin(self, name: str) -> Optional[Dict[str, Any]]:
        """Get plugin metadata."""
        return self._plugins.get(name)
    
    def get_event(self, event_name: str) -> Optional[Dict[str, Any]]:
        """Get event metadata."""
        return self._event_handlers.get(event_name)
    
    def all_events(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered events."""
        return self._event_handlers.copy()

# Global registry instance
_registry = PluginRegistry()

# Backward compatibility
plugin_registry = _registry._plugins
_event_handlers = _registry._event_handlers


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
        _registry.register_plugin(name, {
            "name": name,
            "version": version,
            "description": description,
            **kwargs
        })
        return func_or_module
    return decorator


# get_logger removed - use get_bound_logger from ksi_common.logging instead


def event_handler(event_name: str, data_type: Optional[Type[TypedDict]] = None):
    """
    Enhanced event handler decorator with TypedDict support.
    
    Automatically extracts metadata from multiple sources:
    - AST analysis of function body
    - TypedDict structure (if provided)
    - Docstring documentation
    
    Usage with TypedDict:
        from ksi_daemon.event_types import StateSetData
        
        @event_handler("state:set", data_type=StateSetData)
        def handle_state_set(data: StateSetData) -> Dict[str, Any]:
            '''Set a value in shared state.'''
            return {"status": "set"}
    
    Usage without TypedDict (backward compatible):
        @event_handler("state:get")
        def handle_state_get(data: Dict[str, Any]) -> Dict[str, Any]:
            '''Get a value from shared state.'''
            return {"value": data.get("key")}
    """
    def decorator(func: Callable) -> Callable:
        # Extract metadata with TypedDict support
        metadata = _extract_metadata(func, event_name, data_type)
        
        # Store for discovery
        _registry.register_event(event_name, metadata)
        
        # Mark the function with event info
        func._ksi_event_name = event_name
        func._ksi_event_metadata = metadata
        func._ksi_data_type = data_type  # Store for runtime validation
        
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

class TypedDictParameterExtractor:
    """Extract parameters from TypedDict annotations."""
    
    @staticmethod
    def extract(data_type: Type[TypedDict]) -> Dict[str, Dict[str, Any]]:
        """Extract parameter info from TypedDict."""
        try:
            # Get type hints including special forms
            hints = get_type_hints(data_type, include_extras=True)
            
            # Get required/optional keys
            required_keys = getattr(data_type, '__required_keys__', set())
            optional_keys = getattr(data_type, '__optional_keys__', set())
            
            parameters = {}
            for key, type_hint in hints.items():
                # Extract type information
                type_str = _get_type_string(type_hint)
                is_required = key in required_keys
                
                # Get docstring if available
                doc = getattr(data_type, '__annotations_doc__', {}).get(key, '')
                
                parameters[key] = {
                    'type': type_str,
                    'required': is_required,
                    'discovered_by': 'typeddict'
                }
                
                if doc:
                    parameters[key]['description'] = doc
            
            return parameters
            
        except Exception as e:
            logger = get_bound_logger("plugin_utils")
            logger.debug(f"TypedDict extraction failed: {e}")
            return {}


class ASTParameterExtractor:
    """Extract parameters using AST analysis of function body."""
    
    @staticmethod
    def extract(func: Callable) -> Dict[str, Dict[str, Any]]:
        """Extract parameter usage from function source."""
        try:
            source = inspect.getsource(func)
            tree = ast.parse(source)
            
            parameters = {}
            
            class DataAccessVisitor(ast.NodeVisitor):
                def visit_Call(self, node):
                    # Look for data.get() calls
                    if (isinstance(node.func, ast.Attribute) and 
                        node.func.attr == 'get' and
                        isinstance(node.func.value, ast.Name) and
                        node.func.value.id == 'data'):
                        
                        if node.args and isinstance(node.args[0], ast.Constant):
                            key = node.args[0].value
                            default = None
                            required = True
                            
                            if len(node.args) > 1:
                                required = False
                                if isinstance(node.args[1], ast.Constant):
                                    default = node.args[1].value
                            
                            parameters[key] = {
                                'required': required,
                                'default': default,
                                'discovered_by': 'ast'
                            }
                    
                    self.generic_visit(node)
                
                def visit_Subscript(self, node):
                    # Look for direct dict access: data["key"]
                    if (isinstance(node.value, ast.Name) and
                        node.value.id == 'data' and
                        isinstance(node.slice, ast.Constant)):
                        
                        key = node.slice.value
                        if key not in parameters:
                            parameters[key] = {
                                'required': True,
                                'discovered_by': 'ast'
                            }
                    
                    self.generic_visit(node)
            
            visitor = DataAccessVisitor()
            visitor.visit(tree)
            
            return parameters
            
        except Exception as e:
            # Best practice: Log errors but don't crash
            logger = get_bound_logger("plugin_utils")
            logger.debug(f"AST extraction failed for {func.__name__}: {e}")
            return {}


def _get_type_string(type_hint: Any) -> str:
    """Convert type hint to readable string."""
    if hasattr(type_hint, '__name__'):
        return type_hint.__name__
    
    # Handle Union types
    origin = get_origin(type_hint)
    if origin is Union:
        args = get_args(type_hint)
        # Check if it's Optional (Union with None)
        if type(None) in args:
            non_none_args = [arg for arg in args if arg is not type(None)]
            if len(non_none_args) == 1:
                return f"Optional[{_get_type_string(non_none_args[0])}]"
        return f"Union[{', '.join(_get_type_string(arg) for arg in args)}]"
    
    # Handle generic types
    if origin:
        args = get_args(type_hint)
        if args:
            return f"{origin.__name__}[{', '.join(_get_type_string(arg) for arg in args)}]"
        return origin.__name__
    
    # Default to string representation
    return str(type_hint)


def _extract_metadata(func: Callable, event_name: str, data_type: Optional[Type[TypedDict]] = None) -> Dict[str, Any]:
    """Extract event metadata from a function using multiple methods."""
    # Get docstring
    docstring = inspect.getdoc(func) or ""
    lines = docstring.split('\n')
    
    # Extract summary (first line)
    summary = lines[0].strip() if lines else "No description available"
    
    # Layer 1: AST-based discovery (automatic)
    ast_params = ASTParameterExtractor.extract(func)
    
    # Layer 2: TypedDict extraction (if provided)
    if data_type:
        typed_params = TypedDictParameterExtractor.extract(data_type)
        # Merge TypedDict params (higher priority than AST)
        for key, info in typed_params.items():
            if key in ast_params:
                ast_params[key].update(info)
            else:
                ast_params[key] = info
    
    # Layer 3: Docstring parsing (for descriptions)
    docstring_params = _parse_docstring_params(docstring)
    
    # Layer 4: Merge parameters (docstring takes precedence for descriptions)
    combined_params = ast_params.copy()
    for key, info in docstring_params.items():
        if key in combined_params:
            # Merge: keep discovery info but add docstring details
            combined_params[key].update(info)
        else:
            # Parameter only in docstring
            combined_params[key] = info
    
    # Extract examples from docstring
    examples = _parse_docstring_examples(docstring)
    
    # Build metadata
    metadata = {
        "event": event_name,
        "summary": summary,
        "parameters": combined_params,
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


