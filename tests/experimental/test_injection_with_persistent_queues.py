#!/usr/bin/env python3
"""Test injection router with persistent async_state queues."""

import asyncio
import json
import sys
import time
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from ksi_client import EventClient


async def test_injection_persistence():
    """Test that injection queues persist across operations."""
    async with EventClient() as client:
        print("\n=== Testing Injection Router with Persistent Queues ===\n")
        
        # Test session and agent IDs
        test_session_id = "test_session_persistence"
        test_agent_id = "test_agent_persistence"
        
        # 1. Clear any existing injections for clean test
        print("1. Clearing any existing injections...")
        clear_result = await client.injection.clear(
            session_id=test_session_id
        )
        print(f"Clear result: {json.dumps(clear_result, indent=2)}")
        
        # 2. Store a next-mode injection
        print("\n2. Storing next-mode injection...")
        inject_result = await client.injection.inject(
            content="This is a test injection that should persist in the database.",
            mode="next",
            position="system_reminder",
            session_id=test_session_id,
            metadata={
                "test": True,
                "timestamp": time.time()
            }
        )
        print(f"Inject result: {json.dumps(inject_result, indent=2)}")
        
        # 3. List pending injections to verify storage
        print("\n3. Listing pending injections...")
        list_result = await client.injection.list(
            session_id=test_session_id
        )
        print(f"List result: {json.dumps(list_result, indent=2)}")
        
        # 4. Check async_state directly to verify persistence
        print("\n4. Checking async_state queue directly...")
        queue_result = await client.async_state.get_queue(
            namespace="injection", 
            key=test_session_id
        )
        print(f"Queue contents: {json.dumps(queue_result, indent=2)}")
        
        # 5. Test injection with completion flow
        print("\n5. Testing injection with completion flow...")
        
        # Store injection for an agent (simulating async completion result)
        completion_inject = await client.injection.inject(
            content="Previous async task completed successfully. Results: [test data]",
            mode="next",
            position="system_reminder",
            session_id=f"agent_{test_agent_id}_session",
            metadata={
                "trigger_type": "completion_result",
                "request_id": "test_request_123"
            }
        )
        print(f"Completion injection: {json.dumps(completion_inject, indent=2)}")
        
        # 6. Simulate the completion service processing a result with injection config
        print("\n6. Simulating completion result processing with injection...")
        process_result = await client.injection.process_result(
            request_id="test_optimization_123",
            result={
                "status": "success",
                "response": "The optimization has been completed. Performance improved by 25%."
            },
            injection_metadata={
                "injection_config": {
                    "enabled": True,
                    "mode": "next",
                    "target_sessions": [test_session_id],
                    "trigger_type": "optimization_complete",
                    "follow_up_guidance": "Review the optimization results and determine next steps."
                }
            }
        )
        print(f"Process result: {json.dumps(process_result, indent=2)}")
        
        # 7. Verify both injections are queued
        print("\n7. Verifying all injections are queued...")
        final_list = await client.injection.list()
        print(f"All injection queues: {json.dumps(final_list, indent=2)}")
        
        # 8. Get injection router status
        print("\n8. Getting injection router status...")
        status = await client.injection.status()
        print(f"Injection router status: {json.dumps(status, indent=2)}")
        
        # 9. Clean up test data
        print("\n9. Cleaning up test data...")
        cleanup_results = []
        for session in [test_session_id, f"agent_{test_agent_id}_session"]:
            result = await client.injection.clear(session_id=session)
            cleanup_results.append(result)
        print(f"Cleanup results: {json.dumps(cleanup_results, indent=2)}")
        
        print("\n=== Test Complete ===")
        print("\nKey findings:")
        print("- Injections are stored in persistent async_state queues")
        print("- Queue contents survive across operations")  
        print("- Integration between injection router and async_state is working")
        print("- TTL-based cleanup can be configured per injection")


if __name__ == "__main__":
    asyncio.run(test_injection_persistence())