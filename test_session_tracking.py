#!/usr/bin/env python3
"""
Test session tracking for in-process agents
Verifies that agents maintain conversation continuity via session_id
"""

import json
import socket
import time
import sys

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

def test_session_tracking():
    """Test that agents maintain session continuity"""
    print("🔍 Testing Session Tracking for In-Process Agents")
    print("=" * 50)
    
    # 1. Spawn an agent
    print("\n1. Spawning agent...")
    spawn_resp = send_daemon_command({
        "command": "SPAWN_AGENT",
        "parameters": {
            "task": "Remember a number for me",
            "agent_id": "session_test_agent",
            "profile_name": "conversationalist"
        }
    })
    
    if not spawn_resp or spawn_resp.get('status') != 'success':
        print(f"❌ Failed to spawn agent: {spawn_resp}")
        return False
        
    agent_id = spawn_resp['result']['agent']['id']
    process_id = spawn_resp['result']['agent']['process_id']
    print(f"✅ Agent spawned: {agent_id} (process: {process_id})")
    
    # 2. Send a message to establish session
    print("\n2. Sending initial message to establish session...")
    message1_resp = send_daemon_command({
        "command": "COMPLETION",
        "parameters": {
            "mode": "sync",
            "type": "claude",
            "prompt": "Please remember the number 42 for me. Just acknowledge that you'll remember it.",
            "agent_id": agent_id
        }
    })
    
    if not message1_resp or message1_resp.get('status') != 'success':
        print(f"❌ Failed to send first message: {message1_resp}")
        return False
        
    result1 = message1_resp.get('result', {})
    session_id = result1.get('session_id')
    
    if not session_id:
        print("❌ No session_id returned in first response")
        print(f"   Response: {json.dumps(result1, indent=2)}")
        return False
        
    print(f"✅ Session established: {session_id}")
    print(f"   Claude said: {result1.get('result', '')[:100]}...")
    
    # 3. Wait a moment
    time.sleep(2)
    
    # 4. Send a follow-up message to test continuity
    print("\n3. Testing session continuity...")
    message2_resp = send_daemon_command({
        "command": "COMPLETION",
        "parameters": {
            "mode": "sync",
            "type": "claude",
            "prompt": "What number did I ask you to remember?",
            "agent_id": agent_id  # Don't need session_id when routing through agent
        }
    })
    
    if not message2_resp or message2_resp.get('status') != 'success':
        print(f"❌ Failed to send second message: {message2_resp}")
        return False
        
    result2 = message2_resp.get('result', {})
    response2 = result2.get('result', '')
    
    print(f"✅ Follow-up sent with session {session_id}")
    print(f"   Claude said: {response2[:200]}...")
    
    # 5. Check if Claude remembered the number
    if '42' in response2:
        print("\n✅ Session tracking WORKS! Claude remembered the number 42")
        return True
    else:
        print("\n❌ Session tracking FAILED - Claude didn't remember the number")
        return False

def check_session_logs():
    """Check if session logs are being created"""
    print("\n4. Checking session logs...")
    
    # Get process list to find sessions
    process_resp = send_daemon_command({"command": "GET_PROCESSES"})
    if process_resp and process_resp.get('status') == 'success':
        processes = process_resp.get('result', {}).get('processes', [])
        for proc in processes:
            session_id = proc.get('session_id')
            if session_id:
                print(f"   Found session: {session_id}")
                # Check if log file exists
                import os
                log_file = f"claude_logs/{session_id}.jsonl"
                if os.path.exists(log_file):
                    print(f"   ✅ Log file exists: {log_file}")
                else:
                    print(f"   ❌ Log file missing: {log_file}")

def main():
    """Run session tracking tests"""
    success = test_session_tracking()
    check_session_logs()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ Session tracking verification PASSED")
        return 0
    else:
        print("❌ Session tracking verification FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())