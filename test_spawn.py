#!/usr/bin/env python3
"""Test spawning claude directly"""

import socket
import json
import time
import subprocess

# Start daemon
daemon = subprocess.Popen(['uv', 'run', 'python', 'daemon.py'])
time.sleep(2)

# Connect and send spawn command
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
try:
    sock.connect('sockets/claude_daemon.sock')
    sock.sendall(b'SPAWN:hello claude, what is 2+2?\n')
    
    # Read response
    response = b''
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        response += chunk
        if b'\n' in response:
            break
    
    print("Response:", response.decode())
    
    # Try to parse as JSON
    try:
        data = json.loads(response.decode().strip())
        print("\nParsed JSON:")
        print(json.dumps(data, indent=2))
    except:
        print("Could not parse as JSON")
        
finally:
    sock.close()
    daemon.terminate()
    daemon.wait()