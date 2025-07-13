#!/usr/bin/env python3
"""
Test agent autonomous execution with unique agent IDs to avoid session conflicts.
"""

import asyncio
import json
import time
import uuid
from pathlib import Path


async def test_autonomy():
    """Test autonomous agent behavior with unique ID."""
    import subprocess
    
    # Generate unique agent ID to avoid session conflicts
    agent_id = f"test_agent_{uuid.uuid4().hex[:8]}"
    entity_id = f"test_entity_{uuid.uuid4().hex[:8]}"
    
    print(f"1. Spawning agent: {agent_id}")
    
    # Spawn agent with unique ID
    result = subprocess.run(
        ["ksi", "send", "agent:spawn", 
         "--agent_id", agent_id,
         "--profile", "base_single_agent"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"Error spawning agent: {result.stderr}")
        return
        
    print("✅ Agent spawned successfully")
    await asyncio.sleep(2)
    
    print("\n2. Sending autonomous execution request...")
    
    # Test autonomous event emission
    message = json.dumps({
        "role": "user",
        "content": f"Create an entity with id '{entity_id}', type 'test', and property 'status' = 'autonomous_success'. Emit the JSON event directly."
    })
    
    result = subprocess.run(
        ["ksi", "send", "agent:send_message", 
         "--agent_id", agent_id,
         "--message", message],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"Error sending message: {result.stderr}")
    else:
        print("✅ Message sent successfully")
    
    # Wait for processing
    print("\n3. Waiting for agent to process...")
    await asyncio.sleep(10)
    
    print("\n4. Checking if entity was created...")
    
    # Check entity creation
    result = subprocess.run(
        ["ksi", "send", "state:entity:get", "--id", entity_id],
        capture_output=True,
        text=True
    )
    
    if "autonomous_success" in result.stdout:
        print("✅ SUCCESS: Agent autonomously created the entity!")
        print(f"   Entity found with status = autonomous_success")
    else:
        print("❌ FAILURE: Entity was not created")
        if "not found" in result.stdout.lower():
            print("   Entity does not exist")
        else:
            print(f"   Response: {result.stdout[:200]}")
    
    print("\n5. Checking event logs...")
    
    # Look for the entity creation event
    result = subprocess.run(
        ["ksi", "send", "monitor:get_events",
         "--limit", "50",
         "--pattern", "state:entity:create"],
        capture_output=True,
        text=True
    )
    
    if result.stdout and entity_id in result.stdout:
        print("✅ SUCCESS: Found state:entity:create event for our entity!")
        
        # Check if it was emitted by the agent
        if f'"_agent_id": "{agent_id}"' in result.stdout:
            print(f"   ✅ Event was emitted by our agent!")
        elif f'"_extracted_from_response": true' in result.stdout:
            print(f"   ✅ Event was extracted from agent response!")
    else:
        print("❌ FAILURE: No entity creation event found")
    
    print("\n6. Checking agent's actual response...")
    
    # Find recent response files
    responses_dir = Path("var/logs/responses")
    recent_files = sorted(
        responses_dir.glob("*.jsonl"), 
        key=lambda p: p.stat().st_mtime, 
        reverse=True
    )[:10]
    
    found_response = False
    for session_file in recent_files:
        try:
            with open(session_file, 'r') as f:
                content = f.read()
                if agent_id in content and entity_id in content:
                    print(f"Found agent response in: {session_file.name}")
                    
                    # Re-read file line by line
                    f.seek(0)
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            if entry.get("ksi", {}).get("client_id") == agent_id:
                                response = entry.get("response", {})
                                if isinstance(response, dict):
                                    result_text = response.get("result", "")
                                    if '{"event"' in result_text:
                                        print("   ✅ Agent emitted JSON event!")
                                        # Extract and show the JSON
                                        import re
                                        json_match = re.search(r'\{[^}]+\}', result_text)
                                        if json_match:
                                            print(f"   JSON: {json_match.group()}")
                                    else:
                                        print("   ❌ No JSON event in response")
                                        print(f"   Response preview: {result_text[:300]}...")
                                found_response = True
                                break
                        except Exception as e:
                            continue
                    
                    if found_response:
                        break
        except:
            pass
    
    if not found_response:
        print("   ⚠️  Could not find agent response in recent files")
    
    print("\n7. Cleanup...")
    
    # Terminate agent
    subprocess.run(
        ["ksi", "send", "agent:terminate", "--agent_id", agent_id],
        capture_output=True
    )
    
    # Delete test entity
    subprocess.run(
        ["ksi", "send", "state:entity:delete", "--id", entity_id],
        capture_output=True
    )
    
    print("✅ Test complete!\n")
    
    # Summary
    print("="*50)
    print("SUMMARY:")
    print("- Agent prompt inclusion: ✅ (verified in previous test)")
    print("- Agent spawning: ✅")
    print("- Message sending: ✅") 
    print("- Autonomous execution: Check results above")
    print("- Session management: Using unique IDs to avoid conflicts")
    print("="*50)


if __name__ == "__main__":
    print("=== Agent Autonomous Execution Test V3 ===\n")
    asyncio.run(test_autonomy())