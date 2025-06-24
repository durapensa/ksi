#!/usr/bin/env python3

"""
Session and Shared State Manager - Manages session tracking and shared key-value state
Handles both conversation sessions and agent coordination state
"""

from typing import Dict, Any, Optional, List
import sqlite3
import json
from pathlib import Path
from .manager_framework import BaseManager, with_error_handling, log_operation
from .timestamp_utils import TimestampManager
from .config import config

class SessionAndSharedStateManager(BaseManager):
    """Manages session tracking and shared state for agent coordination"""
    
    def __init__(self):
        super().__init__(
            manager_name="state",
            required_dirs=[]  # No file directories needed for SQLite
        )
    
    def _initialize(self):
        """Initialize manager-specific state"""
        self.sessions = {}  # session_id -> last_output
        self.db_path = str(config.db_path)
        
        # Initialize SQLite database
        self._init_sqlite()
    
    def _init_sqlite(self):
        """Initialize SQLite database for agent shared state"""
        # Ensure var/db directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Check if database exists and create if not
        if not Path(self.db_path).exists():
            self.logger.info(f"Creating new agent shared state database: {self.db_path}")
            # Run schema creation
            schema_path = Path("coordination_schema.sql")
            if schema_path.exists():
                import subprocess
                subprocess.run(['sqlite3', self.db_path], stdin=open(schema_path, 'r'))
            else:
                # Create minimal schema inline if schema file not found
                self._create_schema()
        else:
            self.logger.info(f"Using existing agent shared state database: {self.db_path}")
    
    def _create_schema(self):
        """Create schema inline if schema file not available"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS agent_shared_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    namespace TEXT,
                    owner_agent_id TEXT NOT NULL,
                    scope TEXT DEFAULT 'shared',
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    metadata TEXT
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_namespace ON agent_shared_state(namespace)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_owner ON agent_shared_state(owner_agent_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_expires ON agent_shared_state(expires_at)')
    
    def _extract_namespace(self, key: str) -> Optional[str]:
        """Extract namespace from key using agent_id.purpose.detail convention"""
        parts = key.split('.')
        if len(parts) >= 2:
            return '.'.join(parts[:2])  # agent_id.purpose
        return None
    
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
    def set_shared_state(self, key: str, value: Any, owner_agent_id: str = "system", 
                        scope: str = "shared", expires_at: Optional[str] = None, 
                        metadata: Optional[Dict[str, Any]] = None):
        """Set shared state value with SQLite persistence"""
        return self.create_shared_state(key, value, owner_agent_id, scope, expires_at, metadata)
    
    def create_shared_state(self, key: str, value: Any, owner_agent_id: str = "system",
                          scope: str = "shared", expires_at: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create/update shared state using SQLite (standardized API)"""
        # Convert value to JSON string
        value_json = json.dumps(value) if not isinstance(value, str) else value
        
        # Extract namespace from key
        namespace = self._extract_namespace(key)
        
        # Prepare metadata
        metadata_json = json.dumps(metadata) if metadata else None
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO agent_shared_state 
                (key, value, namespace, owner_agent_id, scope, created_at, expires_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                key, value_json, namespace, owner_agent_id, scope,
                TimestampManager.timestamp_utc(), expires_at, metadata_json
            ))
        
        self.logger.info(f"Set shared state: {key} (owner: {owner_agent_id}, scope: {scope})")
        return key
    
    def update_shared_state(self, key: str, value: Any, owner_agent_id: str = "system") -> bool:
        """Update shared state if it exists (standardized API)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT key FROM agent_shared_state WHERE key = ?', (key,))
            if cursor.fetchone():
                return bool(self.create_shared_state(key, value, owner_agent_id))
        return False
    
    @with_error_handling("get_shared_state")
    def get_shared_state(self, key: str) -> Optional[Any]:
        """Get shared state value from SQLite"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT value FROM agent_shared_state WHERE key = ?', (key,))
            row = cursor.fetchone()
            if row:
                try:
                    # Try to parse as JSON, fallback to string
                    return json.loads(row[0])
                except json.JSONDecodeError:
                    return row[0]
        return None
    
    def list_shared_state(self) -> List[Dict[str, Any]]:
        """List all shared state keys from SQLite (standardized API)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT key, namespace, owner_agent_id, scope, created_at, expires_at 
                FROM agent_shared_state ORDER BY created_at DESC
            ''')
            return [
                {
                    'key': row[0],
                    'namespace': row[1],
                    'owner_agent_id': row[2],
                    'scope': row[3],
                    'created_at': row[4],
                    'expires_at': row[5]
                }
                for row in cursor.fetchall()
            ]
    
    def remove_shared_state(self, key: str) -> bool:
        """Remove shared state key from SQLite (standardized API)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('DELETE FROM agent_shared_state WHERE key = ?', (key,))
            return cursor.rowcount > 0
    
    def clear_shared_state(self) -> int:
        """Clear all shared state from SQLite (standardized API)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT COUNT(*) FROM agent_shared_state')
            count = cursor.fetchone()[0]
            conn.execute('DELETE FROM agent_shared_state')
            return count
    
    def serialize_state(self) -> Dict[str, Any]:
        """Serialize state for hot reload (sessions only - shared state in SQLite)"""
        return {
            'sessions': self.sessions,
            'db_path': self.db_path
        }
    
    def deserialize_state(self, state: Dict[str, Any]):
        """Deserialize state from hot reload (sessions only - shared state in SQLite)"""
        self.sessions = state.get('sessions', {})
        self.db_path = state.get('db_path', 'agent_shared_state.db')
        self.logger.info(f"Loaded state: {len(self.sessions)} sessions, SQLite DB: {self.db_path}")
        
        # Verify SQLite database is accessible
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM agent_shared_state')
                count = cursor.fetchone()[0]
                self.logger.info(f"SQLite shared state contains {count} entries")
        except Exception as e:
            self.logger.warning(f"Could not access SQLite database {self.db_path}: {e}")