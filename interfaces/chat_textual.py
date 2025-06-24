#!/usr/bin/env python3
"""
Enhanced Textual-based chat interface for Claude via the daemon
Rich TUI with support for single-agent chat, multi-agent participation, and conversation browsing
"""

import asyncio
import json
import logging
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
import subprocess
import time

# Import timestamp utilities for consistent timezone handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ksi_daemon.timestamp_utils import TimestampManager
from ksi_client.utils import CommandBuilder, ResponseHandler, ConnectionManager
from ksi_client import SimpleChatClient
# Import AgentProcess later to avoid early logging setup

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, Label, Input, RichLog, Button, ListView, ListItem, Tree
from textual.reactive import reactive
from textual.message import Message
from textual.binding import Binding
from textual import events, work
from textual.worker import Worker, WorkerState


SOCKET_PATH = os.environ.get('CLAUDE_DAEMON_SOCKET', 'sockets/claude_daemon.sock')


class ChatInput(Input):
    """Custom Input that allows app-level key bindings to work"""
    
    def on_key(self, event: events.Key) -> None:
        """Handle key events, allowing app bindings for non-text keys"""
        # Let app-level control keys bubble up naturally - don't intercept them
        # Input widget doesn't handle these anyway, so they'll reach the app bindings
        pass


class PastConversationBrowser(Container):
    """Browse and select past conversations"""
    
    def compose(self) -> ComposeResult:
        yield Label("📚 Past Conversations (Click to replay)", classes="section-header")
        yield ListView(id="past-conversation-list")


class ActiveConversationBrowser(Container):
    """Browse and join active conversations"""
    
    def compose(self) -> ComposeResult:
        yield Label("🔴 Active Conversations (Click to join)", classes="section-header")
        yield ListView(id="active-conversation-list")


class ConversationView(ScrollableContainer):
    """Main conversation display area"""
    
    def compose(self) -> ComposeResult:
        yield RichLog(id="conversation_log", highlight=True, markup=True, wrap=True)


class StatusBar(Static):
    """Status bar showing session info and metrics"""
    
    def __init__(self, id: str = None):
        super().__init__("", id=id)
        self.session_id = "None"
        self.mode = "chat"
        self.conversation_id = None
        self.tokens = 0
        self.cost = 0.0
    
    def update_display(self):
        """Update the status bar display"""
        conv_info = f" | Conv: {self.conversation_id}" if self.conversation_id else ""
        self.update(f"Session: {self.session_id} | Mode: {self.mode}{conv_info} | Tokens: {self.tokens:,} | Cost: ${self.cost:.4f}")


