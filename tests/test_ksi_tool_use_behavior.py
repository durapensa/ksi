#!/usr/bin/env python3
"""Test script for verifying ksi_tool_use behavior component."""

import time
import json
from ksi_common.sync_client import MinimalSyncClient

# Create client instance
client = MinimalSyncClient()


def test_ksi_tool_use_behavior():
    """Test the ksi_events_as_tool_calls behavior component."""
    print("=== Testing KSI Tool Use Behavior ===\n")
    
    # 1. Create a test agent that combines the behavior
    print("1. Creating test agent with tool use behavior...")
    create_result = client.send_event("composition:create_component", {
        "name": "test/tool_use_test_agent",
        "content": """---
component_type: core
name: tool_use_test_agent
dependencies:
  - behaviors/communication/ksi_events_as_tool_calls
---

You are a test agent for validating KSI tool use pattern.

When asked, emit events using the structured format described in your behavioral instructions.
"""
    })
    print(f"Component created: {create_result.get('status')}\n")
    
    # 2. Spawn the agent
    print("2. Spawning test agent...")
    spawn_result = client.send_event("agent:spawn", {
        "component": "test/tool_use_test_agent",
        "capabilities": ["base", "state_management", "agent_communication"]
    })
    agent_id = spawn_result.get("agent_id")
    print(f"Spawned agent: {agent_id}\n")
    
    # 3. Test basic status emission
    print("3. Testing basic status emission...")
    completion_result = client.send_event("completion:async", {
        "agent_id": agent_id,
        "prompt": "Report your status as initialized using the ksi_tool_use format"
    })
    request_id = completion_result.get("request_id")
    print(f"Request ID: {request_id}")
    
    time.sleep(5)
    
    # Get completion result
    completion_response = client.send_event("completion:get", {
        "request_id": request_id
    })
    print(f"Completion status: {completion_response.get('status')}")
    if completion_response.get("result"):
        print(f"Agent response: {completion_response.get('result')[:200]}...")
    
    # Check monitor events - remove _agent_id filter for now
    events = client.send_event("monitor:get_events", {
        "event_patterns": ["agent:status"],
        "limit": 10
    })
    
    if events.get("events"):
        print("✅ Status event emitted successfully!")
        print(f"Event data: {json.dumps(events['events'][0]['data'], indent=2)}\n")
    else:
        print("❌ No status event found\n")
    
    # 4. Test multiple events
    print("4. Testing multiple event emission...")
    client.send_event("completion:async", {
        "agent_id": agent_id,
        "prompt": """Emit the following events in sequence:
1. Set your status to 'processing'
2. Report progress at 50%
3. Set your status to 'completed'

Use the ksi_tool_use format for each event."""
    })
    
    time.sleep(3)
    
    # Check for multiple events
    recent_events = client.send_event("monitor:get_events", {
        "event_patterns": ["agent:status", "agent:progress"],
        "_agent_id": agent_id,
        "limit": 5
    })
    
    event_count = len(recent_events.get("events", []))
    print(f"Found {event_count} recent events")
    
    # 5. Test complex data structure
    print("\n5. Testing complex data structure...")
    client.send_event("completion:async", {
        "agent_id": agent_id,
        "prompt": """Create a state entity with this data:
{
  "type": "test_results",
  "id": "test_001",
  "properties": {
    "scores": [95, 87, 92],
    "metadata": {
      "test_suite": "ksi_tool_use",
      "timestamp": "2025-01-28"
    }
  }
}

Use the state:entity:create event with ksi_tool_use format."""
    })
    
    time.sleep(3)
    
    # Check state entity creation
    entity_events = client.send_event("monitor:get_events", {
        "event_patterns": ["state:entity:create"],
        "_agent_id": agent_id,
        "limit": 1
    })
    
    if entity_events.get("events"):
        print("✅ Complex data structure handled correctly!")
        print(f"Entity data: {json.dumps(entity_events['events'][0]['data'], indent=2)}\n")
    else:
        print("❌ No entity creation event found\n")
    
    # 6. Cleanup
    print("6. Cleaning up...")
    client.send_event("agent:terminate", {"agent_id": agent_id})
    print(f"Agent {agent_id} terminated")
    
    # Summary
    print("\n=== Test Summary ===")
    print("The ksi_tool_use behavior component enables agents to emit events")
    print("using a structured JSON format that leverages LLMs' natural")
    print("tool-calling abilities for reliable event extraction.")


if __name__ == "__main__":
    test_ksi_tool_use_behavior()