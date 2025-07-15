#!/usr/bin/env python3
"""
Debug WebSocket Client for KSI
Monitor all events coming through the WebSocket bridge
"""
import asyncio
import websockets
import json
import sys
from datetime import datetime
from pathlib import Path

class DebugWebSocketClient:
    def __init__(self, uri="ws://localhost:8765", log_file="websocket_debug.log"):
        self.uri = uri
        self.client_id = "debug-logger"
        self.log_file = Path(log_file)
        
        # Clear/create log file
        with open(self.log_file, 'w') as f:
            f.write(f"WebSocket Debug Log Started: {datetime.now()}\n")
            f.write("="*80 + "\n")
        
    async def connect_and_monitor(self):
        """Connect to WebSocket bridge and log all events."""
        try:
            self.log(f"Connecting to {self.uri}...")
            async with websockets.connect(self.uri) as websocket:
                self.log("✓ Connected to WebSocket bridge")
                
                # Subscribe to all events
                subscribe_msg = {
                    "event": "monitor:subscribe",
                    "data": {
                        "client_id": self.client_id,
                        "event_patterns": ["*"]  # Monitor all events
                    }
                }
                
                await websocket.send(json.dumps(subscribe_msg))
                self.log("✓ Sent subscription request for all events")
                
                # Listen for events
                self.log("MONITORING ALL WEBSOCKET EVENTS")
                
                async for message in websocket:
                    await self.log_event(message)
                    
        except websockets.exceptions.ConnectionClosed:
            self.log("WebSocket connection closed")
        except KeyboardInterrupt:
            self.log("Stopping monitor...")
        except Exception as e:
            self.log(f"Error: {e}")
    
    def log(self, message):
        """Write message to both file and stdout."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_line = f"{timestamp} {message}\n"
        
        # Write to file
        with open(self.log_file, 'a') as f:
            f.write(log_line)
        
        # Also print to stdout for immediate feedback
        print(f"{timestamp} {message}")
        
    async def log_event(self, message):
        """Log an event with timestamp and formatting."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        try:
            # Parse JSON
            event_data = json.loads(message)
            event_name = event_data.get("event", "NO_EVENT")
            
            # Extract key info for concise display
            data = event_data.get("data", {})
            
            # Special handling for different event types
            if event_name == "agent:terminate":
                terminated = data.get("terminated", [])
                failed = data.get("failed", [])
                summary = f"terminated={len(terminated)}, failed={len(failed)}"
                if terminated:
                    summary += f", agents={terminated[:3]}{'...' if len(terminated) > 3 else ''}"
            elif event_name.startswith("state:entity:"):
                entity_id = data.get("id") or data.get("entity_id", "?")
                entity_type = data.get("type", "?")
                summary = f"id={entity_id}, type={entity_type}"
            elif event_name == "agent:list":
                agents = data.get("agents", [])
                summary = f"count={len(agents)}"
            else:
                # Generic summary - show first few keys
                keys = list(data.keys())[:3]
                summary = f"keys={keys}"
            
            log_line = f"EVENT: {event_name:<25} {summary}"
            self.log(log_line)
            
            # Full data to file for detailed debugging
            with open(self.log_file, 'a') as f:
                f.write(f"  Full data: {json.dumps(event_data, indent=2)}\n")
            
        except json.JSONDecodeError:
            self.log(f"[RAW] {message}")
        except Exception as e:
            self.log(f"[ERROR] Failed to parse: {e}")
            self.log(f"  Raw message: {message}")

async def main():
    client = DebugWebSocketClient()
    await client.connect_and_monitor()

if __name__ == "__main__":
    asyncio.run(main())