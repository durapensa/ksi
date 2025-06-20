#!/usr/bin/env python3

"""
Test script for daemon hot-reload functionality
"""

import asyncio
import json
import os
import subprocess
import time

async def send_command(socket_path, command):
    """Send command to daemon and return response"""
    try:
        reader, writer = await asyncio.open_unix_connection(socket_path)
        writer.write(f"{command}\n".encode())
        await writer.drain()
        
        response = await asyncio.wait_for(reader.readline(), timeout=5.0)
        writer.close()
        await writer.wait_closed()
        
        return response.decode().strip()
    except Exception as e:
        return f"ERROR: {e}"

async def test_hot_reload():
    """Test hot reload functionality"""
    socket_path = 'sockets/claude_daemon.sock'
    
    print("🔧 Testing Hot Reload Mechanism")
    print("=" * 50)
    
    # 1. Check if daemon is running
    print("1. Checking if daemon is running...")
    health_response = await send_command(socket_path, "HEALTH_CHECK")
    if "HEALTHY" not in health_response:
        print(f"❌ Daemon not healthy: {health_response}")
        print("Please start daemon first: python daemon.py")
        return
    print("✅ Daemon is healthy")
    
    # 2. Add some test state
    print("\n2. Adding test state...")
    await send_command(socket_path, "SET_SHARED:test_reload_key:before_reload_value")
    await send_command(socket_path, "REGISTER_AGENT:test_agent:test_role:testing")
    print("✅ Test state added")
    
    # 3. Verify state exists
    print("\n3. Verifying test state...")
    shared_response = await send_command(socket_path, "GET_SHARED:test_reload_key")
    agents_response = await send_command(socket_path, "GET_AGENTS")
    print(f"   Shared state: {shared_response}")
    print(f"   Agents: {len(json.loads(agents_response).get('agents', {}))} registered")
    
    # 4. Trigger hot reload
    print("\n4. Triggering hot reload...")
    reload_start = time.time()
    reload_response = await send_command(socket_path, "RELOAD_DAEMON")
    reload_time = time.time() - reload_start
    
    print(f"   Reload response: {reload_response}")
    print(f"   Reload took: {reload_time:.2f} seconds")
    
    if "error" in reload_response.lower():
        print("❌ Hot reload failed!")
        return
    
    # 5. Wait a moment for handover
    print("\n5. Waiting for handover to complete...")
    await asyncio.sleep(2)
    
    # 6. Verify daemon is still healthy
    print("\n6. Checking daemon health after reload...")
    health_response = await send_command(socket_path, "HEALTH_CHECK")
    if "HEALTHY" not in health_response:
        print(f"❌ Daemon not healthy after reload: {health_response}")
        return
    print("✅ Daemon healthy after reload")
    
    # 7. Verify state preservation
    print("\n7. Verifying state preservation...")
    shared_response_after = await send_command(socket_path, "GET_SHARED:test_reload_key")
    agents_response_after = await send_command(socket_path, "GET_AGENTS")
    
    print(f"   Shared state after: {shared_response_after}")
    print(f"   Agents after: {len(json.loads(agents_response_after).get('agents', {}))} registered")
    
    # Check if state was preserved
    if "before_reload_value" in shared_response_after:
        print("✅ Shared state preserved")
    else:
        print("❌ Shared state lost")
    
    if "test_agent" in agents_response_after:
        print("✅ Agent registry preserved")  
    else:
        print("❌ Agent registry lost")
    
    # 8. Clean up test data
    print("\n8. Cleaning up test data...")
    await send_command(socket_path, "SET_SHARED:test_reload_key:")  # Clear value
    print("✅ Cleanup complete")
    
    print("\n🎉 Hot reload test completed!")

if __name__ == "__main__":
    asyncio.run(test_hot_reload())