#!/usr/bin/env python3
"""
Monitor Module - Event-Based Version

Event log query API for pull-based monitoring.
Provides endpoints for querying the daemon event log without broadcast overhead.
Supports filtering, pagination, and statistics.
"""

from typing import Dict, Any, List, Optional, TypedDict, Union
from typing_extensions import NotRequired, Required
import json
import asyncio
import fnmatch
import time

from ksi_daemon.event_system import event_handler
from ksi_common.logging import get_bound_logger

# Module state
logger = get_bound_logger("monitor", version="1.0.0")
event_router = None  # Set during startup

# Subscription management (moved from unix_socket transport)
client_subscriptions = {}  # client_id -> set of event patterns
client_writers = {}  # client_id -> writer mapping for broadcasting


async def broadcast_to_subscribed_clients(event_name: str, data: Any) -> int:
    """Broadcast event to clients that have subscribed to matching patterns.
    
    Returns:
        Number of clients the event was broadcast to
    """
    if not client_subscriptions:
        return 0
    
    # Build event message in KSI format
    # If data already has originator info (from universal handler), use it directly
    # Otherwise wrap raw data
    if isinstance(data, dict) and "originator" in data and "data" in data:
        event_message = {
            "event_name": event_name,
            "data": data["data"],
            "originator": data["originator"],
            "timestamp": time.time()
        }
    else:
        event_message = {
            "event_name": event_name,
            "data": data,
            "timestamp": time.time()
        }
    
    # Track broadcast statistics
    broadcast_count = 0
    disconnect_clients = []
    
    # Send ONLY to clients with matching subscription patterns
    for str_client_id, patterns in client_subscriptions.items():
        if not patterns:
            continue
            
        # Check if ANY of this client's patterns match the event
        matches = any(
            pattern == "*" or fnmatch.fnmatch(event_name, pattern) 
            for pattern in patterns
        )
        
        if not matches:
            # This client's patterns don't match - SKIP this client entirely
            continue
            
        # Pattern matched - find the writer for this client
        writer = client_writers.get(str_client_id)
        if not writer:
            logger.debug(f"No writer found for subscribed client {str_client_id}")
            continue
            
        # Try to send to this client
        try:
            message_str = json.dumps(event_message) + '\n'
            writer.write(message_str.encode())
            await writer.drain()
            broadcast_count += 1
            logger.debug(f"Broadcasted {event_name} to client {str_client_id} (matched patterns: {patterns})")
        except Exception as e:
            logger.warning(f"Failed to broadcast to client {str_client_id}: {e}")
            disconnect_clients.append(str_client_id)
    
    # Clean up disconnected clients
    for str_client_id in disconnect_clients:
        if str_client_id in client_subscriptions:
            del client_subscriptions[str_client_id]
        if str_client_id in client_writers:
            del client_writers[str_client_id]
            
    return broadcast_count


def register_client_writer(client_id: str, writer: Any):
    """Register a client writer for broadcasting."""
    client_writers[client_id] = writer
    logger.debug(f"Registered writer for client {client_id}")


def unregister_client_writer(client_id: str):
    """Unregister a client writer."""
    if client_id in client_writers:
        del client_writers[client_id]
    if client_id in client_subscriptions:
        del client_subscriptions[client_id]
    logger.debug(f"Unregistered writer for client {client_id}")


def _cleanup_stale_subscriptions():
    """Remove subscriptions for clients that no longer have valid writers."""
    stale_clients = []
    
    for client_id in list(client_subscriptions.keys()):
        writer = client_writers.get(client_id)
        if not writer:
            # No writer means this subscription is stale
            stale_clients.append(client_id)
        else:
            # Check if writer is still valid (not closed)
            try:
                if hasattr(writer, 'is_closing') and writer.is_closing():
                    stale_clients.append(client_id)
                elif hasattr(writer, 'transport') and writer.transport and writer.transport.is_closing():
                    stale_clients.append(client_id)
            except Exception:
                # If we can't check writer status, assume it's stale
                stale_clients.append(client_id)
    
    # Remove stale subscriptions
    for client_id in stale_clients:
        if client_id in client_subscriptions:
            patterns = client_subscriptions[client_id]
            del client_subscriptions[client_id]
            logger.info(f"Cleaned up stale subscription for client {client_id} (patterns: {patterns})")
        if client_id in client_writers:
            del client_writers[client_id]
    
    if stale_clients:
        logger.info(f"Cleaned up {len(stale_clients)} stale subscriptions. Active clients: {len(client_subscriptions)}")


