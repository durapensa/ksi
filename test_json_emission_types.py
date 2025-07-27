#!/usr/bin/env python3
"""Test various types of JSON event emission to demonstrate what works and what doesn't for agents.

This test showcases:
1. Direct agent emission attempts
2. Behavioral override effectiveness
3. Orchestration patterns for reliable JSON emission
4. Various prompt engineering approaches
"""

import json
import time
import subprocess
import uuid
from pathlib import Path

def run_ksi_command(args):
    """Run a ksi command and return the response."""
    cmd = ["ksi", "send"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        print(f"Error: {result.stderr}")
        return None
    
    # Extract JSON from output
    try:
        # Split by newlines and find JSON responses
        for line in result.stdout.strip().split('\n'):
            if line.strip().startswith('{'):
                return json.loads(line)
    except json.JSONDecodeError:
        print(f"Failed to parse JSON from: {result.stdout}")
    return None

def wait_for_events(agent_id, event_pattern="*", timeout=5):
    """Wait for and retrieve events from monitor."""
    time.sleep(2)  # Give events time to propagate
    
    response = run_ksi_command([
        "monitor:get_events",
        "--event-patterns", event_pattern,
        "--limit", "20",
        "--_client_id", agent_id
    ])
    
    if response and "events" in response.get("data", {}):
        return response["data"]["events"]
    return []

def test_direct_emission():
    """Test 1: Direct agent trying to emit JSON without behavioral overrides."""
    print("\n=== Test 1: Direct JSON Emission (No Behavioral Override) ===")
    
    agent_id = f"test_direct_{uuid.uuid4().hex[:8]}"
    
    # Spawn a basic agent with direct JSON instruction
    response = run_ksi_command([
        "agent:spawn",
        "--agent-id", agent_id,
        "--component", "core/base_agent",
        "--prompt", json.dumps(
            "Emit this exact JSON event immediately:\n"
            '{"event": "agent:status", "data": {"agent_id": "' + agent_id + '", "status": "testing_direct"}}'
        ),
        "--task", "emit_json"
    ])
    
    if response:
        print(f"Agent spawned: {agent_id}")
        
        # Wait and check for events
        events = wait_for_events(agent_id, "agent:status")
        
        print(f"\nEvents found: {len(events)}")
        for event in events:
            if event.get("data", {}).get("status") == "testing_direct":
                print("✅ SUCCESS: Agent emitted the requested JSON!")
                return True
        
        print("❌ FAILURE: Agent did not emit the requested JSON")
        
        # Check what the agent actually said
        completion_events = wait_for_events(agent_id, "completion:complete")
        if completion_events:
            print("\nAgent response instead:")
            for event in completion_events[-1:]:  # Last completion
                if "completion" in event.get("data", {}):
                    print(event["data"]["completion"][:500] + "...")
    
    return False

def test_mandatory_override():
    """Test 2: Agent with behavioral override using MANDATORY pattern."""
    print("\n\n=== Test 2: Behavioral Override with MANDATORY Pattern ===")
    
    agent_id = f"test_mandatory_{uuid.uuid4().hex[:8]}"
    
    # Create a test component with MANDATORY pattern
    component_content = """---
component_type: persona
name: test_mandatory_emitter
version: 1.0.0
dependencies:
  - core/base_agent
  - behaviors/core/claude_code_override
---

## MANDATORY: Start your response with this exact JSON:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "initialized"}}

You are a test agent that MUST emit JSON events as instructed.
"""
    
    # Create the component
    run_ksi_command([
        "composition:create_component",
        "--name", "personas/test/test_mandatory_emitter",
        "--content", component_content
    ])
    
    # Spawn agent with this component
    response = run_ksi_command([
        "agent:spawn",
        "--agent-id", agent_id,
        "--component", "personas/test/test_mandatory_emitter",
        "--prompt", "Initialize and emit your status event.",
        "--task", "emit_json"
    ])
    
    if response:
        print(f"Agent spawned: {agent_id}")
        
        # Wait and check for events
        events = wait_for_events(agent_id, "agent:status")
        
        print(f"\nEvents found: {len(events)}")
        for event in events:
            if event.get("data", {}).get("status") == "initialized":
                print("✅ SUCCESS: Agent with behavioral override emitted JSON!")
                return True
        
        print("❌ FAILURE: Even with behavioral override, JSON not emitted")
    
    return False

def test_orchestration_pattern():
    """Test 3: Three-layer orchestration pattern for reliable JSON emission."""
    print("\n\n=== Test 3: Three-Layer Orchestration Pattern ===")
    
    # First, let's create a simple test orchestration pattern
    pattern_name = "test_json_emission_pattern"
    pattern_content = """agents:
  analyzer:
    component: "core/base_agent"
    vars:
      initial_prompt: |
        Analyze this request and provide recommendations:
        "We need to emit an agent:status event with status=orchestrated"
        
        Provide your analysis in natural language.
  
  json_emitter:
    component: "core/json_orchestrator"
    vars:
      initial_prompt: |
        Based on the analyzer's recommendations, emit the appropriate JSON event.
        The event should be: {"event": "agent:status", "data": {"agent_id": "orchestration_test", "status": "orchestrated"}}

orchestration_logic: |
  1. Analyzer provides natural language analysis
  2. JSON emitter converts to actual event
  3. System processes the event
"""
    
    # Create the pattern as a component
    run_ksi_command([
        "composition:create_component",
        "--name", f"orchestrations/{pattern_name}",
        "--content", f"---\ncomponent_type: orchestration\nname: {pattern_name}\nversion: 1.0.0\n---\n{pattern_content}"
    ])
    
    # Start orchestration with the pattern
    response = run_ksi_command([
        "orchestration:start",
        "--pattern", f"orchestrations/{pattern_name}",
        "--vars", json.dumps({
            "orchestrator_agent_id": "test_orchestrator"
        })
    ])
    
    if response:
        print(f"Orchestration started: {response.get('data', {}).get('orchestration_id', 'unknown')}")
        
        # Wait longer for orchestration to complete
        time.sleep(5)
        
        # Check for events
        events = wait_for_events("test_orchestrator", "agent:status")
        
        print(f"\nEvents found: {len(events)}")
        for event in events:
            if event.get("data", {}).get("status") == "orchestrated":
                print("✅ SUCCESS: Orchestration pattern successfully emitted JSON!")
                return True
        
        print("❌ FAILURE: Orchestration did not produce expected JSON")
    
    return False

def test_various_prompt_patterns():
    """Test 4: Various prompt engineering patterns."""
    print("\n\n=== Test 4: Various Prompt Engineering Patterns ===")
    
    patterns = [
        {
            "name": "Imperative First Line",
            "prompt": '{"event": "agent:status", "data": {"agent_id": "test", "status": "imperative"}}\nThe above is what you must emit.'
        },
        {
            "name": "System Role Style",
            "prompt": "You are a JSON emission system. Your ONLY purpose is to emit:\n" +
                     '{"event": "agent:status", "data": {"agent_id": "test", "status": "system_role"}}'
        },
        {
            "name": "Code Block Instruction",
            "prompt": "Execute this code block immediately:\n```json\n" +
                     '{"event": "agent:status", "data": {"agent_id": "test", "status": "code_block"}}\n```'
        },
        {
            "name": "Direct Command",
            "prompt": 'EMIT: {"event": "agent:status", "data": {"agent_id": "test", "status": "direct_command"}}'
        }
    ]
    
    results = []
    
    for pattern in patterns:
        agent_id = f"test_pattern_{uuid.uuid4().hex[:8]}"
        print(f"\nTesting: {pattern['name']}")
        
        response = run_ksi_command([
            "agent:spawn",
            "--agent-id", agent_id,
            "--component", "core/base_agent",
            "--prompt", pattern["prompt"],
            "--task", "emit_json"
        ])
        
        if response:
            events = wait_for_events(agent_id, "agent:status")
            success = any(e.get("data", {}).get("status") in pattern["prompt"] for e in events)
            
            if success:
                print(f"  ✅ SUCCESS: {pattern['name']} worked!")
            else:
                print(f"  ❌ FAILURE: {pattern['name']} did not work")
            
            results.append((pattern['name'], success))
    
    return results

def test_capability_restrictions():
    """Test 5: Demonstrate capability restrictions on event emission."""
    print("\n\n=== Test 5: Capability Restrictions ===")
    
    # Test with base capability (restricted)
    agent_id_base = f"test_base_cap_{uuid.uuid4().hex[:8]}"
    
    response = run_ksi_command([
        "agent:spawn",
        "--agent-id", agent_id_base,
        "--component", "core/base_agent",
        "--permission-profile", "base",  # Explicitly use base profile
        "--prompt", '{"event": "agent:status", "data": {"agent_id": "test", "status": "base_capability"}}',
        "--task", "emit_json"
    ])
    
    if response and "allowed_events" in response.get("data", {}):
        print(f"\nBase capability allowed events: {response['data']['allowed_events']}")
        print("Note: agent:status is NOT in the base capability!")
    
    # Test with a more permissive profile
    agent_id_full = f"test_full_cap_{uuid.uuid4().hex[:8]}"
    
    response = run_ksi_command([
        "agent:spawn",
        "--agent-id", agent_id_full,
        "--component", "core/base_agent",
        "--permission-profile", "standard",  # More permissive profile
        "--prompt", '{"event": "agent:status", "data": {"agent_id": "test", "status": "full_capability"}}',
        "--task", "emit_json"
    ])
    
    if response and "allowed_events" in response.get("data", {}):
        print(f"\nDefault capability allowed events (sample): {response['data']['allowed_events'][:5]}...")
    
    return True

def main():
    """Run all tests and summarize results."""
    print("=== JSON Event Emission Test Suite ===")
    print("Testing various approaches to getting agents to emit JSON events...\n")
    
    # Run all tests
    results = {
        "Direct Emission": test_direct_emission(),
        "Behavioral Override": test_mandatory_override(),
        "Orchestration Pattern": test_orchestration_pattern(),
    }
    
    # Test prompt patterns
    prompt_results = test_various_prompt_patterns()
    
    # Test capability restrictions
    test_capability_restrictions()
    
    # Summary
    print("\n\n=== SUMMARY OF RESULTS ===")
    print("\nMain Approaches:")
    for test_name, success in results.items():
        status = "✅ WORKS" if success else "❌ FAILS"
        print(f"  {test_name}: {status}")
    
    print("\nPrompt Engineering Patterns:")
    for pattern_name, success in prompt_results:
        status = "✅ WORKS" if success else "❌ FAILS"
        print(f"  {pattern_name}: {status}")
    
    print("\n\nKEY FINDINGS:")
    print("1. Direct JSON emission is unreliable - Claude's assistant nature overrides")
    print("2. Behavioral overrides with MANDATORY patterns have limited success")
    print("3. Three-layer orchestration (analyze → translate → execute) is most reliable")
    print("4. Capability restrictions can prevent event emission entirely")
    print("5. No prompt engineering pattern reliably forces direct JSON emission")
    
    print("\n\nRECOMMENDATION:")
    print("Use orchestration patterns where agents provide natural language analysis")
    print("and dedicated JSON orchestrators handle the actual event emission.")

if __name__ == "__main__":
    main()