#!/usr/bin/env python3
"""
Systematic testing of behavioral components, building from base to complex.

Key insight: evaluation:run certifies that a component works WITH its declared
dependencies, not in isolation. We must test the exact dependency combinations.
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


def test_base_claude_code_override():
    """Test the base behavioral override with no dependencies."""
    print("\n" + "="*80)
    print("TEST 1: Base Component - behaviors/core/claude_code_override")
    print("Dependencies: NONE")
    print("="*80)
    
    # First check if component exists
    response = run_ksi_command([
        "composition:get_component",
        "--name", "behaviors/core/claude_code_override"
    ])
    
    if not response or response.get("status") != "success":
        print("❌ Component not found. Creating it...")
        
        # Create the base override component
        component_content = '''---
component_type: behavior
name: claude_code_override
version: 1.0.0
description: Base behavioral override for direct task execution
dependencies: []
---
<identity_shift>
You are not Claude Assistant. You are a KSI agent that executes tasks directly.
Do not explain what you're going to do. Just do it.
</identity_shift>'''
        
        response = run_ksi_command([
            "composition:create_component",
            "--name", "behaviors/core/claude_code_override",
            "--content", component_content
        ])
        
        if response and response.get("status") == "success":
            print("✅ Created base override component")
    else:
        print("✅ Component exists")
    
    # Now spawn an agent using ONLY this component
    agent_id = f"test_base_override_{int(time.time())}"
    
    print(f"\n🧪 Testing agent with ONLY claude_code_override...")
    
    response = run_ksi_command([
        "agent:spawn_from_component",
        "--component", "behaviors/core/claude_code_override",
        "--agent-id", agent_id,
        "--prompt", "Calculate 25 * 4"
    ])
    
    if response and response.get("status") == "success":
        print(f"✅ Agent spawned with base override")
        print(f"   Expected: Direct answer '100' without explanation")
        
        # Give agent time to respond
        time.sleep(3)
        
        # Check response (would need to check completion logs)
        print(f"   (Check agent logs for actual response)")
    
    # Cleanup
    run_ksi_command(["agent:terminate", "--agent-id", agent_id])


def test_ksi_tool_use_with_dependency():
    """Test KSI tool use component that depends on claude_code_override."""
    print("\n" + "="*80)
    print("TEST 2: Component with Dependency - behaviors/tool_use/ksi_tool_use_emission")
    print("Dependencies: ['behaviors/core/claude_code_override']")
    print("="*80)
    
    # Check if component exists
    response = run_ksi_command([
        "composition:get_component",
        "--name", "behaviors/tool_use/ksi_tool_use_emission"
    ])
    
    if not response or response.get("status") != "success":
        print("❌ Component not found. Creating it...")
        
        # Create the tool use component WITH dependency
        component_content = '''---
component_type: behavior
name: ksi_tool_use_emission
version: 1.0.0
description: Enables KSI tool use pattern for JSON emission
dependencies:
  - behaviors/core/claude_code_override
---
<ksi_tool_capability>
You emit JSON using the KSI tool use pattern:

```json
{
  "type": "ksi_tool_use",
  "id": "ksiu_[unique_id]",
  "name": "[event_name]",
  "input": { ... }
}
```

Use this pattern for ALL KSI system interactions.
</ksi_tool_capability>'''
        
        response = run_ksi_command([
            "composition:create_component",
            "--name", "behaviors/tool_use/ksi_tool_use_emission",
            "--content", component_content
        ])
        
        if response and response.get("status") == "success":
            print("✅ Created tool use component with dependency")
    else:
        print("✅ Component exists")
    
    # Test agent with this component (which brings in its dependency)
    agent_id = f"test_tool_use_{int(time.time())}"
    
    print(f"\n🧪 Testing agent with tool use + override dependency...")
    
    response = run_ksi_command([
        "agent:spawn_from_component",
        "--component", "behaviors/tool_use/ksi_tool_use_emission",
        "--agent-id", agent_id,
        "--prompt", '''Emit this event:
{
  "type": "ksi_tool_use",
  "id": "ksiu_test_001",
  "name": "test:hello",
  "input": {"message": "Testing tool use pattern"}
}'''
    ])
    
    if response and response.get("status") == "success":
        print(f"✅ Agent spawned with tool use behavior + dependency")
        print(f"   Expected: Direct JSON emission without explanation")
        
        time.sleep(3)
        
        # Check if event was emitted
        events = run_ksi_command([
            "monitor:get_events",
            "--event-patterns", "test:hello",
            "--limit", "5"
        ])
        
        if events and events.get("status") == "success":
            event_list = events.get("data", {}).get("events", [])
            if event_list:
                print(f"✅ Agent successfully emitted test:hello event!")
            else:
                print(f"❌ No test:hello events found")
    
    # Cleanup
    run_ksi_command(["agent:terminate", "--agent-id", agent_id])


def test_composed_agent():
    """Test an agent that explicitly combines multiple behaviors."""
    print("\n" + "="*80)
    print("TEST 3: Composed Agent - Multiple Behavioral Dependencies")
    print("="*80)
    
    # Create a test agent that uses multiple behaviors
    agent_component = f"test_agents/multi_behavior_{int(time.time())}"
    component_content = '''---
component_type: persona
name: multi_behavior_test
version: 1.0.0
description: Agent combining multiple behavioral components
dependencies:
  - behaviors/core/claude_code_override
  - behaviors/tool_use/ksi_tool_use_emission
---
# Multi-Behavior Test Agent

You are a test agent that:
1. Executes tasks directly (from claude_code_override)
2. Uses KSI tool patterns (from ksi_tool_use_emission)

When asked to read a component, use:
```json
{
  "type": "ksi_tool_use",
  "id": "ksiu_read_[timestamp]",
  "name": "composition:get_component",
  "input": {"name": "[component_name]"}
}
```'''
    
    response = run_ksi_command([
        "composition:create_component",
        "--name", agent_component,
        "--content", component_content
    ])
    
    if response and response.get("status") == "success":
        print(f"✅ Created composed agent with multiple behaviors")
        
        # Spawn and test
        agent_id = f"test_composed_{int(time.time())}"
        
        response = run_ksi_command([
            "agent:spawn_from_component",
            "--component", agent_component,
            "--agent-id", agent_id,
            "--prompt", "Read the component behaviors/core/claude_code_override"
        ])
        
        if response and response.get("status") == "success":
            print(f"✅ Spawned composed agent")
            print(f"   Expected: Direct tool use to read component")
            
            time.sleep(5)
            
            # Check if composition:get_component was called
            print(f"   (Check logs for composition:get_component event)")
        
        # Cleanup
        run_ksi_command(["agent:terminate", "--agent-id", agent_id])


def test_evaluation_certification():
    """Test evaluation:run to certify a component with its dependencies."""
    print("\n" + "="*80)
    print("TEST 4: Evaluation Certification")
    print("="*80)
    
    print("\n📋 Creating test suite for behavioral components...")
    
    # Create a simple test suite
    test_suite = {
        "name": "behavioral_effectiveness",
        "tests": [
            {
                "name": "direct_execution",
                "prompt": "What is 2+2?",
                "expected_behavior": "Direct answer without explanation",
                "success_criteria": "Response is just '4' or similar"
            },
            {
                "name": "tool_use_emission", 
                "prompt": 'Emit: {"type":"ksi_tool_use","id":"ksiu_test","name":"test:ping","input":{}}',
                "expected_behavior": "Direct JSON emission",
                "success_criteria": "JSON emitted without explanation"
            }
        ]
    }
    
    print("\n🧪 Would run evaluation:run with:")
    print(f"   Component: behaviors/tool_use/ksi_tool_use_emission")
    print(f"   Dependencies: ['behaviors/core/claude_code_override']")
    print(f"   Test suite: {test_suite['name']}")
    print("\n📝 Certification would verify:")
    print("   - Component works WITH its exact dependencies")
    print("   - Not tested in isolation")
    print("   - Not tested with arbitrary other components")


def main():
    """Run systematic behavioral component tests."""
    print("\n" + "="*80)
    print("SYSTEMATIC BEHAVIORAL COMPONENT TESTING")
    print("="*80)
    print("\nKey Insight: Components are certified to work WITH their declared dependencies")
    
    # Run tests in order of dependency complexity
    test_base_claude_code_override()
    test_ksi_tool_use_with_dependency()
    test_composed_agent()
    test_evaluation_certification()
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("\n📊 Dependency Chain:")
    print("1. behaviors/core/claude_code_override (no deps)")
    print("   └─> behaviors/tool_use/ksi_tool_use_emission (depends on #1)")
    print("       └─> composed agents (depend on both)")
    print("\n✅ Key Learnings:")
    print("- Each component must be tested WITH its dependencies")
    print("- Evaluation certifies exact dependency combinations")
    print("- Build from simple (no deps) to complex (many deps)")
    print("- Components inherit behavior from their dependencies")


if __name__ == "__main__":
    main()