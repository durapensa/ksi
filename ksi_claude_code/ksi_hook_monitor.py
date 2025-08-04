#!/usr/bin/env python3
"""
KSI Hook Monitor - Integrates with Claude Code via hooks.
Shows only NEW KSI events since last hook invocation.

Uses smart filtering and silent events to prevent recursive event generation.
For complete documentation, see ksi_hook_monitor_filters.txt in this directory.
"""

import sys
import json
import time
import os
import subprocess
import asyncio
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple

# Suppress ALL logging before imports
os.environ['KSI_LOG_LEVEL'] = 'ERROR'
os.environ['PYTHONWARNINGS'] = 'ignore'

# Add project root to path for proper imports
ksi_root = str(Path(__file__).parent.parent)
sys.path.insert(0, ksi_root)

# Suppress verbose logging from KSI libraries
import logging
logging.getLogger('ksi').setLevel(logging.ERROR)
logging.getLogger('ksi_client').setLevel(logging.ERROR)
logging.getLogger('ksi_common').setLevel(logging.ERROR)
logging.getLogger('ksi_daemon').setLevel(logging.ERROR)

# Force all loggers to use NullHandler to prevent ANY output
logging.getLogger().handlers = []
null_handler = logging.NullHandler()
logging.getLogger().addHandler(null_handler)

# Disable all existing handlers to prevent any output
for name in ['ksi', 'ksi_client', 'ksi_common', 'ksi_daemon', 'asyncio']:
    logger = logging.getLogger(name)
    logger.handlers = []
    logger.addHandler(null_handler)
    logger.propagate = False

# Redirect stdout during imports to suppress any initialization logging
import io
_original_stdout = sys.stdout
sys.stdout = io.StringIO()

try:
    # Import the same client as KSI CLI uses
    from ksi_client import EventClient
    from ksi_client.exceptions import KSIError, KSIConnectionError, KSIEventError
    from ksi_common.config import config
