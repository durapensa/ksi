#!/usr/bin/env python3
"""Test that agents receive raw event emission feedback."""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from ksi_client import send_event

async def test_event_feedback():
    """Test agent event emission feedback loop."""
    print("\n=== Testing Event Feedback System ===\n")
    
    # 1. Spawn an agent
    print("1. Spawning test agent...")
    result = await send_event("agent:spawn", {
        "profile": "base_single_agent",
        "prompt": "Test the event feedback system. First emit this event: {\"event\": \"state:get\", \"data\": {\"key\": \"test_feedback\"}}. Then wait for my response to see if you received feedback about the event emission."
    })
    
    if result.get("status") != "created":
        print(f"Failed to spawn agent: {result}")
        return
    
    agent_id = result["agent_id"]
    print(f"✓ Agent spawned: {agent_id}")
    
    # 2. Wait a moment for agent to process and emit event
    print("\n2. Waiting for agent to emit event...")
    await asyncio.sleep(3)
    
    # 3. Send follow-up message asking about feedback
    print("\n3. Asking agent about event feedback...")
    result = await send_event("agent:send_message", {
        "agent_id": agent_id,
        "message": {
            "role": "user",
            "content": "Did you receive any feedback about the event you emitted? Please describe what you saw in the ksi_event_extraction data if any."
        }
    })
    
    print(f"✓ Follow-up sent: {result.get('status')}")
    
    # 4. Wait for response
    print("\n4. Waiting for agent response...")
    await asyncio.sleep(5)
    
    # 5. Check daemon logs for emission results
    print("\n5. Checking daemon logs for event extraction...")
    try:
        with open("var/logs/daemon/daemon.log", "r") as f:
            # Read last 50 lines
            lines = f.readlines()[-50:]
            for line in lines:
                if "ksi_event_extraction" in line or "Extracted" in line:
                    print(f"Log: {line.strip()}")
    except Exception as e:
        print(f"Could not read logs: {e}")
    
    # 6. Terminate agent
    print(f"\n6. Terminating agent {agent_id}...")
    await send_event("agent:terminate", {"agent_id": agent_id})
    print("✓ Test complete")

if __name__ == "__main__":
    asyncio.run(test_event_feedback())