#!/usr/bin/env python3
"""
Async State Manager - Generalized persistent state for async flows

Provides persistent state management for:
- Injection queues (next-mode injections)
- Completion queues (fork prevention)
- Any async flow that needs restart resilience

Design principles:
- All state persists to SQLite immediately
- State organized by namespace and key
- Supports queue-like operations (push/pop/peek)
- Automatic expiration for stale entries
- Extensible for future async patterns
"""

import json
import time
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import asyncio
from contextlib import contextmanager

from ksi_common.logging import get_logger

logger = get_logger("async_state_manager")


@dataclass
class StateEntry:
    """Represents a single state entry."""
    namespace: str  # e.g., "injection", "completion_queue"
    key: str       # e.g., session_id
    data: Dict[str, Any]
    created_at: float
    expires_at: Optional[float] = None
    position: int = 0  # For queue ordering
    
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class AsyncStateManager:
    """Manages persistent state for async flows."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
    def _init_db(self):
        """Initialize database schema."""
        with self._get_db() as conn:
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
    
    @contextmanager
    def _get_db(self):
        """Get database connection with proper cleanup."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    # Queue-like operations for injection/completion queues
    
    async def push(self, namespace: str, key: str, data: Dict[str, Any], 
                   ttl_seconds: Optional[int] = None) -> int:
        """Push item to queue (append)."""
        created_at = time.time()
        expires_at = created_at + ttl_seconds if ttl_seconds else None
        
        with self._get_db() as conn:
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
            
        logger.debug(f"Pushed to {namespace}:{key} at position {position}")
        return position
    
    async def pop(self, namespace: str, key: str) -> Optional[Dict[str, Any]]:
        """Pop item from queue (remove and return first)."""
        with self._get_db() as conn:
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
            logger.debug(f"Popped from {namespace}:{key}")
            return data
    
    async def peek(self, namespace: str, key: str) -> Optional[Dict[str, Any]]:
        """Peek at first item without removing."""
        with self._get_db() as conn:
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
    
    async def get_queue(self, namespace: str, key: str) -> List[Dict[str, Any]]:
        """Get all items in queue order."""
        with self._get_db() as conn:
            cursor = conn.execute(
                """SELECT data FROM async_state 
                   WHERE namespace = ? AND key = ? 
                   ORDER BY position ASC""",
                (namespace, key)
            )
            
            return [json.loads(row['data']) for row in cursor.fetchall()]
    
    async def queue_length(self, namespace: str, key: str) -> int:
        """Get number of items in queue."""
        with self._get_db() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM async_state WHERE namespace = ? AND key = ?",
                (namespace, key)
            )
            return cursor.fetchone()['count']
    
    # Key-value operations for simple state
    
    async def set(self, namespace: str, key: str, data: Dict[str, Any],
                  ttl_seconds: Optional[int] = None) -> None:
        """Set single value (replaces any existing)."""
        created_at = time.time()
        expires_at = created_at + ttl_seconds if ttl_seconds else None
        
        with self._get_db() as conn:
            # Delete existing
            conn.execute(
                "DELETE FROM async_state WHERE namespace = ? AND key = ?",
                (namespace, key)
            )
            
            # Insert new
            conn.execute(
                """INSERT INTO async_state 
                   (namespace, key, position, data, created_at, expires_at) 
                   VALUES (?, ?, 0, ?, ?, ?)""",
                (namespace, key, json.dumps(data), created_at, expires_at)
            )
            conn.commit()
            
        logger.debug(f"Set {namespace}:{key}")
    
    async def get(self, namespace: str, key: str) -> Optional[Dict[str, Any]]:
        """Get single value."""
        with self._get_db() as conn:
            cursor = conn.execute(
                """SELECT data FROM async_state 
                   WHERE namespace = ? AND key = ? AND position = 0""",
                (namespace, key)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return json.loads(row['data'])
    
    async def delete(self, namespace: str, key: str) -> int:
        """Delete all entries for namespace:key."""
        with self._get_db() as conn:
            cursor = conn.execute(
                "DELETE FROM async_state WHERE namespace = ? AND key = ?",
                (namespace, key)
            )
            conn.commit()
            
            deleted = cursor.rowcount
            if deleted > 0:
                logger.debug(f"Deleted {deleted} entries from {namespace}:{key}")
            return deleted
    
    # Maintenance operations
    
    async def cleanup_expired(self) -> int:
        """Remove expired entries."""
        current_time = time.time()
        
        with self._get_db() as conn:
            cursor = conn.execute(
                "DELETE FROM async_state WHERE expires_at IS NOT NULL AND expires_at < ?",
                (current_time,)
            )
            conn.commit()
            
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} expired entries")
            return deleted
    
    async def get_namespaces(self) -> List[str]:
        """Get all active namespaces."""
        with self._get_db() as conn:
            cursor = conn.execute(
                "SELECT DISTINCT namespace FROM async_state ORDER BY namespace"
            )
            return [row['namespace'] for row in cursor.fetchall()]
    
    async def get_keys(self, namespace: str) -> List[str]:
        """Get all keys in namespace."""
        with self._get_db() as conn:
            cursor = conn.execute(
                "SELECT DISTINCT key FROM async_state WHERE namespace = ? ORDER BY key",
                (namespace,)
            )
            return [row['key'] for row in cursor.fetchall()]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics about stored state."""
        with self._get_db() as conn:
            # Total entries
            cursor = conn.execute("SELECT COUNT(*) as total FROM async_state")
            total = cursor.fetchone()['total']
            
            # By namespace
            cursor = conn.execute(
                """SELECT namespace, COUNT(*) as count 
                   FROM async_state 
                   GROUP BY namespace"""
            )
            by_namespace = {row['namespace']: row['count'] for row in cursor.fetchall()}
            
            # Expired
            cursor = conn.execute(
                """SELECT COUNT(*) as expired 
                   FROM async_state 
                   WHERE expires_at IS NOT NULL AND expires_at < ?""",
                (time.time(),)
            )
            expired = cursor.fetchone()['expired']
            
            return {
                "total_entries": total,
                "by_namespace": by_namespace,
                "expired_entries": expired
            }


# Global instance (initialized by plugin)
async_state_manager: Optional[AsyncStateManager] = None


def get_async_state_manager() -> AsyncStateManager:
    """Get the global async state manager."""
    if async_state_manager is None:
        raise RuntimeError("Async state manager not initialized")
    return async_state_manager