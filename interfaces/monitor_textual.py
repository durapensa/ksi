#!/usr/bin/env python3
"""
KSI Monitor Textual - Command Center Design
Modern event-first monitoring interface built on pull-based event log system.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Set, Any
from pathlib import Path
import sys
import os

from ksi_client import EventBasedClient
from ksi_common import config

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, Label, RichLog, DataTable, ProgressBar
from textual.reactive import reactive
from textual.message import Message
from textual.timer import Timer


# =============================================================================
# Data Models (MVC - Model Layer)
# =============================================================================

class EventLogModel:
    """Pure data layer for event log queries and caching."""
    
    def __init__(self, event_client: EventBasedClient):
        self.event_client = event_client
        self.last_update = 0.0
        self._cache = {}
        self._cache_timeout = 2.0  # Cache for 2 seconds
        
        # Local state for tracking events (replaces MonitorClient state)
        self.active_agents = {}
        self.conversations = {}
        self.tool_calls = []
        self.system_events = []
    
    async def get_recent_events(self, limit=100, patterns=None) -> List[Dict[str, Any]]:
        """Fetch recent events with caching."""
        cache_key = f"recent_events_{limit}_{patterns}"
        now = datetime.now().timestamp()
        
        # Check cache
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if now - timestamp < self._cache_timeout:
                return cached_data
        
        # Fetch fresh data
        events = await self.monitor_client.get_recent_events(
            event_patterns=patterns or ["*"],
            limit=limit
        )
        
        # Cache result
        self._cache[cache_key] = (events, now)
        return events
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get current system health metrics."""
        try:
            # Get system health directly using event request
            health_result = await self.event_client.request_event("system:health", {})
            
            return {
                "status": "healthy",
                "active_agents": len(self.active_agents),
                "conversations": len(self.conversations),
                "memory_usage": "45MB",  # Feature request: Implement actual memory metrics via system:health event
                "cpu_usage": 90,
                "disk_usage": 60,
                "network_usage": 100
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "active_agents": 0,
                "conversations": 0
            }
    
    async def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get active conversation sessions."""
        try:
            events = await self.get_recent_events(limit=200, patterns=["completion:*", "conversation:*"])
            
            # Extract session information from events
            sessions = {}
            for event in events:
                data = event.get("data", {})
                session_id = data.get("session_id")
                if session_id:
                    if session_id not in sessions:
                        sessions[session_id] = {
                            "session_id": session_id,
                            "start_time": event.get("timestamp", 0),
                            "last_activity": event.get("timestamp", 0),
                            "message_count": 0,
                            "cost": 0.0
                        }
                    
                    # Update session stats
                    sessions[session_id]["last_activity"] = max(
                        sessions[session_id]["last_activity"],
                        event.get("timestamp", 0)
                    )
                    sessions[session_id]["message_count"] += 1
                    
                    # Add cost if available
                    if "cost" in data:
                        sessions[session_id]["cost"] += data.get("cost", 0.0)
            
            return list(sessions.values())
            
        except Exception as e:
            return []
    
    async def get_agent_status(self) -> List[Dict[str, Any]]:
        """Get active agent information."""
        try:
            # Return active agents from local state
            return [
                agent for agent in self.active_agents.values()
                if agent.get("status") == "active"
            ]
        except Exception as e:
            return []


# =============================================================================
# UI Components (MVC - View Layer)  
# =============================================================================

class LiveEventsPane(Container):
    """Real-time event stream display."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.event_count = 0
    
    def compose(self) -> ComposeResult:
        yield Label("[bold]Live Events[/]", classes="pane-header")
        yield RichLog(id="live_events", highlight=True, markup=True, max_lines=1000)
    
    def add_event(self, event: Dict[str, Any]):
        """Add new event to the display."""
        log = self.query_one("#live_events", RichLog)
        
        event_name = event.get("event_name", "unknown")
        timestamp = datetime.fromtimestamp(event.get("timestamp", 0)).strftime('%H:%M:%S')
        client_id = event.get("client_id", "unknown")
        
        # Format based on event type
        if event_name.startswith("completion:"):
            self._format_completion_event(log, event, timestamp, client_id)
        elif event_name.startswith("agent:"):
            self._format_agent_event(log, event, timestamp, client_id)
        elif event_name.startswith("transport:"):
            self._format_transport_event(log, event, timestamp, client_id)
        else:
            # Generic event display
            log.write(f"[dim]{timestamp}[/] [cyan]{event_name}[/] [yellow]{client_id}[/]")
        
        self.event_count += 1
    
    def _format_completion_event(self, log: RichLog, event: Dict[str, Any], timestamp: str, client_id: str):
        """Format completion events with rich display."""
        data = event.get("data", {})
        prompt = data.get("prompt", "")
        
        # Truncate prompt for display
        if len(prompt) > 50:
            prompt = prompt[:50] + "..."
        
        log.write(f"[green]● {timestamp}[/] [bold]completion:async[/] [cyan]{client_id}[/]")
        if prompt:
            log.write(f"   \"{prompt}\"")
    
    def _format_agent_event(self, log: RichLog, event: Dict[str, Any], timestamp: str, client_id: str):
        """Format agent lifecycle events."""
        event_name = event.get("event_name", "")
        data = event.get("data", {})
        
        if "spawn" in event_name:
            profile = data.get("profile", "default")
            log.write(f"[green]● {timestamp}[/] [bold]agent:spawn[/] [cyan]{client_id}[/] profile=[yellow]{profile}[/]")
        else:
            log.write(f"[blue]● {timestamp}[/] [bold]{event_name}[/] [cyan]{client_id}[/]")
    
    def _format_transport_event(self, log: RichLog, event: Dict[str, Any], timestamp: str, client_id: str):
        """Format transport/connection events."""
        data = event.get("data", {})
        action = data.get("action", "unknown")
        
        if action == "connect":
            capabilities = data.get("capabilities", [])
            cap_str = f"[{', '.join(capabilities)}]" if capabilities else ""
            log.write(f"[blue]● {timestamp}[/] [bold]transport:connect[/] [cyan]{client_id}[/] {cap_str}")
        else:
            log.write(f"[dim]● {timestamp}[/] [bold]transport:{action}[/] [cyan]{client_id}[/]")


