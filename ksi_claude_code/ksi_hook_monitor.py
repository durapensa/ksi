#!/usr/bin/env python3
"""
KSI Hook Monitor - Integrates with Claude Code via hooks.
Shows only NEW KSI events since last hook invocation.

Uses smart filtering and silent events to prevent recursive event generation.
For complete documentation, see ksi_hook_monitor_filters.txt in this directory.
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
                socket_path = Path.cwd() / "var/run/daemon.sock"
                if not socket_path.exists():
                    # Try harder - look for var directory
                    for parent in Path.cwd().parents:
                        potential = parent / "var/run/daemon.sock"
                        if potential.exists():
                            socket_path = potential
                            break
        
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
                    "_silent": True,  # Prevent recursive event generation
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
            
        except Exception:
            # Silent fail - daemon might not be running
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
            
            query = {"event": "agent:list", "data": {"_silent": True}}
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
    """Hook entry point - receives tool execution data from Claude Code."""
    # Always write basic debug info to help diagnose issues
    with open("/tmp/ksi_hook_diagnostic.log", "a") as f:
        f.write(f"\n{datetime.now().isoformat()} - Hook triggered\n")
    
    # Optional verbose debug logging (set KSI_HOOK_DEBUG=true to enable)
    debug_log = os.environ.get("KSI_HOOK_DEBUG", "").lower() == "true"
    if debug_log:
        with open("/tmp/ksi_hook_debug.log", "a") as f:
            f.write(f"\n{datetime.now().isoformat()} - Hook started\n")
    
    # Read hook input from stdin
    hook_data = {}
    try:
        stdin_input = sys.stdin.read()
        if stdin_input:
            hook_data = json.loads(stdin_input)
            if debug_log:
                with open("/tmp/ksi_hook_debug.log", "a") as f:
                    f.write(f"Received data: {json.dumps(hook_data, indent=2)}\n")
    except Exception:
        # Silent fail - hooks shouldn't crash Claude Code
        sys.exit(0)
    
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
    
    # Skip if no data received
    if tool_name == "unknown" or not hook_data:
        with open("/tmp/ksi_hook_diagnostic.log", "a") as f:
            f.write(f"  No data received, exiting\n")
        sys.exit(0)
    
    # Write tool info to diagnostic log
    with open("/tmp/ksi_hook_diagnostic.log", "a") as f:
        f.write(f"  Tool: {tool_name}\n")
        if tool_name == "Bash":
            command = hook_data.get("tool_input", {}).get("command", "")
            f.write(f"  Command: {command[:100]}\n")
    
    # Smart filtering for Bash commands - only monitor KSI-related activity
    if tool_name == "Bash":
        command = hook_data.get("tool_input", {}).get("command", "")
        
        # Skip if checking hook logs (avoid recursion)
        if "ksi_hook" in command or "hook_diagnostic.log" in command:
            sys.exit(0)
            
        # Load KSI indicators from external file
        def load_ksi_indicators():
            """Load KSI indicators from external filters file."""
            try:
                # Find the filters file relative to this script
                script_dir = Path(__file__).parent
                # Look in same directory (both hook and filters are in ksi_claude_code)
                filters_file = script_dir / "ksi_hook_monitor_filters.txt"
                
                if not filters_file.exists():
                    # Fallback to inline filters if file not found
                    return [
                        "nc -U var/run/daemon.sock", "./daemon_control.py", "daemon_control.py",
                        "agent:spawn", "agent:", "state:", "entity:", "completion:", "event:",
                        "ksi_", "KSI", "/ksi/", "ksi-", "ksi_check"
                    ]
                
                indicators = []
                with open(filters_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            indicators.append(line)
                return indicators
            except Exception:
                # Fallback to inline filters on any error
                return [
                    "nc -U var/run/daemon.sock", "./daemon_control.py", "daemon_control.py",
                    "agent:spawn", "agent:", "state:", "entity:", "completion:", "event:",
                    "ksi_", "KSI", "/ksi/", "ksi-", "ksi_check"
                ]
        
        ksi_indicators = load_ksi_indicators()
        
        if not any(indicator in command for indicator in ksi_indicators):
            with open("/tmp/ksi_hook_diagnostic.log", "a") as f:
                f.write(f"  Not KSI-related, exiting\n")
            sys.exit(0)  # Skip non-KSI bash commands
        else:
            with open("/tmp/ksi_hook_diagnostic.log", "a") as f:
                f.write(f"  KSI-related command detected!\n")
    
    # Future enhancement: Context-aware monitoring based on recent work
    
    # Initialize monitor
    monitor = KSIHookMonitor()
    
    if debug_log:
        with open("/tmp/ksi_hook_debug.log", "a") as f:
            f.write(f"Monitor initialized\n")
            f.write(f"Socket path: {monitor.socket_path}\n")
            f.write(f"Socket exists: {Path(monitor.socket_path).exists()}\n")
            f.write(f"CWD: {os.getcwd()}\n")
    
    # Get KSI status
    with open("/tmp/ksi_hook_diagnostic.log", "a") as f:
        f.write(f"  Getting KSI status...\n")
    
    try:
        events = monitor.get_recent_events("*", limit=20)  # Get more events to find new ones
        with open("/tmp/ksi_hook_diagnostic.log", "a") as f:
            f.write(f"  Got {len(events) if events else 0} events\n")
        
        event_summary, new_events = monitor.format_event_summary(events)
        with open("/tmp/ksi_hook_diagnostic.log", "a") as f:
            f.write(f"  Formatted events, {len(new_events) if new_events else 0} new\n")
        
        agent_status = monitor.check_active_agents()
        with open("/tmp/ksi_hook_diagnostic.log", "a") as f:
            f.write(f"  Agent status: {agent_status[:50]}...\n")
    except Exception as e:
        with open("/tmp/ksi_hook_diagnostic.log", "a") as f:
            f.write(f"  ERROR getting KSI status: {e}\n")
        # Exit with minimal output if can't connect
        print("\n[KSI - offline]", flush=True)
        sys.exit(0)
    
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
        summary_parts = []
        if new_events:
            summary_parts.append(f"{len(new_events)} events")
        if agent_count > 0:
            summary_parts.append(f"{agent_count} agents")
        # Always show something - even if just [KSI] to show hook is working
        if summary_parts:
            message = f"[KSI: {', '.join(summary_parts)}]"
        else:
            message = "[KSI]"  # Minimal output to confirm hook is active
    else:
        # Detailed mode for errors or significant events
        if new_events or agent_status != "No active agents.":
            message = f"[KSI: {len(new_events)} new]"
            if new_events:
                message += f" {event_summary}"
            if agent_status != "No active agents.":
                message += f" {agent_status}"
        else:
            message = "[KSI]"  # Even in detailed mode, always show something
    
    # stderr + exit code 2 (only method that feeds back to Claude per docs)
    with open("/tmp/ksi_hook_diagnostic.log", "a") as f:
        f.write(f"  Stderr feedback output: {message}\n")
    
    print(message, file=sys.stderr, flush=True)
    sys.exit(2)  # Required for Claude Code to feed stderr back to Claude

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # FAILSAFE: Always exit cleanly and show error
        print(f"[KSI Hook Error] {e}")
        sys.exit(0)