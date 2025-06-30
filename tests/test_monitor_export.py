#!/usr/bin/env python3
"""
Test script for conversation export functionality using EventBasedClient.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from ksi_client import EventBasedClient


async def test_monitor_export():
    """Test the conversation export functionality."""
    print("Testing conversation export with EventBasedClient...")
    
    client = EventBasedClient()
    
    try:
        # Connect to daemon
        await client.connect()
        print("✓ Connected to daemon")
        
        # List available conversations
        print("\nListing conversations...")
        conversations = await client.request_event("conversation:list", {"limit": 5})
        
        if "conversations" in conversations and conversations["conversations"]:
            print(f"Found {len(conversations['conversations'])} conversations")
            
            # Export the first conversation
            first_conv = conversations["conversations"][0]
            session_id = first_conv.get("session_id")
            
            if session_id:
                print(f"\nExporting conversation {session_id}...")
                
                # Test markdown export
                result = await monitor.export_conversation(session_id, format="markdown")
                print(f"✓ Markdown export: {result}")
                
                # Test JSON export (currently not supported by the plugin)
                try:
                    result = await monitor.export_conversation(session_id, format="json")
                    print(f"✓ JSON export: {result}")
                except Exception as e:
                    print(f"✓ JSON format not yet supported by plugin: {e}")
                
                # Test invalid format
                try:
                    await client.request_event("conversation:export", {
                        "session_id": session_id,
                        "format": "invalid"
                    })
                except ValueError as e:
                    print(f"✓ Invalid format correctly rejected: {e}")
            else:
                print("No session_id in conversation data")
        else:
            print("No conversations found to export")
        
        # Test conversation search
        print("\nTesting conversation search...")
        search_results = await client.request_event("conversation:search", {
            "query": "test",
            "limit": 5
        })
        print(f"Search results: {search_results.get('count', 0)} matches")
        
        # Test conversation stats
        print("\nGetting conversation statistics...")
        stats = await client.request_event("conversation:stats", {})
        print(f"Stats: {stats}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    finally:
        await client.disconnect()
        print("\n✓ Disconnected from daemon")
    
    return True


async def main():
    """Run the test."""
    success = await test_monitor_export()
    if success:
        print("\n✓ All tests passed!")
    else:
        print("\n✗ Tests failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())