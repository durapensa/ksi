#!/usr/bin/env python3
"""
Test completion flow and show what the KSI hook sees.
"""

import asyncio
import json
import time
from ksi_socket_utils import KSISocketClient, wait_for_completion


async def test_with_hook_monitoring():
    """Test completion and monitor events."""
    client = KSISocketClient("var/run/daemon.sock")
    
    print("=== Testing Completion with Hook Monitoring ===\n")
    
    # Record start time for event monitoring
    start_time = time.time()
    
    # Send a simple completion
    print("1. Sending completion request...")
    result = await client.send_command_async({
        "event": "completion:async",
        "data": {
            "prompt": "Count from 1 to 3",
            "model": "claude-cli/sonnet",
            "agent_config": {
                "profile": "base_single_agent"
            }
        }
    })
    
    request_id = result.get("data", {}).get("request_id")
    print(f"Request ID: {request_id}")
    
    # Wait for completion
    print("\n2. Waiting for completion...")
    completion = await wait_for_completion(request_id, timeout=30)
    
    if completion:
        print(f"\n✓ Got completion!")
        print(f"Response: {completion['response']}")
        print(f"Session ID: {completion['session_id']}")
        print(f"Duration: {completion['duration_ms']}ms")
    else:
        print("✗ Completion timeout")
    
    # Show what events occurred
    print("\n3. Events generated during this test:")
    events = await client.get_events(
        event_patterns=["completion:*", "hook_event_name:*"],
        since=start_time,
        limit=30
    )
    
    print(f"Found {len(events)} events:")
    for event in events:
        print(f"  {event['timestamp']:.2f}: {event['event_name']}")
        if event['event_name'] == 'completion:result' and 'result' in event.get('data', {}):
            print(f"    → Contains actual result data")
    
    # Give hook time to process
    await asyncio.sleep(2)
    
    print("\n4. The KSI hook should have seen these completion events!")


if __name__ == "__main__":
    asyncio.run(test_with_hook_monitoring())