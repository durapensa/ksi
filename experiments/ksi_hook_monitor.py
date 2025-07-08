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
    def __init__(self, socket_path=None):
        # Find socket path - hooks may run from different cwd
        if socket_path is None:
            # Try to find the socket relative to this script
            script_dir = Path(__file__).parent.parent  # ksi project root
            socket_path = script_dir / "var/run/daemon.sock"
            if not socket_path.exists():
                # Fallback to relative path (if running from project root)
                socket_path = "var/run/daemon.sock"
        
        self.socket_path = str(socket_path)
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
            sock.settimeout(2.0)  # Don't hang if daemon is not responding
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
            
        except socket.error as e:
            # Socket connection failed - daemon might not be running
            debug_log = os.environ.get("KSI_HOOK_DEBUG", "").lower() == "true"
            if debug_log:
                with open("/tmp/ksi_hook_debug.log", "a") as f:
                    f.write(f"Socket error: {e} (path: {self.socket_path})\n")
            return []
        except Exception as e:
            debug_log = os.environ.get("KSI_HOOK_DEBUG", "").lower() == "true"
            if debug_log:
                with open("/tmp/ksi_hook_debug.log", "a") as f:
                    f.write(f"Error getting events: {e}\n")
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
    """Hook entry point.
    
    CLAUDE CODE HOOK FORMAT (as of 2025-01):
    The hook receives JSON via stdin with the following structure:
    {
        "tool_name": "Bash",           # Tool that was used
        "session_id": "...",           # Claude Code session ID
        "tool_input": {...},           # Input parameters to the tool
        "tool_response": {...},        # Response from the tool
        "context": {...}               # Additional context
    }
    
    TROUBLESHOOTING:
    If hook is not working:
    1. Check that hook is in .claude/settings.local.json (project-specific)
    2. Verify Python path: use "python3" explicitly to ensure Python 3
    3. Test manually: echo '{"tool_name": "Bash"}' | python3 /path/to/hook.py
    4. Check permissions: Hook file must be readable
    5. Exit code must be 0 for success
    6. Working directory: Hooks run from Claude Code's cwd, not project root
    7. Environment: Hooks don't inherit shell environment (no venv)
    
    KNOWN ISSUES (2025-01):
    - Settings changes require Claude Code restart to take effect
    - If hook stops working, check if Python path changed (python vs python3)
    - Hook may fail silently if socket path is incorrect (we handle this now)
    
    MANUAL TESTING:
    KSI_HOOK_DEBUG=true python3 /path/to/ksi_hook_monitor.py
    Then check /tmp/ksi_hook_debug.log for diagnostics
    
    IMPORTANT: Hooks execute silently unless they print to stdout.
    Output is shown in Claude Code's response AFTER the tool output.
    """
    # Add debug logging for troubleshooting
    debug_log = os.environ.get("KSI_HOOK_DEBUG", "").lower() == "true"
    if debug_log:
        with open("/tmp/ksi_hook_debug.log", "a") as f:
            f.write(f"\n{datetime.now().isoformat()} - Hook started\n")
    
    # Read hook input - be defensive about format
    hook_data = {}
    try:
        stdin_input = sys.stdin.read()
        if stdin_input:
            hook_data = json.loads(stdin_input)
            if debug_log:
                with open("/tmp/ksi_hook_debug.log", "a") as f:
                    f.write(f"Received data: {json.dumps(hook_data, indent=2)}\n")
    except Exception as e:
        if debug_log:
            with open("/tmp/ksi_hook_debug.log", "a") as f:
                f.write(f"Error reading stdin: {e}\n")
        # Don't crash - just continue with empty data
        pass
    
    # Extract context (based on actual hook format)
    tool_name = hook_data.get("tool_name", "unknown")
    session_id = hook_data.get("session_id", "unknown")
    tool_response = hook_data.get("tool_response", {})
    
    # Skip for certain tools to avoid noise
    skip_tools = ["TodoRead", "TodoWrite", "Read"]
    if tool_name in skip_tools:
        if debug_log:
            with open("/tmp/ksi_hook_debug.log", "a") as f:
                f.write(f"Skipping tool: {tool_name}\n")
        sys.exit(0)
    
    # FAILSAFE: Always show something for unknown tool to verify hook is working
    if tool_name == "unknown" or not hook_data:
        print("[KSI Hook] No tool data received - hook is running but may have format issue")
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
            # For debugging: set KSI_HOOK_SHOW_ALL=true to see all commands
            if os.environ.get("KSI_HOOK_SHOW_ALL", "").lower() == "true":
                print(f"[KSI Hook] Non-KSI command: {command[:50]}...")
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
    try:
        main()
    except Exception as e:
        # FAILSAFE: Always exit cleanly and show error
        print(f"[KSI Hook Error] {e}")
        sys.exit(0)