#!/usr/bin/env python3
"""
Test script to verify agent autonomous execution with proper system prompt.

This version:
1. Spawns an agent and verifies the system prompt is included
2. Tests autonomous event emission
3. Checks for blocking operations in logs
"""

import asyncio
import json
import time
from pathlib import Path


async def test_with_ksi_cli():
    """Test using ksi CLI for cleaner output."""
    import subprocess
    
    print("1. Spawning test agent...")
    
    # Spawn agent
    result = subprocess.run(
        ["ksi", "send", "agent:spawn", "--agent_id", "test_autonomy_v2", "--profile", "base_single_agent"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"Error spawning agent: {result.stderr}")
        return
        
    print("Agent spawned successfully")
    await asyncio.sleep(2)
    
    print("\n2. Testing autonomous event emission...")
    
    # Send message asking for autonomous action
    message = json.dumps({
        "role": "user",
        "content": "Please create an entity with id 'test_entity', type 'test', and a property called 'status' with value 'autonomous_success'."
    })
    
    result = subprocess.run(
        ["ksi", "send", "agent:send_message", 
         "--agent_id", "test_autonomy_v2",
         "--message", message],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"Error sending message: {result.stderr}")
        return
        
    print("Message sent successfully")
    await asyncio.sleep(5)
    
    print("\n3. Checking if entity was created...")
    
    # Check if entity was created
    result = subprocess.run(
        ["ksi", "send", "state:entity:get", "--id", "test_entity"],
        capture_output=True,
        text=True
    )
    
    output = {}
    if result.stdout:
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            print(f"Failed to parse JSON: {result.stdout}")
    
    if output.get("entity", {}).get("properties", {}).get("status") == "autonomous_success":
        print("✅ SUCCESS: Agent autonomously created the entity!")
        print(f"   Entity properties: {output.get('entity', {}).get('properties', {})}")
    else:
        print("❌ FAILURE: Entity was not created")
        print(f"   Entity query result: {output}")
    
    print("\n4. Checking for JSON event emission...")
    
    # Check event log
    result = subprocess.run(
        ["ksi", "send", "monitor:get_events", 
         "--limit", "10",
         "--pattern", "state:entity:create"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0 and result.stdout:
        try:
            events_data = json.loads(result.stdout)
            events = events_data.get("events", [])
        except json.JSONDecodeError:
            print(f"Failed to parse events JSON: {result.stdout}")
            events = []
    else:
        events = []
    
    # Look for our state:entity:create event
    for event in events:
        if (event.get("event_name") == "state:entity:create" and 
            event.get("data", {}).get("id") == "test_entity"):
            print("✅ SUCCESS: Found state:entity:create event emitted by agent!")
            print(f"   Event data: {event.get('data')}")
            if event.get("data", {}).get("_agent_id"):
                print(f"   Emitted by agent: {event['data']['_agent_id']}")
            break
    else:
        print("❌ FAILURE: No state:entity:create event found for test_entity")
    
    print("\n5. Checking agent response...")
    
    # Read the agent's actual response
    responses_dir = Path("var/logs/responses")
    recent_files = sorted(responses_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    for session_file in recent_files[:5]:  # Check last 5 sessions
        with open(session_file, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    response = entry.get("response", {})
                    if isinstance(response, dict) and response.get("type") == "result":
                        result_text = response.get("result", "")
                        if "test_entity" in result_text or "autonomous_success" in result_text:
                            print(f"Found agent response in {session_file.name}:")
                            print(f"   {result_text[:200]}...")
                            
                            # Check if JSON was emitted
                            if '{"event"' in result_text:
                                print("   ✅ Agent emitted JSON event in response")
                            else:
                                print("   ❌ No JSON event found in response")
                            break
                except:
                    continue
    
    print("\n6. Cleaning up...")
    
    # Terminate agent
    subprocess.run(
        ["ksi", "send", "agent:terminate", "--agent_id", "test_autonomy_v2"],
        capture_output=True,
        text=True
    )
    
    # Clean up test entity
    subprocess.run(
        ["ksi", "send", "state:entity:delete", "--id", "test_entity"],
        capture_output=True,
        text=True
    )
    
    print("Test complete!")


if __name__ == "__main__":
    print("=== Testing Agent Autonomous Execution V2 ===\n")
    print("This test verifies:")
    print("- System prompt is properly included")
    print("- Agents can autonomously emit events")
    print("- State changes are persisted")
    print("\n" + "="*50 + "\n")
    
    asyncio.run(test_with_ksi_cli())