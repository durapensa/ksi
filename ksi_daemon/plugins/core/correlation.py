#!/usr/bin/env python3
"""
Correlation Tracing Plugin

Provides correlation ID tracing functionality for debugging and monitoring
complex event chains in the KSI daemon system.
"""

from typing import Dict, Any, Optional
import pluggy

from ksi_daemon.plugin_utils import plugin_metadata, event_handler, create_ksi_describe_events_hook
from ksi_daemon import correlation
from ksi_common.logging import get_bound_logger

# Plugin metadata
plugin_metadata("correlation", version="1.0.0",
                description="Correlation ID tracing for event chain debugging")

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Module state
logger = get_bound_logger("correlation", version="1.0.0")

# Plugin info
PLUGIN_INFO = {
    "name": "correlation",
    "version": "1.0.0",
    "description": "Correlation ID tracing and monitoring"
}


@hookimpl
def ksi_startup(config):
    """Initialize correlation plugin."""
    logger.info("Correlation tracing plugin started")
    return {"plugin.correlation": {"loaded": True}}


@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Handle correlation-related events using decorated handlers."""
    
    # Look for decorated handlers
    import sys
    import inspect
    module = sys.modules[__name__]
    
    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj) and hasattr(obj, '_ksi_event_name'):
            if obj._ksi_event_name == event_name:
                return obj(data)
    
    return None


@event_handler("correlation:trace")
def handle_get_trace(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get a specific correlation trace.
    
    Parameters:
        correlation_id: The correlation ID to retrieve trace for
    
    Returns:
        Trace information including timing, data, and children
    """
    correlation_id = data.get("correlation_id")
    
    if not correlation_id:
        return {"error": "correlation_id required"}
    
    trace = correlation.get_trace(correlation_id)
    if not trace:
        return {"error": f"Trace {correlation_id} not found"}
    
    return {
        "correlation_id": trace.correlation_id,
        "parent_id": trace.parent_id,
        "event_name": trace.event_name,
        "created_at": trace.created_at,
        "completed_at": trace.completed_at,
        "duration_ms": (
            int((trace.completed_at - trace.created_at) * 1000) 
            if trace.completed_at else None
        ),
        "data": trace.data,
        "children": trace.children,
        "result": trace.result,
        "error": trace.error
    }


@event_handler("correlation:chain")
def handle_get_trace_chain(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get the full trace chain for a correlation ID.
    
    Parameters:
        correlation_id: The correlation ID to retrieve chain for
    
    Returns:
        Full chain of traces from root to leaf
    """
    correlation_id = data.get("correlation_id")
    
    if not correlation_id:
        return {"error": "correlation_id required"}
    
    chain = correlation.get_trace_chain(correlation_id)
    
    return {
        "correlation_id": correlation_id,
        "chain_length": len(chain),
        "chain": [
            {
                "correlation_id": trace.correlation_id,
                "parent_id": trace.parent_id,
                "event_name": trace.event_name,
                "created_at": trace.created_at,
                "completed_at": trace.completed_at,
                "duration_ms": (
                    int((trace.completed_at - trace.created_at) * 1000) 
                    if trace.completed_at else None
                ),
                "error": trace.error
            }
            for trace in chain
        ]
    }


@event_handler("correlation:tree")
def handle_get_trace_tree(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get the full trace tree for a correlation ID.
    
    Parameters:
        correlation_id: The correlation ID to retrieve tree for
    
    Returns:
        Hierarchical tree of all related traces
    """
    correlation_id = data.get("correlation_id")
    
    if not correlation_id:
        return {"error": "correlation_id required"}
    
    tree = correlation.get_trace_tree(correlation_id)
    
    return {
        "correlation_id": correlation_id,
        "tree": tree
    }


@event_handler("correlation:stats")
def handle_get_stats(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get correlation tracking statistics.
    
    Returns:
        Statistics about active and completed traces
    """
    stats = correlation.get_correlation_stats()
    
    return {
        "correlation_stats": stats
    }


@event_handler("correlation:cleanup")
def handle_cleanup(data: Dict[str, Any]) -> Dict[str, Any]:
    """Clean up old correlation traces.
    
    Parameters:
        max_age_hours: Maximum age in hours for traces to keep (default: 24)
    
    Returns:
        Number of traces cleaned up
    """
    max_age_hours = data.get("max_age_hours", 24)
    
    try:
        cleaned_count = correlation.cleanup_old_traces(max_age_hours)
        return {
            "cleaned_traces": cleaned_count,
            "max_age_hours": max_age_hours
        }
    except Exception as e:
        return {"error": str(e)}


@event_handler("correlation:current")
def handle_get_current(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get current correlation context.
    
    Returns:
        Current and parent correlation IDs
    """
    return {
        "current_correlation_id": correlation.get_current_correlation_id(),
        "parent_correlation_id": correlation.get_parent_correlation_id()
    }


@hookimpl
def ksi_shutdown():
    """Clean up on shutdown."""
    # Clean up old traces on shutdown
    try:
        cleaned_count = correlation.cleanup_old_traces(max_age_hours=1)  # Aggressive cleanup on shutdown
        logger.info(f"Cleaned up {cleaned_count} old traces on shutdown")
    except Exception as e:
        logger.error(f"Error cleaning up traces: {e}")
    
    logger.info("Correlation tracing plugin stopped")
    return {"plugin.correlation": {"stopped": True}}


# Module-level marker for plugin discovery
ksi_plugin = True

# Enable event discovery
ksi_describe_events = create_ksi_describe_events_hook(__name__)