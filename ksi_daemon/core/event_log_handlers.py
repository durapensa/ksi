#!/usr/bin/env python3
"""
Event Log Query Handlers

Provides event handlers for querying the event log system.
Bridges between different query interfaces and parameter naming conventions.
"""

from typing import Dict, Any, List, Optional

from ksi_daemon.event_system import event_handler, emit_event, get_router
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("event_log_handlers")


@event_handler("event_log:query")
async def handle_event_log_query(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query event log - bridges to monitor:get_events with parameter mapping.
    
    This handler provides compatibility for the observation system which
    expects event_log:query to exist. It maps observation-style parameters
    to the monitor module's get_events handler.
    
    Args:
        source_agent: Agent ID to filter by (maps to originator_id)
        event_patterns: List of event name patterns to match
        start_time: Start time for query range (ISO string or timestamp)
        end_time: End time for query range (ISO string or timestamp)
        limit: Maximum number of results
        offset: Pagination offset
    
    Returns:
        events: List of matching events
        total: Total count of matching events
        has_more: Whether more results exist beyond the limit
    """
    # Map observation parameters to monitor parameters
    query = {
        "event_patterns": data.get("event_patterns"),
        "originator_id": data.get("source_agent"),  # Map source_agent to originator_id
        "since": data.get("start_time"),  # Map start_time to since
        "until": data.get("end_time"),    # Map end_time to until
        "limit": data.get("limit", 100),
        "reverse": True  # Always return newest first for observations
    }
    
    # Remove None values to use defaults
    query = {k: v for k, v in query.items() if v is not None}
    
    # Use existing monitor handler
    result = await emit_event("monitor:get_events", query)
    
    # Handle response - emit_event returns a list of responses
    if isinstance(result, list) and result:
        result = result[0]  # Take first response
    else:
        result = {}
    
    # Extract events from result
    events = result.get("events", [])
    total = result.get("total_events", result.get("count", len(events)))
    
    # Handle pagination
    offset = data.get("offset", 0)
    if offset > 0 and offset < len(events):
        events = events[offset:]
    
    # Map response format for observations
    return {
        "events": events,
        "total": total,
        "has_more": len(events) >= query.get("limit", 100),
        "offset": offset
    }


@event_handler("event_log:stats")
async def handle_event_log_stats(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get event log statistics.
    
    Returns current statistics about the event log including:
    - Total events in database
    - Events directory size
    - Database path
    """
    router = get_router()
    
    if not hasattr(router, 'reference_event_log') or not router.reference_event_log:
        return {"error": "Reference event log not available"}
    
    # TODO: Implement stats for reference event log
    # For now, return basic info
    return {
        "status": "reference_event_log",
        "db_path": str(router.reference_event_log.db_path),
        "events_dir": str(router.reference_event_log.events_dir),
        "message": "Detailed stats not yet implemented for reference log"
    }


@event_handler("event_log:clear")
async def handle_event_log_clear(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clear the event log (admin operation).
    
    For reference event log, this would need to clear both
    the SQLite index and JSONL files. Currently disabled
    for safety.
    """
    return {
        "error": "Clear operation not supported for reference event log",
        "message": "File-based logs should be managed through log rotation"
    }