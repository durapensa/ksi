#!/usr/bin/env python3
"""
Async State - Functional persistent state for async flows

Provides persistent state management for:
- Injection queues (next-mode injections)
- Completion queues (fork prevention)
- Any async flow that needs restart resilience

Design principles:
- All state persists to SQLite immediately
- State organized by namespace and key
- Supports queue-like operations (push/pop/peek)
- Automatic expiration for stale entries
- Simple functional interface
"""

import json
import time
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
from contextlib import contextmanager

from ksi_common.logging import get_logger
from ksi_common.config import config

logger = get_logger("async_state")

# Module state
_db_path: Optional[Path] = None
_initialized = False


def initialize(db_path: Optional[Path] = None):
    """Initialize async state database."""
    global _db_path, _initialized
    
    if db_path is None:
        db_path = config.async_state_db_path
    
    _db_path = db_path
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize schema - create connection directly during initialization
    conn = sqlite3.connect(str(_db_path))
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
    
    _initialized = True
    logger.info(f"Async state initialized at {_db_path}")


@contextmanager
def _get_db():
    """Get database connection with proper cleanup."""
    if not _initialized:
        raise RuntimeError("Async state not initialized")
    
    conn = sqlite3.connect(str(_db_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# Queue-like operations

async def push(namespace: str, key: str, data: Dict[str, Any], 
               ttl_seconds: Optional[int] = None) -> int:
    """Push item to queue (append)."""
    created_at = time.time()
    expires_at = created_at + ttl_seconds if ttl_seconds else None
    
    with _get_db() as conn:
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


async def pop(namespace: str, key: str) -> Optional[Dict[str, Any]]:
    """Pop item from queue (remove and return first)."""
    with _get_db() as conn:
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


async def peek(namespace: str, key: str) -> Optional[Dict[str, Any]]:
    """Peek at first item without removing."""
    with _get_db() as conn:
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


async def get_queue(namespace: str, key: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get items in queue order."""
    with _get_db() as conn:
        query = """SELECT data FROM async_state 
                   WHERE namespace = ? AND key = ? 
                   ORDER BY position ASC"""
        
        if limit:
            query += f" LIMIT {limit}"
            
        cursor = conn.execute(query, (namespace, key))
        return [json.loads(row['data']) for row in cursor.fetchall()]


async def queue_length(namespace: str, key: str) -> int:
    """Get number of items in queue."""
    with _get_db() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM async_state WHERE namespace = ? AND key = ?",
            (namespace, key)
        )
        return cursor.fetchone()['count']


async def delete_queue(namespace: str, key: str) -> int:
    """Delete all entries for namespace:key."""
    with _get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM async_state WHERE namespace = ? AND key = ?",
            (namespace, key)
        )
        conn.commit()
        
        deleted = cursor.rowcount
        if deleted > 0:
            logger.debug(f"Deleted {deleted} entries from {namespace}:{key}")
        return deleted


# Key operations

async def get_keys(namespace: str) -> List[str]:
    """Get all keys in namespace."""
    with _get_db() as conn:
        cursor = conn.execute(
            "SELECT DISTINCT key FROM async_state WHERE namespace = ? ORDER BY key",
            (namespace,)
        )
        return [row['key'] for row in cursor.fetchall()]


# Maintenance operations

async def cleanup_expired() -> int:
    """Remove expired entries."""
    current_time = time.time()
    
    with _get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM async_state WHERE expires_at IS NOT NULL AND expires_at < ?",
            (current_time,)
        )
        conn.commit()
        
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} expired entries")
        return deleted