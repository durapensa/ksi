#!/usr/bin/env python3
"""
Test the integrated prompt evaluation system with proper async handling.
"""

import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.ksi_socket_utils import KSISocketClient, wait_for_completion


async def test_prompt_evaluation():
    """Test prompt evaluation on hello_agent profile."""
    
    print("Testing prompt evaluation system...")
    client = KSISocketClient()
    
    # Send evaluation request
    result = await client.send_command_async({
        "event": "prompt:evaluate",
        "data": {
            "composition_name": "hello_agent",
            "composition_type": "profile",
            "test_suite": "basic_effectiveness",
            "model": "claude-cli/sonnet",
            "update_metadata": False,
            "notes": "Testing integrated prompt evaluation"
        }
    })
    
    print(f"\nInitial response: {json.dumps(result, indent=2)}")
    
    if result['data'].get('status') == 'success':
        print("\n✓ Prompt evaluation succeeded!")
        data = result['data']
        
        if 'summary' in data:
            summary = data['summary']
            print(f"\nSummary:")
            print(f"  Total tests: {summary['total_tests']}")
            print(f"  Successful: {summary['successful']}")
            print(f"  Contamination rate: {summary['contamination_rate']:.2%}")
            print(f"  Avg response time: {summary['avg_response_time']:.2f}s")
        
        if 'detailed_results' in data:
            print(f"\nDetailed results:")
            for test_result in data['detailed_results']:
                status = "✓" if test_result['success'] else "✗"
                print(f"\n  {status} {test_result['test_name']}")
                print(f"     Response time: {test_result['response_time']:.2f}s")
                if test_result.get('error'):
                    print(f"     Error: {test_result['error']}")
                else:
                    print(f"     Contaminated: {test_result['contaminated']}")
                    print(f"     Behaviors found: {test_result['behaviors_found']}")
                    print(f"     Expected: {test_result['expected_behaviors']}")
                    
    else:
        print(f"\n✗ Prompt evaluation failed: {result['data'].get('error', 'Unknown error')}")


async def test_simple_prompt():
    """Test with a simple prompt first."""
    
    print("\n\nTesting simple prompt completion...")
    client = KSISocketClient()
    
    # Send a simple completion
    result = await client.send_command_async({
        "event": "completion:async",
        "data": {
            "prompt": "Say 'Hello World!' and nothing else.",
            "model": "claude-cli/sonnet",
            "agent_config": {
                "profile": "hello_agent"
            }
        }
    })
    
    print(f"Initial response: {json.dumps(result, indent=2)}")
    
    if result.get('data', {}).get('request_id'):
        request_id = result['data']['request_id']
        print(f"\nWaiting for completion {request_id}...")
        
        # Wait for completion
        completion_result = await wait_for_completion(request_id, timeout=30)
        
        if completion_result:
            print(f"\n✓ Completion succeeded!")
            print(f"Response: {completion_result.get('response', 'No response')}")
            print(f"Session ID: {completion_result.get('session_id', 'No session ID')}")
        else:
            print(f"\n✗ Completion timed out")


async def main():
    """Run all tests."""
    # Test simple completion first
    await test_simple_prompt()
    
    # Then test full prompt evaluation
    await test_prompt_evaluation()


if __name__ == "__main__":
    asyncio.run(main())