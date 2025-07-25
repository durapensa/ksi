#!/usr/bin/env python3
"""
Test transformer behavior by spawning an agent through the daemon.
"""
import asyncio
import json
import time
from pathlib import Path

# Add KSI to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from experiments.ksi_socket_utils import KSISocketClient as KSIClient

async def test_agent_spawn_transformers():
    """Test if transformers are applied when spawning agent via daemon."""
    client = KSIClient()
    
    # First check what transformers are registered
    print("=== Checking registered transformers ===")
    
    # Query for state entities that should be created by transformer
    print("\n=== Checking for existing agent state entities ===")
    state_result = await client.send_command_async({
        "event": "state:entity:list",
        "data": {
            "entity_type": "agent",
            "limit": 5
        }
    })
    
    if state_result.get("data", {}).get("entities"):
        print(f"Found {len(state_result['data']['entities'])} agent entities")
        for entity in state_result['data']['entities'][:3]:
            print(f"  - {entity.get('id')}: {entity.get('properties', {}).get('status')}")
    else:
        print("No agent state entities found")
    
    # Spawn a test agent
    print("\n=== Spawning test agent ===")
    agent_id = f"transformer_test_{int(time.time())}"
    
    spawn_result = await client.send_command_async({
        "event": "agent:spawn",
        "data": {
            "agent_id": agent_id,
            "profile": "components/core/base_agent"
        }
    })
    
    print(f"Spawn result: {json.dumps(spawn_result.get('data', {}), indent=2)}")
    
    # Wait for transformers to execute
    await asyncio.sleep(1)
    
    # Check if state entity was created
    print("\n=== Checking if transformer created state entity ===")
    entity_result = await client.send_command_async({
        "event": "state:entity:get",
        "data": {
            "entity_id": agent_id,
            "entity_type": "agent"
        }
    })
    
    if entity_result.get("data", {}).get("entity"):
        entity = entity_result["data"]["entity"]
        print(f"✅ State entity created by transformer!")
        print(f"  ID: {entity.get('id')}")
        print(f"  Properties: {json.dumps(entity.get('properties', {}), indent=4)}")
    else:
        print(f"❌ No state entity found for agent {agent_id}")
        print(f"Entity result: {json.dumps(entity_result, indent=2)}")
    
    # Check recent events
    print("\n=== Checking recent events ===")
    events_result = await client.send_command_async({
        "event": "monitor:get_events",
        "data": {
            "event_patterns": ["agent:spawned", "state:entity:create", "monitor:agent_created"],
            "since": time.time() - 10,
            "limit": 20
        }
    })
    
    events = events_result.get("data", {}).get("events", [])
    print(f"Found {len(events)} relevant events:")
    
    # Group by event type
    event_types = {}
    for event in events:
        event_name = event.get("event_name")
        if event_name not in event_types:
            event_types[event_name] = []
        event_types[event_name].append(event)
    
    for event_type, type_events in event_types.items():
        print(f"\n  {event_type}: {len(type_events)} events")
        for event in type_events[:2]:
            data = event.get("data", {})
            if "agent_id" in data:
                print(f"    - agent_id: {data['agent_id']}")
            elif "id" in data:
                print(f"    - entity_id: {data['id']}")
    
    # Clean up
    print("\n=== Cleaning up ===")
    await client.send_command_async({
        "event": "agent:terminate",
        "data": {"agent_id": agent_id}
    })
    print(f"Terminated agent {agent_id}")

if __name__ == "__main__":
    asyncio.run(test_agent_spawn_transformers())