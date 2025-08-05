#!/usr/bin/env python3
"""
Event Genealogy Tracking System

Provides introspection into event chains, parent-child relationships,
and correlation tracking for debugging and analysis.
"""
import asyncio
from typing import Dict, Any, List, Optional, TypedDict
from typing_extensions import NotRequired, Required

from ksi_daemon.event_system import event_handler, get_router
# Removed event_format_linter import - BREAKING CHANGE: Direct TypedDict access
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_common.event_utils import extract_single_response
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("event_genealogy")


def _get_resolved_context(event: Dict[str, Any]) -> Dict[str, Any]:
    """Get resolved context from event (handles both references and full contexts).
    
    PYTHONIC CONTEXT REFACTOR: This helper handles the fact that _ksi_context
    might be a reference string or a full context dict.
    """
    # Check if we already resolved it
    if "_resolved_context" in event:
        return event["_resolved_context"]
    
    # Otherwise try to get it from data
    ksi_context_value = event.get("data", {}).get("_ksi_context")
    if isinstance(ksi_context_value, dict):
        return ksi_context_value
    
    # If it's a reference, we can't resolve it synchronously here
    # The caller should have pre-resolved all contexts
    return {}


# Reference to event router
event_router = None


class SystemContextData(TypedDict):
    """System context with runtime references."""
    emit_event: NotRequired[Any]  # Event emitter function
    shutdown_event: NotRequired[Any]  # Shutdown event object
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("system:context")
async def handle_context(data: SystemContextData, context: Optional[Dict[str, Any]] = None) -> None:
    """Receive module context with event router reference."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    global event_router
    event_router = get_router()
    logger.info("Event genealogy module received event router context")


class EventChainQueryData(TypedDict):
    """Query event chains by correlation ID or event ID."""
    correlation_id: NotRequired[str]  # Find all events in a correlation chain
    event_id: NotRequired[str]  # Find chain starting from specific event
    root_event_id: NotRequired[str]  # Find all events from a root
    include_children: NotRequired[bool]  # Include child events (default: True)
    max_depth: NotRequired[int]  # Maximum depth to traverse (default: -1 for unlimited)
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("introspection:event_chain")
async def handle_event_chain_query(data: EventChainQueryData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Query event chains by correlation ID or event ID."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    
    if not event_router or not hasattr(event_router, 'reference_event_log'):
        return error_response("Reference event log not available", context)
    
    try:
        correlation_id = data.get("correlation_id")
        event_id = data.get("event_id")
        root_event_id = data.get("root_event_id")
        include_children = data.get("include_children", True)
        max_depth = data.get("max_depth", -1)
        
        if not any([correlation_id, event_id, root_event_id]):
            return error_response(
                "Must provide correlation_id, event_id, or root_event_id",
                context
            )
        
        # Build event chain
        event_chain = await build_event_chain(
            correlation_id=correlation_id,
            event_id=event_id,
            root_event_id=root_event_id,
            include_children=include_children,
            max_depth=max_depth
        )
        
        return event_response_builder({
            "chain": event_chain,
            "total_events": len(event_chain),
            "query": {
                "correlation_id": correlation_id,
                "event_id": event_id,
                "root_event_id": root_event_id,
                "include_children": include_children,
                "max_depth": max_depth
            }
        }, context)
        
    except Exception as e:
        logger.error(f"Failed to query event chain: {e}")
        return error_response(f"Query failed: {str(e)}", context)


class EventTreeData(TypedDict):
    """Visualize event tree structure."""
    event_id: NotRequired[str]  # Root event to visualize from
    correlation_id: NotRequired[str]  # Visualize all events in correlation
    max_depth: NotRequired[int]  # Maximum depth (default: 5)
    format: NotRequired[str]  # Output format: "tree" or "graph" (default: "tree")
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("introspection:event_tree")
async def handle_event_tree(data: EventTreeData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Visualize event tree structure."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    
    if not event_router or not hasattr(event_router, 'reference_event_log'):
        return error_response("Reference event log not available", context)
    
    try:
        event_id = data.get("event_id")
        correlation_id = data.get("correlation_id")
        max_depth = data.get("max_depth", 5)
        output_format = data.get("format", "tree")
        
        if not event_id and not correlation_id:
            return error_response("Must provide event_id or correlation_id", context)
        
        # Build event tree structure
        if output_format == "tree":
            tree_output = await build_tree_visualization(
                event_id=event_id,
                correlation_id=correlation_id,
                max_depth=max_depth
            )
            return event_response_builder({
                "tree": tree_output,
                "format": "tree"
            }, context)
        else:
            graph_data = await build_graph_data(
                event_id=event_id,
                correlation_id=correlation_id,
                max_depth=max_depth
            )
            return event_response_builder({
                "graph": graph_data,
                "format": "graph"
            }, context)
            
    except Exception as e:
        logger.error(f"Failed to build event tree: {e}")
        return error_response(f"Tree generation failed: {str(e)}", context)


async def build_event_chain(
    correlation_id: Optional[str] = None,
    event_id: Optional[str] = None,
    root_event_id: Optional[str] = None,
    include_children: bool = True,
    max_depth: int = -1
) -> List[Dict[str, Any]]:
    """Build event chain from monitor events."""
    events = []
    event_map = {}
    
    # Use monitor:get_events to query events
    if not event_router:
        return []
    
    # Get all recent events (we'll filter them ourselves)
    try:
        result = await event_router.emit("monitor:get_events", {
            "limit": 1000,  # Get recent events
            "reverse": True
        })
        
        response = extract_single_response(result)
        if response:
            all_events = response.get("events", [])
            
            # Build event map for quick lookup
            # PYTHONIC CONTEXT REFACTOR: Resolve context references
            from ksi_daemon.core.context_manager import get_context_manager
            cm = get_context_manager()
            
            for event in all_events:
                # _ksi_context might be a reference or full context
                ksi_context_value = event.get("data", {}).get("_ksi_context")
                
                if isinstance(ksi_context_value, str) and ksi_context_value.startswith("ctx_"):
                    # It's a reference - resolve it
                    ksi_context = await cm.get_context(ksi_context_value) or {}
                elif isinstance(ksi_context_value, dict):
                    ksi_context = ksi_context_value
                else:
                    ksi_context = {}
                
                event_id = ksi_context.get("_event_id")
                if event_id:
                    # Store resolved context back in event for later use
                    event["_resolved_context"] = ksi_context
                    event_map[event_id] = event
            
            # Filter based on criteria
            if correlation_id:
                # Get all events with this correlation ID
                # PYTHONIC CONTEXT REFACTOR: Use resolved context
                events = [e for e in all_events if _get_resolved_context(e).get("_correlation_id") == correlation_id]
                events.sort(key=lambda e: _get_resolved_context(e).get("_event_timestamp", 0))
            
            elif event_id:
                # Start from specific event
                if event_id in event_map:
                    events.append(event_map[event_id])
                    
                    if include_children:
                        # Find all children recursively
                        children = _find_children_in_map(event_id, event_map, max_depth)
                        events.extend(children)
            
            elif root_event_id:
                # Find all events with this root
                # PYTHONIC CONTEXT REFACTOR: Use resolved context
                events = [e for e in all_events if _get_resolved_context(e).get("_root_event_id") == root_event_id]
                events.sort(key=lambda e: (
                    _get_resolved_context(e).get("_event_depth", 0),
                    _get_resolved_context(e).get("_event_timestamp", 0)
                ))
    
    except Exception as e:
        logger.error(f"Failed to query events: {e}")
    
    return events


async def build_tree_visualization(
    event_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    max_depth: int = 5
) -> str:
    """Build ASCII tree visualization of event hierarchy."""
    # Build event map
    events = await build_event_chain(
        correlation_id=correlation_id,
        event_id=event_id,
        include_children=True,
        max_depth=max_depth
    )
    
    if not events:
        return "No events found"
    
    # Build event map for tree construction
    # BREAKING CHANGE: Read from _ksi_context
    event_map = {}
    for e in events:
        event_id = _get_resolved_context(e).get("_event_id")
        if event_id:
            event_map[event_id] = e
    
    if correlation_id:
        # Find root events in correlation
        # PYTHONIC CONTEXT REFACTOR: Use resolved context
        roots = [e for e in events if _get_resolved_context(e).get("_event_depth", 0) == 0]
    else:
        # Start from specific event
        # PYTHONIC CONTEXT REFACTOR: Use resolved context
        roots = [e for e in events if _get_resolved_context(e).get("_event_id") == event_id]
        if not roots and events:
            roots = [events[0]]  # Fallback to first event
    
    output_lines = []
    for root in roots:
        await _build_tree_lines(root, output_lines, "", True, max_depth, event_map)
    
    return "\n".join(output_lines)


async def _build_tree_lines(
    event: Dict[str, Any],
    lines: List[str],
    prefix: str,
    is_last: bool,
    max_depth: int,
    event_map: Dict[str, Dict[str, Any]],
    current_depth: int = 0
):
    """Recursively build tree lines."""
    if max_depth >= 0 and current_depth > max_depth:
        return
    
    # Get event details
    # PYTHONIC CONTEXT REFACTOR: Use resolved context
    event_name = event.get("event_name", "unknown")
    ksi_context = _get_resolved_context(event)
    event_id = ksi_context.get("_event_id", "no-id")
    
    # Add current event
    connector = "└─ " if is_last else "├─ "
    lines.append(f"{prefix}{connector}{event_name} ({event_id})")
    
    # Add event details
    extension = "   " if is_last else "│  "
    details_prefix = prefix + extension
    
    # Add correlation info if present
    correlation_id = ksi_context.get("_correlation_id")
    if correlation_id:
        lines.append(f"{details_prefix}  Correlation: {correlation_id}")
    
    # Add depth info
    depth = ksi_context.get("_event_depth", 0)
    if depth > 0:
        lines.append(f"{details_prefix}  Depth: {depth}")
    
    # Find children
    children = await _find_direct_children_from_map(event_id, event_map)
    
    # Process children
    for i, child in enumerate(children):
        is_last_child = (i == len(children) - 1)
        await _build_tree_lines(
            child,
            lines,
            prefix + extension,
            is_last_child,
            max_depth,
            event_map,
            current_depth + 1
        )


async def build_graph_data(
    event_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    max_depth: int = 5
) -> Dict[str, Any]:
    """Build graph data structure for visualization."""
    nodes = []
    edges = []
    processed = set()
    
    if correlation_id:
        events = await build_event_chain(correlation_id=correlation_id)
    else:
        events = await build_event_chain(event_id=event_id, max_depth=max_depth)
    
    for event in events:
        # PYTHONIC CONTEXT REFACTOR: Use resolved context
        ksi_context = _get_resolved_context(event)
        evt_id = ksi_context.get('_event_id', '')
        if evt_id and evt_id not in processed:
            nodes.append({
                "id": evt_id,
                "label": event.get('event_name', 'unknown'),
                "depth": ksi_context.get('_event_depth', 0),
                "timestamp": ksi_context.get('_event_timestamp', 0),
                "correlation_id": ksi_context.get('_correlation_id')
            })
            processed.add(evt_id)
            
            # Add edge to parent
            parent_id = ksi_context.get('_parent_event_id')
            if parent_id:
                edges.append({
                    "from": parent_id,
                    "to": evt_id,
                    "label": "spawned"
                })
    
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "max_depth": max(n['depth'] for n in nodes) if nodes else 0
        }
    }


def _find_children_in_map(parent_id: str, event_map: Dict[str, Dict[str, Any]], max_depth: int, current_depth: int = 0) -> List[Dict[str, Any]]:
    """Find all child events recursively from event map."""
    if max_depth >= 0 and current_depth >= max_depth:
        return []
    
    children = []
    
    # Find direct children
    for event_id, event in event_map.items():
        # PYTHONIC CONTEXT REFACTOR: Use resolved context
        ksi_context = _get_resolved_context(event)
        if ksi_context.get("_parent_event_id") == parent_id:
            children.append(event)
            # Recursively find grandchildren
            grandchildren = _find_children_in_map(
                event_id,
                event_map,
                max_depth,
                current_depth + 1
            )
            children.extend(grandchildren)
    
    return children


async def _find_direct_children_from_map(parent_id: str, event_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Find direct child events from event map."""
    children = []
    
    for event_id, event in event_map.items():
        # PYTHONIC CONTEXT REFACTOR: Use resolved context
        ksi_context = _get_resolved_context(event)
        if ksi_context.get("_parent_event_id") == parent_id:
            children.append(event)
    
    # Sort by timestamp
    children.sort(key=lambda e: _get_resolved_context(e).get("_event_timestamp", 0))
    return children


