#!/usr/bin/env python3
"""Test socket communication with daemon"""

import socket
import time

def test_with_shutdown():
    """Test with proper shutdown (should work)"""
    print("Testing WITH shutdown...")
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect('sockets/claude_daemon.sock')
    s.send(b'SPAWN:test-with-shutdown\n')
    s.shutdown(socket.SHUT_WR)  # Signal we're done writing
    
    response = b''
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        response += chunk
    
    print(f"Response: {response.decode()}")
    s.close()

def test_without_shutdown():
    """Test without shutdown (will hang)"""
    print("\nTesting WITHOUT shutdown (will hang for 5 seconds)...")
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(5.0)  # 5 second timeout to prevent infinite hang
    s.connect('sockets/claude_daemon.sock')
    s.send(b'SPAWN:test-without-shutdown\n')
    # No shutdown here - this is the problem!
    
    try:
        response = s.recv(4096)
        print(f"Response: {response.decode()}")
    except socket.timeout:
        print("Timed out waiting for response (as expected)")
    
    s.close()

if __name__ == "__main__":
    test_with_shutdown()
    test_without_shutdown()