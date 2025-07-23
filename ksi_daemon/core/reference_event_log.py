#!/usr/bin/env python3
"""
Reference-Based Event Log

Implements file-based event logging with selective payload references.
Events are written to JSONL files for tailing/monitoring, with large
payloads stored separately and referenced.
"""

import json
import time
import asyncio
import aiosqlite
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

from ksi_common.logging import get_bound_logger
from ksi_common.config import config
from ksi_common.timestamps import timestamp_utc

logger = get_bound_logger("reference_event_log")


@dataclass
class ReferenceEventLogEntry:
    """Event log entry with reference support."""
    timestamp: float
    event_name: str
    event_type: Optional[str]
    originator_id: Optional[str]  # Using correct terminology
    construct_id: Optional[str]
    correlation_id: Optional[str]
    event_id: Optional[str]
    parent_event_id: Optional[str]  # Parent in event chain
    root_event_id: Optional[str]    # Original event that started chain
    event_depth: Optional[int]       # Depth in event chain
    request_id: Optional[str]
    session_id: Optional[str]
    status: Optional[str]
    model: Optional[str]
    purpose: Optional[str]
    data: Dict[str, Any]
    payload_refs: Dict[str, str]  # field_name -> file_path for referenced payloads


class ReferenceEventLog:
    """
    File-based event log with selective payload references.
    
    Architecture:
    - Events written to daily JSONL files for tailing
    - Large payloads replaced with file references
    - SQLite metadata index for fast queries
    - No in-memory state for live observation
    """
    
    # Fields that should be referenced, not stored inline
    REFERENCEABLE_FIELDS = {
        "response",           # Completion responses
        "content",           # File contents
        "prompt",            # Large prompts
        "messages",          # Chat histories
        "system_prompt",     # Agent system prompts
        "profile",           # Agent profiles
        "composition",       # Composition definitions
        "pattern",           # Orchestration patterns
        "events",            # Arrays of events (from queries)
        "arguments",         # MCP tool arguments
        "result",            # MCP tool results
    }
    
    def __init__(self):
        self.db_path = config.event_db_path
        self.events_dir = config.event_log_dir
        self.reference_threshold = config.event_reference_threshold
        self.daily_file_name = config.event_daily_file_name
        self.current_file = None
        self.current_date = None
        self.file_lock = asyncio.Lock()
        self.db_initialized = False
        
    async def initialize(self):
        """Initialize the event log system."""
        # Ensure directories exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize SQLite metadata index
        await self._init_database()
        
        logger.info(f"Reference event log initialized: db={self.db_path}, events={self.events_dir}")
    
    async def _init_database(self):
        """Initialize SQLite metadata index."""
        async with aiosqlite.connect(str(self.db_path)) as conn:
            # Enable WAL mode for better concurrency
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")
            
            # Create metadata table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS events_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    event_name TEXT NOT NULL,
                    event_type TEXT,
                    originator_id TEXT,
                    construct_id TEXT,
                    correlation_id TEXT,
                    event_id TEXT,
                    parent_event_id TEXT,
                    root_event_id TEXT,
                    event_depth INTEGER,
                    request_id TEXT,
                    session_id TEXT,
                    status TEXT,
                    model TEXT,
                    purpose TEXT,
                    file_path TEXT NOT NULL,
                    file_offset INTEGER,
                    payload_refs TEXT,  -- JSON dict of references
                    created_at REAL DEFAULT (strftime('%s', 'now'))
                )
            """)
            
            # Create indexes for common queries
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_em_timestamp ON events_metadata(timestamp DESC)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_em_event_name ON events_metadata(event_name)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_em_originator ON events_metadata(originator_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_em_construct ON events_metadata(construct_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_em_session ON events_metadata(session_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_em_correlation ON events_metadata(correlation_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_em_status ON events_metadata(status)")
            
            # Migration: Add new genealogy columns if they don't exist
            # Check if columns exist by querying table info
            cursor = await conn.execute("PRAGMA table_info(events_metadata)")
            columns = await cursor.fetchall()
            column_names = {col[1] for col in columns}
            
            # Add missing columns
            if "parent_event_id" not in column_names:
                logger.info("Adding parent_event_id column to events_metadata")
                await conn.execute("ALTER TABLE events_metadata ADD COLUMN parent_event_id TEXT")
            
            if "root_event_id" not in column_names:
                logger.info("Adding root_event_id column to events_metadata")
                await conn.execute("ALTER TABLE events_metadata ADD COLUMN root_event_id TEXT")
            
            if "event_depth" not in column_names:
                logger.info("Adding event_depth column to events_metadata")
                await conn.execute("ALTER TABLE events_metadata ADD COLUMN event_depth INTEGER")
            
            # Create indexes for new columns
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_em_parent_event ON events_metadata(parent_event_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_em_root_event ON events_metadata(root_event_id)")
            
            await conn.commit()
            
        self.db_initialized = True
    
    async def log_event(self, event_name: str, data: Dict[str, Any],
                       originator_id: Optional[str] = None,
                       construct_id: Optional[str] = None,
                       correlation_id: Optional[str] = None,
                       event_id: Optional[str] = None,
                       parent_event_id: Optional[str] = None,
                       root_event_id: Optional[str] = None,
                       event_depth: Optional[int] = None) -> None:
        """
        Log an event with selective payload references.
        
        Large payloads are replaced with file references.
        The full event (minus referenced payloads) is written to JSONL.
        Metadata is indexed in SQLite for fast queries.
        """
        timestamp = time.time()
        
        # Extract metadata fields
        event_type = event_name.split(":")[0] if ":" in event_name else None
        request_id = data.get("request_id")
        session_id = data.get("session_id")
        status = data.get("status")
        model = data.get("model")
        purpose = data.get("purpose")
        
        # Process data to extract references
        processed_data, payload_refs = await self._process_payload(event_name, data)
        
        # Create log entry
        entry = ReferenceEventLogEntry(
            timestamp=timestamp,
            event_name=event_name,
            event_type=event_type,
            originator_id=originator_id,
            construct_id=construct_id,
            correlation_id=correlation_id,
            event_id=event_id,
            parent_event_id=parent_event_id,
            root_event_id=root_event_id,
            event_depth=event_depth,
            request_id=request_id,
            session_id=session_id,
            status=status,
            model=model,
            purpose=purpose,
            data=processed_data,
            payload_refs=payload_refs
        )
        
        # Write to JSONL file
        file_path, file_offset = await self._write_to_file(entry)
        
        # Index in SQLite
        await self._index_event(entry, file_path, file_offset)
    
    async def _process_payload(self, event_name: str, data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """
        Process event payload to extract references for large fields.
        
        Returns:
            Tuple of (processed_data, payload_refs)
        """
        processed = {}
        refs = {}
        
        for key, value in data.items():
            # Check if this field should be referenced
            if key in self.REFERENCEABLE_FIELDS and self._should_reference(value):
                # Check if it's already a reference (e.g., completion responses)
                if event_name == "completion:response" and key == "response" and isinstance(data.get("session_id"), str):
                    # Reference existing response file
                    refs[key] = str(config.response_log_dir / f"{data['session_id']}.jsonl")
                    processed[key] = f"<ref:{refs[key]}>"
                else:
                    # Would create new reference file (future implementation)
                    processed[key] = f"<stripped:{len(str(value))} chars>"
            else:
                # Keep inline
                processed[key] = value
        
        return processed, refs
    
    def _should_reference(self, value: Any) -> bool:
        """Check if a value should be stored as reference."""
        if value is None:
            return False
        
        # Check size threshold
        try:
            size = len(json.dumps(value))
            return size > self.reference_threshold
        except (TypeError, ValueError) as e:
            logger.debug(f"Error serializing value for size check: {e}")
            return False
    
    async def _write_to_file(self, entry: ReferenceEventLogEntry) -> Tuple[Path, int]:
        """Write event to daily JSONL file."""
        async with self.file_lock:
            # Get current date and file
            today = datetime.fromtimestamp(entry.timestamp).strftime("%Y-%m-%d")
            
            # Create date directory if needed
            date_dir = self.events_dir / today
            date_dir.mkdir(exist_ok=True)
            
            # File path
            file_path = date_dir / self.daily_file_name
            
            # BREAKING CHANGE: Only write essential fields, metadata goes in _ksi_context
            # Build the event dict with _ksi_context properly embedded in data
            entry_dict = {
                "timestamp": entry.timestamp,
                "event_name": entry.event_name,
                "data": entry.data  # This already contains _ksi_context from event_system.py
            }
            
            # Sanitize data to ensure JSON serializable
            def make_json_serializable(obj, depth=0, visited=None):
                """Convert non-serializable objects to strings."""
                if visited is None:
                    visited = set()
                
                # Prevent infinite recursion
                if depth > 10:
                    return "<max depth exceeded>"
                
                # Check for circular references
                obj_id = id(obj)
                if obj_id in visited:
                    return "<circular reference>"
                
                # Handle basic types
                if obj is None or isinstance(obj, (str, int, float, bool)):
                    return obj
                
                # Mark this object as visited
                visited.add(obj_id)
                
                try:
                    if callable(obj):
                        return f"<callable: {obj.__name__ if hasattr(obj, '__name__') else str(obj)}>"
                    elif isinstance(obj, dict):
                        return {str(k): make_json_serializable(v, depth+1, visited) for k, v in obj.items()}
                    elif hasattr(obj, '__dict__'):
                        return {str(k): make_json_serializable(v, depth+1, visited) for k, v in obj.__dict__.items()}
                    elif isinstance(obj, (list, tuple)):
                        return [make_json_serializable(item, depth+1, visited) for item in obj]
                    else:
                        # Try to convert to string as last resort
                        try:
                            return str(obj)
                        except:
                            return "<non-serializable>"
                finally:
                    # Remove from visited to allow the same object at different paths
                    visited.discard(obj_id)
            
            # Apply sanitization to data field
            if 'data' in entry_dict:
                entry_dict['data'] = make_json_serializable(entry_dict['data'])
            
            # Get file position before write
            file_offset = file_path.stat().st_size if file_path.exists() else 0
            
            # Append to file (using sync IO in executor for simplicity)
            def write_line():
                with open(file_path, 'a') as f:
                    f.write(json.dumps(entry_dict) + '\n')
            
            await asyncio.get_event_loop().run_in_executor(None, write_line)
            
            return file_path, file_offset
    
    async def _index_event(self, entry: ReferenceEventLogEntry, file_path: Path, file_offset: int):
        """Index event metadata in SQLite."""
        if not self.db_initialized:
            return
        
        async with aiosqlite.connect(str(self.db_path)) as conn:
            await conn.execute("""
                INSERT INTO events_metadata (
                    timestamp, event_name, event_type,
                    originator_id, construct_id, correlation_id,
                    event_id, parent_event_id, root_event_id, event_depth,
                    request_id, session_id,
                    status, model, purpose,
                    file_path, file_offset, payload_refs
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.timestamp, entry.event_name, entry.event_type,
                entry.originator_id, entry.construct_id, entry.correlation_id,
                entry.event_id, entry.parent_event_id, entry.root_event_id, entry.event_depth,
                entry.request_id, entry.session_id,
                entry.status, entry.model, entry.purpose,
                str(file_path), file_offset, json.dumps(entry.payload_refs)
            ))
            await conn.commit()
    
    async def query_metadata(self, 
                           event_patterns: Optional[List[str]] = None,
                           originator_id: Optional[str] = None,
                           start_time: Optional[float] = None,
                           end_time: Optional[float] = None,
                           limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Query event metadata from SQLite index."""
        if not self.db_initialized:
            return []
        
        # Build query
        conditions = []
        params = []
        
        if originator_id:
            conditions.append("originator_id = ?")
            params.append(originator_id)
        
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)
        
        # Event pattern matching using LIKE
        if event_patterns:
            pattern_conditions = []
            for pattern in event_patterns:
                # Convert wildcard to SQL LIKE pattern
                sql_pattern = pattern.replace('*', '%')
                pattern_conditions.append("event_name LIKE ?")
                params.append(sql_pattern)
            
            if pattern_conditions:
                conditions.append(f"({' OR '.join(pattern_conditions)})")
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        limit_clause = f"LIMIT {limit}" if limit else ""
        
        query = f"""
            SELECT timestamp, event_name, event_type,
                   originator_id, construct_id, correlation_id,
                   event_id, request_id, session_id,
                   status, model, purpose,
                   file_path, file_offset, payload_refs
            FROM events_metadata
            {where_clause}
            ORDER BY timestamp DESC
            {limit_clause}
        """
        
        async with aiosqlite.connect(str(self.db_path)) as conn:
            async with conn.execute(query, params) as cursor:
                results = []
                async for row in cursor:
                    results.append({
                        "timestamp": row[0],
                        "event_name": row[1],
                        "event_type": row[2],
                        "originator_id": row[3],
                        "construct_id": row[4],
                        "correlation_id": row[5],
                        "event_id": row[6],
                        "request_id": row[7],
                        "session_id": row[8],
                        "status": row[9],
                        "model": row[10],
                        "purpose": row[11],
                        "file_path": row[12],
                        "file_offset": row[13],
                        "payload_refs": json.loads(row[14]) if row[14] else {}
                    })
                return results
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the event log."""
        if not self.db_initialized:
            return {"error": "Database not initialized"}
        
        stats = {
            "database": {
                "path": str(self.db_path),
                "exists": self.db_path.exists()
            },
            "storage": {
                "events_dir": str(self.events_dir),
                "total_events": 0,
                "file_count": 0,
                "total_size_bytes": 0
            },
            "events": {
                "by_type": {},
                "by_date": {},
                "recent_activity": []
            },
            "performance": {
                "avg_payload_size": 0,
                "referenced_payloads": 0,
                "inline_payloads": 0
            }
        }
        
        try:
            async with aiosqlite.connect(str(self.db_path)) as conn:
                # Total events count
                async with conn.execute("SELECT COUNT(*) FROM events_metadata") as cursor:
                    row = await cursor.fetchone()
                    stats["storage"]["total_events"] = row[0] if row else 0
                
                # Events by type/name
                async with conn.execute("""
                    SELECT event_name, COUNT(*) as count 
                    FROM events_metadata 
                    GROUP BY event_name 
                    ORDER BY count DESC 
                    LIMIT 20
                """) as cursor:
                    async for row in cursor:
                        stats["events"]["by_type"][row[0]] = row[1]
                
                # Events by date (last 7 days)
                async with conn.execute("""
                    SELECT DATE(datetime(timestamp, 'unixepoch')) as date, COUNT(*) as count
                    FROM events_metadata 
                    WHERE timestamp >= ? 
                    GROUP BY date 
                    ORDER BY date DESC
                """, (time.time() - 7*24*3600,)) as cursor:
                    async for row in cursor:
                        stats["events"]["by_date"][row[0]] = row[1]
                
                # Recent activity (last 10 events)
                async with conn.execute("""
                    SELECT timestamp, event_name, originator_id
                    FROM events_metadata 
                    ORDER BY timestamp DESC 
                    LIMIT 10
                """) as cursor:
                    async for row in cursor:
                        stats["events"]["recent_activity"].append({
                            "timestamp": row[0],
                            "event_name": row[1],
                            "originator_id": row[2]
                        })
                
                # Performance metrics
                async with conn.execute("""
                    SELECT 
                        COUNT(CASE WHEN payload_refs != '{}' AND payload_refs IS NOT NULL THEN 1 END) as referenced,
                        COUNT(CASE WHEN payload_refs = '{}' OR payload_refs IS NULL THEN 1 END) as inline
                    FROM events_metadata
                """) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        stats["performance"]["referenced_payloads"] = row[0]
                        stats["performance"]["inline_payloads"] = row[1]
            
            # File system statistics
            if self.events_dir.exists():
                total_size = 0
                file_count = 0
                for file_path in self.events_dir.rglob("*.jsonl"):
                    file_count += 1
                    total_size += file_path.stat().st_size
                
                stats["storage"]["file_count"] = file_count
                stats["storage"]["total_size_bytes"] = total_size
                
                if stats["storage"]["total_events"] > 0:
                    stats["performance"]["avg_payload_size"] = total_size // stats["storage"]["total_events"]
        
        except Exception as e:
            stats["error"] = f"Failed to collect statistics: {e}"
        
        return stats