#!/usr/bin/env python3
"""
Example of using the event parser to handle injected originator fields.

Shows how handlers can cleanly extract expected data while the event system
automatically injects originator information.
"""
from typing import Dict, Any, Optional
from typing_extensions import TypedDict, Required
from ksi_daemon.event_system import event_handler
from ksi_common.event_parser import parse_event_data, extract_originator_info
from ksi_common.event_response_builder import build_response


class MyEventData(TypedDict):
    """Expected data structure for my:event."""
    action: Required[str]
    target: Required[str]
    priority: int  # Optional field


@event_handler("my:event")
async def handle_my_event(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Example handler that properly handles injected originator fields."""
    
    # Parse the event data to get only expected fields
    # This prevents TypedDict validation errors from injected fields
    data = parse_event_data(raw_data, MyEventData)
    
    # Now we can safely access expected fields
    action = data["action"]
    target = data["target"] 
    priority = data.get("priority", 0)
    
    # If we need originator info, extract it separately
    originator = extract_originator_info(raw_data)
    if originator.get("agent_id"):
        print(f"Event from agent: {originator['agent_id']}")
    
    # Process the event
    result = {
        "processed": True,
        "action_taken": f"{action} on {target} with priority {priority}"
    }
    
    # Return response with originator info included
    return build_response(
        result,
        handler_name="example.handle_my_event",
        event_name="my:event",
        context=context
    )


@event_handler("strict:validation")
async def handle_strict_validation(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Example of strict validation that would fail without event parser."""
    
    class StrictData(TypedDict):
        """This TypedDict only allows specific fields."""
        command: str
        value: int
        # No extra fields allowed!
    
    # Without parser, this would fail if originator_id is injected
    # data = StrictData(**raw_data)  # TypeError: unexpected keyword argument 'originator_id'
    
    # With parser, we get clean data
    data = parse_event_data(raw_data, StrictData)
    
    # Now we can validate strictly
    if "command" not in data or "value" not in data:
        return build_response(
            {"error": "Missing required fields"},
            handler_name="example.handle_strict_validation",
            event_name="strict:validation",
            context=context
        )
    
    # Type-safe access
    command: str = data["command"]
    value: int = data["value"]
    
    return build_response(
        {"result": f"Executed {command} with {value}"},
        handler_name="example.handle_strict_validation",
        event_name="strict:validation",
        context=context
    )


# Example of what happens:

"""
Event system receives:
{
    "event": "my:event",
    "data": {
        "action": "update",
        "target": "config",
        "priority": 5
    }
}

With context containing:
{
    "originator_id": "client-123",
    "agent_id": "agent-456",
    "session_id": "sess-789"
}

Event system injects originator fields, so handler receives:
raw_data = {
    "action": "update",
    "target": "config", 
    "priority": 5,
    "originator_id": "client-123",  # Injected!
    "agent_id": "agent-456",         # Injected!
    "session_id": "sess-789"         # Injected!
}

parse_event_data() returns clean data:
{
    "action": "update",
    "target": "config",
    "priority": 5
}

This prevents TypedDict validation errors while preserving originator info.
"""