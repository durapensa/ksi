#!/usr/bin/env python3
"""
State Events Plugin

Thin event handler wrapper that exposes state infrastructure through events.
All actual state functionality is provided by daemon infrastructure.
"""

import json
from typing import Dict, Any, Optional, TypedDict
from typing_extensions import NotRequired
import pluggy

from ksi_daemon.plugin_utils import plugin_metadata, event_handler, create_ksi_describe_events_hook
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

# Plugin metadata
plugin_metadata("state_events", version="4.0.0", 
                description="Event handlers for state management")

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

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


@hookimpl
def ksi_plugin_context(context):
    """Receive infrastructure from daemon context."""
    global state_manager, async_state
    
    state_manager = context.get("state_manager")
    async_state = context.get("async_state")
    
    if state_manager:
        logger.info("State events plugin connected to state infrastructure")
    else:
        logger.error("State manager not available in context")


@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Handle state-related events using decorated handlers."""
    
    if not state_manager:
        return {"error": "State infrastructure not available"}
    
    
    # Look for decorated handlers
    import sys
    import inspect
    module = sys.modules[__name__]
    
    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj) and hasattr(obj, '_ksi_event_name'):
            if obj._ksi_event_name == event_name:
                return obj(data)
    
    # Legacy async_state operations handler (until we migrate all handlers)
    if event_name == "async_state:delete":
        return handle_async_delete(data)
    
    return None


@event_handler("state:get", data_type=StateGetData)
def handle_get(data: StateGetData) -> Dict[str, Any]:
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


@event_handler("state:set", data_type=StateSetData)
def handle_set(data: StateSetData) -> Dict[str, Any]:
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
        {"namespace": "agent", "key": "config", "value": {"timeout": 30}}
    """
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
        state_manager.set_shared_state(full_key, value, metadata=metadata)
        return {
            "status": "set",
            "namespace": namespace,
            "key": key
        }
    except Exception as e:
        logger.error(f"Error setting state: {e}")
        return {"error": str(e)}


@event_handler("state:delete", data_type=StateDeleteData)
def handle_delete(data: StateDeleteData) -> Dict[str, Any]:
    """
    Delete a key from shared state.
    
    Args:
        namespace (str): The namespace to delete from (default: "global")
        key (str): The key to delete (required)
    
    Returns:
        Dictionary with status (deleted/not_found), namespace, and key
    
    Example:
        {"namespace": "agent", "key": "temp_data"}
    """
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
        success = state_manager.remove_shared_state(full_key)
        return {
            "status": "deleted" if success else "not_found",
            "namespace": namespace,
            "key": key
        }
    except Exception as e:
        logger.error(f"Error deleting state: {e}")
        return {"error": str(e)}


@event_handler("state:list", data_type=StateListData)
def handle_list(data: StateListData) -> Dict[str, Any]:
    """
    List keys in shared state.
    
    Args:
        namespace (str): Filter by namespace (optional)
        pattern (str): Filter by pattern substring (optional)
    
    Returns:
        Dictionary with keys array, count, namespace, and pattern
    
    Example:
        {"namespace": "agent", "pattern": "session"}
    """
    namespace = data.get("namespace")
    pattern = data.get("pattern")
    
    try:
        # Get all shared state
        all_state = state_manager.list_shared_state()
        
        # Filter by namespace and pattern
        keys = []
        for item in all_state:
            key = item['key']
            
            # Check namespace match
            if namespace:
                if namespace == "global" and ":" in key:
                    continue  # Skip namespaced keys
                elif namespace != "global" and not key.startswith(f"{namespace}:"):
                    continue  # Skip keys from other namespaces
            
            # Check pattern match (simple substring for now)
            if pattern and pattern not in key:
                continue
                
            # Remove namespace prefix for display
            display_key = key
            if namespace and namespace != "global" and key.startswith(f"{namespace}:"):
                display_key = key[len(namespace)+1:]
            
            keys.append(display_key)
        
        return {
            "keys": keys,
            "count": len(keys),
            "namespace": namespace,
            "pattern": pattern
        }
    except Exception as e:
        logger.error(f"Error listing keys: {e}")
        return {"error": str(e)}


