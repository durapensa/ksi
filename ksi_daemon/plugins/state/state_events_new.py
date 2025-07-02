#!/usr/bin/env python3
"""
State Events Plugin - Event-Based Version

Thin event handler wrapper that exposes state infrastructure through events.
All actual state functionality is provided by daemon infrastructure.
"""

import json
from typing import Dict, Any, Optional, TypedDict, List
from typing_extensions import NotRequired

from ksi_daemon.event_system import event_handler
from ksi_common.logging import get_bound_logger


# Per-plugin TypedDict definitions (optional type safety)
class StateSetData(TypedDict):
    """Type-safe data for state:set."""
    key: str
    value: Any
    namespace: NotRequired[str]
    metadata: NotRequired[Dict[str, Any]]

class StateGetData(TypedDict):
    """Type-safe data for state:get."""
    key: str
    namespace: NotRequired[str]

class StateDeleteData(TypedDict):
    """Type-safe data for state:delete."""
    key: str
    namespace: NotRequired[str]

class StateListData(TypedDict):
    """Type-safe data for state:list."""
    namespace: NotRequired[str]
    pattern: NotRequired[str]


# Module state
logger = get_bound_logger("state_events", version="1.0.0")
state_manager = None
async_state = None

# Plugin info
PLUGIN_INFO = {
    "name": "state_events",
    "version": "4.0.0",
    "description": "Event handlers for state management"
}


@event_handler("system:context")
async def handle_context(context: Dict[str, Any]) -> None:
    """Receive infrastructure from daemon context."""
    global state_manager, async_state
    
    state_manager = context.get("state_manager")
    async_state = context.get("async_state")
    
    if state_manager:
        logger.info("State events plugin connected to state infrastructure")
    else:
        logger.error("State manager not available in context")


