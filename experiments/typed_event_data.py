#!/usr/bin/env python3
"""
Experiment: Using TypedDict for structured event parameters
"""

from typing import Dict, Any, TypedDict, Optional, get_type_hints, get_args, get_origin
from typing_extensions import NotRequired
import inspect

# Define event data structures
class StateSetData(TypedDict):
    """Data structure for state:set event."""
    key: str  # Required
    value: Any  # Required
    namespace: NotRequired[str]  # Optional with default
    metadata: NotRequired[Dict[str, Any]]  # Optional

class StateGetData(TypedDict):
    """Data structure for state:get event."""
    key: str
    namespace: NotRequired[str]

# Enhanced event handler using TypedDict
def typed_event_handler(event_name: str, data_type: type):
    """Decorator that uses TypedDict for parameter discovery."""
    def decorator(func):
        # Extract parameter info from TypedDict
        hints = get_type_hints(data_type, include_extras=True)
        required_keys = getattr(data_type, '__required_keys__', set())
        optional_keys = getattr(data_type, '__optional_keys__', set())
        
        parameters = {}
        for key, type_hint in hints.items():
            is_required = key in required_keys
            
            # Extract type info
            type_str = str(type_hint)
            if hasattr(type_hint, '__name__'):
                type_str = type_hint.__name__
            
            parameters[key] = {
                'type': type_str,
                'required': is_required,
                'description': f"Parameter {key} of type {type_str}"
            }
        
        # Store metadata on function
        func._event_name = event_name
        func._event_parameters = parameters
        func._data_type = data_type
        
        return func
    return decorator

# Example usage
@typed_event_handler("state:set", StateSetData)
def handle_state_set(data: StateSetData) -> Dict[str, Any]:
    """Set a value in shared state."""
    namespace = data.get("namespace", "global")
    key = data["key"]  # TypedDict knows this is required
    value = data["value"]
    metadata = data.get("metadata", {})
    
    return {"status": "set", "key": key, "namespace": namespace}

# Extract discovered parameters
def extract_typed_parameters(func):
    """Extract parameters from a typed event handler."""
    if hasattr(func, '_event_parameters'):
        return func._event_parameters
    return {}

# Test it
params = extract_typed_parameters(handle_state_set)
print(f"Event: {handle_state_set._event_name}")
print("Parameters:")
for name, info in params.items():
    req = "required" if info['required'] else "optional"
    print(f"  {name} ({info['type']}) - {req}")