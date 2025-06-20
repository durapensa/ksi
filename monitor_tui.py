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

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, Label, Tree, DataTable, TextLog, Sparkline
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
        yield TextLog(id="conversation_log", highlight=True, markup=True)


class AgentTreeView(Container):
    """Active agents tree view"""
    
    def compose(self) -> ComposeResult:
        tree = Tree("Active Agents", id="agent_tree")
        tree.root.expand()
        yield tree


class MetricsView(Container):
    """System metrics view"""
    
    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Label("Tokens: ", id="tokens_label")
            yield Label("0", id="tokens_value")
            yield Label(" | Cost: $", id="cost_label")
            yield Label("0.00", id="cost_value")
            yield Label(" | Msg/min: ", id="msg_rate_label")
            yield Label("0", id="msg_rate_value")
            yield Label(" | Active: ", id="active_label")
            yield Label("0", id="active_value")


class ToolCallsView(Container):
    """Tool calls inspector"""
    
    def compose(self) -> ComposeResult:
        yield TextLog(id="tool_log", highlight=True, markup=True)


class EventStreamView(Container):
    """Raw event stream for debugging"""
    
    def compose(self) -> ComposeResult:
        yield TextLog(id="event_log", highlight=True, markup=True, max_lines=1000)


class MultiClaudeMonitor(App):
    """TUI Monitor for Multi-Claude Conversations"""
    
    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 3;
        grid-columns: 1fr 3fr 1fr;
        grid-rows: auto 1fr auto;
    }
    
    Header {
        column-span: 3;
    }
    
    Footer {
        column-span: 3;
    }
    
    #sidebar_left {
        dock: left;
        width: 30;
        border: solid green;
        overflow-y: scroll;
    }
    
    #main_content {
        border: solid blue;
    }
    
    #sidebar_right {
        dock: right;
        width: 40;
        border: solid yellow;
    }
    
    #conversation_log {
        height: 100%;
        border: none;
        scrollbar-gutter: stable;
    }
    
    #tool_log {
        height: 40%;
        border: solid cyan;
        margin: 1;
    }
    
    #event_log {
        height: 55%;
        border: solid magenta;
        margin: 1;
    }
    
    #metrics_container {
        height: 3;
        border: solid white;
        align: center middle;
    }
    
    #agent_tree {
        margin: 1;
    }
    
    Label {
        height: 1;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "clear", "Clear logs"),
        ("p", "pause", "Pause/Resume"),
        ("f", "filter", "Filter view"),
        ("d", "debug", "Toggle debug"),
    ]
    
    def __init__(self, daemon_socket: str = "sockets/claude_daemon.sock"):
        super().__init__()
        self.daemon_socket = daemon_socket
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self.paused = False
        self.debug_mode = False
        
        # Tracking data
        self.active_agents: Dict[str, Dict] = {}
        self.conversations: Dict[str, List[Dict]] = {}
        self.metrics = {
            'tokens': 0,
            'cost': 0.0,
            'messages': 0,
            'start_time': datetime.now()
        }
        self.message_times: List[datetime] = []
        
    def compose(self) -> ComposeResult:
        """Create the UI layout"""
        yield Header(show_clock=True)
        
        # Left sidebar - Agent tree
        with Container(id="sidebar_left"):
            yield Label("[bold green]Active Agents[/]")
            yield AgentTreeView()
        
        # Main content - Conversation view
        with Container(id="main_content"):
            yield Label("[bold blue]Conversation Timeline[/]")
            yield ConversationView()
        
        # Right sidebar - Tools and events
        with Container(id="sidebar_right"):
            yield Label("[bold yellow]Tool Calls[/]")
            yield ToolCallsView()
            yield Label("[bold magenta]Event Stream[/]")
            yield EventStreamView()
        
        # Bottom metrics
        with Container(id="metrics_container"):
            yield MetricsView()
        
        yield Footer()
    
    async def on_mount(self) -> None:
        """Connect to daemon when app starts"""
        self.set_interval(1.0, self.update_metrics)
        await self.connect_to_daemon()
    
    async def connect_to_daemon(self) -> None:
        """Connect to the daemon and start monitoring"""
        try:
            self.reader, self.writer = await asyncio.open_unix_connection(self.daemon_socket)
            self.connected = True
            
            # Subscribe to all message bus events
            command = "SUBSCRIBE:monitor:DIRECT_MESSAGE,BROADCAST,TASK_ASSIGNMENT,TOOL_CALL,AGENT_STATUS,CONVERSATION_INVITE\n"
            self.writer.write(command.encode())
            await self.writer.drain()
            
            # Start listening for messages
            asyncio.create_task(self.listen_for_messages())
            
            self.notify("Connected to daemon", severity="information")
            
        except Exception as e:
            self.notify(f"Failed to connect: {e}", severity="error")
            self.connected = False
    
    async def listen_for_messages(self) -> None:
        """Listen for messages from daemon"""
        event_log = self.query_one("#event_log", TextLog)
        
        try:
            while self.connected and self.reader:
                data = await self.reader.readline()
                if not data:
                    break
                
                try:
                    message = json.loads(data.decode().strip())
                    if not self.paused:
                        await self.process_message(message)
                    
                    # Always log to event stream if in debug mode
                    if self.debug_mode:
                        event_log.write(f"[dim]{datetime.now().strftime('%H:%M:%S')}[/] {json.dumps(message, indent=2)}")
                        
                except json.JSONDecodeError:
                    event_log.write(f"[red]Invalid JSON:[/] {data.decode().strip()}")
                    
        except Exception as e:
            self.notify(f"Connection lost: {e}", severity="error")
        finally:
            self.connected = False
    
    async def process_message(self, message: Dict) -> None:
        """Process incoming message from daemon"""
        msg_type = message.get('type')
        
        # Update metrics
        self.metrics['messages'] += 1
        self.message_times.append(datetime.now())
        
        # Route to appropriate handler
        if msg_type == 'DIRECT_MESSAGE':
            await self.handle_conversation_message(message)
        elif msg_type == 'TOOL_CALL':
            await self.handle_tool_call(message)
        elif msg_type == 'AGENT_STATUS':
            await self.handle_agent_status(message)
        elif msg_type == 'BROADCAST':
            await self.handle_broadcast(message)
        elif msg_type == 'CONVERSATION_INVITE':
            await self.handle_conversation_invite(message)
        
        # Update token/cost estimates
        if 'content' in message:
            # Rough token estimation
            tokens = len(message['content'].split()) * 1.3
            self.metrics['tokens'] += int(tokens)
            self.metrics['cost'] += tokens * 0.00001  # Rough cost estimate
    
    async def handle_conversation_message(self, message: Dict) -> None:
        """Handle conversation message between agents"""
        conv_log = self.query_one("#conversation_log", TextLog)
        
        from_agent = message.get('from', 'Unknown')
        to_agent = message.get('to', 'Unknown')
        content = message.get('content', '')
        conversation_id = message.get('conversation_id', 'default')
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # Store in conversation history
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        self.conversations[conversation_id].append(message)
        
        # Format and display
        conv_log.write(f"\n[bold cyan]{timestamp}[/] [bold green]{from_agent}[/] → [bold blue]{to_agent}[/]")
        
        # Truncate long messages
        if len(content) > 200:
            content = content[:200] + "..."
        
        # Indent the content
        for line in content.split('\n'):
            conv_log.write(f"  {line}")
    
    async def handle_tool_call(self, message: Dict) -> None:
        """Handle tool call event"""
        tool_log = self.query_one("#tool_log", TextLog)
        
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
    
    async def handle_agent_status(self, message: Dict) -> None:
        """Handle agent status update"""
        agent_id = message.get('agent_id')
        status = message.get('status')
        
        if status == 'connected':
            self.active_agents[agent_id] = message
        elif status == 'disconnected':
            self.active_agents.pop(agent_id, None)
        
        # Update agent tree
        await self.update_agent_tree()
    
    async def handle_broadcast(self, message: Dict) -> None:
        """Handle broadcast message"""
        conv_log = self.query_one("#conversation_log", TextLog)
        
        from_agent = message.get('from', 'System')
        content = message.get('content', '')
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        conv_log.write(f"\n[bold magenta]{timestamp}[/] [yellow]📢 BROADCAST from {from_agent}:[/]")
        conv_log.write(f"  {content}")
    
    async def handle_conversation_invite(self, message: Dict) -> None:
        """Handle conversation invite"""
        conv_log = self.query_one("#conversation_log", TextLog)
        
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
        
        for agent_id, info in self.active_agents.items():
            role = info.get('role', 'unknown')
            profile = info.get('profile', 'default')
            node = tree.root.add(f"{agent_id} [{role}]")
            node.add_leaf(f"Profile: {profile}")
            
            # Add conversation participation
            for conv_id, messages in self.conversations.items():
                if any(m.get('from') == agent_id or m.get('to') == agent_id for m in messages):
                    node.add_leaf(f"In: {conv_id[:20]}...")
    
    def update_metrics(self) -> None:
        """Update metrics display"""
        if not self.app:
            return
            
        # Update values
        self.query_one("#tokens_value", Label).update(f"{self.metrics['tokens']:,}")
        self.query_one("#cost_value", Label).update(f"{self.metrics['cost']:.4f}")
        self.query_one("#active_value", Label).update(str(len(self.active_agents)))
        
        # Calculate message rate (last minute)
        now = datetime.now()
        recent_messages = [t for t in self.message_times if (now - t).seconds < 60]
        msg_rate = len(recent_messages)
        self.query_one("#msg_rate_value", Label).update(str(msg_rate))
    
    def action_quit(self) -> None:
        """Quit the application"""
        if self.writer:
            asyncio.create_task(self.disconnect())
        self.exit()
    
    async def disconnect(self) -> None:
        """Disconnect from daemon"""
        if self.writer:
            try:
                self.writer.write(b"DISCONNECT_AGENT:monitor\n")
                await self.writer.drain()
                self.writer.close()
                await self.writer.wait_closed()
            except:
                pass
    
    def action_clear(self) -> None:
        """Clear all logs"""
        self.query_one("#conversation_log", TextLog).clear()
        self.query_one("#tool_log", TextLog).clear()
        self.query_one("#event_log", TextLog).clear()
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
        self.notify(f"Debug mode {status}")


def main():
    """Main entry point"""
    import sys
    
    socket = "sockets/claude_daemon.sock"
    if len(sys.argv) > 1:
        socket = sys.argv[1]
    
    app = MultiClaudeMonitor(daemon_socket=socket)
    app.run()


if __name__ == "__main__":
    main()