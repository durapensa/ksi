#!/usr/bin/env python3
"""
Minimal KSI monitor to test injection of a single event.
"""

import os
import sys
import subprocess
import json
from datetime import datetime

def inject_test_event(session_id):
    """Inject a test event."""
    
    # Create a fake completion event
    test_event = {
        "event": "completion:result",
        "data": {
            "request_id": "test-123",
            "session_id": "agent-session-456",
            "result": "This is a test completion from the minimal monitor",
            "construct_id": "test_agent",
            "timestamp": datetime.now().isoformat()
        }
    }
    
    message = f"\n[KSI Monitor Test - {datetime.now().strftime('%H:%M:%S')}]\n"
    message += "Test Event Injected:\n"
    message += "```json\n"
    message += json.dumps(test_event, indent=2)
    message += "\n```\n"
    
    print(f"Injecting test event with session: {session_id}")
    
    result = subprocess.run(
        ["claude", "--resume", session_id, "--print"],
        input=message.encode(),
        capture_output=True,
        text=False,
        cwd=os.getcwd()
    )
    
    if result.returncode == 0:
        print("✓ Injection successful")
        return True
    else:
        print(f"✗ Injection failed: {result.stderr.decode()}")
        return False

def main():
    # Get session ID from environment or find it
    session_id = os.environ.get('CLAUDE_SESSION_ID')
    
    if not session_id:
        print("❌ No CLAUDE_SESSION_ID environment variable")
        print("Run: export CLAUDE_SESSION_ID=$(./experiments/find_sid.sh)")
        return 1
    
    print(f"Using session ID: {session_id}")
    
    # Inject test event
    if inject_test_event(session_id):
        print("\n✓ Test complete - check your Claude interface")
    else:
        print("\n✗ Test failed")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())