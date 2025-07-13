#!/usr/bin/env python3
"""
Test script to verify agent autonomous execution issue.

This script will:
1. Spawn an agent with base_single_agent profile
2. Send a message asking it to emit a specific JSON event
3. Check if the agent actually emits the event or just describes what it would do
"""

import asyncio
import json
import time
from ksi_client import EventClient


async def test_agent_autonomy():
    """Test if agents can execute autonomously and emit JSON events."""
    
    async with EventClient() as client:
        print("1. Spawning test agent...")
        
        # Spawn agent with base_single_agent profile
        spawn_result = await client.send_single("agent:spawn", {
            "profile": "base_single_agent",
            "agent_id": "test_autonomy_agent"
        })
        
        if spawn_result.get("error"):
            print(f"Error spawning agent: {spawn_result}")
            return
            
        agent_id = spawn_result["agent_id"]
        print(f"Agent spawned: {agent_id}")
        
        # Wait for agent to be ready
        await asyncio.sleep(2)
        
        print("\n2. Sending message asking agent to emit JSON event...")
        
        # Send message asking agent to emit a specific event
        message = """Please emit a JSON event with the following structure:
{"event": "test:autonomous_action", "data": {"status": "success", "message": "I can execute autonomously"}}

Just output the JSON directly without any explanation."""
        
        send_result = await client.send_single("agent:send_message", {
            "agent_id": agent_id,
            "message": {
                "role": "user",
                "content": message
            }
        })
        
        if send_result.get("error"):
            print(f"Error sending message: {send_result}")
            return
            
        print("Message sent to agent")
        
        # Wait for response
        print("\n3. Waiting for agent response...")
        await asyncio.sleep(10)
        
        # Check if the test event was emitted
        print("\n4. Checking for emitted events...")
        
        # Query event log for our test event
        events_result = await client.send_single("monitor:get_events", {
            "limit": 10,
            "pattern": "test:autonomous_action"
        })
        
        if events_result.get("error"):
            print(f"Error querying events: {events_result}")
        else:
            events = events_result.get("events", [])
            if events:
                print(f"✅ SUCCESS: Agent emitted {len(events)} test event(s)")
                for event in events:
                    print(f"  - Event: {event}")
            else:
                print("❌ FAILURE: No test events found - agent likely described rather than executed")
        
        # Also check the agent's actual response
        print("\n5. Checking agent's raw response...")
        
        # Get conversation history
        conv_result = await client.send_single("conversation:list", {
            "limit": 5
        })
        
        if not conv_result.get("error"):
            conversations = conv_result.get("conversations", [])
            for conv in conversations:
                if "test_autonomy_agent" in str(conv):
                    print(f"Found agent conversation: {conv.get('session_id')}")
                    # Could read the actual response file here if needed
        
        # Cleanup
        print("\n6. Terminating test agent...")
        await client.send_single("agent:terminate", {
            "agent_id": agent_id
        })
        print("Test complete!")


if __name__ == "__main__":
    print("=== Testing Agent Autonomous Execution ===\n")
    asyncio.run(test_agent_autonomy())