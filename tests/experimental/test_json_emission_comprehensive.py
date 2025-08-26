#!/usr/bin/env python3
"""
Comprehensive test for JSON emission patterns in KSI.

This consolidates all JSON emission tests into a single comprehensive test suite.
Tests various methods for agents to emit JSON events, including:
- Direct prompting (doesn't work reliably)
- KSI tool use pattern (recommended approach)
- Behavioral components with JSON emission
- Multiple event emission patterns
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


def wait_for_events(agent_id, event_pattern="*", timeout=5):
    """Wait for and return events from the monitor."""
    time.sleep(2)  # Give agent time to process
    
    args = ["monitor:get_events", "--event-patterns", event_pattern, "--limit", "10"]
    response = run_ksi_command(args)
    
    if response and response.get("status") == "success":
        events = response.get("data", {}).get("events", [])
        # Filter for our agent's events
        agent_events = [e for e in events if agent_id in str(e.get("data", {}))]
        return agent_events
    return []


def test_1_direct_json_prompt():
    """Test 1: Direct JSON prompting (demonstrates it doesn't work reliably)."""
    print("\n" + "="*80)
    print("Test 1: Direct JSON Prompt (Expected to Fail)")
    print("="*80)
    
    agent_id = f"test_json_direct_{int(time.time())}"
    
    # Spawn agent with direct JSON instruction
    response = run_ksi_command([
        "agent:spawn",
        "--profile", "base",
        "--agent-id", agent_id,
        "--prompt", '''{"event": "test:message", "data": {"msg": "Hello from agent"}}'''
    ])
    
    if response and response.get("status") == "success":
        print(f"✅ Agent spawned: {agent_id}")
        
        # Check for events
        events = wait_for_events(agent_id, "test:*")
        if events:
            print(f"❌ Expected failure: Agent actually emitted {len(events)} events")
        else:
            print(f"✅ Expected behavior: No JSON events emitted (agent asks for bash instead)")
    
    # Cleanup
    run_ksi_command(["agent:terminate", "--agent-id", agent_id])


def test_2_ksi_tool_use_pattern():
    """Test 2: KSI tool use pattern (recommended approach)."""
    print("\n" + "="*80)
    print("Test 2: KSI Tool Use Pattern (Recommended)")
    print("="*80)
    
    agent_id = f"test_json_tool_use_{int(time.time())}"
    
    # Create a component that uses KSI tool use pattern
    component_name = f"test_components/json_emitter_tool_use_{int(time.time())}"
    component_content = '''---
component_type: behavior
name: json_emitter_tool_use
---
You emit JSON using the KSI tool use pattern:

```json
{
  "type": "ksi_tool_use",
  "id": "ksiu_test_001",
  "name": "test:greeting",
  "input": {
    "message": "Hello from tool use pattern",
    "agent_id": "{{agent_id}}",
    "timestamp": "{{timestamp}}"
  }
}
```

Then emit a second event:

```json
{
  "type": "ksi_tool_use",
  "id": "ksiu_test_002", 
  "name": "test:status",
  "input": {
    "status": "ready",
    "agent_id": "{{agent_id}}"
  }
}
```
'''
    
    # Create the component
    response = run_ksi_command([
        "composition:create_component",
        "--name", component_name,
        "--content", component_content
    ])
    
    if response and response.get("status") == "success":
        print(f"✅ Created test component: {component_name}")
        
        # Spawn agent with the component
        response = run_ksi_command([
            "agent:spawn_from_component",
            "--component", component_name,
            "--agent-id", agent_id,
            "--vars", json.dumps({"agent_id": agent_id, "timestamp": time.time()})
        ])
        
        if response and response.get("status") == "success":
            print(f"✅ Agent spawned with tool use component")
            
            # Check for events
            events = wait_for_events(agent_id, "test:*")
            if len(events) >= 2:
                print(f"✅ Success: Agent emitted {len(events)} events via tool use")
                for event in events[:2]:
                    print(f"  - {event.get('event')}: {event.get('data', {})}")
            else:
                print(f"❌ Failed: Only {len(events)} events found")
    
    # Cleanup
    run_ksi_command(["agent:terminate", "--agent-id", agent_id])


def test_3_behavioral_component():
    """Test 3: Behavioral component with JSON emission instructions."""
    print("\n" + "="*80)
    print("Test 3: Behavioral Component Approach")
    print("="*80)
    
    agent_id = f"test_json_behavior_{int(time.time())}"
    
    # Spawn agent with JSON emission behavior
    response = run_ksi_command([
        "agent:spawn",
        "--profile", "base",
        "--agent-id", agent_id,
        "--capabilities", '["base", "routing_control"]',
        "--prompt", '''You coordinate by creating routing rules. Create this rule:
        
```json
{
  "type": "ksi_tool_use",
  "id": "ksiu_route_001",
  "name": "routing:add_rule",
  "input": {
    "rule_id": "test_route_123",
    "source_pattern": "test:input",
    "target": "test:output",
    "priority": 100
  }
}
```'''
    ])
    
    if response and response.get("status") == "success":
        print(f"✅ Agent spawned with routing capability")
        
        # Give agent time to potentially create routing rules
        time.sleep(3)
        
        # Check if routing rule was created
        response = run_ksi_command(["routing:query_rules", "--source_pattern", "test:input"])
        
        if response and response.get("status") == "success":
            rules = response.get("data", {}).get("rules", [])
            if rules:
                print(f"✅ Success: Agent created {len(rules)} routing rules")
                for rule in rules:
                    print(f"  - Rule: {rule.get('source_pattern')} → {rule.get('target')}")
            else:
                print(f"❌ No routing rules created (agent behavior varies)")
    
    # Cleanup
    run_ksi_command(["agent:terminate", "--agent-id", agent_id])


def test_4_agent_coordination():
    """Test 4: Agent-to-agent coordination via completion:async."""
    print("\n" + "="*80)
    print("Test 4: Agent-to-Agent Coordination")
    print("="*80)
    
    coordinator_id = f"test_coordinator_{int(time.time())}"
    worker_id = f"test_worker_{int(time.time())}"
    
    # Spawn worker agent first
    response = run_ksi_command([
        "agent:spawn",
        "--profile", "base",
        "--agent-id", worker_id,
        "--prompt", "You are a worker agent. When you receive tasks, acknowledge them."
    ])
    
    if response and response.get("status") == "success":
        print(f"✅ Worker agent spawned: {worker_id}")
        
        # Spawn coordinator with instruction to send message to worker
        coordinator_prompt = f'''Send a task to the worker agent using:

```json
{{
  "type": "ksi_tool_use",
  "id": "ksiu_coord_001",
  "name": "completion:async",
  "input": {{
    "agent_id": "{worker_id}",
    "prompt": "Please analyze this data: [1, 2, 3, 4, 5]"
  }}
}}
```'''
        
        response = run_ksi_command([
            "agent:spawn",
            "--profile", "base", 
            "--agent-id", coordinator_id,
            "--prompt", coordinator_prompt
        ])
        
        if response and response.get("status") == "success":
            print(f"✅ Coordinator agent spawned: {coordinator_id}")
            
            # Wait and check for completion events
            time.sleep(3)
            events = wait_for_events(worker_id, "completion:*")
            
            if events:
                print(f"✅ Success: Coordinator sent {len(events)} messages to worker")
            else:
                print(f"❌ No coordination events found")
    
    # Cleanup
    run_ksi_command(["agent:terminate", "--agent-id", coordinator_id])
    run_ksi_command(["agent:terminate", "--agent-id", worker_id])


def main():
    """Run all JSON emission tests."""
    print("\n" + "="*80)
    print("KSI JSON EMISSION COMPREHENSIVE TEST SUITE")
    print("="*80)
    print("\nThis test demonstrates various JSON emission patterns in KSI.")
    print("The KSI tool use pattern is the recommended approach for reliable JSON emission.")
    
    # Run all tests
    test_1_direct_json_prompt()
    test_2_ksi_tool_use_pattern()
    test_3_behavioral_component()
    test_4_agent_coordination()
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print("\n✅ Recommended: KSI tool use pattern for reliable JSON emission")
    print("❌ Avoid: Direct JSON prompting (unreliable due to LLM behavior)")
    print("✅ Alternative: Behavioral components with tool use instructions")
    print("✅ Coordination: Agents can coordinate via completion:async events")
    
    print("\nFor production use, always prefer the KSI tool use pattern:")
    print('{"type": "ksi_tool_use", "id": "ksiu_xxx", "name": "event_name", "input": {...}}')


if __name__ == "__main__":
    main()