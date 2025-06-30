#!/usr/bin/env python3
"""
State Service Plugin

Provides persistent state management using SQLite backend.
Wraps the SessionAndSharedStateManager for plugin architecture.
"""

import json
from typing import Dict, Any, Optional
import logging
import pluggy

from ksi_daemon.plugin_utils import plugin_metadata
from ksi_common import TimestampManager
from ksi_daemon.plugins.state.session_and_shared_state_manager import SessionAndSharedStateManager
from ksi_common.logging import get_logger

# Plugin metadata
plugin_metadata("state_service", version="3.0.0", 
                description="SQLite-backed persistent state management")

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Module state
logger = get_logger("state_service")
state_manager: Optional[SessionAndSharedStateManager] = None

# Plugin info
PLUGIN_INFO = {
    "name": "state_service",
    "version": "3.0.0",
    "description": "SQLite-backed persistent state management"
}

# Reload configuration
_reloadable = True
_reload_strategy = "stateful"
_state_hooks = ["serialize_state", "deserialize_state"]


# Hook implementations
@hookimpl(tryfirst=True)  # Initialize early - other plugins depend on state service
def ksi_startup(config):
    """Initialize state service on startup."""
    global state_manager
    
    try:
        state_manager = SessionAndSharedStateManager()
        # BaseManager automatically calls _initialize() during construction
        
        # Get current state counts
        shared_count = len(state_manager.list_shared_state())
        session_count = len(state_manager.sessions)
        
        logger.info(f"State service started - shared keys: {shared_count}, "
                    f"sessions: {session_count}")
        
        return {
            "status": "state_service_ready",
            "shared_keys": shared_count,
            "sessions": session_count,
            "database": str(state_manager.db_path)
        }
    except Exception as e:
        logger.error(f"Failed to initialize state service: {e}", exc_info=True)
        return {
            "status": "state_service_error", 
            "error": str(e)
        }


@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Handle state-related events."""
    
    if not state_manager:
        return {"error": "State service not initialized"}
    
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


@hookimpl
def ksi_shutdown():
    """Clean up on shutdown."""
    if state_manager:
        try:
            # State manager automatically commits on operations
            logger.info("State service stopped")
        except Exception as e:
            logger.error(f"Error during state service shutdown: {e}")
    
    return {
        "status": "state_service_stopped"
    }


@hookimpl
def ksi_serialize_state():
    """Serialize state for reload."""
    if not state_manager:
        return None
    
    logger.info("Serializing state service state")
    
    # Get current state
    return {
        "sessions": state_manager.sessions.copy(),
        "db_path": str(state_manager.db_path),
        "identities": getattr(state_manager, 'identities', {})
    }


@hookimpl
def ksi_deserialize_state(state):
    """Restore state after reload."""
    if not state_manager or not state:
        return
    
    logger.info("Restoring state service state")
    
    # Restore sessions
    if "sessions" in state:
        state_manager.sessions = state["sessions"]
        logger.info(f"Restored {len(state_manager.sessions)} sessions")
    
    # DB path should already match from init
    # Identities if any
    if "identities" in state:
        setattr(state_manager, 'identities', state["identities"])


@hookimpl
def ksi_validate_reload():
    """Validate if state service can be reloaded."""
    # State service can always be reloaded since SQLite handles persistence
    return {"valid": True}


# Module-level marker for plugin discovery
ksi_plugin = True