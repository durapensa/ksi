#!/usr/bin/env python3
"""
Test the KSI tool use pattern for reliable JSON emission.
"""

import json
import subprocess
import time


def run_ksi_command(event, **kwargs):
    """Execute KSI command."""
    cmd = ["ksi", "send", event]
    for k, v in kwargs.items():
        if isinstance(v, (dict, list)):
            cmd.extend([f"--{k}", json.dumps(v)])
        else:
            cmd.extend([f"--{k}", str(v)])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return {}
    
    try:
        return json.loads(result.stdout)
    except:
        return {"raw": result.stdout}


def test_tool_use_pattern():
    """Test both legacy and tool use patterns."""
    print("Testing KSI Tool Use Pattern for JSON Emission\n")
    
    # Step 1: Create test agent with tool use behavior
    print("1. Creating test agent with ksi_tool_use behavior...")
    
    agent_content = """---
component_type: agent
name: tool_use_test_agent
version: 1.0.0
description: Test agent for ksi_tool_use pattern
dependencies:
  - core/base_agent
  - behaviors/tool_use/ksi_tool_use_emission
---

# Tool Use Test Agent

You are a test agent demonstrating the ksi_tool_use pattern.

## Your Task

When asked to emit events, use the ksi_tool_use format for complex data:

```json
{
  "type": "ksi_tool_use",
  "id": "ksiu_[unique_id]",
  "name": "[event_name]",
  "input": {
    // event data
  }
}
```

This format is especially useful for events with multi-line content."""
    
    # Create the test agent component
    result = run_ksi_command(
        "composition:create_component",
        name="agents/tool_use_test",
        content=agent_content
    )
    print(f"Component creation: {result.get('status', 'unknown')}")
    
    # Step 2: Spawn the agent
    print("\n2. Spawning test agent...")
    result = run_ksi_command(
        "agent:spawn",
        component="agents/tool_use_test",
        agent_id="tool_use_tester"
    )
    print(f"Agent spawn: {result.get('status')}")
    
    # Step 3: Test legacy format
    print("\n3. Testing legacy JSON format...")
    result = run_ksi_command(
        "completion:async",
        agent_id="tool_use_tester",
        prompt='Emit a simple status event using legacy format: {"event": "agent:status", "data": {"agent_id": "test", "status": "ready"}}'
    )
    request_id_1 = result.get("request_id")
    print(f"Request ID: {request_id_1}")
    
    # Step 4: Test tool use format
    print("\n4. Testing ksi_tool_use format...")
    result = run_ksi_command(
        "completion:async",
        agent_id="tool_use_tester",
        prompt='''Emit a component creation event using ksi_tool_use format:
{
  "type": "ksi_tool_use",
  "id": "ksiu_comp_001",
  "name": "composition:create_component",
  "input": {
    "name": "test/simple_component",
    "content": "---\\ncomponent_type: agent\\nname: simple\\n---\\n\\n# Simple Test\\n\\nMulti-line content with:\\n- Lists\\n- Special chars\\n- JSON examples: {\\"test\\": true}"
  }
}'''
    )
    request_id_2 = result.get("request_id")
    print(f"Request ID: {request_id_2}")
    
    # Wait for processing
    print("\n5. Waiting for event extraction...")
    time.sleep(10)
    
    # Check events
    print("\n6. Checking extracted events...")
    result = run_ksi_command(
        "monitor:get_events",
        event_patterns=["agent:status", "composition:create_component"],
        limit=10,
        since=time.time() - 60
    )
    
    events = result.get("events", [])
    print(f"Found {len(events)} recent events")
    
    # Check for our specific events
    legacy_found = False
    tool_use_found = False
    
    for event in events:
        if event.get("event") == "agent:status" and event.get("data", {}).get("_extracted_from_response"):
            legacy_found = True
            print("✓ Legacy format event found")
            
        if event.get("event") == "composition:create_component":
            data = event.get("data", {})
            if data.get("_extracted_via") == "ksi_tool_use":
                tool_use_found = True
                print("✓ Tool use format event found")
                print(f"  Tool use ID: {data.get('_tool_use_id')}")
    
    # Check if component was created
    if tool_use_found:
        result = run_ksi_command(
            "composition:get_component",
            name="test/simple_component"
        )
        if result.get("name"):
            print("✓ Component successfully created via tool use format!")
    
    # Cleanup
    print("\n7. Cleaning up...")
    run_ksi_command("agent:terminate", agent_id="tool_use_tester", force=True)
    
    # Summary
    print("\n" + "="*50)
    print("Test Results:")
    print(f"- Legacy format extraction: {'✓ PASS' if legacy_found else '✗ FAIL'}")
    print(f"- Tool use format extraction: {'✓ PASS' if tool_use_found else '✗ FAIL'}")
    print("="*50)
    
    return legacy_found and tool_use_found


if __name__ == "__main__":
    success = test_tool_use_pattern()
    
    if success:
        print("\n✅ KSI Tool Use Pattern Test PASSED!")
        print("\nThe dual-path extraction is working correctly.")
        print("Agents can now use ksi_tool_use format for reliable JSON emission.")
    else:
        print("\n❌ KSI Tool Use Pattern Test FAILED!")
        print("\nTroubleshooting:")
        print("1. Check daemon logs: tail -f var/logs/daemon/daemon.log.jsonl | jq")
        print("2. Verify tool_use_adapter.py is loaded")
        print("3. Check JSON extraction logs")