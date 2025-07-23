#!/usr/bin/env python3
"""
Context-aware event emission utilities.

Provides functions that automatically propagate correlation IDs and parent event IDs
through the event system, enabling complete event tracing and genealogy.
"""
from typing import Any, Dict, Optional, Callable
from functools import wraps

from ksi_common.logging import get_bound_logger

logger = get_bound_logger("context_aware_emit")


def create_context_aware_emitter(emit_func: Callable, current_context: Dict[str, Any]) -> Callable:
    """Create an event emitter that automatically propagates context.
    
    This function wraps an event emitter to automatically propagate:
    - Correlation ID from the current event chain
    - Parent event ID (current event becomes parent of emitted events)
    - Root event ID and depth tracking
    
    Args:
        emit_func: The base emit function (e.g., router.emit)
        current_context: The context from the current event handler
        
    Returns:
        A wrapped emit function that propagates context
    """
    @wraps(emit_func)
    async def context_aware_emit(event: str, data: Any = None, context: Optional[Dict[str, Any]] = None) -> Any:
        """Emit an event with automatic context propagation."""
        if data is None:
            data = {}
            
        # Create new context if not provided
        if context is None:
            context = {}
        
        # Extract current event metadata from enhanced_data if available
        current_event_id = None
        current_correlation_id = None
        current_root_event_id = None
        current_event_depth = 0
        
        # Look for metadata in the current context
        if current_context:
            current_event_id = current_context.get("_current_event_id")
            current_correlation_id = current_context.get("_correlation_id")
            current_root_event_id = current_context.get("_root_event_id")
            current_event_depth = current_context.get("_event_depth", 0)
        
        # Propagate correlation ID
        if current_correlation_id and "_correlation_id" not in context:
            context["_correlation_id"] = current_correlation_id
            
        # Set parent event ID (current event becomes parent)
        if current_event_id and "_parent_event_id" not in context:
            context["_parent_event_id"] = current_event_id
            context["_root_event_id"] = current_root_event_id or current_event_id
            context["_event_depth"] = current_event_depth + 1
            
        # Call the original emit function with enriched context
        return await emit_func(event, data, context)
    
    return context_aware_emit


def extract_current_event_metadata(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract current event metadata for context propagation.
    
    Args:
        raw_data: The raw event data containing system metadata
        context: The event context
        
    Returns:
        Dictionary with current event metadata for propagation
    """
    metadata = {}
    
    # PYTHONIC CONTEXT REFACTOR: Metadata now comes from context dict
    # The event system populates context with metadata, _ksi_context is just a reference
    if context:
        if "_event_id" in context:
            metadata["_current_event_id"] = context["_event_id"]
        if "_correlation_id" in context:
            metadata["_correlation_id"] = context["_correlation_id"]
        if "_root_event_id" in context:
            metadata["_root_event_id"] = context["_root_event_id"]
        if "_event_depth" in context:
            metadata["_event_depth"] = context["_event_depth"]
    
    # Note: We no longer extract from raw_data["_ksi_context"] as it's now just a reference
    # All metadata is propagated through the context parameter
            
    return metadata


def update_handler_context(func: Callable) -> Callable:
    """Decorator to automatically create context-aware emitter for handlers.
    
    This decorator extracts event metadata and creates a context-aware emitter
    that handlers can use to emit events with proper genealogy tracking.
    
    Usage:
        @event_handler("my:event")
        @update_handler_context
        async def my_handler(data, context):
            # Use context["emit_event"] which automatically propagates IDs
            await context["emit_event"]("another:event", {"foo": "bar"})
    """
    @wraps(func)
    async def wrapper(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None):
        if context is None:
            context = {}
            
        # Extract current event metadata
        event_metadata = extract_current_event_metadata(data, context)
        
        # Add metadata to context for propagation
        context.update(event_metadata)
        
        # If there's an emit_event in context, wrap it
        if "emit_event" in context:
            context["emit_event"] = create_context_aware_emitter(
                context["emit_event"], 
                event_metadata
            )
            
        # Call the original handler
        return await func(data, context)
    
    return wrapper