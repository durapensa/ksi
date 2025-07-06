#!/usr/bin/env python3
"""
Test injection using the correct conversation session ID.
"""

import subprocess
import os
import glob
import sys
from pathlib import Path
from datetime import datetime

def find_conversation_session_id():
    """Find the current conversation session ID."""
    cwd = os.getcwd()
    encoded_path = cwd.replace('/', '-')
    claude_projects_dir = os.path.expanduser(f"~/.claude/projects/{encoded_path}")
    
    pattern = os.path.join(claude_projects_dir, "*.jsonl")
    files = glob.glob(pattern)
    
    if not files:
        return None
    
    latest_file = max(files, key=os.path.getmtime)
    return Path(latest_file).stem

def test_injection(session_id):
    """Test injection using --resume."""
    
    message = f"\n[KSI Event Injection Test - {datetime.now().strftime('%H:%M:%S')}]\n"
    message += "✅ This message was successfully injected into our conversation!\n"
    message += f"Session ID: {session_id}\n"
    message += "The KSI monitoring integration is working.\n"
    
    print(f"Injecting with session ID: {session_id}")
    
    try:
        result = subprocess.run(
            ["claude", "--resume", session_id, "--print"],
            input=message.encode(),
            capture_output=True,
            text=False,
            cwd=os.getcwd()  # Use current directory
        )
        
        if result.returncode == 0:
            print("✓ Command executed successfully")
            response = result.stdout.decode()
            print(f"Claude acknowledged: {response[:100]}...")
            return True
        else:
            print(f"✗ Command failed with code {result.returncode}")
            stderr = result.stderr.decode()
            print(f"Error: {stderr}")
            
            # If it's a session error, show helpful info
            if "session" in stderr.lower():
                print("\nTroubleshooting:")
                print("1. Make sure you're running from the same directory as the Claude session")
                print("2. The session might have expired - try a fresh message in Claude")
                
            return False
            
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False

def main():
    """Main test function."""
    print("=== Claude Conversation Injection Test ===\n")
    
    # Find session ID
    print("Finding conversation session ID...")
    session_id = find_conversation_session_id()
    
    if not session_id:
        print("\n❌ No conversation session found!")
        print("\nMake sure:")
        print("1. You're running from the KSI project directory")
        print("2. You have an active Claude conversation")
        print("3. The conversation was started from this directory")
        return 1
    
    print(f"✓ Found session: {session_id}\n")
    
    # Test injection
    print("Testing injection...")
    if test_injection(session_id):
        print("\n✅ SUCCESS! Check above for the injected message.")
        print("You should see the test message in our conversation.")
        
        # Show how to use in monitor
        print(f"\nTo use in a monitor:")
        print(f"export CLAUDE_SESSION_ID='{session_id}'")
        print(f"python your_monitor.py")
        
    else:
        print("\n❌ Injection failed")
        print("The session might have expired or changed.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())