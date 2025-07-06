#!/usr/bin/env python3
"""
Simple KSI Event Monitor - Shows all events without filtering or injection.
Used to test the subscription mechanism.
"""

import socket
import json
import sys
from datetime import datetime

def monitor_events():
    """Monitor all KSI events."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    
    try:
        # Connect
        sock.connect("var/run/daemon.sock")
        print("✓ Connected to KSI daemon")
        
        # Subscribe to all events
        subscribe_cmd = {
            "event": "monitor:subscribe",
            "data": {
                "patterns": ["*"],  # All events
                "subscriber_id": "event_monitor_test"
            }
        }
        
        sock.sendall(json.dumps(subscribe_cmd).encode() + b'\n')
        print("✓ Subscribed to all events")
        print("\nMonitoring events (Ctrl+C to stop)...\n")
        
        # Read events
        buffer = ""
        while True:
            data = sock.recv(4096).decode()
            if not data:
                break
                
            buffer += data
            
            # Process complete lines
            lines = buffer.split('\n')
            for line in lines[:-1]:  # All complete lines
                if line.strip():
                    try:
                        event = json.loads(line)
                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        event_name = event.get("event", "unknown")
                        
                        # Simple display
                        print(f"[{timestamp}] {event_name}")
                        
                        # Show completion:result in detail
                        if event_name == "completion:result":
                            print(f"  → Request: {event.get('data', {}).get('request_id', 'unknown')}")
                            print(f"  → Session: {event.get('data', {}).get('session_id', 'unknown')}")
                            
                    except json.JSONDecodeError as e:
                        print(f"Parse error: {e}")
                        
            # Keep last incomplete line
            buffer = lines[-1]
            
    except KeyboardInterrupt:
        print("\n\n✓ Stopped by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        sock.close()

if __name__ == "__main__":
    monitor_events()