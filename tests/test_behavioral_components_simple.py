#!/usr/bin/env python3
"""Simple test to verify behavioral components work as expected."""

import time
import json
from ksi_common.sync_client import MinimalSyncClient

# Create client instance
client = MinimalSyncClient()


def test_claude_code_override():
    """Test the claude_code_override behavior."""
    print("=== Testing claude_code_override Behavior ===\n")
    
    # 1. Create test agent with override
    print("1. Creating agent with claude_code_override...")
    spawn_result = client.send_event("agent:spawn", {
        "component": "behaviors/core/claude_code_override",
        "capabilities": ["base"]
    })
    agent_id = spawn_result.get("agent_id")
    print(f"Spawned agent: {agent_id}\n")
    
    # 2. Test direct response behavior
    print("2. Testing direct response (no preamble)...")
    completion_result = client.send_event("completion:async", {
        "agent_id": agent_id,
        "prompt": "Calculate: 2 + 2"
    })
    request_id = completion_result.get("request_id")
    
    time.sleep(3)
    
    response = client.send_event("completion:status", {
        "request_id": request_id
    })
    
    print(f"Completion status: {response.get('status')}")
    if response.get("status") == "completed":
        result = response.get("result", "")
        print(f"Response: '{result}'")
        if result.strip() == "4":
            print("✅ Direct response without explanation!")
        else:
            print("❌ Response includes explanation")
    else:
        print(f"Response: {json.dumps(response, indent=2)}")
    
    # 3. Cleanup
    print("\n3. Cleaning up...")
    client.send_event("agent:terminate", {"agent_id": agent_id})
    print("Agent terminated")


def test_ksi_tool_use_simple():
    """Test ksi_tool_use pattern with a simple agent."""
    print("\n\n=== Testing KSI Tool Use Pattern ===\n")
    
    # 1. Create test component
    print("1. Creating simple test component...")
    timestamp = int(time.time())
    component_name = f"test/tool_use_test_{timestamp}"
    
    create_result = client.send_event("composition:create_component", {
        "name": component_name,
        "content": """---
component_type: core
name: simple_tool_test
dependencies:
  - behaviors/communication/ksi_events_as_tool_calls
---

You are a simple test agent. When asked to emit an event, use the ksi_tool_use format.

For example:
{
  "type": "ksi_tool_use",
  "id": "ksiu_test_001",
  "name": "agent:status",
  "input": {
    "agent_id": "{{agent_id}}",
    "status": "active"
  }
}
"""
    })
    print(f"Component created: {create_result.get('status')}\n")
    
    # 2. Spawn agent
    print("2. Spawning test agent...")
    spawn_result = client.send_event("agent:spawn", {
        "component": component_name,
        "capabilities": ["base", "agent_communication"]
    })
    agent_id = spawn_result.get("agent_id")
    print(f"Agent ID: {agent_id}\n")
    
    # 3. Test event emission
    print("3. Asking agent to emit status event...")
    completion_result = client.send_event("completion:async", {
        "agent_id": agent_id,
        "prompt": f"Emit an agent:status event with status 'testing'. Use agent_id '{agent_id}' in the input."
    })
    request_id = completion_result.get("request_id")
    
    time.sleep(5)
    
    # Check completion
    response = client.send_event("completion:status", {
        "request_id": request_id
    })
    print(f"Completion status: {response.get('status')}")
    if response.get("result"):
        print(f"Agent response preview: {response.get('result')[:200]}...")
    
    # Check for events - look at all recent status events
    print("\n4. Checking for emitted events...")
    events = client.send_event("monitor:get_events", {
        "event_patterns": ["agent:status"],
        "limit": 5
    })
    
    # Find our agent's event
    found_event = False
    for event in events.get("events", []):
        event_data = event.get("data", {})
        if event_data.get("_agent_id") == agent_id:
            found_event = True
            print("✅ Found agent's status event!")
            print(f"Status: {event_data.get('status')}")
            print(f"Agent ID in event: {event_data.get('agent_id')}")
            break
    
    if not found_event:
        print("❌ No status event found from our agent")
    
    # 5. Cleanup
    print("\n5. Cleaning up...")
    client.send_event("agent:terminate", {"agent_id": agent_id})
    client.send_event("composition:delete_component", {"name": component_name})
    print("Cleanup complete")


def main():
    """Run all behavioral component tests."""
    print("Simple Behavioral Component Tests")
    print("=" * 50)
    
    test_claude_code_override()
    test_ksi_tool_use_simple()
    
    print("\n" + "=" * 50)
    print("Tests complete!")


if __name__ == "__main__":
    main()