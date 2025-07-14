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
async def handle_startup(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Initialize correlation plugin."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder
    data = event_format_linter(raw_data, SystemStartupData)
    
    logger.info("Correlation tracing module started")
    return event_response_builder(
        {"module.correlation": {"loaded": True}},
        context=context
    )


@event_handler("correlation:trace")
async def handle_get_trace(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get a specific correlation trace."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, CorrelationTraceData)
    
    correlation_id = data.get("correlation_id")
    
    if not correlation_id:
        return error_response(
            "correlation_id required",
            context=context
        )
    
    trace = correlation.get_trace(correlation_id)
    if not trace:
        return error_response(
            f"Trace {correlation_id} not found",
            context=context
        )
    
    return event_response_builder(
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
            "data": trace.data,
            "children": trace.children,
            "result": trace.result,
            "error": trace.error
        },
        context=context
    )


@event_handler("correlation:chain")
async def handle_get_trace_chain(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get the full trace chain for a correlation ID."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, CorrelationChainData)
    
    correlation_id = data.get("correlation_id")
    
    if not correlation_id:
        return error_response(
            "correlation_id required",
            context=context
        )
    
    chain = correlation.get_trace_chain(correlation_id)
    
    return event_response_builder(
        {
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
        },
        context=context
    )


@event_handler("correlation:tree")
async def handle_get_trace_tree(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get the full trace tree for a correlation ID."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, CorrelationTreeData)
    
    correlation_id = data.get("correlation_id")
    
    if not correlation_id:
        return error_response(
            "correlation_id required",
            context=context
        )
    
    tree = correlation.get_trace_tree(correlation_id)
    
    return event_response_builder(
        {
            "correlation_id": correlation_id,
            "tree": tree
        },
        context=context
    )


@event_handler("correlation:stats")
async def handle_get_stats(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get correlation tracking statistics."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder
    data = event_format_linter(raw_data, CorrelationStatsData)
    
    stats = correlation.get_correlation_stats()
    
    return event_response_builder(
        {
            "correlation_stats": stats
        },
        context=context
    )


@event_handler("correlation:cleanup")
async def handle_cleanup(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Clean up old correlation traces."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, CorrelationCleanupData)
    
    max_age_hours = data.get("max_age_hours", 24)
    
    try:
        cleaned_count = correlation.cleanup_old_traces(max_age_hours)
        return event_response_builder(
            {
                "cleaned_traces": cleaned_count,
                "max_age_hours": max_age_hours
            },
            context=context
        )
    except Exception as e:
        return error_response(
            str(e),
            context=context
        )


@event_handler("correlation:current")
async def handle_get_current(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get current correlation context."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder
    data = event_format_linter(raw_data, CorrelationCurrentData)
    
    return event_response_builder(
        {
            "current_correlation_id": correlation.get_current_correlation_id(),
            "parent_correlation_id": correlation.get_parent_correlation_id()
        },
        context=context
    )


@event_handler("system:shutdown")
async def handle_shutdown(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Clean up on shutdown."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder
    data = event_format_linter(raw_data, SystemShutdownData)
    
    # Clean up old traces on shutdown
    try:
        cleaned_count = correlation.cleanup_old_traces(max_age_hours=1)  # Aggressive cleanup on shutdown
        logger.info(f"Cleaned up {cleaned_count} old traces on shutdown")
    except Exception as e:
        logger.error(f"Error cleaning up traces: {e}")
    
    logger.info("Correlation tracing module stopped")
    return event_response_builder(
        {"module.correlation": {"stopped": True}},
        context=context
    )


