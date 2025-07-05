#!/usr/bin/env python3
"""
Simple test of observation system using netcat-style commands.
"""

import asyncio
import json
import subprocess
import time


def send_event(event_name, data):
    """Send event to daemon and return response."""
    request = json.dumps({"event": event_name, "data": data})
    result = subprocess.run(
        ["nc", "-U", "var/run/daemon.sock"],
        input=request.encode(),
        capture_output=True
    )
    if result.returncode == 0:
        return json.loads(result.stdout.decode())
    else:
        raise Exception(f"Failed to send event: {result.stderr.decode()}")


def main():
    print("=== Testing Observation System ===\n")
    
    # Test 1: Create subscription
    print("1. Creating observation subscription...")
    subscription_result = send_event("observation:subscribe", {
        "observer": "test_observer_1",
        "target": "test_target_1",
        "events": ["test:*", "data:*"]
    })
    
    if "error" in subscription_result:
        print(f"   Error: {subscription_result['error']}")
        return
    
    subscription_id = subscription_result["data"]["subscription_id"]
    print(f"   Created subscription: {subscription_id}")
    
    # Test 2: Generate test events (simulating target agent)
    print("\n2. Generating test events...")
    test_events = [
        {"event": "test:start", "data": {"agent_id": "test_target_1", "phase": "init"}},
        {"event": "data:process", "data": {"agent_id": "test_target_1", "items": 100}},
        {"event": "test:end", "data": {"agent_id": "test_target_1", "phase": "done"}}
    ]
    
    for event in test_events:
        result = send_event(event["event"], event["data"])
        print(f"   Sent {event['event']}")
        time.sleep(0.1)  # Small delay between events
    
    # Test 3: Query observation history
    print("\n3. Querying observation history...")
    history_result = send_event("observation:query_history", {
        "target": "test_target_1",
        "limit": 20
    })
    
    if "error" in history_result:
        print(f"   Error: {history_result['error']}")
    else:
        count = history_result["data"]["count"]
        print(f"   Found {count} observation records")
        if history_result["data"].get("stats"):
            print(f"   Stats: {history_result['data']['stats']}")
    
    # Test 4: Analyze patterns
    print("\n4. Analyzing event patterns...")
    pattern_result = send_event("observation:analyze_patterns", {
        "event_patterns": ["*"],
        "analysis_type": "frequency",
        "limit": 100
    })
    
    if "error" in pattern_result:
        print(f"   Error: {pattern_result['error']}")
    else:
        total = pattern_result["data"].get("total_events", 0)
        print(f"   Analyzed {total} events")
        freq = pattern_result["data"].get("event_frequency", {})
        if freq:
            print("   Most frequent events:")
            for event, count in list(freq.items())[:5]:
                print(f"     - {event}: {count}")
    
    # Test 5: List subscriptions
    print("\n5. Listing active subscriptions...")
    list_result = send_event("observation:list", {})
    
    if "error" in list_result:
        print(f"   Error: {list_result['error']}")
    else:
        subs = list_result["data"]["subscriptions"]
        print(f"   Found {len(subs)} active subscriptions")
        for sub in subs:
            print(f"     - {sub['observer']} -> {sub['target']}: {sub['events']}")
    
    # Test 6: Unsubscribe
    print("\n6. Cleaning up subscription...")
    unsub_result = send_event("observation:unsubscribe", {
        "subscription_id": subscription_id
    })
    
    if "error" in unsub_result:
        print(f"   Error: {unsub_result['error']}")
    else:
        print(f"   Unsubscribed successfully")
    
    print("\n=== Test Complete ===")


if __name__ == "__main__":
    main()