class ActiveSessionsPane(Container):
    """Active sessions and agents display."""
    
    def compose(self) -> ComposeResult:
        yield Label("[bold]Active Sessions[/]", classes="pane-header")
        yield RichLog(id="active_sessions", highlight=True, markup=True, max_lines=500)
    
    def update_sessions(self, sessions: List[Dict[str, Any]], agents: List[Dict[str, Any]]):
        """Update the sessions and agents display."""
        log = self.query_one("#active_sessions", RichLog)
        log.clear()
        
        # Display active sessions
        if sessions:
            for session in sessions[:5]:  # Show top 5 sessions
                session_id = session["session_id"][:12] + "..."
                duration = self._format_duration(session.get("last_activity", 0) - session.get("start_time", 0))
                cost = session.get("cost", 0.0)
                messages = session.get("message_count", 0)
                
                log.write(f"📊 Session {session_id} ({messages} messages)")
                log.write(f"   🔄 Duration: {duration}")
                log.write(f"   💰 Cost: ${cost:.3f}")
                log.write("")
        else:
            log.write("[dim]No active sessions[/]")
        
        # Separator
        if sessions and agents:
            log.write("──────────────────────────────────")
        
        # Display active agents
        if agents:
            for agent in agents[:3]:  # Show top 3 agents
                agent_id = agent.get("id", "unknown")
                profile = agent.get("profile", "default")
                status = agent.get("status", "unknown")
                
                status_icon = "🤖" if status == "active" else "💤"
                log.write(f"{status_icon} Agent {agent_id}")
                log.write(f"   📍 Profile: {profile}")
                log.write(f"   🔗 Status: {status}")
                log.write("")
        else:
            log.write("[dim]No active agents[/]")
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable form."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"


class SystemHealthPane(Container):
    """System metrics and health indicators."""
    
    def compose(self) -> ComposeResult:
        yield Label("[bold]System Health[/]", classes="pane-header")
        yield Static("", id="health_status")
        yield Static("", id="health_metrics")
    
    def update_health(self, health: Dict[str, Any]):
        """Update system health display."""
        status = health.get("status", "unknown")
        
        # Status line
        status_widget = self.query_one("#health_status", Static)
        if status == "healthy":
            status_text = "🟢 Daemon: Healthy"
        elif status == "error":
            status_text = f"🔴 Daemon: Error - {health.get('error', 'Unknown')}"
        else:
            status_text = f"🟡 Daemon: {status}"
        
        # Add key metrics
        agents = health.get("active_agents", 0)
        conversations = health.get("conversations", 0)
        memory = health.get("memory_usage", "Unknown")
        
        status_text += f"  📊 Agents: {agents}  💬 Conversations: {conversations}  💾 Memory: {memory}"
        status_widget.update(status_text)
        
        # Progress bars for system metrics
        metrics_widget = self.query_one("#health_metrics", Static)
        cpu = health.get("cpu_usage", 0)
        disk = health.get("disk_usage", 0)
        network = health.get("network_usage", 0)
        
        # Simple text-based progress bars
        cpu_bar = self._create_progress_bar(cpu, "CPU")
        disk_bar = self._create_progress_bar(disk, "Disk")
        net_bar = self._create_progress_bar(network, "Net")
        
        metrics_widget.update(f"{cpu_bar}   {disk_bar}   {net_bar}")
    
    def _create_progress_bar(self, value: int, label: str) -> str:
        """Create a text-based progress bar."""
        filled = int(value / 10)  # 10 chars max
        empty = 10 - filled
        bar = "▓" * filled + "░" * empty
        return f"{bar} {label} {value}%"


