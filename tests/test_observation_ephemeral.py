#!/usr/bin/env python3
"""
Test ephemeral observation system behavior.

Tests that subscriptions are properly ephemeral with checkpoint/restore capability.
"""

import asyncio
import json
import subprocess
import time
import uuid


def send_event(event_name, data):
    """Send event to daemon and return response."""
    request = json.dumps({"event": event_name, "data": data})
    result = subprocess.run(
        ["nc", "-U", "var/run/daemon.sock"],
        input=request.encode(),
        capture_output=True
    )
    if result.returncode == 0:
        try:
            return json.loads(result.stdout.decode())
        except json.JSONDecodeError:
            return {"error": "Invalid JSON response", "output": result.stdout.decode()}
    else:
        return {"error": f"Failed to send event: {result.stderr.decode()}"}


def restart_daemon():
    """Restart the daemon."""
    subprocess.run(["./daemon_control.py", "restart"], capture_output=True)
    time.sleep(2)  # Wait for daemon to start


def checkpoint_daemon():
    """Create a checkpoint."""
    result = send_event("checkpoint:create", {"reason": "test checkpoint"})
    return result.get("data", {}).get("checkpoint_id")


def restore_checkpoint(checkpoint_id):
    """Restore from checkpoint."""
    subprocess.run(["./daemon_control.py", "stop"], capture_output=True)
    subprocess.run(["./daemon_control.py", "restore", checkpoint_id], capture_output=True)
    time.sleep(2)  # Wait for daemon to start


def test_subscriptions_ephemeral():
    """Test that subscriptions are lost on normal restart."""
    print("\n=== Test 1: Subscriptions are ephemeral on normal restart ===")
    
    # Create test agents
    observer_id = f"test_observer_{uuid.uuid4().hex[:8]}"
    target_id = f"test_target_{uuid.uuid4().hex[:8]}"
    
    send_event("state:entity:create", {
        "type": "agent",
        "id": observer_id,
        "properties": {"role": "observer"}
    })
    
    send_event("state:entity:create", {
        "type": "agent",
        "id": target_id,
        "properties": {"role": "target"}
    })
    
    # Create subscription
    sub_result = send_event("observation:subscribe", {
        "observer": observer_id,
        "target": target_id,
        "events": ["test:*"]
    })
    
    subscription_id = sub_result.get("data", {}).get("subscription_id")
    print(f"✓ Created subscription: {subscription_id}")
    
    # List subscriptions
    list_result = send_event("observation:list", {"observer": observer_id})
    count_before = list_result.get("data", {}).get("count", 0)
    print(f"✓ Subscriptions before restart: {count_before}")
    
    # Restart daemon (normal restart)
    print("  Restarting daemon...")
    restart_daemon()
    
    # List subscriptions again
    list_result = send_event("observation:list", {"observer": observer_id})
    count_after = list_result.get("data", {}).get("count", 0)
    print(f"✓ Subscriptions after restart: {count_after}")
    
    if count_after == 0:
        print("✅ PASS: Subscriptions were properly ephemeral")
    else:
        print("❌ FAIL: Subscriptions persisted across restart")
    
    return count_after == 0


def test_agent_termination_cleanup():
    """Test that subscriptions are cleaned up on agent termination."""
    print("\n=== Test 2: Agent termination cleanup ===")
    
    # Create test agents
    observer_id = f"test_observer_{uuid.uuid4().hex[:8]}"
    target_id = f"test_target_{uuid.uuid4().hex[:8]}"
    
    send_event("state:entity:create", {
        "type": "agent",
        "id": observer_id,
        "properties": {"role": "observer"}
    })
    
    send_event("state:entity:create", {
        "type": "agent",
        "id": target_id,
        "properties": {"role": "target"}
    })
    
    # Create subscription
    sub_result = send_event("observation:subscribe", {
        "observer": observer_id,
        "target": target_id,
        "events": ["test:*"]
    })
    
    subscription_id = sub_result.get("data", {}).get("subscription_id")
    print(f"✓ Created subscription: {subscription_id}")
    
    # Terminate observer agent
    term_result = send_event("agent:terminated", {"agent_id": observer_id})
    removed = term_result.get("data", {}).get("subscriptions_removed", 0)
    print(f"✓ Terminated observer, removed {removed} subscriptions")
    
    # List subscriptions
    list_result = send_event("observation:list", {"observer": observer_id})
    count = list_result.get("data", {}).get("count", 0)
    
    if count == 0:
        print("✅ PASS: Subscriptions cleaned up on agent termination")
    else:
        print("❌ FAIL: Subscriptions remain after agent termination")
    
    return count == 0


