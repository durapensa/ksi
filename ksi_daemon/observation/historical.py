#!/usr/bin/env python3
"""
Historical observation queries against event log.

Enables querying past observations from the event log rather than
relying on real-time subscriptions.
"""

import json
from typing import Dict, Any, List, Optional, TypedDict, Literal
from typing_extensions import NotRequired, Required
from datetime import datetime, timezone

from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import event_handler, get_router

logger = get_bound_logger("observation.historical")
event_emitter = None


# TypedDict definitions for event handlers

class SystemContextData(TypedDict):
    """System context with runtime references."""
    emit_event: NotRequired[Any]  # Event emitter function
    shutdown_event: NotRequired[Any]  # Shutdown event object


class ObservationQueryData(TypedDict):
    """Query historical observations from event log."""
    observer: NotRequired[str]  # Observer agent ID
    target: Required[str]  # Target agent ID
    events: NotRequired[List[str]]  # Event patterns to match (default: ["*"])
    time_range: NotRequired[Dict[str, str]]  # Dict with 'start' and 'end' ISO timestamps
    limit: NotRequired[int]  # Maximum results (default 100, max 1000)
    offset: NotRequired[int]  # Pagination offset (default 0)


class ObservationReplayData(TypedDict):
    """Replay historical observations to an observer."""
    observer: Required[str]  # Observer agent ID
    target: NotRequired[str]  # Target agent ID
    events: NotRequired[List[str]]  # Event patterns to match
    time_range: NotRequired[Dict[str, str]]  # Time range to replay
    limit: NotRequired[int]  # Maximum results to replay
    offset: NotRequired[int]  # Pagination offset


class ObservationAnalyzeData(TypedDict):
    """Analyze patterns in historical observations."""
    target: Required[str]  # Target agent to analyze
    time_range: NotRequired[Dict[str, str]]  # Time range to analyze
    analysis_type: NotRequired[Literal["frequency", "errors", "performance"]]  # Type of analysis (default: "frequency")


@event_handler("system:context")
async def handle_context(context: SystemContextData) -> None:
    """Receive system context with event emitter."""
    global event_emitter
    router = get_router()
    event_emitter = router.emit
    logger.info("Historical observation service initialized")


@event_handler("observation:query")
async def query_historical_observations(data: ObservationQueryData) -> Dict[str, Any]:
    """Query historical observations from event log."""
    observer = data.get("observer")
    target = data.get("target")
    events = data.get("events", ["*"])
    time_range = data.get("time_range", {})
    limit = min(data.get("limit", 100), 1000)  # Cap at 1000
    offset = data.get("offset", 0)
    
    if not target:
        return {"error": "Target agent ID required"}
    
    # Build event log query
    query = {
        "source_agent": target,
        "limit": limit,
        "offset": offset
    }
    
    # Add time range if specified
    if time_range.get("start"):
        query["start_time"] = time_range["start"]
    if time_range.get("end"):
        query["end_time"] = time_range["end"]
    
    # Add event pattern matching
    if events != ["*"]:
        query["event_patterns"] = events
    
    # Query event log
    result = await event_emitter("event_log:query", query)
    
    if result and isinstance(result, list):
        result = result[0] if result else {}
    
    if result.get("error"):
        return {"error": f"Event log query failed: {result['error']}"}
    
    # Format results
    matching_events = result.get("events", [])
    
    return {
        "observer": observer,
        "target": target,
        "events": matching_events,
        "total": result.get("total", len(matching_events)),
        "has_more": result.get("has_more", False),
        "query": {
            "events": events,
            "time_range": time_range,
            "limit": limit,
            "offset": offset
        }
    }


@event_handler("observation:replay")
async def replay_observations(data: ObservationReplayData) -> Dict[str, Any]:
    """Replay historical observations to an observer."""
    observer = data.get("observer")
    if not observer:
        return {"error": "Observer agent ID required"}
    
    # Query historical events
    query_result = await query_historical_observations(data)
    
    if query_result.get("error"):
        return query_result
    
    # Replay each event as an observation
    replayed = 0
    for event in query_result["events"]:
        # Send as observation event
        await event_emitter(f"agent:{observer}:observation", {
            "type": "replay",
            "original_event": event.get("event", "unknown"),
            "source_agent": event.get("source_agent", data.get("target")),
            "data": event.get("data", {}),
            "timestamp": event.get("timestamp"),
            "metadata": {
                "replayed_at": datetime.now(timezone.utc).isoformat(),
                "query": query_result["query"]
            }
        })
        replayed += 1
    
    return {
        "observer": observer,
        "replayed_events": replayed,
        "total_available": query_result["total"],
        "has_more": query_result["has_more"]
    }


@event_handler("observation:analyze")
async def analyze_observation_patterns(data: ObservationAnalyzeData) -> Dict[str, Any]:
    """Analyze patterns in historical observations."""
    target = data.get("target")
    time_range = data.get("time_range", {})
    analysis_type = data.get("analysis_type", "frequency")
    
    if not target:
        return {"error": "Target agent ID required"}
    
    # Query all events for the target in time range
    query = {
        "source_agent": target,
        "limit": 10000  # Large limit for analysis
    }
    
    if time_range.get("start"):
        query["start_time"] = time_range["start"]
    if time_range.get("end"):
        query["end_time"] = time_range["end"]
    
    result = await event_emitter("event_log:query", query)
    
    if result and isinstance(result, list):
        result = result[0] if result else {}
    
    if result.get("error"):
        return {"error": f"Event log query failed: {result['error']}"}
    
    events = result.get("events", [])
    
    # Perform analysis based on type
    if analysis_type == "frequency":
        # Count events by type
        event_counts = {}
        for event in events:
            event_name = event.get("event", "unknown")
            event_counts[event_name] = event_counts.get(event_name, 0) + 1
        
        # Sort by frequency
        sorted_events = sorted(event_counts.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "analysis_type": "frequency",
            "target": target,
            "total_events": len(events),
            "unique_events": len(event_counts),
            "top_events": sorted_events[:10],
            "event_counts": dict(sorted_events)
        }
    
    elif analysis_type == "errors":
        # Find all error events
        error_events = [e for e in events if "error" in e.get("event", "").lower()]
        
        # Group by error type
        error_types = {}
        for event in error_events:
            event_name = event.get("event", "unknown")
            error_types[event_name] = error_types.get(event_name, 0) + 1
        
        return {
            "analysis_type": "errors",
            "target": target,
            "total_errors": len(error_events),
            "error_rate": len(error_events) / max(len(events), 1),
            "error_types": error_types,
            "recent_errors": error_events[-10:]  # Last 10 errors
        }
    
    elif analysis_type == "performance":
        # Analyze completion times for tasks
        task_events = [e for e in events if "task:" in e.get("event", "")]
        
        # Group by task lifecycle
        task_starts = {}
        task_completions = []
        
        for event in task_events:
            event_name = event.get("event", "")
            task_id = event.get("data", {}).get("task_id")
            timestamp = event.get("timestamp")
            
            if not task_id or not timestamp:
                continue
            
            if "task:started" in event_name:
                task_starts[task_id] = timestamp
            elif "task:completed" in event_name and task_id in task_starts:
                duration = timestamp - task_starts[task_id]
                task_completions.append({
                    "task_id": task_id,
                    "duration": duration,
                    "completed_at": timestamp
                })
        
        # Calculate statistics
        if task_completions:
            durations = [t["duration"] for t in task_completions]
            avg_duration = sum(durations) / len(durations)
            min_duration = min(durations)
            max_duration = max(durations)
        else:
            avg_duration = min_duration = max_duration = 0
        
        return {
            "analysis_type": "performance",
            "target": target,
            "total_tasks": len(task_completions),
            "average_duration": avg_duration,
            "min_duration": min_duration,
            "max_duration": max_duration,
            "recent_completions": task_completions[-10:]
        }
    
    else:
        return {"error": f"Unknown analysis type: {analysis_type}"}