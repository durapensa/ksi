#!/usr/bin/env python3
"""
Event response builder for KSI event handlers.

Provides utilities for event handlers to create responses in standardized format
that includes originator information and processing metadata. This ensures all
event responses have consistent structure while preserving handler-specific data.

Usage:
    from ksi_common.event_response_builder import event_response_builder, async_response
    
    # In an event handler:
    return event_response_builder(
        {"result": "success"},
        handler_name="my_handler",
        event_name="my:event",
        context=context
    )
"""
from typing import Any, Dict, Optional, Union


def event_response_builder(
    data: Any,
    context: Optional[Dict[str, Any]] = None,
    include_metadata: bool = True
) -> Dict[str, Any]:
    """Build a standardized response for event handlers.
    
    Creates a response that includes:
    - The actual response data
    - Processing metadata (status, timestamps)
    - System metadata from context
    
    Args:
        data: The actual response data (can be dict, list, string, etc.)
        context: Event context containing system metadata
        include_metadata: Whether to include processing metadata
        
    Returns:
        Standardized response dictionary
    """
    # Start with the data
    if isinstance(data, dict):
        response = data.copy()
    else:
        # Wrap non-dict data
        response = {"result": data}
    
    # Add processing metadata if requested
    if include_metadata:
        # Only set default status if not already set
        if "status" not in response:
            response["status"] = "success"  # Default status
        
        # BREAKING CHANGE: Package metadata into _ksi_context instead of flat fields
        import time
        import uuid
        ksi_context = {
            "_timestamp": time.time(),
            "_response_id": f"resp_{uuid.uuid4().hex[:8]}"
        }
        
        # Extract and add system metadata from context
        if context:
            # Copy system metadata fields from context to _ksi_context
            for field in ["_event_id", "_correlation_id", "_parent_event_id", 
                         "_root_event_id", "_event_depth", "_client_id", "_agent_id"]:
                if field in context:
                    ksi_context[field] = context[field]
        
        # Add _ksi_context to response
        response["_ksi_context"] = ksi_context
    
    return response


def success_response(
    data: Any = None,
    context: Optional[Dict[str, Any]] = None,
    message: str = None
) -> Dict[str, Any]:
    """Build a success response.
    
    Args:
        data: Optional response data
        context: Event context with system metadata
        message: Optional success message
        
    Returns:
        Success response dict
    """
    response_data = {}
    
    if data is not None:
        if isinstance(data, dict):
            response_data.update(data)
        else:
            response_data["result"] = data
            
    if message:
        response_data["message"] = message
        
    return event_response_builder(
        response_data,
        context=context
    )


def error_response(
    error: Union[str, Exception],
    context: Optional[Dict[str, Any]] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build an error response.
    
    Args:
        error: Error message or exception
        context: Event context with system metadata
        details: Additional error details
        
    Returns:
        Error response dict
    """
    response_data = {
        "error": str(error),
        "status": "failed"
    }
    
    if details:
        response_data.update(details)
        
    return event_response_builder(
        response_data,
        context=context
    )


def async_response(
    request_id: str,
    context: Optional[Dict[str, Any]] = None,
    status: str = "queued",
    **kwargs
) -> Dict[str, Any]:
    """Build an async operation response (like completion:async).
    
    Preserves the expected format for async operations while adding
    standardized metadata.
    
    Args:
        request_id: The request ID for tracking
        context: Event context with system metadata
        status: Operation status (default: "queued")
        **kwargs: Additional fields to include
        
    Returns:
        Async response dict with request_id at top level
    """
    response_data = {
        "request_id": request_id,
        "status": status
    }
    
    # Add any additional fields
    response_data.update(kwargs)
    
    return event_response_builder(
        response_data,
        context=context,
        include_metadata=True  # Always include metadata for async responses
    )


def list_response(
    items: list,
    context: Optional[Dict[str, Any]] = None,
    count_field: str = "count",
    items_field: str = "items"
) -> Dict[str, Any]:
    """Build a response containing a list of items.
    
    Args:
        items: List of items
        context: Event context with system metadata
        count_field: Name for count field (default: "count")
        items_field: Name for items field (default: "items")
        
    Returns:
        List response dict
    """
    response_data = {
        items_field: items,
        count_field: len(items)
    }
    
    return event_response_builder(
        response_data,
        context=context
    )