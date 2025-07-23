#!/usr/bin/env python3
"""
Event Log Query Handlers

Provides event handlers for querying the event log system.
Bridges between different query interfaces and parameter naming conventions.
"""

from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict, NotRequired

from ksi_daemon.event_system import event_handler, emit_event, get_router
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("event_log_handlers")


# TypedDict definitions for event handlers
class EventLogQueryData(TypedDict):
    """Query event log with parameter mapping."""
    source_agent: Optional[str]  # Agent ID to filter by (maps to originator_id)
    event_patterns: Optional[List[str]]  # List of event name patterns to match
    start_time: Optional[str]  # Start time for query range (ISO string or timestamp)
    end_time: Optional[str]  # End time for query range (ISO string or timestamp)
    limit: Optional[int]  # Maximum number of results
    offset: Optional[int]  # Pagination offset
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata

class EventLogStatsData(TypedDict):
    """Get event log statistics."""
    # No specific fields - returns all statistics
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata

class EventLogClearData(TypedDict):
    """Clear the event log (admin operation)."""
    # No specific fields for clear operation
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata

@event_handler("event_log:query")
async def handle_event_log_query(data: EventLogQueryData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Query event log - bridges to monitor:get_events with parameter mapping."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder
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
    return event_response_builder(
        {
            "events": events,
            "total": total,
            "has_more": len(events) >= query.get("limit", 100),
            "offset": offset
        },
        context=context
    )


@event_handler("event_log:stats")
async def handle_event_log_stats(data: EventLogStatsData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get event log statistics."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    router = get_router()
    
    if not hasattr(router, 'reference_event_log') or not router.reference_event_log:
        return error_response(
            "Reference event log not available",
            context=context
        )
    
    # Get comprehensive statistics from reference event log
    stats = await router.reference_event_log.get_statistics()
    stats["status"] = "reference_event_log"
    return event_response_builder(
        stats,
        context=context
    )


@event_handler("event_log:clear")
async def handle_event_log_clear(data: EventLogClearData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Clear the event log (admin operation)."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder
    return event_response_builder(
        {
            "error": "Clear operation not supported for reference event log",
            "message": "File-based logs should be managed through log rotation"
        },
        context=context
    )