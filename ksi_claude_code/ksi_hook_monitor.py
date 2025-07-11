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
import logging
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union
from contextlib import contextmanager
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Add ksi_common directory directly to path to bypass __init__.py
ksi_common_path = str(Path(__file__).parent.parent / "ksi_common")
sys.path.insert(0, ksi_common_path)

# Import sync_client module directly
import sync_client
MinimalSyncClient = sync_client.MinimalSyncClient
KSIConnectionError = sync_client.KSIConnectionError
KSIResponseError = sync_client.KSIResponseError

# =============================================================================
# ERROR HANDLING
# =============================================================================

class HookError(Exception):
    """Base exception for hook-related errors"""
    pass

class ConfigurationError(HookError):
    """Raised for configuration issues"""
    pass

# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class HookConfig:
    """Configuration for KSI hook monitor"""
    socket_path: Optional[str] = None
    timestamp_file: str = "/tmp/ksi_hook_last_timestamp.txt"
    mode_file: str = "/tmp/ksi_hook_mode.txt"
    default_mode: str = "summary"
    event_limit: int = 20
    connection_timeout: float = 2.0
    debug_log: bool = False
    diagnostic_log_path: str = "/tmp/ksi_hook_diagnostic.log"
    debug_log_path: str = "/tmp/ksi_hook_debug.log"
    
    @classmethod
    def from_env(cls) -> 'HookConfig':
        """Load configuration from environment variables"""
        return cls(
            socket_path=os.getenv("KSI_SOCKET_PATH"),
            default_mode=os.getenv("KSI_HOOK_MODE", "summary"),
            event_limit=int(os.getenv("KSI_HOOK_EVENT_LIMIT", "20")),
            connection_timeout=float(os.getenv("KSI_HOOK_TIMEOUT", "2.0")),
            debug_log=os.getenv("KSI_HOOK_DEBUG", "").lower() == "true"
        )

# =============================================================================
# EXIT STRATEGY
# =============================================================================

class ExitStrategy:
    """Manage exit codes based on hook state"""
    SUCCESS = 0
    STDERR_FEEDBACK = 2  # Legacy mode - kept for reference
    
    @staticmethod
    def exit_with_feedback(message: str, is_error: bool = False):
        """Exit with JSON decision format for Claude Code feedback"""
        # Use JSON decision format to provide feedback
        output = {
            "decision": "block",
            "reason": message
        }
        print(json.dumps(output), flush=True)
        sys.exit(ExitStrategy.SUCCESS)
    
    @staticmethod
    def exit_silent():
        """Exit silently with no feedback"""
        sys.exit(ExitStrategy.SUCCESS)

# =============================================================================
# STRUCTURED LOGGING
# =============================================================================

class HookLogger:
    """Structured logging for hook diagnostics"""
    def __init__(self, config: HookConfig):
        self.config = config
        self.diagnostic_log = Path(config.diagnostic_log_path)
        self.debug_log = Path(config.debug_log_path) if config.debug_log else None
        
    def log_diagnostic(self, message: str):
        """Log to diagnostic file"""
        try:
            with open(self.diagnostic_log, "a") as f:
                f.write(f"{datetime.now().isoformat()} - {message}\n")
        except Exception:
            pass  # Silent fail for logging
    
    def log_debug(self, message: str):
        """Log to debug file if debug mode is enabled"""
        if self.debug_log:
            try:
                with open(self.debug_log, "a") as f:
                    f.write(f"{datetime.now().isoformat()} - {message}\n")
            except Exception:
                pass  # Silent fail for logging

# =============================================================================
# MAIN HOOK MONITOR
# =============================================================================

