#!/usr/bin/env python3
"""
Debug Completion Service
========================

Check if the completion service is processing prompts at all.
"""

import time
import json
from ksi_common.sync_client import MinimalSyncClient


def test_basic_completion():
    """Test the most basic completion flow."""
    client = MinimalSyncClient()
    
    print("\n=== Testing Basic Completion ===")
    
    # Create a simple agent
    print("\n1. Creating test agent...")
    result = client.send_event("agent:spawn", {
        "agent_id": "debug_agent",
        "component": "components/core/base_agent",
        "task": "Debug test"
    })
    
    if result.get("status") == "created":
        print(f"✓ Agent created")
    else:
        print(f"✗ Failed: {result}")
        return
    
    # Send a simple prompt via completion:async
    print("\n2. Sending simple prompt...")
    result = client.send_event("completion:async", {
        "agent_id": "debug_agent",
        "prompt": "Say the word 'hello' and nothing else.",
        "request_id": "debug_001"
    })
    
    print(f"Result: {result}")
    
    # Wait a bit
    print("\n3. Waiting for completion...")
    time.sleep(3)
    
    # Check completion status
    print("\n4. Checking completion status...")
    status = client.send_event("completion:status", {})
    
    print(f"Active completions: {status.get('active_completions')}")
    print(f"Failed: {status.get('status_counts', {}).get('failed')}")
    print(f"Completed: {status.get('status_counts', {}).get('completed')}")
    
    # Check if we have any response
    print("\n5. Checking monitor for completion events...")
    events = client.send_event("monitor:get_events", {
        "event_patterns": ["completion:*"],
        "limit": 5
    })
    
    for event in events.get("events", []):
        print(f"  - {event.get('event')}: {event.get('data', {}).get('status', 'unknown')}")
    
    # Cleanup
    client.send_event("agent:terminate", {"agent_id": "debug_agent"})


def test_direct_litellm():
    """Test if litellm provider is working at all."""
    client = MinimalSyncClient()
    
    print("\n=== Testing Direct LiteLLM ===")
    
    # Try to use litellm directly
    result = client.send_event("completion:async", {
        "messages": [
            {"role": "user", "content": "Say hello"}
        ],
        "model": "claude-3-haiku-20240307",
        "request_id": "litellm_test"
    })
    
    print(f"Result: {result}")
    
    time.sleep(3)


if __name__ == "__main__":
    test_basic_completion()
    test_direct_litellm()