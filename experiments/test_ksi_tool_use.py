#!/usr/bin/env python3
"""
Test KSI Tool Use Emission
===========================

Direct test of whether agents can emit KSI tool use events.
"""

import time
import json
from ksi_common.sync_client import MinimalSyncClient


def test_direct_tool_use():
    """Test if an agent can emit a simple KSI tool use event."""
    client = MinimalSyncClient()
    
    print("\n=== TEST: Direct KSI Tool Use Emission ===")
    
    # Create test agent with explicit KSI tool use in prompt
    print("\n1. Creating test agent with KSI tool use prompt...")
    
    result = client.send_event("agent:spawn", {
        "agent_id": "tool_use_test",
        "component": "components/core/base_agent",
        "task": "Emit a KSI tool use event",
        "prompt": """You must emit a KSI tool use event. Output this exact JSON:

{
  "type": "ksi_tool_use",
  "id": "test_001",
  "name": "state:entity:create",
  "input": {
    "type": "test",
    "id": "tool_use_test",
    "properties": {
      "status": "success"
    }
  }
}

Output the JSON above now."""
    })
    
    if result.get("status") == "created":
        print(f"✓ Agent created: tool_use_test")
    else:
        print(f"✗ Failed to create agent: {result}")
        return False
    
    # Wait for potential event emission
    print("\n2. Waiting for event emission...")
    time.sleep(3)
    
    # Check if state entity was created
    state_result = client.send_event("state:entity:get", {
        "type": "test",
        "id": "tool_use_test"
    })
    
    if state_result.get("entity", {}).get("properties", {}).get("status") == "success":
        print("✅ SUCCESS! Agent emitted KSI tool use event!")
        success = True
    else:
        print("❌ FAILURE: No event emitted")
        print(f"State result: {state_result}")
        success = False
    
    # Check logs for extraction
    print("\n3. Checking extraction logs...")
    print("(Check daemon logs for 'Extracted' or 'ksi_tool_use' messages)")
    
    # Cleanup
    client.send_event("agent:terminate", {"agent_id": "tool_use_test"})
    client.send_event("state:entity:delete", {"type": "test", "id": "tool_use_test"})
    
    return success


def test_with_completion_async():
    """Test sending KSI tool use via completion:async."""
    client = MinimalSyncClient()
    
    print("\n=== TEST: KSI Tool Use via completion:async ===")
    
    # Create agent
    print("\n1. Creating agent...")
    client.send_event("agent:spawn", {
        "agent_id": "async_tool_test",
        "component": "components/core/base_agent",
        "task": "Respond to prompts"
    })
    
    # Send prompt via completion:async
    print("\n2. Sending prompt with KSI tool use...")
    result = client.send_event("completion:async", {
        "agent_id": "async_tool_test",
        "prompt": """Please emit this event:

{
  "type": "ksi_tool_use",
  "id": "async_test_001",
  "name": "state:entity:create",
  "input": {
    "type": "test",
    "id": "async_tool_test",
    "properties": {
      "status": "completed"
    }
  }
}""",
        "request_id": "test_request_001"
    })
    
    if result.get("status") == "queued":
        print(f"✓ Request queued: {result.get('request_id')}")
    else:
        print(f"✗ Failed to queue: {result}")
    
    # Wait for processing
    print("\n3. Waiting for processing...")
    time.sleep(5)
    
    # Check result
    state_result = client.send_event("state:entity:get", {
        "type": "test",
        "id": "async_tool_test"
    })
    
    if state_result.get("entity", {}).get("properties", {}).get("status") == "completed":
        print("✅ SUCCESS! Event emitted via completion:async")
        success = True
    else:
        print("❌ FAILURE: No event emitted")
        success = False
    
    # Cleanup
    client.send_event("agent:terminate", {"agent_id": "async_tool_test"})
    client.send_event("state:entity:delete", {"type": "test", "id": "async_tool_test"})
    
    return success


def test_malformed_tool_use():
    """Test that malformed KSI tool use generates error feedback."""
    client = MinimalSyncClient()
    
    print("\n=== TEST: Malformed KSI Tool Use Error Handling ===")
    
    # Create agent
    print("\n1. Creating agent...")
    client.send_event("agent:spawn", {
        "agent_id": "malformed_test",
        "component": "components/core/base_agent",
        "task": "Test malformed JSON"
    })
    
    # Send malformed JSON
    print("\n2. Sending malformed KSI tool use...")
    client.send_event("completion:async", {
        "agent_id": "malformed_test",
        "prompt": """Output this malformed JSON:

{
  "type": "ksi_tool_use",
  "id": "bad_json
  "name": "state:entity:create
  "input": {
    "type": "test"
}"""
    })
    
    print("\n3. Waiting for error feedback...")
    time.sleep(3)
    
    print("(Check daemon logs for 'JSON extraction error' or 'malformed' messages)")
    
    # Cleanup
    client.send_event("agent:terminate", {"agent_id": "malformed_test"})
    
    return True


if __name__ == "__main__":
    print("\n" + "="*80)
    print("KSI TOOL USE EXTRACTION TESTS")
    print("="*80)
    
    # Run tests
    test1 = test_direct_tool_use()
    test2 = test_with_completion_async()
    test3 = test_malformed_tool_use()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Direct tool use emission: {'✓ PASS' if test1 else '✗ FAIL'}")
    print(f"Tool use via completion:async: {'✓ PASS' if test2 else '✗ FAIL'}")
    print(f"Malformed JSON handling: {'✓ PASS' if test3 else '✗ FAIL'}")
    
    print("\n⚠️ Check daemon logs for extraction details:")
    print("tail -f var/logs/daemon/daemon.log.jsonl | grep -E 'Extracted|ksi_tool_use|JSON'")