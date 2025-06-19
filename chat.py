#!/usr/bin/env python3
"""
Minimal chat interface for Claude via the daemon
"""

import subprocess
import socket
import time
import sys
import os
import json

SOCKET_PATH = os.environ.get('CLAUDE_DAEMON_SOCKET', 'sockets/claude_daemon.sock')

def start_daemon():
    """Start daemon if not running"""
    try:
        # Check if daemon is running
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(SOCKET_PATH)
        sock.close()
        print("Daemon already running")
    except:
        print("Starting daemon...")
        subprocess.Popen(['uv', 'run', 'python', 'daemon.py'], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
        time.sleep(2)  # Give daemon time to start

def send_to_daemon(message):
    """Send message to daemon and get response"""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(SOCKET_PATH)
        sock.sendall(message.encode())
        
        # Read response
        response = b''
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if b'\n' in response:
                break
        
        return response.decode().strip()
    finally:
        sock.close()

def send_prompt(prompt, session_id=None):
    """Send prompt to Claude via daemon"""
    # Format spawn command
    if session_id:
        command = f"SPAWN:{session_id}:{prompt}"
    else:
        command = f"SPAWN:{prompt}"
    
    # Send to daemon
    response = send_to_daemon(command)
    
    try:
        output = json.loads(response)
        
        # Extract session_id
        new_session_id = output.get('sessionId') or output.get('session_id')
        
        # Display content
        if 'error' in output:
            print(f"\nError: {output['error']}\n")
            return None, None
        elif 'result' in output:
            print(f"\nClaude: {output['result']}\n")
        elif 'content' in output:
            print(f"\nClaude: {output['content']}\n")
        else:
            print(f"\nClaude output: {json.dumps(output, indent=2)}\n")
        
        return output, new_session_id
        
    except json.JSONDecodeError:
        print(f"Non-JSON response: {response}")
        return None, None

def main():
    """Main chat loop"""
    print("Claude Chat Interface")
    print("Type 'exit' to quit")
    print("-" * 50)
    
    # Ensure sockets directory exists
    os.makedirs('sockets', exist_ok=True)
    
    start_daemon()
    
    session_id = None
    
    while True:
        try:
            prompt = input("You: ").strip()
            
            if prompt.lower() == 'exit':
                break
            
            if not prompt:
                continue
                
            output, new_session_id = send_prompt(prompt, session_id)
            
            if new_session_id:
                session_id = new_session_id
                
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == '__main__':
    main()