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

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ksi_client import EventChatClient, MultiAgentClient
from ksi_common import TimestampManager, KSIPaths

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, Label, Input, RichLog, Button, ListView, ListItem, Tree
from textual.binding import Binding
from textual import events, work

# Use KSIPaths for configuration
config = KSIPaths()


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
        
        # Metrics tracking
        self.metrics = {
            'tokens': 0,
            'cost': 0.0,
            'messages': 0
        }
        
        # Event-based clients for new architecture
        self.chat_client: Optional[EventChatClient] = None
        self.agent_client: Optional[MultiAgentClient] = None
    
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
        
        # Initialize chat client for basic operations
        self.chat_client = EventChatClient(
            client_id=f"chat_textual_{self.args.profile}",
            socket_path=str(config.socket_path)
        )
        
        # Initialize multi-agent client for coordination features
        self.agent_client = MultiAgentClient(
            client_id=f"chat_textual_agent_{self.args.profile}",
            socket_path=str(config.socket_path)
        )
        
        try:
            # Connect both clients to daemon
            await self.chat_client.connect()
            await self.agent_client.connect()
            self.daemon_connected = True
            
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
    
    
    
    
    
    def load_profile(self) -> None:
        """Load the specified profile"""
        profile_name = self.args.profile
        profile_path = config.agent_profiles_dir / f'{profile_name}.json'
        
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
    
    
    async def load_available_sessions(self) -> None:
        """Load list of available sessions from logs"""
        self.available_sessions.clear()
        
        logs_dir = config.session_logs_dir
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
            # Query daemon for active agents
            agents = await self.agent_client.list_agents()
            stats = {"agents": agents}
            # Also scan for conversations from logs
            self.scan_recent_conversations()
            # Update UI with combined info
            self.update_active_conversation_list(stats)
        except:
            # Fallback: scan for recent message_bus activity
            self.scan_recent_conversations()
    
    def scan_recent_conversations(self, max_lines: int = 1000) -> None:
        """
        Scan message_bus.jsonl for recent conversations with performance optimization.
        
        Args:
            max_lines: Maximum lines to scan from end of file (default: 1000)
        """
        self.active_conversations.clear()
        
        message_bus_file = config.session_logs_dir / 'message_bus.jsonl'
        if not message_bus_file.exists():
            self.log_message("System", f"No message bus file found at {message_bus_file}")
            return
        
        try:
            # Read recent lines from end of file for better performance
            recent_lines = self._read_recent_lines(message_bus_file, max_lines)
            
            processed_count = 0
            error_count = 0
            
            # Process lines in reverse order (most recent first)
            for line_num, line in enumerate(reversed(recent_lines)):
                try:
                    msg = json.loads(line.strip())
                    conv_id = msg.get('conversation_id')
                    
                    if conv_id:
                        # Initialize conversation if not seen
                        if conv_id not in self.active_conversations:
                            self.active_conversations[conv_id] = {
                                'id': conv_id,
                                'participants': set(),  # Use set for efficiency
                                'last_message': '',
                                'message_count': 0
                            }
                        
                        # Update conversation info
                        conv = self.active_conversations[conv_id]
                        from_agent = msg.get('from')
                        to_agent = msg.get('to')
                        timestamp = msg.get('timestamp', '')
                        
                        # Add participants (filter out None/empty)
                        if from_agent:
                            conv['participants'].add(from_agent)
                        if to_agent and to_agent != from_agent:  # Avoid duplicates
                            conv['participants'].add(to_agent)
                        
                        conv['message_count'] += 1
                        
                        # Update last_message timestamp (keep most recent)
                        if timestamp > conv['last_message']:
                            conv['last_message'] = timestamp
                    
                    processed_count += 1
                    
                except json.JSONDecodeError as e:
                    error_count += 1
                    if error_count <= 5:  # Log first few errors only
                        logger.warning(f"Malformed JSON in message bus: {e}")
                except Exception as e:
                    error_count += 1
                    if error_count <= 5:
                        logger.warning(f"Error processing message bus line: {e}")
                    continue
            
            # Convert participants sets back to lists for UI display
            for conv in self.active_conversations.values():
                conv['participants'] = list(conv['participants'])
            
            # Log scan results
            if self.active_conversations:
                self.log_message("System", f"Found {len(self.active_conversations)} active conversations "
                                          f"(scanned {processed_count} messages, {error_count} errors)")
            else:
                self.log_message("System", "No active conversations found in recent message history")
                
        except Exception as e:
            self.log_message("Error", f"Failed to scan message bus: {e}")
            logger.error(f"Error scanning message bus: {e}", exc_info=True)
        
        self.update_active_conversation_list()
    
    def _read_recent_lines(self, file_path: Path, max_lines: int) -> List[str]:
        """
        Read the last N lines from a file efficiently.
        
        Args:
            file_path: Path to the file
            max_lines: Maximum number of lines to read from end
            
        Returns:
            List of lines (newest last)
        """
        try:
            # For small files, just read everything
            file_size = file_path.stat().st_size
            if file_size < 1024 * 1024:  # Less than 1MB
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                    return lines[-max_lines:] if len(lines) > max_lines else lines
            
            # For larger files, read from end more efficiently
            lines = []
            with open(file_path, 'rb') as f:
                # Start from end of file
                f.seek(0, 2)  # Seek to end
                file_size = f.tell()
                
                # Read in chunks from end until we have enough lines
                chunk_size = min(8192, file_size)
                position = file_size
                buffer = b''
                
                while len(lines) < max_lines and position > 0:
                    # Move back by chunk size
                    position = max(0, position - chunk_size)
                    f.seek(position)
                    
                    # Read chunk and combine with previous buffer
                    chunk = f.read(min(chunk_size, file_size - position))
                    buffer = chunk + buffer
                    
                    # Split into lines
                    chunk_lines = buffer.split(b'\n')
                    
                    # Keep incomplete line for next iteration
                    if position > 0:
                        buffer = chunk_lines[0]
                        chunk_lines = chunk_lines[1:]
                    else:
                        buffer = b''
                    
                    # Convert to strings and add to lines (in reverse order)
                    for line in reversed(chunk_lines):
                        if line.strip():  # Skip empty lines
                            lines.append(line.decode('utf-8', errors='ignore'))
                            if len(lines) >= max_lines:
                                break
                
                # Return in correct order (oldest first)
                return list(reversed(lines[-max_lines:]))
                
        except Exception as e:
            logger.error(f"Error reading recent lines from {file_path}: {e}")
            # Fallback to simple read
            try:
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                    return lines[-max_lines:] if len(lines) > max_lines else lines
            except:
                return []
    
    def update_active_conversation_list(self, stats: Dict = None) -> None:
        """Update the active conversation browser list"""
        list_view = self.query_one("#active-conversation-list", ListView)
        list_view.clear()
        
        if stats and 'agents' in stats:
            # Use daemon-provided agent list
            for agent_info in stats.get('agents', []):
                agent_id = agent_info if isinstance(agent_info, str) else agent_info.get('agent_id', 'Unknown')
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
        # Check persistent file in state directory
        session_file = config.state_dir / 'last_session_id'
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
            # Normal single-agent mode - use event-based client
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
        """Send message in multi-agent mode via message bus"""
        if not self.agent_id:
            # First register as an agent
            self.agent_id = f"user_{self.args.profile}"
            if not await self.agent_client.register_as_agent(self.agent_id):
                self.log_message("Error", "Failed to register as agent")
                return
            
            # Set up message handler
            self.agent_client.on_message(self._handle_agent_message)
        
        # Send message to conversation
        try:
            # Find participants in this conversation
            participants = list(self.active_conversations.get(self.conversation_id, {}).get('participants', []))
            # Remove ourselves
            participants = [p for p in participants if p != self.agent_id]
            
            if not participants:
                self.log_message("System", "No other participants in conversation")
                return
            
            # Send to first participant (could be enhanced to broadcast)
            target = participants[0]
            
            if await self.agent_client.send_message(message, to=target, conversation_id=self.conversation_id):
                self.metrics['messages'] += 1
            else:
                self.log_message("Error", "Failed to send message")
            
        except Exception as e:
            self.log_message("Error", f"Failed to send message: {e}")
    
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
        
        self.mode = "multi"
        self.conversation_id = conversation_id
        self.session_id = None
        
        # Clear current display
        conv_log = self.query_one("#conversation_log", RichLog)
        conv_log.clear()
        self.current_conversation.clear()
        
        # Register as agent if not already
        if not self.agent_id:
            self.agent_id = f"user_{self.args.profile}"
            if not await self.agent_client.register_as_agent(self.agent_id):
                self.log_message("Error", "Failed to register as agent")
                return
            
            # Set up message handler
            self.agent_client.on_message(self._handle_agent_message)
        
        # Join the conversation
        if await self.agent_client.join_conversation(conversation_id):
            # Load recent messages from this conversation
            await self.load_conversation_messages(conversation_id)
            
            self.log_message("System", f"Joined conversation: {conversation_id}")
            self.log_message("System", "You can now send messages to other participants")
        else:
            self.log_message("Error", "Failed to join conversation")
        
        self.update_status()
    
    async def load_conversation_messages(self, conversation_id: str, limit: int = 100) -> None:
        """
        Load messages from a specific conversation with proper ordering and deduplication.
        
        Args:
            conversation_id: The conversation to load
            limit: Maximum number of recent messages to load (default: 100)
        """
        message_bus_file = config.session_logs_dir / 'message_bus.jsonl'
        if not message_bus_file.exists():
            return
        
        try:
            # First pass: collect all matching messages
            messages = []
            seen_messages = set()  # For deduplication
            
            with open(message_bus_file, 'r') as f:
                for line_num, line in enumerate(f):
                    try:
                        msg = json.loads(line.strip())
                        if msg.get('conversation_id') == conversation_id:
                            # Create unique message ID for deduplication
                            timestamp = msg.get('timestamp', '')
                            sender = msg.get('from', 'Unknown')
                            content = msg.get('content', '')
                            
                            # Simple deduplication based on timestamp + sender + content hash
                            msg_id = f"{timestamp}:{sender}:{hash(content)}"
                            
                            if msg_id not in seen_messages:
                                seen_messages.add(msg_id)
                                messages.append({
                                    'timestamp': timestamp,
                                    'sender': sender,
                                    'content': content,
                                    'raw_msg': msg
                                })
                    except json.JSONDecodeError as e:
                        # Log malformed JSON but continue
                        logger.warning(f"Malformed JSON at line {line_num + 1}: {e}")
                        continue
                    except Exception as e:
                        # Log other errors but continue
                        logger.warning(f"Error processing line {line_num + 1}: {e}")
                        continue
            
            # Sort messages by timestamp (chronological order)
            messages.sort(key=lambda m: m['timestamp'] or '1970-01-01T00:00:00Z')
            
            # Apply pagination - show most recent messages
            if len(messages) > limit:
                skipped = len(messages) - limit
                messages = messages[-limit:]  # Take last N messages
                self.log_message("System", f"Showing {limit} most recent messages ({skipped} older messages hidden)")
            
            # Display messages in chronological order
            if messages:
                self.log_message("System", f"Loading {len(messages)} messages from conversation history...")
                for msg in messages:
                    self.log_message(msg['sender'], msg['content'], msg['timestamp'])
            else:
                self.log_message("System", f"No messages found for conversation: {conversation_id}")
                
        except Exception as e:
            self.log_message("Error", f"Failed to load conversation: {e}")
            logger.error(f"Error loading conversation {conversation_id}: {e}", exc_info=True)
    
    async def disconnect_from_conversation(self) -> None:
        """Disconnect from multi-agent conversation"""
        if self.agent_id and self.agent_client:
            try:
                await self.agent_client.leave_conversation()
                await self.agent_client.unregister_agent()
            except:
                pass  # Ignore errors during disconnect
            
            self.agent_id = None
    
    def _handle_agent_message(self, sender: str, content: str, timestamp: str, conversation_id: Optional[str]):
        """Handle incoming message from another agent"""
        # Only display messages for our current conversation
        if conversation_id == self.conversation_id:
            self.log_message(sender, content, timestamp)
    
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
        """Load and display a past conversation with improved error handling and ordering"""
        self.mode = "replay"
        self.session_id = session_id
        self.conversation_id = None
        
        # Clear current conversation
        conv_log = self.query_one("#conversation_log", RichLog)
        conv_log.clear()
        self.current_conversation.clear()
        
        # Load conversation from log file
        log_file = config.session_logs_dir / f'{session_id}.jsonl'
        if not log_file.exists():
            self.log_message("Error", f"Session file not found: {session_id}")
            return
        
        self.log_message("System", f"Loading conversation: {session_id}")
        
        # Special handling for message_bus.jsonl
        if session_id == "message_bus":
            await self.load_message_bus_log()
        else:
            # Normal conversation log - load with ordering and error handling
            try:
                messages = []
                error_count = 0
                
                with open(log_file, 'r') as f:
                    for line_num, line in enumerate(f):
                        try:
                            entry = json.loads(line.strip())
                            
                            # Handle different log formats
                            if 'type' in entry:
                                timestamp = entry.get('timestamp', '')
                                
                                if entry['type'] in ['user', 'human']:
                                    messages.append({
                                        'timestamp': timestamp,
                                        'sender': 'You',
                                        'content': entry.get('content', ''),
                                        'type': 'user'
                                    })
                                elif entry['type'] == 'claude':
                                    content = entry.get('result', entry.get('content', ''))
                                    messages.append({
                                        'timestamp': timestamp,
                                        'sender': 'Claude',
                                        'content': content,
                                        'type': 'claude'
                                    })
                                elif entry['type'] == 'DIRECT_MESSAGE':
                                    # Message bus format embedded in session log
                                    sender = entry.get('from', 'Unknown')
                                    content = entry.get('content', '')
                                    messages.append({
                                        'timestamp': timestamp,
                                        'sender': sender,
                                        'content': content,
                                        'type': 'message'
                                    })
                        
                        except json.JSONDecodeError as e:
                            error_count += 1
                            if error_count <= 3:  # Log first few errors only
                                logger.warning(f"Malformed JSON in {session_id} at line {line_num + 1}: {e}")
                        except Exception as e:
                            error_count += 1
                            if error_count <= 3:
                                logger.warning(f"Error processing {session_id} line {line_num + 1}: {e}")
                            continue
                
                # Sort messages by timestamp for proper chronological order
                messages.sort(key=lambda m: m['timestamp'] or '1970-01-01T00:00:00Z')
                
                # Display messages in order
                if messages:
                    self.log_message("System", f"Loaded {len(messages)} messages from session")
                    if error_count > 0:
                        self.log_message("System", f"Note: {error_count} lines had errors and were skipped")
                    
                    for msg in messages:
                        self.log_message(msg['sender'], msg['content'], msg['timestamp'])
                else:
                    self.log_message("System", f"No messages found in session: {session_id}")
                        
            except Exception as e:
                self.log_message("Error", f"Failed to load conversation: {e}")
                logger.error(f"Error loading past conversation {session_id}: {e}", exc_info=True)
        
        self.log_message("System", "End of conversation replay. Press Ctrl+N to start new session.")
        
        # Don't auto-hide browser
        self.update_status()
    
    async def load_message_bus_log(self) -> None:
        """Special handler for message_bus.jsonl"""
        message_bus_file = config.session_logs_dir / 'message_bus.jsonl'
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
                await self.chat_client.disconnect()
            if self.agent_client:
                await self.agent_client.disconnect()
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
        export_dir = config.state_dir / 'exports'
        export_dir.mkdir(exist_ok=True)
        export_file = export_dir / f'conversation_{session_id}_{timestamp}.md'
        
        try:
            # Build markdown content
            md_lines = [f"# Conversation Export: {session_id}\n"]
            md_lines.append(f"*Exported on {TimestampManager.display_timestamp('%Y-%m-%d %H:%M:%S', utc=False)}*\n")
            md_lines.append("---\n")
            
            # Load conversation from log file
            log_file = config.session_logs_dir / f'{session_id}.jsonl'
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
    # Config directories are created as needed by KSIPaths
    
    # Configure logging to file BEFORE any TUI operations to prevent screen corruption
    log_file = config.log_dir / 'chat_textual.log'
    config.ensure_dir(log_file.parent)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename=str(log_file),
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
    parser.add_argument('--list-conversations', action='store_true',
                       help='List recent conversations and exit (no TUI)')
    parser.add_argument('--export-conversation', metavar='SESSION_ID',
                       help='Export a conversation to markdown and exit (no TUI)')
    parser.add_argument('--search-conversations', metavar='QUERY',
                       help='Search conversations for text and exit (no TUI)')
    parser.add_argument('--conversation-stats', action='store_true',
                       help='Show conversation statistics and exit (no TUI)')
    args = parser.parse_args()
    
    # Ensure additional directories exist
    config.ensure_dir(config.session_logs_dir)
    
    # Handle non-TUI modes
    if (args.test_connection or args.send_message or args.list_conversations or 
        args.export_conversation or args.search_conversations or args.conversation_stats):
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
    from ksi_client import EventChatClient, MultiAgentClient, AsyncClient
    
    print("Testing daemon connection...")
    
    # Create clients
    chat_client = EventChatClient(
        client_id=f"chat_test_{args.profile}",
        socket_path=str(config.socket_path)
    )
    
    agent_client = MultiAgentClient(
        client_id=f"chat_test_agent_{args.profile}",
        socket_path=str(config.socket_path)
    )
    
    # Create async client for conversation operations
    async_client = AsyncClient(
        client_id=f"chat_test_async_{args.profile}",
        socket_path=str(config.socket_path)
    )
    
    try:
        # Connect to daemon
        result = await chat_client.connect()
        if result:
            print("✓ Successfully connected chat client")
        else:
            print("✗ Failed to connect chat client")
            return 1
        
        result = await agent_client.connect()
        if result:
            print("✓ Successfully connected agent client")
        
        result = await async_client.connect()
        if result:
            print("✓ Successfully connected async client")
        
        # Small delay to ensure connection is stable
        await asyncio.sleep(0.1)
        
        # Test health check
        if args.test_connection:
            print("\nTesting health check...")
            health = await chat_client.health_check()
            print(f"✓ Daemon health: {health}")
            
            # Test agent list
            print("\nTesting agent list...")
            agents = await agent_client.list_agents()
            print(f"✓ Active agents: {agents}")
        
        # Send message if provided
        if args.send_message:
            print(f"\nSending message: {args.send_message}")
            response, session_id = await chat_client.send_prompt(args.send_message)
            print(f"\nClaude response:\n{response}")
            print(f"\nSession ID: {session_id}")
        
        # List conversations
        if args.list_conversations:
            print("\nListing recent conversations...")
            result = await async_client.request_event("conversation:list", {
                "limit": 10,
                "sort_by": "last_timestamp",
                "reverse": True
            })
            if result and 'error' not in result:
                conversations = result.get('conversations', [])
                print(f"\nFound {result.get('total', 0)} conversations, showing {len(conversations)}:")
                for conv in conversations:
                    print(f"  - {conv['session_id']}: {conv['message_count']} messages")
                    if conv.get('last_timestamp'):
                        dt = TimestampManager.parse_iso_timestamp(conv['last_timestamp'])
                        local_dt = TimestampManager.utc_to_local(dt)
                        print(f"    Last: {local_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print(f"✗ Failed to list conversations: {result}")
        
        # Export conversation
        if args.export_conversation:
            print(f"\nExporting conversation {args.export_conversation}...")
            result = await async_client.request_event("conversation:export", {
                "session_id": args.export_conversation,
                "format": "markdown"
            })
            if result and 'error' not in result:
                print(f"✓ Exported to: {result.get('filename')}")
                print(f"  Path: {result.get('export_path')}")
                print(f"  Size: {result.get('size_bytes', 0)} bytes")
                print(f"  Messages: {result.get('message_count', 0)}")
            else:
                print(f"✗ Failed to export conversation: {result}")
        
        # Search conversations
        if args.search_conversations:
            print(f"\nSearching conversations for '{args.search_conversations}'...")
            result = await async_client.request_event("conversation:search", {
                "query": args.search_conversations,
                "limit": 10
            })
            if result and 'error' not in result:
                results = result.get('results', [])
                print(f"\nFound matches in {result.get('total_conversations', 0)} conversations:")
                for res in results:
                    print(f"\n  {res['session_id']}: {res['match_count']} matches")
                    for match in res.get('matches', [])[:3]:
                        print(f"    - {match.get('sender', 'Unknown')}: {match.get('content_preview', '')}")
            else:
                print(f"✗ Failed to search conversations: {result}")
        
        # Show conversation stats
        if args.conversation_stats:
            print("\nGetting conversation statistics...")
            result = await async_client.request_event("conversation:stats", {})
            if result and 'error' not in result:
                print(f"\n✓ Conversation Statistics:")
                print(f"  Total conversations: {result.get('total_conversations', 0)}")
                print(f"  Total messages: {result.get('total_messages', 0)}")
                print(f"  Total size: {result.get('total_size_mb', 0):.2f} MB")
                if result.get('earliest_timestamp'):
                    dt = TimestampManager.parse_iso_timestamp(result['earliest_timestamp'])
                    local_dt = TimestampManager.utc_to_local(dt)
                    print(f"  Earliest: {local_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                if result.get('latest_timestamp'):
                    dt = TimestampManager.parse_iso_timestamp(result['latest_timestamp'])
                    local_dt = TimestampManager.utc_to_local(dt)
                    print(f"  Latest: {local_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print(f"✗ Failed to get stats: {result}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        try:
            await chat_client.disconnect()
            await agent_client.disconnect()
            await async_client.disconnect()
        except Exception as e:
            # Ignore disconnect errors - we're exiting anyway
            pass
    
    return 0


if __name__ == '__main__':
    main()