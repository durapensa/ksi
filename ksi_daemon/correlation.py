#!/usr/bin/env python3
"""
Correlation ID Infrastructure for Event Tracing

Provides systematic correlation ID management for tracing complex event chains
across the entire KSI daemon system.
"""

import uuid
import threading
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from contextvars import ContextVar
import structlog
from ksi_common.logging import get_bound_logger

# Thread-local correlation context
_correlation_context: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
_parent_context: ContextVar[Optional[str]] = ContextVar('parent_correlation_id', default=None)

# Global correlation tracker
_correlation_tracker: Dict[str, Dict[str, Any]] = {}
_tracker_lock = threading.Lock()


@dataclass
class CorrelationTrace:
    """Represents a correlation trace with parent-child relationships."""
    correlation_id: str
    parent_id: Optional[str] = None
    event_name: str = ""
    created_at: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)
    children: List[str] = field(default_factory=list)
    completed_at: Optional[float] = None
    result: Optional[Any] = None
    error: Optional[str] = None


# Removed generate_correlation_id - use str(uuid.uuid4()) directly


def get_current_correlation_id() -> Optional[str]:
    """Get the current correlation ID from context."""
    return _correlation_context.get()


def get_parent_correlation_id() -> Optional[str]:
    """Get the parent correlation ID from context."""
    return _parent_context.get()


def set_correlation_context(correlation_id: Optional[str], parent_id: Optional[str] = None):
    """Set the correlation context for the current execution."""
    _correlation_context.set(correlation_id)
    _parent_context.set(parent_id)


def ensure_correlation_id(provided_id: Optional[str] = None, parent_id: Optional[str] = None) -> str:
    """
    Ensure we have a correlation ID, generating one if needed.
    
    Args:
        provided_id: Explicitly provided correlation ID
        parent_id: Parent correlation ID for chaining
        
    Returns:
        The correlation ID to use
    """
    if provided_id:
        correlation_id = provided_id
    else:
        # Check context first
        correlation_id = get_current_correlation_id()
        if not correlation_id:
            # Generate new ID
            correlation_id = str(uuid.uuid4())
    
    # Set context if not already set
    if get_current_correlation_id() != correlation_id:
        # Determine parent - use provided parent_id or current correlation as parent
        if not parent_id:
            parent_id = get_current_correlation_id()
        
        set_correlation_context(correlation_id, parent_id)
    
    return correlation_id


def start_trace(event_name: str, data: Dict[str, Any], 
                correlation_id: Optional[str] = None,
                parent_id: Optional[str] = None) -> str:
    """
    Start a new correlation trace.
    
    Args:
        event_name: Name of the event being traced
        data: Event data (will be sanitized)
        correlation_id: Optional correlation ID
        parent_id: Optional parent correlation ID
        
    Returns:
        The correlation ID for this trace
    """
    # Ensure we have a correlation ID
    trace_id = ensure_correlation_id(correlation_id, parent_id)
    
    # Get the effective parent
    effective_parent = parent_id or get_parent_correlation_id()
    
    # Create trace record
    trace = CorrelationTrace(
        correlation_id=trace_id,
        parent_id=effective_parent,
        event_name=event_name,
        data=_sanitize_data(data)
    )
    
    # Store in tracker
    with _tracker_lock:
        _correlation_tracker[trace_id] = trace
        
        # Add to parent's children if parent exists
        if effective_parent and effective_parent in _correlation_tracker:
            parent_trace = _correlation_tracker[effective_parent]
            if trace_id not in parent_trace.children:
                parent_trace.children.append(trace_id)
    
    return trace_id


def complete_trace(correlation_id: str, result: Any = None, error: Optional[str] = None):
    """
    Complete a correlation trace.
    
    Args:
        correlation_id: The correlation ID to complete
        result: Optional result data
        error: Optional error message
    """
    with _tracker_lock:
        if correlation_id in _correlation_tracker:
            trace = _correlation_tracker[correlation_id]
            trace.completed_at = time.time()
            trace.result = _sanitize_data(result) if result else None
            trace.error = error


def get_trace(correlation_id: str) -> Optional[CorrelationTrace]:
    """Get a correlation trace by ID."""
    with _tracker_lock:
        return _correlation_tracker.get(correlation_id)


def get_trace_chain(correlation_id: str) -> List[CorrelationTrace]:
    """
    Get the full trace chain for a correlation ID.
    
    Returns a list of traces from root to the specified correlation ID.
    """
    traces = []
    current_id = correlation_id
    
    with _tracker_lock:
        # Build chain by following parent links
        visited = set()
        while current_id and current_id not in visited:
            visited.add(current_id)
            trace = _correlation_tracker.get(current_id)
            if trace:
                traces.insert(0, trace)  # Insert at beginning to get root-to-leaf order
                current_id = trace.parent_id
            else:
                break
    
    return traces


