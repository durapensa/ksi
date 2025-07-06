#!/usr/bin/env python3
"""
Example: State handler using TypedDict for type safety and discovery.
"""

from typing import Dict, Any
import sys
sys.path.insert(0, '..')

from ksi_daemon.plugin_utils import event_handler
from ksi_daemon.event_types import StateSetData, StateGetData, StateListData

# Mock state manager for example
state_storage = {}

@event_handler("state:set", data_type=StateSetData)
def handle_state_set(data: StateSetData) -> Dict[str, Any]:
    """
    Set a value in shared state.
    
    This handler now has full type safety and automatic parameter discovery
    from the StateSetData TypedDict.
    """
    namespace = data.get("namespace", "global")
    key = data["key"]  # TypedDict knows this is required
    value = data["value"]  # Also required
    metadata = data.get("metadata", {})
    
    # Store the value
    full_key = f"{namespace}:{key}"
    state_storage[full_key] = {
        "value": value,
        "metadata": metadata
    }
    
    return {
        "status": "set",
        "namespace": namespace,
        "key": key
    }

@event_handler("state:get", data_type=StateGetData)
def handle_state_get(data: StateGetData) -> Dict[str, Any]:
    """Get a value from shared state."""
    namespace = data.get("namespace", "global")
    key = data["key"]
    
    full_key = f"{namespace}:{key}"
    stored = state_storage.get(full_key)
    
    if stored:
        return {
            "value": stored["value"],
            "found": True,
            "namespace": namespace,
            "key": key
        }
    else:
        return {
            "found": False,
            "namespace": namespace,
            "key": key
        }

@event_handler("state:list", data_type=StateListData)
def handle_state_list(data: StateListData) -> Dict[str, Any]:
    """List keys in shared state."""
    namespace = data.get("namespace")
    pattern = data.get("pattern")
    
    keys = []
    for full_key in state_storage:
        # Filter by namespace
        if namespace:
            if namespace == "global" and ":" in full_key:
                continue
            elif namespace != "global" and not full_key.startswith(f"{namespace}:"):
                continue
        
        # Filter by pattern
        if pattern and pattern not in full_key:
            continue
        
        # Extract display key
        if ":" in full_key:
            ns, key = full_key.split(":", 1)
            keys.append(key)
        else:
            keys.append(full_key)
    
    return {
        "keys": keys,
        "count": len(keys),
        "namespace": namespace,
        "pattern": pattern
    }

# Test discovery
if __name__ == "__main__":
    # Print discovered metadata
    for handler in [handle_state_set, handle_state_get, handle_state_list]:
        if hasattr(handler, '_ksi_event_metadata'):
            metadata = handler._ksi_event_metadata
            print(f"\nEvent: {metadata['event']}")
            print(f"Summary: {metadata['summary']}")
            print("Parameters:")
            for name, info in metadata['parameters'].items():
                req = "required" if info.get('required') else "optional"
                type_str = info.get('type', 'Any')
                discovered = info.get('discovered_by', 'unknown')
                print(f"  {name} ({type_str}) - {req} [discovered by: {discovered}]")