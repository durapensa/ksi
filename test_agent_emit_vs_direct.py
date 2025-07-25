#!/usr/bin/env python3
"""
Test the difference between agent_emit_event and direct event emission.
"""
import asyncio
import json
import time
from pathlib import Path

# Add KSI to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from experiments.ksi_socket_utils import KSISocketClient as KSIClient

async def test_emission_methods():
    """Compare different emission methods."""
    client = KSIClient()
    
    print("=== Testing Event Emission Methods ===")
    
    # First, register a test transformer
    print("\n1. Registering test transformer")
    transformer_result = await client.send_command_async({
        "event": "router:register_transformer",
        "data": {
            "transformer": {
                "name": "test_agent_spawned_to_custom",
                "source": "test:agent_spawned", 
                "target": "test:custom_target",
                "mapping": {
                    "agent_id": "{{agent_id}}",
                    "timestamp": "{{timestamp_utc()}}",
                    "transformed": True
                }
            }
        }
    })
    print(f"Transformer registration: {transformer_result.get('data', {}).get('status', 'unknown')}")
    
    # Test 1: Direct event emission (like CLI)
    print("\n2. Testing direct emission (CLI-style)")
    
    start_time = time.time()
    
    # Emit test event
    direct_result = await client.send_command_async({
        "event": "test:agent_spawned",
        "data": {
            "agent_id": "test_direct_emit",
            "method": "direct_cli"
        }
    })
    
    print(f"Direct emission result: {json.dumps(direct_result.get('data', {}), indent=2)}")
    
    # Check if transformer fired
    await asyncio.sleep(0.5)
    
    events_result = await client.send_command_async({
        "event": "monitor:get_events",
        "data": {
            "event_patterns": ["test:agent_spawned", "test:custom_target"],
            "since": start_time,
            "limit": 10
        }
    })
    
    events = events_result.get("data", {}).get("events", [])
    print(f"\nEvents captured: {len(events)}")
    for event in events:
        print(f"  - {event.get('event_name')}: {event.get('data', {}).get('agent_id', 'unknown')}")
    
    # Test 2: Emission through agent context
    print("\n3. Testing emission with agent context")
    
    # Create a test agent first
    agent_id = f"context_test_{int(time.time())}"
    spawn_result = await client.send_command_async({
        "event": "agent:spawn",
        "data": {
            "agent_id": agent_id,
            "profile": "components/core/base_agent"
        }
    })
    
    print(f"Created test agent: {agent_id}")
    
    # Now have the agent emit an event
    agent_emit_result = await client.send_command_async({
        "event": "agent:send_message",
        "data": {
            "agent_id": agent_id,
            "message": {
                "role": "user",
                "content": "Please emit this JSON event: {\"event\": \"test:agent_spawned\", \"data\": {\"agent_id\": \"test_agent_emit\", \"method\": \"agent_context\"}}"
            }
        }
    })
    
    print(f"Agent message sent: {agent_emit_result.get('data', {}).get('status', 'unknown')}")
    
    # Wait and check
    await asyncio.sleep(2)
    
    events_result2 = await client.send_command_async({
        "event": "monitor:get_events",
        "data": {
            "event_patterns": ["test:agent_spawned", "test:custom_target"],
            "since": start_time,
            "limit": 20
        }
    })
    
    events2 = events_result2.get("data", {}).get("events", [])
    print(f"\nAll test events captured: {len(events2)}")
    
    # Group by emission method
    by_method = {}
    for event in events2:
        method = event.get("data", {}).get("method", "unknown")
        if method not in by_method:
            by_method[method] = []
        by_method[method].append(event)
    
    print("\nEvents by emission method:")
    for method, method_events in by_method.items():
        print(f"\n  {method}:")
        for event in method_events:
            print(f"    - {event.get('event_name')}: transformed={event.get('data', {}).get('transformed', False)}")
    
    # Test 3: Check actual agent:spawned transformers
    print("\n4. Checking actual agent:spawned events")
    
    # Get recent agent:spawned events
    agent_events = await client.send_command_async({
        "event": "monitor:get_events",
        "data": {
            "event_patterns": ["agent:spawned", "state:entity:create", "monitor:agent_created"],
            "since": time.time() - 300,  # Last 5 minutes
            "limit": 50
        }
    })
    
    events3 = agent_events.get("data", {}).get("events", [])
    
    # Count by type
    event_counts = {}
    for event in events3:
        event_name = event.get("event_name")
        event_counts[event_name] = event_counts.get(event_name, 0) + 1
    
    print("\nEvent counts (last 5 minutes):")
    for event_type, count in sorted(event_counts.items()):
        print(f"  {event_type}: {count}")
    
    # Look for state:entity:create events with type=agent
    agent_state_creates = [
        e for e in events3 
        if e.get("event_name") == "state:entity:create" 
        and e.get("data", {}).get("type") == "agent"
    ]
    
    print(f"\nstate:entity:create events with type=agent: {len(agent_state_creates)}")
    if agent_state_creates:
        print("  Recent examples:")
        for event in agent_state_creates[:3]:
            data = event.get("data", {})
            print(f"    - id: {data.get('id')}, properties: {list(data.get('properties', {}).keys())}")
    
    # Cleanup
    print("\n5. Cleaning up")
    await client.send_command_async({
        "event": "agent:terminate", 
        "data": {"agent_id": agent_id}
    })

if __name__ == "__main__":
    asyncio.run(test_emission_methods())