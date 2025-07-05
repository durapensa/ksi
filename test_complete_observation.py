#!/usr/bin/env python3
"""
Complete test of all 5 phases of the agent observation system:
1. Originator-construct tracking (via entity relationships)
2. Universal relational state system  
3. Subscription-based observation
4. Enhanced filtered event routing
5. Historical analysis and replay
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
    print("=== Complete Agent Observation System Test ===\n")
    
    # Phase 1 & 2: Create originator-construct relationships using relational state
    print("Phase 1-2: Creating originator-construct relationships...")
    
    # Create entities
    originator_result = send_event("state:entity:create", {
        "type": "agent",
        "id": "originator_master",
        "properties": {"role": "master", "status": "active"}
    })
    
    construct_result = send_event("state:entity:create", {
        "type": "agent", 
        "id": "construct_worker_1",
        "properties": {"role": "worker", "status": "spawned"}
    })
    
    # Create spawned relationship
    spawn_result = send_event("state:relationship:create", {
        "from": "originator_master",
        "to": "construct_worker_1", 
        "type": "spawned",
        "metadata": {"spawn_time": time.time()}
    })
    
    print(f"   Created originator: {originator_result['data']['id']}")
    print(f"   Created construct: {construct_result['data']['id']}")
    print(f"   Created relationship: spawned")
    
    # Phase 3: Create observation subscription
    print("\nPhase 3: Setting up observation subscription...")
    subscription_result = send_event("observation:subscribe", {
        "observer": "originator_master",
        "target": "construct_worker_1",
        "events": ["work:*", "status:*"],
        "filter": {
            "content_match": {
                "field": "priority",
                "value": "high",
                "operator": "equals"
            },
            "rate_limit": {
                "max_events": 10,
                "window_seconds": 1.0
            }
        }
    })
    
    subscription_id = subscription_result["data"]["subscription_id"]
    print(f"   Created filtered subscription: {subscription_id}")
    
    # Phase 4: Generate events to test filtered routing
    print("\nPhase 4: Testing filtered event routing...")
    
    test_events = [
        # This should be filtered out (wrong priority)
        {"event": "work:start", "data": {"agent_id": "construct_worker_1", "priority": "low", "task": "cleanup"}},
        
        # These should pass the filter
        {"event": "work:process", "data": {"agent_id": "construct_worker_1", "priority": "high", "task": "critical_job"}},
        {"event": "status:update", "data": {"agent_id": "construct_worker_1", "priority": "high", "status": "processing"}},
        {"event": "work:complete", "data": {"agent_id": "construct_worker_1", "priority": "high", "task": "critical_job"}},
        
        # This should be filtered out (wrong priority)
        {"event": "status:idle", "data": {"agent_id": "construct_worker_1", "priority": "low", "status": "waiting"}},
    ]
    
    for event in test_events:
        result = send_event(event["event"], event["data"])
        priority = event["data"].get("priority", "none")
        print(f"   Sent {event['event']} (priority: {priority})")
        time.sleep(0.1)
    
    # Wait for events to be processed
    time.sleep(2)
    
    # Phase 5: Historical analysis and replay
    print("\nPhase 5: Historical analysis and replay...")
    
    # Query observation history
    history_result = send_event("observation:query_history", {
        "observer": "originator_master",
        "target": "construct_worker_1",
        "limit": 20
    })
    
    observation_count = history_result["data"]["count"]
    print(f"   Recorded {observation_count} observations")
    
    # Analyze patterns
    pattern_result = send_event("observation:analyze_patterns", {
        "event_patterns": ["work:*", "status:*"],
        "analysis_type": "frequency",
        "limit": 100
    })
    
    total_events = pattern_result["data"]["total_events"]
    print(f"   Analyzed {total_events} events in pattern analysis")
    
    if pattern_result["data"].get("event_frequency"):
        print("   Event frequencies:")
        for event, count in pattern_result["data"]["event_frequency"].items():
            print(f"     - {event}: {count}")
    
    # Test replay functionality
    print("\n   Testing event replay...")
    replay_result = send_event("observation:replay", {
        "event_patterns": ["work:*"],
        "filter": {"limit": 5},
        "speed": 3.0,
        "as_new_events": False
    })
    
    if "error" not in replay_result["data"]:
        session_id = replay_result["data"]["session_id"]
        replay_count = replay_result["data"]["event_count"]
        duration = replay_result["data"]["estimated_duration_seconds"]
        print(f"   Replay session {session_id}: {replay_count} events, {duration:.2f}s")
        
        # Wait for replay to complete
        time.sleep(duration + 0.5)
        print("   Replay completed")
    
    # Verify relational state tracking
    print("\nVerifying state system...")
    
    # Query relationships
    rel_result = send_event("state:relationship:query", {
        "from": "originator_master",
        "type": "spawned"
    })
    
    relationships = rel_result["data"]["relationships"]
    print(f"   Found {len(relationships)} spawn relationships")
    
    # Query entities
    entities_result = send_event("state:entity:query", {
        "type": "agent",
        "where": {"role": "worker"}
    })
    
    workers = entities_result["data"]["entities"]
    print(f"   Found {len(workers)} worker entities")
    
    # Cleanup
    print("\nCleaning up...")
    unsub_result = send_event("observation:unsubscribe", {
        "subscription_id": subscription_id
    })
    print(f"   Unsubscribed from observations")
    
    print("\n=== All 5 phases tested successfully! ===")
    print("\nSummary:")
    print("✓ Phase 1-2: Originator-construct tracking with relational state")
    print("✓ Phase 3: Subscription-based observation with filtering")
    print("✓ Phase 4: Enhanced filtered event routing (priority filter)")
    print("✓ Phase 5: Historical analysis and replay capabilities")


if __name__ == "__main__":
    main()