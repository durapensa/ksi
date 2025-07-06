#!/usr/bin/env python3
"""Test AST-only discovery for existing handlers."""

from hybrid_introspection_prototype import hybrid_event_handler

# Existing handler without TypedDict
@hybrid_event_handler(
    "state:get",
    auto_discover=True  # Only AST discovery
)
def handle_state_get(data):
    """Get a value from shared state."""
    namespace = data.get("namespace", "global")
    key = data.get("key", "")
    
    if not key:
        return {"error": "Key is required"}
    
    # Simulate getting value
    value = f"value_for_{namespace}:{key}"
    
    return {
        "value": value,
        "found": True,
        "namespace": namespace,
        "key": key
    }

# Test discovery
metadata = handle_state_get._ksi_event_metadata
print(f"Event: {metadata['event']}")
print(f"Summary: {metadata['summary']}")
print("\nAST-Discovered Parameters:")

for name, info in metadata['parameters'].items():
    req = "required" if info.get('required', False) else "optional"
    default = f" (default: {info['default']})" if 'default' in info else ""
    print(f"  {name}: {req}{default}")
    if 'discovered_by' in info:
        print(f"    discovered by: {info['discovered_by']}")