# ===== REAL-TIME MONITORING ENHANCEMENTS =====

class EventStreamData(TypedDict):
    """Real-time event stream monitoring."""
    patterns: NotRequired[List[str]]  # Event patterns to monitor (e.g., ["agent:*", "completion:*"])
    duration: NotRequired[int]  # How long to monitor in seconds (default: 60)
    max_events: NotRequired[int]  # Maximum events to capture (default: 100)
    include_context: NotRequired[bool]  # Include full context resolution (default: False)
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("introspection:event_stream")
async def handle_event_stream(data: EventStreamData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Start real-time event monitoring stream."""
    if not event_router:
        return error_response("Event router not available", context)
    
    try:
        patterns = data.get("patterns", ["*"])  # Monitor all by default
        duration = data.get("duration", 60)
        max_events = data.get("max_events", 100)
        include_context = data.get("include_context", False)
        
        # Create monitoring task
        captured_events = []
        start_time = asyncio.get_event_loop().time()
        
        # Monitor for specified duration
        while (asyncio.get_event_loop().time() - start_time) < duration and len(captured_events) < max_events:
            # Get recent events
            result = await event_router.emit("monitor:get_events", {
                "limit": 10,
                "reverse": True
            })
            
            response = extract_single_response(result)
            if response:
                events = response.get("events", [])
                
                for event in events:
                    # Check if event matches patterns
                    event_name = event.get("event_name", "")
                    if any(_matches_pattern(event_name, pattern) for pattern in patterns):
                        # Resolve context if requested
                        if include_context:
                            ksi_context_value = event.get("data", {}).get("_ksi_context")
                            if isinstance(ksi_context_value, str) and ksi_context_value.startswith("ctx_"):
                                from ksi_daemon.core.context_manager import get_context_manager
                                cm = get_context_manager()
                                ksi_context = await cm.get_context(ksi_context_value) or {}
                                event["_resolved_context"] = ksi_context
                        
                        # Check if we already captured this event
                        event_id = _get_resolved_context(event).get("_event_id")
                        if not any(e.get("_resolved_context", {}).get("_event_id") == event_id for e in captured_events):
                            captured_events.append(event)
            
            # Short delay between checks
            await asyncio.sleep(0.5)
        
        # Sort by timestamp
        captured_events.sort(key=lambda e: _get_resolved_context(e).get("_event_timestamp", 0))
        
        return event_response_builder({
            "events": captured_events,
            "total_captured": len(captured_events),
            "monitoring_duration": duration,
            "patterns": patterns,
            "context_resolved": include_context
        }, context)
        
    except Exception as e:
        logger.error(f"Failed to stream events: {e}")
        return error_response(f"Stream failed: {str(e)}", context)


# ===== IMPACT ANALYSIS ENHANCEMENTS =====

class ImpactAnalysisData(TypedDict):
    """Analyze the impact/cascade of events."""
    event_id: str  # Event to analyze impact from
    max_depth: NotRequired[int]  # Maximum cascade depth (default: 5)
    time_window: NotRequired[int]  # Time window in seconds (default: 300)
    include_indirect: NotRequired[bool]  # Include indirect impacts (default: True)
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("introspection:impact_analysis")
async def handle_impact_analysis(data: ImpactAnalysisData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Analyze the cascading impact of an event."""
    if not event_router:
        return error_response("Event router not available", context)
    
    try:
        event_id = data.get("event_id")
        max_depth = data.get("max_depth", 5)
        time_window = data.get("time_window", 300)
        include_indirect = data.get("include_indirect", True)
        
        if not event_id:
            return error_response("event_id is required", context)
        
        # Build impact tree
        impact_tree = await _build_impact_tree(event_id, max_depth, time_window, include_indirect)
        
        # Calculate impact metrics
        metrics = await _calculate_impact_metrics(impact_tree)
        
        return event_response_builder({
            "source_event_id": event_id,
            "impact_tree": impact_tree,
            "metrics": metrics,
            "analysis_params": {
                "max_depth": max_depth,
                "time_window": time_window,
                "include_indirect": include_indirect
            }
        }, context)
        
    except Exception as e:
        logger.error(f"Failed to analyze impact: {e}")
        return error_response(f"Impact analysis failed: {str(e)}", context)


# ===== PERFORMANCE ANALYSIS ENHANCEMENTS =====

class PerformanceAnalysisData(TypedDict):
    """Analyze event performance and timing."""
    correlation_id: NotRequired[str]  # Analyze specific correlation
    event_patterns: NotRequired[List[str]]  # Event patterns to analyze
    time_range: NotRequired[int]  # Time range in seconds (default: 3600)
    group_by: NotRequired[str]  # Group by: "event_type", "agent", "correlation" (default: "event_type")
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("introspection:performance_analysis")
async def handle_performance_analysis(data: PerformanceAnalysisData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Analyze event performance and timing patterns."""
    if not event_router:
        return error_response("Event router not available", context)
    
    try:
        correlation_id = data.get("correlation_id")
        event_patterns = data.get("event_patterns", ["*"])
        time_range = data.get("time_range", 3600)
        group_by = data.get("group_by", "event_type")
        
        # Collect events for analysis
        if correlation_id:
            events = await build_event_chain(correlation_id=correlation_id)
        else:
            # Get recent events matching patterns
            result = await event_router.emit("monitor:get_events", {
                "limit": 1000,
                "reverse": True
            })
            
            events = []
            response = extract_single_response(result)
            if response:
                all_events = response.get("events", [])
                current_time = asyncio.get_event_loop().time()
                
                # Resolve contexts and filter
                from ksi_daemon.core.context_manager import get_context_manager
                cm = get_context_manager()
                
                for event in all_events:
                    # Check time window
                    ksi_context_value = event.get("data", {}).get("_ksi_context")
                    if isinstance(ksi_context_value, str) and ksi_context_value.startswith("ctx_"):
                        ksi_context = await cm.get_context(ksi_context_value) or {}
                        event["_resolved_context"] = ksi_context
                    
                    event_time = _get_resolved_context(event).get("_event_timestamp", 0)
                    if current_time - event_time <= time_range:
                        # Check pattern match
                        event_name = event.get("event_name", "")
                        if any(_matches_pattern(event_name, pattern) for pattern in event_patterns):
                            events.append(event)
        
        # Analyze performance
        performance_data = await _analyze_event_performance(events, group_by)
        
        return event_response_builder({
            "performance_data": performance_data,
            "analysis_params": {
                "correlation_id": correlation_id,
                "event_patterns": event_patterns,
                "time_range": time_range,
                "group_by": group_by,
                "total_events_analyzed": len(events)
            }
        }, context)
        
    except Exception as e:
        logger.error(f"Failed to analyze performance: {e}")
        return error_response(f"Performance analysis failed: {str(e)}", context)


# ===== HELPER FUNCTIONS FOR ENHANCEMENTS =====

def _matches_pattern(event_name: str, pattern: str) -> bool:
    """Check if event name matches pattern (supports * wildcards)."""
    import fnmatch
    return fnmatch.fnmatch(event_name, pattern)


async def _build_impact_tree(event_id: str, max_depth: int, time_window: int, include_indirect: bool) -> Dict[str, Any]:
    """Build tree of events impacted by the source event."""
    # Get the source event first
    result = await event_router.emit("monitor:get_events", {"limit": 1000, "reverse": True})
    
    response = extract_single_response(result)
    if not response:
        return {"error": "Could not retrieve events"}
    
    all_events = response.get("events", [])
    event_map = {}
    
    # Resolve contexts and build event map
    from ksi_daemon.core.context_manager import get_context_manager
    cm = get_context_manager()
    
    for event in all_events:
        ksi_context_value = event.get("data", {}).get("_ksi_context")
        if isinstance(ksi_context_value, str) and ksi_context_value.startswith("ctx_"):
            ksi_context = await cm.get_context(ksi_context_value) or {}
            event["_resolved_context"] = ksi_context
        
        evt_id = _get_resolved_context(event).get("_event_id")
        if evt_id:
            event_map[evt_id] = event
    
    # Find source event
    if event_id not in event_map:
        return {"error": f"Source event {event_id} not found"}
    
    source_event = event_map[event_id]
    source_time = _get_resolved_context(source_event).get("_event_timestamp", 0)
    
    # Build impact tree recursively
    impact_tree = {
        "event_id": event_id,
        "event_name": source_event.get("event_name", "unknown"),
        "timestamp": source_time,
        "direct_impacts": [],
        "indirect_impacts": []
    }
    
    await _collect_impacts(event_id, impact_tree, event_map, source_time, time_window, max_depth, 0)
    
    return impact_tree


async def _collect_impacts(parent_id: str, parent_node: Dict[str, Any], event_map: Dict[str, Dict[str, Any]], 
                          source_time: float, time_window: int, max_depth: int, current_depth: int):
    """Recursively collect impact events."""
    if current_depth >= max_depth:
        return
    
    direct_children = []
    
    # Find direct children
    for evt_id, event in event_map.items():
        ksi_context = _get_resolved_context(event)
        if ksi_context.get("_parent_event_id") == parent_id:
            event_time = ksi_context.get("_event_timestamp", 0)
            if event_time - source_time <= time_window:  # Within time window
                child_node = {
                    "event_id": evt_id,
                    "event_name": event.get("event_name", "unknown"),
                    "timestamp": event_time,
                    "depth": current_depth + 1,
                    "direct_impacts": []
                }
                direct_children.append(child_node)
                
                # Recursively find impacts of this child
                await _collect_impacts(evt_id, child_node, event_map, source_time, time_window, max_depth, current_depth + 1)
    
    parent_node["direct_impacts"] = direct_children


async def _calculate_impact_metrics(impact_tree: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate metrics about the impact tree."""
    def count_impacts(node):
        total = len(node.get("direct_impacts", []))
        for child in node.get("direct_impacts", []):
            total += count_impacts(child)
        return total
    
    def max_depth(node, current=0):
        if not node.get("direct_impacts"):
            return current
        return max(max_depth(child, current + 1) for child in node["direct_impacts"])
    
    total_impacts = count_impacts(impact_tree)
    cascade_depth = max_depth(impact_tree)
    
    return {
        "total_impacted_events": total_impacts,
        "cascade_depth": cascade_depth,
        "direct_impacts": len(impact_tree.get("direct_impacts", [])),
        "has_cascading_effects": cascade_depth > 1
    }


async def _analyze_event_performance(events: List[Dict[str, Any]], group_by: str) -> Dict[str, Any]:
    """Analyze performance characteristics of events."""
    groups = {}
    
    for event in events:
        ksi_context = _get_resolved_context(event)
        
        # Determine grouping key
        if group_by == "event_type":
            key = event.get("event_name", "unknown")
        elif group_by == "agent":
            key = ksi_context.get("_agent_id", "system")
        elif group_by == "correlation":
            key = ksi_context.get("_correlation_id", "no-correlation")
        else:
            key = "all"
        
        if key not in groups:
            groups[key] = {
                "count": 0,
                "timestamps": [],
                "depths": [],
                "events": []
            }
        
        groups[key]["count"] += 1
        groups[key]["timestamps"].append(ksi_context.get("_event_timestamp", 0))
        groups[key]["depths"].append(ksi_context.get("_event_depth", 0))
        groups[key]["events"].append(event)
    
    # Calculate statistics for each group
    analysis = {}
    for group_key, group_data in groups.items():
        timestamps = sorted(group_data["timestamps"])
        depths = group_data["depths"]
        
        # Calculate intervals between events
        intervals = []
        for i in range(1, len(timestamps)):
            intervals.append(timestamps[i] - timestamps[i-1])
        
        analysis[group_key] = {
            "event_count": group_data["count"],
            "avg_interval": sum(intervals) / len(intervals) if intervals else 0,
            "min_interval": min(intervals) if intervals else 0,
            "max_interval": max(intervals) if intervals else 0,
            "avg_depth": sum(depths) / len(depths) if depths else 0,
            "max_depth": max(depths) if depths else 0,
            "time_span": timestamps[-1] - timestamps[0] if len(timestamps) > 1 else 0,
            "frequency": group_data["count"] / (timestamps[-1] - timestamps[0]) if len(timestamps) > 1 and timestamps[-1] != timestamps[0] else 0
        }
    
    return analysis


# Export for discovery
__all__ = [
    "handle_event_chain_query",
    "handle_event_tree",
    "handle_event_stream", 
    "handle_impact_analysis",
    "handle_performance_analysis"
]