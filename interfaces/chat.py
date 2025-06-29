#!/usr/bin/env python3
"""
Minimal chat interface for Claude via the daemon - Event-Based Protocol
"""

import asyncio
import subprocess
import time
import sys
import os
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the new event-based client
from ksi_client import EventChatClient
from ksi_common.config import config

SOCKET_PATH = os.environ.get('KSI_DAEMON_SOCKET', str(config.socket_path))

def start_daemon():
    """Start daemon if not running"""
    print("Starting daemon...")
    # Properly detach daemon from terminal
    subprocess.Popen(['nohup', 'python3', 'ksi-daemon.py', '--foreground'], 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid)  # Create new process group
    time.sleep(3)  # Give daemon time to start

async def check_daemon_health() -> bool:
    """Check if daemon is healthy using event-based protocol"""
    try:
        async with EventChatClient(socket_path=SOCKET_PATH) as client:
            health = await client.health_check()
            return health.get("status") == "healthy"
    except:
        return False

async def send_cleanup(cleanup_type: str) -> str:
    """Send cleanup command to daemon using event protocol"""
    try:
        async with EventChatClient(socket_path=SOCKET_PATH) as client:
            await client.emit_event("system:cleanup", {"type": cleanup_type})
            return f"Cleanup {cleanup_type} initiated"
    except Exception as e:
        return f"Error: {e}"

async def send_prompt(prompt: str, session_id: str = None) -> tuple:
    """Send prompt to Claude via daemon using event protocol"""
    try:
        async with EventChatClient(socket_path=SOCKET_PATH) as client:
            # Send prompt and get response
            response_text, new_session_id = await client.send_prompt(
                prompt=prompt,
                session_id=session_id,
                model="claude-cli/sonnet"
            )
            
            # Display the result
            print(f"\n{response_text}\n")
            
            return response_text, new_session_id
        
    except Exception as e:
        print(f"\nError: {e}\n")
        return None, None

def get_last_session_id() -> str:
    """Try multiple methods to find last session ID"""
    # Method 1: Check persistent file
    session_file = config.last_session_id_file
    if session_file.exists():
        try:
            session_id = session_file.read_text().strip()
            if session_id:
                return session_id
        except:
            pass
    
    # Method 2: Check latest log file  
    logs_dir = Path('claude_logs')
    if logs_dir.exists():
        try:
            log_files = list(logs_dir.glob('*.jsonl'))
            if log_files:
                # Get most recently modified log file
                latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
                session_id = latest_log.stem
                if session_id and session_id != 'latest':
                    return session_id
        except:
            pass
    
    return None

def save_session_id(session_id: str):
    """Save session ID for next time"""
    if session_id:
        try:
            session_file = config.last_session_id_file
            session_file.parent.mkdir(exist_ok=True)
            session_file.write_text(session_id)
        except:
            pass

async def ensure_daemon_running():
    """Ensure daemon is running, start if needed"""
    # Check if daemon is healthy
    if await check_daemon_health():
        return True
    
    # Try to start daemon
    start_daemon()
    
    # Wait a bit and check again
    await asyncio.sleep(2)
    if await check_daemon_health():
        return True
    
    print("❌ Failed to start daemon")
    return False

async def interactive_chat():
    """Interactive chat mode"""
    print("Claude Chat Interface (Event-Based Protocol)")
    print("Type 'quit' or 'exit' to end, 'new' for new conversation")
    print("-" * 50)
    
    # Ensure daemon is running
    if not await ensure_daemon_running():
        return
    
    # Try to resume last session
    session_id = get_last_session_id()
    if session_id:
        print(f"Resuming session: {session_id}")
    else:
        print("Starting new conversation")
    
    while True:
        try:
            prompt = input("\n> ").strip()
            
            if not prompt:
                continue
                
            if prompt.lower() in ['quit', 'exit', 'q']:
                break
            elif prompt.lower() == 'new':
                session_id = None
                print("Starting new conversation")
                continue
            elif prompt.lower() == 'session':
                print(f"Current session: {session_id or 'None'}")
                continue
            
            # Send prompt and get response
            response, new_session_id = await send_prompt(prompt, session_id)
            
            if new_session_id:
                session_id = new_session_id
                save_session_id(session_id)
                
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Chat with Claude via daemon')
    parser.add_argument('prompt', nargs='?', help='Single prompt to send')
    parser.add_argument('--session', '-s', help='Session ID to use')
    parser.add_argument('--new', action='store_true', help='Start new conversation')
    parser.add_argument('--cleanup', help='Run cleanup operation')
    parser.add_argument('--health', action='store_true', help='Check daemon health')
    
    args = parser.parse_args()
    
    # Handle cleanup
    if args.cleanup:
        result = await send_cleanup(args.cleanup)
        print(result)
        return
    
    # Handle health check
    if args.health:
        healthy = await check_daemon_health()
        if healthy:
            print("✅ Daemon is healthy")
        else:
            print("❌ Daemon is not responding")
        return
    
    # Ensure daemon is running
    if not await ensure_daemon_running():
        return
    
    # Handle single prompt
    if args.prompt:
        session_id = None if args.new else (args.session or get_last_session_id())
        response, new_session_id = await send_prompt(args.prompt, session_id)
        
        if new_session_id:
            save_session_id(new_session_id)
        return
    
    # Interactive mode
    await interactive_chat()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)