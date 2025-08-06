# KSI Hybrid Introspection System

## Overview

The KSI daemon now features a powerful hybrid introspection system that combines multiple approaches to provide rich, accurate parameter discovery for events. This system enables Claude and other consumers to understand not just what parameters an event accepts, but also their types, constraints, examples, and best practices.

## The Four-Layer Approach

### 1. AST-Based Discovery (Automatic)

The foundation layer uses Abstract Syntax Tree analysis to automatically discover parameters from the function body:

```python
# Automatically discovers parameters from code like:
def handle_state_set(data: Dict[str, Any]) -> Dict[str, Any]:
    namespace = data.get("namespace", "global")  # Discovered: optional, default="global"
    key = data.get("key", "")                    # Discovered: required (has falsy default)
    value = data.get("value")                    # Discovered: required (no default)
```

**Benefits:**
- Works with existing code without changes
- Always in sync with actual implementation
- Detects required vs optional parameters
- Captures default values

### 2. TypedDict Support (Type Safety)

The second layer adds type safety through TypedDict definitions:

```python
from ksi_daemon.event_types import StateSetData

@event_handler("state:set", data_type=StateSetData)
def handle_state_set(data: StateSetData) -> Dict[str, Any]:
    key = data["key"]  # IDE knows this is required
    value = data["value"]  # Type-checked
    namespace = data.get("namespace", "global")  # Optional with type
```

**Benefits:**
- Strong typing with IDE support
- Clear parameter structure
- Runtime type checking possible
- Self-documenting code

### 3. Docstring Enhancement (Descriptions)

The third layer extracts human-readable descriptions from docstrings:

```python
@event_handler("state:set")
def handle_state_set(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set a value in shared state.
    
    Args:
        key (str): The key to set in state storage
        value (any): The value to store (JSON-serializable)
        namespace (str): Storage namespace (default: "global")
        metadata (dict): Optional metadata to attach
    """
```

**Benefits:**
- Human-readable descriptions
- Maintains documentation close to code
- Works with existing documentation practices

### 4. Enhanced Metadata (Rich Discovery)

The top layer provides comprehensive metadata for advanced use cases:

```python
from ksi_daemon.enhanced_decorators import enhanced_event_handler, EventParameter

@enhanced_event_handler(
    "completion:async",
    category=EventCategory.COMPUTE,
    parameters=[
        EventParameter(
            name="model",
            type="string",
            description="Model identifier",
            required=True,
            allowed_values=["claude-cli/sonnet", "gpt-4"],
            example="claude-cli/sonnet"
        )
    ],
    async_response=True,
    has_cost=True,
    best_practices=["Always handle async responses"],
    common_errors=["Invalid model format"]
)
```

**Benefits:**
- Rich constraints and examples
- Performance characteristics
- Cost/resource hints
- Best practices documentation

## Discovery Output Example

The hybrid system produces comprehensive discovery data:

```json
{
  "event": "state:set",
  "summary": "Set a value in shared state",
  "category": "data",
  "parameters": {
    "key": {
      "type": "string",
      "description": "The key to set in state storage",
      "required": true,
      "discovered_by": "typeddict",
      "example": "user_preferences"
    },
    "value": {
      "type": "any",
      "description": "The value to store (JSON-serializable)",
      "required": true,
      "discovered_by": "typeddict"
    },
    "namespace": {
      "type": "string",
      "description": "Storage namespace",
      "required": false,
      "default": "global",
      "discovered_by": "ast",
      "allowed_values": ["global", "user", "system", "temp"]
    }
  },
  "performance": {
    "async_response": false,
    "typical_duration_ms": 10,
    "has_side_effects": true,
    "idempotent": true
  },
  "examples": [
    {
      "description": "Store user preferences",
      "data": {
        "key": "preferences",
        "value": {"theme": "dark"},
        "namespace": "user"
      }
    }
  ]
}
```

## Migration Path

### For Existing Handlers (No Changes Required)

AST discovery works immediately:

```python
@event_handler("my:event")
def handle_my_event(data: Dict[str, Any]) -> Dict[str, Any]:
    param1 = data.get("param1")  # Automatically discovered
    param2 = data.get("param2", "default")  # Optional with default
```

### Adding Type Safety (Gradual Enhancement)

Define TypedDict for better tooling:

```python
class MyEventData(TypedDict):
    param1: str
    param2: NotRequired[str]

@event_handler("my:event", data_type=MyEventData)
def handle_my_event(data: MyEventData) -> Dict[str, Any]:
    param1 = data["param1"]  # Type-safe access
```

### Full Enhancement (For Critical Events)

Use enhanced decorator for comprehensive metadata:

```python
@enhanced_event_handler(
    "my:critical_event",
    parameters=[
        EventParameter(
            name="action",
            type="string",
            description="Action to perform",
            allowed_values=["start", "stop", "restart"]
        )
    ],
    has_cost=True,
    best_practices=["Check status before action"]
)
```

## Best Practices

1. **Start Simple**: Let AST discovery work for you
2. **Add Types Gradually**: Use TypedDict for frequently-used events
3. **Document in Code**: Keep descriptions in docstrings
4. **Enhance Critical Events**: Use full metadata for important APIs
5. **Fix As You Go**: Address anti-patterns when encountered

## Benefits for Claude Integration

The hybrid system provides Claude with:

1. **Complete Parameter Info**: Never miss required parameters
2. **Type Understanding**: Know exactly what data types to send
3. **Contextual Examples**: See real usage patterns
4. **Performance Awareness**: Understand which events are expensive
5. **Error Prevention**: Know common mistakes to avoid

## Conclusion

The KSI hybrid introspection system represents a best-in-class approach to API discovery, combining automatic analysis with explicit documentation to provide the richest possible metadata for consumers. This enables Claude and other agents to interact with KSI more effectively and reliably.