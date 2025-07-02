#!/usr/bin/env python3
"""Test composition API functionality."""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize logging before importing ksi_client
from ksi_common.logging import configure_structlog
configure_structlog(log_level="INFO")

from ksi_client import EventClient


async def test_composition_api():
    """Test composition service API."""
    print("Testing composition service API...")
    
    # Create and use client with async context manager
    async with EventClient(
        client_id="test_composition_client", 
        socket_path="var/run/daemon.sock"
    ) as client:
        try:
            print("✓ Connected to daemon")
            
            # Test 1: List compositions
            result = await client.send_event("composition:list", {})
            print(f"\nComposition list response (first 200 chars): {str(result)[:200]}...")
            
            if result and 'error' not in result:
                compositions = result.get('compositions', [])
                profiles = [c for c in compositions if c.get('type') == 'profile']
                prompts = [c for c in compositions if c.get('type') == 'prompt']
                print(f"✓ Found {len(profiles)} profiles, {len(prompts)} prompts")
                
                # Test 2: Get a specific composition
                if profiles:
                    profile = profiles[0]
                    profile_name = profile.get('name')
                    result = await client.send_event("composition:get", {
                        "name": profile_name,
                        "type": "profile"
                    })
                    composition = result.get('composition', {})
                    print(f"\n✓ Got profile '{profile_name}': version {composition.get('version', 'N/A')}")
                    print(f"  Components: {len(composition.get('components', []))}")
                    print(f"  Variables: {composition.get('variables', [])}")
                    
                # Test 3: Validate a composition
                if profiles:
                    profile_name = profiles[0].get('name')
                    result = await client.send_event("composition:validate", {
                        "name": profile_name,
                        "type": "profile"
                    })
                    print(f"\n✓ Validated '{profile_name}': valid={result.get('valid', False)}")
                    if result.get('issues'):
                        print(f"  Issues: {result['issues']}")
            else:
                print(f"❌ Composition list failed: {result}")
                
            return True
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = asyncio.run(test_composition_api())
    sys.exit(0 if success else 1)