def get_trace_tree(correlation_id: str) -> Dict[str, Any]:
    """
    Get the full trace tree for a correlation ID (including all children).
    
    Returns a nested dictionary representing the trace tree.
    """
    def build_tree(trace_id: str) -> Dict[str, Any]:
        trace = _correlation_tracker.get(trace_id)
        if not trace:
            return {"error": f"Trace {trace_id} not found"}
        
        return {
            "correlation_id": trace.correlation_id,
            "event_name": trace.event_name,
            "created_at": trace.created_at,
            "completed_at": trace.completed_at,
            "duration_ms": (
                int((trace.completed_at - trace.created_at) * 1000) 
                if trace.completed_at else None
            ),
            "error": trace.error,
            "children": [build_tree(child_id) for child_id in trace.children]
        }
    
    with _tracker_lock:
        return build_tree(correlation_id)


def cleanup_old_traces(max_age_hours: int = 24):
    """Clean up traces older than max_age_hours."""
    cutoff_time = time.time() - (max_age_hours * 3600)
    
    with _tracker_lock:
        expired_ids = [
            trace_id for trace_id, trace in _correlation_tracker.items()
            if trace.created_at < cutoff_time
        ]
        
        for trace_id in expired_ids:
            del _correlation_tracker[trace_id]
    
    return len(expired_ids)


def get_correlation_stats() -> Dict[str, Any]:
    """Get correlation tracking statistics."""
    with _tracker_lock:
        total_traces = len(_correlation_tracker)
        completed_traces = sum(1 for trace in _correlation_tracker.values() if trace.completed_at)
        error_traces = sum(1 for trace in _correlation_tracker.values() if trace.error)
        
        return {
            "total_traces": total_traces,
            "completed_traces": completed_traces,
            "active_traces": total_traces - completed_traces,
            "error_traces": error_traces,
            "success_rate": (completed_traces - error_traces) / max(completed_traces, 1)
        }


def _sanitize_data(data: Any) -> Any:
    """
    Sanitize data for storage in traces.
    
    Removes sensitive information and limits data size.
    """
    if data is None:
        return None
    
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            # Skip potentially sensitive keys
            if any(sensitive in key.lower() for sensitive in ['password', 'token', 'secret', 'key', 'auth']):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = _sanitize_data(value)
        return sanitized
    
    elif isinstance(data, (list, tuple)):
        return [_sanitize_data(item) for item in data[:10]]  # Limit list size
    
    elif isinstance(data, str):
        return data[:1000]  # Limit string length
    
    else:
        return data


def get_correlation_logger(name: str):
    """
    Get a logger that automatically includes correlation ID in all log messages.
    
    Args:
        name: Logger name
        
    Returns:
        A bound logger with correlation context
    """
    logger = get_bound_logger(name, correlation_enabled=True)
    
    # Bind correlation context
    correlation_id = get_current_correlation_id()
    parent_id = get_parent_correlation_id()
    
    bound_fields = {}
    if correlation_id:
        bound_fields["correlation_id"] = correlation_id
    if parent_id:
        bound_fields["parent_correlation_id"] = parent_id
    
    return logger.bind(**bound_fields) if bound_fields else logger


# Decorator for automatic correlation tracing
def trace_event(event_name: Optional[str] = None):
    """
    Decorator to automatically trace function calls with correlation IDs.
    
    Args:
        event_name: Optional event name (defaults to function name)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Determine event name
            trace_event_name = event_name or f"{func.__module__}.{func.__name__}"
            
            # Start trace
            correlation_id = start_trace(
                event_name=trace_event_name,
                data={"args_count": len(args), "kwargs_keys": list(kwargs.keys())}
            )
            
            try:
                result = func(*args, **kwargs)
                complete_trace(correlation_id, result={"success": True})
                return result
            except Exception as e:
                complete_trace(correlation_id, error=str(e))
                raise
        
        async def async_wrapper(*args, **kwargs):
            # Determine event name
            trace_event_name = event_name or f"{func.__module__}.{func.__name__}"
            
            # Start trace
            correlation_id = start_trace(
                event_name=trace_event_name,
                data={"args_count": len(args), "kwargs_keys": list(kwargs.keys())}
            )
            
            try:
                result = await func(*args, **kwargs)
                complete_trace(correlation_id, result={"success": True})
                return result
            except Exception as e:
                complete_trace(correlation_id, error=str(e))
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
    
    return decorator