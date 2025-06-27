#!/usr/bin/env python3
"""
Basic test for completion service v2 functionality.
"""

import json
import socket
import time

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


def test_basic_sync_completion():
    """Test basic synchronous completion."""
    print("\n=== Testing Basic Sync Completion ===")
    
    response = send_event("completion:request", {
        "prompt": "What is 2+2?",
        "model": "claude-cli/sonnet",
        "max_tokens": 50
    })
    
    if response and response.get('response', {}).get('result'):
        print(f"✓ Got result: {response['response']['result']}")
        return True
    else:
        print(f"✗ Failed: {response}")
        return False


def test_async_completion():
    """Test async completion."""
    print("\n=== Testing Async Completion ===")
    
    response = send_event("completion:async", {
        "prompt": "What is 3+3?",
        "model": "claude-cli/sonnet",
        "priority": "high",
        "max_tokens": 50
    })
    
    if response and response.get('status') == 'ready':
        print(f"✓ Async request queued: {response['request_id']}")
        return True
    else:
        print(f"✗ Failed: {response}")
        return False


def test_queue_status():
    """Test queue status."""
    print("\n=== Testing Queue Status ===")
    
    response = send_event("completion:queue_status", {})
    
    if response and 'queued' in response:
        print(f"✓ Queue status: {response}")
        return True
    else:
        print(f"✗ Failed: {response}")
        return False


def test_conversation_lock():
    """Test conversation locking."""
    print("\n=== Testing Conversation Lock ===")
    
    # Acquire lock
    response = send_event("conversation:acquire_lock", {
        "request_id": "test_req_001",
        "conversation_id": "test_conv_001"
    })
    
    if response and response.get('acquired'):
        print(f"✓ Lock acquired: {response}")
        
        # Try to acquire same lock again
        response2 = send_event("conversation:acquire_lock", {
            "request_id": "test_req_002",
            "conversation_id": "test_conv_001"
        })
        
        if response2 and not response2.get('acquired'):
            print(f"✓ Second lock correctly queued: {response2}")
            
            # Release first lock
            release = send_event("conversation:release_lock", {
                "request_id": "test_req_001"
            })
            
            if release and release.get('released'):
                print(f"✓ Lock released: {release}")
                return True
    
    print("✗ Lock test failed")
    return False


def main():
    """Run all tests."""
    print("=== Completion Service V2 Basic Tests ===")
    
    tests = [
        test_basic_sync_completion,
        test_async_completion,
        test_queue_status,
        test_conversation_lock
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n=== Results: {passed}/{len(tests)} tests passed ===")


if __name__ == "__main__":
    main()