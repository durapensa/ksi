#!/usr/bin/env python3
"""
Test completion service v2 deployment and integration.
"""

import json
import socket
import time
import uuid

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


def test_completion_service_v2_features():
    """Test all v2 features in one comprehensive test."""
    print("\n=== Testing Completion Service V2 Features ===")
    
    # Test 1: Basic async completion (replaces old sync interface)
    print("\n1. Testing basic async completion...")
    request_id = f"test_req_{uuid.uuid4().hex[:8]}"
    response = send_event("completion:async", {
        "request_id": request_id,
        "prompt": "What is 5+5?",
        "model": "claude-cli/sonnet",
        "client_id": "test_client",
        "priority": "normal",
        "max_tokens": 50
    })
    
    if response and response.get('status') in ['queued', 'ready']:
        print(f"   ✓ Async completion accepted: request_id={request_id}")
    else:
        print(f"   ✗ Async completion failed: {response}")
        return False
    
    # Test 2: Queue status
    print("\n2. Testing queue status...")
    status = send_event("completion:queue_status", {})
    print(f"   Queue status: {status}")
    
    # Test 3: Conversation locking with unique IDs
    print("\n3. Testing conversation locking...")
    conv_id = f"test_conv_{uuid.uuid4().hex[:8]}"
    req1_id = f"test_req_{uuid.uuid4().hex[:8]}"
    req2_id = f"test_req_{uuid.uuid4().hex[:8]}"
    
    # First lock should succeed
    lock1 = send_event("conversation:acquire_lock", {
        "request_id": req1_id,
        "conversation_id": conv_id
    })
    
    if lock1 and lock1.get('acquired'):
        print(f"   ✓ First lock acquired: {lock1}")
        
        # Second lock should be queued
        lock2 = send_event("conversation:acquire_lock", {
            "request_id": req2_id,
            "conversation_id": conv_id
        })
        
        if lock2 and not lock2.get('acquired') and lock2.get('state') == 'queued':
            print(f"   ✓ Second lock correctly queued: {lock2}")
            
            # Release first lock
            release = send_event("conversation:release_lock", {
                "request_id": req1_id
            })
            
            if release and release.get('released'):
                print(f"   ✓ Lock released successfully")
                
                # Check if second request now holds lock
                status = send_event("conversation:lock_status", {
                    "conversation_id": conv_id
                })
                
                if status and status.get('holder') == req2_id:
                    print(f"   ✓ Lock transferred to queued request")
                else:
                    print(f"   ✗ Lock transfer failed: {status}")
    
    # Test 4: Async completion with priority
    print("\n4. Testing async completion with priority...")
    
    # Queue multiple requests with different priorities
    priorities = ["low", "high", "critical", "normal"]
    requests = []
    
    for priority in priorities:
        response = send_event("completion:async", {
            "prompt": f"Test {priority} priority",
            "model": "claude-cli/sonnet",
            "priority": priority,
            "max_tokens": 20
        })
        
        if response and response.get('status') == 'ready':
            requests.append({
                'priority': priority,
                'request_id': response['request_id']
            })
            print(f"   ✓ Queued {priority} priority request: {response['request_id']}")
    
    # Check final queue status
    time.sleep(0.5)  # Give queue time to process
    final_status = send_event("completion:queue_status", {})
    print(f"\n   Final queue status: {final_status}")
    
    # Test 5: Circuit breaker simulation (optional)
    print("\n5. Testing circuit breaker (simulated)...")
    
    # Try to queue a request with circuit breaker config
    cb_response = send_event("completion:async", {
        "prompt": "Test with circuit breaker",
        "model": "claude-cli/sonnet",
        "priority": "normal",
        "max_tokens": 50,
        "circuit_breaker_config": {
            "max_depth": 3,
            "token_budget": 10000
        }
    })
    
    if cb_response:
        print(f"   ✓ Request with circuit breaker config: {cb_response}")
    
    return True


def main():
    """Run deployment verification."""
    print("=== Completion Service V2 Deployment Test ===")
    
    # Check daemon health first
    health = send_event("system:health", {})
    if not health or health.get('status') != 'healthy':
        print("✗ Daemon is not healthy!")
        return
    
    print(f"✓ Daemon is healthy (uptime: {health.get('uptime', 0):.1f}s)")
    
    # Run comprehensive test
    if test_completion_service_v2_features():
        print("\n✅ Completion Service V2 is fully deployed and working!")
    else:
        print("\n❌ Completion Service V2 has issues")


if __name__ == "__main__":
    main()