#!/usr/bin/env python3
"""
Test a single prompt to debug the framework.
"""

import asyncio
import json
from ksi_socket_utils import KSISocketClient, wait_for_completion


async def test_single_prompt():
    """Test a single prompt directly."""
    print("Testing single prompt...\n")
    
    client = KSISocketClient("../var/run/daemon.sock")
    
    # Check daemon health
    if not client.check_health():
        print("❌ Daemon not healthy!")
        return
    
    print("✓ Daemon is healthy")
    
    # Spawn a simple agent
    print("\nSpawning agent...")
    spawn_result = await client.spawn_agent(
        profile="base_single_agent",
        prompt="Say OK",
        model="claude-cli/sonnet"
    )
    
    print(f"Spawn result: {json.dumps(spawn_result, indent=2)}")
    
    if "error" in spawn_result:
        print(f"❌ Spawn error: {spawn_result['error']}")
        return
    
    # Get session ID
    session_id = spawn_result.get("data", {}).get("session_id")
    agent_id = spawn_result.get("data", {}).get("agent_id")
    construct_id = spawn_result.get("data", {}).get("construct_id")
    
    print(f"\nSession ID: {session_id}")
    print(f"Agent ID: {agent_id}")
    print(f"Construct ID: {construct_id}")
    
    if not session_id:
        print("❌ No session_id in spawn result")
        return
    
    # Wait for completion
    print("\nWaiting for completion...")
    completion = await wait_for_completion(
        session_id,
        timeout=30,
        poll_interval=1.0,
        socket_path="../var/run/daemon.sock"
    )
    
    if completion:
        print(f"\n✓ Completion received:")
        print(f"Response: {completion.get('response', 'No response')}")
        print(f"Model: {completion.get('model', 'Unknown')}")
    else:
        print("❌ Completion timeout or failure")
    
    # Cleanup
    print("\nCleaning up...")
    try:
        await client.terminate_agent(agent_id)
        print("✓ Agent terminated")
    except Exception as e:
        print(f"❌ Cleanup error: {e}")


if __name__ == "__main__":
    asyncio.run(test_single_prompt())