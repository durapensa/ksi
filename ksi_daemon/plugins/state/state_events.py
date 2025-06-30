#!/usr/bin/env python3
"""
State Events Plugin

Thin event handler wrapper that exposes state infrastructure through events.
All actual state functionality is provided by daemon infrastructure.
"""

import json
from typing import Dict, Any, Optional
import pluggy

from ksi_daemon.plugin_utils import plugin_metadata
from ksi_common.logging import get_bound_logger

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
    """Handle state-related events."""
    
    if not state_manager:
        return {"error": "State infrastructure not available"}
    
    # Get operation
    if event_name == "state:get":
        return handle_get(data)
    
    # Set operation
    elif event_name == "state:set":
        return handle_set(data)
    
    # Delete operation
    elif event_name == "state:delete":
        return handle_delete(data)
    
    # List keys
    elif event_name == "state:list":
        return handle_list(data)
    
    # Clear namespace
    elif event_name == "state:clear":
        return handle_clear(data)
    
    # Session operations
    elif event_name == "state:session:update":
        return handle_session_update(data)
    
    elif event_name == "state:session:get":
        return handle_session_get(data)
    
    # Async state operations
    elif event_name == "async_state:push":
        return handle_async_push(data)
    
    elif event_name == "async_state:pop":
        return handle_async_pop(data)
    
    elif event_name == "async_state:get_queue":
        return handle_async_get_queue(data)
    
    elif event_name == "async_state:get_keys":
        return handle_async_get_keys(data)
    
    elif event_name == "async_state:queue_length":
        return handle_async_queue_length(data)
    
    elif event_name == "async_state:delete":
        return handle_async_delete(data)
    
    return None


def handle_get(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle state get operation."""
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


def handle_set(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle state set operation."""
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


def handle_delete(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle state delete operation."""
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


def handle_list(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle state list operation."""
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


def handle_clear(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle state clear operation."""
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


def handle_session_update(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle session update."""
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


def handle_session_get(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle session get."""
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
async def handle_async_push(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle async state push operation."""
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


async def handle_async_pop(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle async state pop operation."""
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


async def handle_async_get_queue(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle async state get queue operation."""
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


async def handle_async_get_keys(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle async state get keys operation."""
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


async def handle_async_queue_length(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle async state queue length operation."""
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


async def handle_async_delete(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle async state delete operation."""
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