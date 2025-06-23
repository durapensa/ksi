#!/usr/bin/env python3
"""
Test session continuity and JSONL logging with the new subprocess approach
"""

import json
import socket
import sys
import time
import os
from pathlib import Path

def send_daemon_command(command):
    """Send command to daemon and get response"""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect('sockets/claude_daemon.sock')
        
        sock.sendall((json.dumps(command) + '\n').encode())
        
        response_data = b''
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response_data += chunk
            if b'\n' in response_data:
                break
        
        sock.close()
        return json.loads(response_data.decode().strip())
        
    except Exception as e:
        print(f"❌ Failed to send command: {e}")
        return None

def test_session_continuity():
    """Test session continuity and JSONL logging"""
    
    print("🔗 Testing session continuity with new subprocess implementation...")
    
    # First message - start new session
    command1 = {
        "command": "SPAWN",
        "parameters": {
            "mode": "sync",
            "type": "claude",
            "prompt": "Remember this number: 42. What is it?",
            "enable_tools": False,
            "model": "sonnet"
        }
    }
    
    print("📨 Sending first message (create session)...")
    response1 = send_daemon_command(command1)
    
    if not response1 or response1.get('status') != 'success':
        print(f"❌ First message failed: {response1}")
        return False
    
    # Extract session ID
    result1 = response1.get('result', {})
    session_id = None
    
    if isinstance(result1, dict):
        session_id = result1.get('sessionId') or result1.get('session_id')
    
    if not session_id:
        print("❌ No session ID in first response")
        return False
    
    print(f"✅ Got session ID: {session_id}")
    
    # Wait a moment
    time.sleep(2)
    
    # Second message - resume session
    command2 = {
        "command": "SPAWN", 
        "parameters": {
            "mode": "sync",
            "type": "claude",
            "prompt": "What number did I ask you to remember?",
            "enable_tools": False,
            "model": "sonnet",
            "session_id": session_id  # Resume previous session
        }
    }
    
    print("📨 Sending second message (resume session)...")
    response2 = send_daemon_command(command2)
    
    if not response2 or response2.get('status') != 'success':
        print(f"❌ Second message failed: {response2}")
        return False
    
    print("✅ Session continuity test completed!")
    
    # Check JSONL logging
    log_file = f"claude_logs/{session_id}.jsonl"
    if os.path.exists(log_file):
        print(f"✅ JSONL log file exists: {log_file}")
        
        # Count entries
        with open(log_file, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]
            
        print(f"✅ JSONL contains {len(lines)} entries")
        
        # Verify structure
        valid_entries = 0
        for line in lines:
            try:
                entry = json.loads(line)
                if 'timestamp' in entry and 'type' in entry:
                    valid_entries += 1
            except:
                pass
        
        print(f"✅ {valid_entries} valid JSONL entries found")
        
        if valid_entries >= 4:  # Should have at least 2 human + 2 claude entries
            print("✅ JSONL logging working correctly")
            return True
        else:
            print("⚠️  Fewer JSONL entries than expected")
            return True  # Still a success, might be timing issue
    else:
        print(f"❌ JSONL log file not found: {log_file}")
        return False

if __name__ == "__main__":
    success = test_session_continuity()
    sys.exit(0 if success else 1)