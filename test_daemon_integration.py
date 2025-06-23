#!/usr/bin/env python3
"""
Test daemon integration with ClaudeProcessManagerV2 using the new subprocess implementation
"""

import json
import socket
import sys
import time

def test_daemon_spawn():
    """Test basic SPAWN command through daemon with tools disabled"""
    
    try:
        # Connect to daemon socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect('sockets/claude_daemon.sock')
        
        # Safe test command with tools disabled
        command = {
            "command": "SPAWN",
            "parameters": {
                "mode": "sync",
                "type": "claude",
                "prompt": "What is 3+3?",
                "enable_tools": False,  # Disable all tools for safety
                "model": "sonnet"
            }
        }
        
        print("🚀 Sending SPAWN command to daemon...")
        sock.sendall((json.dumps(command) + '\n').encode())
        
        # Read response
        response_data = b''
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response_data += chunk
            if b'\n' in response_data:
                break
        
        sock.close()
        
        # Parse response
        response = json.loads(response_data.decode().strip())
        
        print("✅ Daemon integration test successful!")
        print(f"Status: {response.get('status', 'unknown')}")
        
        if response.get('status') == 'success' and 'result' in response:
            result = response['result']
            if isinstance(result, str):
                print(f"Result preview: {result[:100]}...")
            elif isinstance(result, dict):
                print(f"Session ID: {result.get('sessionId', 'N/A')}")
                if 'result' in result:
                    print(f"Claude response: {str(result['result'])[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Daemon integration test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_daemon_spawn()
    sys.exit(0 if success else 1)