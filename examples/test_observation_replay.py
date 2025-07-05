#!/usr/bin/env python3
"""
Test observation replay and historical analysis capabilities.

Demonstrates recording, querying, and replaying observed events.
"""

import asyncio
import time
from ksi_client import EventClient


async def test_observation_recording():
    """Test that observations are being recorded."""
    async with EventClient() as client:
        print("=== Testing Observation Recording ===\n")
        
        # Create test agents
        observer_id = "replay_observer_1"
        target_id = "replay_target_1"
        
        # 1. Set up observation
        print("1. Creating observation subscription...")
        subscription = await client.send_event("observation:subscribe", {
            "observer": observer_id,
            "target": target_id,
            "events": ["test:*", "data:*"]
        })
        
        subscription_id = subscription.get("subscription_id")
        print(f"   Subscription: {subscription_id}")
        
        # 2. Generate some test events
        print("\n2. Generating test events...")
        test_events = [
            {"event": "test:start", "data": {"phase": "initialization"}},
            {"event": "data:process", "data": {"items": 100, "status": "processing"}},
            {"event": "test:checkpoint", "data": {"progress": 50}},
            {"event": "data:complete", "data": {"items": 100, "status": "done"}},
            {"event": "test:end", "data": {"phase": "cleanup"}}
        ]
        
        for i, event_info in enumerate(test_events):
            await client.send_event(event_info["event"], {
                "agent_id": target_id,
                **event_info["data"],
                "sequence": i
            })
            print(f"   Emitted: {event_info['event']}")
            await asyncio.sleep(0.2)  # Small delay between events
        
        # Give time for observations to be recorded
        await asyncio.sleep(1.0)
        
        # 3. Query observation history
        print("\n3. Querying observation history...")
        history = await client.send_event("observation:query_history", {
            "target": target_id,
            "limit": 20
        })
        
        print(f"   Found {history.get('count', 0)} observation records")
        print(f"   Stats: {history.get('stats', {})}")
        
        # Clean up
        await client.send_event("observation:unsubscribe", {
            "subscription_id": subscription_id
        })
        
        return history


async def test_replay_functionality():
    """Test event replay capabilities."""
    async with EventClient() as client:
        print("\n=== Testing Event Replay ===\n")
        
        # 1. Query recent observations to replay
        print("1. Finding events to replay...")
        history = await client.send_event("observation:query_history", {
            "event_name": "data:*",
            "limit": 10
        })
        
        if history.get("count", 0) == 0:
            print("   No events found to replay")
            return
            
        print(f"   Found {history['count']} events to replay")
        
        # 2. Start replay session
        print("\n2. Starting replay session...")
        replay_result = await client.send_event("observation:replay", {
            "event_patterns": ["data:*"],
            "filter": {
                "limit": 5
            },
            "speed": 2.0,  # 2x speed
            "as_new_events": False  # Emit as replay events
        })
        
        session_id = replay_result.get("session_id")
        print(f"   Session ID: {session_id}")
        print(f"   Events to replay: {replay_result.get('event_count')}")
        print(f"   Estimated duration: {replay_result.get('estimated_duration_seconds', 0):.1f}s")
        
        # 3. Listen for replay events
        print("\n3. Waiting for replay to complete...")
        
        # In a real scenario, you would subscribe to replay events
        # For now, just wait for the estimated duration
        wait_time = replay_result.get('estimated_duration_seconds', 0) + 1
        await asyncio.sleep(wait_time)
        
        print("   Replay session completed")


async def test_pattern_analysis():
    """Test pattern analysis capabilities."""
    async with EventClient() as client:
        print("\n=== Testing Pattern Analysis ===\n")
        
        # 1. Frequency analysis
        print("1. Analyzing event frequency...")
        freq_analysis = await client.send_event("observation:analyze_patterns", {
            "event_patterns": ["*"],
            "filter": {},
            "analysis_type": "frequency",
            "limit": 100
        })
        
        if "error" not in freq_analysis:
            print(f"   Total events analyzed: {freq_analysis.get('total_events', 0)}")
            print("   Most frequent events:")
            for event, count in freq_analysis.get("event_frequency", {}).items():
                print(f"     - {event}: {count}")
        
        # 2. Sequence analysis
        print("\n2. Analyzing event sequences...")
        seq_analysis = await client.send_event("observation:analyze_patterns", {
            "event_patterns": ["*"],
            "filter": {},
            "analysis_type": "sequence",
            "limit": 100
        })
        
        if "error" not in seq_analysis:
            print(f"   Unique sequences found: {seq_analysis.get('sequence_count', 0)}")
            common_seqs = seq_analysis.get("common_sequences", [])
            if common_seqs:
                print("   Most common sequences:")
                for seq_info in common_seqs[:3]:
                    print(f"     - {' -> '.join(seq_info['sequence'])}: {seq_info['count']} times")
        
        # 3. Performance analysis
        print("\n3. Analyzing performance patterns...")
        perf_analysis = await client.send_event("observation:analyze_patterns", {
            "event_patterns": ["observe:*"],  # Need observe events for performance
            "filter": {},
            "analysis_type": "performance",
            "limit": 1000
        })
        
        if "error" not in perf_analysis:
            event_perf = perf_analysis.get("event_performance", {})
            if event_perf:
                print("   Event performance statistics:")
                for event, stats in list(event_perf.items())[:3]:
                    print(f"     - {event}:")
                    print(f"       Average: {stats['avg_ms']:.2f}ms")
                    print(f"       Range: {stats['min_ms']:.2f}ms - {stats['max_ms']:.2f}ms")


async def test_targeted_replay():
    """Test replaying events to a specific agent."""
    async with EventClient() as client:
        print("\n=== Testing Targeted Replay ===\n")
        
        # Create a new target agent for replay
        new_target = "replay_receiver_1"
        
        print(f"1. Replaying recent events to agent: {new_target}")
        
        # Replay recent test events to the new target
        replay_result = await client.send_event("observation:replay", {
            "event_patterns": ["test:*"],
            "filter": {
                "limit": 3
            },
            "speed": 5.0,  # 5x speed
            "target_agent": new_target,
            "as_new_events": True  # Re-emit as original events
        })
        
        if "error" in replay_result:
            print(f"   Error: {replay_result['error']}")
        else:
            print(f"   Replaying {replay_result.get('event_count', 0)} events")
            print(f"   Target agent will receive original events")
            
            # Wait for replay
            await asyncio.sleep(replay_result.get('estimated_duration_seconds', 0) + 0.5)
            print("   Replay completed")


async def main():
    """Run all replay tests."""
    # First, record some observations
    print("Setting up test data...\n")
    history = await test_observation_recording()
    
    if history.get("count", 0) > 0:
        # Test replay functionality
        await test_replay_functionality()
        
        # Test pattern analysis
        await test_pattern_analysis()
        
        # Test targeted replay
        await test_targeted_replay()
    else:
        print("No observation data recorded. Skipping replay tests.")
    
    print("\n=== Observation Replay Testing Complete ===")


if __name__ == "__main__":
    asyncio.run(main())