#!/usr/bin/env python3
"""
Monitor Plugin - Event log query API for pull-based monitoring

Provides endpoints for querying the daemon event log without broadcast overhead.
Supports filtering, pagination, and statistics.
"""

from typing import Dict, Any, List, Optional
import pluggy

from ksi_daemon.plugin_utils import get_logger, plugin_metadata

# Plugin metadata
plugin_metadata("monitor", version="1.0.0",
                description="Event log query API for monitoring")

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Module state
logger = get_logger("monitor")
event_router = None  # Set during startup


@hookimpl
def ksi_startup(config):
    """Initialize monitor plugin."""
    logger.info("Monitor plugin started")
    return {"plugin.monitor": {"loaded": True}}


@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Handle monitor-related events."""
    
    if event_name == "monitor:get_events":
        return handle_get_events(data)
    
    elif event_name == "monitor:get_stats":
        return handle_get_stats(data)
        
    elif event_name == "monitor:clear_log":
        return handle_clear_log(data)
    
    return None


@hookimpl
def ksi_plugin_context(context):
    """Receive plugin context with event router reference."""
    global event_router
    event_router = context.get("event_router")


def handle_get_events(data: Dict[str, Any]) -> Dict[str, Any]:
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
            "events": events,
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


def handle_get_stats(data: Dict[str, Any]) -> Dict[str, Any]:
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


def handle_clear_log(data: Dict[str, Any]) -> Dict[str, Any]:
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


# Module-level marker for plugin discovery
ksi_plugin = True