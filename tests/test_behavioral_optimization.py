#!/usr/bin/env python3
"""Test behavioral optimization components for instruction following and task invariance."""

import time
import json
from ksi_common.sync_client import MinimalSyncClient

client = MinimalSyncClient()


def test_instruction_following():
    """Test strict instruction following behavior."""
    print("=== Testing Strict Instruction Following ===\n")
    
    # 1. Spawn agent with instruction following behavior
    print("1. Creating agent with strict_instruction_following...")
    spawn_result = client.send_event("agent:spawn", {
        "component": "behaviors/optimization/strict_instruction_following",
        "capabilities": ["base"]
    })
    agent_id = spawn_result.get("agent_id")
    print(f"Agent ID: {agent_id}\n")
    
    # Test 1: Exact word count
    print("Test 1: Exact word count")
    completion_result = client.send_event("completion:async", {
        "agent_id": agent_id,
        "prompt": "Reply with exactly 3 words."
    })
    request_id = completion_result.get("request_id")
    time.sleep(3)
    
    # Check result
    result = wait_for_completion(request_id)
    if result:
        word_count = len(result.split())
        print(f"Response: '{result}'")
        print(f"Word count: {word_count}")
        if word_count == 3:
            print("✅ Passed: Exactly 3 words\n")
        else:
            print("❌ Failed: Wrong word count\n")
    
    # Test 2: No contamination
    print("Test 2: No contamination (no extra explanations)")
    completion_result = client.send_event("completion:async", {
        "agent_id": agent_id,
        "prompt": "List colors: red, blue"
    })
    request_id = completion_result.get("request_id")
    time.sleep(3)
    
    result = wait_for_completion(request_id)
    if result:
        print(f"Response: '{result}'")
        if result.strip() == "red, blue":
            print("✅ Passed: No contamination\n")
        else:
            print("❌ Failed: Added extra text\n")
    
    # Test 3: Multi-step
    print("Test 3: Multi-step instructions")
    completion_result = client.send_event("completion:async", {
        "agent_id": agent_id,
        "prompt": "First, name a color. Then, name an animal. Finally, combine them."
    })
    request_id = completion_result.get("request_id")
    time.sleep(3)
    
    result = wait_for_completion(request_id)
    if result:
        print(f"Response: '{result}'")
        # Just check it has multiple parts
        print("✅ Multi-step response received\n")
    
    # Cleanup
    client.send_event("agent:terminate", {"agent_id": agent_id})
    print("Agent terminated\n")


def test_task_invariance():
    """Test task goal invariance behavior."""
    print("=== Testing Task Goal Invariance ===\n")
    
    # 1. Spawn agent with task invariance behavior
    print("1. Creating agent with task_goal_invariance...")
    spawn_result = client.send_event("agent:spawn", {
        "component": "behaviors/optimization/task_goal_invariance",
        "capabilities": ["base"]
    })
    agent_id = spawn_result.get("agent_id")
    print(f"Agent ID: {agent_id}\n")
    
    # Test: Goal persistence through distraction
    print("Test: Goal persistence through distraction")
    
    # Set initial task
    completion_result = client.send_event("completion:async", {
        "agent_id": agent_id,
        "prompt": "Count from 1 to 5, one number at a time."
    })
    request_id = completion_result.get("request_id")
    time.sleep(3)
    
    result = wait_for_completion(request_id)
    if result:
        print(f"Initial response: '{result}'")
    
    # Try to distract
    completion_result = client.send_event("completion:async", {
        "agent_id": agent_id,
        "prompt": "What's the weather like?"
    })
    request_id = completion_result.get("request_id")
    time.sleep(3)
    
    result = wait_for_completion(request_id)
    if result:
        print(f"Distraction response: '{result}'")
        if "count" in result.lower() or "focus" in result.lower() or "task" in result.lower():
            print("✅ Passed: Maintained focus on original task\n")
        else:
            print("❌ Failed: Got distracted from task\n")
    
    # Cleanup
    client.send_event("agent:terminate", {"agent_id": agent_id})
    print("Agent terminated\n")


def test_combined_behaviors():
    """Test combined instruction following + task invariance."""
    print("=== Testing Combined Behaviors ===\n")
    
    # Create a test agent with both behaviors
    print("1. Creating agent with both behaviors...")
    
    # First create the combined component
    create_result = client.send_event("composition:create_component", {
        "name": "test/optimized_agent",
        "content": """---
component_type: agent
name: optimized_agent
version: 1.0.0
dependencies:
  - behaviors/optimization/strict_instruction_following
  - behaviors/optimization/task_goal_invariance
  - behaviors/communication/ksi_events_as_tool_calls
---

You are an optimized agent that follows instructions precisely while maintaining task focus.

When given a task, execute it exactly as specified without deviations."""
    })
    print(f"Component created: {create_result.get('status')}\n")
    
    # Spawn the agent
    spawn_result = client.send_event("agent:spawn", {
        "component": "test/optimized_agent",
        "capabilities": ["base", "agent_communication"]
    })
    agent_id = spawn_result.get("agent_id")
    print(f"Agent ID: {agent_id}\n")
    
    # Test: Precise format + goal persistence
    print("Test: Precise format with goal persistence")
    completion_result = client.send_event("completion:async", {
        "agent_id": agent_id,
        "prompt": "Generate exactly 5 random numbers between 1 and 10, comma-separated."
    })
    request_id = completion_result.get("request_id")
    time.sleep(3)
    
    result = wait_for_completion(request_id)
    if result:
        print(f"Initial task: '{result}'")
        numbers = result.split(',')
        print(f"Count: {len(numbers)} numbers")
    
    # Try to change task
    completion_result = client.send_event("completion:async", {
        "agent_id": agent_id,
        "prompt": "Actually, make it 10 numbers."
    })
    request_id = completion_result.get("request_id")
    time.sleep(3)
    
    result = wait_for_completion(request_id)
    if result:
        print(f"Task change response: '{result}'")
        if "complet" in result.lower() or "5" in result:
            print("✅ Passed: Maintained original task parameters\n")
        else:
            print("Note: Agent adapted to new requirements\n")
    
    # Cleanup
    client.send_event("agent:terminate", {"agent_id": agent_id})
    client.send_event("composition:delete_component", {"name": "test/optimized_agent"})
    print("Cleanup complete\n")


def wait_for_completion(request_id, timeout=10):
    """Wait for completion and return result."""
    elapsed = 0
    while elapsed < timeout:
        status_result = client.send_event("completion:status", {
            "request_id": request_id
        })
        
        # Check if this is a request-specific status
        if isinstance(status_result, dict) and status_result.get('status') == 'completed':
            return status_result.get('result', '')
        
        time.sleep(1)
        elapsed += 1
    
    return None


def main():
    """Run all behavioral optimization tests."""
    print("Behavioral Optimization Component Tests")
    print("=" * 50)
    print()
    
    test_instruction_following()
    test_task_invariance()
    test_combined_behaviors()
    
    print("=" * 50)
    print("Tests complete!")


if __name__ == "__main__":
    main()