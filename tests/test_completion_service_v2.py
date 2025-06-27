#!/usr/bin/env python3
"""
Test script for completion service v2 with queue and injection integration.
"""

import asyncio
import json
import uuid
import socket
import time
from pathlib import Path

# Socket path
SOCKET_PATH = "/Users/dp/projects/ksi/var/run/daemon.sock"


def send_event(event_name: str, data: dict):
    """Send event to daemon via Unix socket."""
    
    message = {
        "event": event_name,
        "data": data
    }
    
    try:
        # Connect to socket
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(SOCKET_PATH)
        
        # Send message
        client.send(json.dumps(message).encode() + b'\n')
        
        # Read response
        response = b""
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            response += chunk
            if b'\n' in response:
                break
        
        client.close()
        
        # Parse response
        if response:
            return json.loads(response.decode().strip())
        return None
        
    except Exception as e:
        print(f"Error sending event: {e}")
        return None


def test_basic_completion():
    """Test basic synchronous completion."""
    print("\n=== Testing Basic Completion ===")
    
    response = send_event("completion:request", {
        "prompt": "What is 2+2?",
        "model": "claude-cli/haiku",
        "session_id": "test_session_001",
        "max_tokens": 100
    })
    
    print(f"Response: {json.dumps(response, indent=2)}")
    
    return response


def test_async_completion_with_injection():
    """Test async completion with injection configuration."""
    print("\n=== Testing Async Completion with Injection ===")
    
    request_id = f"async_test_{uuid.uuid4().hex[:8]}"
    
    response = send_event("completion:async", {
        "request_id": request_id,
        "prompt": "Research the history of Unix sockets and summarize key developments.",
        "model": "claude-cli/haiku",
        "session_id": "research_session_001",
        "priority": "high",
        "injection_config": {
            "enabled": True,
            "trigger_type": "research",
            "target_sessions": ["coordinator_session"],
            "follow_up_guidance": "Consider if this research reveals any architectural patterns relevant to KSI."
        },
        "circuit_breaker_config": {
            "max_depth": 3,
            "token_budget": 10000,
            "time_window": 600
        }
    })
    
    print(f"Queue response: {json.dumps(response, indent=2)}")
    
    # Wait a moment for processing
    print("Waiting for async processing...")
    time.sleep(3)
    
    # Check queue status
    queue_status = send_event("completion:queue_status", {})
    print(f"Queue status: {json.dumps(queue_status, indent=2)}")
    
    return response


def test_conversation_lock():
    """Test conversation locking mechanism."""
    print("\n=== Testing Conversation Lock ===")
    
    session_id = "lock_test_session"
    
    # Send two rapid requests to same session
    print("Sending first request...")
    response1 = send_event("completion:async", {
        "prompt": "First request",
        "session_id": session_id,
        "priority": "normal"
    })
    print(f"First response: {json.dumps(response1, indent=2)}")
    
    print("\nSending second request immediately...")
    response2 = send_event("completion:async", {
        "prompt": "Second request",
        "session_id": session_id,
        "priority": "normal"
    })
    print(f"Second response: {json.dumps(response2, indent=2)}")
    
    # Check lock status
    lock_status = send_event("conversation:lock_status", {
        "conversation_id": session_id
    })
    print(f"\nLock status: {json.dumps(lock_status, indent=2)}")
    
    return response1, response2


def test_circuit_breaker():
    """Test circuit breaker limits."""
    print("\n=== Testing Circuit Breaker ===")
    
    # Try to create a deep chain
    parent_request_id = None
    
    for i in range(5):
        request_id = f"chain_test_{i}"
        
        response = send_event("completion:async", {
            "request_id": request_id,
            "prompt": f"Chain request {i}",
            "session_id": f"chain_session_{i}",
            "priority": "low",
            "injection_config": {
                "enabled": True,
                "trigger_type": "coordination"
            },
            "circuit_breaker_config": {
                "max_depth": 3,
                "parent_request_id": parent_request_id
            }
        })
        
        print(f"Chain {i} response: {json.dumps(response, indent=2)}")
        
        if response.get('status') == 'blocked':
            print(f"Circuit breaker triggered at depth {i}")
            break
        
        parent_request_id = request_id
        time.sleep(0.5)


def test_priority_queue():
    """Test priority-based queue processing."""
    print("\n=== Testing Priority Queue ===")
    
    # Send requests with different priorities
    priorities = [
        ("low", "Low priority task"),
        ("critical", "URGENT: Critical task"),
        ("normal", "Normal task"),
        ("high", "High priority task"),
        ("background", "Background task")
    ]
    
    requests = []
    for priority, prompt in priorities:
        response = send_event("completion:async", {
            "prompt": prompt,
            "priority": priority,
            "session_id": f"priority_test_{priority}"
        })
        requests.append((priority, response))
        print(f"Queued {priority}: {response.get('status')}")
    
    # Check queue order
    time.sleep(1)
    queue_status = send_event("completion:queue_status", {})
    print(f"\nQueue status: {json.dumps(queue_status, indent=2)}")


def test_completion_status():
    """Test completion service status."""
    print("\n=== Testing Completion Status ===")
    
    status = send_event("completion:status", {})
    print(f"Completion service status: {json.dumps(status, indent=2)}")


def main():
    """Run all tests."""
    
    print("=== Completion Service V2 Integration Test ===")
    print(f"Socket: {SOCKET_PATH}")
    
    # Check if daemon is running
    if not Path(SOCKET_PATH).exists():
        print("\nERROR: Daemon socket not found. Is the daemon running?")
        print("Start with: ./daemon_control.sh start")
        return
    
    try:
        # Run tests
        test_basic_completion()
        test_async_completion_with_injection()
        test_conversation_lock()
        test_circuit_breaker()
        test_priority_queue()
        test_completion_status()
        
        print("\n=== All tests completed ===")
        
    except KeyboardInterrupt:
        print("\nTests interrupted")
    except Exception as e:
        print(f"\nTest error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()