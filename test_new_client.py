#!/usr/bin/env python3
"""
Test script for new adaptive KSI client
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from ksi_client import EventClient


async def test_client():
    """Test the new adaptive client."""
    print("Testing new adaptive KSI client...")
    print("-" * 50)
    
    try:
        async with EventClient() as client:
            print("✓ Client connected and discovered events")
            
            # Test 1: Show discovered namespaces
            namespaces = client.get_namespaces()
            print(f"\nDiscovered {len(namespaces)} namespaces:")
            for ns in sorted(namespaces)[:5]:  # Show first 5
                events = client.get_events_in_namespace(ns)
                print(f"  - {ns}: {len(events)} events")
            
            # Test 2: Show permission profiles
            profiles = client.get_permission_profiles()
            print(f"\nAvailable permission profiles: {profiles}")
            
            # Test 3: Show tools for restricted profile
            restricted_tools = client.get_profile_tools("restricted")
            print(f"\nRestricted profile tools:")
            print(f"  Allowed: {restricted_tools['allowed']}")
            print(f"  Disallowed: {restricted_tools['disallowed'][:5]}...")  # First 5
            
            # Test 4: Health check
            print("\nTesting system:health event...")
            health = await client.system.health()
            print(f"  Status: {health.get('status', 'unknown')}")
            
            # Test 5: Chat completion with restricted permissions
            print("\nTesting completion with restricted permissions...")
            response = await client.create_chat_completion(
                prompt="What tools do you have access to?",
                permission_profile="restricted"
            )
            
            print(f"  Response: {response.get('content', 'No content')[:100]}...")
            
            # Test 6: Generate type stubs
            print("\nGenerating type stubs...")
            stub_path = Path("ksi_client/types/discovered.pyi")
            client.generate_type_stubs(stub_path)
            print(f"  Type stubs written to: {stub_path}")
            
            print("\n✓ All tests passed!")
            
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(test_client())
    sys.exit(exit_code)