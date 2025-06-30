#!/usr/bin/env python3
"""
Multi-Claude Conversation Monitor - Textual TUI for real-time observation
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Set, Any
from pathlib import Path
import re
import sys
import os
import logging

from ksi_client import EventBasedClient
from ksi_common import config

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, Label, Tree, DataTable, RichLog, Sparkline
from textual.reactive import reactive
from textual.message import Message
from textual import events
from textual.timer import Timer


class MessageEvent(Message):
    """Custom message event for daemon updates"""
    def __init__(self, data: dict) -> None:
        self.data = data
        super().__init__()


class ConversationView(ScrollableContainer):
    """Main conversation timeline view"""
    
    def compose(self) -> ComposeResult:
        yield RichLog(id="conversation_log", highlight=True, markup=True)


class AgentTreeView(Container):
    """Active agents tree view"""
    
    def compose(self) -> ComposeResult:
        tree = Tree("Active Agents", id="agent_tree")
        tree.root.expand()
        yield tree


class MetricsView(Static):
    """System metrics status line"""
    
    def __init__(self):
        super().__init__("Tokens: 0 | Cost: $0.00 | Msg/min: 0 | Active: 0", id="status-line")


class ToolCallsView(Container):
    """Tool calls inspector"""
    
    def compose(self) -> ComposeResult:
        yield RichLog(id="tool_log", highlight=True, markup=True)


class EventStreamView(Container):
    """Raw event stream for debugging"""
    
    def compose(self) -> ComposeResult:
        yield RichLog(id="event_log", highlight=True, markup=True, max_lines=1000)




class MultiClaudeMonitor(App):
    """TUI Monitor for Multi-Claude Conversations"""
    
    CSS = """
    /* Main container layout */
    #main-container {
        layout: vertical;
        height: 100%;
    }
    
    /* Content area grid */
    #content-grid {
        layout: grid;
        grid-size: 3 1;
        grid-columns: 1fr 4fr 2fr;
        height: 1fr;
    }
    
    /* Footer container for 2-line footer */
    #footer-container {
        layout: vertical;
        height: 2;
        dock: bottom;
    }
    
    /* Status line (first line of footer) */
    #status-line {
        height: 1;
        background: $surface;
        color: $text-muted;
        text-align: center;
        border-top: solid $primary;
    }
    
    /* Custom footer (second line with shortcuts) */
    #custom-footer {
        height: 1;
        background: $primary;
        color: $text;
        text-align: center;
        padding: 0 1;
    }
    
    /* Sidebar styling */
    #sidebar_left {
        border: solid $primary;
        overflow-y: scroll;
        padding: 1;
        background: $surface;
    }
    
    #main_content {
        border: solid $primary;
        padding: 1;
        background: $surface;
    }
    
    #sidebar_right {
        border: solid $primary;
        padding: 1;
        background: $surface;
    }
    
    /* Conversation log */
    #conversation_log {
        height: 100%;
        border: none;
        scrollbar-gutter: stable;
        background: $surface-lighten-1;
    }
    
    /* Right sidebar components */
    #tool_log {
        height: 25%;
        border: solid $accent;
        margin-bottom: 1;
        background: $surface-lighten-1;
    }
    
    #event_log {
        height: 70%;
        border: solid $accent;
        margin-bottom: 1;
        background: $surface-lighten-1;
    }
    
    
    /* Agent tree */
    #agent_tree {
        margin: 1;
        background: $surface-lighten-1;
    }
    
    /* General styling */
    Label.title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    
    Label {
        height: 1;
    }
    
    /* Section headers */
    .section-header {
        text-style: bold;
        color: $primary;
        background: $surface-darken-1;
        padding: 0 1;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "clear", "Clear logs"),
        ("p", "pause", "Pause/Resume"),
        ("f", "filter", "Filter view"),
        ("d", "debug", "Toggle debug"),
    ]
    
    def __init__(self, daemon_socket: str = None, request_timeout: float = 30.0):
        super().__init__()
        self.daemon_socket = daemon_socket or str(config.socket_path)
        self.request_timeout = request_timeout
        self.event_client = EventBasedClient(socket_path=self.daemon_socket)
        self.connected = False
        self.paused = False
        self.debug_mode = True  # Start in debug mode for troubleshooting
        
        # Local state tracking (replaces MonitorClient state)
        self.active_agents = {}
        self.conversations = {}
        self.tool_calls = []
        self.system_events = []
        self.metrics = {
            'tokens': 0,
            'cost': 0.0,
            'messages': 0,
            'start_time': datetime.now()
        }
        self.message_times: List[datetime] = []
        
    def compose(self) -> ComposeResult:
        """Create the UI layout"""
        # Main container
        with Container(id="main-container"):
            yield Header(show_clock=True)
            
            # Content grid
            with Container(id="content-grid"):
                # Left sidebar - Agent tree
                with Container(id="sidebar_left"):
                    yield Label("[bold]Active Agents[/]", classes="section-header")
                    yield AgentTreeView()
                
                # Main content - Conversation view (now much wider)
                with Container(id="main_content"):
                    yield Label("[bold]Conversation Timeline[/]", classes="section-header")
                    yield ConversationView()
                
                # Right sidebar - Tools, Events, and Temporal Intelligence
                with Container(id="sidebar_right"):
                    yield Label("[bold]Tool Calls[/]", classes="section-header")
                    yield ToolCallsView()
                    yield Label("[bold]Event Stream[/]", classes="section-header")
                    yield EventStreamView()
            
            # Two-line footer container
            with Container(id="footer-container"):
                # Status line (line 1)
                yield MetricsView()
                # Shortcuts line (line 2)
                yield Static(
                    "Monitor: [bold cyan]Q[/]uit [bold cyan]C[/]lear [bold cyan]P[/]ause [bold cyan]D[/]ebug | "
                    "Filter: [bold cyan]F[/]ilter view [bold cyan]T[/]oggle debug",
                    id="custom-footer"
                )
    
    async def on_mount(self) -> None:
        """Connect to daemon when app starts"""
        self.set_interval(1.0, self.update_metrics)
        await self.connect_to_daemon()
        
        # Test conversation log
        try:
            conv_log = self.query_one("#conversation_log", RichLog)
            conv_log.write("[green]Monitor started - conversation log active[/]")
        except Exception as e:
            event_log = self.query_one("#event_log", RichLog)
            event_log.write(f"[red]Failed to write test message to conv_log: {e}[/]")
    
    async def connect_to_daemon(self) -> None:
        """Connect to the daemon and start monitoring"""
        event_log = self.query_one("#event_log", RichLog)
        
        try:
            # Connect event client
            await self.event_client.connect()
            self.connected = True
            
            # Subscribe to all events with a unified handler
            async def handle_all_events(event_name: str, event_data: dict):
                if self.debug_mode and not self.paused:
                    await self.handle_debug_event(event_name, event_data)
                
                # Route events to specific handlers
                if event_name.startswith("message:") or event_name.startswith("conversation:"):
                    await self.handle_message_event(event_name, event_data)
                elif event_name.startswith("agent:"):
                    await self.handle_agent_event(event_name, event_data)
                elif event_name.startswith("tool:"):
                    await self.handle_tool_event(event_name, event_data)
                elif event_name.startswith("system:"):
                    await self.handle_system_event(event_name, event_data)
                
                # Update local state
                await self._update_local_state(event_name, event_data)
            
            self.event_client.subscribe("*", handle_all_events)
            
            self.notify("Connected to daemon and monitoring via events", severity="information")
            event_log.write(f"[green]Monitor connected at {datetime.now().strftime('%H:%M:%S')} (event-based)[/]")
            
        except Exception as e:
            self.notify(f"Failed to connect: {e}", severity="error")
            event_log.write(f"[red]Connection failed: {e}[/]")
            self.connected = False
    
    async def handle_debug_event(self, event_name: str, event_data: Dict[str, Any]) -> None:
        """Handle any event in debug mode for raw visibility"""
        if self.debug_mode and not self.paused:
            event_log = self.query_one("#event_log", RichLog)
            event_log.write(f"[dim]{datetime.now().strftime('%H:%M:%S')} {event_name}[/] {json.dumps(event_data, indent=2)}")
    
    async def _update_local_state(self, event_name: str, event_data: dict) -> None:
        """Update local state based on incoming events."""
        try:
            # Update active agents
            if event_name.startswith("agent:"):
                agent_id = event_data.get("agent_id")
                if agent_id:
                    if event_name == "agent:connect":
                        self.active_agents[agent_id] = {
                            "agent_id": agent_id,
                            "status": "active",
                            "timestamp": event_data.get("timestamp")
                        }
                    elif event_name == "agent:disconnect" and agent_id in self.active_agents:
                        del self.active_agents[agent_id]
            
            # Update conversations
            elif event_name.startswith("message:") or event_name.startswith("conversation:"):
                conv_id = event_data.get("conversation_id")
                if conv_id:
                    if conv_id not in self.conversations:
                        self.conversations[conv_id] = []
                    self.conversations[conv_id].append(event_data)
            
            # Track tool calls
            elif event_name.startswith("tool:"):
                self.tool_calls.append({
                    "event": event_name,
                    "data": event_data,
                    "timestamp": event_data.get("timestamp")
                })
                # Keep only recent tool calls
                if len(self.tool_calls) > 100:
                    self.tool_calls = self.tool_calls[-50:]
            
            # Track system events
            elif event_name.startswith("system:"):
                self.system_events.append({
                    "event": event_name,
                    "data": event_data,
                    "timestamp": event_data.get("timestamp")
                })
                # Keep only recent system events
                if len(self.system_events) > 100:
                    self.system_events = self.system_events[-50:]
        
        except Exception as e:
            # Don't notify errors for every event - just log them
            pass
    
    # Removed poll_event_log - now using event subscriptions instead of polling
    
    async def _process_event_from_log(self, event: Dict[str, Any]) -> None:
        """Process an event from the event log"""
        event_name = event.get("event_name", "unknown")
        event_data = event.get("data", {})
        
        # Route to existing handlers
        if event_name.startswith("completion:"):
            await self._handle_completion_event(event_name, event_data, event)
        elif event_name.startswith("transport:"):
            await self._handle_transport_event(event_name, event_data, event)
        
        # Always show in debug/event log
        if self.debug_mode:
            event_log = self.query_one("#event_log", RichLog)
            timestamp = datetime.fromtimestamp(event.get("timestamp", 0)).strftime('%H:%M:%S')
            client_id = event.get("client_id", "unknown")
            event_log.write(f"[dim]{timestamp} {event_name}[/] [cyan]{client_id}[/] {json.dumps(event_data, indent=2)}")
    
    async def _handle_completion_event(self, event_name: str, event_data: Dict[str, Any], event: Dict[str, Any]) -> None:
        """Handle completion events from event log"""
        client_id = event.get("client_id", "unknown")
        prompt = event_data.get("prompt", "")[:50] + "..." if len(event_data.get("prompt", "")) > 50 else event_data.get("prompt", "")
        
        # Update conversation log
        conv_log = self.query_one("#conversation_log", RichLog)
        timestamp = datetime.fromtimestamp(event.get("timestamp", 0)).strftime('%H:%M:%S')
        conv_log.write(f"[green]{timestamp} {client_id}[/]: {prompt}")
        
        # Update metrics
        self.metrics['messages'] += 1
        self.message_times.append(datetime.fromtimestamp(event.get("timestamp", 0)))
    
    async def _handle_transport_event(self, event_name: str, event_data: Dict[str, Any], event: Dict[str, Any]) -> None:
        """Handle transport events from event log"""
        if event_data.get("action") == "connect":
            client_id = event_data.get("client_id", "unknown")
            timestamp = datetime.fromtimestamp(event.get("timestamp", 0)).strftime('%H:%M:%S')
            
            conv_log = self.query_one("#conversation_log", RichLog)
            conv_log.write(f"[blue]{timestamp} Client connected: {client_id}[/]")
    
    async def handle_message_event(self, event_name: str, event_data: Dict[str, Any]) -> None:
        """Handle message events"""
        if self.paused:
            return
            
        # Update metrics
        self.metrics['messages'] += 1
        self.message_times.append(datetime.now())
        
        # The event_data contains the message
        msg_type = event_data.get('type')
        
        # Route based on message type
        if msg_type in ['DIRECT_MESSAGE', 'CONVERSATION_MESSAGE']:
            await self.handle_conversation_message(event_data)
        elif msg_type == 'BROADCAST':
            await self.handle_broadcast(event_data)
        elif msg_type == 'CONVERSATION_INVITE':
            await self.handle_conversation_invite(event_data)
        
        # Update token/cost estimates
        if 'content' in event_data:
            # Rough token estimation
            tokens = len(event_data['content'].split()) * 1.3
            self.metrics['tokens'] += int(tokens)
            self.metrics['cost'] += tokens * 0.00001  # Rough cost estimate
    
    async def handle_agent_event(self, event_name: str, event_data: Dict[str, Any]) -> None:
        """Handle agent lifecycle events"""
        if self.paused:
            return
            
        if event_name == 'agent:connect':
            await self.handle_agent_connect(event_data)
        elif event_name == 'agent:disconnect':
            await self.handle_agent_disconnect(event_data)
        elif event_name == 'agent:status' or event_data.get('type') == 'AGENT_STATUS':
            await self.handle_agent_status(event_data)
    
    async def handle_tool_event(self, event_name: str, event_data: Dict[str, Any]) -> None:
        """Handle tool events"""
        if self.paused:
            return
            
        await self.handle_tool_call(event_data)
    
    async def handle_system_event(self, event_name: str, event_data: Dict[str, Any]) -> None:
        """Handle system events"""
        if self.paused:
            return
            
        event_log = self.query_one("#event_log", RichLog)
        event_log.write(f"[yellow]System: {event_name}[/] {event_data}")
    
    async def handle_conversation_message(self, message: Dict) -> None:
        """Handle conversation message between agents"""
        try:
            conv_log = self.query_one("#conversation_log", RichLog)
            
            from_agent = message.get('from', 'Unknown')
            to_agent = message.get('to', 'Unknown')
            content = message.get('content', '')
            conversation_id = message.get('conversation_id', 'default')
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            # Format and display
            conv_log.write(f"\n[bold cyan]{timestamp}[/] [bold green]{from_agent}[/] → [bold blue]{to_agent}[/]")
            
            # Truncate long messages
            if len(content) > 200:
                content = content[:200] + "..."
            
            # Indent the content
            for line in content.split('\n'):
                conv_log.write(f"  {line}")
                
            # Force refresh
            conv_log.refresh()
            self.refresh()
                
            event_log.write(f"[yellow]DEBUG: Successfully wrote to conv_log[/]")
        except Exception as e:
            event_log = self.query_one("#event_log", RichLog)
            event_log.write(f"[red]ERROR in handle_conversation_message: {e}[/]")
            import traceback
            event_log.write(f"[red]{traceback.format_exc()}[/]")
    
    async def handle_tool_call(self, message: Dict) -> None:
        """Handle tool call event"""
        tool_log = self.query_one("#tool_log", RichLog)
        
        agent_id = message.get('agent_id', 'Unknown')
        tool = message.get('tool', 'Unknown')
        params = message.get('params', {})
        result = message.get('result', 'pending...')
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        tool_log.write(f"\n[bold yellow]{timestamp}[/] [green]{agent_id}[/] → [cyan]{tool}[/]")
        
        # Show parameters
        if params:
            param_str = json.dumps(params, indent=2)
            for line in param_str.split('\n'):
                tool_log.write(f"  [dim]{line}[/]")
        
        # Show result preview
        if result and result != 'pending...':
            result_str = str(result)
            if len(result_str) > 100:
                result_str = result_str[:100] + "..."
            tool_log.write(f"  [green]→ {result_str}[/]")
    
    async def handle_agent_connect(self, event_data: Dict) -> None:
        """Handle agent connection"""
        agent_id = event_data.get('agent_id')
        if agent_id:
            # Update agent tree using monitor client's data
            await self.update_agent_tree()
    
    async def handle_agent_disconnect(self, event_data: Dict) -> None:
        """Handle agent disconnection"""
        agent_id = event_data.get('agent_id')
        if agent_id:
            # Update agent tree using monitor client's data
            await self.update_agent_tree()
    
    async def handle_agent_status(self, message: Dict) -> None:
        """Handle agent status update"""
        # Update agent tree using monitor client's data
        await self.update_agent_tree()
    
    async def handle_broadcast(self, message: Dict) -> None:
        """Handle broadcast message"""
        conv_log = self.query_one("#conversation_log", RichLog)
        
        from_agent = message.get('from', 'System')
        content = message.get('content', '')
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        conv_log.write(f"\n[bold magenta]{timestamp}[/] [yellow]📢 BROADCAST from {from_agent}:[/]")
        conv_log.write(f"  {content}")
    
    async def handle_conversation_invite(self, message: Dict) -> None:
        """Handle conversation invite"""
        conv_log = self.query_one("#conversation_log", RichLog)
        
        initiator = message.get('initiator')
        invited = message.get('to')
        topic = message.get('topic')
        conversation_id = message.get('conversation_id')
        
        conv_log.write(f"\n[bold green]New Conversation Started:[/] {conversation_id}")
        conv_log.write(f"  Topic: {topic}")
        conv_log.write(f"  Initiator: {initiator} → {invited}")
    
    async def update_agent_tree(self) -> None:
        """Update the agent tree view"""
        tree = self.query_one("#agent_tree", Tree)
        tree.clear()
        
        # Get agents from local state
        active_agents = [
            agent for agent in self.active_agents.values()
            if agent.get("status") == "active"
        ]
        
        for agent_info in active_agents:
            agent_id = agent_info.get('agent_id', 'Unknown')
            role = agent_info.get('role', 'unknown')
            profile = agent_info.get('profile', 'default')
            node = tree.root.add(f"{agent_id} [{role}]")
            node.add_leaf(f"Profile: {profile}")
            
            # Add conversation participation from local data
            for conv_id in self.conversations.keys():
                messages = self.conversations[conv_id]
                if any(m.get('from') == agent_id or 
                      m.get('to') == agent_id for m in messages):
                    node.add_leaf(f"In: {conv_id[:20]}...")
    
    def update_metrics(self) -> None:
        """Update metrics display"""
        if not self.app:
            return
            
        # Calculate message rate (last minute)
        now = datetime.now()
        recent_messages = [t for t in self.message_times if (now - t).seconds < 60]
        msg_rate = len(recent_messages)
        
        # Get active agent count from local state
        active_count = len([a for a in self.active_agents.values() if a.get("status") == "active"])
        
        # Update single status line
        status_text = f"Tokens: {self.metrics['tokens']:,} | Cost: ${self.metrics['cost']:.4f} | Msg/min: {msg_rate} | Active: {active_count}"
        try:
            self.query_one("#status-line", Static).update(status_text)
        except (AttributeError, KeyError):
            pass  # Widget might not be ready yet
    
    def action_quit(self) -> None:
        """Quit the application"""
        if self.connected:
            asyncio.create_task(self.disconnect())
        self.exit()

    async def disconnect(self) -> None:
        """Disconnect from daemon"""
        if self.connected:
            try:
                await self.event_client.disconnect()
                self.connected = False
            except Exception as e:
                self.notify(f"Error during disconnect: {e}", severity="warning")
    
    def action_clear(self) -> None:
        """Clear all logs"""
        self.query_one("#conversation_log", RichLog).clear()
        self.query_one("#tool_log", RichLog).clear()
        self.query_one("#event_log", RichLog).clear()
        self.notify("Logs cleared")
    
    def action_pause(self) -> None:
        """Toggle pause state"""
        self.paused = not self.paused
        status = "paused" if self.paused else "resumed"
        self.notify(f"Monitoring {status}")
    
    def action_debug(self) -> None:
        """Toggle debug mode"""
        self.debug_mode = not self.debug_mode
        status = "enabled" if self.debug_mode else "disabled"
        
        # Debug handler is automatically managed through event subscriptions
        
        self.notify(f"Debug mode {status}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="KSI Monitor TUI")
    parser.add_argument("--socket", default=str(config.socket_path), 
                       help=f"Daemon socket path (default: {config.socket_path})")
    parser.add_argument("--debug", action="store_true",
                       help="Start in debug mode")
    parser.add_argument("--timeout", type=float, default=30.0,
                       help="Request timeout in seconds (default: 30)")
    parser.add_argument("--test-connection", action="store_true",
                       help="Test daemon connection before starting TUI")
    parser.add_argument("--test-only", action="store_true",
                       help="Test daemon connection and exit (no TUI)")
    
    args = parser.parse_args()
    
    app = MultiClaudeMonitor(daemon_socket=args.socket)
    if args.debug:
        app.debug_mode = True
    app.request_timeout = getattr(args, 'timeout', 30.0)
    
    if args.test_connection or args.test_only:
        # Test connection before starting TUI
        import asyncio
        
        async def test_connection():
            client = EventBasedClient(socket_path=args.socket)
            try:
                await client.connect()
                print(f"✓ Successfully connected to daemon at {args.socket}")
                
                # Test basic functionality
                print("✓ Testing basic event communication...")
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
        
        # If --test-only, exit after successful test
        if args.test_only:
            print("✓ Connection test completed successfully")
            return 0
    
    app.run()
    return 0


if __name__ == "__main__":
    main()