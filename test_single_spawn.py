#!/usr/bin/env python3
"""Test single spawn to debug the issue"""

import socket
import json
import time

def test_single_spawn():
    """Test spawning a single Claude instance"""
    
    command = 'SPAWN:test123:Create a file called test_output.txt with "Hello from spawned Claude"\n'
    
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect('sockets/claude_daemon.sock')
        sock.sendall(command.encode())
        sock.shutdown(socket.SHUT_WR)
        
        print("Command sent, waiting for response...")
        
        # Read response
        response = b''
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        
        print(f"Response received: {len(response)} bytes")
        
        try:
            result = json.loads(response.decode())
            print(json.dumps(result, indent=2))
        except:
            print(f"Raw response: {response.decode()}")
            
    finally:
        sock.close()

if __name__ == "__main__":
    test_single_spawn()