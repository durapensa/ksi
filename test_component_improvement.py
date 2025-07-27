#!/usr/bin/env python3
"""
Test script for component improvement workflow.
Tests that agents can successfully improve components.
"""

import json
import time
import subprocess

def test_component_improvement():
    """Test the component improvement workflow."""
    
    def ksi_send(event, data):
        """Send KSI event via CLI."""
        cmd = ["ksi", "send", event]
        for key, value in data.items():
            if isinstance(value, dict) or isinstance(value, list):
                cmd.extend([f"--{key}", json.dumps(value)])
            else:
                cmd.extend([f"--{key}", str(value)])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            return {}
        
        try:
            return json.loads(result.stdout)
        except:
            return {"raw": result.stdout}
    
    # The verbose greeting component to improve
    verbose_component = """---
component_type: agent
name: verbose_greeting_agent
version: 1.0.0
description: An overly verbose greeting agent that needs optimization
author: test_system
---

# Professional Greeting Specialist Agent

You are a highly trained professional greeting specialist with extensive experience in interpersonal communication and customer service excellence.

## Your Role and Responsibilities

As a greeting specialist, your primary responsibility is to provide warm, welcoming, and professionally appropriate greetings to all users who interact with you. You should always maintain a friendly and approachable demeanor while ensuring that your greetings are contextually appropriate.

## Greeting Guidelines

When a user greets you with any form of salutation such as:
- "Hello"
- "Hi"
- "Good morning"
- "Good afternoon"  
- "Good evening"
- "Hey"
- "Greetings"
- Or any other form of greeting in any language

You should respond with an appropriate greeting that:
1. Acknowledges their greeting
2. Is warm and welcoming
3. Is professionally appropriate
4. May include a brief pleasantry or offer of assistance

## Example Interactions

If a user says "Hello", you might respond with:
- "Hello! How may I assist you today?"
- "Greetings! It's wonderful to hear from you."
- "Hello there! I hope you're having a great day."

## Important Considerations

Remember to always:
- Be respectful and courteous
- Match the formality level of the user when appropriate
- Maintain a positive and helpful attitude
- Be ready to transition from greeting to providing assistance

Your goal is to make every user feel welcomed and valued through your greeting interactions."""
    
    print("Testing component improvement workflow...")
    
    # Step 1: Spawn a component improver agent
    print("\n1. Spawning component improver agent...")
    spawn_result = ksi_send("agent:spawn", {
        "component": "agents/comprehensive_component_improver",
        "agent_id": "test_improver_workflow",
        "task": "Improve components comprehensively"
    })
    
    if spawn_result.get("status") != "created":
        print(f"Failed to spawn agent: {spawn_result}")
        return False
    
    print(f"✓ Agent spawned: {spawn_result.get('agent_id')}")
    
    # Wait for agent to initialize
    time.sleep(2)
    
    # Step 2: Send the component for improvement
    print("\n2. Sending component for improvement...")
    improvement_request = f"Please improve this component:\n\n{verbose_component}"
    
    completion_result = ksi_send("completion:async", {
        "agent_id": "test_improver_workflow",
        "prompt": improvement_request
    })
    
    request_id = completion_result.get("request_id")
    print(f"✓ Request queued: {request_id}")
    
    # Step 3: Wait for completion
    print("\n3. Waiting for improvement result...")
    max_wait = 60  # seconds
    check_interval = 5
    elapsed = 0
    
    while elapsed < max_wait:
        time.sleep(check_interval)
        elapsed += check_interval
        
        # Check completion status
        status_result = ksi_send("completion:status", {
            "request_id": request_id
        })
        
        if status_result.get("status") == "completed":
            print("✓ Improvement completed!")
            break
        elif status_result.get("status") == "failed":
            print(f"✗ Improvement failed: {status_result.get('error')}")
            return False
        else:
            print(f"  Status: {status_result.get('status')} ({elapsed}s elapsed)")
    
    # Step 4: Check for created components
    print("\n4. Checking for improved component...")
    
    # Monitor for composition:create_component events
    monitor_result = ksi_send("monitor:get_events", {
        "event_patterns": ["composition:create_component"],
        "limit": 10,
        "since": time.time() - 120  # Last 2 minutes
    })
    
    created_components = []
    for event in monitor_result.get("events", []):
        if event.get("event") == "composition:create_component":
            created_components.append(event.get("data", {}).get("name"))
    
    if created_components:
        print(f"✓ Components created: {created_components}")
    else:
        print("✗ No components created")
    
    # Step 5: Cleanup
    print("\n5. Cleaning up...")
    ksi_send("agent:terminate", {
        "agent_id": "test_improver_workflow"
    })
    print("✓ Agent terminated")
    
    # Summary
    print("\n" + "="*50)
    print("Test Summary:")
    print(f"- Agent spawned: ✓")
    print(f"- Improvement requested: ✓")
    print(f"- Components created: {'✓' if created_components else '✗'}")
    print("="*50)
    
    return len(created_components) > 0


if __name__ == "__main__":
    # Run the test
    success = test_component_improvement()
    
    if success:
        print("\n✅ Component improvement workflow test PASSED!")
    else:
        print("\n❌ Component improvement workflow test FAILED!")
        print("\nTroubleshooting:")
        print("1. Check daemon logs: tail -f var/logs/daemon/daemon.log.jsonl | jq")
        print("2. Check agent responses: ls -lat var/logs/responses/*.jsonl | head")
        print("3. Verify component exists: ksi send composition:get_component --name 'agents/comprehensive_component_improver'")