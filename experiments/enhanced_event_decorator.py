#!/usr/bin/env python3
"""
Experiment: Enhanced event decorator with explicit parameter declaration
"""

from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, field
from enum import Enum

class ParamType(Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    ANY = "any"

@dataclass
class EventParameter:
    """Describes a single event parameter."""
    name: str
    type: ParamType
    description: str
    required: bool = True
    default: Any = None
    allowed_values: Optional[List[Any]] = None
    example: Any = None
    
    def to_dict(self):
        """Convert to discovery format."""
        result = {
            "type": self.type.value,
            "description": self.description,
            "required": self.required
        }
        if self.default is not None:
            result["default"] = self.default
        if self.allowed_values:
            result["allowed_values"] = self.allowed_values
        if self.example is not None:
            result["example"] = self.example
        return result

def event_handler_v2(
    event_name: str,
    parameters: List[EventParameter],
    summary: Optional[str] = None,
    examples: Optional[List[Dict[str, Any]]] = None
):
    """
    Enhanced event handler decorator with explicit parameter declaration.
    
    This approach provides complete parameter metadata without relying on
    docstring parsing or runtime analysis.
    """
    def decorator(func):
        # Build parameter dictionary
        param_dict = {p.name: p.to_dict() for p in parameters}
        
        # Extract summary from docstring if not provided
        if summary is None:
            import inspect
            doc = inspect.getdoc(func)
            if doc:
                summary_text = doc.split('\n')[0].strip()
            else:
                summary_text = f"Handler for {event_name}"
        else:
            summary_text = summary
        
        # Store all metadata on function
        func._ksi_event_name = event_name
        func._ksi_event_metadata = {
            "event": event_name,
            "summary": summary_text,
            "parameters": param_dict,
            "examples": examples or []
        }
        
        # Also support parameter validation
        func._ksi_parameters = {p.name: p for p in parameters}
        
        return func
    return decorator

# Example usage with rich metadata
@event_handler_v2(
    "state:set",
    parameters=[
        EventParameter(
            name="key",
            type=ParamType.STRING,
            description="The key to set in state storage",
            required=True,
            example="user_preferences"
        ),
        EventParameter(
            name="value",
            type=ParamType.ANY,
            description="The value to store (can be any JSON-serializable type)",
            required=True,
            example={"theme": "dark", "language": "en"}
        ),
        EventParameter(
            name="namespace",
            type=ParamType.STRING,
            description="The namespace to store the key in",
            required=False,
            default="global",
            allowed_values=["global", "user", "system", "temp"]
        ),
        EventParameter(
            name="metadata",
            type=ParamType.OBJECT,
            description="Optional metadata to attach to the state entry",
            required=False,
            default={},
            example={"created_by": "user_123", "ttl": 3600}
        )
    ],
    examples=[
        {
            "description": "Store user preferences",
            "data": {
                "key": "user_preferences",
                "value": {"theme": "dark", "notifications": True},
                "namespace": "user"
            }
        },
        {
            "description": "Store temporary data with metadata",
            "data": {
                "key": "processing_status",
                "value": "in_progress",
                "namespace": "temp",
                "metadata": {"ttl": 300}
            }
        }
    ]
)
def handle_state_set_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    """Set a value in shared state with validation."""
    # Could add automatic validation based on parameter definitions
    params = getattr(handle_state_set_v2, '_ksi_parameters', {})
    
    # Validate required parameters
    for name, param in params.items():
        if param.required and name not in data:
            return {"error": f"{name} is required"}
    
    # Extract with defaults
    namespace = data.get("namespace", "global")
    key = data.get("key")
    value = data.get("value")
    metadata = data.get("metadata", {})
    
    # Validate allowed values
    if "namespace" in params:
        ns_param = params["namespace"]
        if ns_param.allowed_values and namespace not in ns_param.allowed_values:
            return {"error": f"namespace must be one of: {ns_param.allowed_values}"}
    
    return {
        "status": "set",
        "key": key,
        "namespace": namespace
    }

# Test parameter extraction
if __name__ == "__main__":
    metadata = handle_state_set_v2._ksi_event_metadata
    print(f"Event: {metadata['event']}")
    print(f"Summary: {metadata['summary']}")
    print("\nParameters:")
    for name, info in metadata['parameters'].items():
        print(f"  {name}:")
        for k, v in info.items():
            print(f"    {k}: {v}")