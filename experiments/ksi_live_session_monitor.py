#!/usr/bin/env python3
"""
Live session-aware KSI monitor with file watching.
Automatically detects session changes and adapts.
"""

import socket
import json
import subprocess
import time
import sys
import os
import glob
import threading
from datetime import datetime
from pathlib import Path
from collections import deque
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class SessionFileHandler(FileSystemEventHandler):
    """Watch for session file changes."""
    
    def __init__(self, monitor):
        self.monitor = monitor
        self.session_pattern = "statsig.session_id."
        
    def on_created(self, event):
        if not event.is_directory and self.session_pattern in event.src_path:
            print(f"\n🔄 New session file detected: {os.path.basename(event.src_path)}")
            # Give it a moment to be written
            time.sleep(0.5)
            new_session = self.monitor.find_current_session()
            if new_session and new_session != self.monitor.current_session_id:
                self.monitor.current_session_id = new_session
                print(f"✓ Switched to new session: {new_session}")
    
    def on_modified(self, event):
        if not event.is_directory and self.session_pattern in event.src_path:
            # Session file updated (lastUpdate changed)
            pass  # We don't need to react to every update

class LiveSessionKSIMonitor:
    def __init__(self, socket_path="var/run/daemon.sock"):
        self.socket_path = socket_path
        self.sock = None
        self.event_times = deque(maxlen=10)
        self.events_per_minute = 5
        self.current_session_id = None
        self.session_dir = os.path.expanduser("~/.claude/statsig")
        self.observer = None
        self.running = True
        
    def find_current_session(self):
        """Find the most recent session ID."""
        pattern = os.path.join(self.session_dir, "statsig.session_id.*")
        session_files = glob.glob(pattern)
        
        if not session_files:
            return None
            
        latest_file = max(session_files, key=os.path.getmtime)
        
        try:
            with open(latest_file, 'r') as f:
                data = json.load(f)
                return data.get('sessionID')
        except Exception as e:
            print(f"❌ Error reading session: {e}")
            return None
    
    def start_file_watcher(self):
        """Start watching for session file changes."""
        event_handler = SessionFileHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.session_dir, recursive=False)
        self.observer.start()
        print(f"✓ Watching for session changes in {self.session_dir}")
    
    def connect(self):
        """Connect to KSI daemon."""
        try:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.connect(self.socket_path)
            self.sock.setblocking(False)
            print(f"✓ Connected to KSI daemon")
            return True
        except Exception as e:
            print(f"✗ Failed to connect: {e}")
            return False
    
    def subscribe_to_events(self):
        """Subscribe to interesting events."""
        patterns = [
            "completion:result",      # Completion results
            "agent:spawn:success",    # New agents
            "agent:error",           # Errors
            "system:alert"           # System alerts
        ]
        
        cmd = {
            "event": "monitor:subscribe",
            "data": {
                "patterns": patterns,
                "subscriber_id": "live_session_monitor"
            }
        }
        
        self.sock.sendall(json.dumps(cmd).encode() + b'\n')
        print(f"✓ Subscribed to: {', '.join(patterns)}")
    
    def inject_event(self, event):
        """Inject event into current session."""
        if not self.current_session_id:
            return False
            
        # Format based on event type
        event_type = event.get("event", "unknown")
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        message = f"\n[KSI Monitor - {timestamp}] {event_type}\n"
        
        # Custom formatting for different event types
        if event_type == "completion:result":
            data = event.get("data", {})
            message += f"Request: {data.get('request_id', 'unknown')}\n"
            message += f"Session: {data.get('session_id', 'unknown')}\n"
            if 'result' in data:
                result_preview = str(data['result'])[:200]
                message += f"Result: {result_preview}...\n" if len(result_preview) == 200 else f"Result: {result_preview}\n"
                
        elif event_type == "agent:spawn:success":
            data = event.get("data", {})
            message += f"New agent: {data.get('agent_id', 'unknown')}\n"
            message += f"Profile: {data.get('profile', 'unknown')}\n"
            
        elif event_type == "agent:error":
            data = event.get("data", {})
            message += f"⚠️ Agent: {data.get('agent_id', 'unknown')}\n"
            message += f"Error: {data.get('error', 'unknown')}\n"
        
        # Add raw data in collapsed section
        message += "\n<details>\n<summary>Raw Event Data</summary>\n\n```json\n"
        message += json.dumps(event, indent=2)
        message += "\n```\n</details>\n"
        
        try:
            result = subprocess.run(
                ["claude", "--resume", self.current_session_id, "--print"],
                input=message.encode(),
                capture_output=True,
                text=False,
                cwd="/Users/dp/projects/ksi"
            )
            
            if result.returncode == 0:
                print(f"  ✓ Injected {event_type}")
                return True
            else:
                if "session" in result.stderr.decode().lower():
                    print(f"  ✗ Session expired, finding new one...")
                    self.current_session_id = self.find_current_session()
                return False
                
        except Exception as e:
            print(f"  ✗ Injection error: {e}")
            return False
    
    def should_inject(self):
        """Rate limiting."""
        now = time.time()
        while self.event_times and (now - self.event_times[0]) > 60:
            self.event_times.popleft()
        
        if len(self.event_times) >= self.events_per_minute:
            return False
            
        self.event_times.append(now)
        return True
    
    def read_events(self):
        """Read events from socket."""
        import select
        
        buffer = ""
        event_count = 0
        
        while self.running:
            ready = select.select([self.sock], [], [], 0.5)
            if ready[0]:
                try:
                    data = self.sock.recv(4096).decode()
                    if not data:
                        break
                        
                    buffer += data
                    
                    # Process complete lines
                    lines = buffer.split('\n')
                    for line in lines[:-1]:
                        if line.strip():
                            try:
                                event = json.loads(line)
                                event_count += 1
                                
                                event_type = event.get("event", "unknown")
                                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Event #{event_count}: {event_type}")
                                
                                if self.should_inject():
                                    self.inject_event(event)
                                else:
                                    print("  ⚠️ Rate limited")
                                    
                            except json.JSONDecodeError:
                                pass
                    
                    buffer = lines[-1]
                    
                except BlockingIOError:
                    pass
                except Exception as e:
                    print(f"Read error: {e}")
                    break
            
            # Check if we're still running
            if not self.running:
                break
    
    def run(self):
        """Main run loop."""
        print("\n=== Live Session KSI Monitor ===")
        print(f"Session: {self.current_session_id}")
        print(f"Rate limit: {self.events_per_minute} events/minute")
        print("\nMonitoring KSI events...")
        print("Press Ctrl+C to stop\n")
        
        try:
            # Start file watcher
            self.start_file_watcher()
            
            # Subscribe to events
            self.subscribe_to_events()
            
            # Read events
            self.read_events()
            
        except KeyboardInterrupt:
            print("\n\n✓ Stopped by user")
        finally:
            self.running = False
            if self.observer:
                self.observer.stop()
                self.observer.join()
            if self.sock:
                self.sock.close()

def main():
    """Entry point."""
    # Check for watchdog dependency
    try:
        import watchdog
    except ImportError:
        print("❌ This script requires watchdog for file monitoring")
        print("Install with: pip install watchdog")
        return 1
    
    monitor = LiveSessionKSIMonitor()
    
    # Find initial session
    monitor.current_session_id = monitor.find_current_session()
    if not monitor.current_session_id:
        print("❌ No Claude session found")
        print("Start a Claude conversation and try again")
        return 1
    
    # Connect to KSI
    if not monitor.connect():
        print("❌ Cannot connect to KSI daemon")
        return 1
    
    # Run monitor
    monitor.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())