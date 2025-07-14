#!/usr/bin/env python3
"""
Example of using the event response builder in KSI handlers.

Shows how handlers can return standardized responses that include
originator information from context.
"""
from typing import Dict, Any, Optional
from ksi_daemon.event_system import event_handler
from ksi_common.event_response_builder import (
    build_response, 
    success_response, 
    error_response,
    async_response,
    list_response
)


@event_handler("example:test")
async def handle_example_test(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Example handler showing basic response building."""
    
    # Process the event
    result = {"processed": True, "input_received": data}
    
    # Return standardized response with originator info
    return build_response(
        result,
        handler_name="example.handle_test",
        event_name="example:test",
        context=context  # This adds originator_id, agent_id, etc.
    )


@event_handler("example:async_operation")
async def handle_async_operation(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Example of async operation response (like completion:async)."""
    
    request_id = data.get("request_id", "test-123")
    
    # Return async response format
    return async_response(
        request_id,
        handler_name="example.handle_async_operation",
        event_name="example:async_operation",
        context=context,
        status="queued",
        message="Operation queued for processing"
    )


@event_handler("example:list_items")
async def handle_list_items(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Example of returning a list with metadata."""
    
    items = [
        {"id": "1", "name": "Item 1"},
        {"id": "2", "name": "Item 2"},
        {"id": "3", "name": "Item 3"}
    ]
    
    return list_response(
        items,
        handler_name="example.handle_list_items",
        event_name="example:list_items",
        context=context,
        items_field="results"  # Custom field name
    )


@event_handler("example:error_case")
async def handle_error_case(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Example of error response."""
    
    if "required_field" not in data:
        return error_response(
            "Missing required_field in request",
            handler_name="example.handle_error_case",
            event_name="example:error_case",
            context=context,
            details={"provided_fields": list(data.keys())}
        )
    
    # Success case
    return success_response(
        {"processed": data["required_field"]},
        handler_name="example.handle_error_case",
        event_name="example:error_case",
        context=context,
        message="Successfully processed required field"
    )


# Example of what the responses look like:

"""
Request with context:
{
    "event": "example:test",
    "data": {"message": "Hello"},
    "originator_id": "agent-123",
    "session_id": "sess-456"
}

Response:
{
    "processed": true,
    "input_received": {"message": "Hello"},
    "event_processed": true,
    "handler": "example.handle_test",
    "event": "example:test",
    "originator_id": "agent-123",
    "session_id": "sess-456"
}

This ensures:
1. Handler-specific data is preserved
2. Processing metadata is added
3. Originator info from context is included
4. Response format is consistent across all handlers
"""