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
import argparse
from pathlib import Path

SOCKET_PATH = os.environ.get('CLAUDE_DAEMON_SOCKET', 'sockets/claude_daemon.sock')

def start_daemon():
    """Start daemon if not running"""
    print("Starting daemon...")
    # Properly detach daemon from terminal
    subprocess.Popen(['nohup', 'python3', 'daemon.py'], 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid)  # Create new process group
    time.sleep(3)  # Give daemon time to start

def send_to_daemon(message):
    """Send message to daemon and get response"""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(SOCKET_PATH)
        # Ensure message ends with newline for daemon's readline()
        if not message.endswith('\n'):
            message += '\n'
        sock.sendall(message.encode())
        sock.shutdown(socket.SHUT_WR)  # Signal end of writing
        
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

def get_last_session_id():
    """Try multiple methods to find last session ID"""
    # Method 1: Check persistent file
    session_file = Path('sockets/last_session_id')
    if session_file.exists():
        try:
            session_id = session_file.read_text().strip()
            if session_id:
                return session_id
        except:
            pass
    
    # Method 2: Scan logs for most recent Claude response
    logs_dir = Path('claude_logs')
    if logs_dir.exists():
        # Get all log files sorted by modification time (newest first)
        log_files = sorted(logs_dir.glob('*.jsonl'), key=lambda p: p.stat().st_mtime, reverse=True)
        
        for log_file in log_files:
            if log_file.name == 'latest.jsonl':
                continue
            
            try:
                # Read last line of file (should be Claude response if conversation happened)
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        last_line = lines[-1]
                        entry = json.loads(last_line)
                        if entry.get('type') == 'claude' and 'session_id' in entry:
                            return entry['session_id']
            except:
                continue
    
    return None

def main():
    """Main chat loop"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Claude Chat Interface')
    parser.add_argument('--new', '-n', action='store_true', 
                       help='Start new session (default: resume last)')
    parser.add_argument('--resume', '-r', metavar='SESSION_ID',
                       help='Resume specific session ID')
    args = parser.parse_args()
    
    print("Claude Chat Interface")
    print("Type 'exit' to quit, '/cleanup <type>' to cleanup (logs, sessions, sockets, all)")
    print("-" * 50)
    
    # Ensure sockets directory exists
    os.makedirs('sockets', exist_ok=True)
    
    start_daemon()
    
    # Determine session ID based on arguments
    session_id = None
    if args.new:
        print("Starting new session...")
        session_id = None
    elif args.resume:
        session_id = args.resume
        print(f"Resuming session: {session_id}")
    else:
        # Default: try to resume last session
        session_id = get_last_session_id()
        if session_id:
            print(f"Resuming last session: {session_id}")
        else:
            print("No previous session found, starting new session...")
    
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