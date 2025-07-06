#!/usr/bin/env python3
"""
Test direct session resume injection.
"""

import subprocess
import json
import sys
from datetime import datetime

def test_resume_injection(session_id):
    """Test injection using --resume."""
    
    message = f"\n[Test Resume Injection - {datetime.now().strftime('%H:%M:%S')}]\n"
    message += "This message should appear in our current conversation.\n"
    message += f"Session ID: {session_id}\n"
    
    print(f"Attempting to inject with session ID: {session_id}")
    
    try:
        result = subprocess.run(
            ["claude", "--resume", session_id, "--print"],
            input=message.encode(),
            capture_output=True,
            text=False,
            cwd="/Users/dp/projects/ksi"
        )
        
        if result.returncode == 0:
            print("✓ Command executed successfully")
            response = result.stdout.decode()
            print(f"Claude response: {response[:200]}...")
            return True
        else:
            print(f"✗ Command failed with code {result.returncode}")
            print(f"Error: {result.stderr.decode()}")
            return False
            
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False

if __name__ == "__main__":
    # Use the session ID we found
    session_id = "1c5d9e0d-2301-414a-b90b-d738d2311834"
    
    print("Testing resume injection...")
    print(f"Session ID: {session_id}\n")
    
    if test_resume_injection(session_id):
        print("\n✓ Check your Claude interface - the message should appear there!")
    else:
        print("\n✗ Injection failed - check error messages above")