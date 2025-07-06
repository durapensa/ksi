#!/usr/bin/env python3
"""
Debug the completion flow to understand why results aren't being returned.
"""

import asyncio
import json
import time
from ksi_socket_utils import KSISocketClient


async def debug_completion():
    """Debug a single completion request."""
    client = KSISocketClient("var/run/daemon.sock")
    
    print("=== Debugging Completion Flow ===\n")
    
    # 1. Send completion request
    print("1. Sending completion request...")
    completion_request = {
        "event": "completion:async",
        "data": {
            "prompt": "Say HELLO",
            "model": "claude-cli/sonnet",
            "agent_config": {
                "profile": "base_single_agent"
            }
        }
    }
    
    result = await client.send_command_async(completion_request)
    print(f"Response: {json.dumps(result, indent=2)}")
    
    request_id = result.get("data", {}).get("request_id")
    if not request_id:
        print("❌ No request_id returned")
        return
    
    print(f"\n✓ Request ID: {request_id}")
    
    # 2. Poll for status
    print("\n2. Polling for status...")
    for i in range(30):  # 30 seconds max
        await asyncio.sleep(1)
        
        status_result = await client.send_command_async({
            "event": "completion:status",
            "data": {"request_id": request_id}
        })
        
        # Check if this is a specific status
        if "data" in status_result and isinstance(status_result["data"], dict):
            status = status_result["data"].get("status")
            if status:
                print(f"  Status: {status}")
                if status in ["completed", "failed", "error"]:
                    break
    
    # 3. Try to get result
    print("\n3. Getting result...")
    result_response = await client.send_command_async({
        "event": "completion:result",
        "data": {"request_id": request_id}
    })
    
    print(f"Result response: {json.dumps(result_response, indent=2)}")
    
    # 4. Check event log for this request
    print("\n4. Checking event log...")
    events = await client.get_events(
        event_patterns=["completion:*"],
        since=time.time() - 60,  # Last minute
        limit=50
    )
    
    request_events = [e for e in events if request_id in str(e.get("data", {}))]
    print(f"Found {len(request_events)} events for this request:")
    for event in request_events:
        print(f"  - {event['event_name']} at {event['timestamp']}")
    
    # 5. Check for any completion results in general
    print("\n5. Checking for ANY completion:result events...")
    result_events = [e for e in events if e["event_name"] == "completion:result"]
    print(f"Found {len(result_events)} completion:result events in the last minute")
    
    # 6. Check active completions
    print("\n6. Checking completion service status...")
    service_status = await client.send_command_async({
        "event": "completion:status",
        "data": {}
    })
    
    if "data" in service_status:
        data = service_status["data"]
        print(f"Active completions: {data.get('active_completions', 'unknown')}")
        print(f"Status counts: {data.get('status_counts', {})}")


if __name__ == "__main__":
    asyncio.run(debug_completion())