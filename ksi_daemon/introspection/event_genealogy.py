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
        
        if result and isinstance(result, list) and result[0]:
            all_events = result[0].get("events", [])
            
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


# Export for discovery
__all__ = [
    "handle_event_chain_query",
    "handle_event_tree"
]