def get_subscription_stats():
    """Get statistics about current subscriptions for debugging."""
    stats = {
        "total_subscriptions": len(client_subscriptions),
        "total_writers": len(client_writers),
        "clients_with_writers": len(set(client_subscriptions.keys()) & set(client_writers.keys())),
        "clients_without_writers": len(set(client_subscriptions.keys()) - set(client_writers.keys())),
        "writers_without_subscriptions": len(set(client_writers.keys()) - set(client_subscriptions.keys())),
        "subscriptions": {client_id: list(patterns) for client_id, patterns in client_subscriptions.items()}
    }
    return stats


# Module info
MODULE_INFO = {
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


class SystemStartupData(TypedDict):
    """System startup configuration."""
    # No specific fields required for this handler
    pass


@event_handler("system:startup")
async def handle_startup(config: SystemStartupData) -> Dict[str, Any]:
    """Initialize monitor module."""
    logger.debug("Monitor startup event received")
    logger.info("Monitor module started")
    return {"monitor_module": {"ready": True}}


class SystemContextData(TypedDict):
    """System context with runtime references."""
    emit_event: NotRequired[Any]  # Event emitter function
    shutdown_event: NotRequired[Any]  # Shutdown event object


@event_handler("system:context")
async def handle_context(context: SystemContextData) -> Dict[str, Any]:
    """Receive module context with event router reference."""
    global event_router
    # Get router directly to avoid JSON serialization issues
    from ksi_daemon.event_system import get_router
    event_router = get_router()
    logger.info("Monitor module received event router context")
    return {
        "event_processed": True,
        "handler": "monitor.handle_context",
        "module": "monitor"
    }


class MonitorGetEventsData(TypedDict):
    """Query event log with filtering and pagination."""
    event_patterns: NotRequired[List[str]]  # Event name patterns (supports wildcards)
    originator_id: NotRequired[str]  # Filter by specific originator
    since: NotRequired[Union[str, float]]  # Start time (ISO string or timestamp)
    until: NotRequired[Union[str, float]]  # End time (ISO string or timestamp)
    limit: NotRequired[int]  # Maximum number of events to return (default: 100)
    reverse: NotRequired[bool]  # Return newest first (default: True)


@event_handler("monitor:get_events")
async def handle_get_events(data: MonitorGetEventsData) -> Dict[str, Any]:
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
        
        # Get actual total from database if we're not pattern filtering
        if event_patterns:
            total_events = len(metadata_results)  # Pattern filtering doesn't give us true total
        else:
            # Get accurate total count from database
            stats = await event_router.reference_event_log.get_statistics()
            total_events = stats.get("storage", {}).get("total_events", len(metadata_results))
        
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


class MonitorGetStatsData(TypedDict):
    """Get event statistics."""
    # No specific fields - returns overall stats
    pass


@event_handler("monitor:get_stats")
async def handle_get_stats(data: MonitorGetStatsData) -> Dict[str, Any]:
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


class MonitorClearLogData(TypedDict):
    """Clear event log (admin operation)."""
    # No specific fields - clears entire log
    pass


@event_handler("monitor:clear_log")
async def handle_clear_log(data: MonitorClearLogData) -> Dict[str, Any]:
    """
    Clear event log (admin operation).
    
    Returns:
        Confirmation of log clearing
    """
    return {
        "error": "Clear operation not supported for reference event log",
        "message": "File-based logs should be managed through log rotation"
    }


class MonitorSubscribeData(TypedDict):
    """Subscribe to real-time event stream."""
    event_patterns: NotRequired[List[str]]  # Event name patterns (supports wildcards)
    filter_fn: NotRequired[Any]  # Additional filter function
    originator_id: NotRequired[str]  # Originator identifier
    writer: NotRequired[Any]  # Transport writer reference


@event_handler("monitor:subscribe")
async def handle_subscribe(data: MonitorSubscribeData) -> Dict[str, Any]:
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
    # Get client_id from data
    client_id = data.get("client_id") or data.get("originator_id")
    if not client_id:
        return {"error": "client_id required"}
    
    event_patterns = data.get("event_patterns", ["*"])
    
    # Import unix_socket module to access subscriptions
    from ksi_daemon.transport import unix_socket
    
    # Clean up any stale subscriptions first (clients with invalid writers)
    _cleanup_stale_subscriptions()
    
    # Check for duplicate subscriptions from the same logical client
    existing_patterns = client_subscriptions.get(client_id, set())
    new_patterns = set(event_patterns)
    
    # Replace subscription entirely instead of accumulating
    client_subscriptions[client_id] = new_patterns
    
    if existing_patterns:
        if existing_patterns == new_patterns:
            logger.debug(f"Client {client_id} re-subscribed with identical patterns: {event_patterns}")
        else:
            logger.info(f"Client {client_id} replaced subscription - old: {existing_patterns}, new: {new_patterns}")
    else:
        logger.info(f"Client {client_id} subscribed to patterns: {event_patterns}")
    
    logger.debug(f"Active subscriptions: {len(client_subscriptions)} clients, patterns: {dict(client_subscriptions)}")
    
    return {
        "status": "subscribed",
        "client_id": client_id,
        "patterns": list(client_subscriptions[client_id])
    }


class MonitorUnsubscribeData(TypedDict):
    """Unsubscribe from event stream."""
    originator_id: Required[str]  # Originator identifier


@event_handler("monitor:unsubscribe")
async def handle_unsubscribe(data: MonitorUnsubscribeData) -> Dict[str, Any]:
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


class MonitorGetSubscriptionsData(TypedDict):
    """Get subscription statistics for debugging."""
    # No specific fields - returns current subscription state
    pass


@event_handler("monitor:get_subscriptions")
async def handle_get_subscriptions(data: MonitorGetSubscriptionsData) -> Dict[str, Any]:
    """
    Get subscription statistics for debugging.
    
    Returns:
        Dictionary with subscription statistics and current state
    """
    # Clean up stale subscriptions before reporting
    _cleanup_stale_subscriptions()
    
    stats = get_subscription_stats()
    
    return {
        "subscription_stats": stats,
        "timestamp": time.time()
    }


class MonitorQueryData(TypedDict):
    """Execute custom SQL query against event database."""
    query: Required[str]  # SQL query string
    params: NotRequired[tuple]  # Query parameters
    limit: NotRequired[int]  # Maximum results (default: 1000)


@event_handler("monitor:query")
async def handle_query(data: MonitorQueryData) -> Dict[str, Any]:
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


class MonitorGetSessionEventsData(TypedDict):
    """Get all events for a specific session."""
    session_id: Required[str]  # Session ID to query
    include_memory: NotRequired[bool]  # Include events from memory buffer (default: True)
    reverse: NotRequired[bool]  # Sort newest first (default: True)


@event_handler("monitor:get_session_events")
async def handle_get_session_events(data: MonitorGetSessionEventsData) -> Dict[str, Any]:
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


class MonitorGetCorrelationChainData(TypedDict):
    """Get all events in a correlation chain."""
    correlation_id: Required[str]  # Correlation ID to trace
    include_memory: NotRequired[bool]  # Include events from memory buffer (default: True)


@event_handler("monitor:get_correlation_chain")
async def handle_get_correlation_chain(data: MonitorGetCorrelationChainData) -> Dict[str, Any]:
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


class SystemShutdownData(TypedDict):
    """System shutdown notification."""
    # No specific fields for shutdown
    pass


@event_handler("system:shutdown")
async def handle_shutdown(data: SystemShutdownData) -> Dict[str, Any]:
    """Clean up on shutdown."""
    logger.info("Monitor module shutting down")
    return {
        "event_processed": True,
        "handler": "monitor.handle_shutdown",
        "module": "monitor",
        "subscriptions_cleared": len(client_subscriptions)
    }


class MonitorGetStatusData(TypedDict):
    """Get consolidated KSI daemon status including recent events and agent info."""
    event_patterns: NotRequired[List[str]]  # Event name patterns (supports wildcards)
    since: NotRequired[Union[str, float]]  # Start time for events (ISO string or timestamp)
    limit: NotRequired[int]  # Maximum number of events to return (default: 20)
    include_agents: NotRequired[bool]  # Include agent status (default: True)
    include_events: NotRequired[bool]  # Include recent events (default: True)


@event_handler("monitor:get_status")
async def handle_get_status(data: MonitorGetStatusData) -> Dict[str, Any]:
    """
    Get consolidated KSI daemon status including recent events and agent information.
    
    This endpoint combines monitor:get_events and agent:list functionality to reduce
    the number of socket calls needed for status monitoring.
    
    Args:
        data: Query parameters:
            - event_patterns: List of event name patterns (supports wildcards)
            - since: Start time for events (ISO string or timestamp)
            - limit: Maximum number of events to return (default: 20)
            - include_agents: Include agent status (default: True)
            - include_events: Include recent events (default: True)
    
    Returns:
        Dictionary with consolidated status information
    """
    result = {}
    
    # Get recent events if requested
    include_events = data.get("include_events", True)
    if include_events:
        try:
            # Prepare event query parameters
            events_data = MonitorGetEventsData(
                event_patterns=data.get("event_patterns"),
                since=data.get("since"),
                limit=data.get("limit", 20),
                reverse=True
            )
            
            # Get events using existing handler
            events_result = await handle_get_events(events_data)
            if "error" not in events_result:
                result["events"] = events_result["events"]
                result["event_count"] = events_result["count"]
            else:
                result["events"] = []
                result["event_count"] = 0
                result["events_error"] = events_result["error"]
                
        except Exception as e:
            logger.error(f"Failed to get events for status: {e}")
            result["events"] = []
            result["event_count"] = 0
            result["events_error"] = str(e)
    
    # Get agent status if requested
    include_agents = data.get("include_agents", True)
    if include_agents:
        try:
            # Import agent service to get agent list
            from ksi_daemon.agent.agent_service import agents, identities
            
            # Build agent status summary
            agent_list = []
            for agent_id, agent_info in agents.items():
                agent_summary = {
                    "agent_id": agent_id,
                    "profile": agent_info.get("profile", "unknown"),
                    "status": agent_info.get("status", "unknown"),
                    "created": agent_info.get("created", 0)
                }
                # Add identity info if available
                if agent_id in identities:
                    identity = identities[agent_id]
                    agent_summary["identity"] = {
                        "name": identity.get("name", agent_id),
                        "type": identity.get("type", "agent")
                    }
                agent_list.append(agent_summary)
            
            result["agents"] = agent_list
            result["agent_count"] = len(agent_list)
            result["total_identities"] = len(identities)
            
        except Exception as e:
            logger.error(f"Failed to get agent status: {e}")
            result["agents"] = []
            result["agent_count"] = 0
            result["agents_error"] = str(e)
    
    # Add timestamp for status snapshot
    result["timestamp"] = time.time()
    result["status"] = "ok"
    
    return result


# Universal event handler for broadcasting (moved from unix_socket)
from typing_extensions import Any as AnyData

@event_handler("*")  # Match ALL events
async def handle_universal_broadcast(data: AnyData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Universal event handler that broadcasts all events to subscribed clients.
    
    This is the proper place for broadcasting logic - in the monitor module,
    not in the transport layer.
    """
    if not context:
        return {"event_processed": True, "handler": "universal_broadcast", "reason": "no_context"}
        
    # Get the event name from context
    event_name = context.get("event")
    if not event_name:
        return {"event_processed": True, "handler": "universal_broadcast", "reason": "no_event_name"}
    
    # Skip internal events to avoid loops
    if event_name.startswith('transport:') or event_name == 'monitor:subscribe':
        return {"event_processed": True, "handler": "universal_broadcast", "reason": "internal_event_skipped"}
    
    # Extract originator information from context
    originator_info = {
        "originator_id": context.get("originator_id") or context.get("agent_id"),
        "agent_id": context.get("agent_id"),
        "source_agent": context.get("source_agent"),
        "construct_id": context.get("construct_id"),
        "correlation_id": context.get("correlation_id"),
        "event_id": context.get("event_id"),
        "session_id": context.get("session_id")
    }
    
    # Remove None values for cleaner output
    originator_info = {k: v for k, v in originator_info.items() if v is not None}
    
    # Log originator info for debugging
    if originator_info:
        logger.debug(f"Broadcasting {event_name} with originator: {originator_info}")
    
    # Create enhanced data that includes both event data and originator context
    enhanced_data = {
        "data": data,
        "originator": originator_info
    }
    
    # Track broadcast stats
    broadcast_count = 0
    if client_subscriptions:
        broadcast_count = await broadcast_to_subscribed_clients(event_name, enhanced_data)
    
    return {
        "event_processed": True,
        "handler": "universal_broadcast",
        "broadcast_count": broadcast_count,
        "event": event_name
    }


