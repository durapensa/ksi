#!/usr/bin/env python3
"""
Test script for injecting messages into Claude Code session.
This tests the basic mechanism before adding KSI event monitoring.
"""

import subprocess
import json
import time
import sys
from datetime import datetime

def inject_to_claude(message):
    """Inject a message into the current Claude session."""
    try:
        # Run claude --continue --print with the message
        result = subprocess.run(
            ["claude", "--continue", "--print"],
            input=message.encode(),
            capture_output=True,
            text=False,
            cwd="/Users/dp/projects/ksi"
        )
        
        if result.returncode != 0:
            print(f"Error injecting message: {result.stderr.decode()}", file=sys.stderr)
            return False
        
        # Claude's response goes to stdout when using --print
        print(f"Claude acknowledged: {result.stdout.decode()[:100]}...")
        return True
        
    except Exception as e:
        print(f"Exception during injection: {e}", file=sys.stderr)
        return False

def test_simple_injection():
    """Test 1: Simple text injection."""
    print("=== Test 1: Simple Text Injection ===")
    message = "\n[Test Injection] Hello from the monitoring script!\n"
    
    if inject_to_claude(message):
        print("✓ Simple injection successful")
    else:
        print("✗ Simple injection failed")
    
    time.sleep(2)

def test_json_event_injection():
    """Test 2: JSON event injection."""
    print("\n=== Test 2: JSON Event Injection ===")
    
    # Simulate a completion:result event
    event = {
        "event": "completion:result",
        "data": {
            "request_id": "test-request-123",
            "session_id": "test-session-456",
            "result": "This is a simulated agent response",
            "construct_id": "test_agent_1",
            "timestamp": datetime.now().isoformat()
        },
        "correlation_id": "test-correlation",
        "timestamp": time.time()
    }
    
    # Format as we expect to receive from KSI
    message = f"\n[KSI Event Monitor]\n```json\n{json.dumps(event, indent=2)}\n```\n"
    
    if inject_to_claude(message):
        print("✓ JSON event injection successful")
    else:
        print("✗ JSON event injection failed")
    
    time.sleep(2)

def test_multiple_injections():
    """Test 3: Multiple rapid injections with rate limiting."""
    print("\n=== Test 3: Multiple Injections ===")
    
    for i in range(3):
        event = {
            "event": "agent:progress",
            "data": {
                "agent_id": f"test_agent_{i}",
                "message": f"Progress update {i+1}",
                "percent": (i+1) * 33
            },
            "timestamp": time.time()
        }
        
        message = f"\n[KSI Event {i+1}/3]\n```json\n{json.dumps(event, indent=2)}\n```\n"
        
        print(f"Injecting event {i+1}...")
        if inject_to_claude(message):
            print(f"✓ Event {i+1} injected")
        else:
            print(f"✗ Event {i+1} failed")
        
        # Rate limit
        time.sleep(3)

def test_error_event():
    """Test 4: Error event injection."""
    print("\n=== Test 4: Error Event Injection ===")
    
    error_event = {
        "event": "agent:error",
        "data": {
            "agent_id": "failing_agent",
            "error": "Connection timeout",
            "context": {
                "operation": "completion:async",
                "retry_count": 3
            }
        },
        "severity": "warning",
        "timestamp": time.time()
    }
    
    message = f"\n[KSI Error Event]\n```json\n{json.dumps(error_event, indent=2)}\n```\n"
    
    if inject_to_claude(message):
        print("✓ Error event injection successful")
    else:
        print("✗ Error event injection failed")

def main():
    """Run all injection tests."""
    print("Starting Claude injection tests...")
    print("This will inject test messages into the current Claude session.")
    print("You should see the injected content appear in your Claude interface.\n")
    
    # Wait a moment for user to be ready
    print("Starting in 3 seconds...")
    time.sleep(3)
    
    # Run tests
    test_simple_injection()
    test_json_event_injection()
    test_multiple_injections()
    test_error_event()
    
    print("\n=== All Tests Complete ===")
    print("Check your Claude interface for the injected messages.")
    print("\nIf injections worked, you should see:")
    print("- A simple text message")
    print("- A JSON completion event")
    print("- Three progress events")
    print("- An error event")

if __name__ == "__main__":
    main()