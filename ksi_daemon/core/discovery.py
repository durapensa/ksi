#!/usr/bin/env python3
"""
Event Discovery Plugin - Simplified Pure Event-Based Version

Provides essential discovery capabilities:
- List all events with parameters
- Show which events trigger other events
- Automatic extraction from implementation code
"""

import ast
import inspect
from typing import Dict, List, Any, Optional, Callable

from ksi_daemon.event_system import event_handler
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("discovery", version="2.0.0")


@event_handler("system:startup")
async def handle_startup(config: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize discovery service."""
    logger.info("Discovery service started")
    return {"status": "discovery_ready"}


@event_handler("system:discover")
async def handle_discover(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Universal discovery endpoint - everything you need to understand KSI.
    
    Parameters:
        detail: Include parameters and triggers (default: True)
        namespace: Filter by namespace (optional)
        event: Get details for specific event (optional)
    
    Returns:
        Dictionary with events, their parameters, and what they trigger
    """
    include_detail = data.get('detail', True)
    namespace_filter = data.get('namespace')
    event_filter = data.get('event')
    
    from ksi_daemon.event_system import get_router
    router = get_router()
    
    events = {}
    
    for event_name, handlers in router._handlers.items():
        # Apply filters
        if event_filter and event_name != event_filter:
            continue
        if namespace_filter:
            ns = event_name.split(':')[0] if ':' in event_name else 'default'
            if ns != namespace_filter:
                continue
        
        handler = handlers[0]  # Use first handler
        
        # Basic info
        event_info = {
            'module': handler.module,
            'handler': handler.name,
            'async': handler.is_async,
            'summary': extract_summary(handler.func)
        }
        
        if include_detail:
            # Extract implementation details via AST
            analysis = analyze_handler(handler.func, event_name)
            event_info.update({
                'parameters': analysis['parameters'],
                'triggers': analysis['triggers']
            })
        
        events[event_name] = event_info
    
    # Build namespace list
    namespaces = list(set(e.split(':')[0] if ':' in e else 'default' 
                         for e in events.keys()))
    
    return {
        'events': events,
        'total': len(events),
        'namespaces': sorted(namespaces)
    }


@event_handler("system:help")
async def handle_help(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get detailed help for a specific event.
    
    Parameters:
        event: The event name to get help for (required)
    """
    event_name = data.get('event')
    if not event_name:
        return {"error": "event parameter required"}
    
    # Get event details
    result = await handle_discover({'event': event_name, 'detail': True})
    
    if event_name not in result['events']:
        return {"error": f"Event not found: {event_name}"}
    
    event_info = result['events'][event_name]
    
    # Format as help
    return {
        'event': event_name,
        'summary': event_info['summary'],
        'module': event_info['module'],
        'async': event_info['async'],
        'parameters': event_info['parameters'],
        'triggers': event_info.get('triggers', []),
        'usage': generate_usage_example(event_name, event_info['parameters'])
    }


def extract_summary(func: Callable) -> str:
    """Extract summary from function docstring."""
    doc = inspect.getdoc(func)
    if doc:
        # First line is summary
        return doc.split('\n')[0].strip()
    return f"Handle {func.__name__}"


def analyze_handler(func: Callable, event_name: str) -> Dict[str, Any]:
    """
    Analyze handler implementation to extract parameters and triggers.
    
    Returns dict with:
    - parameters: Dict of param info extracted from data access
    - triggers: List of events this handler emits
    """
    try:
        source = inspect.getsource(func)
        tree = ast.parse(source)
        
        analyzer = SimpleAnalyzer()
        analyzer.visit(tree)
        
        # Merge parameters from different sources
        parameters = {}
        
        # From data.get() calls
        for name, info in analyzer.data_gets.items():
            parameters[name] = {
                'type': 'Any',
                'required': info['required'],
                'default': info['default'],
                'description': f"{name} parameter"
            }
        
        # From data["key"] access
        for name in analyzer.data_subscripts:
            if name not in parameters:
                parameters[name] = {
                    'type': 'Any',
                    'required': True,
                    'description': f"{name} parameter"
                }
        
        # Try to enhance with docstring info
        doc_params = parse_docstring_params(func)
        for name, doc_info in doc_params.items():
            if name in parameters:
                parameters[name].update(doc_info)
        
        return {
            'parameters': parameters,
            'triggers': analyzer.triggers
        }
        
    except Exception as e:
        logger.debug(f"Analysis failed for {func.__name__}: {e}")
        return {'parameters': {}, 'triggers': []}


class SimpleAnalyzer(ast.NodeVisitor):
    """AST visitor to extract parameters and event triggers."""
    
    def __init__(self):
        self.data_gets = {}      # data.get() calls
        self.data_subscripts = set()  # data["key"] access
        self.triggers = []       # Events emitted
    
    def visit_Call(self, node):
        # Check for data.get() calls
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
                
                self.data_gets[key] = {
                    'required': required,
                    'default': default
                }
        
        # Check for event emissions
        elif self._is_emit_call(node):
            event_name = self._extract_event_name(node)
            if event_name:
                self.triggers.append(event_name)
        
        self.generic_visit(node)
    
    def visit_Subscript(self, node):
        # Check for data["key"] access
        if (isinstance(node.value, ast.Name) and
            node.value.id == 'data' and
            isinstance(node.slice, ast.Constant)):
            
            key = node.slice.value
            self.data_subscripts.add(key)
        
        self.generic_visit(node)
    
    def _is_emit_call(self, node):
        """Check if this is an event emission."""
        if isinstance(node.func, ast.Attribute):
            return node.func.attr in ['emit', 'emit_event', 'emit_first']
        elif isinstance(node.func, ast.Name):
            return node.func.id in ['emit_event', 'emit']
        return False
    
    def _extract_event_name(self, node):
        """Extract event name from emit call."""
        if node.args and isinstance(node.args[0], ast.Constant):
            return node.args[0].value
        return None


def parse_docstring_params(func: Callable) -> Dict[str, Dict[str, Any]]:
    """Extract parameter descriptions from docstring."""
    doc = inspect.getdoc(func)
    if not doc:
        return {}
    
    params = {}
    lines = doc.split('\n')
    in_params = False
    
    for line in lines:
        line = line.strip()
        
        # Look for parameter section
        if line.lower() in ['parameters:', 'args:', 'arguments:']:
            in_params = True
            continue
        elif line.lower().startswith(('returns:', 'example:')):
            in_params = False
            continue
        
        if in_params and line:
            # Parse "name (type): description" format
            if ':' in line:
                parts = line.split(':', 1)
                if '(' in parts[0]:
                    # Has type info
                    name_type = parts[0].split('(')
                    name = name_type[0].strip().lstrip('-').strip()
                    type_str = name_type[1].rstrip(')').strip()
                    desc = parts[1].strip()
                    
                    params[name] = {
                        'type': type_str,
                        'description': desc,
                        'required': 'optional' not in desc.lower()
                    }
                else:
                    # No type info
                    name = parts[0].strip().lstrip('-').strip()
                    desc = parts[1].strip()
                    
                    params[name] = {
                        'description': desc,
                        'required': 'optional' not in desc.lower()
                    }
    
    return params


def generate_usage_example(event_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a usage example for an event."""
    example_data = {}
    
    for param_name, param_info in parameters.items():
        if param_info.get('required', False):
            # Add required parameters with example values
            param_type = param_info.get('type', 'Any')
            if 'str' in param_type.lower():
                example_data[param_name] = f"example_{param_name}"
            elif 'int' in param_type.lower():
                example_data[param_name] = 123
            elif 'bool' in param_type.lower():
                example_data[param_name] = True
            elif 'dict' in param_type.lower():
                example_data[param_name] = {}
            elif 'list' in param_type.lower():
                example_data[param_name] = []
            else:
                example_data[param_name] = f"<{param_type}>"
    
    return {
        "event": event_name,
        "data": example_data
    }


@event_handler("system:shutdown")
async def handle_shutdown(data: Dict[str, Any]) -> None:
    """Clean shutdown."""
    logger.info("Discovery service stopped")