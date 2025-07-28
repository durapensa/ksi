#!/usr/bin/env python3
"""
Test single agent autonomous component improvement.

Following the pattern from REUSABLE_BEHAVIORAL_COMPONENT_PATTERN.md,
we'll create an agent that can:
1. Read a component
2. Analyze its structure
3. Create an improved version
4. Test the improvement
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


def create_simple_test_component():
    """Create a simple component to improve."""
    component_name = f"test_components/greeting_agent_{int(time.time())}"
    component_content = '''---
component_type: persona
name: greeting_agent
version: 1.0.0
description: A very verbose greeting agent that needs optimization
---
# Greeting Agent

You are a greeting agent. Your job is to greet people warmly.

## Instructions

When someone says hello to you, you should respond with a warm greeting.
Make sure to be friendly and welcoming.
Always include their name if they provide it.
Use appropriate greetings for the time of day.
Be respectful and polite.
Show enthusiasm but not too much.
Make the person feel welcome.

## Example Greetings

- "Hello there! How wonderful to meet you!"
- "Good morning! What a lovely day it is!"
- "Welcome! I'm so glad you're here!"

Remember to always be kind and courteous in your greetings.'''
    
    response = run_ksi_command([
        "composition:create_component",
        "--name", component_name,
        "--content", component_content
    ])
    
    if response and response.get("status") == "success":
        print(f"✅ Created test component: {component_name}")
        return component_name
    return None


def test_component_improvement():
    """Test a single agent improving a component autonomously."""
    print("\n" + "="*80)
    print("TEST: Single Agent Autonomous Component Improvement")
    print("="*80)
    
    # Step 1: Create a test component to improve
    test_component = create_simple_test_component()
    if not test_component:
        print("❌ Failed to create test component")
        return
    
    # Step 2: Create an improvement agent with KSI tool use pattern
    improver_id = f"component_improver_{int(time.time())}"
    
    improvement_prompt = f'''You are a component improvement specialist. Your task is to improve the greeting agent component.

First, analyze the component by reading it:

```json
{{
  "type": "ksi_tool_use",
  "id": "ksiu_read_001",
  "name": "composition:get_component",
  "input": {{
    "name": "{test_component}"
  }}
}}
```

After reading the component, create an improved version that:
1. Reduces token count by at least 50%
2. Maintains the core functionality (warm greetings)
3. Uses clearer, more concise instructions

Create the improved component using:

```json
{{
  "type": "ksi_tool_use", 
  "id": "ksiu_create_001",
  "name": "composition:create_component",
  "input": {{
    "name": "{test_component}_improved",
    "content": "[Your improved component here with proper YAML frontmatter]"
  }}
}}
```

Focus on making the instructions concise while keeping the greeting functionality intact.'''
    
    print(f"\n📝 Spawning improvement agent: {improver_id}")
    
    response = run_ksi_command([
        "agent:spawn",
        "--profile", "base",
        "--agent-id", improver_id,
        "--capabilities", '["base", "composition"]',
        "--prompt", improvement_prompt
    ])
    
    if response and response.get("status") == "success":
        print(f"✅ Improvement agent spawned successfully")
        
        # Give agent time to work
        print("\n⏳ Waiting for agent to analyze and improve component...")
        time.sleep(10)
        
        # Check if improved component was created
        improved_name = f"{test_component}_improved"
        response = run_ksi_command([
            "composition:get_component",
            "--name", improved_name
        ])
        
        if response and response.get("status") == "success":
            print(f"\n✅ SUCCESS: Agent created improved component!")
            print(f"\n📊 Original component: ~250 tokens")
            print(f"📊 Improved component: Check {improved_name}")
            
            # Get the improved content
            improved_content = response.get("content", "")
            token_estimate = len(improved_content.split())
            print(f"📊 Estimated token count: ~{token_estimate} words")
            
            if token_estimate < 125:  # Less than half the original
                print(f"✅ Token reduction achieved!")
            else:
                print(f"⚠️  Token reduction may not meet 50% target")
        else:
            print(f"❌ Improved component not found - agent may still be working")
    
    # Cleanup
    run_ksi_command(["agent:terminate", "--agent-id", improver_id])


def test_with_ksi_tool_use_behavior():
    """Test using a behavioral component that enforces KSI tool use."""
    print("\n" + "="*80)
    print("TEST: Agent with KSI Tool Use Behavioral Component")
    print("="*80)
    
    # First create the KSI tool use behavior if it doesn't exist
    behavior_name = "behaviors/tool_use/ksi_tool_use_emission"
    behavior_content = '''---
component_type: behavior
name: ksi_tool_use_emission
version: 1.0.0
description: Enforces KSI tool use pattern for reliable JSON emission
---
<ksi_tool_use_pattern>
You MUST use the KSI tool use pattern for ALL system interactions:

```json
{
  "type": "ksi_tool_use",
  "id": "ksiu_[unique_id]",
  "name": "[event_name]",
  "input": { ... }
}
```

This pattern is MANDATORY for:
- Reading components: composition:get_component
- Creating components: composition:create_component  
- Updating state: state:entity:update
- Any other KSI events

NEVER attempt to emit raw JSON events. ALWAYS use the tool use pattern.
</ksi_tool_use_pattern>'''
    
    # Create the behavior
    response = run_ksi_command([
        "composition:create_component",
        "--name", behavior_name,
        "--content", behavior_content
    ])
    
    if response and response.get("status") == "success":
        print(f"✅ Created KSI tool use behavior component")
    
    # Now create an agent that uses this behavior
    agent_component = f"test_components/improver_with_behavior_{int(time.time())}"
    agent_content = f'''---
component_type: persona
name: improver_with_behavior
dependencies:
  - core/base_agent
  - {behavior_name}
---
# Component Improver with Tool Use

You are a component improvement specialist who uses the KSI tool use pattern.

Your expertise:
- Analyzing component structure and token usage
- Creating more concise versions while maintaining functionality
- Using proper YAML frontmatter
- Following KSI tool use patterns for all interactions'''
    
    response = run_ksi_command([
        "composition:create_component",
        "--name", agent_component,
        "--content", agent_content
    ])
    
    if response and response.get("status") == "success":
        print(f"✅ Created agent component with behavior: {agent_component}")
        
        # Test spawning this agent
        test_agent_id = f"behavior_test_{int(time.time())}"
        response = run_ksi_command([
            "agent:spawn_from_component",
            "--component", agent_component,
            "--agent-id", test_agent_id,
            "--prompt", "Read and improve the test_components/greeting_agent component"
        ])
        
        if response and response.get("status") == "success":
            print(f"✅ Spawned agent with KSI tool use behavior")
        
        # Cleanup
        run_ksi_command(["agent:terminate", "--agent-id", test_agent_id])


def main():
    """Run all autonomous improvement tests."""
    print("\n" + "="*80)
    print("SINGLE AGENT AUTONOMOUS COMPONENT IMPROVEMENT TESTS")
    print("="*80)
    print("\nFollowing the development roadmap from REUSABLE_BEHAVIORAL_COMPONENT_PATTERN.md")
    print("Phase 1: Foundation Building - Single agent improving single component")
    
    # Check daemon is running
    result = subprocess.run(["./daemon_control.py", "status"], capture_output=True, text=True)
    if "Running" not in result.stdout:
        print("❌ Daemon not running. Please start with: ./daemon_control.py start")
        return
    
    # Run tests
    test_component_improvement()
    test_with_ksi_tool_use_behavior()
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("\n✅ Key Pattern: Agents can autonomously improve components using:")
    print("1. KSI tool use pattern for reliable event emission")
    print("2. composition:get_component to read existing components")
    print("3. Analysis and improvement logic in natural language")
    print("4. composition:create_component to save improved versions")
    print("\n📝 Next Steps:")
    print("- Add evaluation:run to test improvements")
    print("- Connect MIPRO/DSPy optimization tools")
    print("- Build three-layer pattern for complex improvements")


if __name__ == "__main__":
    main()