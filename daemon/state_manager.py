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
        """Track a session output (legacy name for create/update)"""
        self.sessions[session_id] = output
    
    def create_session(self, session_id: str, output: Dict[str, Any]) -> str:
        """Create/update session (standardized API)"""
        self.sessions[session_id] = output
        return session_id
    
    def update_session(self, session_id: str, output: Dict[str, Any]) -> bool:
        """Update session (standardized API)"""
        if session_id in self.sessions:
            self.sessions[session_id] = output
            return True
        return False
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        return self.sessions.get(session_id)
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions (standardized API)"""
        from typing import List
        return [
            {'session_id': sid, 'has_output': bool(output)}
            for sid, output in self.sessions.items()
        ]
    
    def remove_session(self, session_id: str) -> bool:
        """Remove a session (standardized API)"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
    
    @log_operation()
    def clear_sessions(self) -> int:
        """Clear all session tracking"""
        count = len(self.sessions)
        self.sessions.clear()
        return count
    
    @log_operation()
    @with_error_handling("set_shared_state")
    def set_shared_state(self, key: str, value: str):
        """Set shared state value with persistence (legacy name)"""
        return self.create_shared_state(key, value)
    
    def create_shared_state(self, key: str, value: str) -> str:
        """Create/update shared state (standardized API)"""
        self.shared_state[key] = value
        
        # Persist to file using FileOperations
        shared_file = f'shared_state/{key}.json'
        FileOperations.save_json(shared_file, {
            'value': value,
            'updated_at': TimestampManager.timestamp_utc()
        })
        
        self.logger.info(f"Set shared state: {key}")
        return key
    
    def update_shared_state(self, key: str, value: str) -> bool:
        """Update shared state (standardized API)"""
        if key in self.shared_state:
            self.create_shared_state(key, value)
            return True
        return False
    
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
    
    def list_shared_state(self) -> List[Dict[str, Any]]:
        """List all shared state keys (standardized API)"""
        from typing import List
        return [
            {'key': key, 'has_value': bool(value)}
            for key, value in self.shared_state.items()
        ]
    
    def remove_shared_state(self, key: str) -> bool:
        """Remove shared state key (standardized API)"""
        if key in self.shared_state:
            del self.shared_state[key]
            # Also remove file
            shared_file = f'shared_state/{key}.json'
            try:
                Path(shared_file).unlink(missing_ok=True)
            except:
                pass
            return True
        return False
    
    def clear_shared_state(self) -> int:
        """Clear all shared state (standardized API)"""
        count = len(self.shared_state)
        self.shared_state.clear()
        return count
    
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