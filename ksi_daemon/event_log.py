#!/usr/bin/env python3
"""
Daemon Event Log - Pull-based monitoring system

High-performance event logging for monitoring without broadcast overhead.
Uses ring buffer for memory efficiency with optional persistence.
"""

import time
import json
import asyncio
import sqlite3
from typing import Dict, Any, List, Optional, Union, Set, Callable
from collections import deque
from dataclasses import dataclass, asdict, field
from pathlib import Path
import fnmatch
from contextlib import contextmanager

from ksi_common import TimestampManager, get_logger
from ksi_common.config import config

logger = get_logger(__name__)


@dataclass
class EventLogEntry:
    """Single event log entry with standardized fields."""
    timestamp: float
    event_name: str
    data: Dict[str, Any]
    client_id: Optional[str] = None
    correlation_id: Optional[str] = None
    event_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def matches_filter(self, event_patterns: List[str] = None, 
                      client_id: Optional[str] = None,
                      since: Optional[float] = None,
                      until: Optional[float] = None) -> bool:
        """Check if entry matches filter criteria."""
        # Time range filter
        if since and self.timestamp < since:
            return False
        if until and self.timestamp > until:
            return False
            
        # Client filter
        if client_id and self.client_id != client_id:
            return False
            
        # Event pattern filter
        if event_patterns:
            matches = False
            for pattern in event_patterns:
                if fnmatch.fnmatch(self.event_name, pattern):
                    matches = True
                    break
            if not matches:
                return False
                
        return True


