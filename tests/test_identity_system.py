#!/usr/bin/env python3

"""
Test script for the identity management system
"""

import asyncio
import json
import socket
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def send_daemon_command(command: str) -> dict:
    """Send command to daemon and get response"""
    try:
        reader, writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
        
        # Send command
        if not command.endswith('\n'):
            command += '\n'
        writer.write(command.encode())
        await writer.drain()
        
        # Read response
        response = await reader.readline()
        writer.close()
        await writer.wait_closed()
        
        if response:
            return json.loads(response.decode().strip())
        return None
        
    except Exception as e:
        print(f"Error communicating with daemon: {e}")
        return None

async def test_identity_system():
    """Test the identity management system"""
    print("🔧 Testing Identity Management System")
    print("="*50)
    
    # Test 1: Create a new identity
    print("\n1. Creating a new identity...")
    result = await send_daemon_command("CREATE_IDENTITY:test-agent:TestBot:researcher:[\"analytical\", \"thorough\"]")
    
    if result and result.get('status') == 'identity_created':
        print(f"✅ Identity created: {result['identity']['display_name']}")
        print(f"   Traits: {result['identity']['personality_traits']}")
        print(f"   UUID: {result['identity']['identity_uuid']}")
    else:
        print(f"❌ Failed to create identity: {result}")
        return False
    
    # Test 2: Get the identity
    print("\n2. Retrieving the identity...")
    result = await send_daemon_command("GET_IDENTITY:test-agent")
    
    if result and result.get('status') == 'identity_found':
        identity = result['identity']
        print(f"✅ Identity found: {identity['display_name']}")
        print(f"   Role: {identity['role']}")
        print(f"   Appearance: {identity['appearance']}")
    else:
        print(f"❌ Failed to get identity: {result}")
        return False
    
    # Test 3: Update the identity
    print("\n3. Updating the identity...")
    updates = {
        "display_name": "ResearchBot-Pro",
        "preferences": {
            "communication_style": "academic",
            "verbosity": "detailed"
        }
    }
    
    result = await send_daemon_command(f"UPDATE_IDENTITY:test-agent:{json.dumps(updates)}")
    
    if result and result.get('status') == 'identity_updated':
        print(f"✅ Identity updated: {result['identity']['display_name']}")
        print(f"   Communication style: {result['identity']['preferences']['communication_style']}")
    else:
        print(f"❌ Failed to update identity: {result}")
        return False
    
    # Test 4: List all identities
    print("\n4. Listing all identities...")
    result = await send_daemon_command("LIST_IDENTITIES")
    
    if result and result.get('status') == 'identities_listed':
        identities = result['identities']
        print(f"✅ Found {result['count']} identities:")
        for agent_id, info in identities.items():
            print(f"   {agent_id}: {info['display_name']} ({info['role']})")
            print(f"      Traits: {', '.join(info['personality_traits'])}")
    else:
        print(f"❌ Failed to list identities: {result}")
        return False
    
    # Test 5: Remove the test identity
    print("\n5. Removing test identity...")
    result = await send_daemon_command("REMOVE_IDENTITY:test-agent")
    
    if result and result.get('status') == 'identity_removed':
        print(f"✅ Identity removed for agent: {result['agent_id']}")
    else:
        print(f"❌ Failed to remove identity: {result}")
        return False
    
    print("\n🎉 All identity system tests passed!")
    return True

async def main():
    """Main test runner"""
    # Check if daemon is running
    try:
        reader, writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
        writer.close()
        await writer.wait_closed()
    except Exception:
        print("❌ Daemon is not running. Please start it first with: python3 daemon.py")
        return
    
    success = await test_identity_system()
    
    if success:
        print("\n✅ All tests passed! Identity system is working correctly.")
    else:
        print("\n❌ Some tests failed. Check the output above.")

if __name__ == '__main__':
    asyncio.run(main())