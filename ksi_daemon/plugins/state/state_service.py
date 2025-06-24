#!/usr/bin/env python3
"""
State Service Plugin

Provides persistent state management as a plugin service.
Handles key-value storage, session tracking, and shared state through events.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from datetime import datetime
import logging

from ...plugin_base import BasePlugin, hookimpl
from ...plugin_types import PluginMetadata, PluginCapabilities
from ...timestamp_utils import TimestampManager
from ...config import config

logger = logging.getLogger(__name__)


class StateServicePlugin(BasePlugin):
    """Service plugin for persistent state management."""
    
    def __init__(self):
        super().__init__(
            metadata=PluginMetadata(
                name="state_service",
                version="1.0.0",
                description="Persistent state management service",
                author="KSI Team"
            ),
            capabilities=PluginCapabilities(
                event_namespaces=["/state"],
                commands=[
                    "state:get", "state:set", "state:delete", "state:list",
                    "state:load", "state:save", "state:clear"
                ],
                provides_services=["state", "session_tracking"]
            )
        )
        
        # State storage
        self.agent_state: Dict[str, Dict[str, Any]] = {}
        self.shared_state: Dict[str, Any] = {}
        self.sessions: Dict[str, Dict[str, Any]] = {}
        
        # Plugin context
        self._event_bus = None
        
        # State persistence
        self.state_dir = Path(config.state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        # Load persisted state on startup
        self._load_persisted_state()
    
    @hookimpl
    def ksi_startup(self):
        """Initialize state service on startup."""
        logger.info("State service plugin starting")
        
        # Report loaded state
        return {
            "status": "state_service_ready",
            "agents": len(self.agent_state),
            "shared_keys": len(self.shared_state),
            "sessions": len(self.sessions)
        }
    
    @hookimpl
    def ksi_plugin_context(self, context):
        """Receive plugin context with event bus."""
        self._event_bus = context.get("event_bus")
    
    @hookimpl
    def ksi_handle_event(self, event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
        """Handle state-related events."""
        
        # Key-value operations
        if event_name == "state:get":
            return self._handle_get(data)
        
        elif event_name == "state:set":
            return self._handle_set(data)
        
        elif event_name == "state:delete":
            return self._handle_delete(data)
        
        elif event_name == "state:list":
            return self._handle_list(data)
        
        # State persistence operations
        elif event_name == "state:load":
            return self._handle_load(data)
        
        elif event_name == "state:save":
            return self._handle_save(data)
        
        elif event_name == "state:clear":
            return self._handle_clear(data)
        
        # Session operations
        elif event_name == "state:update_session":
            return self._handle_update_session(data)
        
        elif event_name == "state:get_session":
            return self._handle_get_session(data)
        
        return None
    
    def _handle_get(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Get a state value."""
        namespace = data.get("namespace", "")
        key = data.get("key", "")
        
        # Check for agent-specific state
        if namespace.startswith("agent:"):
            agent_id = namespace.split(":", 1)[1]
            agent_data = self.agent_state.get(agent_id, {})
            
            if key:
                value = agent_data.get(key)
                return {"value": value, "found": value is not None}
            else:
                # Return all agent state
                return {"value": agent_data, "found": True}
        
        # Check for shared state
        elif namespace == "shared" or key.startswith("shared:"):
            actual_key = key.split(":", 1)[1] if ":" in key else key
            value = self.shared_state.get(actual_key)
            return {"value": value, "found": value is not None}
        
        # Default: global state
        else:
            # For backward compatibility, check agent state with agent_id
            agent_id = data.get("agent_id")
            if agent_id:
                agent_data = self.agent_state.get(agent_id, {})
                value = agent_data.get(key)
                return {"value": value, "found": value is not None}
            
            # Otherwise check shared state
            value = self.shared_state.get(key)
            return {"value": value, "found": value is not None}
    
    def _handle_set(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Set a state value."""
        namespace = data.get("namespace", "")
        key = data.get("key", "")
        value = data.get("value")
        
        if not key:
            return {"error": "Key is required"}
        
        # Set agent-specific state
        if namespace.startswith("agent:"):
            agent_id = namespace.split(":", 1)[1]
            if agent_id not in self.agent_state:
                self.agent_state[agent_id] = {}
            
            self.agent_state[agent_id][key] = value
            self._persist_agent_state(agent_id)
            
            # Emit state change event
            asyncio.create_task(self._emit_state_change("agent", agent_id, key, value))
            
            return {"status": "set", "namespace": namespace, "key": key}
        
        # Set shared state
        elif namespace == "shared" or key.startswith("shared:"):
            actual_key = key.split(":", 1)[1] if ":" in key else key
            self.shared_state[actual_key] = value
            self._persist_shared_state()
            
            # Emit state change event
            asyncio.create_task(self._emit_state_change("shared", None, actual_key, value))
            
            return {"status": "set", "namespace": "shared", "key": actual_key}
        
        # Default: handle backward compatibility
        else:
            agent_id = data.get("agent_id")
            if agent_id:
                # Set as agent state
                if agent_id not in self.agent_state:
                    self.agent_state[agent_id] = {}
                
                self.agent_state[agent_id][key] = value
                self._persist_agent_state(agent_id)
                
                # Emit state change event
                asyncio.create_task(self._emit_state_change("agent", agent_id, key, value))
                
                return {"status": "set", "agent_id": agent_id, "key": key}
            else:
                # Set as shared state
                self.shared_state[key] = value
                self._persist_shared_state()
                
                # Emit state change event
                asyncio.create_task(self._emit_state_change("shared", None, key, value))
                
                return {"status": "set", "namespace": "shared", "key": key}
    
    def _handle_delete(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a state value."""
        namespace = data.get("namespace", "")
        key = data.get("key", "")
        
        if not key:
            return {"error": "Key is required"}
        
        # Delete from agent state
        if namespace.startswith("agent:"):
            agent_id = namespace.split(":", 1)[1]
            if agent_id in self.agent_state and key in self.agent_state[agent_id]:
                del self.agent_state[agent_id][key]
                self._persist_agent_state(agent_id)
                return {"status": "deleted", "namespace": namespace, "key": key}
        
        # Delete from shared state
        elif namespace == "shared" or key.startswith("shared:"):
            actual_key = key.split(":", 1)[1] if ":" in key else key
            if actual_key in self.shared_state:
                del self.shared_state[actual_key]
                self._persist_shared_state()
                return {"status": "deleted", "namespace": "shared", "key": actual_key}
        
        return {"status": "not_found"}
    
    def _handle_list(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """List keys in a namespace."""
        namespace = data.get("namespace", "")
        pattern = data.get("pattern", "*")
        
        keys = []
        
        # List agent keys
        if namespace.startswith("agent:"):
            agent_id = namespace.split(":", 1)[1]
            if agent_id in self.agent_state:
                keys = list(self.agent_state[agent_id].keys())
        
        # List shared keys
        elif namespace == "shared":
            keys = list(self.shared_state.keys())
        
        # List all namespaces
        elif namespace == "" or namespace == "*":
            result = {
                "agents": list(self.agent_state.keys()),
                "shared_keys": list(self.shared_state.keys()),
                "sessions": list(self.sessions.keys())
            }
            return result
        
        # Apply pattern filtering if needed
        if pattern != "*":
            import fnmatch
            keys = [k for k in keys if fnmatch.fnmatch(k, pattern)]
        
        return {"keys": keys, "count": len(keys)}
    
    def _handle_load(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Load state from disk."""
        namespace = data.get("namespace", "*")
        
        loaded = {
            "agents": 0,
            "shared_keys": 0,
            "sessions": 0
        }
        
        if namespace == "*" or namespace == "agents":
            self._load_agent_states()
            loaded["agents"] = len(self.agent_state)
        
        if namespace == "*" or namespace == "shared":
            self._load_shared_state()
            loaded["shared_keys"] = len(self.shared_state)
        
        if namespace == "*" or namespace == "sessions":
            self._load_sessions()
            loaded["sessions"] = len(self.sessions)
        
        return {"status": "loaded", "counts": loaded}
    
    def _handle_save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Save state to disk."""
        namespace = data.get("namespace", "*")
        
        saved = {
            "agents": 0,
            "shared_keys": 0,
            "sessions": 0
        }
        
        if namespace == "*" or namespace == "agents":
            for agent_id in self.agent_state:
                self._persist_agent_state(agent_id)
            saved["agents"] = len(self.agent_state)
        
        if namespace == "*" or namespace == "shared":
            self._persist_shared_state()
            saved["shared_keys"] = len(self.shared_state)
        
        if namespace == "*" or namespace == "sessions":
            self._persist_sessions()
            saved["sessions"] = len(self.sessions)
        
        return {"status": "saved", "counts": saved}
    
    def _handle_clear(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Clear state (with optional namespace)."""
        namespace = data.get("namespace", "")
        confirm = data.get("confirm", False)
        
        if not confirm:
            return {"error": "Set confirm=true to clear state"}
        
        cleared = {
            "agents": 0,
            "shared_keys": 0,
            "sessions": 0
        }
        
        if namespace == "*" or namespace == "":
            # Clear everything
            cleared["agents"] = len(self.agent_state)
            cleared["shared_keys"] = len(self.shared_state)
            cleared["sessions"] = len(self.sessions)
            
            self.agent_state.clear()
            self.shared_state.clear()
            self.sessions.clear()
            
        elif namespace == "agents":
            cleared["agents"] = len(self.agent_state)
            self.agent_state.clear()
            
        elif namespace == "shared":
            cleared["shared_keys"] = len(self.shared_state)
            self.shared_state.clear()
            
        elif namespace == "sessions":
            cleared["sessions"] = len(self.sessions)
            self.sessions.clear()
            
        elif namespace.startswith("agent:"):
            agent_id = namespace.split(":", 1)[1]
            if agent_id in self.agent_state:
                cleared["agents"] = 1
                del self.agent_state[agent_id]
        
        return {"status": "cleared", "counts": cleared}
    
    def _handle_update_session(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update session tracking."""
        session_id = data.get("session_id")
        session_data = data.get("data", {})
        
        if not session_id:
            return {"error": "session_id required"}
        
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "created_at": TimestampManager.format_for_logging(),
                "updated_at": TimestampManager.format_for_logging(),
                "message_count": 0
            }
        
        # Update session
        self.sessions[session_id].update(session_data)
        self.sessions[session_id]["updated_at"] = TimestampManager.format_for_logging()
        self.sessions[session_id]["message_count"] = self.sessions[session_id].get("message_count", 0) + 1
        
        # Persist sessions
        self._persist_sessions()
        
        return {"status": "updated", "session_id": session_id}
    
    def _handle_get_session(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Get session information."""
        session_id = data.get("session_id")
        
        if session_id:
            session = self.sessions.get(session_id)
            return {"session": session, "found": session is not None}
        else:
            # Return all sessions
            return {"sessions": self.sessions}
    
    # Persistence methods
    def _persist_agent_state(self, agent_id: str):
        """Persist agent state to disk."""
        agent_file = self.state_dir / f"agent_{agent_id}.json"
        with open(agent_file, 'w') as f:
            json.dump(self.agent_state.get(agent_id, {}), f, indent=2)
    
    def _persist_shared_state(self):
        """Persist shared state to disk."""
        shared_file = self.state_dir / "shared_state.json"
        with open(shared_file, 'w') as f:
            json.dump(self.shared_state, f, indent=2)
    
    def _persist_sessions(self):
        """Persist session data to disk."""
        sessions_file = self.state_dir / "sessions.json"
        with open(sessions_file, 'w') as f:
            json.dump(self.sessions, f, indent=2)
    
    def _load_persisted_state(self):
        """Load all persisted state from disk."""
        self._load_agent_states()
        self._load_shared_state()
        self._load_sessions()
    
    def _load_agent_states(self):
        """Load agent states from disk."""
        for agent_file in self.state_dir.glob("agent_*.json"):
            agent_id = agent_file.stem.replace("agent_", "")
            try:
                with open(agent_file) as f:
                    self.agent_state[agent_id] = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load agent state {agent_id}: {e}")
    
    def _load_shared_state(self):
        """Load shared state from disk."""
        shared_file = self.state_dir / "shared_state.json"
        if shared_file.exists():
            try:
                with open(shared_file) as f:
                    self.shared_state = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load shared state: {e}")
    
    def _load_sessions(self):
        """Load session data from disk."""
        sessions_file = self.state_dir / "sessions.json"
        if sessions_file.exists():
            try:
                with open(sessions_file) as f:
                    self.sessions = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load sessions: {e}")
    
    async def _emit_state_change(self, state_type: str, agent_id: Optional[str], 
                                 key: str, value: Any):
        """Emit state change event."""
        if self._event_bus:
            event_data = {
                "type": state_type,
                "key": key,
                "value": value,
                "timestamp": TimestampManager.format_for_logging()
            }
            
            if agent_id:
                event_data["agent_id"] = agent_id
            
            await self._event_bus.publish("state:changed", event_data)
    
    @hookimpl
    def ksi_shutdown(self):
        """Clean up on shutdown."""
        # Persist all state
        for agent_id in self.agent_state:
            self._persist_agent_state(agent_id)
        
        self._persist_shared_state()
        self._persist_sessions()
        
        return {
            "status": "state_service_stopped",
            "persisted": {
                "agents": len(self.agent_state),
                "shared_keys": len(self.shared_state),
                "sessions": len(self.sessions)
            }
        }


# Plugin instance
plugin = StateServicePlugin()