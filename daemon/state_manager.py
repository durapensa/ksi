#!/usr/bin/env python3

"""
State Manager - Session and shared state management
Extracted from daemon_clean.py with 100% functionality preservation
"""

import json
import os
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger('daemon')

class StateManager:
    """Manages session tracking and shared state"""
    
    def __init__(self):
        self.sessions = {}  # session_id -> last_output
        self.shared_state = {}  # key -> value for agent coordination
        
        # Ensure directories exist
        os.makedirs('shared_state', exist_ok=True)
    
    def track_session(self, session_id: str, output: dict):
        """Track a session output"""
        self.sessions[session_id] = output
    
    def get_session(self, session_id: str) -> dict:
        """Get session data"""
        return self.sessions.get(session_id)
    
    def get_all_sessions(self) -> dict:
        """Get all tracked sessions"""
        return self.sessions.copy()
    
    def clear_sessions(self) -> int:
        """Clear all session tracking"""
        count = len(self.sessions)
        self.sessions.clear()
        return count
    
    def set_shared_state(self, key: str, value: str):
        """Set shared state value with persistence"""
        self.shared_state[key] = value
        
        # Persist to file
        shared_file = f'shared_state/{key}.json'
        with open(shared_file, 'w') as f:
            json.dump({'value': value, 'updated_at': datetime.utcnow().isoformat() + "Z"}, f)
        
        logger.info(f"Set shared state: {key}")
    
    def get_shared_state(self, key: str) -> str:
        """Get shared state value with file fallback"""
        value = self.shared_state.get(key)
        
        if value is None:
            # Try to load from file
            shared_file = f'shared_state/{key}.json'
            try:
                with open(shared_file, 'r') as f:
                    data = json.load(f)
                    value = data.get('value')
                    self.shared_state[key] = value  # Cache it
            except (FileNotFoundError, json.JSONDecodeError):
                pass
        
        return value
    
    def get_all_shared_state(self) -> dict:
        """Get all shared state"""
        return self.shared_state.copy()
    
    def serialize_state(self) -> dict:
        """Serialize state for hot reload - EXACT copy from daemon_clean.py"""
        return {
            'sessions': self.sessions,
            'shared_state': self.shared_state
        }
    
    def deserialize_state(self, state: dict):
        """Deserialize state from hot reload - EXACT copy from daemon_clean.py"""
        self.sessions = state.get('sessions', {})
        self.shared_state = state.get('shared_state', {})
        logger.info(f"Loaded state: {len(self.sessions)} sessions")