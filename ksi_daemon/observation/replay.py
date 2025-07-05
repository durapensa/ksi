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
from typing import Dict, List, Any, Optional, AsyncIterator
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc, numeric_to_iso
from ksi_daemon.event_system import event_handler, get_router

logger = get_bound_logger("observation_replay")

# Module state
_event_emitter = None
_event_router = None


@dataclass
class ObservationRecord:
    """Record of an observed event for historical analysis."""
    observation_id: str
    subscription_id: str
    observer: str
    target: str
    event_name: str
    event_data: Dict[str, Any]
    timestamp: float
    event_type: str  # "begin" or "end"
    result: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data["timestamp_iso"] = numeric_to_iso(self.timestamp)
        return data


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
    
    This handler runs alongside the normal observation flow to capture
    events for historical analysis.
    """
    if not _event_emitter:
        return
        
    # Create observation record
    record = ObservationRecord(
        observation_id=data["observation_id"],
        subscription_id=data["subscription_id"],
        observer=data["observer"],
        target=data["source"],
        event_name=data["original_event"],
        event_data=data.get("original_data", {}),
        timestamp=data.get("timestamp", time.time()),
        event_type="begin"
    )
    
    # Store in relational state for persistence
    await _event_emitter("state:entity:create", {
        "type": "observation_record",
        "id": f"{record.observation_id}_begin",
        "properties": record.to_dict()
    })
    
    logger.debug(f"Recorded observation begin: {record.observation_id}")


@event_handler("observe:end")
async def record_observation_end(data: Dict[str, Any]) -> None:
    """
    Record the completion of an observed event.
    
    Captures results and calculates duration for performance analysis.
    """
    if not _event_emitter:
        return
        
    # Look up the begin record to calculate duration
    begin_id = f"{data['observation_id']}_begin"
    begin_result = await _event_emitter("state:entity:get", {
        "id": begin_id
    })
    
    duration_ms = None
    if begin_result and isinstance(begin_result, list) and begin_result[0].get("entity"):
        begin_timestamp = begin_result[0]["entity"]["properties"].get("timestamp", 0)
        current_timestamp = data.get("timestamp", time.time())
        duration_ms = (current_timestamp - begin_timestamp) * 1000
    
    # Create end record
    record = ObservationRecord(
        observation_id=data["observation_id"],
        subscription_id=data["subscription_id"],
        observer=data["observer"],
        target=data["source"],
        event_name=data["original_event"],
        event_data={},  # Already captured in begin
        timestamp=data.get("timestamp", time.time()),
        event_type="end",
        result=data.get("result"),
        duration_ms=duration_ms
    )
    
    # Store end record
    await _event_emitter("state:entity:create", {
        "type": "observation_record",
        "id": f"{record.observation_id}_end",
        "properties": record.to_dict()
    })
    
    logger.debug(f"Recorded observation end: {record.observation_id} (duration: {duration_ms:.2f}ms)")


@event_handler("observation:query_history")
async def query_observation_history(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query historical observation records.
    
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
    # Build query
    where_conditions = {"type": "observation_record"}
    
    if data.get("observer"):
        where_conditions["observer"] = data["observer"]
    if data.get("target"):
        where_conditions["target"] = data["target"]
    if data.get("event_name"):
        where_conditions["event_name"] = data["event_name"]
        
    # Query records
    result = await _event_emitter("state:entity:query", {
        "type": "observation_record",
        "where": where_conditions,
        "limit": data.get("limit", 100),
        "order_by": "timestamp",
        "order": "DESC"
    })
    
    if not result or not isinstance(result, list):
        return {"records": [], "count": 0}
        
    records = []
    for entity_result in result:
        if entity_result.get("entities"):
            for entity in entity_result["entities"]:
                props = entity.get("properties", {})
                
                # Apply time filters
                timestamp = props.get("timestamp", 0)
                if data.get("since") and timestamp < data["since"]:
                    continue
                if data.get("until") and timestamp > data["until"]:
                    continue
                    
                # Build record
                record = {
                    "observation_id": props.get("observation_id"),
                    "event_name": props.get("event_name"),
                    "observer": props.get("observer"),
                    "target": props.get("target"),
                    "timestamp": timestamp,
                    "timestamp_iso": props.get("timestamp_iso"),
                    "event_type": props.get("event_type"),
                    "duration_ms": props.get("duration_ms")
                }
                
                if data.get("include_data", False):
                    record["event_data"] = props.get("event_data")
                    record["result"] = props.get("result")
                    
                records.append(record)
    
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
    Replay a sequence of observed events.
    
    Args:
        observation_ids (list): Specific observations to replay
        filter: Same as query_history to select events
        speed (float): Replay speed multiplier (1.0 = real-time)
        target_agent (str): Agent to receive replayed events
        as_new_events (bool): Emit as new events vs observe:replay events
    
    Returns:
        Replay session information
    """
    # Query observations to replay
    query_data = data.get("filter", {})
    query_data["include_data"] = True
    
    history_result = await query_observation_history(query_data)
    records = history_result.get("records", [])
    
    if not records:
        return {"error": "No observations found to replay"}
    
    # Filter to begin events only (we replay the originals)
    begin_records = [r for r in records if r.get("event_type") == "begin"]
    
    # Sort by timestamp for chronological replay
    begin_records.sort(key=lambda r: r.get("timestamp", 0))
    
    # Create replay session
    session_id = f"replay_{int(time.time())}"
    speed = data.get("speed", 1.0)
    target_agent = data.get("target_agent")
    as_new_events = data.get("as_new_events", False)
    
    # Start replay task
    asyncio.create_task(
        replay_events_async(session_id, begin_records, speed, target_agent, as_new_events)
    )
    
    return {
        "session_id": session_id,
        "event_count": len(begin_records),
        "speed": speed,
        "estimated_duration_seconds": calculate_replay_duration(begin_records, speed)
    }


