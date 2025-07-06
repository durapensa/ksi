#!/usr/bin/env python3
"""
Prototype: Hybrid introspection system for KSI event parameters

Combines AST analysis, TypedDict, and explicit metadata for the best
of all worlds.
"""

import ast
import inspect
from typing import Dict, Any, Optional, TypedDict, get_type_hints, Type, Callable
from typing_extensions import NotRequired
import functools

# --- AST Analysis Component ---

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
                    # Look for data.get() or data[] access
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
                    
                    # Also look for direct dict access: data["key"]
                    elif (isinstance(node, ast.Subscript) and
                          isinstance(node.value, ast.Name) and
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
            for node in ast.walk(tree):
                if isinstance(node, ast.Subscript):
                    visitor.visit_Subscript(node)
                else:
                    visitor.visit(node)
            
            return parameters
            
        except Exception as e:
            return {}

# --- TypedDict Component ---

class TypedDictParameterExtractor:
    """Extract parameters from TypedDict annotations."""
    
    @staticmethod
    def extract(data_type: Type[TypedDict]) -> Dict[str, Dict[str, Any]]:
        """Extract parameter info from TypedDict."""
        try:
            hints = get_type_hints(data_type, include_extras=True)
            required_keys = getattr(data_type, '__required_keys__', set())
            optional_keys = getattr(data_type, '__optional_keys__', set())
            
            parameters = {}
            for key, type_hint in hints.items():
                type_str = getattr(type_hint, '__name__', str(type_hint))
                
                parameters[key] = {
                    'type': type_str,
                    'required': key in required_keys,
                    'discovered_by': 'typeddict'
                }
            
            return parameters
            
        except Exception:
            return {}

# --- Hybrid Event Handler ---

def hybrid_event_handler(
    event_name: str,
    data_type: Optional[Type[TypedDict]] = None,
    metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    auto_discover: bool = True
):
    """
    Hybrid event handler that combines multiple introspection methods.
    
    Args:
        event_name: The event name (e.g., "state:set")
        data_type: Optional TypedDict for type safety
        metadata: Optional explicit parameter metadata
        auto_discover: Whether to use AST analysis
    """
    def decorator(func: Callable) -> Callable:
        # Start with empty parameter dict
        combined_params = {}
        
        # Layer 1: AST discovery (if enabled)
        if auto_discover:
            ast_params = ASTParameterExtractor.extract(func)
            combined_params.update(ast_params)
        
        # Layer 2: TypedDict (if provided)
        if data_type:
            typed_params = TypedDictParameterExtractor.extract(data_type)
            for key, info in typed_params.items():
                if key in combined_params:
                    combined_params[key].update(info)
                else:
                    combined_params[key] = info
        
        # Layer 3: Explicit metadata (highest priority)
        if metadata:
            for key, info in metadata.items():
                if key in combined_params:
                    combined_params[key].update(info)
                else:
                    combined_params[key] = info
        
        # Layer 4: Docstring parsing (for descriptions)
        docstring = inspect.getdoc(func) or ""
        docstring_params = _parse_simple_docstring(docstring)
        for key, desc in docstring_params.items():
            if key in combined_params:
                combined_params[key]['description'] = desc
        
        # Build final metadata
        func._ksi_event_name = event_name
        func._ksi_event_metadata = {
            'event': event_name,
            'summary': docstring.split('\n')[0] if docstring else f"Handler for {event_name}",
            'parameters': combined_params
        }
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator

def _parse_simple_docstring(docstring: str) -> Dict[str, str]:
    """Simple docstring parser for parameter descriptions."""
    params = {}
    lines = docstring.split('\n')
    in_args = False
    
    for line in lines:
        line = line.strip()
        if line.lower() in ['args:', 'arguments:', 'parameters:']:
            in_args = True
        elif line and ':' in line and in_args:
            # Simple parsing: "key: description"
            parts = line.split(':', 1)
            if len(parts) == 2:
                key = parts[0].strip().lstrip('-').strip()
                desc = parts[1].strip()
                params[key] = desc
        elif line.startswith(('Returns:', 'Example:')):
            break
    
    return params

# --- Example Usage ---

# Define TypedDict for type safety
class StateSetData(TypedDict):
    key: str
    value: Any
    namespace: NotRequired[str]
    metadata: NotRequired[Dict[str, Any]]

# Use the hybrid decorator
@hybrid_event_handler(
    "state:set",
    data_type=StateSetData,
    metadata={
        "key": {
            "description": "The key to set in state storage",
            "example": "user_preferences"
        },
        "value": {
            "description": "The value to store (JSON-serializable)",
            "example": {"theme": "dark"}
        },
        "namespace": {
            "description": "Storage namespace",
            "allowed_values": ["global", "user", "system", "temp"]
        }
    }
)
def handle_state_set(data: StateSetData) -> Dict[str, Any]:
    """
    Set a value in shared state.
    
    Args:
        key: The state key
        value: The value to store
        namespace: The namespace (default: global)
        metadata: Optional metadata
    """
    namespace = data.get("namespace", "global")
    key = data["key"]
    value = data["value"]
    metadata = data.get("metadata", {})
    
    return {"status": "set", "key": key, "namespace": namespace}

# Test the introspection
if __name__ == "__main__":
    metadata = handle_state_set._ksi_event_metadata
    print(f"Event: {metadata['event']}")
    print(f"Summary: {metadata['summary']}")
    print("\nDiscovered Parameters:")
    
    for name, info in metadata['parameters'].items():
        print(f"\n  {name}:")
        for k, v in info.items():
            print(f"    {k}: {v}")
    
    print("\n--- Discovery Sources ---")
    for name, info in metadata['parameters'].items():
        source = info.get('discovered_by', 'metadata')
        print(f"{name}: discovered by {source}")