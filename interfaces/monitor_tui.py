#!/usr/bin/env python3
"""
Multi-Claude Conversation Monitor - Textual TUI for real-time observation
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Set
from pathlib import Path
import re
import sys
import os
import logging

# Add path for ksi_admin
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ksi_admin import MonitorClient

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
    
    def __init__(self, daemon_socket: str = "var/run/daemon.sock"):
        super().__init__()
        self.daemon_socket = daemon_socket
        self.monitor_client = MonitorClient(socket_path=daemon_socket)
        self.connected = False
        self.paused = False
        self.debug_mode = True  # Start in debug mode for troubleshooting
        
        # Tracking data - MonitorClient maintains these internally
        # We'll sync from monitor_client as needed
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
            # Connect monitor client
            await self.monitor_client.connect()
            self.connected = True
            
            # Register event handlers
            self.monitor_client.on_message_flow(self.handle_message_event)
            self.monitor_client.on_agent_activity(self.handle_agent_event)
            self.monitor_client.on_tool_usage(self.handle_tool_event)
            self.monitor_client.on_system_event(self.handle_system_event)
            
            # Also register a catch-all handler for debug mode
            if self.debug_mode:
                self.monitor_client.on_any_activity(self.handle_debug_event)
            
            # Start observing all events
            await self.monitor_client.observe_all()
            
            self.notify("Connected to daemon and monitoring all events", severity="information")
            event_log.write(f"[green]Monitor connected at {datetime.now().strftime('%H:%M:%S')}[/]")
            
        except Exception as e:
            self.notify(f"Failed to connect: {e}", severity="error")
            event_log.write(f"[red]Connection failed: {e}[/]")
            self.connected = False
    
    async def handle_debug_event(self, event_name: str, event_data: Dict[str, Any]) -> None:
        """Handle any event in debug mode for raw visibility"""
        if self.debug_mode and not self.paused:
            event_log = self.query_one("#event_log", RichLog)
            event_log.write(f"[dim]{datetime.now().strftime('%H:%M:%S')} {event_name}[/] {json.dumps(event_data, indent=2)}")
    
    async def handle_message_event(self, event_name: str, event_data: Dict[str, Any]) -> None:
        """Handle message events from MonitorClient"""
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
        """Handle agent lifecycle events from MonitorClient"""
        if self.paused:
            return
            
        if event_name == 'agent:connect':
            await self.handle_agent_connect(event_data)
        elif event_name == 'agent:disconnect':
            await self.handle_agent_disconnect(event_data)
        elif event_name == 'agent:status' or event_data.get('type') == 'AGENT_STATUS':
            await self.handle_agent_status(event_data)
    
    async def handle_tool_event(self, event_name: str, event_data: Dict[str, Any]) -> None:
        """Handle tool events from MonitorClient"""
        if self.paused:
            return
            
        await self.handle_tool_call(event_data)
    
    async def handle_system_event(self, event_name: str, event_data: Dict[str, Any]) -> None:
        """Handle system events from MonitorClient"""
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
        
        # Get agents from monitor client
        active_agents = self.monitor_client.get_active_agents()
        
        for agent_info in active_agents:
            agent_id = agent_info.get('id', 'Unknown')
            role = agent_info.get('role', 'unknown')
            profile = agent_info.get('profile', 'default')
            node = tree.root.add(f"{agent_id} [{role}]")
            node.add_leaf(f"Profile: {profile}")
            
            # Add conversation participation from monitor client data
            for conv_id in self.monitor_client.conversations.keys():
                messages = self.monitor_client.get_conversation_messages(conv_id)
                if any(m.get('data', {}).get('from') == agent_id or 
                      m.get('data', {}).get('to') == agent_id for m in messages):
                    node.add_leaf(f"In: {conv_id[:20]}...")
    
    def update_metrics(self) -> None:
        """Update metrics display"""
        if not self.app:
            return
            
        # Calculate message rate (last minute)
        now = datetime.now()
        recent_messages = [t for t in self.message_times if (now - t).seconds < 60]
        msg_rate = len(recent_messages)
        
        # Get active agent count from monitor client
        active_count = len(self.monitor_client.get_active_agents())
        
        # Update single status line
        status_text = f"Tokens: {self.metrics['tokens']:,} | Cost: ${self.metrics['cost']:.4f} | Msg/min: {msg_rate} | Active: {active_count}"
        try:
            self.query_one("#status-line", Static).update(status_text)
        except:
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
                await self.monitor_client.stop_observing()
                await self.monitor_client.disconnect()
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
        
        # Register/unregister debug handler based on mode
        if self.debug_mode and self.connected:
            self.monitor_client.on_any_activity(self.handle_debug_event)
        
        self.notify(f"Debug mode {status}")


def main():
    """Main entry point"""
    import sys
    
    socket = "var/run/daemon.sock"
    if len(sys.argv) > 1:
        socket = sys.argv[1]
    
    app = MultiClaudeMonitor(daemon_socket=socket)
    app.run()


if __name__ == "__main__":
    main()