async def replay_events_async(session_id: str, records: List[Dict], 
                            speed: float, target_agent: Optional[str],
                            as_new_events: bool) -> None:
    """
    Asynchronously replay events with proper timing.
    """
    if not records:
        return
        
    logger.info(f"Starting replay session {session_id} with {len(records)} events")
    
    # Emit replay started event
    await _event_emitter("observation:replay_started", {
        "session_id": session_id,
        "event_count": len(records),
        "speed": speed
    })
    
    start_time = time.time()
    first_timestamp = records[0]["timestamp"]
    
    for i, record in enumerate(records):
        # Calculate delay
        if i > 0:
            time_diff = record["timestamp"] - records[i-1]["timestamp"]
            delay = time_diff / speed
            if delay > 0:
                await asyncio.sleep(delay)
        
        # Prepare event data
        event_data = record.get("event_data", {})
        
        if target_agent:
            # Override agent_id if targeting specific agent
            event_data["agent_id"] = target_agent
            
        if as_new_events:
            # Re-emit as original event
            await _event_emitter(record["event_name"], event_data)
        else:
            # Emit as replay event
            await _event_emitter("observation:replayed_event", {
                "session_id": session_id,
                "original_event": record["event_name"],
                "original_data": event_data,
                "original_timestamp": record["timestamp"],
                "observation_id": record["observation_id"],
                "sequence": i + 1,
                "total": len(records)
            })
    
    # Emit replay completed
    await _event_emitter("observation:replay_completed", {
        "session_id": session_id,
        "events_replayed": len(records),
        "duration_seconds": time.time() - start_time
    })
    
    logger.info(f"Replay session {session_id} completed")


