#!/usr/bin/env python3
"""
Detailed test to understand transformer behavior with agent:spawned events.
"""
import asyncio
import json
import time
from pathlib import Path

# Add KSI to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from experiments.ksi_socket_utils import KSISocketClient as KSIClient

async def test_transformer_details():
    """Test transformer details."""
    client = KSIClient()
    
    # First, let's manually check what transformers are registered
    print("=== Manually testing transformer behavior ===")
    
    # Send a test event directly to see if state:entity:create handler exists
    print("\n1. Testing state:entity:create handler directly")
    test_result = await client.send_command_async({
        "event": "state:entity:create",
        "data": {
            "type": "test",
            "id": "manual_test_123",
            "properties": {
                "test": True,
                "created_at": time.time()
            }
        }
    })
    
    print(f"Direct state:entity:create result: {json.dumps(test_result.get('data', {}), indent=2)}")
    
    # Check if it was created
    get_result = await client.send_command_async({
        "event": "state:entity:get",
        "data": {
            "entity_type": "test",
            "entity_id": "manual_test_123"
        }
    })
    
    if get_result.get("data", {}).get("entity"):
        print("✅ State system is working - entity was created")
    else:
        print("❌ State system issue - entity not created")
        print(f"Get result: {json.dumps(get_result, indent=2)}")
    
    # Now test the full flow
    print("\n2. Testing full agent spawn flow with monitoring")
    
    # Subscribe to monitor events to see what's happening
    subscribe_result = await client.send_command_async({
        "event": "monitor:subscribe",
        "data": {
            "client_id": "test_monitor",
            "event_patterns": ["agent:*", "state:entity:*", "monitor:agent_*"]
        }
    })
    print(f"Monitor subscription: {subscribe_result.get('data', {}).get('status')}")
    
    # Spawn agent
    agent_id = f"detail_test_{int(time.time())}"
    print(f"\n3. Spawning agent: {agent_id}")
    
    spawn_result = await client.send_command_async({
        "event": "agent:spawn",
        "data": {
            "agent_id": agent_id,
            "profile": "components/core/base_agent"
        }
    })
    
    print(f"Spawn completed: {spawn_result.get('data', {}).get('status')}")
    
    # Wait a bit
    await asyncio.sleep(2)
    
    # Check what events occurred
    print("\n4. Checking recent events")
    events_result = await client.send_command_async({
        "event": "monitor:get_events", 
        "data": {
            "event_patterns": ["agent:spawned", "state:entity:create", "monitor:agent_created", "monitor:agent_*"],
            "since": time.time() - 10,
            "limit": 20
        }
    })
    
    events = events_result.get("data", {}).get("events", [])
    print(f"\nFound {len(events)} events:")
    
    # Group and display
    by_type = {}
    for event in events:
        event_name = event.get("event_name")
        if event_name not in by_type:
            by_type[event_name] = []
        by_type[event_name].append(event)
    
    for event_type, type_events in by_type.items():
        print(f"\n{event_type}: {len(type_events)} events")
        for event in type_events:
            data = event.get("data", {})
            # Show relevant fields
            if event_type == "agent:spawned":
                print(f"  - agent_id: {data.get('agent_id')}")
            elif event_type == "state:entity:create":
                print(f"  - type: {data.get('type')}, id: {data.get('id')}")
                if data.get("error"):
                    print(f"    ERROR: {data.get('error')}")
            elif event_type.startswith("monitor:"):
                print(f"  - data: {json.dumps(data, indent=4)}")
    
    # Check state entity
    print(f"\n5. Checking if state entity exists for agent {agent_id}")
    entity_check = await client.send_command_async({
        "event": "state:entity:get",
        "data": {
            "entity_type": "agent",
            "entity_id": agent_id
        }
    })
    
    if entity_check.get("data", {}).get("entity"):
        print("✅ Agent state entity exists!")
        entity = entity_check["data"]["entity"]
        print(f"  Properties: {json.dumps(entity.get('properties', {}), indent=4)}")
    else:
        print("❌ No agent state entity found")
        
        # Try listing all agent entities
        list_result = await client.send_command_async({
            "event": "state:entity:list",
            "data": {
                "entity_type": "agent",
                "limit": 10
            }
        })
        
        entities = list_result.get("data", {}).get("entities", [])
        print(f"\nAll agent entities ({len(entities)}):")
        for entity in entities[:5]:
            print(f"  - {entity.get('id')}: created {entity.get('properties', {}).get('created_at_iso', 'unknown')}")
    
    # Cleanup
    print("\n6. Cleaning up")
    await client.send_command_async({
        "event": "agent:terminate",
        "data": {"agent_id": agent_id}
    })
    
    # Unsubscribe
    await client.send_command_async({
        "event": "monitor:unsubscribe",
        "data": {"client_id": "test_monitor"}
    })

if __name__ == "__main__":
    asyncio.run(test_transformer_details())