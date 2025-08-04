#!/usr/bin/env python3
"""
Test agent spawning directly.
"""
import asyncio
import json
from ksi_client.client import EventClient

async def test_agent():
    """Test agent spawning and completion."""
    client = EventClient()
    await client.connect()
    
    print("Spawning test agent...")
    
    # Spawn agent
    spawn_result = await client.send_event("agent:spawn", {
        "agent_id": "test_simple_agent",
        "model": "claude-sonnet-4",
        "component": "behaviors/optimization/strict_instruction_following"
    })
    
    print(f"Spawn result: {json.dumps(spawn_result, indent=2)}")
    
    # Send completion
    print("\nSending completion request...")
    completion_result = await client.send_event("completion:async", {
        "agent_id": "test_simple_agent",
        "prompt": "Please emit an agent:status event to confirm you are operational."
    })
    
    print(f"Completion result: {json.dumps(completion_result, indent=2)}")
    
    # Wait longer for completion
    await asyncio.sleep(10)
    
    # Check for completion results
    print("\nChecking for completion results...")
    monitor_result = await client.send_event("monitor:get_events", {
        "limit": 20
    })
    
    events = monitor_result.get('data', {}).get('events', [])
    print(f"\nFound {len(events)} events:")
    for event in events:
        print(f"  - {event.get('timestamp')}: {event.get('event_name')}")
        
    # Stop agent
    print("\nStopping agent...")
    await client.send_event("agent:stop", {"agent_id": "test_simple_agent"})
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_agent())