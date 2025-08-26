#!/usr/bin/env python3
"""
Direct test of behavioral components to understand their actual effects.
"""

import json
import subprocess
import time
import sys


def run_ksi_command(args):
    """Execute a KSI command and return parsed JSON response."""
    cmd = ["./ksi", "send"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        print(f"Error: {result.stderr}")
        return None
    
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Failed to parse JSON from: {result.stdout}")
        return None


def test_1_base_agent_no_override():
    """Test base agent without any behavioral override."""
    print("\n" + "="*80)
    print("TEST 1: Base Agent (No Behavioral Components)")
    print("="*80)
    
    agent_id = f"test_base_{int(time.time())}"
    
    response = run_ksi_command([
        "agent:spawn",
        "--profile", "base",
        "--agent-id", agent_id,
        "--prompt", "What is 10 + 15?"
    ])
    
    if response and response.get("status") == "success":
        print(f"✅ Spawned base agent: {agent_id}")
        print("   Expected: Typical Claude Assistant response with explanation")
        print("   (Check completion logs to see actual response)")
    
    # Cleanup
    time.sleep(2)
    run_ksi_command(["agent:terminate", "--agent-id", agent_id])


def test_2_agent_with_override():
    """Test agent with claude_code_override behavior."""
    print("\n" + "="*80)
    print("TEST 2: Agent with claude_code_override")
    print("="*80)
    
    agent_id = f"test_override_{int(time.time())}"
    
    # First create a test component that uses the override
    component_name = f"test_components/with_override_{int(time.time())}"
    component_content = '''---
component_type: persona
name: test_with_override
version: 1.0.0
dependencies:
  - behaviors/core/claude_code_override
---
# Test Agent with Override

You calculate and report results.'''
    
    response = run_ksi_command([
        "composition:create_component",
        "--name", component_name,
        "--content", component_content
    ])
    
    if response and response.get("status") == "success":
        print(f"✅ Created test component with override dependency")
        
        # Spawn agent from this component
        response = run_ksi_command([
            "agent:spawn_from_component",
            "--component", component_name,
            "--agent-id", agent_id,
            "--prompt", "What is 10 + 15?"
        ])
        
        if response and response.get("status") == "success":
            print(f"✅ Spawned agent with override behavior")
            print("   Expected: Direct answer '25' without preamble")
            print("   (Check completion logs to see actual response)")
    
    # Cleanup
    time.sleep(2)
    run_ksi_command(["agent:terminate", "--agent-id", agent_id])


def test_3_agent_with_tool_use():
    """Test agent with tool use emission behavior."""
    print("\n" + "="*80)
    print("TEST 3: Agent with ksi_events_as_tool_calls behavior")
    print("="*80)
    
    agent_id = f"test_tool_use_{int(time.time())}"
    
    # Create component with tool use behavior
    component_name = f"test_components/with_tool_use_{int(time.time())}"
    component_content = '''---
component_type: persona
name: test_with_tool_use
version: 1.0.0
dependencies:
  - behaviors/communication/ksi_events_as_tool_calls
---
# Test Agent with Tool Use

You emit events using the KSI tool use pattern.'''
    
    response = run_ksi_command([
        "composition:create_component",
        "--name", component_name,
        "--content", component_content
    ])
    
    if response and response.get("status") == "success":
        print(f"✅ Created test component with tool use dependency")
        
        # Spawn agent and ask it to emit an event
        response = run_ksi_command([
            "agent:spawn_from_component",
            "--component", component_name,
            "--agent-id", agent_id,
            "--prompt", '''Emit a test event using:
{
  "type": "ksi_tool_use",
  "id": "ksiu_test_001",
  "name": "test:hello",
  "input": {"message": "Hello from tool use pattern"}
}'''
        ])
        
        if response and response.get("status") == "success":
            print(f"✅ Spawned agent with tool use behavior")
            print("   Expected: Agent emits the JSON event")
            
            # Wait and check for event
            time.sleep(3)
            events = run_ksi_command([
                "monitor:get_events",
                "--event-patterns", "test:hello",
                "--limit", "5"
            ])
            
            if events and events.get("status") == "success":
                event_list = events.get("data", {}).get("events", [])
                if event_list:
                    print(f"✅ SUCCESS: Found {len(event_list)} test:hello events!")
                    for evt in event_list[:2]:
                        print(f"   Event: {evt.get('event')} - {evt.get('data', {}).get('message', 'N/A')}")
                else:
                    print(f"❌ No test:hello events found")
    
    # Cleanup
    run_ksi_command(["agent:terminate", "--agent-id", agent_id])


def test_4_combined_behaviors():
    """Test agent with both override and tool use behaviors."""
    print("\n" + "="*80)
    print("TEST 4: Agent with Combined Behaviors (like tool_use_test_agent)")
    print("="*80)
    
    agent_id = f"test_combined_{int(time.time())}"
    
    # Create component with both behaviors - matching tool_use_test_agent structure
    component_name = f"test_components/combined_behaviors_{int(time.time())}"
    component_content = '''---
component_type: persona
name: test_combined
version: 1.0.0
dependencies:
  - behaviors/core/claude_code_override
  - behaviors/communication/ksi_events_as_tool_calls
---
# Test Agent with Combined Behaviors

You execute tasks directly AND emit events using KSI tool use pattern.'''
    
    response = run_ksi_command([
        "composition:create_component",
        "--name", component_name,
        "--content", component_content
    ])
    
    if response and response.get("status") == "success":
        print(f"✅ Created test component with combined behaviors")
        
        # Spawn agent with a task requiring both behaviors
        response = run_ksi_command([
            "agent:spawn_from_component",
            "--component", component_name,
            "--agent-id", agent_id,
            "--prompt", '''Calculate 20 + 30, then emit the result as an event:
{
  "type": "ksi_tool_use",
  "id": "ksiu_calc_001",
  "name": "test:calculation",
  "input": {"result": 50}
}'''
        ])
        
        if response and response.get("status") == "success":
            print(f"✅ Spawned agent with combined behaviors")
            print("   Expected: Direct calculation AND event emission")
            
            # Check for event
            time.sleep(3)
            events = run_ksi_command([
                "monitor:get_events",
                "--event-patterns", "test:calculation",
                "--limit", "5"
            ])
            
            if events and events.get("status") == "success":
                event_list = events.get("data", {}).get("events", [])
                if event_list:
                    print(f"✅ SUCCESS: Found calculation event!")
                    result = event_list[0].get("data", {}).get("result", "N/A")
                    print(f"   Result from event: {result}")
    
    # Cleanup
    run_ksi_command(["agent:terminate", "--agent-id", agent_id])


def test_5_existing_tool_use_agent():
    """Test the actual tool_use_test_agent.md from the system."""
    print("\n" + "="*80)
    print("TEST 5: Existing agents/tool_use_test_agent Component")
    print("="*80)
    
    agent_id = f"test_existing_{int(time.time())}"
    
    print("📋 Using agents/tool_use_test_agent which declares dependencies:")
    print("   - behaviors/core/claude_code_override")
    print("   - behaviors/communication/ksi_events_as_tool_calls")
    
    response = run_ksi_command([
        "agent:spawn_from_component",
        "--component", "agents/tool_use_test_agent",
        "--agent-id", agent_id,
        "--prompt", "Initialize and demonstrate the tool use pattern"
    ])
    
    if response and response.get("status") == "success":
        print(f"✅ Spawned existing tool_use_test_agent")
        print("   Expected: Immediate initialization event, then demonstrations")
        
        # Give agent time to emit events
        time.sleep(5)
        
        # Check for initialization event
        events = run_ksi_command([
            "monitor:get_events",
            "--event-patterns", "agent:status",
            "--limit", "10"
        ])
        
        if events and events.get("status") == "success":
            event_list = events.get("data", {}).get("events", [])
            # Filter for our agent's events
            agent_events = [e for e in event_list if e.get("data", {}).get("agent_id") == agent_id]
            if agent_events:
                print(f"✅ Agent emitted {len(agent_events)} status events!")
                for evt in agent_events[:2]:
                    status = evt.get("data", {}).get("status", "N/A")
                    message = evt.get("data", {}).get("message", "N/A")
                    print(f"   Status: {status} - {message}")
    
    # Cleanup
    run_ksi_command(["agent:terminate", "--agent-id", agent_id])


def main():
    """Run direct behavioral component tests."""
    print("\n" + "="*80)
    print("DIRECT BEHAVIORAL COMPONENT TESTING")
    print("="*80)
    print("\nTesting how behavioral components actually affect agent behavior")
    
    # Run tests
    test_1_base_agent_no_override()
    test_2_agent_with_override()
    test_3_agent_with_tool_use()
    test_4_combined_behaviors()
    test_5_existing_tool_use_agent()
    
    print("\n" + "="*80)
    print("KEY INSIGHTS")
    print("="*80)
    print("\n✅ Dependency Structure:")
    print("1. behaviors/core/claude_code_override - Base override (no dependencies)")
    print("2. behaviors/communication/ksi_events_as_tool_calls - Tool use (no dependencies)")
    print("3. agents/tool_use_test_agent - Combines both behaviors via dependencies")
    print("\n✅ Evaluation Certification:")
    print("- evaluation:run would test tool_use_test_agent WITH its exact dependencies")
    print("- Not tested in isolation, not with random other components")
    print("- Certifies the specific combination works as intended")
    print("\n📝 Next: Build evaluation test suites for these behavioral combinations")


if __name__ == "__main__":
    main()