#!/usr/bin/env python3
"""
Incremental test of DSL optimization executor capabilities.
Tests basic event emission before attempting full optimization workflows.
"""

import asyncio
import json
import time
from pathlib import Path
from ksi_client.client import EventClient

async def test_basic_event_emission():
    """Test 1: Can the agent emit basic JSON events?"""
    print("\n=== TEST 1: Basic Event Emission ===")
    
    client = EventClient()
    await client.connect()
    
    # Spawn DSL executor
    agent_id = f"test_dsl_basic_{int(time.time())}"
    spawn_result = await client.send_event("agent:spawn_from_component", {
        "component": "components/agents/dsl_optimization_executor",
        "agent_id": agent_id
    })
    
    print(f"Spawned agent: {agent_id}")
    print(f"Security profile: {spawn_result.get('config', {}).get('security_profile', 'unknown')}")
    
    # Test basic event emission
    print("\nRequesting basic event emission...")
    completion = await client.send_event("completion:async", {
        "agent_id": agent_id,
        "prompt": 'Emit this exact JSON event:\n{"event": "agent:progress", "data": {"agent_id": "' + agent_id + '", "progress": 0.5, "message": "Testing basic emission"}}\n\nDo not describe or explain, just emit the JSON.'
    })
    
    # Wait for response
    await asyncio.sleep(12)
    
    # Check for emitted events
    events = await client.send_event("monitor:get_events", {
        "event_patterns": ["agent:progress"],
        "data_contains": agent_id,
        "limit": 5
    })
    
    found_progress = False
    for event in events.get("events", []):
        if event.get("data", {}).get("message") == "Testing basic emission":
            found_progress = True
            print("✅ Agent successfully emitted progress event!")
            break
    
    if not found_progress:
        print("❌ No progress event found. Agent may be asking for permissions.")
    
    # Cleanup
    await client.send_event("agent:terminate", {"agent_id": agent_id})
    await client.disconnect()
    
    return found_progress

async def test_optimization_event():
    """Test 2: Can the agent emit optimization:async events?"""
    print("\n=== TEST 2: Optimization Event Emission ===")
    
    client = EventClient()
    await client.connect()
    
    # Spawn DSL executor
    agent_id = f"test_dsl_opt_{int(time.time())}"
    spawn_result = await client.send_event("agent:spawn_from_component", {
        "component": "components/agents/dsl_optimization_executor",
        "agent_id": agent_id
    })
    
    print(f"Spawned agent: {agent_id}")
    
    # Test optimization event emission
    print("\nRequesting optimization event emission...")
    completion = await client.send_event("completion:async", {
        "agent_id": agent_id,
        "prompt": 'Emit this exact JSON event:\n{"event": "optimization:async", "data": {"component": "test_component", "framework": "dspy", "config": {"test": true, "trials": 1}}}\n\nDo not describe or explain, just emit the JSON.'
    })
    
    # Wait for response
    await asyncio.sleep(12)
    
    # Check for optimization events
    events = await client.send_event("monitor:get_events", {
        "event_patterns": ["optimization:async"],
        "limit": 10
    })
    
    found_optimization = False
    for event in events.get("events", []):
        if event.get("data", {}).get("component") == "test_component":
            found_optimization = True
            print("✅ Agent successfully emitted optimization:async event!")
            print(f"   Optimization ID: {event.get('data', {}).get('optimization_id', 'unknown')}")
            break
    
    if not found_optimization:
        print("❌ No optimization event found.")
    
    # Cleanup
    await client.send_event("agent:terminate", {"agent_id": agent_id})
    await client.disconnect()
    
    return found_optimization

async def test_dsl_execution():
    """Test 3: Can the agent execute DSL patterns?"""
    print("\n=== TEST 3: DSL Pattern Execution ===")
    
    client = EventClient()
    await client.connect()
    
    # Spawn DSL executor
    agent_id = f"test_dsl_exec_{int(time.time())}"
    spawn_result = await client.send_event("agent:spawn_from_component", {
        "component": "components/agents/dsl_optimization_executor",
        "agent_id": agent_id
    })
    
    print(f"Spawned agent: {agent_id}")
    
    # Test DSL execution
    dsl_prompt = f"""You are a DSL interpreter. Emit these events in sequence:

1. First emit:
{{"event": "agent:status", "data": {{"agent_id": "{agent_id}", "status": "executing_dsl", "phase": 1}}}}

2. Then emit:
{{"event": "agent:progress", "data": {{"agent_id": "{agent_id}", "progress": 0.5, "message": "DSL execution in progress"}}}}

3. Finally emit:
{{"event": "agent:status", "data": {{"agent_id": "{agent_id}", "status": "dsl_complete", "phase": 3}}}}

Emit all three JSON events in your response, one per line. Do not describe or explain."""
    
    print("\nRequesting DSL execution...")
    completion = await client.send_event("completion:async", {
        "agent_id": agent_id,
        "prompt": dsl_prompt
    })
    
    # Wait for response
    await asyncio.sleep(12)
    
    # Check for DSL execution events
    status_events = await client.send_event("monitor:get_events", {
        "event_patterns": ["agent:status", "agent:progress"],
        "data_contains": agent_id,
        "limit": 10
    })
    
    found_dsl_execution = False
    statuses_found = []
    for event in status_events.get("events", []):
        status = event.get("data", {}).get("status")
        if status in ["executing_dsl", "dsl_complete"]:
            statuses_found.append(status)
    
    if "executing_dsl" in statuses_found and "dsl_complete" in statuses_found:
        found_dsl_execution = True
        print("✅ Agent successfully executed DSL pattern (multiple events emitted)!")
    elif statuses_found:
        print(f"⚠️  Partial success - found statuses: {statuses_found}")
    
    if not found_dsl_execution:
        print("❌ No DSL execution events found.")
    
    # Cleanup
    await client.send_event("agent:terminate", {"agent_id": agent_id})
    await client.disconnect()
    
    return found_dsl_execution

async def main():
    """Run incremental tests of DSL executor capabilities."""
    print("DSL Optimization Executor - Incremental Testing")
    print("=" * 50)
    
    # Test 1: Basic event emission
    test1_passed = await test_basic_event_emission()
    
    # Test 2: Optimization event emission
    if test1_passed:
        test2_passed = await test_optimization_event()
    else:
        print("\nSkipping Test 2 - basic emission not working")
        test2_passed = False
    
    # Test 3: DSL pattern execution
    if test2_passed:
        test3_passed = await test_dsl_execution()
    else:
        print("\nSkipping Test 3 - optimization events not working")
        test3_passed = False
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY:")
    print(f"Test 1 (Basic Emission): {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"Test 2 (Optimization Event): {'✅ PASS' if test2_passed else '❌ FAIL'}")
    print(f"Test 3 (DSL Execution): {'✅ PASS' if test3_passed else '❌ FAIL'}")
    
    if test3_passed:
        print("\n🎉 DSL Executor is ready for full optimization workflows!")
    else:
        print("\n⚠️  DSL Executor needs fixes before running full workflows.")

if __name__ == "__main__":
    asyncio.run(main())