@event_handler("state:get")
async def handle_get(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get a value from shared state.
    
    Args:
        namespace (str): The namespace to get from (default: "global")
        key (str): The key to retrieve (required)
    
    Returns:
        Dictionary with value, found status, namespace, and key
    
    Example:
        {"namespace": "agent", "key": "session_data"}
    """
    if not state_manager:
        return {"error": "State infrastructure not available"}
        
    namespace = data.get("namespace", "global")
    key = data.get("key", "")
    
    if not key:
        return {"error": "Key is required"}
    
    # Handle shared: prefix for backward compatibility
    if key.startswith("shared:"):
        key = key[7:]  # Remove "shared:" prefix
    
    try:
        # Prefix key with namespace if provided
        full_key = f"{namespace}:{key}" if namespace != "global" else key
        value = state_manager.get_shared_state(full_key)
        return {
            "value": value,
            "found": value is not None,
            "namespace": namespace,
            "key": key
        }
    except Exception as e:
        logger.error(f"Error getting state: {e}")
        return {"error": str(e)}


@event_handler("state:set")
async def handle_set(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set a value in shared state.
    
    Args:
        namespace (str): The namespace to set in (default: "global")
        key (str): The key to set (required)
        value (any): The value to store (required)
        metadata (dict): Optional metadata to attach (default: {})
    
    Returns:
        Dictionary with status, namespace, and key
    
    Example:
        {"namespace": "agent", "key": "config", "value": {"model": "claude-2"}}
    """
    if not state_manager:
        return {"error": "State infrastructure not available"}
        
    namespace = data.get("namespace", "global")
    key = data.get("key", "")
    value = data.get("value")
    metadata = data.get("metadata", {})
    
    if not key:
        return {"error": "Key is required"}
    
    # Handle shared: prefix for backward compatibility
    if key.startswith("shared:"):
        key = key[7:]  # Remove "shared:" prefix
    
    try:
        # Prefix key with namespace if provided
        full_key = f"{namespace}:{key}" if namespace != "global" else key
        state_manager.set_shared_state(full_key, value, metadata)
        return {
            "status": "set",
            "namespace": namespace,
            "key": key
        }
    except Exception as e:
        logger.error(f"Error setting state: {e}")
        return {"error": str(e)}


@event_handler("state:delete")
async def handle_delete(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Delete a key from shared state.
    
    Args:
        namespace (str): The namespace to delete from (default: "global")
        key (str): The key to delete (required)
    
    Returns:
        Dictionary with status, namespace, and key
    """
    if not state_manager:
        return {"error": "State infrastructure not available"}
        
    namespace = data.get("namespace", "global")
    key = data.get("key", "")
    
    if not key:
        return {"error": "Key is required"}
    
    # Handle shared: prefix for backward compatibility
    if key.startswith("shared:"):
        key = key[7:]  # Remove "shared:" prefix
    
    try:
        # Prefix key with namespace if provided
        full_key = f"{namespace}:{key}" if namespace != "global" else key
        state_manager.delete_shared_state(full_key)
        return {
            "status": "deleted",
            "namespace": namespace,
            "key": key
        }
    except Exception as e:
        logger.error(f"Error deleting state: {e}")
        return {"error": str(e)}


@event_handler("state:list") 
async def handle_list(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    List keys in shared state.
    
    Args:
        namespace (str): Filter by namespace (optional)
        pattern (str): Filter by pattern (optional, supports * wildcard)
    
    Returns:
        Dictionary with list of keys
    """
    if not state_manager:
        return {"error": "State infrastructure not available"}
        
    namespace = data.get("namespace")
    pattern = data.get("pattern")
    
    try:
        # Get all keys
        all_keys = state_manager.list_shared_state()
        
        # Filter by namespace if provided
        if namespace:
            prefix = f"{namespace}:"
            all_keys = [k for k in all_keys if k.startswith(prefix)]
        
        # Filter by pattern if provided
        if pattern:
            import fnmatch
            all_keys = [k for k in all_keys if fnmatch.fnmatch(k, pattern)]
        
        return {
            "keys": all_keys,
            "count": len(all_keys)
        }
    except Exception as e:
        logger.error(f"Error listing state: {e}")
        return {"error": str(e)}


# Async state handlers

@event_handler("async_state:get")
async def handle_async_get(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get value from async state."""
    if not async_state:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "default")
    key = data.get("key", "")
    
    if not key:
        return {"error": "Key is required"}
    
    try:
        value = await async_state.get(namespace, key)
        return {
            "value": value,
            "found": value is not None,
            "namespace": namespace,
            "key": key
        }
    except Exception as e:
        logger.error(f"Error getting async state: {e}")
        return {"error": str(e)}


@event_handler("async_state:set")
async def handle_async_set(data: Dict[str, Any]) -> Dict[str, Any]:
    """Set value in async state."""
    if not async_state:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "default")
    key = data.get("key", "")
    value = data.get("value")
    
    if not key:
        return {"error": "Key is required"}
    
    try:
        await async_state.set(namespace, key, value)
        return {
            "status": "set",
            "namespace": namespace,
            "key": key
        }
    except Exception as e:
        logger.error(f"Error setting async state: {e}")
        return {"error": str(e)}


@event_handler("async_state:delete")
async def handle_async_delete(data: Dict[str, Any]) -> Dict[str, Any]:
    """Delete key from async state."""
    if not async_state:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "default")
    key = data.get("key", "")
    
    if not key:
        return {"error": "Key is required"}
    
    try:
        await async_state.delete(namespace, key)
        return {
            "status": "deleted",
            "namespace": namespace,
            "key": key
        }
    except Exception as e:
        logger.error(f"Error deleting async state: {e}")
        return {"error": str(e)}


@event_handler("async_state:push")
async def handle_async_push(data: Dict[str, Any]) -> Dict[str, Any]:
    """Push value to async queue."""
    if not async_state:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "default")
    queue_name = data.get("queue_name", "")
    value = data.get("value")
    
    if not queue_name:
        return {"error": "Queue name is required"}
    
    try:
        await async_state.push(namespace, queue_name, value)
        return {
            "status": "pushed",
            "namespace": namespace,
            "queue_name": queue_name
        }
    except Exception as e:
        logger.error(f"Error pushing to async queue: {e}")
        return {"error": str(e)}


@event_handler("async_state:pop")
async def handle_async_pop(data: Dict[str, Any]) -> Dict[str, Any]:
    """Pop value from async queue."""
    if not async_state:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "default")
    queue_name = data.get("queue_name", "")
    
    if not queue_name:
        return {"error": "Queue name is required"}
    
    try:
        value = await async_state.pop(namespace, queue_name)
        return {
            "value": value,
            "found": value is not None,
            "namespace": namespace,
            "queue_name": queue_name
        }
    except Exception as e:
        logger.error(f"Error popping from async queue: {e}")
        return {"error": str(e)}


@event_handler("async_state:get_keys")
async def handle_async_get_keys(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get all keys in a namespace."""
    if not async_state:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "default")
    pattern = data.get("pattern")
    
    try:
        keys = await async_state.get_keys(namespace, pattern)
        return {
            "keys": keys,
            "count": len(keys),
            "namespace": namespace
        }
    except Exception as e:
        logger.error(f"Error getting async state keys: {e}")
        return {"error": str(e)}


@event_handler("async_state:queue_length")
async def handle_async_queue_length(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get length of async queue."""
    if not async_state:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "default") 
    queue_name = data.get("queue_name", "")
    
    if not queue_name:
        return {"error": "Queue name is required"}
    
    try:
        length = await async_state.queue_length(namespace, queue_name)
        return {
            "length": length,
            "namespace": namespace,
            "queue_name": queue_name
        }
    except Exception as e:
        logger.error(f"Error getting async queue length: {e}")
        return {"error": str(e)}


# Module-level marker for plugin discovery
ksi_plugin = True