# Deep Introspection Approaches for Event Parameter Discovery

## Overview

The KSI event system currently relies on docstring parsing to extract parameter information. This document explores deeper Python introspection techniques that could provide more reliable and richer parameter discovery.

## Current Approach: Docstring Parsing

**Limitations:**
- Requires well-formatted docstrings
- No type validation
- Manual maintenance required
- Can get out of sync with code

## Proposed Approaches

### 1. AST (Abstract Syntax Tree) Analysis

**How it works:** Parse the function body to find `data.get()` calls

**Pros:**
- ✅ Automatic - no manual declarations needed
- ✅ Always in sync with actual code
- ✅ Can detect required vs optional (based on defaults)
- ✅ Works with existing code without changes

**Cons:**
- ❌ Limited type information
- ❌ No parameter descriptions
- ❌ Can't detect complex parameter extraction patterns
- ❌ Doesn't capture business logic constraints

**Best for:** Retrofitting existing handlers, automated discovery

### 2. TypedDict-Based Parameter Declaration

**How it works:** Use TypedDict to define the structure of event data

**Pros:**
- ✅ Strong typing with IDE support
- ✅ Clear parameter structure
- ✅ Runtime type checking possible
- ✅ Works well with modern Python tooling

**Cons:**
- ❌ Requires Python 3.8+ (or typing_extensions)
- ❌ No descriptions or examples in type definition
- ❌ Requires refactoring existing handlers
- ❌ Limited metadata (no allowed values, etc.)

**Best for:** New handlers, type-safe codebases

### 3. Enhanced Decorator with Explicit Declaration

**How it works:** Extend @event_handler to accept parameter definitions

**Pros:**
- ✅ Richest metadata (descriptions, examples, allowed values)
- ✅ Built-in validation support
- ✅ Self-documenting code
- ✅ No docstring maintenance needed
- ✅ Can generate OpenAPI/JSON Schema

**Cons:**
- ❌ More verbose decorator usage
- ❌ Requires updating all handlers
- ❌ Parameter definitions separate from usage

**Best for:** Production systems, API documentation

## Hybrid Approach Recommendation

Combine the best of all approaches:

```python
from typing import TypedDict, Optional
from ksi_daemon.plugin_utils import event_handler_v3

class StateSetData(TypedDict):
    """Type definition for state:set parameters."""
    key: str
    value: Any
    namespace: NotRequired[str]
    metadata: NotRequired[Dict[str, Any]]

@event_handler_v3(
    "state:set",
    data_type=StateSetData,  # Type safety
    auto_discover=True,      # AST analysis fallback
    metadata={               # Rich descriptions
        "key": {"description": "The state key to set"},
        "value": {"description": "The value to store"},
        "namespace": {"description": "Storage namespace", "default": "global"},
        "metadata": {"description": "Optional metadata"}
    }
)
def handle_state_set(data: StateSetData) -> Dict[str, Any]:
    """Set a value in shared state."""
    # Implementation remains the same
    key = data["key"]
    value = data["value"]
    namespace = data.get("namespace", "global")
    metadata = data.get("metadata", {})
    ...
```

## Implementation Plan

### Phase 1: AST Analysis for Existing Handlers
- Implement AST-based discovery as fallback
- No code changes required
- Provides basic parameter discovery immediately

### Phase 2: TypedDict Migration
- Define TypedDict for each event type
- Update handlers to use typed parameters
- Enable type checking in CI/CD

### Phase 3: Enhanced Metadata
- Add rich metadata to critical events
- Include examples, constraints, allowed values
- Generate API documentation automatically

## Benefits of Deep Introspection

1. **Better Claude Integration**: Richer parameter info helps Claude understand events
2. **Type Safety**: Catch errors before runtime
3. **Self-Documentation**: Code is the documentation
4. **Validation**: Automatic parameter validation
5. **API Generation**: Can generate OpenAPI specs

## Example: Enhanced Discovery Output

```json
{
  "event": "state:set",
  "summary": "Set a value in shared state",
  "parameters": {
    "key": {
      "type": "string",
      "required": true,
      "description": "The state key to set",
      "example": "user_preferences"
    },
    "value": {
      "type": "any",
      "required": true,
      "description": "The value to store",
      "example": {"theme": "dark"}
    },
    "namespace": {
      "type": "string",
      "required": false,
      "default": "global",
      "description": "Storage namespace",
      "allowed_values": ["global", "user", "system", "temp"]
    }
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

## Conclusion

While docstring parsing works, combining AST analysis, TypedDict, and enhanced decorators would provide:
- Automatic discovery for existing code
- Type safety for new code
- Rich metadata for Claude and other consumers
- A migration path that doesn't break existing handlers

The hybrid approach allows gradual adoption while immediately improving parameter discovery.