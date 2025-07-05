#!/usr/bin/env python3
"""
Monitor Plugin - Event-Based Version

Event log query API for pull-based monitoring.
Provides endpoints for querying the daemon event log without broadcast overhead.
Supports filtering, pagination, and statistics.
"""

from typing import Dict, Any, List, Optional

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
    event_router = context.get("event_router")
    logger.info("Monitor module received event router context")


@event_handler("monitor:get_events")
async def handle_get_events(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query event log with filtering and pagination.
    
    Args:
        data: Query parameters:
            - event_patterns: List of event name patterns (supports wildcards)
            - client_id: Filter by specific client  
            - since: Start time (ISO string or timestamp)
            - until: End time (ISO string or timestamp)
            - limit: Maximum number of events to return
            - reverse: Return newest first (default True)
    
    Returns:
        Dictionary with events list and metadata
    """
    if not event_router or not hasattr(event_router, 'event_log'):
        return {"error": "Event log not available"}
    
    try:
        # Extract query parameters
        event_patterns = data.get("event_patterns")
        client_id = data.get("client_id") 
        since = data.get("since")
        until = data.get("until")
        limit = data.get("limit", 100)  # Default limit
        reverse = data.get("reverse", True)
        
        # Query event log
        events = event_router.event_log.get_events(
            event_patterns=event_patterns,
            client_id=client_id,
            since=since,
            until=until,
            limit=limit,
            reverse=reverse
        )
        
        # Get stats for metadata
        stats = event_router.event_log.get_stats()
        
        return {
            "events": [event.to_dict() for event in events],  # Convert objects to dicts for JSON
            "count": len(events),
            "total_events": stats["total_events"],
            "query": {
                "event_patterns": event_patterns,
                "client_id": client_id,
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
    if not event_router or not hasattr(event_router, 'event_log'):
        return {"error": "Event log not available"}
    
    try:
        stats = event_router.event_log.get_stats()
        
        # Add router stats
        router_stats = getattr(event_router, 'stats', {})
        
        return {
            "event_log": stats,
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
    if not event_router or not hasattr(event_router, 'event_log'):
        return {"error": "Event log not available"}
    
    try:
        # Get stats before clearing
        old_stats = event_router.event_log.get_stats()
        
        # Clear log
        event_router.event_log.clear()
        
        logger.info("Event log cleared by admin request")
        
        return {
            "status": "cleared",
            "events_cleared": old_stats["total_events"]
        }
        
    except Exception as e:
        logger.error(f"Failed to clear log: {e}")
        return {"error": f"Clear failed: {str(e)}"}


@event_handler("monitor:subscribe")
async def handle_subscribe(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Subscribe to real-time event stream.
    
    Note: In event system, context is passed through data
    
    Args:
        data: Subscription parameters:
            - event_patterns: List of event name patterns (supports wildcards)
            - filter_fn: Optional additional filter function
            - client_id: Client identifier
            - writer: Transport writer reference
    
    Returns:
        Subscription confirmation
    """
    if not event_router or not hasattr(event_router, 'event_log'):
        return {"error": "Event log not available"}
    
    # Get subscription parameters
    client_id = data.get("client_id")
    patterns = data.get("event_patterns", ["*"])
    
    # Get transport writer
    writer = data.get("writer")
    if not writer:
        return {"error": "No writer available for streaming"}
    
    try:
        # Subscribe to event stream
        subscription = event_router.event_log.subscribe(
            client_id=client_id,
            patterns=patterns,
            writer=writer
        )
        
        logger.info(f"Client {client_id} subscribed to events: {patterns}")
        
        return {
            "status": "subscribed",
            "client_id": client_id,
            "patterns": patterns
        }
        
    except Exception as e:
        logger.error(f"Failed to subscribe {client_id}: {e}")
        return {"error": f"Subscription failed: {str(e)}"}


@event_handler("monitor:unsubscribe")
async def handle_unsubscribe(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Unsubscribe from event stream.
    
    Args:
        data: Unsubscribe parameters:
            - client_id: Client identifier
    
    Returns:
        Unsubscribe confirmation
    """
    if not event_router or not hasattr(event_router, 'event_log'):
        return {"error": "Event log not available"}
    
    # Get client ID
    client_id = data.get("client_id")
    if not client_id:
        return {"error": "No client_id provided"}
    
    try:
        # Unsubscribe from event stream
        event_router.event_log.unsubscribe(client_id)
        
        logger.info(f"Client {client_id} unsubscribed from events")
        
        return {
            "status": "unsubscribed",
            "client_id": client_id
        }
        
    except Exception as e:
        logger.error(f"Failed to unsubscribe {client_id}: {e}")
        return {"error": f"Unsubscribe failed: {str(e)}"}


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
    if not event_router or not hasattr(event_router, 'event_log'):
        return {"error": "Event log not available"}
    
    # Get query parameters
    query = data.get("query")
    params = data.get("params", ())
    limit = data.get("limit", 1000)
    
    if not query:
        return {"error": "No query provided"}
    
    # Security: Only allow SELECT queries
    if not query.strip().upper().startswith("SELECT"):
        return {"error": "Only SELECT queries are allowed"}
    
    try:
        # Add limit if not present
        if "LIMIT" not in query.upper():
            query = f"{query} LIMIT {limit}"
        
        # Execute query
        results = event_router.event_log.query_db(query, params)
        
        return {
            "results": results,
            "count": len(results),
            "query": query
        }
        
    except Exception as e:
        logger.error(f"Query failed: {e}")
        return {"error": f"Query failed: {str(e)}"}


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
    if not event_router or not hasattr(event_router, 'event_log'):
        return {"error": "Event log not available"}
    
    session_id = data.get("session_id")
    if not session_id:
        return {"error": "No session_id provided"}
    
    include_memory = data.get("include_memory", True)
    reverse = data.get("reverse", True)
    
    try:
        events = []
        
        # Get events from database
        db_events = event_router.event_log.query_db(
            """SELECT * FROM events 
               WHERE session_id = ? OR json_extract(data, '$.session_id') = ?
               ORDER BY timestamp""",
            (session_id, session_id)
        )
        events.extend(db_events)
        
        # Get events from memory buffer if requested
        if include_memory:
            memory_events = event_router.event_log.get_events(limit=None)
            # Filter for session
            for event in memory_events:
                event_data = event.get("data", {})
                if event_data.get("session_id") == session_id:
                    # Check if not already in db results
                    if not any(e.get("event_id") == event.get("event_id") 
                             for e in db_events if e.get("event_id")):
                        events.append(event)
        
        # Sort by timestamp
        events.sort(key=lambda e: e.get("timestamp", 0), reverse=reverse)
        
        return {
            "session_id": session_id,
            "events": events,
            "count": len(events),
            "sources": ["database"] + (["memory"] if include_memory else [])
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
    if not event_router or not hasattr(event_router, 'event_log'):
        return {"error": "Event log not available"}
    
    correlation_id = data.get("correlation_id")
    if not correlation_id:
        return {"error": "No correlation_id provided"}
    
    include_memory = data.get("include_memory", True)
    
    try:
        events = []
        
        # Get events from database
        db_events = event_router.event_log.query_db(
            """SELECT * FROM events 
               WHERE correlation_id = ?
               ORDER BY timestamp""",
            (correlation_id,)
        )
        events.extend(db_events)
        
        # Get events from memory buffer if requested
        if include_memory:
            memory_events = event_router.event_log.get_events(limit=None)
            # Filter for correlation
            for event in memory_events:
                if event.get("correlation_id") == correlation_id:
                    # Check if not already in db results
                    if not any(e.get("event_id") == event.get("event_id") 
                             for e in db_events if e.get("event_id")):
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


