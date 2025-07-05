#!/usr/bin/env python3
"""
Demonstrate filtered event routing in KSI.

Shows how to use the built-in filter system for event handlers
and the enhanced observation system with content filtering.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_daemon.event_system import (
    event_handler, 
    get_router,
    content_filter,
    source_filter,
    combine_filters,
    rate_limit_10_per_second,
    RateLimiter
)
from ksi_client import AsyncClient


# Example 1: Simple content filtering
@event_handler("data:process", 
              filter_func=content_filter("priority", value="high"))
async def handle_high_priority(data):
    """Only processes events where data["priority"] == "high"."""
    print(f"High priority event: {data}")
    return {"processed": "high_priority"}


# Example 2: Pattern matching filter
@event_handler("log:entry",
              filter_func=content_filter("message", pattern="ERROR:*", operator="glob"))
async def handle_error_logs(data):
    """Only processes log entries that start with ERROR:"""
    print(f"Error log detected: {data['message']}")
    return {"alert": "error_detected"}


# Example 3: Numeric comparison filter
@event_handler("metric:report",
              filter_func=content_filter("cpu_usage", value=80, operator="gt"))
async def handle_high_cpu(data):
    """Only processes when CPU usage > 80%"""
    print(f"High CPU alert: {data['cpu_usage']}%")
    return {"alert": "high_cpu"}


# Example 4: Combined filters
@event_handler("task:submit",
              filter_func=combine_filters(
                  content_filter("department", value="engineering"),
                  content_filter("urgency", value=7, operator="gte"),
                  mode="all"
              ))
async def handle_urgent_engineering_tasks(data):
    """Only processes urgent engineering tasks"""
    print(f"Urgent engineering task: {data}")
    return {"assigned": "priority_queue"}


# Example 5: Rate-limited handler
@event_handler("api:request",
              filter_func=rate_limit_10_per_second)
async def handle_api_request(data):
    """Rate limited to 10 requests per second"""
    print(f"Processing API request: {data.get('endpoint')}")
    return {"status": "processed"}


# Example 6: Custom rate limiter
burst_limiter = RateLimiter(max_events=5, window_seconds=0.1)  # 5 events per 100ms

@event_handler("burst:event",
              filter_func=burst_limiter)
async def handle_burst_event(data):
    """Custom rate limiting for burst protection"""
    print(f"Burst event processed: {data}")
    return {"status": "ok"}


async def test_filtered_handlers():
    """Test the filtered event handlers."""
    router = get_router()
    
    print("=== Testing Filtered Event Routing ===\n")
    
    # Test 1: Content filtering
    print("1. Testing priority filter...")
    await router.emit("data:process", {"priority": "low", "task": "cleanup"})
    result = await router.emit("data:process", {"priority": "high", "task": "deploy"})
    print(f"   High priority result: {result}\n")
    
    # Test 2: Pattern matching
    print("2. Testing error log filter...")
    await router.emit("log:entry", {"message": "INFO: System started"})
    result = await router.emit("log:entry", {"message": "ERROR: Connection failed"})
    print(f"   Error log result: {result}\n")
    
    # Test 3: Numeric comparison
    print("3. Testing CPU usage filter...")
    await router.emit("metric:report", {"cpu_usage": 45})
    result = await router.emit("metric:report", {"cpu_usage": 92})
    print(f"   High CPU result: {result}\n")
    
    # Test 4: Combined filters
    print("4. Testing combined filters...")
    await router.emit("task:submit", {"department": "sales", "urgency": 8})
    await router.emit("task:submit", {"department": "engineering", "urgency": 5})
    result = await router.emit("task:submit", {"department": "engineering", "urgency": 9})
    print(f"   Urgent engineering result: {result}\n")
    
    # Test 5: Rate limiting
    print("5. Testing rate limiting (10/sec)...")
    results = []
    for i in range(15):
        result = await router.emit("api:request", {"endpoint": f"/api/v1/data/{i}"})
        if result:
            results.append(i)
    print(f"   Processed {len(results)} out of 15 requests\n")
    
    # Test 6: Burst limiting
    print("6. Testing burst limiting (5 per 100ms)...")
    burst_results = []
    for i in range(10):
        result = await router.emit("burst:event", {"id": i})
        if result:
            burst_results.append(i)
    print(f"   Processed {len(burst_results)} out of 10 burst events")
    
    # Wait for rate limit window to reset
    await asyncio.sleep(0.2)
    result = await router.emit("burst:event", {"id": 99})
    print(f"   After cooldown: {result}\n")


async def test_observation_filtering():
    """Test the enhanced observation system with filtering."""
    async with AsyncClient() as client:
        print("\n=== Testing Observation Filtering ===\n")
        
        # Create test agents
        observer_id = "filter_observer_1"
        target_id = "filter_target_1"
        
        # 1. Subscribe with content filtering
        print("1. Creating filtered observation subscription...")
        subscription = await client.emit_event("observation:subscribe", {
            "observer": observer_id,
            "target": target_id,
            "events": ["task:*"],
            "filter": {
                "content_match": {
                    "field": "priority",
                    "value": "critical"
                },
                "rate_limit": {
                    "max_events": 3,
                    "window_seconds": 1.0
                }
            }
        })
        print(f"   Subscription: {subscription.get('subscription_id')}")
        
        # 2. Test content filtering - these should be filtered out
        print("\n2. Testing content filtering...")
        print("   Emitting low priority task (should be filtered)...")
        await client.emit_event("task:created", {
            "agent_id": target_id,
            "priority": "low",
            "task": "routine_check"
        })
        
        print("   Emitting critical priority task (should be observed)...")
        await client.emit_event("task:created", {
            "agent_id": target_id,
            "priority": "critical",
            "task": "emergency_response"
        })
        
        # 3. Test rate limiting on observations
        print("\n3. Testing observation rate limiting (3 per second)...")
        for i in range(5):
            await client.emit_event("task:updated", {
                "agent_id": target_id,
                "priority": "critical",
                "update_id": i
            })
            print(f"   Emitted critical task update {i}")
        
        # 4. Complex filtering example
        print("\n4. Creating complex filtered subscription...")
        complex_sub = await client.emit_event("observation:subscribe", {
            "observer": observer_id,
            "target": target_id,
            "events": ["metric:*"],
            "filter": {
                "content_match": {
                    "field": "value",
                    "value": 90,
                    "operator": "gt"
                },
                "exclude": ["metric:debug"],
                "sampling_rate": 0.5  # Only observe 50% of matching events
            }
        })
        print(f"   Complex subscription: {complex_sub.get('subscription_id')}")
        
        # Test complex filtering
        print("\n   Testing complex filters...")
        await client.emit_event("metric:cpu", {
            "agent_id": target_id,
            "value": 85  # Below threshold
        })
        print("   Emitted CPU metric: 85 (should be filtered)")
        
        await client.emit_event("metric:cpu", {
            "agent_id": target_id,
            "value": 95  # Above threshold
        })
        print("   Emitted CPU metric: 95 (may be observed - 50% chance)")
        
        await client.emit_event("metric:debug", {
            "agent_id": target_id,
            "value": 99  # Excluded pattern
        })
        print("   Emitted debug metric: 99 (should be excluded)")
        
        # 5. List active subscriptions
        print("\n5. Active observation subscriptions:")
        subs = await client.emit_event("observation:list", {
            "observer": observer_id
        })
        for sub in subs.get("subscriptions", []):
            print(f"   - {sub['subscription_id']}: {sub['target']} -> {sub['events']}")
        
        # Clean up
        print("\n6. Cleaning up subscriptions...")
        await client.emit_event("observation:unsubscribe", {
            "observer": observer_id,
            "target": target_id
        })
        print("   All subscriptions removed")


async def main():
    """Run all filter demonstrations."""
    # Test basic filtered handlers
    await test_filtered_handlers()
    
    # Test observation filtering
    await test_observation_filtering()
    
    print("\n=== Filter Testing Complete ===")


if __name__ == "__main__":
    asyncio.run(main())