@event_handler("observation:analyze_patterns")
async def analyze_observation_patterns(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze patterns in observation history.
    
    Args:
        filter: Same as query_history to select events
        analysis_type: "frequency", "sequence", "performance", "errors"
    
    Returns:
        Pattern analysis results
    """
    # Query observations
    query_data = data.get("filter", {})
    query_data["limit"] = data.get("limit", 1000)  # Higher limit for analysis
    
    history_result = await query_observation_history(query_data)
    records = history_result.get("records", [])
    
    if not records:
        return {"error": "No observations found to analyze"}
    
    analysis_type = data.get("analysis_type", "frequency")
    
    if analysis_type == "frequency":
        return analyze_frequency_patterns(records)
    elif analysis_type == "sequence":
        return analyze_sequence_patterns(records)
    elif analysis_type == "performance":
        return analyze_performance_patterns(records)
    elif analysis_type == "errors":
        return analyze_error_patterns(records)
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


def calculate_replay_duration(records: List[Dict], speed: float) -> float:
    """Calculate estimated replay duration."""
    if not records or len(records) < 2:
        return 0.0
        
    first_timestamp = records[0]["timestamp"]
    last_timestamp = records[-1]["timestamp"]
    duration = last_timestamp - first_timestamp
    
    return duration / speed


def analyze_frequency_patterns(records: List[Dict]) -> Dict[str, Any]:
    """Analyze event frequency patterns."""
    from collections import Counter
    
    # Count events by type
    event_counts = Counter(r["event_name"] for r in records)
    
    # Count by observer-target pairs
    pair_counts = Counter((r["observer"], r["target"]) for r in records)
    
    # Time-based frequency (hourly)
    hourly_counts = {}
    for record in records:
        hour = datetime.fromtimestamp(record["timestamp"]).strftime("%Y-%m-%d %H:00")
        hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
    
    return {
        "analysis_type": "frequency",
        "event_frequency": dict(event_counts.most_common(10)),
        "observer_target_pairs": [
            {"observer": obs, "target": tgt, "count": cnt}
            for (obs, tgt), cnt in pair_counts.most_common(10)
        ],
        "hourly_distribution": hourly_counts,
        "total_events": len(records)
    }


def analyze_sequence_patterns(records: List[Dict]) -> Dict[str, Any]:
    """Analyze event sequence patterns."""
    # Sort by timestamp
    sorted_records = sorted(records, key=lambda r: r["timestamp"])
    
    # Find common sequences (2-grams)
    sequences = []
    for i in range(len(sorted_records) - 1):
        if sorted_records[i]["target"] == sorted_records[i+1]["target"]:
            sequences.append((
                sorted_records[i]["event_name"],
                sorted_records[i+1]["event_name"]
            ))
    
    from collections import Counter
    sequence_counts = Counter(sequences)
    
    return {
        "analysis_type": "sequence",
        "common_sequences": [
            {"sequence": list(seq), "count": cnt}
            for seq, cnt in sequence_counts.most_common(10)
        ],
        "sequence_count": len(sequence_counts)
    }


def analyze_performance_patterns(records: List[Dict]) -> Dict[str, Any]:
    """Analyze performance patterns."""
    # Filter to end records with duration
    perf_records = [r for r in records 
                   if r.get("event_type") == "end" and r.get("duration_ms") is not None]
    
    if not perf_records:
        return {"analysis_type": "performance", "error": "No performance data available"}
    
    # Group by event type
    perf_by_event = {}
    for record in perf_records:
        event_name = record["event_name"]
        if event_name not in perf_by_event:
            perf_by_event[event_name] = []
        perf_by_event[event_name].append(record["duration_ms"])
    
    # Calculate stats per event type
    event_stats = {}
    for event_name, durations in perf_by_event.items():
        event_stats[event_name] = {
            "avg_ms": sum(durations) / len(durations),
            "min_ms": min(durations),
            "max_ms": max(durations),
            "count": len(durations)
        }
    
    return {
        "analysis_type": "performance",
        "event_performance": event_stats,
        "slowest_events": sorted(
            perf_records,
            key=lambda r: r["duration_ms"],
            reverse=True
        )[:10]
    }


def analyze_error_patterns(records: List[Dict]) -> Dict[str, Any]:
    """Analyze error patterns in observations."""
    # This would need to look at the result data for errors
    # For now, return a placeholder
    return {
        "analysis_type": "errors",
        "message": "Error analysis requires result data inspection",
        "total_records": len(records)
    }