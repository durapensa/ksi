#!/usr/bin/env python3
"""Test composition flow to understand data structure."""

import json
import asyncio
from ksi_client import EventClient

async def test_composition():
    client = EventClient()
    await client.connect()
    
    # Test compose profile for base_multi_agent
    result = await client.send_event("composition:profile", {
        "name": "base_multi_agent",
        "variables": {"agent_id": "test_agent"}
    })
    
    print("=== Composed Profile Result ===")
    print(json.dumps(result, indent=2))
    
    # Also check what permissions are set
    perm_result = await client.send_event("permission:get_profile", {
        "name": "trusted"
    })
    
    print("\n=== Trusted Permission Profile ===")
    print(json.dumps(perm_result, indent=2))
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_composition())