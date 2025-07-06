#!/usr/bin/env python3
"""
KSI Hook Monitor - Integrates with Claude Code via hooks.
Shows only NEW KSI events since last hook invocation.

Features:
- Smart filtering: Only triggers on KSI-related Bash commands
- Summary mode: Shows concise event counts by default
- Detailed mode: Activates for errors or significant events
- Timestamp tracking: Only shows truly new events
- Token efficient: Minimal output to save context

Configuration:
- Registered in .claude/settings.local.json
- Triggers on: Bash|Write|Edit|MultiEdit
- Filters out: non-KSI commands, internal events, recursion

Future enhancements could include:
- Context-aware monitoring based on current work
- Configurable verbosity levels
- Pattern-based event filtering
- Custom event formatters
"""

import sys
import json
import socket
import time
import os
from datetime import datetime
from pathlib import Path

class KSIHookMonitor:
    def __init__(self, socket_path="var/run/daemon.sock"):
        self.socket_path = socket_path
        self.timestamp_file = Path("/tmp/ksi_hook_last_timestamp.txt")
        self.last_timestamp = self.load_last_timestamp()
        
    def load_last_timestamp(self):
        """Load the timestamp of the last event we showed."""
        try:
            if self.timestamp_file.exists():
                return float(self.timestamp_file.read_text().strip())
        except:
            pass
        return time.time() - 300  # Default to 5 minutes ago
        
    def save_last_timestamp(self, timestamp):
        """Save the timestamp for next run."""
        try:
            self.timestamp_file.write_text(str(timestamp))
        except:
            pass
        
    def get_recent_events(self, pattern="*", limit=20):
        """Query recent KSI events since last check."""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)
            
            # Query events since last timestamp using built-in filtering
            query = {
                "event": "monitor:get_events",
                "data": {
                    "event_patterns": [pattern] if pattern != "*" else None,
                    "since": self.last_timestamp,  # Only get events after this timestamp
                    "limit": limit,
                    "reverse": True
                }
            }
            
            sock.sendall(json.dumps(query).encode() + b'\n')
            
            # Read response
            response = ""
            while True:
                data = sock.recv(4096).decode()
                if not data:
                    break
                response += data
                if response.count('{') == response.count('}') and response.count('{') > 0:
                    break
            
            sock.close()
            
            result = json.loads(response)
            return result.get("data", {}).get("events", [])
            
        except Exception as e:
            return []
    
    def format_event_summary(self, events):
        """Format events for display."""
        # Events are already filtered by the server using 'since' parameter
        if not events:
            return "No new KSI events since last check.", []
        
        # Concise event summary
        lines = []
        for event in events[:5]:  # Limit to 5 for token efficiency
            event_name = event.get("event_name", "unknown")
            timestamp = event.get("timestamp", 0)
            
            # Ultra-concise format
            time_str = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S") if timestamp else "?"
            
            # Special cases with key info only
            if event_name == "completion:result":
                session = event.get("data", {}).get("session_id", "?")[:8]
                lines.append(f"{time_str} completion:{session}")
            elif event_name == "agent:spawn:success":
                agent_id = event.get("data", {}).get("agent_id", "?")
                lines.append(f"{time_str} spawn:{agent_id}")
            elif "error" in event_name:
                lines.append(f"{time_str} ERROR:{event_name}")
            else:
                # Skip verbose internal events
                if event_name not in ["hook_event_name:PostToolUse", "permission:check", "capability:check", "sandbox:create", "mcp:config:create"]:
                    lines.append(f"{time_str} {event_name}")
        
        return "\n".join(lines), events
    
    def check_active_agents(self):
        """Check for active agents."""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)
            
            query = {"event": "agent:list", "data": {}}
            sock.sendall(json.dumps(query).encode() + b'\n')
            
            # Read response
            response = ""
            while True:
                data = sock.recv(4096).decode()
                if not data:
                    break
                response += data
                if response.count('{') == response.count('}') and response.count('{') > 0:
                    break
            
            sock.close()
            
            result = json.loads(response)
            agents = result.get("data", {}).get("agents", [])
            
            if agents:
                # Concise agent list
                agent_ids = [a['agent_id'] for a in agents[:3]]
                more = f"+{len(agents)-3}" if len(agents) > 3 else ""
                return f"Agents[{len(agents)}]: {', '.join(agent_ids)}{more}"
            else:
                return "No active agents."
                
        except Exception as e:
            return f"Error checking agents: {e}"

