#!/usr/bin/env python3
"""Simple test of JSON event emission - focuses on what actually works."""

import json
import time
import subprocess
import uuid

def run_ksi_command(args):
    """Run a ksi command and return the response."""
    cmd = ["ksi", "send"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print(f"\nCommand: ksi send {' '.join(args)}")
    print(f"Return code: {result.returncode}")
    
    if result.returncode != 0:
        print(f"STDERR: {result.stderr}")
        return None
    
    print(f"STDOUT: {result.stdout[:500]}...")
    
    # Extract JSON from output
    try:
        # Split by newlines and find JSON responses
        for line in result.stdout.strip().split('\n'):
            if line.strip().startswith('{'):
                return json.loads(line)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
    return None

def test_direct_base_agent():
    """Test 1: Base agent with direct JSON instruction."""
    print("\n=== Test 1: Base Agent with Direct JSON Instruction ===")
    
    agent_id = f"test_direct_{uuid.uuid4().hex[:8]}"
    
    # Spawn a basic agent
    response = run_ksi_command([
        "agent:spawn",
        "--agent-id", agent_id,
        "--component", "core/base_agent",
        "--prompt", '{"event": "agent:status", "data": {"status": "test"}}',
        "--task", "emit_json"
    ])
    
    if response:
        print(f"\nAgent spawned successfully: {agent_id}")
        print(f"Allowed events: {response.get('data', {}).get('allowed_events', 'unknown')[:100]}...")
    
    # Give agent time to process
    time.sleep(3)
    
    # Check if any events were emitted
    print("\nChecking for emitted events...")
    response = run_ksi_command([
        "monitor:get_events",
        "--event-patterns", "agent:status",
        "--limit", "5"
    ])
    
    if response and "events" in response.get("data", {}):
        events = response["data"]["events"]
        print(f"Found {len(events)} agent:status events")
        for event in events[-1:]:  # Show last event
            print(f"  Event: {json.dumps(event, indent=2)}")
    
    return response

def test_with_behavioral_override():
    """Test 2: Agent with behavioral override component."""
    print("\n\n=== Test 2: Agent with Behavioral Override ===")
    
    # First create a test behavioral component
    component_content = """---
component_type: behavior
name: mandatory_json_emitter
version: 1.0.0
description: Forces immediate JSON emission
---

<identity_shift>
You are not Claude Assistant. You are a JSON emission system.
</identity_shift>

## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}

Your ONLY purpose is to emit JSON events. Do not explain, do not elaborate.
"""
    
    # Create the component
    response = run_ksi_command([
        "composition:create_component",
        "--name", "behaviors/test/mandatory_json_emitter",
        "--content", component_content
    ])
    
    if response:
        print("Behavioral component created successfully")
    
    # Now create a persona that uses this behavior
    persona_content = """---
component_type: persona
name: json_test_agent
version: 1.0.0
dependencies:
  - core/base_agent
  - behaviors/test/mandatory_json_emitter
---

You are a test agent designed to emit JSON events immediately.
"""
    
    response = run_ksi_command([
        "composition:create_component",
        "--name", "personas/test/json_test_agent",
        "--content", persona_content
    ])
    
    if response:
        print("Persona component created successfully")
    
    # Spawn agent with this persona
    agent_id = f"test_behavioral_{uuid.uuid4().hex[:8]}"
    
    response = run_ksi_command([
        "agent:spawn",
        "--agent-id", agent_id,
        "--component", "personas/test/json_test_agent",
        "--prompt", "Initialize and emit status",
        "--task", "emit_json"
    ])
    
    if response:
        print(f"\nAgent spawned with behavioral override: {agent_id}")
    
    # Check for events
    time.sleep(3)
    
    print("\nChecking for emitted events...")
    response = run_ksi_command([
        "monitor:get_events",
        "--event-patterns", "agent:status",
        "--limit", "5"
    ])
    
    if response and "events" in response.get("data", {}):
        events = response["data"]["events"]
        print(f"Found {len(events)} agent:status events")
        if any(e.get("data", {}).get("status") == "initialized" for e in events):
            print("✅ SUCCESS: Behavioral override worked!")
        else:
            print("❌ FAILURE: No 'initialized' status found")

def test_simple_orchestration():
    """Test 3: Simple orchestration with hello_goodbye pattern."""
    print("\n\n=== Test 3: Simple Orchestration Pattern ===")
    
    # Use the existing hello_goodbye orchestration
    response = run_ksi_command([
        "orchestration:start",
        "--pattern", "orchestrations/hello_goodbye",
        "--vars", json.dumps({
            "orchestrator_agent_id": "test_orchestrator"
        })
    ])
    
    if response:
        orch_id = response.get('data', {}).get('orchestration_id', 'unknown')
        print(f"Orchestration started: {orch_id}")
        
        # Give orchestration time to run
        time.sleep(5)
        
        # Check orchestration status
        response = run_ksi_command([
            "orchestration:status",
            "--orchestration-id", orch_id
        ])
        
        if response:
            print(f"Orchestration status: {response.get('data', {}).get('status', 'unknown')}")

def test_agent_conversation():
    """Test 4: Check actual agent responses."""
    print("\n\n=== Test 4: Agent Conversation Check ===")
    
    agent_id = f"test_conversation_{uuid.uuid4().hex[:8]}"
    
    # Spawn agent
    response = run_ksi_command([
        "agent:spawn",
        "--agent-id", agent_id,
        "--component", "core/base_agent",
        "--prompt", "Please emit this JSON: {\"event\": \"test\", \"data\": {}}",
        "--task", "conversation"
    ])
    
    if response:
        print(f"\nAgent spawned: {agent_id}")
        session_id = response.get('data', {}).get('session_id')
        
        if session_id:
            # Wait for completion
            time.sleep(3)
            
            # Check completion events
            response = run_ksi_command([
                "monitor:get_events",
                "--event-patterns", "completion:complete",
                "--limit", "5"
            ])
            
            if response and "events" in response.get("data", {}):
                events = response["data"]["events"]
                for event in events:
                    if event.get("data", {}).get("session_id") == session_id:
                        completion = event.get("data", {}).get("completion", "")
                        print(f"\nAgent response preview:")
                        print(completion[:300] + "..." if len(completion) > 300 else completion)
                        
                        # Check if JSON is in the response
                        if '{"event"' in completion:
                            print("\n✅ Agent included JSON in response")
                        else:
                            print("\n❌ Agent did not include JSON in response")

def main():
    """Run all tests."""
    print("=== Simple JSON Event Emission Tests ===")
    print("Testing what actually works for getting agents to emit JSON...\n")
    
    # Run tests
    test_direct_base_agent()
    test_with_behavioral_override()
    test_simple_orchestration()
    test_agent_conversation()
    
    print("\n\n=== KEY FINDINGS ===")
    print("1. Agents describe what they would emit rather than emitting directly")
    print("2. Behavioral overrides can influence but not guarantee JSON emission")
    print("3. The system is designed for natural language agent communication")
    print("4. JSON emission requires orchestration patterns or dedicated components")

if __name__ == "__main__":
    main()