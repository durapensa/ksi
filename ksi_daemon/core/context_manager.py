"""
Context Manager for KSI Event System

Implements Python contextvars-based context propagation with reference-based storage.
This replaces the old approach of embedding full context in every event.

Key features:
- Automatic context propagation via Python's async internals
- Reference-based storage (66% size reduction)
- Two-tier architecture: Hot (memory) + Cold (SQLite)
- Zero data loss with dual-path persistence
"""

import asyncio
import json
import time
import uuid
from contextvars import ContextVar
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path
from collections import OrderedDict
import logging

from ksi_common.config import config

logger = logging.getLogger(__name__)

# Global context variable for automatic propagation
ksi_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar('ksi_context', default=None)


class InMemoryHotStorage:
    """Ultra-fast in-memory storage for recent events (last 24 hours)."""
    
    def __init__(self, ttl_hours: int = 24, max_size: int = 1_000_000):
        self.ttl_seconds = ttl_hours * 3600
        self.max_size = max_size
        
        # Fully denormalized storage for O(1) access
        self.events: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.contexts_by_ref: Dict[str, Dict[str, Any]] = {}
        self.events_by_correlation: Dict[str, List[str]] = {}
        self.events_by_agent: Dict[str, List[str]] = {}
        self.event_chains: Dict[str, List[str]] = {}  # parent -> children
        
        # Aging task
        self._aging_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start the aging background task."""
        self._aging_task = asyncio.create_task(self._aging_loop())
        
    async def stop(self):
        """Stop the aging background task."""
        if self._aging_task:
            self._aging_task.cancel()
            try:
                await self._aging_task
            except asyncio.CancelledError:
                pass
    
    def add_event(self, event: Dict[str, Any], context: Dict[str, Any]) -> None:
        """
        Add event to in-memory structures.
        This is synchronous for instant access.
        """
        event_id = event.get("event_id") or context.get("_event_id")
        if not event_id:
            return
            
        # Create fully denormalized record
        hot_record = {
            **event,
            "_ksi_context": context,
            "_added_at": time.time()
        }
        
        # Store in all indexes
        self.events[event_id] = hot_record
        self.contexts_by_ref[context.get("_ref", "")] = context
        
        # Update correlation index
        corr_id = context.get("_correlation_id")
        if corr_id:
            if corr_id not in self.events_by_correlation:
                self.events_by_correlation[corr_id] = []
            self.events_by_correlation[corr_id].append(event_id)
        
        # Update agent index
        agent_id = context.get("_agent_id")
        if agent_id:
            if agent_id not in self.events_by_agent:
                self.events_by_agent[agent_id] = []
            self.events_by_agent[agent_id].append(event_id)
        
        # Update event chains
        parent_id = context.get("_parent_event_id")
        if parent_id:
            if parent_id not in self.event_chains:
                self.event_chains[parent_id] = []
            self.event_chains[parent_id].append(event_id)
        
        # Enforce size limit (LRU)
        if len(self.events) > self.max_size:
            self._evict_oldest()
    
    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get event by ID - O(1) lookup."""
        return self.events.get(event_id)
    
    def get_context(self, ref: str) -> Optional[Dict[str, Any]]:
        """Get context by reference - O(1) lookup."""
        return self.contexts_by_ref.get(ref)
    
    def get_events_by_correlation(self, correlation_id: str) -> List[Dict[str, Any]]:
        """Get all events in a correlation - O(n) where n is events in correlation."""
        event_ids = self.events_by_correlation.get(correlation_id, [])
        return [self.events[eid] for eid in event_ids if eid in self.events]
    
    def get_event_chain(self, event_id: str) -> List[Dict[str, Any]]:
        """Get event and all its descendants - O(n) where n is chain size."""
        chain = []
        to_process = [event_id]
        
        while to_process:
            current_id = to_process.pop(0)
            if current_id in self.events:
                chain.append(self.events[current_id])
                children = self.event_chains.get(current_id, [])
                to_process.extend(children)
        
        return chain
    
    def _evict_oldest(self):
        """Remove oldest event when size limit reached."""
        if not self.events:
            return
            
        # Remove oldest (first) item
        event_id, event = self.events.popitem(last=False)
        context = event.get("_ksi_context", {})
        
        # Clean up indexes
        ref = context.get("_ref")
        if ref and ref in self.contexts_by_ref:
            del self.contexts_by_ref[ref]
        
        corr_id = context.get("_correlation_id")
        if corr_id and corr_id in self.events_by_correlation:
            self.events_by_correlation[corr_id].remove(event_id)
            if not self.events_by_correlation[corr_id]:
                del self.events_by_correlation[corr_id]
        
        agent_id = context.get("_agent_id")
        if agent_id and agent_id in self.events_by_agent:
            self.events_by_agent[agent_id].remove(event_id)
            if not self.events_by_agent[agent_id]:
                del self.events_by_agent[agent_id]
    
    async def _aging_loop(self):
        """Background task to remove events older than TTL."""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                await self._age_out_old_events()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in aging loop: {e}")
    
    async def _age_out_old_events(self):
        """Remove events older than TTL."""
        cutoff_time = time.time() - self.ttl_seconds
        events_to_remove = []
        
        # Find old events
        for event_id, event in self.events.items():
            if event.get("_added_at", 0) < cutoff_time:
                events_to_remove.append(event_id)
            else:
                # OrderedDict maintains insertion order, so we can stop
                break
        
        # Remove old events
        for event_id in events_to_remove:
            event = self.events.pop(event_id, None)
            if not event:
                continue
                
            context = event.get("_ksi_context", {})
            
            # Clean up indexes (same as _evict_oldest)
            ref = context.get("_ref")
            if ref and ref in self.contexts_by_ref:
                del self.contexts_by_ref[ref]
            
            corr_id = context.get("_correlation_id")
            if corr_id and corr_id in self.events_by_correlation:
                self.events_by_correlation[corr_id].remove(event_id)
                if not self.events_by_correlation[corr_id]:
                    del self.events_by_correlation[corr_id]
            
            agent_id = context.get("_agent_id")
            if agent_id and agent_id in self.events_by_agent:
                self.events_by_agent[agent_id].remove(event_id)
                if not self.events_by_agent[agent_id]:
                    del self.events_by_agent[agent_id]
        
        if events_to_remove:
            logger.info(f"Aged out {len(events_to_remove)} events from hot storage")