@event_handler("state:clear")
def handle_clear(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clear all keys in a namespace.
    
    Args:
        namespace (str): The namespace to clear (required)
    
    Returns:
        Dictionary with status, namespace, and keys_deleted count
    
    Example:
        {"namespace": "temp"}
    """
    namespace = data.get("namespace")
    
    if not namespace:
        return {"error": "Namespace is required for clear operation"}
    
    try:
        # Get all shared state
        all_state = state_manager.list_shared_state()
        
        # Find and delete keys in namespace
        deleted_count = 0
        for item in all_state:
            key = item['key']
            
            # Check if key belongs to namespace
            if namespace == "global" and ":" not in key:
                state_manager.remove_shared_state(key)
                deleted_count += 1
            elif namespace != "global" and key.startswith(f"{namespace}:"):
                state_manager.remove_shared_state(key)
                deleted_count += 1
        
        return {
            "status": "cleared",
            "namespace": namespace,
            "keys_deleted": deleted_count
        }
    except Exception as e:
        logger.error(f"Error clearing namespace: {e}")
        return {"error": str(e)}


@event_handler("state:session:update")
def handle_session_update(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update session output data.
    
    Args:
        session_id (str): The session ID to update (required)
        output (any): The output data to store (required)
    
    Returns:
        Dictionary with status and session_id
    
    Example:
        {"session_id": "abc123", "output": {"result": "completed"}}
    """
    session_id = data.get("session_id")
    output = data.get("output")
    
    if not session_id:
        return {"error": "session_id required"}
    
    try:
        state_manager.update_session(session_id, output)
        return {
            "status": "updated",
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Error updating session: {e}")
        return {"error": str(e)}


@event_handler("state:session:get")
def handle_session_get(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get session output data.
    
    Args:
        session_id (str): The session ID to retrieve (required)
    
    Returns:
        Dictionary with session_id, output, and found status
    
    Example:
        {"session_id": "abc123"}
    """
    session_id = data.get("session_id")
    
    if not session_id:
        return {"error": "session_id required"}
    
    try:
        output = state_manager.get_session_output(session_id)
        return {
            "session_id": session_id,
            "output": output,
            "found": output is not None
        }
    except Exception as e:
        logger.error(f"Error getting session: {e}")
        return {"error": str(e)}


# Async state handler functions
@event_handler("async_state:push")
async def handle_async_push(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Push a value to an async state queue.
    
    Args:
        namespace (str): The namespace for the queue (required)
        key (str): The queue key (required)
        data (any): The data to push to the queue (required)
        ttl_seconds (int): Optional time-to-live in seconds
    
    Returns:
        Dictionary with status, position in queue, namespace, and key
    
    Example:
        {"namespace": "events", "key": "incoming", "data": {"type": "click"}, "ttl_seconds": 3600}
    """
    if not async_state:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "")
    key = data.get("key", "")
    value = data.get("data")
    ttl_seconds = data.get("ttl_seconds")
    
    if not namespace or not key:
        return {"error": "namespace and key are required"}
    
    try:
        position = await async_state.push(namespace, key, value, ttl_seconds)
        return {
            "status": "pushed",
            "position": position,
            "namespace": namespace,
            "key": key
        }
    except Exception as e:
        logger.error(f"Error pushing to async state: {e}")
        return {"error": str(e)}


@event_handler("async_state:pop")
async def handle_async_pop(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pop a value from an async state queue.
    
    Args:
        namespace (str): The namespace for the queue (required)
        key (str): The queue key (required)
    
    Returns:
        Dictionary with status, data (if found), found status, namespace, and key
    
    Example:
        {"namespace": "events", "key": "incoming"}
    """
    if not async_state:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "")
    key = data.get("key", "")
    
    if not namespace or not key:
        return {"error": "namespace and key are required"}
    
    try:
        value = await async_state.pop(namespace, key)
        return {
            "status": "popped",
            "data": value,
            "found": value is not None,
            "namespace": namespace,
            "key": key
        }
    except Exception as e:
        logger.error(f"Error popping from async state: {e}")
        return {"error": str(e)}


@event_handler("async_state:get_queue")
async def handle_async_get_queue(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get all values from an async state queue without removing them.
    
    Args:
        namespace (str): The namespace for the queue (required)
        key (str): The queue key (required)
        limit (int): Maximum number of items to return (optional)
    
    Returns:
        Dictionary with status, data array, count, namespace, and key
    
    Example:
        {"namespace": "events", "key": "incoming", "limit": 10}
    """
    if not async_state:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "")
    key = data.get("key", "")
    limit = data.get("limit")
    
    if not namespace or not key:
        return {"error": "namespace and key are required"}
    
    try:
        items = await async_state.get_queue(namespace, key, limit)
        return {
            "status": "success",
            "data": items,
            "count": len(items),
            "namespace": namespace,
            "key": key
        }
    except Exception as e:
        logger.error(f"Error getting queue from async state: {e}")
        return {"error": str(e)}


@event_handler("async_state:get_keys")
async def handle_async_get_keys(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get all queue keys in a namespace.
    
    Args:
        namespace (str): The namespace to list keys from (required)
    
    Returns:
        Dictionary with status, keys array, count, and namespace
    
    Example:
        {"namespace": "events"}
    """
    if not async_state:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "")
    
    if not namespace:
        return {"error": "namespace is required"}
    
    try:
        keys = await async_state.get_keys(namespace)
        return {
            "status": "success",
            "keys": keys,
            "count": len(keys),
            "namespace": namespace
        }
    except Exception as e:
        logger.error(f"Error getting keys from async state: {e}")
        return {"error": str(e)}


@event_handler("async_state:queue_length")
async def handle_async_queue_length(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get the length of an async state queue.
    
    Args:
        namespace (str): The namespace for the queue (required)
        key (str): The queue key (required)
    
    Returns:
        Dictionary with status, length, namespace, and key
    
    Example:
        {"namespace": "events", "key": "incoming"}
    """
    if not async_state:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "")
    key = data.get("key", "")
    
    if not namespace or not key:
        return {"error": "namespace and key are required"}
    
    try:
        length = await async_state.queue_length(namespace, key)
        return {
            "status": "success",
            "length": length,
            "namespace": namespace,
            "key": key
        }
    except Exception as e:
        logger.error(f"Error getting queue length from async state: {e}")
        return {"error": str(e)}


@event_handler("async_state:delete")
async def handle_async_delete(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Delete an entire async state queue.
    
    Args:
        namespace (str): The namespace for the queue (required)
        key (str): The queue key (required)
    
    Returns:
        Dictionary with status, deleted flag, namespace, and key
    
    Example:
        {"namespace": "events", "key": "old_queue"}
    """
    if not async_state:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "")
    key = data.get("key", "")
    
    if not namespace or not key:
        return {"error": "namespace and key are required"}
    
    try:
        deleted = await async_state.delete_queue(namespace, key)
        return {
            "status": "deleted",
            "deleted": deleted,
            "namespace": namespace,
            "key": key
        }
    except Exception as e:
        logger.error(f"Error deleting from async state: {e}")
        return {"error": str(e)}


# Module-level marker for plugin discovery
ksi_plugin = True

# Enable event discovery
ksi_describe_events = create_ksi_describe_events_hook(__name__)