#!/usr/bin/env python3
"""
Test script for the orchestration plugin.
"""

import asyncio
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


def test_orchestration_status():
    """Test orchestration status query."""
    print("\n=== Testing Orchestration Status ===")
    
    response = send_event("orchestration:status", {})
    print(f"Status response: {json.dumps(response, indent=2)}")
    
    return response


def test_start_hello_goodbye():
    """Test starting hello-goodbye orchestration."""
    print("\n=== Testing Hello-Goodbye Orchestration ===")
    
    response = send_event("orchestration:start", {
        "pattern": "hello_goodbye",
        "vars": {
            "greeting": "Hello from orchestration test!"
        }
    })
    
    print(f"Start response: {json.dumps(response, indent=2)}")
    
    if response and "orchestration_id" in response:
        orch_id = response["orchestration_id"]
        
        # Wait a moment for agents to spawn
        time.sleep(2)
        
        # Check status
        status = send_event("orchestration:status", {
            "orchestration_id": orch_id
        })
        print(f"\nOrchestration status: {json.dumps(status, indent=2)}")
        
        # Wait for messages
        time.sleep(3)
        
        # Check final status
        final_status = send_event("orchestration:status", {
            "orchestration_id": orch_id
        })
        print(f"\nFinal status: {json.dumps(final_status, indent=2)}")
    
    return response


def test_start_debate():
    """Test starting debate orchestration."""
    print("\n=== Testing Debate Orchestration ===")
    
    response = send_event("orchestration:start", {
        "pattern": "debate",
        "vars": {
            "topic": "Should AI systems have consciousness?"
        }
    })
    
    print(f"Start response: {json.dumps(response, indent=2)}")
    
    if response and "orchestration_id" in response:
        orch_id = response["orchestration_id"]
        
        # Let it run for a bit
        print("\nLetting debate run for 10 seconds...")
        time.sleep(10)
        
        # Check status
        status = send_event("orchestration:status", {
            "orchestration_id": orch_id
        })
        print(f"\nDebate status: {json.dumps(status, indent=2)}")
        
        # Terminate
        print("\nTerminating debate...")
        term_result = send_event("orchestration:terminate", {
            "orchestration_id": orch_id
        })
        print(f"Termination result: {json.dumps(term_result, indent=2)}")
    
    return response


def main():
    """Run orchestration tests."""
    print("=== Orchestration Plugin Tests ===")
    
    # Test 1: Check initial status
    test_orchestration_status()
    
    # Test 2: Start hello-goodbye orchestration
    test_start_hello_goodbye()
    
    # Test 3: Start debate orchestration
    test_start_debate()
    
    # Final status check
    print("\n=== Final Status Check ===")
    test_orchestration_status()


if __name__ == "__main__":
    main()