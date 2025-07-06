#!/usr/bin/env python3
"""
KSI Completion Monitor - Injects completion:result events into Claude Code session.
"""

import socket
import json
import subprocess
import time
import sys
import select
from datetime import datetime
from collections import deque

class KSICompletionMonitor:
    def __init__(self, socket_path="var/run/daemon.sock"):
        self.socket_path = socket_path
        self.sock = None
        self.event_times = deque(maxlen=10)  # Track last 10 events for rate limiting
        self.events_per_minute = 5  # Max events to inject per minute
        
    def connect(self):
        """Connect to KSI daemon socket."""
        try:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.connect(self.socket_path)
            self.sock.setblocking(False)  # Non-blocking for select()
            print(f"✓ Connected to KSI daemon at {self.socket_path}")
            return True
        except Exception as e:
            print(f"✗ Failed to connect: {e}", file=sys.stderr)
            return False
    
    def subscribe_to_completions(self):
        """Subscribe to completion events via monitor:subscribe."""
        subscribe_cmd = {
            "event": "monitor:subscribe",
            "data": {
                "patterns": ["completion:result"],
                "subscriber_id": "claude_completion_monitor"
            }
        }
        
        message = json.dumps(subscribe_cmd) + "\n"
        self.sock.sendall(message.encode())
        print("✓ Subscribed to completion:result events")
    
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
    
    def inject_to_claude(self, event):
        """Inject event into Claude session."""
        # Format the event for clarity
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Extract key information
        request_id = event.get("data", {}).get("request_id", "unknown")
        session_id = event.get("data", {}).get("session_id", "unknown") 
        
        message = f"\n[KSI Completion Monitor - {timestamp}]\n"
        message += f"Request: {request_id}\n"
        message += f"Session: {session_id}\n"
        message += "```json\n"
        message += json.dumps(event, indent=2)
        message += "\n```\n"
        
        try:
            result = subprocess.run(
                ["claude", "--continue", "--print"],
                input=message.encode(),
                capture_output=True,
                text=False,
                cwd="/Users/dp/projects/ksi"
            )
            
            if result.returncode == 0:
                print(f"✓ Injected completion event: {request_id}")
                return True
            else:
                print(f"✗ Failed to inject: {result.stderr.decode()}", file=sys.stderr)
                return False
                
        except Exception as e:
            print(f"✗ Injection error: {e}", file=sys.stderr)
            return False
    
    def read_event(self):
        """Read a complete JSON event from socket."""
        # This is tricky because we need to read complete JSON objects
        # Events are newline-delimited JSON
        buffer = ""
        
        while True:
            ready = select.select([self.sock], [], [], 0.1)
            if ready[0]:
                try:
                    data = self.sock.recv(4096).decode()
                    if not data:
                        return None
                    
                    buffer += data
                    
                    # Check if we have a complete JSON object
                    lines = buffer.split('\n')
                    for i, line in enumerate(lines[:-1]):  # All but last (might be incomplete)
                        if line.strip():
                            try:
                                event = json.loads(line)
                                # Remove processed lines from buffer
                                buffer = '\n'.join(lines[i+1:])
                                return event
                            except json.JSONDecodeError:
                                continue
                    
                    # If buffer is too large, clear it
                    if len(buffer) > 10000:
                        buffer = ""
                        
                except BlockingIOError:
                    return None
            else:
                return None
    
    def monitor(self):
        """Main monitoring loop."""
        print("\n=== KSI Completion Monitor Started ===")
        print(f"Rate limit: {self.events_per_minute} events/minute")
        print("Monitoring for completion:result events...")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                event = self.read_event()
                
                if event:
                    # Check if it's a completion:result event
                    if event.get("event") == "completion:result":
                        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Completion detected!")
                        
                        if self.should_inject():
                            self.inject_to_claude(event)
                        else:
                            print("⚠️  Rate limit reached, skipping injection")
                
                # Small sleep to prevent CPU spinning
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n\n✓ Monitor stopped by user")
        except Exception as e:
            print(f"\n✗ Monitor error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

def main():
    """Run the completion monitor."""
    monitor = KSICompletionMonitor()
    
    # Connect to daemon
    if not monitor.connect():
        print("Failed to connect to KSI daemon. Is it running?")
        print("Check with: ./daemon_control.py status")
        return 1
    
    # Subscribe to events
    monitor.subscribe_to_completions()
    
    # Start monitoring
    monitor.monitor()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())