#!/usr/bin/env python3
"""
Test the async completion queue with injection system.

This test demonstrates:
1. Circuit breaker preventing runaway chains
2. Conversation lock preventing forking
3. Injection router handling completion results
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_daemon.plugins.injection.circuit_breakers import (
    CompletionCircuitBreaker, 
    check_completion_allowed,
    get_circuit_breaker_status
)
from ksi_daemon.plugins.completion.completion_queue import (
    CompletionQueue,
    Priority,
    enqueue_completion,
    get_next_completion,
    mark_completion_done,
    get_queue_status
)
from ksi_daemon.plugins.injection.injection_router import (
    queue_completion_with_injection,
    handle_completion_result,
    get_trigger_boilerplate
)


async def test_circuit_breakers():
    """Test circuit breaker functionality."""
    print("\n=== Testing Circuit Breakers ===")
    
    # Test 1: Normal request should pass
    request1 = {
        'id': 'test_req_1',
        'prompt': 'What is the meaning of life?',
        'circuit_breaker_config': {
            'max_depth': 3,
            'token_budget': 10000
        }
    }
    
    allowed = check_completion_allowed(request1)
    print(f"Test 1 - Normal request allowed: {allowed}")
    assert allowed, "Normal request should be allowed"
    
    # Test 2: Chain depth limit
    requests = []
    parent_id = 'test_req_1'
    
    for i in range(2, 6):
        request = {
            'id': f'test_req_{i}',
            'prompt': f'Follow-up question {i}',
            'circuit_breaker_config': {
                'parent_request_id': parent_id,
                'max_depth': 3,
                'token_budget': 10000
            }
        }
        
        allowed = check_completion_allowed(request)
        requests.append((request, allowed))
        
        if allowed:
            parent_id = request['id']
    
    # Check that depth 4 and 5 were blocked
    print(f"Test 2 - Depth 2 allowed: {requests[0][1]}")
    print(f"Test 2 - Depth 3 allowed: {requests[1][1]}")
    print(f"Test 2 - Depth 4 blocked: {not requests[2][1]}")
    print(f"Test 2 - Depth 5 blocked: {not requests[3][1]}")
    
    assert requests[0][1], "Depth 2 should be allowed"
    assert requests[1][1], "Depth 3 should be allowed"
    assert not requests[2][1], "Depth 4 should be blocked"
    assert not requests[3][1], "Depth 5 should be blocked"
    
    # Test 3: Get circuit breaker status
    status = get_circuit_breaker_status('test_req_3')
    print(f"\nTest 3 - Circuit breaker status: {json.dumps(status, indent=2)}")
    
    print("\n✓ Circuit breaker tests passed")


async def test_completion_queue():
    """Test completion queue with conversation locks."""
    print("\n=== Testing Completion Queue ===")
    
    queue = CompletionQueue()
    
    # Test 1: Basic enqueue/dequeue
    request1 = {
        'request_id': 'queue_test_1',
        'prompt': 'Hello world',
        'session_id': 'conv_123'
    }
    
    result1 = await queue.enqueue(request1)
    print(f"Test 1 - Enqueue result: {json.dumps(result1, indent=2)}")
    assert result1['status'] == 'ready', "First request should be ready"
    
    # Test 2: Second request to same conversation should queue
    request2 = {
        'request_id': 'queue_test_2',
        'prompt': 'Follow-up question',
        'session_id': 'conv_123'  # Same conversation
    }
    
    result2 = await queue.enqueue(request2)
    print(f"\nTest 2 - Second request queued: {json.dumps(result2, indent=2)}")
    assert result2['status'] == 'queued', "Second request should be queued"
    assert result2.get('conversation_locked'), "Should indicate conversation is locked"
    
    # Test 3: Different conversation should proceed
    request3 = {
        'request_id': 'queue_test_3',
        'prompt': 'Different conversation',
        'session_id': 'conv_456'  # Different conversation
    }
    
    result3 = await queue.enqueue(request3)
    print(f"\nTest 3 - Different conversation ready: {json.dumps(result3, indent=2)}")
    assert result3['status'] == 'ready', "Different conversation should be ready"
    
    # Test 4: Complete first request, second should become ready
    completion_result = {
        'result': 'The meaning of life is 42',
        'session_id': 'conv_123'  # Same conversation ID returned
    }
    
    complete_result = await queue.complete('queue_test_1', completion_result)
    print(f"\nTest 4 - Completion result: {json.dumps(complete_result, indent=2)}")
    assert complete_result['next_request'] == 'queue_test_2', "Next request should be activated"
    
    # Test 5: Fork detection
    fork_result = {
        'result': 'This caused a fork',
        'session_id': 'conv_123_forked'  # Different ID = fork!
    }
    
    fork_complete = await queue.complete('queue_test_2', fork_result)
    print(f"\nTest 5 - Fork detection: {json.dumps(fork_complete, indent=2)}")
    assert fork_complete['fork_info'], "Fork should be detected"
    assert fork_complete['fork_info']['fork_detected'], "Fork detection flag should be true"
    
    # Test 6: Queue status
    status = queue.get_status()
    print(f"\nTest 6 - Queue status: {json.dumps(status, indent=2)}")
    
    print("\n✓ Completion queue tests passed")


async def test_injection_router():
    """Test injection router functionality."""
    print("\n=== Testing Injection Router ===")
    
    # Test 1: Queue completion with injection
    request_id = queue_completion_with_injection({
        'id': 'inject_test_1',
        'prompt': 'Research the history of AI',
        'injection_config': {
            'enabled': True,
            'trigger_type': 'research',
            'target_sessions': ['session_001', 'session_002'],
            'follow_up_guidance': 'Consider storing findings in collective memory'
        },
        'circuit_breaker_config': {
            'max_depth': 5
        }
    })
    
    print(f"Test 1 - Injection metadata stored for: {request_id}")
    
    # Test 2: Handle completion result (simulated)
    completion_data = {
        'request_id': request_id,
        'result': 'AI research began in the 1950s with pioneers like Alan Turing...',
        'session_id': 'session_001',
        'attributes': {
            'confidence': 0.95,
            'sources': 3
        }
    }
    
    # This would normally be called by the event system
    injection_result = handle_completion_result(completion_data, {})
    print(f"\nTest 2 - Injection result: {json.dumps(injection_result, indent=2)}")
    
    if injection_result and 'injection:queued' in injection_result:
        assert injection_result['injection:queued']['target_count'] == 2, "Should queue 2 injections"
    
    # Test 3: Test trigger boilerplate generation
    for trigger_type in ['antThinking', 'coordination', 'research', 'memory', 'general']:
        boilerplate = get_trigger_boilerplate(trigger_type)
        print(f"\nTest 3 - {trigger_type} trigger preview:")
        print(boilerplate[:200] + "...")
    
    print("\n✓ Injection router tests passed")


async def test_integration():
    """Test full integration of all components."""
    print("\n=== Testing Full Integration ===")
    
    # Scenario: Multiple agents researching with coordination
    
    # Agent 1 starts research
    request1 = {
        'request_id': 'agent1_research',
        'prompt': 'Research quantum computing applications',
        'session_id': 'research_session_001',
        'injection_config': {
            'enabled': True,
            'trigger_type': 'research',
            'target_sessions': ['coordinator_session'],
            'follow_up_guidance': 'Report findings to coordinator'
        },
        'circuit_breaker_config': {
            'max_depth': 3,
            'token_budget': 20000
        }
    }
    
    # Check circuit breaker
    if check_completion_allowed(request1):
        print("✓ Agent 1 research request passed circuit breakers")
    
    # Enqueue request
    queue = CompletionQueue()
    queue_result = await queue.enqueue(request1, Priority.HIGH)
    print(f"✓ Agent 1 request status: {queue_result['status']}")
    
    # Agent 2 tries same conversation (should queue)
    request2 = {
        'request_id': 'agent2_followup',
        'prompt': 'Add information about quantum cryptography',
        'session_id': 'research_session_001',  # Same session!
    }
    
    queue_result2 = await queue.enqueue(request2, Priority.NORMAL)
    print(f"✓ Agent 2 request queued: {queue_result2['status']} at position {queue_result2.get('position', 0)}")
    
    # Simulate completion of Agent 1's request
    completion1 = {
        'result': 'Quantum computing has applications in cryptography, optimization...',
        'session_id': 'research_session_001'
    }
    
    complete_result = await queue.complete('agent1_research', completion1)
    print(f"✓ Agent 1 completed, next request: {complete_result.get('next_request')}")
    
    # Handle injection for coordinator
    injection_handled = handle_completion_result({
        'request_id': 'agent1_research',
        'result': completion1['result'],
        'session_id': completion1['session_id']
    }, {})
    
    if injection_handled and 'injection:queued' in injection_handled:
        print(f"✓ Injection queued for coordinator: {injection_handled}")
    
    # Check final status
    final_status = queue.get_status()
    print(f"\n✓ Final system status: {json.dumps(final_status, indent=2)}")
    
    print("\n✓ Integration test completed successfully!")


async def main():
    """Run all tests."""
    print("Testing Async Completion Queue with Event-Driven Injection\n")
    
    try:
        await test_circuit_breakers()
        await test_completion_queue()
        await test_injection_router()
        await test_integration()
        
        print("\n🎉 All tests passed!")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())