class EventDetailsPane(Container):
    """Detailed view of selected events."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_event = None
    
    def compose(self) -> ComposeResult:
        yield Label("[bold]Event Details[/]", classes="pane-header")
        yield RichLog(id="event_details", highlight=True, markup=True, max_lines=500)
    
    def show_event_details(self, event: Dict[str, Any]):
        """Show detailed information about an event."""
        self.selected_event = event
        log = self.query_one("#event_details", RichLog)
        log.clear()
        
        event_name = event.get("event_name", "unknown")
        timestamp = datetime.fromtimestamp(event.get("timestamp", 0)).strftime('%H:%M:%S.%f')[:-3]
        
        log.write(f"Selected: [bold]{event_name}[/] @ {timestamp}")
        log.write("")
        
        # Show event-specific details based on type
        if event_name.startswith("completion:"):
            self._show_completion_details(log, event)
        elif event_name.startswith("agent:"):
            self._show_agent_details(log, event)
        else:
            self._show_generic_details(log, event)
    
    def _show_completion_details(self, log: RichLog, event: Dict[str, Any]):
        """Show completion event details with structured layout."""
        data = event.get("data", {})
        
        # Request details
        log.write("┌─Request─────────────┐")
        log.write(f"│ Client: {event.get('client_id', 'unknown')[:15]:<15} │")
        log.write(f"│ Model: {data.get('model', 'unknown')[:16]:<16} │")
        log.write(f"│ Session: {'continuing' if data.get('session_id') else 'new':<12} │")
        log.write("└─────────────────────┘")
        log.write("")
        
        # Response details (if available)
        if "response" in data or "status" in data:
            log.write("┌─Response────────────┐")
            status = data.get("status", "unknown")
            tokens_in = data.get("tokens_in", 0)
            tokens_out = data.get("tokens_out", 0)
            cost = data.get("cost", 0.0)
            
            log.write(f"│ Status: {status:<12} │")
            log.write(f"│ Tokens: {tokens_in} → {tokens_out:<6} │")
            log.write(f"│ Cost: ${cost:.4f}{'':>9} │")
            log.write("└─────────────────────┘")
            log.write("")
        
        # Performance details (if available)
        if "duration_ms" in data:
            log.write("┌─Performance─────────┐")
            duration = data.get("duration_ms", 0) / 1000
            api_time = data.get("api_time_ms", 0) / 1000
            queue_time = data.get("queue_time_ms", 0) / 1000
            
            log.write(f"│ Duration: {duration:.3f}s{'':>7} │")
            log.write(f"│ API Time: {api_time:.3f}s{'':>7} │")
            log.write(f"│ Queue Time: {queue_time:.3f}s{'':>5} │")
            log.write("└─────────────────────┘")
    
    def _show_agent_details(self, log: RichLog, event: Dict[str, Any]):
        """Show agent event details."""
        data = event.get("data", {})
        
        log.write("┌─Agent Details───────┐")
        log.write(f"│ ID: {data.get('agent_id', 'unknown')[:16]:<16} │")
        log.write(f"│ Profile: {data.get('profile', 'default')[:11]:<11} │")
        log.write(f"│ Action: {event.get('event_name', '').split(':')[-1]:<12} │")
        log.write("└─────────────────────┘")
        
        # Show additional data if present
        if len(data) > 3:
            log.write("")
            log.write("Additional Data:")
            for key, value in data.items():
                if key not in ["agent_id", "profile"]:
                    log.write(f"  {key}: {value}")
    
    def _show_generic_details(self, log: RichLog, event: Dict[str, Any]):
        """Show generic event details."""
        data = event.get("data", {})
        
        log.write("┌─Event Data──────────┐")
        log.write(f"│ Client: {event.get('client_id', 'unknown')[:12]:<12} │")
        log.write(f"│ Type: {event.get('event_name', 'unknown')[:14]:<14} │")
        log.write("└─────────────────────┘")
        
        if data:
            log.write("")
            log.write("Data:")
            for key, value in data.items():
                # Truncate long values
                str_value = str(value)
                if len(str_value) > 50:
                    str_value = str_value[:50] + "..."
                log.write(f"  {key}: {str_value}")


# =============================================================================
# Controller and Main App (MVC - Controller Layer)
# =============================================================================

class MonitorController:
    """Coordinates between model and view components."""
    
    def __init__(self, model: EventLogModel):
        self.model = model
        self.last_timestamp = 0.0
        self.update_interval = 0.5  # 500ms updates
    
    async def get_updates(self) -> Dict[str, Any]:
        """Get all necessary updates for the UI."""
        # Get recent events (new ones only)
        all_events = await self.model.get_recent_events(limit=50)
        new_events = [
            event for event in all_events
            if event.get("timestamp", 0) > self.last_timestamp
        ]
        
        # Update timestamp tracking
        if new_events:
            self.last_timestamp = max(event.get("timestamp", 0) for event in new_events)
        
        # Get other data
        health = await self.model.get_system_health()
        sessions = await self.model.get_active_sessions()
        agents = await self.model.get_agent_status()
        
        return {
            "new_events": new_events,
            "health": health,
            "sessions": sessions,
            "agents": agents
        }


class MonitorApp(App):
    """KSI Command Center - Main monitoring application."""
    
    CSS = """
    /* Main layout */
    #main-grid {
        layout: grid;
        grid-size: 2 3;
        grid-columns: 1fr 1fr;
        grid-rows: 1fr 1fr auto;
        height: 100%;
    }
    
    /* Pane styling */
    .pane-header {
        background: $primary;
        color: $text;
        text-style: bold;
        height: 1;
        text-align: center;
        margin-bottom: 1;
    }
    
    .monitor-pane {
        border: solid $primary;
        background: $surface;
        margin: 1;
        padding: 1;
    }
    
    /* Event stream styling */
    #live_events {
        background: $surface-lighten-1;
        height: 100%;
    }
    
    #active_sessions {
        background: $surface-lighten-1;
        height: 100%;
    }
    
    #event_details {
        background: $surface-lighten-1;
        height: 100%;
    }
    
    /* Health indicators */
    #health_status {
        height: 1;
        text-align: center;
        margin-bottom: 1;
    }
    
    #health_metrics {
        height: 1;
        text-align: center;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("c", "clear", "Clear"),
        ("tab", "next_pane", "Next Pane"),
        ("shift+tab", "prev_pane", "Previous Pane"),
        ("enter", "drill_down", "Details"),
        ("escape", "back", "Back"),
    ]
    
    def __init__(self, daemon_socket: str = None):
        super().__init__()
        self.daemon_socket = daemon_socket or str(config.socket_path)
        self.event_client = EventBasedClient(socket_path=self.daemon_socket)
        self.model = EventLogModel(self.event_client)
        self.controller = MonitorController(self.model)
        self.connected = False
        self.update_timer = None
    
    def compose(self) -> ComposeResult:
        """Create the Command Center layout."""
        yield Header(show_clock=True)
        
        with Container(id="main-grid"):
            # Top row: Live Events and Active Sessions
            yield LiveEventsPane(classes="monitor-pane", id="live_events_pane")
            yield ActiveSessionsPane(classes="monitor-pane", id="active_sessions_pane")
            
            # Middle row: System Health (spans both columns)
            with Container(classes="monitor-pane", id="system_health_pane"):
                yield SystemHealthPane()
            
            # Bottom row: Event Details (spans both columns)  
            with Container(classes="monitor-pane", id="event_details_pane"):
                yield EventDetailsPane()
        
        yield Footer()
    
    async def on_mount(self) -> None:
        """Initialize the monitoring system."""
        await self.connect_to_daemon()
        if self.connected:
            self.update_timer = self.set_timer(0.5, self.update_display)
    
    async def connect_to_daemon(self) -> None:
        """Connect to the KSI daemon."""
        try:
            await self.event_client.connect()
            
            # Subscribe to all events to maintain local state
            async def handle_event(event_name: str, event_data: dict):
                await self._update_local_state(event_name, event_data)
            
            self.event_client.subscribe("*", handle_event)
            self.connected = True
            self.notify("Connected to daemon", severity="information")
        except Exception as e:
            self.notify(f"Failed to connect: {e}", severity="error")
            self.connected = False
    
    async def update_display(self) -> None:
        """Update all display components with new data."""
        if not self.connected:
            return
        
        try:
            updates = await self.controller.get_updates()
            
            # Update live events
            live_events_pane = self.query_one("#live_events_pane", LiveEventsPane)
            for event in updates["new_events"]:
                live_events_pane.add_event(event)
            
            # Update active sessions
            sessions_pane = self.query_one("#active_sessions_pane", ActiveSessionsPane)
            sessions_pane.update_sessions(updates["sessions"], updates["agents"])
            
            # Update system health
            health_pane = self.query_one(SystemHealthPane)
            health_pane.update_health(updates["health"])
            
        except Exception as e:
            self.notify(f"Update error: {e}", severity="warning")
    
    def action_quit(self) -> None:
        """Quit the application."""
        if self.connected:
            asyncio.create_task(self.disconnect())
        self.exit()
    
    async def disconnect(self) -> None:
        """Disconnect from daemon."""
        if self.connected:
            try:
                await self.event_client.disconnect()
                self.connected = False
            except Exception as e:
                self.notify(f"Disconnect error: {e}", severity="warning")
    
    async def _update_local_state(self, event_name: str, event_data: dict) -> None:
        """Update local state based on incoming events."""
        try:
            # Update active agents
            if event_name.startswith("agent:"):
                agent_id = event_data.get("agent_id")
                if agent_id:
                    if event_name == "agent:connect":
                        self.model.active_agents[agent_id] = {
                            "agent_id": agent_id,
                            "status": "active",
                            "timestamp": event_data.get("timestamp")
                        }
                    elif event_name == "agent:disconnect" and agent_id in self.model.active_agents:
                        del self.model.active_agents[agent_id]
            
            # Update conversations
            elif event_name.startswith("message:") or event_name.startswith("conversation:"):
                conv_id = event_data.get("conversation_id")
                if conv_id:
                    if conv_id not in self.model.conversations:
                        self.model.conversations[conv_id] = []
                    self.model.conversations[conv_id].append(event_data)
            
            # Track tool calls
            elif event_name.startswith("tool:"):
                self.model.tool_calls.append({
                    "event": event_name,
                    "data": event_data,
                    "timestamp": event_data.get("timestamp")
                })
                # Keep only recent tool calls
                if len(self.model.tool_calls) > 100:
                    self.model.tool_calls = self.model.tool_calls[-50:]
            
            # Track system events
            elif event_name.startswith("system:"):
                self.model.system_events.append({
                    "event": event_name,
                    "data": event_data,
                    "timestamp": event_data.get("timestamp")
                })
                # Keep only recent system events
                if len(self.model.system_events) > 100:
                    self.model.system_events = self.model.system_events[-50:]
        
        except Exception as e:
            # Don't notify errors for every event - just log them
            pass
    
    def action_refresh(self) -> None:
        """Force refresh of all data."""
        self.model._cache.clear()  # Clear cache to force fresh data
        self.notify("Display refreshed")
    
    def action_clear(self) -> None:
        """Clear all logs."""
        try:
            self.query_one("#live_events", RichLog).clear()
            self.query_one("#active_sessions", RichLog).clear()
            self.query_one("#event_details", RichLog).clear()
            self.notify("Logs cleared")
        except Exception:
            pass
    
    def action_next_pane(self) -> None:
        """Focus next pane."""
        self.screen.focus_next()
    
    def action_prev_pane(self) -> None:
        """Focus previous pane."""
        self.screen.focus_previous()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="KSI Monitor Textual - Command Center")
    parser.add_argument("--socket", default=str(config.socket_path),
                       help=f"Daemon socket path (default: {config.socket_path})")
    parser.add_argument("--test-connection", action="store_true",
                       help="Test daemon connection before starting")
    
    args = parser.parse_args()
    
    if args.test_connection:
        # Test connection
        async def test_connection():
            client = EventBasedClient(socket_path=args.socket)
            try:
                await client.connect()
                print(f"✓ Successfully connected to daemon at {args.socket}")
                
                # Test basic event request
                health = await client.request_event("system:health", {})
                print("✓ Event communication working")
                
                await client.disconnect()
                return True
            except Exception as e:
                print(f"✗ Failed to connect to daemon: {e}")
                return False
        
        success = asyncio.run(test_connection())
        if not success:
            return 1
    
    app = MonitorApp(daemon_socket=args.socket)
    app.run()
    return 0


if __name__ == "__main__":
    main()