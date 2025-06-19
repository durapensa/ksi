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
        subprocess.Popen(['python3', 'daemon.py'], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
        time.sleep(2)  # Give daemon time to start

def send_prompt(prompt, session_id=None):
    """Send prompt to Claude via daemon"""
    # Build command
    cmd_parts = [
        'echo', f'"{prompt}"', '|',
        'claude', '--model', 'sonnet', '--print', '--output-format', 'json',
        '--allowedTools', '"Task Bash Glob Grep LS Read Edit MultiEdit Write WebFetch WebSearch"'
    ]
    
    if session_id:
        cmd_parts.extend(['--resume', session_id])
    
    # Just tee output to file
    cmd_parts.extend(['|', 'tee', 'sockets/claude_last_output.json'])
    
    cmd = ' '.join(cmd_parts)
    
    # Execute
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return None, None
    
    # Read the tee'd output
    try:
        with open('sockets/claude_last_output.json', 'r') as f:
            output = json.load(f)
        
        session_id = output.get('sessionId')
        
        # Extract message content
        if 'messages' in output:
            for msg in output['messages']:
                if msg.get('role') == 'assistant':
                    print(f"\nClaude: {msg.get('content', '')}\n")
        else:
            # Handle different output format
            content = output.get('content', '')
            if content:
                print(f"\nClaude: {content}\n")
            else:
                print(f"\nClaude output: {json.dumps(output, indent=2)}\n")
            
        return output, session_id
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error reading output: {e}")
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