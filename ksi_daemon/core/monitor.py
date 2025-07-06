#!/usr/bin/env python3
"""
Monitor Plugin - Event-Based Version

Event log query API for pull-based monitoring.
Provides endpoints for querying the daemon event log without broadcast overhead.
Supports filtering, pagination, and statistics.
"""

from typing import Dict, Any, List, Optional
import json
import asyncio

from ksi_daemon.event_system import event_handler
from ksi_common.logging import get_bound_logger

# Module state
logger = get_bound_logger("monitor", version="1.0.0")
event_router = None  # Set during startup

# Plugin info
PLUGIN_INFO = {
    "name": "monitor",
    "version": "1.0.0",
    "description": "Event log query API for monitoring"
}


async def _load_event_from_file(file_path: str, file_offset: int) -> Optional[Dict[str, Any]]:
    """Load a single event from JSONL file at given offset."""
    try:
        def read_line():
            with open(file_path, 'r') as f:
                f.seek(file_offset)
                line = f.readline()
                if line:
                    return json.loads(line.strip())
            return None
        
        return await asyncio.get_event_loop().run_in_executor(None, read_line)
    except Exception as e:
        logger.error(f"Failed to load event from {file_path}:{file_offset} - {e}")
    return None


@event_handler("system:startup")
async def handle_startup(config: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize monitor module."""
    logger.debug("Monitor startup event received")
    logger.info("Monitor module started")
    return {"monitor_module": {"ready": True}}


@event_handler("system:context")
async def handle_context(context: Dict[str, Any]) -> None:
    """Receive module context with event router reference."""
    global event_router
    # Get router directly to avoid JSON serialization issues
    from ksi_daemon.event_system import get_router
    event_router = get_router()
    logger.info("Monitor module received event router context")


@event_handler("monitor:get_events")
async def handle_get_events(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query event log with filtering and pagination.
    
    Args:
        data: Query parameters:
            - event_patterns: List of event name patterns (supports wildcards)
            - originator_id: Filter by specific originator  
            - since: Start time (ISO string or timestamp)
            - until: End time (ISO string or timestamp)
            - limit: Maximum number of events to return
            - reverse: Return newest first (default True)
    
    Returns:
        Dictionary with events list and metadata
    """
    if not event_router or not hasattr(event_router, 'reference_event_log'):
        return {"error": "Reference event log not available"}
    
    try:
        # Extract query parameters
        event_patterns = data.get("event_patterns")
        originator_id = data.get("originator_id")
        since = data.get("since")
        until = data.get("until")
        limit = data.get("limit", 100)  # Default limit
        reverse = data.get("reverse", True)
        
        # Convert time strings to timestamps if needed
        if isinstance(since, str):
            from ksi_common.timestamps import parse_iso_timestamp
            since = parse_iso_timestamp(since).timestamp()
        if isinstance(until, str):
            from ksi_common.timestamps import parse_iso_timestamp
            until = parse_iso_timestamp(until).timestamp()
        
        # Query metadata from SQLite
        metadata_results = await event_router.reference_event_log.query_metadata(
            event_patterns=event_patterns,
            originator_id=originator_id,
            start_time=since,
            end_time=until,
            limit=limit
        )
        
        # Load full events from files
        events = []
        for meta in metadata_results:
            # Read event from JSONL file
            event = await _load_event_from_file(meta["file_path"], meta["file_offset"])
            if event:
                events.append(event)
        
        # TODO: Get stats from reference log
        total_events = len(metadata_results)
        
        return {
            "events": events,
            "count": len(events),
            "total_events": total_events,
            "query": {
                "event_patterns": event_patterns,
                "originator_id": originator_id,
                "since": since,
                "until": until,
                "limit": limit,
                "reverse": reverse
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to query events: {e}")
        return {"error": f"Query failed: {str(e)}"}


@event_handler("monitor:get_stats")
async def handle_get_stats(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get event log statistics.
    
    Returns:
        Dictionary with event log statistics
    """
    if not event_router or not hasattr(event_router, 'reference_event_log'):
        return {"error": "Reference event log not available"}
    
    try:
        # For reference-based event log, return basic info
        ref_log = event_router.reference_event_log
        
        # Add router stats
        router_stats = getattr(event_router, 'stats', {})
        
        return {
            "event_log": {
                "type": "reference_event_log",
                "db_path": str(ref_log.db_path),
                "events_dir": str(ref_log.events_dir),
                "message": "Detailed stats not available for file-based log"
            },
            "router": router_stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {"error": f"Stats failed: {str(e)}"}


@event_handler("monitor:clear_log")
async def handle_clear_log(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clear event log (admin operation).
    
    Returns:
        Confirmation of log clearing
    """
    return {
        "error": "Clear operation not supported for reference event log",
        "message": "File-based logs should be managed through log rotation"
    }


@event_handler("monitor:subscribe")
async def handle_subscribe(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Subscribe to real-time event stream.
    
    Note: In event system, context is passed through data
    
    Args:
        data: Subscription parameters:
            - event_patterns: List of event name patterns (supports wildcards)
            - filter_fn: Optional additional filter function
            - originator_id: Originator identifier
            - writer: Transport writer reference
    
    Returns:
        Subscription confirmation
    """
    return {
        "error": "Real-time subscription not yet implemented for reference event log",
        "message": "Use polling with monitor:get_events or implement file tailing"
    }


@event_handler("monitor:unsubscribe")
async def handle_unsubscribe(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Unsubscribe from event stream.
    
    Args:
        data: Unsubscribe parameters:
            - originator_id: Originator identifier
    
    Returns:
        Unsubscribe confirmation
    """
    return {
        "error": "Subscription not implemented for reference event log",
        "message": "No active subscriptions to unsubscribe from"
    }


@event_handler("monitor:query")
async def handle_query(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute custom SQL query against event database.
    
    Args:
        data: Query parameters:
            - query: SQL query string
            - params: Optional query parameters (tuple)
            - limit: Maximum results (default 1000)
    
    Returns:
        Query results with metadata
    """
    return {
        "error": "Direct SQL queries not supported for reference event log",
        "message": "Use monitor:get_events with filters instead"
    }


@event_handler("monitor:get_session_events")
async def handle_get_session_events(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get all events for a specific session.
    
    Args:
        data: Query parameters:
            - session_id: Session ID to query
            - include_memory: Include events from memory buffer (default True)
            - reverse: Sort newest first (default True)
    
    Returns:
        Events for the session
    """
    if not event_router or not hasattr(event_router, 'reference_event_log'):
        return {"error": "Reference event log not available"}
    
    session_id = data.get("session_id")
    if not session_id:
        return {"error": "No session_id provided"}
    
    reverse = data.get("reverse", True)
    
    try:
        # Query all events and filter by session_id
        # Note: Reference event log doesn't have direct session filtering yet
        metadata_results = await event_router.reference_event_log.query_metadata(
            limit=1000  # Get recent events
        )
        
        # Load and filter events by session
        events = []
        for meta in metadata_results:
            if meta.get("session_id") == session_id:
                # Read event from JSONL file
                event = await _load_event_from_file(meta["file_path"], meta["file_offset"])
                if event:
                    events.append(event)
            else:
                # Also check in data field
                event = await _load_event_from_file(meta["file_path"], meta["file_offset"])
                if event and event.get("data", {}).get("session_id") == session_id:
                    events.append(event)
        
        # Sort by timestamp
        events.sort(key=lambda e: e.get("timestamp", 0), reverse=reverse)
        
        return {
            "session_id": session_id,
            "events": events,
            "count": len(events),
            "sources": ["file_storage"]
        }
        
    except Exception as e:
        logger.error(f"Failed to get session events: {e}")
        return {"error": f"Query failed: {str(e)}"}


@event_handler("monitor:get_correlation_chain")
async def handle_get_correlation_chain(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get all events in a correlation chain.
    
    Args:
        data: Query parameters:
            - correlation_id: Correlation ID to trace
            - include_memory: Include events from memory buffer (default True)
    
    Returns:
        Events in the correlation chain
    """
    if not event_router or not hasattr(event_router, 'reference_event_log'):
        return {"error": "Reference event log not available"}
    
    correlation_id = data.get("correlation_id")
    if not correlation_id:
        return {"error": "No correlation_id provided"}
    
    try:
        # Query events by correlation_id
        metadata_results = await event_router.reference_event_log.query_metadata(
            limit=1000  # Get recent events
        )
        
        # Load events with matching correlation_id
        events = []
        for meta in metadata_results:
            if meta.get("correlation_id") == correlation_id:
                # Read event from JSONL file
                event = await _load_event_from_file(meta["file_path"], meta["file_offset"])
                if event:
                    events.append(event)
        
        # Sort by timestamp to show chain progression
        events.sort(key=lambda e: e.get("timestamp", 0))
        
        # Build chain metadata
        chain_info = {
            "correlation_id": correlation_id,
            "events": events,
            "count": len(events),
            "duration_ms": None,
            "event_types": list(set(e.get("event_name", "") for e in events))
        }
        
        # Calculate chain duration
        if len(events) >= 2:
            chain_info["duration_ms"] = int(
                (events[-1].get("timestamp", 0) - events[0].get("timestamp", 0)) * 1000
            )
        
        return chain_info
        
    except Exception as e:
        logger.error(f"Failed to get correlation chain: {e}")
        return {"error": f"Query failed: {str(e)}"}


@event_handler("system:shutdown")
async def handle_shutdown(data: Dict[str, Any]) -> None:
    """Clean up on shutdown."""
    logger.info("Monitor module shutting down")


