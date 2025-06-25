#!/usr/bin/env python3
"""Test the event discovery service plugin."""

import json
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksi_client import AsyncClient


async def test_discovery_service():
    """Test event discovery functionality."""
    print("Testing event discovery service...")
    
    # Create client
    client = AsyncClient(
        client_id="test_discovery_client",
        socket_path="var/run/daemon.sock"
    )
    
    try:
        # Connect to daemon
        await client.connect()
        print("✓ Connected to daemon")
        
        # Test 1: Discover all events
        print("\n1. Testing system:discover...")
        result = await client.request_event("system:discover", {})
        if result and 'error' not in result:
            namespaces = result.get('namespaces', [])
            total = result.get('total_events', 0)
            print(f"✓ Found {total} events across {len(namespaces)} namespaces:")
            for ns in namespaces:
                events = result['events'].get(ns, [])
                print(f"  - {ns}: {len(events)} events")
        else:
            print(f"✗ Discovery failed: {result}")
        
        # Test 2: Discover specific namespace
        print("\n2. Testing namespace filter...")
        result = await client.request_event("system:discover", {
            "namespace": "agent"
        })
        if result and 'error' not in result:
            events = result.get('events', {}).get('agent', [])
            print(f"✓ Found {len(events)} agent events:")
            for event in events[:3]:
                print(f"  - {event['event']}: {event['summary']}")
        else:
            print(f"✗ Namespace filter failed: {result}")
        
        # Test 3: Get help for specific event
        print("\n3. Testing system:help...")
        result = await client.request_event("system:help", {
            "event": "completion:request"
        })
        if result and 'error' not in result:
            print(f"✓ Got help for {result['event']}:")
            print(f"  Summary: {result['summary']}")
            print(f"  Parameters:")
            for param, info in result.get('parameters', {}).items():
                req = "required" if info.get('required') else "optional"
                print(f"    - {param} ({info.get('type', 'Any')}) [{req}]")
            if result.get('examples'):
                print(f"  Example: {json.dumps(result['examples'][0], indent=2)}")
        else:
            print(f"✗ Help failed: {result}")
        
        # Test 4: Get daemon capabilities
        print("\n4. Testing system:capabilities...")
        result = await client.request_event("system:capabilities", {})
        if result and 'error' not in result:
            print(f"✓ Daemon capabilities:")
            print(f"  Version: {result.get('version')}")
            print(f"  Plugin-based: {result.get('plugin_based')}")
            print(f"  Namespaces:")
            for ns, info in result.get('namespaces', {}).items():
                print(f"    - {ns}: {info['description']} ({info['event_count']} events)")
        else:
            print(f"✗ Capabilities failed: {result}")
        
        # Test 5: Test GET_COMMANDS equivalent
        print("\n5. Testing GET_COMMANDS equivalent...")
        print("  (In the new system, use system:discover to list all events)")
        result = await client.request_event("system:discover", {
            "include_internal": True
        })
        if result and 'error' not in result:
            # Format like old GET_COMMANDS output
            print("  Available commands (events):")
            for ns, events in result.get('events', {}).items():
                for event in events:
                    params = ", ".join(event.get('parameters', {}).keys())
                    print(f"    {event['event']}: {event['summary']} [{params}]")
        
        print("\n✅ All discovery tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(test_discovery_service())