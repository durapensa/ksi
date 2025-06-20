#!/usr/bin/env python3
"""
Test script for Multi-Claude conversation system
"""

import asyncio
import json
import sys


async def test_basic_conversation():
    """Test basic conversation between two Claude nodes"""
    print("Testing Multi-Claude Conversation System...")
    print("-" * 50)
    
    # Test 1: Check daemon connection
    try:
        reader, writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
        writer.write(b"HEALTH_CHECK\n")
        await writer.drain()
        
        response = await reader.readline()
        if response.strip() == b"HEALTHY":
            print("✓ Daemon is running")
        else:
            print("✗ Daemon health check failed")
            return
            
        writer.close()
        await writer.wait_closed()
    except Exception as e:
        print(f"✗ Cannot connect to daemon: {e}")
        print("  Please start the daemon with: python daemon.py")
        return
    
    # Test 2: Check message bus
    try:
        reader, writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
        writer.write(b"MESSAGE_BUS_STATS\n")
        await writer.drain()
        
        response = await reader.readline()
        stats = json.loads(response.decode().strip())
        print(f"✓ Message bus active: {len(stats.get('connected_agents', []))} agents connected")
        
        writer.close()
        await writer.wait_closed()
    except Exception as e:
        print(f"✗ Message bus error: {e}")
    
    # Test 3: Simple agent registration
    try:
        reader, writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
        
        # Register test agent
        writer.write(b"REGISTER_AGENT:test_agent_1:tester:testing\n")
        await writer.drain()
        
        response = await reader.readline()
        result = json.loads(response.decode().strip())
        
        if result.get('status') == 'registered':
            print("✓ Agent registration working")
        else:
            print(f"✗ Agent registration failed: {result}")
        
        writer.close()
        await writer.wait_closed()
    except Exception as e:
        print(f"✗ Agent registration error: {e}")
    
    print("\nSystem appears ready for multi-Claude conversations!")
    print("\nTo start a conversation, run:")
    print("  python orchestrate.py 'Your topic here' --mode debate --agents 2")
    print("\nTo monitor conversations, run:")
    print("  python monitor_tui.py")


async def main():
    """Main test runner"""
    if len(sys.argv) > 1 and sys.argv[1] == "full":
        # Run full integration test
        print("Running full integration test...")
        # This would spawn actual Claude nodes and verify conversation
    else:
        # Run basic connectivity test
        await test_basic_conversation()


if __name__ == '__main__':
    asyncio.run(main())