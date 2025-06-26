#!/usr/bin/env python3
"""
Test script for the event-based client with the new plugin architecture.

This tests:
- Event-based client connection
- Legacy command compatibility
- Event subscriptions
- Completion flow
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksi_client import EventBasedClient, EventChatClient


async def test_basic_connection():
    """Test basic connection and health check."""
    print("\n=== Testing Basic Connection ===")
    
    async with EventBasedClient() as client:
        print(f"Connected as {client.client_id}")
        
        # Test health check
        try:
            health = await client.health_check()
            print(f"Health check: {health}")
        except Exception as e:
            print(f"Health check failed: {e}")
            print("Note: This might fail if daemon is using legacy format")


async def test_event_subscriptions():
    """Test event subscription functionality."""
    print("\n=== Testing Event Subscriptions ===")
    
    events_received = []
    
    async def event_handler(event_name: str, data: dict):
        print(f"Received event: {event_name}")
        events_received.append((event_name, data))
    
    async with EventBasedClient() as client:
        # Subscribe to system events
        client.subscribe("system:*", event_handler)
        
        # Trigger some events
        await client.emit_event("system:test", {"message": "Test event"})
        
        # Wait a bit for events
        await asyncio.sleep(1)
        
        print(f"Received {len(events_received)} events")


async def test_legacy_compatibility():
    """Test legacy command compatibility."""
    print("\n=== Testing Legacy Command Compatibility ===")
    
    client = EventBasedClient()
    await client.connect()
    
    try:
        # Send a legacy-style command directly
        legacy_cmd = {
            "command": "HEALTH_CHECK",
            "parameters": {}
        }
        
        # Write directly to test legacy format
        cmd_str = json.dumps(legacy_cmd) + '\n'
        client.writer.write(cmd_str.encode())
        await client.writer.drain()
        
        # Read response
        response_data = await asyncio.wait_for(
            client.reader.readline(), 
            timeout=5.0
        )
        
        if response_data:
            response = json.loads(response_data.decode().strip())
            print(f"Legacy command response: {response}")
            
            if response.get("status") == "success":
                print("✓ Legacy command compatibility working")
            else:
                print("✗ Legacy command failed")
        else:
            print("✗ No response received")
            
    except asyncio.TimeoutError:
        print("✗ Legacy command timed out")
    except Exception as e:
        print(f"✗ Legacy command error: {e}")
    finally:
        await client.disconnect()


async def test_plugin_discovery():
    """Test plugin discovery and capabilities."""
    print("\n=== Testing Plugin Discovery ===")
    
    async with EventBasedClient() as client:
        try:
            # Get loaded plugins
            plugins = await client.get_plugins()
            print(f"Found {len(plugins)} plugins:")
            
            for name, info in plugins.items():
                print(f"  - {name}: {info.get('description', 'No description')}")
                caps = info.get('capabilities', {})
                if caps.get('event_namespaces'):
                    print(f"    Namespaces: {', '.join(caps['event_namespaces'])}")
                if caps.get('provides_services'):
                    print(f"    Services: {', '.join(caps['provides_services'])}")
            
            # Get aggregated capabilities
            capabilities = await client.get_capabilities()
            print(f"\nTotal capabilities:")
            for cap_type, items in capabilities.items():
                print(f"  {cap_type}: {len(items)} items")
                
        except Exception as e:
            print(f"Plugin discovery failed: {e}")
            print("Note: This requires system:plugins event to be implemented")


async def test_chat_client():
    """Test the simplified chat client."""
    print("\n=== Testing Event Chat Client ===")
    
    async with EventChatClient() as chat:
        print(f"Chat client connected as {chat.client_id}")
        
        try:
            # Send a test prompt
            print("Sending test prompt...")
            response, session_id = await chat.send_prompt(
                "What is 2+2? Reply with just the number.",
                model="sonnet"
            )
            
            print(f"Response: {response}")
            print(f"Session ID: {session_id}")
            
            # Test conversation continuity
            response2, session_id2 = await chat.send_prompt(
                "What was my previous question?",
                session_id=session_id
            )
            
            print(f"Follow-up: {response2[:100]}...")
            print(f"Same session: {session_id == session_id2}")
            
        except Exception as e:
            print(f"Chat test failed: {e}")
            print("Note: This requires completion plugin to be working")


async def test_completion_flow():
    """Test the full completion flow with events."""
    print("\n=== Testing Completion Flow ===")
    
    completion_events = []
    
    async def completion_logger(event_name: str, data: dict):
        print(f"Completion event: {event_name}")
        completion_events.append(event_name)
    
    async with EventBasedClient() as client:
        # Subscribe to completion events
        client.subscribe("completion:*", completion_logger)
        
        try:
            print("Creating completion...")
            result = await client.create_completion(
                prompt="Say 'Hello from the event-based client!'",
                timeout=30.0
            )
            
            print(f"Completion result: {result}")
            print(f"Events observed: {completion_events}")
            
        except Exception as e:
            print(f"Completion failed: {e}")
            print("Note: This requires completion plugin to handle events")


async def main():
    """Run all tests."""
    print("KSI Event-Based Client Test Suite")
    print("=================================")
    
    # Check if daemon is running
    from ksi_common import config
    socket_path = config.socket_path
    if not socket_path.exists():
        print("\n⚠️  Daemon socket not found!")
        print("Please start the daemon with: ./daemon_control.sh start")
        return
    
    # Run tests
    tests = [
        test_basic_connection,
        test_event_subscriptions,
        test_legacy_compatibility,
        test_plugin_discovery,
        test_chat_client,
        test_completion_flow
    ]
    
    for test in tests:
        try:
            await test()
        except Exception as e:
            print(f"\n❌ Test {test.__name__} failed with: {e}")
        
        # Small delay between tests
        await asyncio.sleep(0.5)
    
    print("\n=== Test Suite Complete ===")


if __name__ == "__main__":
    asyncio.run(main())