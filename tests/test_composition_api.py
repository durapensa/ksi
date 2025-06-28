#!/usr/bin/env python3
"""Test composition API functionality."""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksi_client import AsyncClient


async def test_composition_api():
    """Test composition service API."""
    print("Testing composition service API...")
    
    # Create client
    client = AsyncClient(
        client_id="test_composition_client",
        socket_path="var/run/daemon.sock"
    )
    
    try:
        # Connect to daemon
        await client.connect()
        print("✓ Connected to daemon")
        
        # Test 1: List compositions
        result = await client.request_event("composition:list", {})
        print(f"\nComposition list response: {result}")
        
        if result and 'error' not in result:
            compositions = result.get('compositions', [])
            profiles = [c for c in compositions if c.get('type') == 'profile']
            prompts = [c for c in compositions if c.get('type') == 'prompt']
            print(f"✓ Found {len(profiles)} profiles, {len(prompts)} prompts")
            
            # Test 2: Get a specific composition
            if profiles:
                profile = profiles[0]
                profile_name = profile.get('name')
                result = await client.request_event("composition:get", {
                    "name": profile_name,
                    "type": "profile"
                })
                print(f"\nGot profile '{profile_name}': {result.get('composition', {}).get('name', 'ERROR')}")
        else:
            print(f"❌ Composition list failed: {result}")
            
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        await client.disconnect()


if __name__ == "__main__":
    success = asyncio.run(test_composition_api())
    sys.exit(0 if success else 1)