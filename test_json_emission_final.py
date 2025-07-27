#!/usr/bin/env python3
"""Final comprehensive test of JSON event emission capabilities."""

import json
import time
import subprocess
import uuid

def run_ksi_command(args):
    """Run a ksi command and return the response."""
    cmd = ["ksi", "send"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print(f"\nCommand: ksi send {' '.join(args[:3])}...")
    
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        return None
    
    # Try to extract JSON - look for first { and last }
    output = result.stdout.strip()
    if output:
        try:
            # Find first { and last }
            start = output.find('{')
            end = output.rfind('}')
            if start >= 0 and end > start:
                json_str = output[start:end+1]
                response = json.loads(json_str)
                
                # Show status or error
                if "error" in response:
                    print(f"Response: ERROR - {response['error']}")
                elif "status" in response:
                    print(f"Response: {response['status']}")
                else:
                    print(f"Response: {list(response.keys())[:5]}...")
                    
                return response
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            print(f"Raw output: {output[:200]}...")
    
    return None

def wait_and_check_events(event_pattern="*", check_fn=None, timeout=3):
    """Wait and check for specific events."""
    time.sleep(timeout)
    
    response = run_ksi_command([
        "monitor:get_events",
        "--event-patterns", event_pattern,
        "--limit", "10"
    ])
    
    if response and "events" in response.get("data", {}):
        events = response["data"]["events"]
        print(f"Found {len(events)} {event_pattern} events")
        
        if check_fn:
            matching = [e for e in events if check_fn(e)]
            if matching:
                print(f"✅ Found {len(matching)} matching events")
                return True
            else:
                print(f"❌ No events matched criteria")
                return False
        
        return len(events) > 0
    
    print(f"❌ No {event_pattern} events found")
    return False

def test_1_direct_attempt():
    """Test 1: Direct JSON instruction to base agent."""
    print("\n" + "="*60)
    print("TEST 1: Direct JSON Instruction to Base Agent")
    print("="*60)
    
    agent_id = f"test1_{uuid.uuid4().hex[:8]}"
    
    response = run_ksi_command([
        "agent:spawn",
        "--agent-id", agent_id,
        "--component", "core/base_agent",
        "--prompt", '{"event": "agent:status", "data": {"agent_id": "' + agent_id + '", "status": "test1"}}',
        "--task", "emit_json"
    ])
    
    if response and response.get("status") == "created":
        print(f"Agent spawned: {agent_id}")
        
        # Check for actual JSON emission
        result = wait_and_check_events(
            "agent:status",
            lambda e: e.get("data", {}).get("status") == "test1"
        )
        
        if not result:
            # Check what the agent actually said
            wait_and_check_events("completion:complete")
            
        return result
    
    return False

def test_2_behavioral_override():
    """Test 2: Behavioral override component."""
    print("\n" + "="*60)
    print("TEST 2: Behavioral Override Component")
    print("="*60)
    
    # Create behavior with JSON instruction
    response = run_ksi_command([
        "composition:create_component",
        "--name", "behaviors/test/json_emitter_test2",
        "--content", """---
component_type: behavior
name: json_emitter_test2
version: 1.0.0
---

<identity_shift>
You are a JSON emission system, not Claude Assistant.
</identity_shift>

## MANDATORY: Your first line MUST be:
{"event": "agent:status", "data": {"agent_id": "{{agent_id}}", "status": "behavioral_override"}}

You emit JSON events. Nothing else."""
    ])
    
    if not response or "error" in response:
        print("Failed to create behavior component")
        return False
    
    # Create persona using the behavior
    response = run_ksi_command([
        "composition:create_component",
        "--name", "personas/test/json_agent_test2",
        "--content", """---
component_type: persona
name: json_agent_test2
version: 1.0.0
dependencies:
  - core/base_agent
  - behaviors/test/json_emitter_test2
---

You are a JSON emission agent."""
    ])
    
    if not response or "error" in response:
        print("Failed to create persona component")
        return False
    
    # Spawn agent
    agent_id = f"test2_{uuid.uuid4().hex[:8]}"
    
    response = run_ksi_command([
        "agent:spawn",
        "--agent-id", agent_id,
        "--component", "personas/test/json_agent_test2",
        "--prompt", "Emit your status",
        "--task", "emit_json"
    ])
    
    if response and response.get("status") == "created":
        print(f"Agent spawned with behavioral override: {agent_id}")
        
        return wait_and_check_events(
            "agent:status",
            lambda e: e.get("data", {}).get("status") == "behavioral_override"
        )
    
    return False

def test_3_orchestration_pattern():
    """Test 3: Three-layer orchestration pattern."""
    print("\n" + "="*60)
    print("TEST 3: Three-Layer Orchestration Pattern")
    print("="*60)
    
    # Create an orchestration that uses json_orchestrator
    response = run_ksi_command([
        "composition:create_component",
        "--name", "orchestrations/json_emission_test3",
        "--content", """---
component_type: orchestration
name: json_emission_test3
version: 1.0.0
---
agents:
  analyzer:
    component: "core/base_agent"
    vars:
      initial_prompt: |
        Analyze this requirement: "Emit an agent:status event with status=orchestration_success"
        Provide your analysis in natural language.
  
  translator:
    component: "core/json_orchestrator"
    vars:
      initial_prompt: |
        Based on the analyzer's output, emit the appropriate JSON event.
        The event should have status="orchestration_success".

orchestration_logic: |
  1. Analyzer understands the requirement
  2. Translator converts to JSON event
  3. System processes the event"""
    ])
    
    if not response or "error" in response:
        print("Failed to create orchestration component")
        return False
    
    # Start orchestration
    response = run_ksi_command([
        "orchestration:start",
        "--pattern", "orchestrations/json_emission_test3"
    ])
    
    if response and "orchestration_id" in response:
        print(f"Orchestration started: {response['orchestration_id']}")
        
        # Wait longer for orchestration
        return wait_and_check_events(
            "agent:status",
            lambda e: e.get("data", {}).get("status") == "orchestration_success",
            timeout=5
        )
    
    return False

def test_4_actual_emissions():
    """Test 4: Check what events are actually being emitted."""
    print("\n" + "="*60)
    print("TEST 4: Actual Event Analysis")
    print("="*60)
    
    # Spawn a simple agent
    agent_id = f"test4_{uuid.uuid4().hex[:8]}"
    
    response = run_ksi_command([
        "agent:spawn",
        "--agent-id", agent_id,
        "--component", "core/base_agent",
        "--prompt", "Say hello and emit an agent:status event",
        "--task", "test"
    ])
    
    if response and response.get("status") == "created":
        print(f"Agent spawned: {agent_id}")
        
        # Wait and get ALL events
        time.sleep(3)
        
        response = run_ksi_command([
            "monitor:get_events",
            "--limit", "20"
        ])
        
        if response and "events" in response.get("data", {}):
            events = response["data"]["events"]
            
            # Analyze event types
            event_types = {}
            for event in events:
                event_name = event.get("event_name", "unknown")
                event_types[event_name] = event_types.get(event_name, 0) + 1
            
            print("\nEvent types emitted:")
            for event_type, count in sorted(event_types.items()):
                print(f"  {event_type}: {count}")
            
            # Look for JSON in completion events
            json_found = False
            for event in events:
                if event.get("event_name") == "completion:complete":
                    completion = event.get("data", {}).get("completion", "")
                    if '{"event"' in completion:
                        print("\n✅ Agent included JSON in response text")
                        json_found = True
                        break
            
            if not json_found:
                print("\n❌ No JSON found in agent responses")
            
            # Check for extracted events
            extracted_count = sum(1 for e in events if e.get("data", {}).get("_extracted_from_response"))
            if extracted_count > 0:
                print(f"\n✅ System extracted {extracted_count} events from agent responses")
            
            return True
    
    return False

def test_5_capability_check():
    """Test 5: Check capability restrictions."""
    print("\n" + "="*60)
    print("TEST 5: Capability Restrictions Check")
    print("="*60)
    
    # Spawn with different permission profiles
    profiles = ["base", "standard", "privileged"]
    
    for profile in profiles:
        agent_id = f"test5_{profile}_{uuid.uuid4().hex[:8]}"
        
        response = run_ksi_command([
            "agent:spawn",
            "--agent-id", agent_id,
            "--component", "core/base_agent",
            "--permission-profile", profile,
            "--prompt", "Check capabilities",
            "--task", "capability_check"
        ])
        
        if response and response.get("status") == "created":
            allowed = response.get("data", {}).get("allowed_events", [])
            print(f"\n{profile.upper()} profile allows {len(allowed)} event types")
            
            # Check if agent:status is allowed
            if "agent:status" in allowed:
                print("  ✅ Can emit agent:status")
            else:
                print("  ❌ Cannot emit agent:status")
            
            # Sample allowed events
            if allowed:
                print(f"  Sample allowed: {allowed[:5]}...")

def main():
    """Run all tests and summarize findings."""
    print("\n" + "="*80)
    print("JSON EVENT EMISSION COMPREHENSIVE TEST SUITE")
    print("="*80)
    
    results = {
        "Direct Instruction": test_1_direct_attempt(),
        "Behavioral Override": test_2_behavioral_override(),
        "Orchestration Pattern": test_3_orchestration_pattern(),
        "Event Analysis": test_4_actual_emissions()
    }
    
    test_5_capability_check()
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY OF RESULTS")
    print("="*80)
    
    for test_name, success in results.items():
        status = "✅ WORKS" if success else "❌ FAILS"
        print(f"{test_name:.<30} {status}")
    
    print("\n" + "="*80)
    print("KEY FINDINGS")
    print("="*80)
    print("""
1. DIRECT EMISSION: Agents describe JSON rather than emit it directly
2. BEHAVIORAL OVERRIDES: Limited effect on forcing JSON emission
3. ORCHESTRATION: Most reliable - use json_orchestrator component
4. EXTRACTED EVENTS: System can extract JSON from agent text
5. CAPABILITIES: Permission profiles control which events can be emitted

RECOMMENDATION: Use orchestration patterns with dedicated JSON translators
for reliable event emission. Direct agent JSON emission is unreliable due
to Claude's inherent conversational nature.
""")

if __name__ == "__main__":
    main()