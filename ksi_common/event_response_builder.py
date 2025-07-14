#!/usr/bin/env python3
"""
Event response builder for KSI event handlers.

Provides utilities for event handlers to create responses in standardized format
that includes originator information and processing metadata. This ensures all
event responses have consistent structure while preserving handler-specific data.

Usage:
    from ksi_common.event_response_builder import build_response, async_response
    
    # In an event handler:
    return build_response(
        {"result": "success"},
        handler_name="my_handler",
        event_name="my:event",
        context=context
    )
"""
from typing import Any, Dict, Optional, Union


def build_response(
    data: Any,
    handler_name: str,
    event_name: str,
    context: Optional[Dict[str, Any]] = None,
    include_metadata: bool = True
) -> Dict[str, Any]:
    """Build a standardized response for event handlers.
    
    Creates a response that includes:
    - The actual response data
    - Processing metadata (handler, event_processed)
    - Originator information from context
    
    Args:
        data: The actual response data (can be dict, list, string, etc.)
        handler_name: Name of the handler processing the event
        event_name: Name of the event being handled
        context: Event context containing originator info
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
        response["event_processed"] = True
        response["handler"] = handler_name
        response["event"] = event_name
    
    # Extract and add originator information from context
    if context:
        # Add individual fields directly to response
        originator_fields = [
            "originator_id",
            "agent_id", 
            "session_id",
            "correlation_id",
            "construct_id",
            "event_id"
        ]
        
        for field in originator_fields:
            if field in context and field not in response:
                response[field] = context[field]
    
    return response


def success_response(
    data: Any = None,
    handler_name: str = None,
    event_name: str = None,
    context: Optional[Dict[str, Any]] = None,
    message: str = None
) -> Dict[str, Any]:
    """Build a success response.
    
    Args:
        data: Optional response data
        handler_name: Handler name (required)
        event_name: Event name (required)
        context: Event context with originator info
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
        
    return build_response(
        response_data,
        handler_name=handler_name,
        event_name=event_name,
        context=context
    )


def error_response(
    error: Union[str, Exception],
    handler_name: str = None,
    event_name: str = None,
    context: Optional[Dict[str, Any]] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build an error response.
    
    Args:
        error: Error message or exception
        handler_name: Handler name
        event_name: Event name
        context: Event context with originator info
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
        
    return build_response(
        response_data,
        handler_name=handler_name,
        event_name=event_name,
        context=context
    )


def async_response(
    request_id: str,
    handler_name: str = None,
    event_name: str = None,
    context: Optional[Dict[str, Any]] = None,
    status: str = "queued",
    **kwargs
) -> Dict[str, Any]:
    """Build an async operation response (like completion:async).
    
    Preserves the expected format for async operations while adding
    standardized metadata.
    
    Args:
        request_id: The request ID for tracking
        handler_name: Handler name
        event_name: Event name
        context: Event context with originator info
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
    
    return build_response(
        response_data,
        handler_name=handler_name,
        event_name=event_name,
        context=context,
        include_metadata=True  # Always include metadata for async responses
    )


def list_response(
    items: list,
    handler_name: str = None,
    event_name: str = None,
    context: Optional[Dict[str, Any]] = None,
    count_field: str = "count",
    items_field: str = "items"
) -> Dict[str, Any]:
    """Build a response containing a list of items.
    
    Args:
        items: List of items
        handler_name: Handler name
        event_name: Event name
        context: Event context with originator info
        count_field: Name for count field (default: "count")
        items_field: Name for items field (default: "items")
        
    Returns:
        List response dict
    """
    response_data = {
        items_field: items,
        count_field: len(items)
    }
    
    return build_response(
        response_data,
        handler_name=handler_name,
        event_name=event_name,
        context=context
    )