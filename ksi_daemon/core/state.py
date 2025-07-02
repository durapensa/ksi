#!/usr/bin/env python3
"""
Core State Management - Unified session tracking, shared state, and async queue operations

Provides three types of state management:
1. Session tracking - in-memory session data for conversation continuity
2. Shared state - persistent SQLite key-value store for agent coordination
3. Async state - persistent SQLite queue operations for async flows

All state functionality is exposed through both direct API and event handlers.
"""

import asyncio
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, Optional, List, TypedDict
from typing_extensions import NotRequired

from ksi_daemon.event_system import event_handler
from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc

logger = get_bound_logger("core_state", version="1.0.0")

# Type definitions for event handlers
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


class CoreStateManager:
    """Unified state manager for sessions, shared state, and async operations."""
    
    def __init__(self):
        self.logger = get_bound_logger("core_state", version="1.0.0")
        self.sessions = {}  # session_id -> last_output
        self.db_path = str(config.db_path)
        self.async_db_path = str(config.async_state_db_path)
        self._async_initialized = False
        
        # Initialize databases
        self._init_shared_state_db()
        self._init_async_state_db()
    
    # Session Management
    
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
    
    def get_session_output(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session output (alias for get_session)"""
        return self.get_session(session_id)
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions (standardized API)"""
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
    
    def clear_sessions(self) -> int:
        """Clear all session tracking"""
        count = len(self.sessions)
        self.sessions.clear()
        return count
    
    # Shared State Management (SQLite)
    
    def _init_shared_state_db(self):
        """Initialize SQLite database for shared state"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        if not Path(self.db_path).exists():
            self.logger.info(f"Creating new shared state database: {self.db_path}")
        else:
            self.logger.info(f"Using existing shared state database: {self.db_path}")
        
        self._create_shared_state_schema()
    
    def _create_shared_state_schema(self):
        """Create shared state schema"""
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
                timestamp_utc(), expires_at, metadata_json
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
    
    def delete_shared_state(self, key: str) -> bool:
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
    
    # Async State Management (SQLite Queue Operations)
    
    def _init_async_state_db(self):
        """Initialize async state database."""
        Path(self.async_db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize schema
        conn = sqlite3.connect(str(self.async_db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS async_state (
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    position INTEGER NOT NULL DEFAULT 0,
                    data TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL,
                    PRIMARY KEY (namespace, key, position)
                )
            """)
            
            # Indexes for efficient queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_async_state_expiry 
                ON async_state(expires_at) 
                WHERE expires_at IS NOT NULL
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_async_state_namespace_key 
                ON async_state(namespace, key)
            """)
            
            conn.commit()
        finally:
            conn.close()
        
        self._async_initialized = True
        self.logger.info(f"Async state initialized at {self.async_db_path}")
    
    @contextmanager
    def _get_async_db(self):
        """Get async state database connection with proper cleanup."""
        if not self._async_initialized:
            raise RuntimeError("Async state not initialized")
        
        conn = sqlite3.connect(str(self.async_db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    async def async_push(self, namespace: str, key: str, data: Dict[str, Any], 
                        ttl_seconds: Optional[int] = None) -> int:
        """Push item to async queue (append)."""
        created_at = time.time()
        expires_at = created_at + ttl_seconds if ttl_seconds else None
        
        with self._get_async_db() as conn:
            # Get next position
            cursor = conn.execute(
                "SELECT MAX(position) as max_pos FROM async_state WHERE namespace = ? AND key = ?",
                (namespace, key)
            )
            row = cursor.fetchone()
            position = (row['max_pos'] + 1) if row['max_pos'] is not None else 0
            
            # Insert new entry
            conn.execute(
                """INSERT INTO async_state 
                   (namespace, key, position, data, created_at, expires_at) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (namespace, key, position, json.dumps(data), created_at, expires_at)
            )
            conn.commit()
            
        self.logger.debug(f"Pushed to {namespace}:{key} at position {position}")
        return position
    
    async def async_pop(self, namespace: str, key: str) -> Optional[Dict[str, Any]]:
        """Pop item from async queue (remove and return first)."""
        with self._get_async_db() as conn:
            # Get first item
            cursor = conn.execute(
                """SELECT * FROM async_state 
                   WHERE namespace = ? AND key = ? 
                   ORDER BY position ASC LIMIT 1""",
                (namespace, key)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            # Delete it
            conn.execute(
                """DELETE FROM async_state 
                   WHERE namespace = ? AND key = ? AND position = ?""",
                (namespace, key, row['position'])
            )
            conn.commit()
            
            data = json.loads(row['data'])
            self.logger.debug(f"Popped from {namespace}:{key}")
            return data
    
    async def async_peek(self, namespace: str, key: str) -> Optional[Dict[str, Any]]:
        """Peek at first item without removing."""
        with self._get_async_db() as conn:
            cursor = conn.execute(
                """SELECT data FROM async_state 
                   WHERE namespace = ? AND key = ? 
                   ORDER BY position ASC LIMIT 1""",
                (namespace, key)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return json.loads(row['data'])
    
    async def async_get_queue(self, namespace: str, key: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get items in queue order."""
        with self._get_async_db() as conn:
            query = """SELECT data FROM async_state 
                       WHERE namespace = ? AND key = ? 
                       ORDER BY position ASC"""
            
            if limit:
                query += f" LIMIT {limit}"
                
            cursor = conn.execute(query, (namespace, key))
            return [json.loads(row['data']) for row in cursor.fetchall()]
    
    async def async_queue_length(self, namespace: str, key: str) -> int:
        """Get number of items in queue."""
        with self._get_async_db() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM async_state WHERE namespace = ? AND key = ?",
                (namespace, key)
            )
            return cursor.fetchone()['count']
    
    async def async_delete_queue(self, namespace: str, key: str) -> int:
        """Delete all entries for namespace:key."""
        with self._get_async_db() as conn:
            cursor = conn.execute(
                "DELETE FROM async_state WHERE namespace = ? AND key = ?",
                (namespace, key)
            )
            conn.commit()
            
            deleted = cursor.rowcount
            if deleted > 0:
                self.logger.debug(f"Deleted {deleted} entries from {namespace}:{key}")
            return deleted
    
    async def async_get_keys(self, namespace: str) -> List[str]:
        """Get all keys in namespace."""
        with self._get_async_db() as conn:
            cursor = conn.execute(
                "SELECT DISTINCT key FROM async_state WHERE namespace = ? ORDER BY key",
                (namespace,)
            )
            return [row['key'] for row in cursor.fetchall()]
    
    async def async_cleanup_expired(self) -> int:
        """Remove expired entries."""
        current_time = time.time()
        
        with self._get_async_db() as conn:
            cursor = conn.execute(
                "DELETE FROM async_state WHERE expires_at IS NOT NULL AND expires_at < ?",
                (current_time,)
            )
            conn.commit()
            
            deleted = cursor.rowcount
            if deleted > 0:
                self.logger.info(f"Cleaned up {deleted} expired entries")
            return deleted


# Global state manager instance - initialized by daemon core
state_manager: Optional[CoreStateManager] = None


def get_state_manager() -> CoreStateManager:
    """Get the global state manager instance."""
    if state_manager is None:
        raise RuntimeError("State manager not initialized")
    return state_manager


def initialize_state() -> CoreStateManager:
    """Initialize the global state manager."""
    global state_manager
    if state_manager is None:
        state_manager = CoreStateManager()
        logger.info("Core state manager initialized")
    return state_manager


# Event Handlers - expose state functionality through events

@event_handler("system:context")
async def handle_context(context: Dict[str, Any]) -> None:
    """Receive infrastructure context - state manager is available."""
    # State manager is now a core service, always available
    if state_manager:
        logger.info("Core state manager connected to event system")
    else:
        logger.error("State manager not available in core module")


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
        state_manager.set_shared_state(full_key, value, "system", "shared", None, metadata)
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
        all_keys = [item['key'] for item in state_manager.list_shared_state()]
        
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
    if not state_manager:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "default")
    key = data.get("key", "")
    
    if not key:
        return {"error": "Key is required"}
    
    try:
        value = await state_manager.async_peek(namespace, key)
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
    if not state_manager:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "default")
    key = data.get("key", "")
    value = data.get("value")
    
    if not key:
        return {"error": "Key is required"}
    
    try:
        await state_manager.async_push(namespace, key, value)
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
    if not state_manager:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "default")
    key = data.get("key", "")
    
    if not key:
        return {"error": "Key is required"}
    
    try:
        deleted_count = await state_manager.async_delete_queue(namespace, key)
        return {
            "status": "deleted",
            "namespace": namespace,
            "key": key,
            "deleted_count": deleted_count
        }
    except Exception as e:
        logger.error(f"Error deleting async state: {e}")
        return {"error": str(e)}


@event_handler("async_state:push")
async def handle_async_push(data: Dict[str, Any]) -> Dict[str, Any]:
    """Push value to async queue."""
    if not state_manager:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "default")
    queue_name = data.get("queue_name", "")
    value = data.get("value")
    
    if not queue_name:
        return {"error": "Queue name is required"}
    
    try:
        position = await state_manager.async_push(namespace, queue_name, value)
        return {
            "status": "pushed",
            "namespace": namespace,
            "queue_name": queue_name,
            "position": position
        }
    except Exception as e:
        logger.error(f"Error pushing to async queue: {e}")
        return {"error": str(e)}


@event_handler("async_state:pop")
async def handle_async_pop(data: Dict[str, Any]) -> Dict[str, Any]:
    """Pop value from async queue."""
    if not state_manager:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "default")
    queue_name = data.get("queue_name", "")
    
    if not queue_name:
        return {"error": "Queue name is required"}
    
    try:
        value = await state_manager.async_pop(namespace, queue_name)
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
    if not state_manager:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "default")
    
    try:
        keys = await state_manager.async_get_keys(namespace)
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
    if not state_manager:
        return {"error": "Async state infrastructure not available"}
        
    namespace = data.get("namespace", "default") 
    queue_name = data.get("queue_name", "")
    
    if not queue_name:
        return {"error": "Queue name is required"}
    
    try:
        length = await state_manager.async_queue_length(namespace, queue_name)
        return {
            "length": length,
            "namespace": namespace,
            "queue_name": queue_name
        }
    except Exception as e:
        logger.error(f"Error getting async queue length: {e}")
        return {"error": str(e)}