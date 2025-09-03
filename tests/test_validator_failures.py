#!/usr/bin/env python3
"""Investigate specific validator failure cases."""

import asyncio
from ksi_client.client import EventClient

async def test_specific_failures():
    """Test specific failing cases to understand the issues."""
    client = EventClient()
    await client.connect()
    
    print("=== Investigating Validator Failures ===\n")
    
    # Test 1: Negative coordinates (showing as failed in edge cases)
    print("Test 1: Negative coordinates")
    response = await client.send_event("validator:movement:validate", {
        "from_x": -10.0,
        "from_y": -10.0,
        "to_x": -5.0,
        "to_y": -5.0,
        "movement_type": "walk",
        "entity_capacity": 10.0
    })
    print(f"  Valid: {response.get('valid')}")
    print(f"  Distance: {response.get('actual_distance')}")
    if not response.get('valid'):
        print(f"  Reason: {response.get('reason')}")
    print()
    
    # Test 2: Large coordinates  
    print("Test 2: Large coordinates")
    response = await client.send_event("validator:movement:validate", {
        "from_x": 1000000.0,
        "from_y": 1000000.0,
        "to_x": 1000001.0,
        "to_y": 1000001.0,
        "movement_type": "walk",
        "entity_capacity": 10.0
    })
    print(f"  Valid: {response.get('valid')}")
    print(f"  Distance: {response.get('actual_distance')}")
    if not response.get('valid'):
        print(f"  Reason: {response.get('reason')}")
    print()
    
    # Test 3: Self-transfer (resource)
    print("Test 3: Self-transfer of resources")
    # First set up ownership
    await client.send_event("validator:resource:update_ownership", {
        "entity": "test_agent",
        "resource_type": "gold",
        "amount": 100.0
    })
    response = await client.send_event("validator:resource:validate", {
        "from_entity": "test_agent",
        "to_entity": "test_agent",
        "resource_type": "gold",
        "amount": 50.0,
        "transfer_type": "trade"
    })
    print(f"  Valid: {response.get('valid')}")
    if not response.get('valid'):
        print(f"  Reason: {response.get('reason')}")
    print()
    
    # Test 4: Zero range interaction
    print("Test 4: Zero range interaction")
    response = await client.send_event("validator:interaction:validate", {
        "actor_id": "agent_1",
        "target_id": "agent_2",
        "interaction_type": "cooperate",
        "actor_x": 0.0,
        "actor_y": 0.0,
        "target_x": 5.0,
        "target_y": 5.0,
        "range_limit": 0.0,
        "capabilities": ["cooperate"]
    })
    print(f"  Valid: {response.get('valid')}")
    if not response.get('valid'):
        print(f"  Reason: {response.get('reason')}")
    print()
    
    # Test 5: Unknown interaction type
    print("Test 5: Unknown interaction type")
    response = await client.send_event("validator:interaction:validate", {
        "actor_id": "agent_1",
        "target_id": "agent_2",
        "interaction_type": "mind_meld",
        "actor_x": 0.0,
        "actor_y": 0.0,
        "target_x": 1.0,
        "target_y": 1.0,
        "range_limit": 5.0,
        "capabilities": ["cooperate"]
    })
    print(f"  Valid: {response.get('valid')}")
    if not response.get('valid'):
        print(f"  Reason: {response.get('reason')}")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_specific_failures())