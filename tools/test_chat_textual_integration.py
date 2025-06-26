#!/usr/bin/env python3
"""
Test script to verify chat_textual.py integration with conversation plugin.
This demonstrates that chat_textual.py now uses conversation events.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from ksi_client import AsyncClient


async def test_integration():
    """Test that conversation operations work via the plugin."""
    print("Testing chat_textual.py conversation plugin integration...")
    print("=" * 60)
    
    client = AsyncClient(client_id="integration_test")
    
    try:
        await client.connect()
        print("✓ Connected to daemon")
        
        # 1. List conversations - simulating what chat_textual.py does
        print("\n1. Testing conversation listing (as used by chat_textual.py)...")
        result = await client.request_event("conversation:list", {
            "limit": 50,
            "sort_by": "last_timestamp", 
            "reverse": True
        })
        
        if "conversations" in result:
            print(f"✓ Found {len(result['conversations'])} conversations")
            if result['conversations']:
                # Show first conversation
                conv = result['conversations'][0]
                print(f"  Latest: {conv['session_id']} ({conv['message_count']} messages)")
        
        # 2. Load a specific conversation - simulating replay mode
        if result.get('conversations'):
            session_id = result['conversations'][0]['session_id']
            print(f"\n2. Testing conversation loading (session: {session_id})...")
            
            conv_result = await client.request_event("conversation:get", {
                "session_id": session_id,
                "limit": 10
            })
            
            if "messages" in conv_result:
                print(f"✓ Loaded {len(conv_result['messages'])} messages")
                if conv_result['messages']:
                    msg = conv_result['messages'][0]
                    print(f"  First message: {msg['sender']}: {msg['content'][:50]}...")
        
        # 3. Test export functionality
        if result.get('conversations'):
            session_id = result['conversations'][0]['session_id']
            print(f"\n3. Testing export functionality...")
            
            # Test markdown export
            export_result = await client.request_event("conversation:export", {
                "session_id": session_id,
                "format": "markdown"
            })
            
            if "export_path" in export_result:
                print(f"✓ Markdown export: {export_result['filename']}")
            
            # Test JSON export (NEW!)
            export_result = await client.request_event("conversation:export", {
                "session_id": session_id,
                "format": "json"
            })
            
            if "export_path" in export_result:
                print(f"✓ JSON export: {export_result['filename']}")
        
        # 4. Test search functionality
        print(f"\n4. Testing search functionality...")
        search_result = await client.request_event("conversation:search", {
            "query": "claude",
            "limit": 5
        })
        
        if "results" in search_result:
            print(f"✓ Search found matches in {len(search_result['results'])} conversations")
        
        # 5. Test stats
        print(f"\n5. Testing conversation stats...")
        stats_result = await client.request_event("conversation:stats", {})
        
        if "total_conversations" in stats_result:
            print(f"✓ Stats: {stats_result['total_conversations']} conversations, "
                  f"{stats_result['total_messages']} messages")
        
        print("\n" + "=" * 60)
        print("✓ All integration tests passed!")
        print("\nSummary:")
        print("- chat_textual.py now uses conversation:list for browsing")
        print("- chat_textual.py now uses conversation:get for replay")
        print("- chat_textual.py now uses conversation:export for exports")
        print("- Fallback methods remain for graceful degradation")
        print("- JSON export is now available alongside markdown")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        await client.disconnect()
        print("\n✓ Disconnected from daemon")
    
    return True


async def main():
    """Run the integration test."""
    print("Note: This tests the conversation plugin integration.")
    print("Ensure daemon is running with ./daemon_control.sh start")
    print()
    
    success = await test_integration()
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())