def main():
    """Hook entry point."""
    # Read hook input
    try:
        hook_data = json.load(sys.stdin)
    except:
        hook_data = {}
    
    # Extract context (based on actual hook format)
    tool_name = hook_data.get("tool_name", "unknown")
    session_id = hook_data.get("session_id", "unknown")
    tool_response = hook_data.get("tool_response", {})
    
    # Skip for certain tools to avoid noise
    skip_tools = ["TodoRead", "TodoWrite", "Read"]
    if tool_name in skip_tools:
        sys.exit(0)
    
    # Smart filtering for Bash commands - only monitor KSI-related activity
    if tool_name == "Bash":
        command = hook_data.get("tool_input", {}).get("command", "")
        
        # Skip if checking hook logs (avoid recursion)
        if "experiments/ksi_hook" in command or "hook_diagnostic.log" in command:
            sys.exit(0)
            
        # Only proceed if this is a KSI-related command
        ksi_indicators = [
            "nc -U var/run/daemon.sock",  # Direct socket commands
            "./daemon_control.py",         # Daemon control
            "daemon_control.py",           # Daemon control (any path)
            "agent:spawn", "agent:",       # Agent operations
            "state:", "entity:",           # State operations
            "completion:", "event:",       # Other KSI events
            "ksi_", "KSI",                # KSI scripts/mentions
            "/ksi/", "ksi-"               # KSI paths and tools
        ]
        
        if not any(indicator in command for indicator in ksi_indicators):
            sys.exit(0)  # Skip non-KSI bash commands
    
    # TODO: Future enhancement - Context-aware triggering
    # We could track what the user is working on and adjust monitoring:
    # - If recent commands involve agents → focus on agent events
    # - If working with state/entities → focus on state events
    # - If debugging → show more detailed output
    # - If idle → show only critical events
    # This would require maintaining session context across hook invocations
    
    # Initialize monitor
    monitor = KSIHookMonitor()
    
    # Get KSI status
    events = monitor.get_recent_events("*", limit=20)  # Get more events to find new ones
    event_summary, new_events = monitor.format_event_summary(events)
    agent_status = monitor.check_active_agents()
    
    # Update timestamp if we showed new events
    if new_events:
        # Get the newest timestamp from the new events
        newest_timestamp = max(e.get("timestamp", 0) for e in new_events)
        monitor.save_last_timestamp(newest_timestamp)
    
    # Summary mode by default (for token efficiency)
    # Determine if we need detailed output
    has_errors = any("error" in e.get("event_name", "").lower() for e in new_events)
    has_significant = any(e.get("event_name", "") in ["agent:spawn:success", "completion:result"] for e in new_events)
    
    # Check for active agents
    agent_count = len(agent_status.split(": ")[1].split(", ")) if "Agents[" in agent_status else 0
    
    # Summary mode - ultra concise
    if not has_errors and not has_significant and len(new_events) <= 3:
        if new_events or agent_count > 0:
            summary_parts = []
            if new_events:
                summary_parts.append(f"{len(new_events)} events")
            if agent_count > 0:
                summary_parts.append(f"{agent_count} agents")
            print(f"\n[KSI: {', '.join(summary_parts)}]")
    else:
        # Detailed mode for errors or significant events
        if new_events or agent_status != "No active agents.":
            output = f"\n[KSI: {len(new_events)} new] "
            if new_events:
                output += event_summary
            if agent_status != "No active agents.":
                output += f"\n{agent_status}"
            print(output)
    
    # Success exit
    sys.exit(0)

if __name__ == "__main__":
    main()