#!/usr/bin/env python3
"""
Daemon Event Log - Pull-based monitoring system

High-performance event logging for monitoring without broadcast overhead.
Uses ring buffer for memory efficiency with optional persistence.
"""

import time
import json
from typing import Dict, Any, List, Optional, Union
from collections import deque
from dataclasses import dataclass, asdict
from pathlib import Path
import fnmatch

from ksi_common import TimestampManager, get_logger

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
        # TODO: Implement file persistence with rotation
        # This would allow long-term audit trails
        pass