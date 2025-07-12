#!/usr/bin/env python3
"""
Correlation Tracing Module - Event-Based Version

Provides correlation ID tracing functionality for debugging and monitoring
complex event chains in the KSI daemon system.
"""

from typing import Dict, Any, Optional, TypedDict
from typing_extensions import NotRequired, Required

from ksi_daemon.event_system import event_handler
from ksi_daemon import correlation
from ksi_common.logging import get_bound_logger

# Module state
logger = get_bound_logger("correlation", version="1.0.0")


# TypedDict definitions for event handlers

class SystemStartupData(TypedDict):
    """System startup configuration."""
    # No specific fields required for correlation module
    pass


class CorrelationTraceData(TypedDict):
    """Get a specific correlation trace."""
    correlation_id: Required[str]  # Correlation ID to retrieve trace for


class CorrelationChainData(TypedDict):
    """Get the full trace chain for a correlation ID."""
    correlation_id: Required[str]  # Correlation ID to retrieve chain for


class CorrelationTreeData(TypedDict):
    """Get the full trace tree for a correlation ID."""
    correlation_id: Required[str]  # Correlation ID to retrieve tree for


class CorrelationStatsData(TypedDict):
    """Get correlation tracking statistics."""
    # No specific fields - returns all statistics
    pass


class CorrelationCleanupData(TypedDict):
    """Clean up old correlation traces."""
    max_age_hours: NotRequired[int]  # Maximum age in hours for traces to keep (default: 24)


class CorrelationCurrentData(TypedDict):
    """Get current correlation context."""
    # No specific fields - returns current context
    pass


class SystemShutdownData(TypedDict):
    """System shutdown notification."""
    # No specific fields for shutdown
    pass

# Module info
MODULE_INFO = {
    "name": "correlation",
    "version": "1.0.0",
    "description": "Correlation ID tracing and monitoring"
}


@event_handler("system:startup")
async def handle_startup(config: SystemStartupData) -> Dict[str, Any]:
    """Initialize correlation plugin."""
    logger.info("Correlation tracing module started")
    return {"module.correlation": {"loaded": True}}


@event_handler("correlation:trace")
async def handle_get_trace(data: CorrelationTraceData) -> Dict[str, Any]:
    """Get a specific correlation trace."""
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
async def handle_get_trace_chain(data: CorrelationChainData) -> Dict[str, Any]:
    """Get the full trace chain for a correlation ID."""
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
async def handle_get_trace_tree(data: CorrelationTreeData) -> Dict[str, Any]:
    """Get the full trace tree for a correlation ID."""
    correlation_id = data.get("correlation_id")
    
    if not correlation_id:
        return {"error": "correlation_id required"}
    
    tree = correlation.get_trace_tree(correlation_id)
    
    return {
        "correlation_id": correlation_id,
        "tree": tree
    }


@event_handler("correlation:stats")
async def handle_get_stats(data: CorrelationStatsData) -> Dict[str, Any]:
    """Get correlation tracking statistics."""
    stats = correlation.get_correlation_stats()
    
    return {
        "correlation_stats": stats
    }


@event_handler("correlation:cleanup")
async def handle_cleanup(data: CorrelationCleanupData) -> Dict[str, Any]:
    """Clean up old correlation traces."""
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
async def handle_get_current(data: CorrelationCurrentData) -> Dict[str, Any]:
    """Get current correlation context."""
    return {
        "current_correlation_id": correlation.get_current_correlation_id(),
        "parent_correlation_id": correlation.get_parent_correlation_id()
    }


@event_handler("system:shutdown")
async def handle_shutdown(data: SystemShutdownData) -> Dict[str, Any]:
    """Clean up on shutdown."""
    # Clean up old traces on shutdown
    try:
        cleaned_count = correlation.cleanup_old_traces(max_age_hours=1)  # Aggressive cleanup on shutdown
        logger.info(f"Cleaned up {cleaned_count} old traces on shutdown")
    except Exception as e:
        logger.error(f"Error cleaning up traces: {e}")
    
    logger.info("Correlation tracing module stopped")
    return {"module.correlation": {"stopped": True}}


