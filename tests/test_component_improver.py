#!/usr/bin/env python3
"""Test the simple component improver agent."""

import time
import json
from ksi_common.sync_client import MinimalSyncClient

client = MinimalSyncClient()


def test_component_improver():
    """Test the component improver on a verbose component."""
    print("=== Testing Component Improver Agent ===\n")
    
    # 1. Create a verbose test component
    print("1. Creating verbose test component...")
    verbose_component = """---
component_type: behavior
name: verbose_example
---

# Verbose Example Component

This is a very verbose component that contains a lot of unnecessary text and repetitive instructions that could be simplified significantly.

## Instructions

When you receive a request, you should:

1. First, make sure to carefully read the entire request
2. Then, after reading the request, analyze what is being asked
3. Next, after analyzing the request, formulate your response
4. Finally, provide your response

## Additional Instructions

Remember to always:
- Read requests carefully (as mentioned above)
- Analyze what is being asked (as stated previously)
- Formulate good responses (this is important)
- Provide helpful responses (this is critical)

## More Details

This component is designed to help you understand how to process requests. When processing requests, it's important to read them carefully, analyze them thoroughly, and respond appropriately.

## Summary

In summary, this component teaches you to:
1. Read requests
2. Analyze requests  
3. Respond to requests

Remember all of the above instructions when using this component.
"""
    
    create_result = client.send_event("composition:create_component", {
        "name": "test/verbose_example",
        "content": verbose_component
    })
    print(f"Component created: {create_result.get('status')}\n")
    
    # 2. Spawn the improver agent
    print("2. Spawning component improver agent...")
    spawn_result = client.send_event("agent:spawn", {
        "component": "personas/improvers/simple_component_improver",
        "capabilities": ["base", "composition", "agent_communication"]
    })
    agent_id = spawn_result.get("agent_id")
    print(f"Agent ID: {agent_id}\n")
    
    # 3. Ask agent to analyze the verbose component
    print("3. Asking agent to analyze verbose component...")
    completion_result = client.send_event("completion:async", {
        "agent_id": agent_id,
        "prompt": f"Please analyze this component and suggest improvements:\n\n{verbose_component}"
    })
    request_id = completion_result.get("request_id")
    print(f"Request ID: {request_id}")
    
    # Wait for processing
    print("Waiting for analysis...")
    time.sleep(10)
    
    # 4. Check for agent results
    print("\n4. Checking for analysis results...")
    events = client.send_event("monitor:get_events", {
        "event_patterns": ["agent:result", "agent:status"],
        "limit": 10
    })
    
    # Find our agent's events
    agent_events = []
    for event in events.get("events", []):
        if event.get("data", {}).get("_agent_id") == agent_id:
            agent_events.append(event)
    
    print(f"Found {len(agent_events)} events from improver agent")
    
    # Look for analysis result
    for event in agent_events:
        if event.get("event_name") == "agent:result":
            result_data = event.get("data", {})
            if result_data.get("result_type") == "component_analysis":
                print("\n✅ Found component analysis!")
                analysis = result_data.get("analysis", {})
                print(f"Token estimate: {analysis.get('token_count_estimate')}")
                print(f"Improvements found: {len(analysis.get('improvements', []))}")
                print(f"Summary: {analysis.get('improvement_summary')}")
                
                # Show first improvement
                improvements = analysis.get('improvements', [])
                if improvements:
                    print(f"\nFirst improvement:")
                    print(json.dumps(improvements[0], indent=2))
                break
    else:
        print("❌ No analysis result found")
    
    # 5. Cleanup
    print("\n5. Cleaning up...")
    client.send_event("agent:terminate", {"agent_id": agent_id})
    client.send_event("composition:delete_component", {"name": "test/verbose_example"})
    print("Test complete!")


def main():
    """Run component improver test."""
    test_component_improver()


if __name__ == "__main__":
    main()