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
        self.mode_file = Path("/tmp/ksi_hook_mode.txt")
        self.last_timestamp = self.load_last_timestamp()
        self.verbosity_mode = self.load_verbosity_mode()
        
    def load_last_timestamp(self):
        """Load the timestamp of the last event we showed."""
        try:
            if self.timestamp_file.exists():
                return float(self.timestamp_file.read_text().strip())
        except:
            pass
        return time.time() - 300  # Default to 5 minutes ago
        
    def load_verbosity_mode(self):
        """Load the current verbosity mode."""
        try:
            if self.mode_file.exists():
                return self.mode_file.read_text().strip()
        except:
            pass
        return "summary"  # Default mode
    
    def save_verbosity_mode(self, mode):
        """Save the verbosity mode for next run."""
        try:
            self.mode_file.write_text(mode)
        except:
            pass
    
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
    
    def _group_repetitive_events(self, events):
        """Group similar events together (not just consecutive)."""
        if not events:
            return []
        
        # Events to group when repetitive
        groupable_patterns = [
            "completion:progress",
            "completion:async", 
            "completion:result",
            "permission:check",
            "capability:check"
        ]
        
        # First pass: separate groupable and non-groupable events
        event_groups = {}
        ordered_events = []
        
        for event in events:
            event_name = event.get("event_name", "unknown")
            is_groupable = any(pattern in event_name for pattern in groupable_patterns)
            
            if is_groupable:
                if event_name not in event_groups:
                    event_groups[event_name] = {
                        "type": event_name,
                        "count": 0,
                        "first_event": None,
                        "first_timestamp": event.get("timestamp", 0),
                        "last_timestamp": event.get("timestamp", 0)
                    }
                
                group = event_groups[event_name]
                group["count"] += 1
                if not group["first_event"]:
                    group["first_event"] = event
                group["last_timestamp"] = event.get("timestamp", 0)
            else:
                # Non-groupable event - keep in order
                ordered_events.append({"type": "single", "event": event, "timestamp": event.get("timestamp", 0)})
        
        # Second pass: merge grouped events with singles, maintaining some chronological order
        # Add groups at the position of their last occurrence
        for event_name, group in event_groups.items():
            if group["count"] > 2:  # Only group if more than 2 occurrences
                ordered_events.append({
                    "type": "group",
                    "group": group,
                    "timestamp": group["last_timestamp"]
                })
            else:
                # Too few to group - add as singles
                for event in events:
                    if event.get("event_name") == event_name:
                        ordered_events.append({"type": "single", "event": event, "timestamp": event.get("timestamp", 0)})
        
        # Sort by timestamp to maintain chronological order
        ordered_events.sort(key=lambda x: x["timestamp"])
        
        # Convert to final format
        final_groups = []
        for item in ordered_events:
            if item["type"] == "single":
                final_groups.append({"type": "single", "event": item["event"]})
            else:
                final_groups.append(item["group"])
        
        return final_groups
    
    def format_event_summary(self, events):
        """Format events for display."""
        # Events are already filtered by the server using 'since' parameter
        if not events:
            return "No new KSI events since last check.", []
        
        # Group repetitive events
        event_groups = self._group_repetitive_events(events)
        
        # Concise event summary
        lines = []
        for group in event_groups[:8]:  # Limit output for token efficiency
            if group["type"] == "single":
                # Single event formatting
                event = group["event"]
                event_name = event.get("event_name", "unknown")
                timestamp = event.get("timestamp", 0)
            else:
                # Grouped events
                event = group["first_event"]
                event_name = group["type"]
                timestamp = group["last_timestamp"]
                count = group["count"]
            
            # Ultra-concise format
            time_str = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S") if timestamp else "?"
            
            # Handle grouped events
            if group["type"] != "single" and group["count"] > 1:
                # Show grouped events concisely
                if "completion:" in event_name:
                    lines.append(f"{time_str} completion:* (×{count})")
                else:
                    lines.append(f"{time_str} {event_name} (×{count})")
            else:
                # Special cases with key info only
                if event_name == "completion:result":
                    session = event.get("data", {}).get("session_id", "?")[:8]
                    # Check if completion was successful
                    data = event.get("data", {})
                    if data.get("result", {}).get("response", {}).get("is_error", False):
                        lines.append(f"{time_str} ✗ completion:{session}")
                    else:
                        lines.append(f"{time_str} ✓ completion:{session}")
                elif event_name == "agent:spawn:success":
                    agent_id = event.get("data", {}).get("agent_id", "?")
                    lines.append(f"{time_str} ✓ spawn:{agent_id}")
                elif event_name == "agent:spawn:failed":
                    lines.append(f"{time_str} ✗ agent:spawn failed")
                elif "error" in event_name:
                    lines.append(f"{time_str} ✗ ERROR:{event_name}")
                elif event_name == "evaluation:prompt":
                    lines.append(f"{time_str} ✓ evaluation:prompt")
                elif event_name == "composition:evaluate":
                    lines.append(f"{time_str} ✓ composition:evaluate")
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
        
        # Check for verbosity control commands
        if command.strip() in ["echo ksi_verbose", "echo ksi_summary", "echo ksi_errors", "echo ksi_silent", "echo ksi_status"]:
            monitor = KSIHookMonitor()
            
            if command.strip() == "echo ksi_verbose":
                monitor.save_verbosity_mode("verbose")
                print("[KSI] Mode: verbose", file=sys.stderr, flush=True)
            elif command.strip() == "echo ksi_summary":
                monitor.save_verbosity_mode("summary")
                print("[KSI] Mode: summary", file=sys.stderr, flush=True)
            elif command.strip() == "echo ksi_errors":
                monitor.save_verbosity_mode("errors")
                print("[KSI] Mode: errors only", file=sys.stderr, flush=True)
            elif command.strip() == "echo ksi_silent":
                monitor.save_verbosity_mode("silent")
                print("[KSI] Mode: silent", file=sys.stderr, flush=True)
            elif command.strip() == "echo ksi_status":
                mode = monitor.verbosity_mode
                print(f"[KSI] Current mode: {mode}", file=sys.stderr, flush=True)
            
            sys.exit(2)  # Exit with stderr feedback
            
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
    
    # Check verbosity mode
    mode = monitor.verbosity_mode
    
    # Silent mode - no output
    if mode == "silent":
        sys.exit(0)
    
    # Determine if we have errors or significant events
    has_errors = any("error" in e.get("event_name", "").lower() for e in new_events)
    has_significant = any(e.get("event_name", "") in ["agent:spawn:success", "completion:result"] for e in new_events)
    
    # Check for active agents
    agent_count = len(agent_status.split(": ")[1].split(", ")) if "Agents[" in agent_status else 0
    
    # Errors mode - only show errors
    if mode == "errors":
        if has_errors:
            error_events = [e for e in new_events if "error" in e.get("event_name", "").lower()]
            message = f"[KSI: {len(error_events)} errors]"
            for event in error_events[:3]:
                event_name = event.get("event_name", "unknown")
                timestamp = event.get("timestamp", 0)
                time_str = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S") if timestamp else "?"
                message += f" {time_str} {event_name}"
        else:
            sys.exit(0)  # No errors, no output in errors mode
    
    # Verbose mode - show everything
    elif mode == "verbose":
        message = f"[KSI: {len(new_events)} new]"
        if new_events:
            message += f" {event_summary}"
        if agent_status != "No active agents.":
            message += f" {agent_status}"
        if not new_events and agent_status == "No active agents.":
            message = "[KSI]"  # Still show something even if nothing happening
    
    # Summary mode (default) - concise
    else:
        summary_parts = []
        if new_events:
            summary_parts.append(f"{len(new_events)} events")
        if agent_count > 0:
            summary_parts.append(f"{agent_count} agents")
        
        # Show errors even in summary mode with indicator
        if has_errors:
            error_count = len([e for e in new_events if "error" in e.get("event_name", "").lower()])
            summary_parts.insert(0, f"✗ {error_count} errors")
        
        # Always show something - even if just [KSI] to show hook is working
        if summary_parts:
            message = f"[KSI: {', '.join(summary_parts)}]"
        else:
            message = "[KSI]"  # Minimal output to confirm hook is active
    
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