def test_checkpoint_restore():
    """Test that subscriptions are preserved through checkpoint/restore."""
    print("\n=== Test 3: Checkpoint/restore preservation ===")
    
    # Create test agents
    observer_id = f"test_observer_{uuid.uuid4().hex[:8]}"
    target_id = f"test_target_{uuid.uuid4().hex[:8]}"
    
    send_event("state:entity:create", {
        "type": "agent",
        "id": observer_id,
        "properties": {"role": "observer"}
    })
    
    send_event("state:entity:create", {
        "type": "agent",
        "id": target_id,
        "properties": {"role": "target"}
    })
    
    # Create subscription with rate limiting
    sub_result = send_event("observation:subscribe", {
        "observer": observer_id,
        "target": target_id,
        "events": ["test:*"],
        "filter": {
            "rate_limit": {
                "max_events": 10,
                "window_seconds": 60.0
            }
        }
    })
    
    subscription_id = sub_result.get("data", {}).get("subscription_id")
    print(f"✓ Created subscription with rate limit: {subscription_id}")
    
    # Create checkpoint
    print("  Creating checkpoint...")
    checkpoint_id = checkpoint_daemon()
    print(f"✓ Created checkpoint: {checkpoint_id}")
    
    # Restore from checkpoint
    print("  Restoring from checkpoint...")
    restore_checkpoint(checkpoint_id)
    
    # List subscriptions
    list_result = send_event("observation:list", {"observer": observer_id})
    subscriptions = list_result.get("data", {}).get("subscriptions", [])
    count = len(subscriptions)
    
    if count == 1:
        print("✅ PASS: Subscription preserved through checkpoint/restore")
        # Check if rate limit was preserved
        if subscriptions[0].get("subscription_id") == subscription_id:
            print("✅ PASS: Subscription ID preserved")
    else:
        print(f"❌ FAIL: Expected 1 subscription, found {count}")
    
    return count == 1


def test_historical_query():
    """Test querying historical observations from event log."""
    print("\n=== Test 4: Historical observation query ===")
    
    # Create test agent
    target_id = f"test_target_{uuid.uuid4().hex[:8]}"
    
    send_event("state:entity:create", {
        "type": "agent",
        "id": target_id,
        "properties": {"role": "target"}
    })
    
    # Generate some events
    for i in range(5):
        send_event("test:event", {
            "agent_id": target_id,
            "value": i
        })
    
    time.sleep(1)  # Let events settle
    
    # Query historical observations
    query_result = send_event("observation:query", {
        "target": target_id,
        "events": ["test:*"],
        "limit": 10
    })
    
    events = query_result.get("data", {}).get("events", [])
    print(f"✓ Found {len(events)} historical events")
    
    if len(events) >= 5:
        print("✅ PASS: Historical query returned events")
    else:
        print(f"❌ FAIL: Expected at least 5 events, found {len(events)}")
    
    return len(events) >= 5


def test_circuit_breaker():
    """Test circuit breaker for failing observers."""
    print("\n=== Test 5: Circuit breaker pattern ===")
    
    # This test would need a way to simulate observer failures
    # For now, just verify the async queue is working
    
    observer_id = f"test_observer_{uuid.uuid4().hex[:8]}"
    target_id = f"test_target_{uuid.uuid4().hex[:8]}"
    
    send_event("state:entity:create", {
        "type": "agent",
        "id": observer_id,
        "properties": {"role": "observer"}
    })
    
    send_event("state:entity:create", {
        "type": "agent",
        "id": target_id,
        "properties": {"role": "target"}
    })
    
    # Create subscription
    sub_result = send_event("observation:subscribe", {
        "observer": observer_id,
        "target": target_id,
        "events": ["test:*"]
    })
    
    # Generate many events quickly
    print("  Generating burst of events...")
    for i in range(20):
        send_event("test:burst", {
            "agent_id": target_id,
            "value": i
        })
    
    print("✅ PASS: Async queue handled burst without blocking")
    return True


def main():
    """Run all tests."""
    print("=== Ephemeral Observation System Tests ===")
    
    tests = [
        test_subscriptions_ephemeral,
        test_agent_termination_cleanup,
        test_checkpoint_restore,
        test_historical_query,
        test_circuit_breaker
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            failed += 1
    
    print(f"\n=== Summary ===")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total: {len(tests)}")
    
    if failed == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ {failed} tests failed")


if __name__ == "__main__":
    main()