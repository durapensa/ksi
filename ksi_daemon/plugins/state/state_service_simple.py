#!/usr/bin/env python3
"""
Simplified State Service Plugin

Provides persistent state management without complex inheritance.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import pluggy

from ...plugin_utils import get_logger, event_handler, plugin_metadata
from ...timestamp_utils import TimestampManager
from ...config import config

# Plugin metadata
plugin_metadata("state_service", version="2.0.0", 
                description="Simplified persistent state management")

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Module state
logger = get_logger("state_service")
agent_state: Dict[str, Dict[str, Any]] = {}
shared_state: Dict[str, Any] = {}
sessions: Dict[str, Dict[str, Any]] = {}
state_dir = Path(config.state_dir)
state_dir.mkdir(parents=True, exist_ok=True)


# Persistence functions
def persist_agent_state(agent_id: str):
    """Persist agent state to disk."""
    agent_file = state_dir / f"agent_{agent_id}.json"
    with open(agent_file, 'w') as f:
        json.dump(agent_state.get(agent_id, {}), f, indent=2)


def persist_shared_state():
    """Persist shared state to disk."""
    shared_file = state_dir / "shared_state.json"
    with open(shared_file, 'w') as f:
        json.dump(shared_state, f, indent=2)


def persist_sessions():
    """Persist session data to disk."""
    sessions_file = state_dir / "sessions.json"
    with open(sessions_file, 'w') as f:
        json.dump(sessions, f, indent=2)


def load_persisted_state():
    """Load all persisted state from disk."""
    # Load agent states
    for agent_file in state_dir.glob("agent_*.json"):
        agent_id = agent_file.stem.replace("agent_", "")
        try:
            with open(agent_file) as f:
                agent_state[agent_id] = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load agent state {agent_id}: {e}")
    
    # Load shared state
    shared_file = state_dir / "shared_state.json"
    if shared_file.exists():
        try:
            with open(shared_file) as f:
                shared_state.update(json.load(f))
        except Exception as e:
            logger.error(f"Failed to load shared state: {e}")
    
    # Load sessions
    sessions_file = state_dir / "sessions.json"
    if sessions_file.exists():
        try:
            with open(sessions_file) as f:
                sessions.update(json.load(f))
        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")


# Hook implementations
@hookimpl
def ksi_startup(config):
    """Initialize state service on startup."""
    load_persisted_state()
    logger.info(f"State service started - agents: {len(agent_state)}, "
                f"shared keys: {len(shared_state)}, sessions: {len(sessions)}")
    return {
        "status": "state_service_ready",
        "agents": len(agent_state),
        "shared_keys": len(shared_state),
        "sessions": len(sessions)
    }


@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Handle state-related events."""
    
    # Get operation
    if event_name == "state:get":
        namespace = data.get("namespace", "")
        key = data.get("key", "")
        
        # Agent-specific state
        if namespace.startswith("agent:"):
            agent_id = namespace.split(":", 1)[1]
            agent_data = agent_state.get(agent_id, {})
            
            if key:
                value = agent_data.get(key)
                return {"value": value, "found": value is not None}
            else:
                return {"value": agent_data, "found": True}
        
        # Shared state
        elif namespace == "shared":
            value = shared_state.get(key)
            return {"value": value, "found": value is not None}
        
        # Default: check both
        else:
            agent_id = data.get("agent_id")
            if agent_id:
                agent_data = agent_state.get(agent_id, {})
                value = agent_data.get(key)
            else:
                value = shared_state.get(key)
            return {"value": value, "found": value is not None}
    
    # Set operation
    elif event_name == "state:set":
        namespace = data.get("namespace", "")
        key = data.get("key", "")
        value = data.get("value")
        
        if not key:
            return {"error": "Key is required"}
        
        # Agent-specific state
        if namespace.startswith("agent:"):
            agent_id = namespace.split(":", 1)[1]
            if agent_id not in agent_state:
                agent_state[agent_id] = {}
            
            agent_state[agent_id][key] = value
            persist_agent_state(agent_id)
            return {"status": "set", "namespace": namespace, "key": key}
        
        # Shared state
        elif namespace == "shared":
            shared_state[key] = value
            persist_shared_state()
            return {"status": "set", "namespace": "shared", "key": key}
        
        # Default behavior
        else:
            agent_id = data.get("agent_id")
            if agent_id:
                if agent_id not in agent_state:
                    agent_state[agent_id] = {}
                agent_state[agent_id][key] = value
                persist_agent_state(agent_id)
                return {"status": "set", "agent_id": agent_id, "key": key}
            else:
                shared_state[key] = value
                persist_shared_state()
                return {"status": "set", "namespace": "shared", "key": key}
    
    # Delete operation
    elif event_name == "state:delete":
        namespace = data.get("namespace", "")
        key = data.get("key", "")
        
        if not key:
            return {"error": "Key is required"}
        
        # Agent state
        if namespace.startswith("agent:"):
            agent_id = namespace.split(":", 1)[1]
            if agent_id in agent_state and key in agent_state[agent_id]:
                del agent_state[agent_id][key]
                persist_agent_state(agent_id)
                return {"status": "deleted", "namespace": namespace, "key": key}
        
        # Shared state
        elif namespace == "shared":
            if key in shared_state:
                del shared_state[key]
                persist_shared_state()
                return {"status": "deleted", "namespace": "shared", "key": key}
        
        return {"status": "not_found"}
    
    # List operation
    elif event_name == "state:list":
        namespace = data.get("namespace", "")
        pattern = data.get("pattern", "*")
        
        # List agent keys
        if namespace.startswith("agent:"):
            agent_id = namespace.split(":", 1)[1]
            if agent_id in agent_state:
                keys = list(agent_state[agent_id].keys())
                return {"keys": keys, "count": len(keys)}
        
        # List shared keys
        elif namespace == "shared":
            keys = list(shared_state.keys())
            return {"keys": keys, "count": len(keys)}
        
        # List all namespaces
        elif namespace == "" or namespace == "*":
            return {
                "agents": list(agent_state.keys()),
                "shared_keys": list(shared_state.keys()),
                "sessions": list(sessions.keys())
            }
        
        return {"keys": [], "count": 0}
    
    # Save operation
    elif event_name == "state:save":
        namespace = data.get("namespace", "*")
        saved = {"agents": 0, "shared_keys": 0, "sessions": 0}
        
        if namespace in ("*", "agents"):
            for agent_id in agent_state:
                persist_agent_state(agent_id)
            saved["agents"] = len(agent_state)
        
        if namespace in ("*", "shared"):
            persist_shared_state()
            saved["shared_keys"] = len(shared_state)
        
        if namespace in ("*", "sessions"):
            persist_sessions()
            saved["sessions"] = len(sessions)
        
        return {"status": "saved", "counts": saved}
    
    # Clear operation
    elif event_name == "state:clear":
        namespace = data.get("namespace", "")
        confirm = data.get("confirm", False)
        
        if not confirm:
            return {"error": "Set confirm=true to clear state"}
        
        cleared = {"agents": 0, "shared_keys": 0, "sessions": 0}
        
        if namespace in ("*", ""):
            cleared["agents"] = len(agent_state)
            cleared["shared_keys"] = len(shared_state)
            cleared["sessions"] = len(sessions)
            agent_state.clear()
            shared_state.clear()
            sessions.clear()
        elif namespace == "agents":
            cleared["agents"] = len(agent_state)
            agent_state.clear()
        elif namespace == "shared":
            cleared["shared_keys"] = len(shared_state)
            shared_state.clear()
        elif namespace == "sessions":
            cleared["sessions"] = len(sessions)
            sessions.clear()
        elif namespace.startswith("agent:"):
            agent_id = namespace.split(":", 1)[1]
            if agent_id in agent_state:
                cleared["agents"] = 1
                del agent_state[agent_id]
        
        return {"status": "cleared", "counts": cleared}
    
    # Session operations
    elif event_name == "state:update_session":
        session_id = data.get("session_id")
        session_data = data.get("data", {})
        
        if not session_id:
            return {"error": "session_id required"}
        
        if session_id not in sessions:
            sessions[session_id] = {
                "created_at": TimestampManager.format_for_logging(),
                "updated_at": TimestampManager.format_for_logging(),
                "message_count": 0
            }
        
        sessions[session_id].update(session_data)
        sessions[session_id]["updated_at"] = TimestampManager.format_for_logging()
        sessions[session_id]["message_count"] = sessions[session_id].get("message_count", 0) + 1
        
        persist_sessions()
        return {"status": "updated", "session_id": session_id}
    
    elif event_name == "state:get_session":
        session_id = data.get("session_id")
        
        if session_id:
            session = sessions.get(session_id)
            return {"session": session, "found": session is not None}
        else:
            return {"sessions": sessions}
    
    return None


@hookimpl
def ksi_shutdown():
    """Clean up on shutdown."""
    # Persist all state
    for agent_id in agent_state:
        persist_agent_state(agent_id)
    
    persist_shared_state()
    persist_sessions()
    
    logger.info(f"State service stopped - persisted {len(agent_state)} agents, "
                f"{len(shared_state)} shared keys, {len(sessions)} sessions")
    
    return {
        "status": "state_service_stopped",
        "persisted": {
            "agents": len(agent_state),
            "shared_keys": len(shared_state),
            "sessions": len(sessions)
        }
    }


# Module-level marker for plugin discovery
ksi_plugin = True