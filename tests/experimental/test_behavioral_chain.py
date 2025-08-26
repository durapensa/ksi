#!/usr/bin/env python3
"""
Test the actual behavioral component dependency chain:
1. behaviors/core/claude_code_override (no dependencies)
2. agents/tool_use_test_agent (depends on #1 + ksi_events_as_tool_calls)
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
        response = json.loads(result.stdout)
        # Print the full response for debugging
        print(f"Response: {json.dumps(response, indent=2)}")
        return response
    except json.JSONDecodeError:
        print(f"Failed to parse JSON from: {result.stdout}")
        return None


def test_behavioral_dependency_chain():
    """Test the dependency chain from base behavior to composed agent."""
    print("\n" + "="*80)
    print("BEHAVIORAL COMPONENT DEPENDENCY CHAIN TEST")
    print("="*80)
    
    # Test 1: Base agent without any behaviors
    print("\n1️⃣ TEST: Base agent (no behavioral components)")
    print("-" * 40)
    
    agent_id = f"base_test_{int(time.time())}"
    response = run_ksi_command([
        "agent:spawn",
        "--profile", "base",
        "--agent-id", agent_id,
        "--prompt", "Calculate 10 + 15"
    ])
    
    if response and response.get("status") == "success":
        print(f"✅ Base agent spawned: {agent_id}")
        time.sleep(2)
        run_ksi_command(["agent:terminate", "--agent-id", agent_id])
    
    # Test 2: Agent with just claude_code_override behavior
    print("\n2️⃣ TEST: Agent with only claude_code_override behavior")
    print("-" * 40)
    
    # Create a minimal agent with just the override
    agent_id = f"override_test_{int(time.time())}"
    component_name = f"test_agents/minimal_override_{int(time.time())}"
    
    component_content = '''---
component_type: persona
name: minimal_override_test
version: 1.0.0
dependencies:
  - behaviors/core/claude_code_override
---
# Minimal Override Test

You are a test agent that calculates directly.'''
    
    response = run_ksi_command([
        "composition:create_component",
        "--name", component_name,
        "--content", component_content
    ])
    
    if response and response.get("status") == "success":
        print(f"✅ Created minimal override component")
        
        response = run_ksi_command([
            "agent:spawn_from_component",
            "--component", component_name,
            "--agent-id", agent_id,
            "--prompt", "Calculate 10 + 15"
        ])
        
        if response and response.get("status") == "success":
            print(f"✅ Override agent spawned: {agent_id}")
            time.sleep(2)
            run_ksi_command(["agent:terminate", "--agent-id", agent_id])
    
    # Test 3: The full tool_use_test_agent with both behaviors
    print("\n3️⃣ TEST: agents/tool_use_test_agent (both behaviors)")
    print("-" * 40)
    
    agent_id = f"tool_use_test_{int(time.time())}"
    response = run_ksi_command([
        "agent:spawn_from_component",
        "--component", "agents/tool_use_test_agent",
        "--agent-id", agent_id,
        "--prompt", "Initialize yourself"
    ])
    
    if response and response.get("status") == "success":
        print(f"✅ Tool use test agent spawned: {agent_id}")
        
        # Wait for agent to process and emit events
        print("\n⏳ Waiting for agent to emit events...")
        time.sleep(5)
        
        # Check for agent:status events
        print("\n📊 Checking for agent:status events...")
        events = run_ksi_command([
            "monitor:get_events",
            "--event-patterns", "agent:status",
            "--limit", "20"
        ])
        
        if events and events.get("status") == "success":
            event_list = events.get("data", {}).get("events", [])
            agent_events = [e for e in event_list if e.get("data", {}).get("agent_id") == agent_id]
            
            print(f"\n✅ Found {len(agent_events)} agent:status events from our agent!")
            for evt in agent_events:
                status = evt.get("data", {}).get("status", "N/A")
                message = evt.get("data", {}).get("message", "N/A")
                print(f"   - Status: {status}, Message: {message}")
        
        # Cleanup
        run_ksi_command(["agent:terminate", "--agent-id", agent_id])
    
    print("\n" + "="*80)
    print("DEPENDENCY CHAIN SUMMARY")
    print("="*80)
    print("\n📋 Component Dependency Structure:")
    print("   behaviors/core/claude_code_override (no deps)")
    print("   └─> agents/tool_use_test_agent (depends on override + tool use)")
    print("\n✅ Key Finding:")
    print("   evaluation:run would certify tool_use_test_agent works WITH:")
    print("   - behaviors/core/claude_code_override")
    print("   - behaviors/communication/ksi_events_as_tool_calls")
    print("   Not tested separately, but as a complete combination!")


if __name__ == "__main__":
    test_behavioral_dependency_chain()