class DaemonEventLog:
    """
    High-performance event log for daemon monitoring.
    
    Uses ring buffer for memory efficiency with optional persistence.
    Designed for pull-based monitoring without broadcast overhead.
    """
    
    def __init__(self, max_size: int = 10000, persist_to_file: Optional[Path] = None):
        """
        Initialize event log.
        
        Args:
            max_size: Maximum entries in ring buffer
            persist_to_file: Optional file for persistence (not implemented yet)
        """
        self.max_size = max_size
        self.persist_to_file = persist_to_file
        
        # Ring buffer for efficient memory usage
        self.events: deque[EventLogEntry] = deque(maxlen=max_size)
        
        # Statistics
        self.stats = {
            "total_events": 0,
            "events_dropped": 0,
            "log_started": time.time()
        }
        
        logger.info(f"EventLog initialized with max_size={max_size}")
    
    def log_event(self, event_name: str, data: Dict[str, Any], 
                  client_id: Optional[str] = None,
                  correlation_id: Optional[str] = None,
                  event_id: Optional[str] = None) -> None:
        """
        Log an event with minimal overhead.
        
        Args:
            event_name: Name of the event (e.g., "completion:request")
            data: Event data dictionary
            client_id: Client that triggered the event
            correlation_id: Request correlation ID
            event_id: Unique event identifier
        """
        try:
            # Check if we'll drop an event (ring buffer is full)
            if len(self.events) >= self.max_size:
                self.stats["events_dropped"] += 1
            
            # Create entry
            entry = EventLogEntry(
                timestamp=time.time(),
                event_name=event_name,
                data=data,
                client_id=client_id,
                correlation_id=correlation_id,
                event_id=event_id
            )
            
            # Add to ring buffer (automatically drops oldest if full)
            self.events.append(entry)
            self.stats["total_events"] += 1
            
            # Optional: Persist to file (future enhancement)
            if self.persist_to_file:
                self._persist_entry(entry)
                
        except Exception as e:
            logger.error(f"Failed to log event {event_name}: {e}")
    
    def get_events(self, event_patterns: List[str] = None,
                   client_id: Optional[str] = None,
                   since: Optional[Union[str, float]] = None,
                   until: Optional[Union[str, float]] = None,
                   limit: Optional[int] = None,
                   reverse: bool = True) -> List[Dict[str, Any]]:
        """
        Query events with filtering and pagination.
        
        Args:
            event_patterns: List of event name patterns (supports wildcards)
            client_id: Filter by specific client
            since: Start time (ISO string or timestamp)
            until: End time (ISO string or timestamp)
            limit: Maximum number of events to return
            reverse: Return newest first (default True)
            
        Returns:
            List of matching event dictionaries
        """
        try:
            # Convert time strings to timestamps
            since_ts = self._parse_time(since) if since else None
            until_ts = self._parse_time(until) if until else None
            
            # Filter events
            matching_events = []
            for entry in self.events:
                if entry.matches_filter(event_patterns, client_id, since_ts, until_ts):
                    matching_events.append(entry.to_dict())
            
            # Sort by timestamp
            matching_events.sort(key=lambda e: e['timestamp'], reverse=reverse)
            
            # Apply limit
            if limit:
                matching_events = matching_events[:limit]
            
            return matching_events
            
        except Exception as e:
            logger.error(f"Failed to query events: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event log statistics."""
        current_time = time.time()
        uptime = current_time - self.stats["log_started"]
        
        return {
            "total_events": self.stats["total_events"],
            "events_dropped": self.stats["events_dropped"],
            "current_size": len(self.events),
            "max_size": self.max_size,
            "uptime_seconds": uptime,
            "events_per_second": self.stats["total_events"] / uptime if uptime > 0 else 0,
            "oldest_event": self.events[0].timestamp if self.events else None,
            "newest_event": self.events[-1].timestamp if self.events else None
        }
    
    def clear(self) -> None:
        """Clear all events from the log."""
        self.events.clear()
        logger.info("Event log cleared")
    
    def _parse_time(self, time_input: Union[str, float]) -> float:
        """Parse time input to timestamp."""
        if isinstance(time_input, (int, float)):
            return float(time_input)
        
        # Try to parse ISO timestamp
        try:
            dt = TimestampManager.parse_iso_timestamp(time_input)
            return dt.timestamp()
        except Exception:
            # Fallback: treat as relative time (e.g., "10m" for 10 minutes ago)
            # For now, just return current time
            logger.warning(f"Could not parse time: {time_input}")
            return time.time()
    
    def _persist_entry(self, entry: EventLogEntry) -> None:
        """Persist entry to file (future enhancement)."""
        # File persistence with rotation not yet implemented
        # This would allow long-term audit trails
        pass


@dataclass
class EventSubscriber:
    """Tracks a real-time event subscription."""
    client_id: str
    patterns: List[str]
    writer: asyncio.StreamWriter
    active: bool = True
    filter_fn: Optional[Callable] = None


class AsyncSQLiteEventLog(DaemonEventLog):
    """
    Event log with async SQLite persistence and real-time streaming.
    
    Combines in-memory ring buffer with durable SQLite storage.
    Supports real-time event streaming to subscribers.
    """
    
    def __init__(self, max_size: int = 10000, db_path: Optional[Path] = None):
        """
        Initialize async event log with SQLite persistence.
        
        Args:
            max_size: Maximum entries in ring buffer
            db_path: Path to SQLite database (uses config default if None)
        """
        super().__init__(max_size)
        
        self.db_path = db_path or config.event_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Async write infrastructure
        self.write_queue: asyncio.Queue = asyncio.Queue(maxsize=config.event_write_queue_size)
        self.writer_task: Optional[asyncio.Task] = None
        
        # Real-time subscribers
        self.subscribers: Dict[str, EventSubscriber] = {}
        
        # SQLite connection (created in start())
        self.conn: Optional[sqlite3.Connection] = None
        
        logger.info(f"AsyncSQLiteEventLog initialized with db={self.db_path}")
    
    async def start(self) -> None:
        """Start async writer task and initialize database."""
        # Initialize SQLite with WAL mode for better concurrency
        self._init_database()
        
        # Start background writer
        self.writer_task = asyncio.create_task(self._async_writer())
        
        # Optional recovery from database
        if config.event_recovery:
            await self._recover_from_db()
        
        logger.info("AsyncSQLiteEventLog started")
    
    async def stop(self) -> None:
        """Stop async writer and close database."""
        if self.writer_task:
            self.writer_task.cancel()
            try:
                await self.writer_task
            except asyncio.CancelledError:
                pass
        
        if self.conn:
            self.conn.close()
        
        logger.info("AsyncSQLiteEventLog stopped")
    
    def _init_database(self) -> None:
        """Initialize SQLite database with schema."""
        self.conn = sqlite3.connect(str(self.db_path))
        
        # Enable WAL mode for better concurrency
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        
        # Create events table with extracted fields for indexing
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                event_name TEXT NOT NULL,
                event_type TEXT,
                client_id TEXT,
                session_id TEXT,
                correlation_id TEXT,
                event_id TEXT,
                data TEXT NOT NULL,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        
        # Create indexes for common queries
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON events(timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_event_name ON events(event_name)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON events(session_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_correlation_id ON events(correlation_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_client_id ON events(client_id)")
        
        self.conn.commit()
    
    def log_event(self, event_name: str, data: Dict[str, Any], 
                  client_id: Optional[str] = None,
                  correlation_id: Optional[str] = None,
                  event_id: Optional[str] = None) -> None:
        """
        Log event to memory and queue for async disk write.
        
        Non-blocking: adds to ring buffer and write queue without waiting.
        """
        # Add to ring buffer (parent class, sync)
        super().log_event(event_name, data, client_id, correlation_id, event_id)
        
        # Get the entry we just added
        if self.events:
            entry = self.events[-1]
            
            # Queue for async write (non-blocking)
            try:
                self.write_queue.put_nowait(entry)
            except asyncio.QueueFull:
                logger.warning("Event write queue full, dropping disk write")
                self.stats["events_dropped"] += 1
            
            # Notify real-time subscribers
            self._notify_subscribers(entry)
    
    def subscribe(self, client_id: str, patterns: List[str], 
                  writer: asyncio.StreamWriter,
                  filter_fn: Optional[Callable] = None) -> EventSubscriber:
        """
        Subscribe to real-time event stream.
        
        Args:
            client_id: Unique subscriber identifier
            patterns: Event name patterns to match (supports wildcards)
            writer: Stream writer for sending events
            filter_fn: Optional additional filter function
            
        Returns:
            EventSubscriber instance
        """
        subscriber = EventSubscriber(client_id, patterns, writer, True, filter_fn)
        self.subscribers[client_id] = subscriber
        
        logger.info(f"Client {client_id} subscribed to patterns: {patterns}")
        return subscriber
    
    def unsubscribe(self, client_id: str) -> None:
        """Remove event subscription."""
        if client_id in self.subscribers:
            self.subscribers[client_id].active = False
            del self.subscribers[client_id]
            logger.info(f"Client {client_id} unsubscribed")
    
    def _notify_subscribers(self, entry: EventLogEntry) -> None:
        """
        Push event to all matching subscribers.
        
        Non-blocking: creates tasks for async delivery.
        """
        if not self.subscribers:
            return
        
        # Pre-serialize event once
        event_dict = entry.to_dict()
        event_json = json.dumps(event_dict) + '\n'
        
        # Notify matching subscribers
        for subscriber in list(self.subscribers.values()):
            if not subscriber.active:
                continue
            
            # Check if event matches patterns
            if self._matches_subscriber_patterns(entry.event_name, subscriber.patterns):
                # Apply additional filter if provided
                if subscriber.filter_fn and not subscriber.filter_fn(event_dict):
                    continue
                
                # Queue async send (non-blocking)
                asyncio.create_task(
                    self._send_to_subscriber(subscriber, event_json)
                )
    
    def _matches_subscriber_patterns(self, event_name: str, patterns: List[str]) -> bool:
        """Check if event name matches any subscription pattern."""
        for pattern in patterns:
            if fnmatch.fnmatch(event_name, pattern):
                return True
        return False
    
    async def _send_to_subscriber(self, subscriber: EventSubscriber, event_json: str) -> None:
        """Send event to subscriber asynchronously."""
        try:
            subscriber.writer.write(event_json.encode())
            await subscriber.writer.drain()
        except Exception as e:
            logger.debug(f"Failed to send event to {subscriber.client_id}: {e}")
            subscriber.active = False
            # Will be cleaned up later
    
    async def _async_writer(self) -> None:
        """Background task for writing events to SQLite."""
        batch = []
        
        while True:
            try:
                # Collect events for batch write
                deadline = asyncio.get_event_loop().time() + config.event_flush_interval
                
                while asyncio.get_event_loop().time() < deadline:
                    try:
                        timeout = max(0.001, deadline - asyncio.get_event_loop().time())
                        entry = await asyncio.wait_for(
                            self.write_queue.get(),
                            timeout=timeout
                        )
                        batch.append(entry)
                        
                        # Write immediately if batch is large
                        if len(batch) >= config.event_batch_size:
                            break
                    except asyncio.TimeoutError:
                        break
                
                # Write batch to database
                if batch:
                    await self._write_batch(batch)
                    batch = []
                
                # Clean up old events periodically
                if time.time() % 3600 < config.event_flush_interval:  # Hourly
                    await self._cleanup_old_events()
                    
            except asyncio.CancelledError:
                # Final flush on shutdown
                if batch:
                    await self._write_batch(batch)
                break
            except Exception as e:
                logger.error(f"Error in async writer: {e}")
                await asyncio.sleep(1)  # Brief pause on error
    
    async def _write_batch(self, batch: List[EventLogEntry]) -> None:
        """Write batch of events to SQLite."""
        if not self.conn:
            return
        
        try:
            # Prepare batch data
            rows = []
            for entry in batch:
                # Extract session_id from data if present
                session_id = entry.data.get("session_id")
                
                # Determine event type from name
                event_type = entry.event_name.split(":")[0] if ":" in entry.event_name else None
                
                rows.append((
                    entry.timestamp,
                    entry.event_name,
                    event_type,
                    entry.client_id,
                    session_id,
                    entry.correlation_id,
                    entry.event_id,
                    json.dumps(entry.data)
                ))
            
            # Batch insert
            self.conn.executemany("""
                INSERT INTO events 
                (timestamp, event_name, event_type, client_id, session_id, 
                 correlation_id, event_id, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            
            self.conn.commit()
            
            logger.debug(f"Wrote batch of {len(batch)} events to SQLite")
            
        except Exception as e:
            logger.error(f"Failed to write event batch: {e}")
    
    async def _recover_from_db(self) -> None:
        """Recover recent events from database into ring buffer."""
        if not self.conn:
            return
        
        try:
            # Load events from last hour
            since = time.time() - 3600
            
            cursor = self.conn.execute("""
                SELECT timestamp, event_name, client_id, correlation_id, 
                       event_id, data
                FROM events
                WHERE timestamp > ?
                ORDER BY timestamp
                LIMIT ?
            """, (since, self.max_size))
            
            count = 0
            for row in cursor:
                entry = EventLogEntry(
                    timestamp=row[0],
                    event_name=row[1],
                    data=json.loads(row[5]),
                    client_id=row[2],
                    correlation_id=row[3],
                    event_id=row[4]
                )
                self.events.append(entry)
                count += 1
            
            logger.info(f"Recovered {count} events from database")
            
        except Exception as e:
            logger.error(f"Failed to recover events: {e}")
    
    async def _cleanup_old_events(self) -> None:
        """Remove events older than retention period."""
        if not self.conn:
            return
        
        try:
            cutoff = time.time() - (config.event_retention_days * 86400)
            
            cursor = self.conn.execute(
                "DELETE FROM events WHERE timestamp < ?",
                (cutoff,)
            )
            
            if cursor.rowcount > 0:
                self.conn.commit()
                logger.info(f"Cleaned up {cursor.rowcount} old events")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old events: {e}")
    
    def query_db(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        Execute SQL query and return results.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of result dictionaries
        """
        if not self.conn:
            return []
        
        try:
            self.conn.row_factory = sqlite3.Row
            cursor = self.conn.execute(query, params)
            
            results = []
            for row in cursor:
                # Convert Row to dict
                result = dict(row)
                # Parse JSON data field if present
                if 'data' in result:
                    result['data'] = json.loads(result['data'])
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []
        finally:
            self.conn.row_factory = None