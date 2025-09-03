#!/usr/bin/env python3
"""Test validator parameter formats."""

import asyncio
from ksi_client.client import EventClient

async def test_parameter_formats():
    """Test different parameter formats for validators."""
    client = EventClient()
    await client.connect()
    
    print("=== Testing Movement Validator Parameter Formats ===\n")
    
    # Test 1: Array format (what debug test used)
    print("Test 1: Array format (from_position/to_position)")
    response = await client.send_event("validator:movement:validate", {
        "from_position": [5, 5, 0],
        "to_position": [8, 8, 0],
        "movement_type": "walk"
    })
    print(f"  Result: {'✓ PASSED' if response.get('valid') else '✗ FAILED'}")
    print(f"  Response: {response}\n")
    
    # Test 2: Individual coordinate format (what validator expects)
    print("Test 2: Individual coordinates (from_x/from_y/to_x/to_y)")
    response = await client.send_event("validator:movement:validate", {
        "from_x": 5.0,
        "from_y": 5.0,
        "to_x": 8.0,
        "to_y": 8.0,
        "movement_type": "walk"
    })
    print(f"  Result: {'✓ PASSED' if response.get('valid') else '✗ FAILED'}")
    print(f"  Response: {response}\n")
    
    # Test 3: Mixed format
    print("Test 3: Mixed format (some array, some individual)")
    response = await client.send_event("validator:movement:validate", {
        "from_position": [5, 5],
        "to_x": 8.0,
        "to_y": 8.0,
        "movement_type": "walk"
    })
    print(f"  Result: {'✓ PASSED' if response.get('valid') else '✗ FAILED'}")
    print(f"  Response: {response}\n")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_parameter_formats())