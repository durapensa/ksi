#!/usr/bin/env python3
"""Test that agent spawning works after removing composed_prompt."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from ksi_client import EventClient

async def test_agent_spawn():
    """Test agent spawning without composed_prompt."""
    print("\n=== Testing Agent Spawn After composed_prompt Removal ===\n")
    
    async with EventClient() as client:
        # 1. Spawn an agent with self-configuring context
        print("1. Spawning test agent with initial prompt...")
        result = await client.send_single("agent:spawn", {
            "profile": "base_single_agent",
            "prompt": "Hello! Please confirm you received this initial prompt and briefly describe your configuration."
        })
    
        if result.get("status") != "created":
            print(f"Failed to spawn agent: {result}")
            return
        
        agent_id = result["agent_id"]
        print(f"✓ Agent spawned: {agent_id}")
        
        # 2. Wait for agent to process initial prompt
        print("\n2. Waiting for agent to process initial prompt...")
        await asyncio.sleep(5)
        
        # 3. Send a follow-up message
        print("\n3. Sending follow-up message...")
        result = await client.send_single("agent:send_message", {
            "agent_id": agent_id,
            "message": {
                "role": "user",
                "content": "Great! Now please emit this event to test your capabilities: {\"event\": \"system:health\", \"data\": {}}"
            }
        })
        
        print(f"✓ Message sent: {result.get('status')}")
        
        # 4. Wait for response
        print("\n4. Waiting for agent response...")
        await asyncio.sleep(3)
        
        # 5. Check agent info to verify no composed_prompt field
        print("\n5. Checking agent info...")
        info_result = await client.send_single("agent:info", {"agent_id": agent_id})
        
        if "composed_prompt" in info_result:
            print("❌ FAIL: composed_prompt field still present in agent info")
        else:
            print("✓ PASS: composed_prompt field correctly removed")
        
        # 6. Terminate agent
        print(f"\n6. Terminating agent {agent_id}...")
        await client.send_single("agent:terminate", {"agent_id": agent_id})
        print("✓ Test complete")

if __name__ == "__main__":
    asyncio.run(test_agent_spawn())