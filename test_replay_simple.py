#!/usr/bin/env python3
"""
Test event replay functionality.
"""

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
    print("=== Testing Event Replay ===\n")
    
    # Generate some test events first
    print("1. Generating test events for replay...")
    test_events = [
        {"event": "replay_test:start", "data": {"agent_id": "replay_agent", "step": 1}},
        {"event": "replay_test:process", "data": {"agent_id": "replay_agent", "step": 2, "items": 50}},
        {"event": "replay_test:complete", "data": {"agent_id": "replay_agent", "step": 3}},
    ]
    
    for event in test_events:
        result = send_event(event["event"], event["data"])
        print(f"   Generated: {event['event']}")
        time.sleep(0.1)
    
    # Test replay functionality
    print("\n2. Testing event replay...")
    replay_result = send_event("observation:replay", {
        "event_patterns": ["replay_test:*"],
        "filter": {
            "limit": 10
        },
        "speed": 5.0,
        "as_new_events": False  # Emit as replay events
    })
    
    if "error" in replay_result["data"]:
        print(f"   Error: {replay_result['data']['error']}")
    else:
        session_id = replay_result["data"]["session_id"]
        event_count = replay_result["data"]["event_count"]
        duration = replay_result["data"]["estimated_duration_seconds"]
        print(f"   Session: {session_id}")
        print(f"   Events to replay: {event_count}")
        print(f"   Estimated duration: {duration:.2f}s")
        
        # Wait for replay to complete
        time.sleep(duration + 0.5)
        print("   Replay completed")
    
    # Test pattern analysis
    print("\n3. Testing pattern analysis...")
    pattern_result = send_event("observation:analyze_patterns", {
        "event_patterns": ["replay_test:*"],
        "analysis_type": "frequency",
        "limit": 100
    })
    
    if "error" in pattern_result["data"]:
        print(f"   Error: {pattern_result['data']['error']}")
    else:
        total = pattern_result["data"].get("total_events", 0)
        print(f"   Analyzed {total} events")
        freq = pattern_result["data"].get("event_frequency", {})
        if freq:
            print("   Event frequencies:")
            for event, count in freq.items():
                print(f"     - {event}: {count}")
    
    print("\n=== Replay Test Complete ===")


if __name__ == "__main__":
    main()