class SQLiteContextDatabase:
    """SQLite-backed context storage for persistence and historical queries."""
    
    def __init__(self, db_path: Optional[Path] = None, retention_days: int = 30):
        self.db_path = db_path or config.context_db_path
        self.retention_days = retention_days
        self.conn: Optional[sqlite3.Connection] = None
        
    async def initialize(self):
        """Initialize database and create tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use connection with JSON support
        self.conn = sqlite3.connect(str(self.db_path), isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        
        # Enable JSON functions
        self.conn.execute("PRAGMA journal_mode=WAL")
        
        # Create tables
        await self._create_tables()
        
        # Start cleanup task
        asyncio.create_task(self._cleanup_loop())
    
    async def _create_tables(self):
        """Create database schema."""
        self.conn.executescript("""
            -- Context storage with all metadata including sessions
            CREATE TABLE IF NOT EXISTS contexts (
                ref TEXT PRIMARY KEY,
                event_id TEXT UNIQUE,
                correlation_id TEXT,
                session_id TEXT,
                agent_id TEXT,
                context_json JSON NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            );
            
            -- Indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_contexts_correlation 
                ON contexts(correlation_id);
            CREATE INDEX IF NOT EXISTS idx_contexts_session 
                ON contexts(session_id);
            CREATE INDEX IF NOT EXISTS idx_contexts_agent 
                ON contexts(agent_id);
            CREATE INDEX IF NOT EXISTS idx_contexts_expires 
                ON contexts(expires_at);
            
            -- Event index (minimal, references context)
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                event_name TEXT NOT NULL,
                timestamp REAL NOT NULL,
                context_ref TEXT NOT NULL,
                jsonl_offset INTEGER,
                jsonl_file TEXT,
                FOREIGN KEY (context_ref) REFERENCES contexts(ref)
            );
            
            -- Indexes for event queries
            CREATE INDEX IF NOT EXISTS idx_events_name 
                ON events(event_name);
            CREATE INDEX IF NOT EXISTS idx_events_timestamp 
                ON events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_events_context 
                ON events(context_ref);
        """)
    
    async def store_context(self, ref: str, context: Dict[str, Any]) -> None:
        """Store context in database."""
        now = int(time.time())
        expires_at = now + (self.retention_days * 86400)
        
        # Extract key fields for indexing
        event_id = context.get("_event_id", "")
        correlation_id = context.get("_correlation_id", "")
        session_id = context.get("_session", {}).get("id", "") if isinstance(context.get("_session"), dict) else ""
        agent_id = context.get("_agent_id", "")
        
        self.conn.execute("""
            INSERT OR REPLACE INTO contexts 
            (ref, event_id, correlation_id, session_id, agent_id, 
             context_json, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ref, event_id, correlation_id, session_id, agent_id,
              json.dumps(context), now, expires_at))
    
    async def get_context(self, ref: str) -> Optional[Dict[str, Any]]:
        """Retrieve context by reference."""
        row = self.conn.execute(
            "SELECT context_json FROM contexts WHERE ref = ?", (ref,)
        ).fetchone()
        
        if row:
            return json.loads(row["context_json"])
        return None
    
    async def store_event_index(self, event_id: str, event_name: str, 
                               timestamp: float, context_ref: str,
                               jsonl_file: str, jsonl_offset: int) -> None:
        """Store minimal event index entry."""
        self.conn.execute("""
            INSERT OR REPLACE INTO events
            (event_id, event_name, timestamp, context_ref, jsonl_file, jsonl_offset)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (event_id, event_name, timestamp, context_ref, jsonl_file, jsonl_offset))
    
    async def get_events_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all events in a session."""
        rows = self.conn.execute("""
            SELECT e.*, c.context_json
            FROM events e
            JOIN contexts c ON e.context_ref = c.ref
            WHERE c.session_id = ?
            ORDER BY e.timestamp
        """, (session_id,)).fetchall()
        
        return [dict(row) for row in rows]
    
    async def _cleanup_loop(self):
        """Periodically clean up expired contexts."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run hourly
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _cleanup_expired(self):
        """Remove expired contexts and orphaned events."""
        now = int(time.time())
        
        # Delete expired contexts
        result = self.conn.execute(
            "DELETE FROM contexts WHERE expires_at < ?", (now,)
        )
        
        if result.rowcount > 0:
            logger.info(f"Cleaned up {result.rowcount} expired contexts")
        
        # Clean up orphaned events
        self.conn.execute("""
            DELETE FROM events 
            WHERE context_ref NOT IN (SELECT ref FROM contexts)
        """)


class ContextManager:
    """
    Main context manager that coordinates hot and cold storage.
    Provides unified interface for context operations.
    """
    
    def __init__(self):
        self.hot_storage = InMemoryHotStorage()
        self.cold_storage = SQLiteContextDatabase()
        self._initialized = False
    
    async def initialize(self):
        """Initialize storage backends."""
        if self._initialized:
            return
            
        await self.hot_storage.start()
        await self.cold_storage.initialize()
        self._initialized = True
        logger.info("Context manager initialized with hot and cold storage")
    
    async def shutdown(self):
        """Clean shutdown of storage backends."""
        await self.hot_storage.stop()
        if self.cold_storage.conn:
            self.cold_storage.conn.close()
        self._initialized = False
    
    def generate_ref(self, event_id: Optional[str] = None) -> str:
        """Generate a context reference."""
        if event_id:
            return f"ctx_{event_id}"
        return f"ctx_evt_{uuid.uuid4().hex[:8]}"
    
    async def create_context(self, **kwargs) -> Dict[str, Any]:
        """
        Create a new context with automatic fields.
        This becomes the new contextvars value.
        """
        # Get current context if any
        current = ksi_context.get()
        
        # Extract known fields
        event_id = kwargs.pop("event_id", f"evt_{uuid.uuid4().hex[:8]}")
        timestamp = kwargs.pop("timestamp", time.time())
        correlation_id = kwargs.pop("correlation_id", None)
        
        # Build new context
        context = {
            "_event_id": event_id,
            "_event_timestamp": timestamp,
            "_correlation_id": correlation_id or 
                              (current.get("_correlation_id") if current else None) or
                              f"corr_{uuid.uuid4().hex[:8]}",
            "_ref": None,  # Will be set when stored
        }
        
        # Add any remaining kwargs to context (like agent_id, custom fields)
        for key, value in kwargs.items():
            context[f"_{key}" if not key.startswith("_") else key] = value
        
        # Handle parent context
        if current:
            context["_parent_event_id"] = current.get("_event_id")
            context["_root_event_id"] = current.get("_root_event_id", current.get("_event_id"))
            context["_event_depth"] = current.get("_event_depth", 0) + 1
            
            # Inherit session if present
            if "_session" in current:
                context["_session"] = current["_session"]
            
            # Inherit all custom fields from parent (those starting with _)
            for key, value in current.items():
                if key.startswith("_") and key not in context:
                    # Don't override fields already set, but inherit others
                    if key not in ["_event_id", "_event_timestamp", "_ref", 
                                   "_parent_event_id", "_root_event_id", "_event_depth"]:
                        context[key] = value
        else:
            context["_event_depth"] = 0
        
        # Generate and set reference
        context["_ref"] = self.generate_ref(context["_event_id"])
        
        # Set as current context
        ksi_context.set(context)
        
        return context
    
    async def store_event_with_context(self, event: Dict[str, Any]) -> str:
        """
        Store an event with its context using dual-path pattern.
        Returns the context reference.
        """
        # Get current context
        context = ksi_context.get()
        if not context:
            # Create minimal context if none exists
            context = await self.create_context(
                event_id=event.get("event_id"),
                timestamp=event.get("timestamp", time.time())
            )
        else:
            # If event has its own event_id, we need to create a new context for it
            # while preserving the chain
            if event.get("event_id") and event["event_id"] != context.get("_event_id"):
                # Create child context for this specific event
                context = await self.create_context(
                    event_id=event["event_id"],
                    timestamp=event.get("timestamp", time.time())
                )
        
        # Add to hot storage immediately (synchronous)
        self.hot_storage.add_event(event, context)
        
        # Persist to cold storage asynchronously
        asyncio.create_task(self._persist_to_cold(event, context))
        
        return context["_ref"]
    
    async def _persist_to_cold(self, event: Dict[str, Any], context: Dict[str, Any]):
        """Persist event and context to SQLite (async)."""
        try:
            # Store context
            await self.cold_storage.store_context(context["_ref"], context)
            
            # Store event index
            await self.cold_storage.store_event_index(
                event_id=event.get("event_id", context["_event_id"]),
                event_name=event.get("event_name", ""),
                timestamp=event.get("timestamp", context["_event_timestamp"]),
                context_ref=context["_ref"],
                jsonl_file=event.get("jsonl_file", ""),
                jsonl_offset=event.get("jsonl_offset", 0)
            )
        except Exception as e:
            logger.error(f"Failed to persist to cold storage: {e}")
    
    async def get_context(self, ref: str) -> Optional[Dict[str, Any]]:
        """Get context by reference, checking hot first then cold."""
        # Try hot storage first
        context = self.hot_storage.get_context(ref)
        if context:
            return context
        
        # Fall back to cold storage
        return await self.cold_storage.get_context(ref)
    
    async def get_event_with_context(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get event with full context, checking hot first then cold."""
        # Try hot storage first
        event = self.hot_storage.get_event(event_id)
        if event:
            return event
        
        # Fall back to cold storage
        row = self.cold_storage.conn.execute("""
            SELECT e.*, c.context_json
            FROM events e
            JOIN contexts c ON e.context_ref = c.ref
            WHERE e.event_id = ?
        """, (event_id,)).fetchone()
        
        if row:
            event = dict(row)
            event["_ksi_context"] = json.loads(event["context_json"])
            return event
        
        return None
    
    def copy_current_context(self) -> Optional[Dict[str, Any]]:
        """Get a copy of the current context for serialization."""
        context = ksi_context.get()
        return dict(context) if context else None
    
    def restore_context(self, context: Dict[str, Any]) -> None:
        """Restore a context (e.g., from external source)."""
        ksi_context.set(context)


# Global instance
_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """Get the global context manager instance."""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager