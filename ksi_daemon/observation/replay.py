#!/usr/bin/env python3
"""
Observation Replay System

Provides historical analysis and replay capabilities for observed events.
Builds on the existing event log infrastructure to enable pattern analysis
and event sequence replay.
"""

import asyncio
import json
import time
import fnmatch
from typing import Dict, List, Any, Optional, AsyncIterator
from datetime import datetime, timedelta

from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc, numeric_to_iso
from ksi_daemon.event_system import event_handler, get_router

logger = get_bound_logger("observation_replay")

# Module state
_event_emitter = None
_event_router = None


# Note: ObservationRecord removed - we now use the event log directly
# which stores all events automatically without needing separate records


@event_handler("system:context")
async def handle_context(context: Dict[str, Any]) -> None:
    """Receive system context."""
    global _event_emitter, _event_router
    router = get_router()
    _event_emitter = router.emit
    _event_router = router
    logger.info("Observation replay system initialized")


@event_handler("observe:begin")
async def record_observation_begin(data: Dict[str, Any]) -> None:
    """
    Record the beginning of an observed event.
    
    This handler runs alongside the normal observation flow but since
    all events are now logged, we don't need to store separately.
    We just add observation metadata to help with queries.
    """
    # No need to store - the event log already captured this
    # Just log for debugging
    logger.debug(f"Observation begin: {data.get('observation_id')} for event {data.get('original_event')}")


@event_handler("observe:end")
async def record_observation_end(data: Dict[str, Any]) -> None:
    """
    Record the completion of an observed event.
    
    The event log captures this automatically, we just log for debugging.
    Duration calculation can be done during query time.
    """
    # No need to store - the event log already captured this
    logger.debug(f"Observation end: {data.get('observation_id')} for event {data.get('original_event')}")


@event_handler("observation:query_history")
async def query_observation_history(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query historical observation records from the event log.
    
    Args:
        observer (str): Filter by observer (optional)
        target (str): Filter by target (optional)
        event_name (str): Filter by event name pattern (optional)
        since (float): Start timestamp (optional)
        until (float): End timestamp (optional)
        limit (int): Maximum records to return (default 100)
        include_data (bool): Include full event data (default False)
    
    Returns:
        Historical observation records with statistics
    """
    if not _event_emitter:
        return {"error": "Event system not initialized"}
    
    # Build event patterns to query
    event_patterns = ["observe:begin", "observe:end"]
    if data.get("event_name"):
        # Also include the original event patterns
        event_patterns.append(data["event_name"])
    
    # Query event log through event handler
    query_result = await _event_emitter("event_log:query", {
        "event_patterns": event_patterns,
        "source_agent": data.get("observer"),  # Observer is the source_agent
        "start_time": data.get("since"),
        "end_time": data.get("until"),
        "limit": data.get("limit", 100) * 2  # Get more since we'll filter
    })
    
    # Extract events from result
    events = query_result[0].get("events", []) if query_result else []
    
    # Process events into observation records
    observations = {}  # observation_id -> record
    
    for event in events:
        event_data = event.get("data", {})
        event_name = event.get("event_name", "")
        timestamp = event.get("timestamp", 0)
        
        # Filter by target if specified
        if data.get("target") and event_data.get("source") != data["target"]:
            continue
            
        obs_id = event_data.get("observation_id")
        if not obs_id:
            continue
            
        if obs_id not in observations:
            observations[obs_id] = {
                "observation_id": obs_id,
                "event_name": event_data.get("original_event"),
                "observer": event_data.get("observer"),
                "target": event_data.get("source"),
                "timestamp": timestamp,
                "timestamp_iso": numeric_to_iso(timestamp)
            }
        
        # Update with event-specific data
        if event_name == "observe:begin":
            observations[obs_id]["begin_timestamp"] = timestamp
            if data.get("include_data", False):
                observations[obs_id]["event_data"] = event_data.get("original_data")
        elif event_name == "observe:end":
            observations[obs_id]["end_timestamp"] = timestamp
            if "begin_timestamp" in observations[obs_id]:
                duration_ms = (timestamp - observations[obs_id]["begin_timestamp"]) * 1000
                observations[obs_id]["duration_ms"] = duration_ms
            if data.get("include_data", False):
                observations[obs_id]["result"] = event_data.get("result")
    
    # Convert to list and apply limit
    records = list(observations.values())[:data.get("limit", 100)]
    
    # Calculate statistics
    stats = calculate_observation_stats(records)
    
    return {
        "records": records,
        "count": len(records),
        "stats": stats
    }


@event_handler("observation:replay")
async def replay_observations(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Replay a sequence of events from the event log.
    
    Args:
        event_patterns (list): Event patterns to replay (e.g. ["task:*", "data:*"])
        filter: Additional filters
            - originator_id: Filter by specific originator/agent
            - since: Start timestamp
            - until: End timestamp
        speed (float): Replay speed multiplier (1.0 = real-time)
        target_agent (str): Agent to receive replayed events
        as_new_events (bool): Emit as new events vs observe:replay events
    
    Returns:
        Replay session information
    """
    if not _event_emitter:
        return {"error": "Event system not initialized"}
    
    # Query events to replay
    event_patterns = data.get("event_patterns", ["*"])
    filter_data = data.get("filter", {})
    
    # Query from event log through event handler
    query_result = await _event_emitter("event_log:query", {
        "event_patterns": event_patterns,
        "source_agent": filter_data.get("originator_id"),
        "start_time": filter_data.get("since"),
        "end_time": filter_data.get("until"),
        "limit": filter_data.get("limit", 1000)
    })
    
    # Extract events from result (already in chronological order from event_log:query)
    events = query_result[0].get("events", []) if query_result else []
    
    if not events:
        return {"error": "No events found to replay"}
    
    # Filter out system events we don't want to replay
    skip_patterns = ["observe:*", "observation:*", "system:*", "monitor:*"]
    filtered_events = []
    for event in events:
        event_name = event.get("event_name", "")
        skip = False
        for pattern in skip_patterns:
            if fnmatch.fnmatch(event_name, pattern):
                skip = True
                break
        if not skip:
            filtered_events.append(event)
    
    if not filtered_events:
        return {"error": "No replayable events found after filtering"}
    
    # Create replay session
    session_id = f"replay_{int(time.time())}"
    speed = data.get("speed", 1.0)
    target_agent = data.get("target_agent")
    as_new_events = data.get("as_new_events", False)
    
    # Start replay task
    asyncio.create_task(
        replay_events_from_log(session_id, filtered_events, speed, target_agent, as_new_events)
    )
    
    return {
        "session_id": session_id,
        "event_count": len(filtered_events),
        "speed": speed,
        "estimated_duration_seconds": calculate_replay_duration_from_events(filtered_events, speed)
    }


async def replay_events_from_log(session_id: str, events: List, 
                               speed: float, target_agent: Optional[str],
                               as_new_events: bool) -> None:
    """
    Asynchronously replay events from the event log with proper timing.
    """
    if not events:
        return
        
    logger.info(f"Starting replay session {session_id} with {len(events)} events")
    
    # Emit replay started event
    await _event_emitter("observation:replay_started", {
        "session_id": session_id,
        "event_count": len(events),
        "speed": speed
    })
    
    start_time = time.time()
    first_timestamp = events[0].get("timestamp", 0)
    
    for i, event in enumerate(events):
        # Calculate delay
        if i > 0:
            time_diff = event.get("timestamp", 0) - events[i-1].get("timestamp", 0)
            delay = time_diff / speed
            if delay > 0:
                await asyncio.sleep(delay)
        
        # Prepare event data
        event_data = event.get("data", {}).copy()
        
        if target_agent:
            # Override agent_id if targeting specific agent
            event_data["agent_id"] = target_agent
            
        if as_new_events:
            # Re-emit as original event
            await _event_emitter(event.get("event_name", ""), event_data)
        else:
            # Emit as replay event
            await _event_emitter("observation:replayed_event", {
                "session_id": session_id,
                "original_event": event.get("event_name", ""),
                "original_data": event_data,
                "original_timestamp": event.get("timestamp", 0),
                "event_id": event.get("event_id"),
                "sequence": i + 1,
                "total": len(events)
            })
    
    # Emit replay completed
    await _event_emitter("observation:replay_completed", {
        "session_id": session_id,
        "events_replayed": len(events),
        "duration_seconds": time.time() - start_time
    })
    
    logger.info(f"Replay session {session_id} completed")


@event_handler("observation:analyze_patterns")
async def analyze_observation_patterns(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze patterns in event history from the event log.
    
    Args:
        event_patterns (list): Event patterns to analyze (default ["*"])
        filter: Additional filters
            - originator_id: Filter by specific originator/agent
            - since: Start timestamp
            - until: End timestamp
        analysis_type: "frequency", "sequence", "performance", "errors"
    
    Returns:
        Pattern analysis results
    """
    if not _event_emitter:
        return {"error": "Event system not initialized"}
    
    # Query events from log
    event_patterns = data.get("event_patterns", ["*"])
    filter_data = data.get("filter", {})
    
    # Query from event log through event handler
    query_result = await _event_emitter("event_log:query", {
        "event_patterns": event_patterns,
        "source_agent": filter_data.get("originator_id"),
        "start_time": filter_data.get("since"),
        "end_time": filter_data.get("until"),
        "limit": data.get("limit", 1000)
    })
    
    # Extract events from result
    events = query_result[0].get("events", []) if query_result else []
    
    if not events:
        return {"error": "No events found to analyze"}
    
    analysis_type = data.get("analysis_type", "frequency")
    
    if analysis_type == "frequency":
        return analyze_frequency_patterns_from_events(events)
    elif analysis_type == "sequence":
        return analyze_sequence_patterns_from_events(events)
    elif analysis_type == "performance":
        return analyze_performance_patterns_from_events(events)
    elif analysis_type == "errors":
        return analyze_error_patterns_from_events(events)
    else:
        return {"error": f"Unknown analysis type: {analysis_type}"}


def calculate_observation_stats(records: List[Dict]) -> Dict[str, Any]:
    """Calculate basic statistics from observation records."""
    if not records:
        return {}
        
    # Group by event type
    begins = [r for r in records if r.get("event_type") == "begin"]
    ends = [r for r in records if r.get("event_type") == "end"]
    
    # Calculate durations
    durations = [r["duration_ms"] for r in ends if r.get("duration_ms") is not None]
    
    stats = {
        "total_observations": len(set(r["observation_id"] for r in records)),
        "completed_observations": len(ends),
        "event_types": list(set(r["event_name"] for r in records))
    }
    
    if durations:
        stats["performance"] = {
            "avg_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "total_duration_ms": sum(durations)
        }
        
    return stats


def calculate_replay_duration_from_events(events: List, speed: float) -> float:
    """Calculate estimated replay duration from event log entries."""
    if not events or len(events) < 2:
        return 0.0
        
    first_timestamp = events[0].get("timestamp", 0)
    last_timestamp = events[-1].get("timestamp", 0)
    duration = last_timestamp - first_timestamp
    
    return duration / speed


def analyze_frequency_patterns_from_events(events: List) -> Dict[str, Any]:
    """Analyze event frequency patterns from event log entries."""
    from collections import Counter
    
    # Count events by type
    event_counts = Counter(e.get("event_name", "") for e in events)
    
    # Count by client (agent) - using originator_id from event log
    client_counts = Counter(e.get("originator_id") for e in events if e.get("originator_id"))
    
    # Time-based frequency (hourly)
    hourly_counts = {}
    for event in events:
        timestamp = event.get("timestamp", 0)
        if timestamp:
            hour = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:00")
            hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
    
    return {
        "analysis_type": "frequency",
        "event_frequency": dict(event_counts.most_common(10)),
        "client_frequency": dict(client_counts.most_common(10)),
        "hourly_distribution": hourly_counts,
        "total_events": len(events),
        "time_range": {
            "start": numeric_to_iso(events[0].get("timestamp", 0)) if events else None,
            "end": numeric_to_iso(events[-1].get("timestamp", 0)) if events else None
        }
    }


def analyze_sequence_patterns_from_events(events: List) -> Dict[str, Any]:
    """Analyze event sequence patterns from event log entries."""
    # Events should already be sorted by timestamp
    
    # Find common sequences (2-grams) - same client
    sequences = []
    for i in range(len(events) - 1):
        client_id1 = events[i].get("originator_id")
        client_id2 = events[i+1].get("originator_id")
        if client_id1 and client_id1 == client_id2:
            # Only if events are close in time (within 60 seconds)
            time_diff = events[i+1].get("timestamp", 0) - events[i].get("timestamp", 0)
            if time_diff < 60:
                sequences.append((
                    events[i].get("event_name", ""),
                    events[i+1].get("event_name", "")
                ))
    
    from collections import Counter
    sequence_counts = Counter(sequences)
    
    # Find 3-grams for more complex patterns
    trigrams = []
    for i in range(len(events) - 2):
        client_id1 = events[i].get("originator_id")
        client_id2 = events[i+1].get("originator_id")
        client_id3 = events[i+2].get("originator_id")
        if (client_id1 and 
            client_id1 == client_id2 == client_id3 and
            events[i+2].get("timestamp", 0) - events[i].get("timestamp", 0) < 120):
            trigrams.append((
                events[i].get("event_name", ""),
                events[i+1].get("event_name", ""),
                events[i+2].get("event_name", "")
            ))
    
    trigram_counts = Counter(trigrams)
    
    return {
        "analysis_type": "sequence",
        "common_sequences": [
            {"sequence": list(seq), "count": cnt}
            for seq, cnt in sequence_counts.most_common(10)
        ],
        "common_trigrams": [
            {"sequence": list(seq), "count": cnt}
            for seq, cnt in trigram_counts.most_common(5)
        ],
        "sequence_count": len(sequence_counts),
        "trigram_count": len(trigram_counts)
    }


def analyze_performance_patterns_from_events(events: List) -> Dict[str, Any]:
    """Analyze performance patterns by looking at observe:begin/end pairs."""
    # Find paired observe events to calculate durations
    observations = {}  # observation_id -> {begin_time, end_time, event_name}
    
    for event in events:
        event_name = event.get("event_name", "")
        if event_name in ["observe:begin", "observe:end"]:
            event_data = event.get("data", {})
            obs_id = event_data.get("observation_id")
            if obs_id:
                if obs_id not in observations:
                    observations[obs_id] = {}
                
                if event_name == "observe:begin":
                    observations[obs_id]["begin_time"] = event.get("timestamp", 0)
                    observations[obs_id]["event_name"] = event_data.get("original_event", "unknown")
                elif event_name == "observe:end":
                    observations[obs_id]["end_time"] = event.get("timestamp", 0)
    
    # Calculate durations
    perf_by_event = {}
    for obs_id, obs_data in observations.items():
        if "begin_time" in obs_data and "end_time" in obs_data:
            duration_ms = (obs_data["end_time"] - obs_data["begin_time"]) * 1000
            event_name = obs_data["event_name"]
            
            if event_name not in perf_by_event:
                perf_by_event[event_name] = []
            perf_by_event[event_name].append(duration_ms)
    
    # Calculate stats per event type
    event_stats = {}
    for event_name, durations in perf_by_event.items():
        if durations:
            event_stats[event_name] = {
                "avg_ms": sum(durations) / len(durations),
                "min_ms": min(durations),
                "max_ms": max(durations),
                "count": len(durations)
            }
    
    # Find slowest individual events
    slow_events = []
    for obs_id, obs_data in observations.items():
        if "begin_time" in obs_data and "end_time" in obs_data:
            duration_ms = (obs_data["end_time"] - obs_data["begin_time"]) * 1000
            slow_events.append({
                "observation_id": obs_id,
                "event_name": obs_data["event_name"],
                "duration_ms": duration_ms,
                "timestamp": obs_data["begin_time"]
            })
    
    slow_events.sort(key=lambda x: x["duration_ms"], reverse=True)
    
    return {
        "analysis_type": "performance",
        "event_performance": event_stats,
        "slowest_events": slow_events[:10],
        "total_observations": len(observations),
        "completed_observations": sum(1 for o in observations.values() 
                                    if "begin_time" in o and "end_time" in o)
    }


def analyze_error_patterns_from_events(events: List) -> Dict[str, Any]:
    """Analyze error patterns from event log."""
    from collections import Counter
    
    # Find error-related events
    error_events = []
    error_types = Counter()
    error_by_client = Counter()
    
    for event in events:
        event_name = event.get("event_name", "")
        event_data = event.get("data", {})
        
        # Check if it's an error event
        if (event_name.startswith("error:") or 
            event_name == "event:error" or
            (event_data and "error" in event_data)):
            
            error_events.append(event)
            error_types[event_name] += 1
            
            originator_id = event.get("originator_id")
            if originator_id:
                error_by_client[originator_id] += 1
    
    # Extract error messages if available
    error_messages = []
    for event in error_events[:100]:  # Limit to prevent huge output
        event_data = event.get("data", {})
        if event_data:
            if isinstance(event_data.get("error"), str):
                error_messages.append({
                    "event": event.get("event_name", ""),
                    "error": event_data["error"],
                    "timestamp": numeric_to_iso(event.get("timestamp", 0)),
                    "client": event.get("originator_id")
                })
    
    return {
        "analysis_type": "errors",
        "total_errors": len(error_events),
        "error_types": dict(error_types.most_common()),
        "errors_by_client": dict(error_by_client.most_common(10)),
        "recent_errors": error_messages[:10],
        "error_rate": {
            "errors_per_event": len(error_events) / len(events) if events else 0,
            "percentage": (len(error_events) / len(events) * 100) if events else 0
        }
    }