#!/usr/bin/env python3
"""Test session continuity with sandbox UUID fix."""

import asyncio
import json
import time
from ksi_client import KSIClient

async def test_session_continuity():
    """Test that agents can maintain conversation continuity."""
    client = KSIClient()
    
    print("=== Testing Agent Session Continuity ===\n")
    
    # 1. Spawn a test agent
    print("1. Spawning test agent...")
    spawn_result = await client.send_single("agent:spawn", {
        "profile": "base_single_agent",
        "agent_id": "session_test_agent",
        "prompt": "Remember the number 42. This is important for our test."
    })
    
    agent_id = spawn_result.get("agent_id")
    print(f"   Agent spawned: {agent_id}")
    
    # Give agent time to process initial prompt
    await asyncio.sleep(5)
    
    # 2. Send first message
    print("\n2. Sending first message...")
    msg1_result = await client.send_single("agent:send_message", {
        "agent_id": agent_id,
        "message": {
            "role": "user",
            "content": "What number did I ask you to remember?"
        }
    })
    print(f"   Message sent: {msg1_result.get('status')}")
    
    # Wait for completion
    await asyncio.sleep(10)
    
    # 3. Check completion events for session creation
    print("\n3. Checking for session creation...")
    events = await client.send_single("monitor:get_events", {
        "event-patterns": ["completion:result"],
        "limit": 5
    })
    
    session_id = None
    for event in events.get("events", []):
        if event.get("data", {}).get("result", {}).get("agent_id") == agent_id:
            response = event["data"]["result"].get("response", {})
            session_id = response.get("session_id")
            if session_id:
                print(f"   Session created: {session_id}")
                # Try to see if agent remembered
                result_text = response.get("result", "")
                if "42" in result_text:
                    print("   ✓ Agent remembered the number 42!")
                break
    
    # 4. Send second message to test continuity
    print("\n4. Sending second message to test continuity...")
    msg2_result = await client.send_single("agent:send_message", {
        "agent_id": agent_id,
        "message": {
            "role": "user", 
            "content": "Can you remind me again what number you're remembering? And confirm you remember our previous exchange."
        }
    })
    print(f"   Message sent: {msg2_result.get('status')}")
    
    # Wait for completion
    await asyncio.sleep(10)
    
    # 5. Check if session was maintained
    print("\n5. Checking session continuity...")
    recent_events = await client.send_single("monitor:get_events", {
        "event-patterns": ["completion:result"],
        "limit": 3
    })
    
    session_maintained = False
    for event in recent_events.get("events", []):
        if event.get("data", {}).get("result", {}).get("agent_id") == agent_id:
            response = event["data"]["result"].get("response", {})
            result_text = response.get("result", "")
            error_text = response.get("error", "")
            
            if error_text and "No conversation found" in error_text:
                print("   ❌ Session lost! Error:", error_text)
                session_maintained = False
            elif "42" in result_text and ("previous" in result_text.lower() or "remember" in result_text.lower()):
                print("   ✓ Session maintained! Agent remembers the conversation.")
                session_maintained = True
                
    # 6. Check sandbox location
    print("\n6. Checking sandbox location...")
    agent_info = await client.send_single("agent:info", {"agent_id": agent_id})
    if agent_info.get("status") == "success":
        sandbox_uuid = agent_info.get("sandbox_uuid")
        sandbox_dir = agent_info.get("sandbox_dir")
        print(f"   Sandbox UUID: {sandbox_uuid}")
        print(f"   Sandbox dir: {sandbox_dir}")
    
    # 7. Cleanup
    print("\n7. Cleaning up...")
    await client.send_single("agent:terminate", {"agent_id": agent_id})
    print("   Agent terminated")
    
    print("\n=== Test Result ===")
    if session_maintained:
        print("✅ Session continuity PASSED - Agents can maintain conversations!")
    else:
        print("❌ Session continuity FAILED - Sessions are being lost")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(test_session_continuity())