class KSIHookMonitor:
    def __init__(self, config: Optional[HookConfig] = None):
        self.config = config or HookConfig.from_env()
        self.logger = HookLogger(self.config)
        
        # Find socket path if not provided
        if self.config.socket_path is None:
            self.config.socket_path = self._find_socket_path()
        
        self.socket_path = str(self.config.socket_path)
        self.client = MinimalSyncClient(self.socket_path, self.config.connection_timeout)
        
        # State files
        self.timestamp_file = Path(self.config.timestamp_file)
        self.mode_file = Path(self.config.mode_file)
        
        # Load state
        self.last_timestamp = self._load_last_timestamp()
        self.verbosity_mode = self._load_verbosity_mode()
        
    def _find_socket_path(self) -> Path:
        """Find the daemon socket path"""
        # Try to find the socket relative to this script
        script_dir = Path(__file__).parent.parent  # ksi project root
        socket_path = script_dir / "var/run/daemon.sock"
        
        if socket_path.exists():
            return socket_path
            
        # Fallback to relative path (if running from project root)
        socket_path = Path.cwd() / "var/run/daemon.sock"
        if socket_path.exists():
            return socket_path
            
        # Try harder - look for var directory
        for parent in Path.cwd().parents:
            potential = parent / "var/run/daemon.sock"
            if potential.exists():
                return potential
                
        # Default to relative path even if not found
        return Path.cwd() / "var/run/daemon.sock"
        
    def _load_last_timestamp(self) -> float:
        """Load the timestamp of the last event we showed."""
        try:
            if self.timestamp_file.exists():
                return float(self.timestamp_file.read_text().strip())
        except Exception as e:
            self.logger.log_debug(f"Failed to load timestamp: {e}")
        return time.time() - 300  # Default to 5 minutes ago
        
    def _load_verbosity_mode(self) -> str:
        """Load the current verbosity mode."""
        try:
            if self.mode_file.exists():
                mode = self.mode_file.read_text().strip()
                if mode in ["summary", "verbose", "errors", "silent"]:
                    return mode
        except Exception as e:
            self.logger.log_debug(f"Failed to load mode: {e}")
        return self.config.default_mode
    
    def save_verbosity_mode(self, mode: str):
        """Save the verbosity mode for next run."""
        try:
            self.mode_file.write_text(mode)
        except Exception as e:
            self.logger.log_debug(f"Failed to save mode: {e}")
    
    def save_last_timestamp(self, timestamp: float):
        """Save the timestamp for next run."""
        try:
            self.timestamp_file.write_text(str(timestamp))
        except Exception as e:
            self.logger.log_debug(f"Failed to save timestamp: {e}")
        
    def get_recent_events(self, pattern: str = "*", limit: int = None) -> List[Dict[str, Any]]:
        """Query recent KSI events since last check."""
        limit = limit or self.config.event_limit
        
        try:
            data = {
                "_silent": True,  # Prevent recursive event generation
                "event_patterns": [pattern] if pattern != "*" else None,
                "since": self.last_timestamp,  # Only get events after this timestamp
                "limit": limit,
                "reverse": True
            }
            
            result = self.client.send_event("monitor:get_events", data)
            return result.get("events", [])
                
        except KSIConnectionError:
            self.logger.log_diagnostic("Daemon not running or socket not found")
            return []
        except Exception as e:
            self.logger.log_diagnostic(f"Error getting events: {e}")
            return []
    
    def check_active_agents(self) -> str:
        """Check for active agents."""
        try:
            result = self.client.send_event("agent:list", {"_silent": True})
            agents = result.get("agents", [])
            
            if agents:
                # Concise agent list
                agent_ids = [a['agent_id'] for a in agents[:3]]
                more = f"+{len(agents)-3}" if len(agents) > 3 else ""
                return f"Agents[{len(agents)}]: {', '.join(agent_ids)}{more}"
            else:
                return "No active agents."
                    
        except Exception as e:
            self.logger.log_diagnostic(f"Error checking agents: {e}")
            return "No active agents."
    
    def _group_repetitive_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
    
    def format_event_summary(self, events: List[Dict[str, Any]]) -> tuple[str, List[Dict[str, Any]]]:
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
    
    def handle_mode_command(self, command: str) -> bool:
        """Handle verbosity mode commands. Returns True if handled."""
        mode_commands = {
            "echo ksi_verbose": "verbose",
            "echo ksi_summary": "summary", 
            "echo ksi_errors": "errors",
            "echo ksi_silent": "silent",
            "echo ksi_status": None  # Special case - just show status
        }
        
        if command.strip() in mode_commands:
            new_mode = mode_commands[command.strip()]
            
            if new_mode is None:
                # Status command
                ExitStrategy.exit_with_feedback(f"[KSI] Current mode: {self.verbosity_mode}")
            else:
                # Mode change command
                self.save_verbosity_mode(new_mode)
                mode_messages = {
                    "verbose": "[KSI] Mode: verbose",
                    "summary": "[KSI] Mode: summary",
                    "errors": "[KSI] Mode: errors only",
                    "silent": "[KSI] Mode: silent"
                }
                ExitStrategy.exit_with_feedback(mode_messages[new_mode])
            
            return True
        return False
    
    def format_output(self, events: List[Dict[str, Any]], agent_status: str) -> str:
        """Format output based on verbosity mode."""
        event_summary, new_events = self.format_event_summary(events)
        
        # Check verbosity mode
        mode = self.verbosity_mode
        
        # Silent mode - no output
        if mode == "silent":
            return None
        
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
                return message
            else:
                return None  # No errors, no output in errors mode
        
        # Verbose mode - show everything
        elif mode == "verbose":
            message = f"[KSI: {len(new_events)} new]"
            if new_events:
                message += f" {event_summary}"
            if agent_status != "No active agents.":
                message += f" {agent_status}"
            if not new_events and agent_status == "No active agents.":
                message = "[KSI]"  # Still show something even if nothing happening
            return message
        
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
            
            return message
    
    def should_process_command(self, tool_name: str, hook_data: Dict[str, Any]) -> bool:
        """Determine if this command should be processed by the hook."""
        # Skip for certain tools to avoid noise
        skip_tools = ["TodoRead", "TodoWrite", "Read"]
        if tool_name in skip_tools:
            self.logger.log_debug(f"Skipping tool: {tool_name}")
            return False
        
        # Skip if no data received
        if tool_name == "unknown" or not hook_data:
            self.logger.log_diagnostic("No data received, skipping")
            return False
        
        # Smart filtering for Bash commands - only monitor KSI-related activity
        if tool_name == "Bash":
            command = hook_data.get("tool_input", {}).get("command", "")
            
            # Skip if checking hook logs (avoid recursion)
            if "ksi_hook" in command or "hook_diagnostic.log" in command:
                return False
            
            # Check for mode commands first
            if self.handle_mode_command(command):
                return False  # Already handled
            
            # Load KSI indicators
            ksi_indicators = self._load_ksi_indicators()
            
            if not any(indicator in command for indicator in ksi_indicators):
                self.logger.log_diagnostic("Not KSI-related, skipping")
                return False
            else:
                self.logger.log_diagnostic("KSI-related command detected!")
                return True
        
        return True
    
    def _load_ksi_indicators(self) -> List[str]:
        """Load KSI indicators from external filters file."""
        try:
            # Find the filters file relative to this script
            script_dir = Path(__file__).parent
            filters_file = script_dir / "ksi_hook_monitor_filters.txt"
            
            if not filters_file.exists():
                raise FileNotFoundError("Filters file not found")
            
            indicators = []
            with open(filters_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        indicators.append(line)
            return indicators
            
        except Exception as e:
            self.logger.log_debug(f"Failed to load indicators: {e}")
            # Fallback to inline filters on any error
            return [
                "nc -U var/run/daemon.sock", "./daemon_control.py", "daemon_control.py",
                "agent:spawn", "agent:", "state:", "entity:", "completion:", "event:",
                "ksi_", "KSI", "/ksi/", "ksi-", "ksi_check"
            ]

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Hook entry point - receives tool execution data from Claude Code."""
    config = HookConfig.from_env()
    logger = HookLogger(config)
    monitor = None
    
    try:
        # Always write basic debug info to help diagnose issues
        logger.log_diagnostic("Hook triggered")
        
        # Read hook input from stdin
        hook_data = {}
        try:
            stdin_input = sys.stdin.read()
            if stdin_input:
                hook_data = json.loads(stdin_input)
                logger.log_debug(f"Received data: {json.dumps(hook_data, indent=2)}")
        except Exception as e:
            logger.log_diagnostic(f"Failed to parse input: {e}")
            ExitStrategy.exit_silent()
        
        # Extract context (based on actual hook format)
        tool_name = hook_data.get("tool_name", "unknown")
        session_id = hook_data.get("session_id", "unknown")
        tool_response = hook_data.get("tool_response", {})
        
        # Write tool info to diagnostic log
        logger.log_diagnostic(f"Tool: {tool_name}")
        if tool_name == "Bash":
            command = hook_data.get("tool_input", {}).get("command", "")
            logger.log_diagnostic(f"Command: {command[:100]}")
        
        # Initialize monitor
        monitor = KSIHookMonitor(config)
        
        # Check if we should process this command
        if not monitor.should_process_command(tool_name, hook_data):
            ExitStrategy.exit_silent()
        
        # Get KSI status
        logger.log_diagnostic("Getting KSI status...")
        
        try:
            events = monitor.get_recent_events("*", limit=config.event_limit)
            logger.log_diagnostic(f"Got {len(events) if events else 0} events")
            
            agent_status = monitor.check_active_agents()
            logger.log_diagnostic(f"Agent status: {agent_status[:50]}...")
            
        except KSIConnectionError:
            logger.log_diagnostic("Daemon not running")
            # Exit with feedback if can't connect
            ExitStrategy.exit_with_feedback("[KSI - offline]")
        except Exception as e:
            logger.log_diagnostic(f"ERROR getting KSI status: {e}")
            # Exit with feedback on error
            ExitStrategy.exit_with_feedback("[KSI - error]")
        
        # Update timestamp if we showed new events
        if events:
            # Get the newest timestamp from the new events
            newest_timestamp = max(e.get("timestamp", 0) for e in events)
            monitor.save_last_timestamp(newest_timestamp)
        
        # Format output based on mode
        output = monitor.format_output(events, agent_status)
        
        if output:
            logger.log_diagnostic(f"Stderr feedback output: {output}")
            ExitStrategy.exit_with_feedback(output)
        else:
            ExitStrategy.exit_silent()
            
    except Exception as e:
        logger.log_diagnostic(f"Hook error: {e}")
        # FAILSAFE: Always exit cleanly and show error
        ExitStrategy.exit_with_feedback(f"[KSI Hook Error] {e}")

if __name__ == "__main__":
    main()