class ChatInterface(App):
    """Enhanced Textual-based chat interface"""
    
    # Standard Textual configuration
    AUTO_FOCUS = ""  # Disable auto-focus to prevent Input consuming key events
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    #header-container {
        height: 3;
        background: $surface;
        padding: 1;
        border-bottom: solid $primary;
    }
    
    #main-container {
        layout: horizontal;
        height: 1fr;
        margin-bottom: 2;
    }
    
    #past-sidebar {
        width: 45;
        border-right: solid $primary;
        padding: 1;
        display: none;
    }
    
    #past-sidebar.visible {
        display: block;
    }
    
    #active-sidebar {
        width: 45;
        border-right: solid $primary;
        padding: 1;
        display: none;
    }
    
    #active-sidebar.visible {
        display: block;
    }
    
    #past-conversation-list, #active-conversation-list {
        height: 1fr;
        background: $surface;
    }
    
    #past-conversation-list > ListItem, #active-conversation-list > ListItem {
        padding: 0 1;
    }
    
    #past-conversation-list > ListItem.--highlight, #active-conversation-list > ListItem.--highlight {
        background: $primary;
    }
    
    #chat-container {
        width: 1fr;
        padding: 1;
    }
    
    #conversation_log {
        height: 1fr;
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
    }
    
    #input-container {
        height: 3;
        layout: horizontal;
    }
    
    #input-field {
        width: 1fr;
        margin-right: 1;
    }
    
    #send-button {
        width: 10;
        min-width: 10;
    }
    
    #status-bar {
        height: 2;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
        border-top: solid $primary;
        dock: bottom;
        display: block;
    }
    
    .section-header {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+n", "new_session", "New Session"),
        Binding("ctrl+b", "toggle_past_browser", "Past Sessions"),
        Binding("ctrl+r", "toggle_active_browser", "Active Sessions"),
        Binding("ctrl+l", "clear_conversation", "Clear"),
        Binding("ctrl+e", "export_conversation", "Export", show=False),
        Binding("f1", "show_help", "Help"),
    ]
    
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.session_id: Optional[str] = None
        self.mode = "chat"  # chat, replay, or multi
        self.conversation_id: Optional[str] = None  # For multi-agent conversations
        self.show_past_browser = False
        self.show_active_browser = False
        self.input_history: List[str] = []
        self.history_index = -1
        self.daemon_connected = False
        self.current_conversation: List[Dict] = []
        self.available_sessions: List[Tuple[str, str, int]] = []  # (session_id, timestamp, message_count)
        self.active_conversations: Dict[str, Dict] = {}  # conversation_id -> info
        self.profile_data: Optional[Dict] = None
        self.selected_past_session: Optional[str] = None  # For export functionality
        
        # For multi-agent mode
        self.agent_id: Optional[str] = None
        self.message_reader: Optional[asyncio.StreamReader] = None
        self.message_writer: Optional[asyncio.StreamWriter] = None
        
        # Metrics tracking
        self.metrics = {
            'tokens': 0,
            'cost': 0.0,
            'messages': 0
        }
        
        # Agent process for composition-aware messaging
        self.agent_process = None
        
        # Multi-socket client for new architecture
        self.chat_client: Optional[SimpleChatClient] = None
    
    def compose(self) -> ComposeResult:
        """Create the UI layout"""
        # Header
        with Container(id="header-container"):
            yield Label("🤖 Claude Chat (Textual) - F1: Help | Ctrl+B: Past | Ctrl+R: Active", classes="section-header")
        
        # Main content area
        with Container(id="main-container"):
            # Past conversations sidebar
            with Container(id="past-sidebar"):
                yield PastConversationBrowser()
            
            # Active conversations sidebar
            with Container(id="active-sidebar"):
                yield ActiveConversationBrowser()
            
            # Chat area
            with Container(id="chat-container"):
                yield ConversationView()
                
                # Input area
                with Container(id="input-container"):
                    yield ChatInput(
                        placeholder="Type your message... (Ctrl+Q to quit, F1 for help)",
                        id="input-field"
                    )
                    yield Button("Send", id="send-button", variant="primary")
        
        # Status bar
        yield StatusBar(id="status-bar")
    
    def on_mount(self) -> None:
        """Initialize when app starts"""
        # Set initial focus to input
        self.set_focus(self.query_one("#input-field"))
        
        # Start initialization in background
        self.init_app()
    
    
    @work(exclusive=True)
    async def init_app(self) -> None:
        """Initialize the application in background"""
        # Load profile first
        self.load_profile()
        
        # First ensure daemon is running
        await self.ensure_daemon_running()
        
        # Initialize multi-socket client
        self.chat_client = SimpleChatClient(client_id=f"chat_textual_{self.args.profile}")
        
        try:
            # Initialize the client (connects to messaging socket, subscribes to events)
            await self.chat_client.initialize()
            self.daemon_connected = True
            
            # Note: AgentProcess is deprecated with new architecture
            # Composition support is now handled by the daemon
            
            # Load available sessions
            await self.load_available_sessions()
            
            # Load active conversations
            await self.load_active_conversations()
            
            # Initialize session based on arguments
            await self.initialize_session()
            
            self.update_status()
        except Exception as e:
            self.daemon_connected = False
            self.log_message("Error", f"Failed to initialize: {str(e)}")
    
    async def ensure_daemon_running(self) -> None:
        """Start daemon if not running"""
        # Check if daemon is running by trying to connect
        try:
            reader, writer = await asyncio.open_unix_connection(SOCKET_PATH)
            writer.close()
            await writer.wait_closed()
            return  # Daemon is running
        except:
            pass
        
        # Start daemon with all output suppressed
        self.log_message("System", "Starting daemon...")
        with open(os.devnull, 'w') as devnull:
            subprocess.Popen(['python3', 'ksi-daemon.py', '--foreground'], 
                            stdout=devnull, 
                            stderr=devnull,
                            stdin=devnull,
                            preexec_fn=os.setsid)
        
        # Wait for daemon to start
        for i in range(20):  # 10 seconds timeout
            await asyncio.sleep(0.5)
            try:
                reader, writer = await asyncio.open_unix_connection(SOCKET_PATH)
                writer.close()
                await writer.wait_closed()
                self.log_message("System", "Daemon started successfully")
                return
            except:
                continue
        
        self.log_message("System", "Warning: Daemon may not have started properly")
    
    async def connect_to_daemon(self) -> bool:
        """Test daemon connection"""
        try:
            # Use multi-socket client to test connection
            if self.chat_client:
                health = await self.chat_client.health_check()
                return bool(health)
            return False
        except Exception as e:
            return False
    
    async def send_to_daemon(self, command: str, parameters: Dict[str, Any] = None) -> str:
        """Send command to daemon and get response"""
        try:
            if not self.chat_client:
                return json.dumps({"status": "error", "error": {"message": "Client not initialized"}})
            
            # Map commands to appropriate sockets
            socket_map = {
                "HEALTH_CHECK": "admin",
                "GET_PROCESSES": "admin",
                "MESSAGE_BUS_STATS": "admin",
                "SHUTDOWN": "admin",
                "GET_AGENTS": "agents",
                "REGISTER_AGENT": "agents",
                "SUBSCRIBE": "messaging",
                "PUBLISH": "messaging",
                "AGENT_CONNECTION": "messaging",
                "SET_AGENT_KV": "state",
                "GET_AGENT_KV": "state",
                "COMPLETION": "completion"
            }
            
            socket_name = socket_map.get(command, "admin")
            
            # Send command using multi-socket client
            response = await self.chat_client.send_command(socket_name, command, parameters)
            
            # Return as JSON string for compatibility
            return json.dumps(response)
            
        except Exception as e:
            return json.dumps({"status": "error", "error": {"message": f"Command failed: {str(e)}"}})
    
    async def send_spawn_command(self, command_dict: dict) -> str:
        """DEPRECATED: This method is no longer used. Use chat_client.send_prompt() instead."""
        return json.dumps({"status": "error", "error": {"message": "SPAWN command is deprecated. Use COMPLETION instead."}})
    
    def load_profile(self) -> None:
        """Load the specified profile"""
        profile_name = self.args.profile
        profile_path = Path(f'agent_profiles/{profile_name}.json')
        
        if not profile_path.exists():
            self.log_message("System", f"Profile {profile_name} not found, using default behavior")
            return
        
        try:
            with open(profile_path, 'r') as f:
                self.profile_data = json.load(f)
            self.log_message("System", f"Loaded profile: {profile_name}")
        except Exception as e:
            self.log_message("Error", f"Failed to load profile: {e}")
            self.profile_data = None
    
    async def initialize_agent_process(self) -> None:
        """DEPRECATED: AgentProcess functionality now handled by daemon via COMPLETION command"""
        # The old AgentProcess was removed in the multi-socket architecture refactor
        # Composition support is now server-side in the daemon
        self.agent_process = None
    
    async def load_available_sessions(self) -> None:
        """Load list of available sessions from logs"""
        self.available_sessions.clear()
        
        logs_dir = Path('claude_logs')
        if not logs_dir.exists():
            return
        
        # Get all log files
        log_files = list(logs_dir.glob('*.jsonl'))
        log_files = [f for f in log_files if f.name != 'latest.jsonl']
        
        for log_file in sorted(log_files, key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                # Read first line to get timestamp
                with open(log_file, 'r') as f:
                    first_line = f.readline()
                    if first_line:
                        first_entry = json.loads(first_line)
                        session_id = log_file.stem
                        timestamp = first_entry.get('timestamp', 'Unknown')
                        
                        # Count messages
                        f.seek(0)
                        message_count = sum(1 for _ in f)
                        
                        self.available_sessions.append((session_id, timestamp, message_count))
            except:
                continue
        
        # Update the conversation list
        self.update_past_conversation_list()
    
    def update_past_conversation_list(self) -> None:
        """Update the past conversation browser list"""
        list_view = self.query_one("#past-conversation-list", ListView)
        list_view.clear()
        
        for session_id, timestamp, message_count in self.available_sessions[:20]:  # Show last 20
            # Format timestamp for display (convert UTC to local)
            try:
                dt = TimestampManager.parse_iso_timestamp(timestamp)
                local_dt = TimestampManager.utc_to_local(dt)
                time_str = local_dt.strftime('%Y-%m-%d %H:%M')
            except:
                time_str = timestamp[:19] if len(timestamp) > 19 else timestamp
            
            label = f"{time_str} ({message_count} messages)"
            item = ListItem(Label(label))
            item.session_id = session_id  # Store session_id on the item
            list_view.append(item)
    
    async def load_active_conversations(self) -> None:
        """Load list of active conversations from daemon"""
        try:
            # Query daemon for message bus stats
            stats = await self.chat_client.get_message_bus_stats()
            # Always scan for conversations regardless
            self.scan_recent_conversations()
            # Then update with combined info
            self.update_active_conversation_list(stats)
        except:
            # Fallback: scan for recent message_bus activity
            self.scan_recent_conversations()
    
    def scan_recent_conversations(self) -> None:
        """Scan message_bus.jsonl for recent conversations"""
        self.active_conversations.clear()
        
        message_bus_file = Path('claude_logs/message_bus.jsonl')
        if not message_bus_file.exists():
            self.log_message("System", f"No message bus file found at {message_bus_file}")
            return
        
        try:
            with open(message_bus_file, 'r') as f:
                for line in f:
                    try:
                        msg = json.loads(line)
                        conv_id = msg.get('conversation_id')
                        if conv_id and conv_id not in self.active_conversations:
                            self.active_conversations[conv_id] = {
                                'id': conv_id,
                                'participants': [],
                                'last_message': msg.get('timestamp', ''),
                                'message_count': 0
                            }
                        
                        if conv_id:
                            # Update conversation info
                            conv = self.active_conversations[conv_id]
                            from_agent = msg.get('from', 'Unknown')
                            to_agent = msg.get('to', 'Unknown')
                            
                            # Add participants if not already present
                            if from_agent not in conv['participants']:
                                conv['participants'].append(from_agent)
                            if to_agent not in conv['participants']:
                                conv['participants'].append(to_agent)
                            conv['message_count'] += 1
                            conv['last_message'] = msg.get('timestamp', conv['last_message'])
                    except:
                        continue
            
            # Log what we found
            if self.active_conversations:
                self.log_message("System", f"Found {len(self.active_conversations)} active conversations")
            else:
                self.log_message("System", "No active conversations found in message bus")
                
        except Exception as e:
            self.log_message("Error", f"Failed to scan message bus: {e}")
        
        self.update_active_conversation_list()
    
    def update_active_conversation_list(self, stats: Dict = None) -> None:
        """Update the active conversation browser list"""
        list_view = self.query_one("#active-conversation-list", ListView)
        list_view.clear()
        
        if stats and 'connected_agents' in stats:
            # Use daemon-provided stats
            for agent_id in stats['connected_agents']:
                label = f"🟢 {agent_id}"
                item = ListItem(Label(label))
                item.agent_id = agent_id
                list_view.append(item)
        
        # Add discovered conversations
        for conv_id, conv_info in sorted(self.active_conversations.items(), 
                                       key=lambda x: x[1]['last_message'], 
                                       reverse=True)[:10]:
            participants = conv_info['participants'][:2]  # Show first 2
            participant_str = " ↔ ".join(participants)
            if len(conv_info['participants']) > 2:
                participant_str += f" +{len(conv_info['participants']) - 2}"
            
            # Format last message timestamp
            time_str = ""
            if conv_info.get('last_message'):
                try:
                    dt = TimestampManager.parse_iso_timestamp(conv_info['last_message'])
                    local_dt = TimestampManager.utc_to_local(dt)
                    time_str = f" {local_dt.strftime('%m/%d %H:%M')}"
                except:
                    # Fallback for malformed timestamps
                    timestamp = conv_info['last_message']
                    if len(timestamp) >= 16:  # Basic ISO format check
                        time_str = f" {timestamp[5:10]} {timestamp[11:16]}"
            
            label = f"💬 {participant_str} ({conv_info['message_count']} msgs){time_str}"
            item = ListItem(Label(label))
            item.conversation_id = conv_id
            list_view.append(item)
        
        # Force refresh
        list_view.refresh()
    
    async def initialize_session(self) -> None:
        """Initialize session based on command line arguments"""
        if self.args.new:
            self.log_message("System", "Starting new session...")
            self.session_id = None
            self.mode = "chat"
        elif self.args.resume:
            self.session_id = self.args.resume
            self.log_message("System", f"Resuming session: {self.session_id}")
            self.mode = "chat"
        else:
            # Try to resume last session
            self.session_id = await self.get_last_session_id()
            if self.session_id:
                self.log_message("System", f"Resuming last session: {self.session_id}")
                self.mode = "chat"
            else:
                self.log_message("System", "Starting new session...")
                self.mode = "chat"
        
        # Send initial prompt if provided
        if self.args.prompt and self.mode == "chat":
            try:
                prompt_path = Path(self.args.prompt)
                if prompt_path.exists():
                    initial_prompt = prompt_path.read_text().strip()
                    self.log_message("System", f"Loaded prompt from {self.args.prompt}")
                    await self.send_message(initial_prompt)
            except Exception as e:
                self.log_message("System", f"Error loading prompt file: {e}")
    
    async def get_last_session_id(self) -> Optional[str]:
        """Get the last session ID"""
        # Check persistent file
        session_file = Path('sockets/last_session_id')
        if session_file.exists():
            try:
                session_id = session_file.read_text().strip()
                if session_id:
                    return session_id
            except:
                pass
        
        # Use first session from available sessions
        if self.available_sessions:
            return self.available_sessions[0][0]
        
        return None
    
    def log_message(self, sender: str, content: str, timestamp: str = None) -> None:
        """Log a message to the conversation view with optional timestamp"""
        try:
            conv_log = self.query_one("#conversation_log", RichLog)
        except:
            # UI not ready yet, just print to console
            print(f"{sender}: {content}")
            return
        
        # Format timestamp for display
        time_str = ""
        if timestamp:
            try:
                dt = TimestampManager.parse_iso_timestamp(timestamp)
                local_dt = TimestampManager.utc_to_local(dt)
                time_str = f" [dim]({local_dt.strftime('%H:%M:%S')})[/]"
            except:
                # Fallback if timestamp parsing fails
                time_str = f" [dim]({timestamp[:8] if len(timestamp) >= 8 else timestamp})[/]"
        
        # Format based on sender with timestamp
        if sender == "You":
            conv_log.write(f"\n[bold cyan]{sender}:{time_str}[/]")
        elif sender == "Claude":
            conv_log.write(f"\n[bold green]{sender}:{time_str}[/]")
        elif sender == "System":
            conv_log.write(f"\n[dim yellow]{sender}:{time_str}[/]")
        elif sender == "Error":
            conv_log.write(f"\n[bold red]{sender}:{time_str}[/]")
        else:
            # Other agents in multi-agent mode
            conv_log.write(f"\n[bold magenta]{sender}:{time_str}[/]")
        
        # Write content with proper formatting
        # Ensure content is a string
        content_str = str(content)
        for line in content_str.split('\n'):
            conv_log.write(f"  {line}")
        
        # Track conversation for context
        if sender in ["You", "Claude"] or (self.mode == "multi" and sender != "System"):
            entry = {
                "type": "user" if sender == "You" else "claude",
                "content": content,
                "timestamp": timestamp or TimestampManager.timestamp_utc(),
                "sender": sender
            }
            self.current_conversation.append(entry)
    
    @work(exclusive=True)
    async def send_message(self, message: str) -> None:
        """Send a message to Claude"""
        if not message.strip() or not self.daemon_connected:
            return
        
        # Don't send in replay mode
        if self.mode == "replay":
            self.log_message("System", "Cannot send messages in replay mode. Press Ctrl+N for new session.")
            return
        
        # Log user message
        self.log_message("You", message)
        
        # Handle special commands
        if message.startswith('/'):
            await self.handle_command(message)
            return
        
        if self.mode == "multi" and self.conversation_id:
            # Send via message bus
            await self.send_multi_agent_message(message)
        else:
            # Normal single-agent mode - use new multi-socket client
            try:
                # Send prompt and get response
                response, new_session_id = await self.chat_client.send_prompt(
                    prompt=message,
                    session_id=self.session_id,
                    model="sonnet"  # Could be configurable
                )
                
                # Update session ID if we got a new one
                if new_session_id:
                    self.session_id = new_session_id
                
                # Display response
                self.log_message("Claude", response)
                
                # Update metrics (rough estimates)
                self.metrics['messages'] += 2
                tokens = len(response.split()) * 1.3
                self.metrics['tokens'] += int(tokens)
                self.metrics['cost'] += tokens * 0.00001
                
            except asyncio.TimeoutError:
                self.log_message("Error", "Request timed out. Please try again.")
            except Exception as e:
                self.log_message("Error", f"Failed to get response: {str(e)}")
        
        # Update status and refresh sessions list
        self.update_status()
        await self.load_available_sessions()
    
    async def send_multi_agent_message(self, message: str) -> None:
        """Send message in multi-agent mode"""
        # TODO: Implement multi-agent message sending via message bus
        self.log_message("System", "Multi-agent messaging coming soon...")
    
    async def handle_command(self, command: str) -> None:
        """Handle special commands"""
        parts = command.split()
        cmd = parts[0].lower()
        
        if cmd == '/help':
            self.show_help_message()
        elif cmd == '/clear':
            self.action_clear_conversation()
        elif cmd == '/new':
            await self.start_new_session()
        elif cmd == '/join' and len(parts) > 1:
            conversation_id = parts[1]
            await self.join_conversation(conversation_id)
        else:
            self.log_message("System", f"Unknown command: {command}")
    
    async def start_new_session(self) -> None:
        """Start a new chat session"""
        # Disconnect from multi-agent if connected
        if self.mode == "multi" and self.agent_id:
            await self.disconnect_from_conversation()
        
        self.session_id = None
        self.mode = "chat"
        self.conversation_id = None
        self.log_message("System", "Started new session")
        self.update_status()
    
    async def join_conversation(self, conversation_id: str) -> None:
        """Join an active multi-agent conversation"""
        self.log_message("System", f"Joining conversation: {conversation_id}")
        
        # TODO: Implement actual connection to message bus
        # For now, just switch mode and show messages from message_bus.jsonl
        
        self.mode = "multi"
        self.conversation_id = conversation_id
        self.session_id = None
        
        # Clear current display
        conv_log = self.query_one("#conversation_log", RichLog)
        conv_log.clear()
        self.current_conversation.clear()
        
        # Load recent messages from this conversation
        await self.load_conversation_messages(conversation_id)
        
        self.log_message("System", f"Joined conversation: {conversation_id}")
        self.log_message("System", "Multi-agent interaction coming soon. For now, viewing conversation history.")
        
        self.update_status()
    
    async def load_conversation_messages(self, conversation_id: str) -> None:
        """Load messages from a specific conversation"""
        message_bus_file = Path('claude_logs/message_bus.jsonl')
        if not message_bus_file.exists():
            return
        
        try:
            with open(message_bus_file, 'r') as f:
                for line in f:
                    try:
                        msg = json.loads(line)
                        if msg.get('conversation_id') == conversation_id:
                            sender = msg.get('from', 'Unknown')
                            content = msg.get('content', '')
                            timestamp = msg.get('timestamp')
                            self.log_message(sender, content, timestamp)
                    except:
                        continue
        except Exception as e:
            self.log_message("Error", f"Failed to load conversation: {e}")
    
    async def disconnect_from_conversation(self) -> None:
        """Disconnect from multi-agent conversation"""
        if self.agent_id:
            try:
                # Already handled by chat_client.close()
                pass
            except:
                pass
        
        # Clean up message writer if it exists
        if self.message_writer:
            try:
                self.message_writer.close()
                await self.message_writer.wait_closed()
            except:
                pass
        
        self.agent_id = None
        self.message_reader = None
        self.message_writer = None
    
    def show_help_message(self) -> None:
        """Show help information"""
        help_text = """[bold]Available Commands:[/]
  /help          - Show this help message
  /clear         - Clear the conversation display
  /new           - Start a new session
  /join ID       - Join an active conversation

[bold]Keyboard Shortcuts:[/]
  Ctrl+Q         - Quit
  Ctrl+N         - New session
  Ctrl+B         - Browse past sessions (replay)
  Ctrl+R         - Browse active conversations (join)
  Ctrl+L         - Clear conversation
  Ctrl+E         - Export selected conversation (when browsing past)
  F1             - Show help
  Up/Down        - Navigate input history

[bold]Modes:[/]
  chat           - Single-agent conversation
  replay         - Viewing past conversation
  multi          - Multi-agent conversation (partial support)"""
        
        self.log_message("Help", help_text)
    
    def update_status(self) -> None:
        """Update the status bar"""
        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.session_id = self.session_id or "None"
        status_bar.mode = self.mode
        status_bar.conversation_id = self.conversation_id
        status_bar.tokens = self.metrics['tokens']
        status_bar.cost = self.metrics['cost']
        status_bar.update_display()
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission"""
        message = event.value.strip()
        if message:
            # Add to history
            self.input_history.append(message)
            self.history_index = len(self.input_history)
            
            # Clear input
            event.input.value = ""
            
            # Send message
            self.send_message(message)
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "send-button":
            input_field = self.query_one("#input-field", Input)
            message = input_field.value.strip()
            if message:
                self.input_history.append(message)
                self.history_index = len(self.input_history)
                input_field.value = ""
                self.send_message(message)
    
    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle conversation selection from browsers"""
        # Check which list view sent the event
        if event.list_view.id == "past-conversation-list":
            if hasattr(event.item, 'session_id'):
                self.selected_past_session = event.item.session_id
                await self.load_past_conversation(event.item.session_id)
        elif event.list_view.id == "active-conversation-list":
            if hasattr(event.item, 'conversation_id'):
                await self.join_conversation(event.item.conversation_id)
            elif hasattr(event.item, 'agent_id'):
                # TODO: Join as observer of specific agent
                self.log_message("System", f"Agent observation not yet implemented: {event.item.agent_id}")
    
    async def load_past_conversation(self, session_id: str) -> None:
        """Load and display a past conversation"""
        self.mode = "replay"
        self.session_id = session_id
        self.conversation_id = None
        
        # Clear current conversation
        conv_log = self.query_one("#conversation_log", RichLog)
        conv_log.clear()
        self.current_conversation.clear()
        
        # Load conversation from log file
        log_file = Path(f'claude_logs/{session_id}.jsonl')
        if not log_file.exists():
            self.log_message("Error", f"Session file not found: {session_id}")
            return
        
        self.log_message("System", f"Loading conversation: {session_id}")
        
        # Special handling for message_bus.jsonl
        if session_id == "message_bus":
            await self.load_message_bus_log()
        else:
            # Normal conversation log
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        entry = json.loads(line)
                        
                        # Handle different log formats
                        if 'type' in entry:
                            # Extract timestamp defensively - older convos may have timestamp bugs
                            timestamp = entry.get('timestamp')
                            
                            if entry['type'] in ['user', 'human']:
                                self.log_message("You", entry.get('content', ''), timestamp)
                            elif entry['type'] == 'claude':
                                content = entry.get('result', entry.get('content', ''))
                                self.log_message("Claude", content, timestamp)
                            elif entry['type'] == 'DIRECT_MESSAGE':
                                # Message bus format
                                sender = entry.get('from', 'Unknown')
                                content = entry.get('content', '')
                                self.log_message(sender, content, timestamp)
                        
            except Exception as e:
                self.log_message("Error", f"Failed to load conversation: {e}")
        
        self.log_message("System", "End of conversation replay. Press Ctrl+N to start new session.")
        
        # Don't auto-hide browser
        self.update_status()
    
    async def load_message_bus_log(self) -> None:
        """Special handler for message_bus.jsonl"""
        message_bus_file = Path('claude_logs/message_bus.jsonl')
        if not message_bus_file.exists():
            return
        
        self.log_message("System", "Loading inter-agent messages...")
        
        try:
            with open(message_bus_file, 'r') as f:
                for line in f:
                    try:
                        msg = json.loads(line)
                        msg_type = msg.get('type', '')
                        
                        if msg_type == 'DIRECT_MESSAGE':
                            sender = msg.get('from', 'Unknown')
                            to = msg.get('to', 'Unknown')
                            content = msg.get('content', '')
                            conv_id = msg.get('conversation_id', '')
                            timestamp = msg.get('timestamp')
                            
                            # Show conversation context with timestamp
                            self.log_message(f"{sender} → {to}", content, timestamp)
                            
                            if conv_id and conv_id != self.conversation_id:
                                self.conversation_id = conv_id
                                conv_log = self.query_one("#conversation_log", RichLog)
                                conv_log.write(f"\n[dim cyan]--- Conversation: {conv_id} ---[/]\n")
                    except:
                        continue
        except Exception as e:
            self.log_message("Error", f"Failed to load message bus: {e}")
    
    async def on_key(self, event: events.Key) -> None:
        """Handle key events for input history navigation"""
        # Only handle arrow keys when input field has focus
        input_field = self.query_one("#input-field", ChatInput)
        if self.focused == input_field:
            if event.key == "up":
                if self.history_index > 0:
                    self.history_index -= 1
                    input_field.value = self.input_history[self.history_index]
                    event.prevent_default()
                    return
            elif event.key == "down":
                if self.history_index < len(self.input_history) - 1:
                    self.history_index += 1
                    input_field.value = self.input_history[self.history_index]
                elif self.history_index == len(self.input_history) - 1:
                    self.history_index = len(self.input_history)
                    input_field.value = ""
                event.prevent_default()
                return
    
    def action_quit(self) -> None:
        """Quit the application"""
        # Schedule cleanup before exit
        if self.chat_client:
            asyncio.create_task(self._cleanup_and_exit())
        else:
            self.exit()
    
    async def _cleanup_and_exit(self):
        """Clean up connections before exiting"""
        try:
            if self.chat_client:
                await self.chat_client.close()
        except:
            pass
        self.exit()
    
    def action_new_session(self) -> None:
        """Start a new session"""
        self.run_worker(self.start_new_session())
    
    def action_toggle_past_browser(self) -> None:
        """Toggle the past conversation browser"""
        self.show_past_browser = not self.show_past_browser
        sidebar = self.query_one("#past-sidebar")
        
        if self.show_past_browser:
            # Hide active browser if open
            if self.show_active_browser:
                self.show_active_browser = False
                active_sidebar = self.query_one("#active-sidebar")
                active_sidebar.remove_class("visible")
            
            sidebar.add_class("visible")
            # Reload sessions when showing browser
            self.run_worker(self.load_available_sessions())
        else:
            sidebar.remove_class("visible")
        
        # Refocus input
        self.set_focus(self.query_one("#input-field"))
    
    def action_toggle_active_browser(self) -> None:
        """Toggle the active conversation browser"""
        self.show_active_browser = not self.show_active_browser
        sidebar = self.query_one("#active-sidebar")
        
        if self.show_active_browser:
            # Hide past browser if open
            if self.show_past_browser:
                self.show_past_browser = False
                past_sidebar = self.query_one("#past-sidebar")
                past_sidebar.remove_class("visible")
            
            sidebar.add_class("visible")
            # Reload active conversations
            self.run_worker(self.load_active_conversations())
        else:
            sidebar.remove_class("visible")
        
        # Refocus input
        self.set_focus(self.query_one("#input-field"))
    
    def action_clear_conversation(self) -> None:
        """Clear the conversation log"""
        self.query_one("#conversation_log", RichLog).clear()
        self.notify("Conversation cleared")
    
    def action_export_conversation(self) -> None:
        """Export the selected conversation to markdown"""
        if not self.selected_past_session:
            self.notify("No conversation selected to export", severity="warning")
            return
        
        # Run export in background
        self.run_worker(self.export_conversation_to_markdown())
    
    async def export_conversation_to_markdown(self) -> None:
        """Export conversation to markdown file"""
        session_id = self.selected_past_session
        
        # Determine export filename (use local time for user convenience)
        timestamp = TimestampManager.filename_timestamp(utc=False)
        export_dir = Path('exports')
        export_dir.mkdir(exist_ok=True)
        export_file = export_dir / f'conversation_{session_id}_{timestamp}.md'
        
        try:
            # Build markdown content
            md_lines = [f"# Conversation Export: {session_id}\n"]
            md_lines.append(f"*Exported on {TimestampManager.display_timestamp('%Y-%m-%d %H:%M:%S', utc=False)}*\n")
            md_lines.append("---\n")
            
            # Load conversation from log file
            log_file = Path(f'claude_logs/{session_id}.jsonl')
            if not log_file.exists():
                self.notify(f"Session file not found: {session_id}", severity="error")
                return
            
            # Special handling for message_bus
            if session_id == "message_bus":
                md_lines.append("## Inter-Agent Conversation Messages\n")
                with open(log_file, 'r') as f:
                    for line in f:
                        try:
                            msg = json.loads(line)
                            if msg.get('type') == 'DIRECT_MESSAGE':
                                sender = msg.get('from', 'Unknown')
                                to = msg.get('to', 'Unknown')
                                content = msg.get('content', '')
                                timestamp = msg.get('timestamp', '')
                                
                                # Format timestamp (convert UTC to local for display)
                                try:
                                    dt = TimestampManager.parse_iso_timestamp(timestamp)
                                    local_dt = TimestampManager.utc_to_local(dt)
                                    time_str = local_dt.strftime('%Y-%m-%d %H:%M:%S')
                                except:
                                    time_str = timestamp
                                
                                md_lines.append(f"### {time_str} - {sender} → {to}\n")
                                md_lines.append(f"{content}\n")
                                md_lines.append("---\n")
                        except:
                            continue
            else:
                # Normal conversation log
                with open(log_file, 'r') as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            timestamp = entry.get('timestamp', '')
                            
                            # Format timestamp
                            try:
                                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                            except:
                                time_str = timestamp
                            
                            if entry.get('type') in ['user', 'human']:
                                md_lines.append(f"### {time_str} - You\n")
                                md_lines.append(f"{entry.get('content', '')}\n")
                                md_lines.append("---\n")
                            elif entry.get('type') == 'claude':
                                content = entry.get('result', entry.get('content', ''))
                                md_lines.append(f"### {time_str} - Claude\n")
                                md_lines.append(f"{content}\n")
                                md_lines.append("---\n")
                        except:
                            continue
            
            # Write to file
            with open(export_file, 'w', encoding='utf-8') as f:
                f.writelines(md_lines)
            
            # Show success notification
            self.notify(f"Exported to: {export_file.name}", title="Export Complete", timeout=3)
            
        except Exception as e:
            self.notify(f"Export failed: {str(e)}", severity="error")
    
    def action_show_help(self) -> None:
        """Show help"""
        self.show_help_message()


def main():
    """Main entry point"""
    # Configure logging to file BEFORE any TUI operations to prevent screen corruption
    os.makedirs('logs', exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename='logs/chat_textual.log',
        filemode='a'
    )
    
    # Disable logging to console for all existing loggers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and handler.stream in (sys.stdout, sys.stderr):
            root_logger.removeHandler(handler)
    
    parser = argparse.ArgumentParser(description='Enhanced Claude Chat Interface (Textual)')
    parser.add_argument('--new', '-n', action='store_true', 
                       help='Start new session (default: resume last)')
    parser.add_argument('--resume', '-r', metavar='SESSION_ID',
                       help='Resume specific session ID')
    parser.add_argument('--prompt', '-p', metavar='FILENAME',
                       help='Send initial prompt from file')
    parser.add_argument('--profile', default='ksi-developer',
                       help='Agent profile to use (default: ksi-developer)')
    parser.add_argument('--test-connection', action='store_true',
                       help='Test daemon connection without starting TUI')
    parser.add_argument('--send-message', metavar='MESSAGE',
                       help='Send a single message and exit (no TUI)')
    args = parser.parse_args()
    
    # Ensure required directories exist
    os.makedirs('sockets', exist_ok=True)
    os.makedirs('claude_logs', exist_ok=True)
    os.makedirs('agent_profiles', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    # Handle non-TUI modes
    if args.test_connection or args.send_message:
        asyncio.run(test_mode(args))
        return
    
    # Redirect stdout/stderr to prevent TUI corruption - keep logging normal
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    devnull = open(os.devnull, 'w')
    
    try:
        # Redirect stdout/stderr before starting TUI
        sys.stdout = devnull
        sys.stderr = devnull
        
        # Reconfigure all loggers to use file output (handles modules that configured logging after main())
        for logger_name in logging.Logger.manager.loggerDict:
            logger = logging.getLogger(logger_name)
            for handler in logger.handlers[:]:
                if isinstance(handler, logging.StreamHandler) and handler.stream in (original_stdout, original_stderr):
                    logger.removeHandler(handler)
        
        # Run the app
        app = ChatInterface(args)
        app.run()
    except KeyboardInterrupt:
        pass
    finally:
        # Always restore stdout/stderr
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        devnull.close()


async def test_mode(args):
    """Test mode without TUI"""
    from ksi_client import SimpleChatClient
    
    print("Testing daemon connection...")
    
    # Create client
    client = SimpleChatClient(client_id=f"chat_test_{args.profile}")
    
    try:
        # Initialize client
        await client.initialize()
        print("✓ Successfully connected to daemon")
        
        # Test health check
        health = await client.health_check()
        print(f"✓ Daemon health: {health}")
        
        # Send message if provided
        if args.send_message:
            print(f"\nSending message: {args.send_message}")
            response, session_id = await client.send_prompt(args.send_message)
            print(f"\nClaude response:\n{response}")
            print(f"\nSession ID: {session_id}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return 1
    finally:
        await client.close()
    
    return 0


if __name__ == '__main__':
    main()