finally:
    # Restore stdout after imports
    sys.stdout = _original_stdout

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
    timestamp_file: str = str(config.hook_timestamp_file)
    mode_file: str = str(config.hook_mode_file)
    default_mode: str = "summary"
    event_limit: int = 20
    connection_timeout: float = 2.0
    debug_log: bool = False
    diagnostic_log_path: str = str(config.hook_diagnostic_log_path)
    debug_log_path: str = str(config.hook_debug_log_path)
    
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
    
    @staticmethod
    def exit_with_feedback(message: str, is_error: bool = False):
        """Exit with JSON format for Claude Code feedback"""
        # Note: "decision": "block" is required for "reason" to be shown
        # Despite the name, it doesn't actually block tool execution
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
        """Log to diagnostic file - DISABLED for production"""
        pass  # Diagnostic logging disabled
    
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
        
        self.socket_path = Path(self.config.socket_path)
        
        # State files
        self.timestamp_file = Path(self.config.timestamp_file)
        self.mode_file = Path(self.config.mode_file)
        
        # Load state
        self.last_timestamp = self._load_last_timestamp()
        self.verbosity_mode = self._load_verbosity_mode()
    
    async def _send_event_async(self, event_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send an event using EventClient (async)."""
        # Redirect stdout to suppress KSI client logging
        import io
        original_stdout = sys.stdout
        sys.stdout = io.StringIO()  # Capture stdout
        
        try:
            client = EventClient(client_id="ksi-hook", socket_path=self.socket_path)
            async with client:
                result = await client.send_event(event_name, data)
            return result
        finally:
            # Restore stdout
            sys.stdout = original_stdout
    
    def _send_event(self, event_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send an event using EventClient (sync wrapper)."""
        try:
            return asyncio.run(self._send_event_async(event_name, data))
        except Exception as e:
            # Convert async exceptions to sync ones the rest of the code expects
            if "connection" in str(e).lower() or "socket" in str(e).lower():
                raise KSIConnectionError(f"Failed to connect to daemon: {e}")
            else:
                raise KSIError(f"Event send failed: {e}")
        
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
                if mode in ["summary", "verbose", "errors", "silent", "orchestration"]:
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
        
    def get_optimization_status(self, events: List[Dict[str, Any]]) -> Optional[str]:
        """Check for active optimizations from the events we already have."""
        try:
            # Look for optimization:progress events in the events we already fetched
            opt_events = [e for e in events if e.get("event_name", "").startswith("optimization:")]
            
            if opt_events:
                # Look for the most recent optimization:progress event
                progress_events = [e for e in opt_events if e.get("event_name") == "optimization:progress"]
                
                if progress_events:
                    # Get component name from the most recent progress event
                    latest = progress_events[0]
                    opt_data = latest.get("data", {})
                    opt_id = opt_data.get("optimization_id", "")
                    
                    # Try to extract component from optimization_id pattern or other data
                    if "mandatory_json" in str(opt_data).lower():
                        return "Optimizing mandatory_json"
                    elif "claude_code_override" in str(opt_data).lower():
                        return "Optimizing claude_code_override"
                    else:
                        return "Optimizing component"
                
                # Fallback: any optimization event means optimization is active
                return "Optimizing"
            
            return None
            
        except Exception as e:
            self.logger.log_debug(f"Error checking optimization status: {e}")
            return None

    def get_status_consolidated(self, pattern: str = "*", limit: int = None) -> tuple[List[Dict[str, Any]], str, Optional[str]]:
        """Get single event dump and extract all status information from it."""
        limit = limit or self.config.event_limit
        
        try:
            # Single comprehensive event query - get everything since last run
            data = {
                "_silent": True,  # Prevent recursive event generation
                "since": self.last_timestamp,  # Only get events after this timestamp
                "limit": limit * 2,  # Get more events to find agent/optimization info
                "reverse": True
            }
            
            result = self._send_event("monitor:get_events", data)
            events = result.get("events", [])
            
            # Extract agent status from events (no additional queries)
            agent_status = self._extract_agent_status_from_events(events)
            
            # Extract optimization status from events (no additional queries)
            optimization_status = self.get_optimization_status(events)
            
            return events, agent_status, optimization_status
                
        except KSIConnectionError:
            self.logger.log_diagnostic("Daemon not running or socket not found")
            return [], "No active agents.", None
        except Exception as e:
            self.logger.log_diagnostic(f"Error getting consolidated status: {e}")
            return [], "Status error.", None
    
    def _extract_agent_status_from_events(self, events: List[Dict[str, Any]]) -> str:
        """Extract agent status from events without additional queries."""
        try:
            # Look for recent agent:spawn:success events to find active agents
            spawn_events = [e for e in events if e.get("event_name") == "agent:spawn:success"]
            
            if spawn_events:
                # Extract agent IDs from spawn events
                agent_ids = []
                for event in spawn_events[:3]:  # Limit to first 3
                    agent_id = event.get("data", {}).get("agent_id")
                    if agent_id:
                        agent_ids.append(agent_id)
                
                if agent_ids:
                    more = f"+{len(spawn_events)-3}" if len(spawn_events) > 3 else ""
                    return f"Agents[{len(spawn_events)}]: {', '.join(agent_ids)}{more}"
            
            return "No active agents."
            
        except Exception as e:
            self.logger.log_debug(f"Error extracting agent status from events: {e}")
            return "No active agents."
    
    def get_detailed_agent_info(self, agent_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get detailed agent information using agent:info event."""
        detailed_info = {}
        
        for agent_id in agent_ids:
            try:
                result = self._send_event("agent:info", {
                    "_silent": True,
                    "agent_id": agent_id,
                    "include_capabilities": True,
                    "include_identity": True,
                    "include_status": True,
                    "include_metrics": True
                })
                
                if result.get("success", False):
                    detailed_info[agent_id] = result.get("agent_info", {})
                else:
                    self.logger.log_debug(f"Failed to get info for agent {agent_id}: {result.get('error')}")
                    
            except Exception as e:
                self.logger.log_debug(f"Error getting agent info for {agent_id}: {e}")
        
        return detailed_info
    
    def check_claude_processes(self) -> List[Dict[str, Any]]:
        """Check for KSI-spawned claude processes (with ?? TTY)."""
        try:
            # Run ps to find claude processes
            ps_output = subprocess.check_output(['ps', '-ef'], text=True)
            claude_processes = []
            
            for line in ps_output.split('\n'):
                if 'claude' in line and '??' in line:
                    # Parse ps output: UID PID PPID C STIME TTY TIME CMD
                    parts = line.split(None, 7)  # Split on whitespace, max 8 parts
                    if len(parts) >= 8:
                        # Safety check: Never include processes with TTY (Claude Code itself)
                        if parts[5] == '??':
                            claude_processes.append({
                                'pid': parts[1],
                                'ppid': parts[2],
                                'start_time': parts[4],
                                'runtime': parts[6],
                                'cmd': parts[7][:50]  # Truncate command
                            })
            
            return claude_processes
        except Exception as e:
            self.logger.log_debug(f"Error checking claude processes: {e}")
            return []
    
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
                        # Try to get duration from response
                        duration_ms = data.get("result", {}).get("response", {}).get("duration_ms")
                        if duration_ms and self.verbosity_mode == "orchestration":
                            duration_s = duration_ms / 1000
                            lines.append(f"{time_str} ✓ completion:{session} ({duration_s:.1f}s)")
                        else:
                            lines.append(f"{time_str} ✓ completion:{session}")
                elif event_name == "agent:spawn:success":
                    agent_id = event.get("data", {}).get("agent_id", "?")
                    session_id = event.get("data", {}).get("session_id")
                    if session_id and self.verbosity_mode == "orchestration":
                        lines.append(f"{time_str} ✓ spawn:{agent_id} session:{session_id[:8]}")
                    else:
                        lines.append(f"{time_str} ✓ spawn:{agent_id}")
                elif event_name == "agent:spawn:failed":
                    lines.append(f"{time_str} ✗ agent:spawn failed")
                elif "error" in event_name:
                    lines.append(f"{time_str} ✗ ERROR:{event_name}")
                elif event_name == "evaluation:prompt":
                    lines.append(f"{time_str} ✓ evaluation:prompt")
                elif event_name == "composition:evaluate":
                    lines.append(f"{time_str} ✓ composition:evaluate")
                elif event_name == "orchestration:load_pattern":
                    data = event.get("data", {})
                    if isinstance(data.get("pattern"), dict):
                        # Response format with pattern details
                        pattern_name = data["pattern"].get("name", "?")
                        transformer_count = len(data["pattern"].get("transformers", []))
                        lines.append(f"{time_str} ✓ pattern:{pattern_name} ({transformer_count} transformers)")
                    else:
                        # Request format with just pattern name
                        pattern_name = data.get("pattern", "?")
                        lines.append(f"{time_str} pattern:load:{pattern_name}")
                elif event_name.startswith("transformer:"):
                    if "registered" in event_name:
                        source = event.get("data", {}).get("source", "?")
                        target = event.get("data", {}).get("target", "?")
                        # Warn about potentially expensive async transformers
                        if target == "completion:async" and self.verbosity_mode == "orchestration":
                            lines.append(f"{time_str} ⚠️  transformer:{source}→{target} (unbounded)")
                        else:
                            lines.append(f"{time_str} transformer:{source}→{target}")
                    elif "executed" in event_name:
                        # Show transformer execution details
                        data = event.get("data", {})
                        source_event = data.get("source_event", "?")
                        target_event = data.get("target_event", "?")
                        lines.append(f"{time_str} ✓ transformed:{source_event}→{target_event}")
                    else:
                        lines.append(f"{time_str} {event_name}")
                elif event_name == "agent:send_message" and self.verbosity_mode == "orchestration":
                    # Show agent messages in orchestration mode
                    data = event.get("data", {})
                    agent_id = data.get("agent_id", "?")[:12]
                    message = data.get("message", {})
                    content = str(message.get("content", ""))[:50]
                    lines.append(f"{time_str} msg→{agent_id}: {content}...")
                elif event_name == "completion:async" and self.verbosity_mode == "orchestration":
                    # Show completion requests with prompt preview
                    data = event.get("data", {})
                    prompt = str(data.get("prompt", ""))[:60]
                    lines.append(f"{time_str} completion: {prompt}...")
                elif self.verbosity_mode == "orchestration" and any(pattern in event_name for pattern in ["discovery:", "swarm:", "tournament:", "observer:", "pattern:"]):
                    # In orchestration mode, show these events with data preview
                    data_str = str(event.get("data", {}))[:80]
                    lines.append(f"{time_str} {event_name} {data_str}")
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
            "echo ksi_orchestration": "orchestration",
            "echo ksi_status": None  # Special case - just show status
        }
        
        if command.strip() in mode_commands:
            new_mode = mode_commands[command.strip()]
            
            if new_mode is None:
                # Status command - WITHOUT brackets
                ExitStrategy.exit_with_feedback(f"KSI Current mode: {self.verbosity_mode}")
            else:
                # Mode change command - WITHOUT brackets
                self.save_verbosity_mode(new_mode)
                mode_messages = {
                    "verbose": "KSI Mode: verbose",
                    "summary": "KSI Mode: summary",
                    "errors": "KSI Mode: errors only",
                    "silent": "KSI Mode: silent",
                    "orchestration": "KSI Mode: orchestration debug"
                }
                ExitStrategy.exit_with_feedback(mode_messages[new_mode])
            
            return True
        return False
    
    def format_output(self, events: List[Dict[str, Any]], agent_status: str, optimization_status: Optional[str] = None) -> str:
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
        
        # Extract agent IDs for detailed info in enhanced modes
        agent_ids = []
        if "Agents[" in agent_status and agent_count > 0:
            # Extract agent IDs from status string
            agent_part = agent_status.split(": ")[1]
            agent_ids = [aid.strip() for aid in agent_part.replace("+", "").split(",") if aid.strip() and not aid.isdigit()]
        
        # Errors mode - only show errors
        if mode == "errors":
            if has_errors:
                error_events = [e for e in new_events if "error" in e.get("event_name", "").lower()]
                message = f"KSI: {len(error_events)} errors"
                for event in error_events[:3]:
                    event_name = event.get("event_name", "unknown")
                    timestamp = event.get("timestamp", 0)
                    time_str = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S") if timestamp else "?"
                    message += f" {time_str} {event_name}"
                return message
            else:
                return None  # No errors, no output in errors mode
        
        # Verbose mode - show event details with enhanced agent info
        elif mode == "verbose":
            parts = []
            
            # Compact status line
            if new_events:
                parts.append(f"⚡{len(new_events)}")
            if agent_count > 0:
                parts.append(f"🤖{agent_count}")
            if optimization_status:
                parts.append(f"🔧{optimization_status}")
            
            if parts:
                message = f"KSI {' '.join(parts)}"
                # Add the most recent significant event on next line
                if event_summary and event_summary.strip():
                    # Extract just the latest event line
                    latest_event = event_summary.strip().split('\n')[0]
                    message += f"\n{latest_event}"
                
                # Add agent capabilities summary if agents present
                if agent_ids and len(agent_ids) <= 2:  # Only for small numbers
                    try:
                        detailed_info = self.get_detailed_agent_info(agent_ids[:2])
                        for agent_id in agent_ids[:2]:
                            if agent_id in detailed_info:
                                info = detailed_info[agent_id]
                                capabilities = info.get("capabilities", {})
                                active_caps = [k for k, v in capabilities.items() if v]
                                if active_caps:
                                    caps_str = ", ".join(active_caps[:3])
                                    if len(active_caps) > 3:
                                        caps_str += f" +{len(active_caps)-3}"
                                    message += f"\n🔧 {agent_id[:12]}: {caps_str}"
                    except Exception as e:
                        self.logger.log_debug(f"Failed to get detailed agent info in verbose mode: {e}")
            else:
                message = "KSI"
                
            return message
        
        # Orchestration mode - detailed view for debugging with full agent info
        elif mode == "orchestration":
            message = f"KSI: {len(new_events)} events"
            if new_events:
                message += f"\n{event_summary}"
            if agent_count > 0:
                message += f"\nAgents: {agent_count}"
            
            if optimization_status:
                message += f"\nOptimization: {optimization_status}"
                
                # Add detailed agent information
                if agent_ids:
                    try:
                        detailed_info = self.get_detailed_agent_info(agent_ids[:3])
                        for agent_id in agent_ids[:3]:
                            if agent_id in detailed_info:
                                info = detailed_info[agent_id]
                                
                                # Format agent details
                                agent_line = f"\n  {agent_id}"
                                
                                # Add identity if available
                                identity = info.get("identity", {})
                                if identity.get("role"):
                                    agent_line += f" ({identity['role']})"
                                
                                # Add status
                                status = info.get("status", {})
                                if status.get("state"):
                                    agent_line += f" [{status['state']}]"
                                
                                # Add key capabilities
                                capabilities = info.get("capabilities", {})
                                active_caps = [k for k, v in capabilities.items() if v]
                                if active_caps:
                                    caps_preview = ", ".join(active_caps[:2])
                                    if len(active_caps) > 2:
                                        caps_preview += f" +{len(active_caps)-2}"
                                    agent_line += f" - {caps_preview}"
                                
                                message += agent_line
                    except Exception as e:
                        self.logger.log_debug(f"Failed to get detailed agent info in orchestration mode: {e}")
            
            # Check for active claude processes
            claude_processes = self.check_claude_processes()
            if claude_processes:
                message += f"\nClaude processes: {len(claude_processes)}"
                for proc in claude_processes[:2]:  # Show first 2
                    message += f"\n  PID {proc['pid']}: {proc['runtime']} (started {proc['start_time']})"
            
            # Try to detect active pattern from recent events
            pattern_events = [e for e in new_events if any(p in e.get("event_name", "") for p in ["orchestration:load_pattern", "pattern:", "tournament:", "swarm:", "discovery:"])]
            if pattern_events:
                # Try to identify the pattern
                for event in pattern_events:
                    if "load_pattern" in event.get("event_name", ""):
                        data = event.get("data", {})
                        if isinstance(data.get("pattern"), dict):
                            pattern_name = data["pattern"].get("name", "unknown")
                            message += f"\n📋 Pattern: {pattern_name}"
                        elif isinstance(data.get("pattern"), str):
                            message += f"\n📋 Pattern: {data.get('pattern')}"
                        break
            
            return message
        
        # Summary mode (default) - ultra-concise
        else:
            # Build compact status with emojis
            parts = []
            
            # Events with E:
            if new_events:
                parts.append(f"E:{len(new_events)}")
            
            # Agents with A:
            if agent_count > 0:
                parts.append(f"A:{agent_count}")
            
            # Optimization with O:
            if optimization_status:
                parts.append(f"O:{optimization_status.split('(')[0].strip()}")  # Just the component name
                
            # Errors with ERR:
            if has_errors:
                error_count = len([e for e in new_events if "error" in e.get("event_name", "").lower()])
                parts.insert(0, f"ERR:{error_count}")
            
            # Format message
            if parts:
                message = f"KSI {' '.join(parts)}"
            else:
                message = "KSI"  # Minimal output to confirm hook is active
            
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
            
            # Process any command with 'ksi ' to show event status
            # Note: "decision": "block" doesn't actually block execution
            # It just displays the feedback message
            if 'ksi ' in command or command.strip() == "echo ksi_check":
                return True
            
            return False
        
        # Only process Bash commands with KSI indicators
        return False
    
    # Removed _load_ksi_indicators method - no longer using filters file
    # Now using simple 'ksi ' pattern matching directly

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Hook entry point - receives tool execution data from Claude Code."""
    config = HookConfig.from_env()
    logger = HookLogger(config)
    monitor = None
    
    try:
        
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
        
        # Initialize monitor
        monitor = KSIHookMonitor(config)
        
        # Check if we should process this command
        if not monitor.should_process_command(tool_name, hook_data):
            ExitStrategy.exit_silent()
        
        # Get KSI status (consolidated call)
        try:
            events, agent_status, optimization_status = monitor.get_status_consolidated("*", limit=config.event_limit)
            
        except KSIConnectionError:
            logger.log_diagnostic("Daemon not running")
            # Exit with feedback if can't connect - WITHOUT brackets
            ExitStrategy.exit_with_feedback("KSI - offline")
        except Exception as e:
            logger.log_diagnostic(f"ERROR getting KSI status: {e}")
            # Exit with feedback on error - WITHOUT brackets
            ExitStrategy.exit_with_feedback("KSI - error")
        
        # Update timestamp if we showed new events
        if events:
            # Get the newest timestamp from the new events
            newest_timestamp = max(e.get("timestamp", 0) for e in events)
            monitor.save_last_timestamp(newest_timestamp)
        
        # Format output based on mode
        output = monitor.format_output(events, agent_status, optimization_status)
        
        if output:
            ExitStrategy.exit_with_feedback(output)
        else:
            ExitStrategy.exit_silent()
            
    except Exception as e:
        logger.log_diagnostic(f"Hook error: {e}")
        # FAILSAFE: Always exit cleanly and show error - WITHOUT brackets
        ExitStrategy.exit_with_feedback(f"KSI Hook Error: {e}")

if __name__ == "__main__":
    main()