#!/usr/bin/env python3
"""Test the conversation service plugin."""

import json
import asyncio
from pathlib import Path
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksi_client import AsyncClient


async def test_conversation_service():
    """Test conversation service functionality."""
    print("Testing conversation service plugin...")
    
    # Create client
    client = AsyncClient(
        client_id="test_conversation_client",
        socket_path="var/run/daemon.sock"
    )
    
    try:
        # Connect to daemon
        await client.connect()
        print("✓ Connected to daemon")
        
        # Test 1: Get conversation stats
        print("\n1. Testing conversation:stats...")
        result = await client.request_event("conversation:stats", {})
        if result and 'error' not in result:
            print(f"✓ Stats: {result.get('total_conversations', 0)} conversations, "
                  f"{result.get('total_messages', 0)} messages")
        else:
            print(f"✗ Stats failed: {result}")
        
        # Test 2: List conversations
        print("\n2. Testing conversation:list...")
        result = await client.request_event("conversation:list", {
            "limit": 5,
            "sort_by": "last_timestamp",
            "reverse": True
        })
        if result and 'error' not in result:
            convs = result.get('conversations', [])
            print(f"✓ Found {len(convs)} recent conversations")
            for conv in convs[:3]:
                print(f"  - {conv['session_id']}: {conv['message_count']} messages")
        else:
            print(f"✗ List failed: {result}")
        
        # Test 3: Search conversations
        print("\n3. Testing conversation:search...")
        result = await client.request_event("conversation:search", {
            "query": "hello",
            "limit": 5
        })
        if result and 'error' not in result:
            results = result.get('results', [])
            print(f"✓ Search found {len(results)} conversations containing 'hello'")
            for res in results[:2]:
                print(f"  - {res['session_id']}: {res['match_count']} matches")
        else:
            print(f"✗ Search failed: {result}")
        
        # Test 4: Get specific conversation (if any exist)
        print("\n4. Testing conversation:get...")
        list_result = await client.request_event("conversation:list", {"limit": 1})
        if list_result and list_result.get('conversations'):
            session_id = list_result['conversations'][0]['session_id']
            result = await client.request_event("conversation:get", {
                "session_id": session_id,
                "limit": 5
            })
            if result and 'error' not in result:
                msgs = result.get('messages', [])
                print(f"✓ Retrieved {len(msgs)} messages from {session_id}")
                for msg in msgs[:2]:
                    print(f"  - {msg['sender']}: {msg['content'][:50]}...")
            else:
                print(f"✗ Get failed: {result}")
        else:
            print("  (No conversations available to test)")
        
        # Test 5: Export conversation
        print("\n5. Testing conversation:export...")
        if list_result and list_result.get('conversations'):
            session_id = list_result['conversations'][0]['session_id']
            result = await client.request_event("conversation:export", {
                "session_id": session_id,
                "format": "markdown"
            })
            if result and 'error' not in result:
                print(f"✓ Exported to: {result.get('filename')}")
                print(f"  Size: {result.get('size_bytes', 0)} bytes")
                print(f"  Messages: {result.get('message_count', 0)}")
            else:
                print(f"✗ Export failed: {result}")
        
        print("\n✅ All tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(test_conversation_service())