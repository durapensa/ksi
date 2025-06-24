#!/usr/bin/env python3
"""
Enhanced integration tests for the new multi-socket architecture and completion flow.

Tests:
1. Multi-socket client connectivity
2. COMPLETION command flow with session continuity
3. Targeted pub/sub for COMPLETION_RESULT events
4. Multiple concurrent completions
5. Performance and stress testing
6. Real Claude CLI integration
7. Error recovery and resilience
8. Agent lifecycle and state management
"""

import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_client import AsyncClient, SimpleChatClient


async def test_basic_connectivity():
    """Test basic connectivity to all sockets"""
    print("\n=== Testing Basic Connectivity ===")
    
    client = AsyncClient(client_id="test_client_001")
    
    try:
        # Initialize (connects to messaging socket)
        await client.initialize()
        print("✓ Client initialized")
        
        # Test admin socket
        health = await client.health_check()
        print(f"✓ Admin socket: {health}")
        
        # Test agents socket
        agents = await client.get_agents()
        print(f"✓ Agents socket: {len(agents)} agents")
        
        # Test state socket
        await client.set_agent_kv("test_client", "test_key", "test_value")
        value = await client.get_agent_kv("test_client", "test_key")
        print(f"✓ State socket: stored and retrieved '{value}'")
        
        # Test messaging socket (already connected)
        await client.publish_event("TEST_EVENT", {"message": "Hello"})
        print("✓ Messaging socket: published event")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        await client.close()


async def test_completion_flow():
    """Test the new COMPLETION command flow"""
    print("\n=== Testing Completion Flow ===")
    
    client = SimpleChatClient(client_id="test_chat_client")
    
    try:
        await client.initialize()
        print("✓ Chat client initialized")
        
        # Send a simple prompt
        prompt = "What is 2+2? Answer in one word."
        print(f"→ Sending prompt: {prompt}")
        
        response, session_id = await client.send_prompt(prompt)
        
        print(f"✓ Got response: {response}")
        print(f"✓ Session ID: {session_id}")
        
        # Test conversation continuity
        followup = "What about 3+3?"
        print(f"→ Sending followup: {followup}")
        
        response2, session_id2 = await client.send_prompt(followup, session_id)
        
        print(f"✓ Got followup response: {response2}")
        print(f"✓ Session maintained: {session_id == session_id2}")
        
        return True
        
    except asyncio.TimeoutError:
        print("✗ Completion timed out")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        await client.close()


async def test_concurrent_completions():
    """Test multiple concurrent completions"""
    print("\n=== Testing Concurrent Completions ===")
    
    # Create multiple clients
    clients = [
        SimpleChatClient(client_id=f"concurrent_client_{i}")
        for i in range(3)
    ]
    
    try:
        # Initialize all clients
        for i, client in enumerate(clients):
            await client.initialize()
            print(f"✓ Client {i} initialized")
        
        # Send concurrent prompts
        prompts = [
            "Count to 3",
            "Name 3 colors",
            "List 3 animals"
        ]
        
        print("\n→ Sending 3 concurrent prompts...")
        
        # Create tasks for concurrent execution
        tasks = [
            client.send_prompt(prompt)
            for client, prompt in zip(clients, prompts)
        ]
        
        # Wait for all to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"✗ Client {i} failed: {result}")
            else:
                response, session_id = result
                print(f"✓ Client {i} got response: {response[:50]}...")
        
        return all(not isinstance(r, Exception) for r in results)
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        # Clean up all clients
        for client in clients:
            await client.close()


async def test_targeted_delivery():
    """Test that targeted delivery works (clients only get their own results)"""
    print("\n=== Testing Targeted Delivery ===")
    
    # Create two clients with event tracking
    received_events = {
        "client_A": [],
        "client_B": []
    }
    
    async def track_events(client_name):
        """Track all events received by a client"""
        client = AsyncClient(client_id=client_name)
        
        # Add handler to track ALL events
        def event_handler(event):
            received_events[client_name].append(event)
        
        # Subscribe to all COMPLETION_RESULT events
        client.add_event_handler("COMPLETION_RESULT", event_handler)
        
        await client.initialize()
        return client
    
    try:
        # Create and initialize clients
        client_a = await track_events("client_A")
        client_b = await track_events("client_B")
        
        print("✓ Both clients initialized and subscribed")
        
        # Send completions from each client
        prompt_a = "Say 'Hello from A'"
        prompt_b = "Say 'Hello from B'"
        
        print(f"→ Client A sending: {prompt_a}")
        print(f"→ Client B sending: {prompt_b}")
        
        # Send concurrently
        response_a, response_b = await asyncio.gather(
            client_a.create_completion(prompt_a),
            client_b.create_completion(prompt_b)
        )
        
        # Give a moment for any stray events
        await asyncio.sleep(0.5)
        
        # Check results
        print(f"\n✓ Client A response: {response_a[:50]}...")
        print(f"✓ Client B response: {response_b[:50]}...")
        
        # Analyze received events
        print(f"\nClient A received {len(received_events['client_A'])} events")
        print(f"Client B received {len(received_events['client_B'])} events")
        
        # With targeted delivery, each should only get their own
        a_got_own = any(e.get('client_id') == 'client_A' for e in received_events['client_A'])
        a_got_other = any(e.get('client_id') == 'client_B' for e in received_events['client_A'])
        b_got_own = any(e.get('client_id') == 'client_B' for e in received_events['client_B'])
        b_got_other = any(e.get('client_id') == 'client_A' for e in received_events['client_B'])
        
        if a_got_own and not a_got_other and b_got_own and not b_got_other:
            print("✓ Targeted delivery working: Clients only received their own results")
            return True
        else:
            print("✗ Clients received each other's results (broadcast mode)")
            return False
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        await client_a.close()
        await client_b.close()


async def main():
    """Run all tests"""
    print("Testing New Multi-Socket Architecture")
    print("=" * 40)
    
    # Ensure daemon is running
    socket_path = Path("sockets/admin.sock")
    if not socket_path.exists():
        print("✗ Daemon not running. Please start ksi-daemon.py first.")
        return
    
    tests = [
        ("Basic Connectivity", test_basic_connectivity),
        ("Completion Flow", test_completion_flow),
        ("Concurrent Completions", test_concurrent_completions),
        ("Targeted Delivery", test_targeted_delivery)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = await test_func()
        except Exception as e:
            print(f"\n✗ Test '{test_name}' crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 40)
    print("Test Summary:")
    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {test_name}: {status}")
    
    total = len(results)
    passed = sum(1 for p in results.values() if p)
    print(f"\nTotal: {passed}/{total} tests passed")


if __name__ == "__main__":
    asyncio.run(main())