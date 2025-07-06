#!/usr/bin/env python3
"""
Session-aware KSI Event Monitor that injects into the current Claude conversation.
Uses --resume with discovered session ID instead of --continue.
"""

import socket
import json
import subprocess
import time
import sys
import os
import glob
from datetime import datetime
from pathlib import Path
from collections import deque

class SessionAwareKSIMonitor:
    def __init__(self, socket_path="var/run/daemon.sock"):
        self.socket_path = socket_path
        self.sock = None
        self.event_times = deque(maxlen=10)
        self.events_per_minute = 5
        self.current_session_id = None
        
    def find_current_session(self):
        """Find the current conversation session ID."""
        # Get current directory and encode it
        cwd = os.getcwd()
        encoded_path = cwd.replace('/', '-')
        
        # Build path to conversation files
        claude_projects_dir = os.path.expanduser(f"~/.claude/projects/{encoded_path}")
        
        # Find all .jsonl files
        pattern = os.path.join(claude_projects_dir, "*.jsonl")
        files = glob.glob(pattern)
        
        if not files:
            print(f"❌ No conversation files found in {claude_projects_dir}")
            print("  Make sure you're running from the same directory as your Claude session")
            return None
        
        # Get the most recent file
        latest_file = max(files, key=os.path.getmtime)
        
        # Extract session ID from filename
        session_id = Path(latest_file).stem
        
        # Show session info
        file_age = time.time() - os.path.getmtime(latest_file)
        age_str = f"{int(file_age/60)} minutes" if file_age < 3600 else f"{file_age/3600:.1f} hours"
        
        print(f"✓ Found conversation session: {session_id}")
        print(f"  File: {os.path.basename(latest_file)}")
        print(f"  Age: {age_str}")
        
        return session_id
    
    def connect(self):
        """Connect to KSI daemon socket."""
        try:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.connect(self.socket_path)
            self.sock.setblocking(False)
            print(f"✓ Connected to KSI daemon")
            return True
        except Exception as e:
            print(f"✗ Failed to connect: {e}", file=sys.stderr)
            return False
    
    def subscribe_to_completions(self):
        """Subscribe to completion events."""
        subscribe_cmd = {
            "event": "monitor:subscribe",
            "data": {
                "patterns": ["completion:result"],
                "subscriber_id": "session_aware_monitor"
            }
        }
        
        message = json.dumps(subscribe_cmd) + "\n"
        self.sock.sendall(message.encode())
        print("✓ Subscribed to completion:result events")
    
    def inject_with_resume(self, event):
        """Inject event using --resume with current session ID."""
        if not self.current_session_id:
            print("❌ No session ID available for injection")
            return False
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Format injection message
        message = f"\n[KSI Event - {timestamp}]\n"
        request_id = event.get("data", {}).get("request_id", "unknown")
        session_id = event.get("data", {}).get("session_id", "unknown")
        
        message += f"Completion Result - Request: {request_id}, Session: {session_id}\n"
        message += "```json\n"
        message += json.dumps(event.get("data", {}), indent=2)
        message += "\n```\n"
        
        try:
            # Use --resume with session ID
            result = subprocess.run(
                ["claude", "--resume", self.current_session_id, "--print"],
                input=message.encode(),
                capture_output=True,
                text=False,
                cwd="/Users/dp/projects/ksi"
            )
            
            if result.returncode == 0:
                print(f"✓ Injected via --resume: {request_id}")
                # Show brief acknowledgment
                ack = result.stdout.decode()[:100]
                print(f"  Claude: {ack}...")
                return True
            else:
                error = result.stderr.decode()
                print(f"✗ Injection failed: {error}")
                
                # If session expired, try to find new one
                if "session" in error.lower() or "not found" in error.lower():
                    print("  Attempting to find new session...")
                    self.current_session_id = self.find_current_session()
                    
                return False
                
        except Exception as e:
            print(f"✗ Injection error: {e}", file=sys.stderr)
            return False
    
    def should_inject(self):
        """Rate limiting check."""
        now = time.time()
        # Remove events older than 60 seconds
        while self.event_times and (now - self.event_times[0]) > 60:
            self.event_times.popleft()
        
        if len(self.event_times) >= self.events_per_minute:
            return False
        
        self.event_times.append(now)
        return True
    
    def read_event(self):
        """Read complete JSON event from socket."""
        import select
        
        buffer = ""
        while True:
            ready = select.select([self.sock], [], [], 0.1)
            if ready[0]:
                try:
                    data = self.sock.recv(4096).decode()
                    if not data:
                        return None
                    
                    buffer += data
                    
                    # Process complete lines
                    lines = buffer.split('\n')
                    for i, line in enumerate(lines[:-1]):
                        if line.strip():
                            try:
                                event = json.loads(line)
                                buffer = '\n'.join(lines[i+1:])
                                return event
                            except json.JSONDecodeError:
                                continue
                    
                    if len(buffer) > 10000:
                        buffer = ""
                        
                except BlockingIOError:
                    return None
            else:
                return None
    
    def test_injection(self):
        """Test injection with a simple message."""
        print("\n=== Testing Injection ===")
        
        test_event = {
            "event": "test:injection",
            "data": {
                "message": "Session-aware monitor is active",
                "session_id": self.current_session_id,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        if self.inject_with_resume(test_event):
            print("✓ Test injection successful")
            return True
        else:
            print("✗ Test injection failed")
            return False
    
    def monitor(self):
        """Main monitoring loop."""
        print("\n=== Session-Aware KSI Monitor Started ===")
        print(f"Session ID: {self.current_session_id}")
        print(f"Rate limit: {self.events_per_minute} events/minute")
        print("\nMonitoring for completion:result events...")
        print("Press Ctrl+C to stop\n")
        
        # Test injection first
        if not self.test_injection():
            print("\n⚠️  Test injection failed - monitor may not work properly")
            print("Continue anyway? (y/n): ", end='', flush=True)
            if input().lower() != 'y':
                return
        
        try:
            event_count = 0
            while True:
                event = self.read_event()
                
                if event and event.get("event") == "completion:result":
                    event_count += 1
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Event #{event_count}")
                    
                    if self.should_inject():
                        if self.inject_with_resume(event):
                            print("  ✓ Injected into conversation")
                        else:
                            print("  ✗ Injection failed")
                    else:
                        print("  ⚠️  Rate limited")
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print(f"\n\n✓ Monitor stopped (processed {event_count} events)")
        except Exception as e:
            print(f"\n✗ Monitor error: {e}")
            import traceback
            traceback.print_exc()

def main():
    """Run the session-aware monitor."""
    monitor = SessionAwareKSIMonitor()
    
    # Find current session
    monitor.current_session_id = monitor.find_current_session()
    if not monitor.current_session_id:
        print("\n❌ Cannot proceed without session ID")
        print("\nTry starting a new Claude conversation and run again.")
        return 1
    
    # Connect to daemon
    if not monitor.connect():
        print("\n❌ Failed to connect to KSI daemon")
        print("Check with: ./daemon_control.py status")
        return 1
    
    # Subscribe and monitor
    monitor.subscribe_to_completions()
    monitor.monitor()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())