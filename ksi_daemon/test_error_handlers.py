#!/usr/bin/env python3
"""
Test handlers for universal error propagation testing.
"""

from typing import Dict, Any, Optional
from ksi_daemon.event_system import event_handler
from ksi_common.event_response_builder import success_response
from ksi_common.universal_operation import ksi_operation


@event_handler("test:trigger_error")
@ksi_operation(operation_type="handler")
async def handle_trigger_error(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Test handler that deliberately triggers an error."""
    message = data.get("message", "Test error")
    error_type = data.get("error_type", "test_error")
    
    # Deliberately raise an exception to test error propagation
    if error_type == "handler_failure":
        raise RuntimeError(f"Deliberate handler failure: {message}")
    elif error_type == "value_error":
        raise ValueError(f"Deliberate value error: {message}")
    elif error_type == "type_error":
        raise TypeError(f"Deliberate type error: {message}")
    else:
        raise Exception(f"Generic test error: {message}")


@event_handler("test:agent_error")
@ksi_operation(operation_type="handler")
async def handle_agent_error(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Test handler that triggers error for specific agent."""
    agent_id = data.get("agent_id")
    error_message = data.get("error_message", "Agent-specific test error")
    
    # Add agent context to trigger proper routing
    if context is None:
        context = {}
    
    context["_ksi_context"] = {
        "_client_id": f"agent_{agent_id}",
        "_agent_id": agent_id
    }
    
    # Trigger error that should be routed to the agent
    raise RuntimeError(error_message)


@event_handler("test:success_response")
@ksi_operation(operation_type="handler")
async def handle_success_test(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Test handler that returns success."""
    return success_response({
        "test": "success",
        "input_data": data
    })


@event_handler("test:none_response")
@ksi_operation(operation_type="handler")
async def handle_none_response(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Test handler that returns None (should be converted to status:completed)."""
    # Return None - decorator should convert to {"status": "completed"}
    return None