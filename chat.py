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
    print("Starting daemon...")
    # Properly detach daemon from terminal
    subprocess.Popen(['nohup', 'python', 'daemon.py'], 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid)  # Create new process group
    time.sleep(3)  # Give daemon time to start

def send_to_daemon(message):
    """Send message to daemon and get response"""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(SOCKET_PATH)
        sock.sendall(message.encode())
        
        # Read response until connection closes
        response = b''
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        
        return response.decode().strip()
    finally:
        sock.close()

def send_cleanup(cleanup_type):
    """Send cleanup command to daemon"""
    command = f"CLEANUP:{cleanup_type}"
    response = send_to_daemon(command)
    return response

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
        
        # Display only the result content
        if 'error' in output:
            print(f"\nError: {output['error']}\n")
            return None, None
        elif 'result' in output:
            print(f"\n{output['result']}\n")
        elif 'content' in output:
            print(f"\n{output['content']}\n")
        else:
            print(f"\nNo result content found\n")
        
        return output, new_session_id
        
    except json.JSONDecodeError:
        print(f"Non-JSON response: {response}")
        return None, None

def main():
    """Main chat loop"""
    print("Claude Chat Interface")
    print("Type 'exit' to quit, '/cleanup <type>' to cleanup (logs, sessions, sockets, all)")
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
            
            # Handle cleanup commands
            if prompt.startswith('/cleanup '):
                cleanup_type = prompt[9:].strip()
                if cleanup_type in ['logs', 'sessions', 'sockets', 'all']:
                    result = send_cleanup(cleanup_type)
                    print(f"\nCleanup result: {result}\n")
                else:
                    print("\nInvalid cleanup type. Use: logs, sessions, sockets, or all\n")
                continue
                
            output, new_session_id = send_prompt(prompt, session_id)
            
            if new_session_id:
                session_id = new_session_id
                
        except EOFError:
            print("\nNo input available, exiting...")
            break
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == '__main__':
    main()