#!/usr/bin/env python3

"""
State Manager - Session and shared state management
Refactored to use BaseManager pattern
"""

from typing import Dict, Any, Optional
from .base_manager import BaseManager, with_error_handling, log_operation
from .file_operations import FileOperations
from .timestamp_utils import TimestampManager

class StateManager(BaseManager):
    """Manages session tracking and shared state"""
    
    def __init__(self):
        super().__init__(
            manager_name="state",
            required_dirs=["shared_state"]
        )
    
    def _initialize(self):
        """Initialize manager-specific state"""
        self.sessions = {}  # session_id -> last_output
        self.shared_state = {}  # key -> value for agent coordination
        
        # TODO: Implement garbage collection system for shared_state/ files
        # These files accumulate from testing and need periodic cleanup
        # Consider: TTL-based cleanup, size limits, or explicit cleanup commands
    
    @log_operation()
    def track_session(self, session_id: str, output: Dict[str, Any]):
        """Track a session output"""
        self.sessions[session_id] = output
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        return self.sessions.get(session_id)
    
    def get_all_sessions(self) -> Dict[str, Any]:
        """Get all tracked sessions"""
        return self.sessions.copy()
    
    @log_operation()
    def clear_sessions(self) -> int:
        """Clear all session tracking"""
        count = len(self.sessions)
        self.sessions.clear()
        return count
    
    @log_operation()
    @with_error_handling("set_shared_state")
    def set_shared_state(self, key: str, value: str):
        """Set shared state value with persistence"""
        self.shared_state[key] = value
        
        # Persist to file using FileOperations
        shared_file = f'shared_state/{key}.json'
        FileOperations.save_json(shared_file, {
            'value': value,
            'updated_at': TimestampManager.timestamp_utc()
        })
        
        self.logger.info(f"Set shared state: {key}")
    
    @with_error_handling("get_shared_state")
    def get_shared_state(self, key: str) -> Optional[str]:
        """Get shared state value with file fallback"""
        value = self.shared_state.get(key)
        
        if value is None:
            # Try to load from file
            shared_file = f'shared_state/{key}.json'
            data = FileOperations.load_json(shared_file)
            if data:
                value = data.get('value')
                self.shared_state[key] = value  # Cache it
        
        return value
    
    def get_all_shared_state(self) -> Dict[str, str]:
        """Get all shared state"""
        return self.shared_state.copy()
    
    def serialize_state(self) -> Dict[str, Any]:
        """Serialize state for hot reload"""
        return {
            'sessions': self.sessions,
            'shared_state': self.shared_state
        }
    
    def deserialize_state(self, state: Dict[str, Any]):
        """Deserialize state from hot reload"""
        self.sessions = state.get('sessions', {})
        self.shared_state = state.get('shared_state', {})
        self.logger.info(f"Loaded state: {len(self.sessions)} sessions")