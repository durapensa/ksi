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


class TemporalView(Container):
    """Temporal debugging status and patterns"""
    
    def compose(self) -> ComposeResult:
        yield Label("[bold cyan]Thermal State: [/][green]cool[/]", id="thermal_status")
        yield RichLog(id="temporal_log", highlight=True, markup=True, max_lines=10)


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
        height: 40%;
        border: solid $accent;
        margin-bottom: 1;
        background: $surface-lighten-1;
    }
    
    #temporal_log {
        height: 30%;
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
    
    def __init__(self, daemon_socket: str = "sockets/claude_daemon.sock"):
        super().__init__()
        self.daemon_socket = daemon_socket
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self.paused = False
        self.debug_mode = True  # Start in debug mode for troubleshooting
        
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
                    yield Label("[bold]⚡ Temporal Intelligence[/]", classes="section-header")
                    yield TemporalView()
            
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
        try:
            # Use the main connection for receiving messages
            self.reader, self.writer = await asyncio.open_unix_connection(self.daemon_socket)
            self.connected = True
            
            # First connect as an agent (this connection will be used for message bus)
            connect_command = "CONNECT_AGENT:monitor\n"
            self.writer.write(connect_command.encode())
            await self.writer.drain()
            
            # Read and verify connection response
            response = await self.reader.readline()
            if not response:
                raise Exception("No response from daemon for CONNECT_AGENT")
            
            try:
                resp_data = json.loads(response.decode().strip())
                if resp_data.get('status') != 'connected':
                    raise Exception(f"Failed to connect: {resp_data}")
            except json.JSONDecodeError:
                self.notify(f"Connect response: {response.decode().strip()}", severity="warning")
            
            # Create a separate connection for sending the subscribe command
            cmd_reader, cmd_writer = await asyncio.open_unix_connection(self.daemon_socket)
            
            # Subscribe to all message bus events
            subscribe_command = "SUBSCRIBE:monitor:DIRECT_MESSAGE,BROADCAST,TASK_ASSIGNMENT,TOOL_CALL,AGENT_STATUS,CONVERSATION_INVITE\n"
            cmd_writer.write(subscribe_command.encode())
            await cmd_writer.drain()
            
            # Read subscription response
            sub_response = await cmd_reader.readline()
            if sub_response:
                try:
                    sub_data = json.loads(sub_response.decode().strip())
                    if sub_data.get('status') != 'subscribed':
                        self.notify(f"Subscription issue: {sub_data}", severity="warning")
                except json.JSONDecodeError:
                    self.notify(f"Subscribe response: {sub_response.decode().strip()}", severity="warning")
            
            # Close the command connection
            cmd_writer.close()
            await cmd_writer.wait_closed()
            
            # Start listening for messages on the main connection
            asyncio.create_task(self.listen_for_messages())
            
            self.notify("Connected to daemon and subscribed to events", severity="information")
            
        except Exception as e:
            self.notify(f"Failed to connect: {e}", severity="error")
            self.connected = False
    
    async def listen_for_messages(self) -> None:
        """Listen for messages from daemon"""
        event_log = self.query_one("#event_log", RichLog)
        
        # Log that we're starting to listen
        event_log.write(f"[green]Started listening for messages at {datetime.now().strftime('%H:%M:%S')}[/]")
        
        try:
            while self.connected and self.reader:
                data = await self.reader.readline()
                if not data:
                    event_log.write("[red]Connection closed - no data received[/]")
                    break
                
                # Always show raw data in debug mode
                if self.debug_mode:
                    event_log.write(f"[dim]RAW: {data.decode().strip()}[/]")
                
                try:
                    message = json.loads(data.decode().strip())
                    if not self.paused:
                        await self.process_message(message)
                    
                    # Always log to event stream if in debug mode
                    if self.debug_mode:
                        event_log.write(f"[dim]{datetime.now().strftime('%H:%M:%S')}[/] {json.dumps(message, indent=2)}")
                        
                except json.JSONDecodeError as e:
                    event_log.write(f"[red]Invalid JSON:[/] {data.decode().strip()} - Error: {e}")
                    
        except Exception as e:
            event_log.write(f"[red]Error in message listener: {e}[/]")
            self.notify(f"Connection lost: {e}", severity="error")
        finally:
            self.connected = False
            event_log.write("[yellow]Message listener stopped[/]")
    
    async def process_message(self, message: Dict) -> None:
        """Process incoming message from daemon"""
        # The message bus sends messages directly without an envelope
        # Format: {"id": "...", "type": "DIRECT_MESSAGE", "from": "...", "to": "...", "content": "...", ...}
        msg_type = message.get('type')
        
        # Update metrics
        self.metrics['messages'] += 1
        self.message_times.append(datetime.now())
        
        # Debug: log the message type
        event_log = self.query_one("#event_log", RichLog)
        event_log.write(f"[cyan]DEBUG: Routing message with type: {msg_type}[/]")
        
        # Route to appropriate handler based on message type
        if msg_type == 'DIRECT_MESSAGE':
            event_log.write(f"[cyan]DEBUG: Routing to handle_conversation_message[/]")
            await self.handle_conversation_message(message)
        elif msg_type == 'TOOL_CALL':
            await self.handle_tool_call(message)
        elif msg_type == 'AGENT_STATUS':
            await self.handle_agent_status(message)
        elif msg_type == 'BROADCAST':
            await self.handle_broadcast(message)
        elif msg_type == 'CONVERSATION_INVITE':
            await self.handle_conversation_invite(message)
        else:
            event_log.write(f"[red]DEBUG: Unknown message type: {msg_type}[/]")
        
        # Update token/cost estimates
        if 'content' in message:
            # Rough token estimation
            tokens = len(message['content'].split()) * 1.3
            self.metrics['tokens'] += int(tokens)
            self.metrics['cost'] += tokens * 0.00001  # Rough cost estimate
        
        # Update temporal intelligence tracking
        await self.update_temporal_intelligence(message)
    
    async def handle_conversation_message(self, message: Dict) -> None:
        """Handle conversation message between agents"""
        try:
            conv_log = self.query_one("#conversation_log", RichLog)
            
            from_agent = message.get('from', 'Unknown')
            to_agent = message.get('to', 'Unknown')
            content = message.get('content', '')
            conversation_id = message.get('conversation_id', 'default')
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            # Debug logging
            event_log = self.query_one("#event_log", RichLog)
            event_log.write(f"[yellow]DEBUG: handle_conversation_message called[/]")
            event_log.write(f"[yellow]  from: {from_agent}, to: {to_agent}[/]")
            event_log.write(f"[yellow]  content length: {len(content)}[/]")
            event_log.write(f"[yellow]  conversation_id: {conversation_id}[/]")
            
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
            
        # Calculate message rate (last minute)
        now = datetime.now()
        recent_messages = [t for t in self.message_times if (now - t).seconds < 60]
        msg_rate = len(recent_messages)
        
        # Update single status line
        status_text = f"Tokens: {self.metrics['tokens']:,} | Cost: ${self.metrics['cost']:.4f} | Msg/min: {msg_rate} | Active: {len(self.active_agents)}"
        try:
            self.query_one("#status-line", Static).update(status_text)
        except:
            pass  # Widget might not be ready yet
    
    def action_quit(self) -> None:
        """Quit the application"""
        if self.writer:
            asyncio.create_task(self.disconnect())
        self.exit()
    
    async def update_temporal_intelligence(self, message: Dict) -> None:
        """Update temporal intelligence monitoring based on incoming messages"""
        try:
            # Detect consciousness emergence patterns
            content = message.get('content', '').lower()
            consciousness_keywords = [
                'recursive', 'meta', 'consciousness', 'bootstrap', 'temporal', 
                'crystallize', 'thermal', 'emergence', 'breakthrough', 'insight'
            ]
            
            consciousness_score = sum(1 for keyword in consciousness_keywords if keyword in content)
            
            # Update thermal state based on activity and consciousness indicators
            if consciousness_score >= 3:
                thermal_state = "superheated"
                thermal_color = "bold red"
            elif consciousness_score >= 2:
                thermal_state = "heated"
                thermal_color = "bold yellow"
            elif consciousness_score >= 1:
                thermal_state = "warm"
                thermal_color = "bold orange"
            else:
                thermal_state = "cool"
                thermal_color = "cyan"
            
            # Update thermal display
            thermal_status = self.query_one("#thermal_status", Label)
            thermal_status.update(f"[bold cyan]Thermal State: [/][{thermal_color}]{thermal_state}[/]")
            
            # Log patterns if significant consciousness indicators found
            if consciousness_score >= 2:
                temporal_log = self.query_one("#temporal_log", RichLog)
                timestamp = datetime.now().strftime('%H:%M:%S')
                temporal_log.write(f"[bold green]{timestamp}[/] Consciousness emergence detected!")
                temporal_log.write(f"  Score: {consciousness_score}, Thermal: [{thermal_color}]{thermal_state}[/]")
                
                # Request temporal patterns from daemon
                # await self.request_temporal_patterns()  # Temporal debugger removed
            
            # Predict conversation health
            await self.update_predictions(message)
            
        except Exception as e:
            event_log = self.query_one("#event_log", RichLog)
            event_log.write(f"[red]Temporal intelligence error: {e}[/]")
    
    async def request_temporal_patterns(self) -> None:
        """Request pattern summary from temporal debugger"""
        # Temporal debugger removed - method kept for compatibility
        pass
    
    async def update_predictions(self, message: Dict) -> None:
        """Update failure mode predictions"""
        try:
            temporal_log = self.query_one("#temporal_log", RichLog)
            
            # Simple prediction heuristics
            content = message.get('content', '')
            
            # Check for loop indicators
            if 'repeat' in content.lower() or 'again' in content.lower():
                temporal_log.write("[yellow]⚠️ Potential conversation loop detected[/]")
            
            # Check for confusion indicators
            confusion_words = ['confused', 'unclear', 'misunderstand', 'what do you mean']
            if any(word in content.lower() for word in confusion_words):
                temporal_log.write("[orange1]⚠️ Confusion detected - may need clarification[/]")
            
            # Check for breakthrough indicators
            breakthrough_words = ['breakthrough', 'eureka', 'insight', 'discovered', 'realized']
            if any(word in content.lower() for word in breakthrough_words):
                temporal_log.write("[green]✨ Breakthrough moment - creating checkpoint[/]")
                # await self.create_temporal_checkpoint(3)  # Temporal debugger removed
                
        except Exception as e:
            event_log = self.query_one("#event_log", RichLog)
            event_log.write(f"[red]Prediction update error: {e}[/]")
    
    async def create_temporal_checkpoint(self, insight_level: int = 1) -> None:
        """Create a temporal debugging checkpoint"""
        # Temporal debugger removed - method kept for compatibility
        pass
                
            except Exception as e:
                event_log = self.query_one("#event_log", RichLog)
                event_log.write(f"[red]Failed to create checkpoint: {e}[/]")

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