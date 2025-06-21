#!/usr/bin/env python3
"""
Textual-based chat interface for Claude via the daemon
Rich TUI with support for single-agent chat and multi-agent participation
"""

import asyncio
import json
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import subprocess
import time

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Static, Label, Input, RichLog, Button, ListView, ListItem, Tree
from textual.reactive import reactive
from textual.message import Message
from textual.binding import Binding
from textual import events, work
from textual.worker import Worker, WorkerState


SOCKET_PATH = os.environ.get('CLAUDE_DAEMON_SOCKET', 'sockets/claude_daemon.sock')


class ConversationBrowser(Container):
    """Browse and select past conversations"""
    
    def compose(self) -> ComposeResult:
        yield Label("Past Conversations (Click to replay)", classes="section-header")
        yield ListView(id="conversation-list")


class ConversationView(ScrollableContainer):
    """Main conversation display area"""
    
    def compose(self) -> ComposeResult:
        yield RichLog(id="conversation_log", highlight=True, markup=True, wrap=True)


class StatusBar(Static):
    """Status bar showing session info and metrics"""
    
    def __init__(self, id: str = None):
        super().__init__("", id=id)
        self.session_id = "None"
        self.mode = "browse"
        self.tokens = 0
        self.cost = 0.0
    
    def update_display(self):
        """Update the status bar display"""
        self.update(f"Session: {self.session_id} | Mode: {self.mode} | Tokens: {self.tokens:,} | Cost: ${self.cost:.4f}")


class ChatInterface(App):
    """Textual-based chat interface"""
    
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
    }
    
    #sidebar {
        width: 40;
        border-right: solid $primary;
        padding: 1;
        display: none;
    }
    
    #sidebar.visible {
        display: block;
    }
    
    #conversation-list {
        height: 1fr;
        background: $surface;
    }
    
    #conversation-list > ListItem {
        padding: 0 1;
    }
    
    #conversation-list > ListItem.--highlight {
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
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
        border-top: solid $primary;
        dock: bottom;
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
        Binding("ctrl+b", "toggle_browser", "Browse Sessions"),
        Binding("ctrl+l", "clear_conversation", "Clear"),
        Binding("f1", "show_help", "Help"),
        Binding("escape", "escape", "Close Browser", show=False),
    ]
    
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.session_id: Optional[str] = None
        self.mode = "chat"  # chat, browse, or replay
        self.show_browser = False
        self.input_history: List[str] = []
        self.history_index = -1
        self.daemon_connected = False
        self.current_conversation: List[Dict] = []
        self.available_sessions: List[Tuple[str, str, int]] = []  # (session_id, timestamp, message_count)
        self.profile_data: Optional[Dict] = None
        
        # Metrics tracking
        self.metrics = {
            'tokens': 0,
            'cost': 0.0,
            'messages': 0
        }
    
    def compose(self) -> ComposeResult:
        """Create the UI layout"""
        # Header
        with Container(id="header-container"):
            yield Label("🤖 Claude Chat (Textual) - Press F1 for help", classes="section-header")
        
        # Main content area
        with Container(id="main-container"):
            # Sidebar for conversation browser
            with Container(id="sidebar"):
                yield ConversationBrowser()
            
            # Chat area
            with Container(id="chat-container"):
                yield ConversationView()
                
                # Input area
                with Container(id="input-container"):
                    yield Input(
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
        
        # Connect to daemon
        self.daemon_connected = await self.connect_to_daemon()
        
        if self.daemon_connected:
            # Load available sessions
            await self.load_available_sessions()
            
            # Initialize session based on arguments
            await self.initialize_session()
            
            self.update_status()
        else:
            self.log_message("Error", "Failed to connect to daemon. Please check if daemon is running.")
    
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
        
        # Start daemon
        self.log_message("System", "Starting daemon...")
        subprocess.Popen(['python3', 'daemon.py'], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL,
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
            # Test connection
            reader, writer = await asyncio.open_unix_connection(SOCKET_PATH)
            writer.close()
            await writer.wait_closed()
            return True
        except Exception as e:
            return False
    
    async def send_to_daemon(self, command: str) -> str:
        """Send command to daemon and get response"""
        try:
            # Create new connection for each command
            reader, writer = await asyncio.open_unix_connection(SOCKET_PATH)
            
            # Ensure command ends with newline
            if not command.endswith('\n'):
                command += '\n'
            
            writer.write(command.encode())
            await writer.drain()
            writer.write_eof()
            
            # Read full response
            response = await reader.read()
            
            writer.close()
            await writer.wait_closed()
            
            return response.decode().strip()
            
        except Exception as e:
            return json.dumps({"error": f"Command failed: {str(e)}"})
    
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
    
    def compose_prompt(self, user_message: str) -> str:
        """Compose prompt using profile template if available"""
        if not self.profile_data or 'prompt_template' not in self.profile_data:
            return user_message
        
        # Get the template
        template = self.profile_data['prompt_template']
        
        # Build context from conversation history
        context = ""
        if self.session_id and self.current_conversation:
            # Include last few messages for context
            recent_messages = self.current_conversation[-4:]  # Last 2 exchanges
            context_parts = []
            for msg in recent_messages:
                if msg.get('type') == 'user':
                    context_parts.append(f"User: {msg.get('content', '')}")
                elif msg.get('type') == 'claude':
                    context_parts.append(f"Claude: {msg.get('content', '')[:200]}...")
            context = "\n".join(context_parts)
        
        # Format the template
        try:
            formatted_prompt = template.format(
                task=user_message,
                context=context if context else "No previous context"
            )
            return formatted_prompt
        except KeyError as e:
            self.log_message("Error", f"Profile template error: {e}")
            return user_message
    
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
                # Read first and last lines to get session info
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        first_line = json.loads(lines[0])
                        session_id = log_file.stem
                        timestamp = first_line.get('timestamp', 'Unknown')
                        message_count = len(lines)
                        
                        self.available_sessions.append((session_id, timestamp, message_count))
            except:
                continue
        
        # Update the conversation list
        self.update_conversation_list()
    
    def update_conversation_list(self) -> None:
        """Update the conversation browser list"""
        list_view = self.query_one("#conversation-list", ListView)
        list_view.clear()
        
        for session_id, timestamp, message_count in self.available_sessions[:20]:  # Show last 20
            # Format timestamp
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_str = dt.strftime('%Y-%m-%d %H:%M')
            except:
                time_str = timestamp[:19] if len(timestamp) > 19 else timestamp
            
            label = f"{time_str} ({message_count} messages)"
            item = ListItem(Label(label))
            item.session_id = session_id  # Store session_id on the item
            list_view.append(item)
    
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
    
    def log_message(self, sender: str, content: str) -> None:
        """Log a message to the conversation view"""
        try:
            conv_log = self.query_one("#conversation_log", RichLog)
        except:
            # UI not ready yet, just print to console
            print(f"{sender}: {content}")
            return
        
        # Format based on sender
        if sender == "You":
            conv_log.write(f"\n[bold cyan]{sender}:[/]")
        elif sender == "Claude":
            conv_log.write(f"\n[bold green]{sender}:[/]")
        elif sender == "System":
            conv_log.write(f"\n[dim yellow]{sender}:[/]")
        elif sender == "Error":
            conv_log.write(f"\n[bold red]{sender}:[/]")
        else:
            conv_log.write(f"\n[dim]{sender}:[/]")
        
        # Write content with proper formatting
        for line in content.split('\n'):
            conv_log.write(f"  {line}")
        
        # Track conversation for context
        if sender in ["You", "Claude"]:
            entry = {
                "type": "user" if sender == "You" else "claude",
                "content": content,
                "timestamp": datetime.now().isoformat()
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
        
        # Compose prompt using profile if available
        composed_prompt = self.compose_prompt(message)
        
        # Build spawn command
        if self.session_id:
            command = f"SPAWN:{self.session_id}:{composed_prompt}"
        else:
            command = f"SPAWN::{composed_prompt}"
        
        # Send command
        response = await self.send_to_daemon(command)
        
        try:
            output = json.loads(response)
            
            # Extract session_id
            new_session_id = output.get('sessionId') or output.get('session_id')
            if new_session_id:
                self.session_id = new_session_id
            
            # Display response
            if 'error' in output:
                self.log_message("Error", output['error'])
            elif 'result' in output:
                self.log_message("Claude", output['result'])
            elif 'content' in output:
                self.log_message("Claude", output['content'])
            else:
                self.log_message("System", "No response content")
            
            # Update metrics
            self.metrics['messages'] += 2
            if 'result' in output or 'content' in output:
                content = output.get('result', output.get('content', ''))
                tokens = len(content.split()) * 1.3
                self.metrics['tokens'] += int(tokens)
                self.metrics['cost'] += tokens * 0.00001
            
        except json.JSONDecodeError:
            self.log_message("Error", f"Invalid response from daemon")
        
        # Update status and refresh sessions list
        self.update_status()
        await self.load_available_sessions()
    
    async def handle_command(self, command: str) -> None:
        """Handle special commands"""
        parts = command.split()
        cmd = parts[0].lower()
        
        if cmd == '/help':
            self.show_help_message()
        elif cmd == '/clear':
            self.action_clear_conversation()
        elif cmd == '/new':
            self.session_id = None
            self.mode = "chat"
            self.log_message("System", "Started new session")
            self.update_status()
        else:
            self.log_message("System", f"Unknown command: {command}")
    
    def show_help_message(self) -> None:
        """Show help information"""
        help_text = """[bold]Available Commands:[/]
  /help          - Show this help message
  /clear         - Clear the conversation display
  /new           - Start a new session

[bold]Keyboard Shortcuts:[/]
  Ctrl+Q         - Quit
  Ctrl+N         - New session
  Ctrl+B         - Browse/replay past sessions
  Ctrl+L         - Clear conversation
  F1             - Show help
  Escape         - Close browser (when open)
  Up/Down        - Navigate input history"""
        
        self.log_message("Help", help_text)
    
    def update_status(self) -> None:
        """Update the status bar"""
        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.session_id = self.session_id or "None"
        status_bar.mode = self.mode
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
        """Handle conversation selection from browser"""
        if hasattr(event.item, 'session_id'):
            await self.load_conversation(event.item.session_id)
    
    async def load_conversation(self, session_id: str) -> None:
        """Load and display a past conversation"""
        self.mode = "replay"
        self.session_id = session_id
        
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
        
        try:
            with open(log_file, 'r') as f:
                for line in f:
                    entry = json.loads(line)
                    
                    if entry.get('type') == 'user':
                        self.log_message("You", entry.get('content', ''))
                    elif entry.get('type') == 'human':
                        # Handle alternate format
                        self.log_message("You", entry.get('content', ''))
                    elif entry.get('type') == 'claude':
                        content = entry.get('result', entry.get('content', ''))
                        self.log_message("Claude", content)
                    
            self.log_message("System", "End of conversation replay. Press Ctrl+N to start new session.")
            
        except Exception as e:
            self.log_message("Error", f"Failed to load conversation: {e}")
        
        # Hide browser after loading
        self.show_browser = False
        sidebar = self.query_one("#sidebar")
        sidebar.remove_class("visible")
        
        self.update_status()
    
    async def on_key(self, event: events.Key) -> None:
        """Handle key events"""
        if event.key == "up":
            if self.history_index > 0:
                self.history_index -= 1
                input_field = self.query_one("#input-field", Input)
                input_field.value = self.input_history[self.history_index]
        elif event.key == "down":
            if self.history_index < len(self.input_history) - 1:
                self.history_index += 1
                input_field = self.query_one("#input-field", Input)
                input_field.value = self.input_history[self.history_index]
            elif self.history_index == len(self.input_history) - 1:
                self.history_index = len(self.input_history)
                input_field = self.query_one("#input-field", Input)
                input_field.value = ""
    
    def action_quit(self) -> None:
        """Quit the application"""
        self.exit()
    
    def action_new_session(self) -> None:
        """Start a new session"""
        self.session_id = None
        self.mode = "chat"
        self.log_message("System", "Started new session")
        self.update_status()
        
        # Clear conversation
        self.query_one("#conversation_log", RichLog).clear()
        
        # Hide browser if shown
        if self.show_browser:
            self.action_toggle_browser()
    
    def action_toggle_browser(self) -> None:
        """Toggle the conversation browser"""
        self.show_browser = not self.show_browser
        sidebar = self.query_one("#sidebar")
        
        if self.show_browser:
            sidebar.add_class("visible")
            # Reload sessions when showing browser
            self.run_worker(self.load_available_sessions())
        else:
            sidebar.remove_class("visible")
        
        # Refocus input
        self.set_focus(self.query_one("#input-field"))
    
    def action_clear_conversation(self) -> None:
        """Clear the conversation log"""
        self.query_one("#conversation_log", RichLog).clear()
        self.notify("Conversation cleared")
    
    def action_show_help(self) -> None:
        """Show help"""
        self.show_help_message()
    
    def action_escape(self) -> None:
        """Handle escape key"""
        if self.show_browser:
            self.action_toggle_browser()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Claude Chat Interface (Textual)')
    parser.add_argument('--new', '-n', action='store_true', 
                       help='Start new session (default: resume last)')
    parser.add_argument('--resume', '-r', metavar='SESSION_ID',
                       help='Resume specific session ID')
    parser.add_argument('--prompt', '-p', metavar='FILENAME',
                       help='Send initial prompt from file')
    parser.add_argument('--profile', default='ksi-developer',
                       help='Agent profile to use (default: ksi-developer)')
    args = parser.parse_args()
    
    # Ensure required directories exist
    os.makedirs('sockets', exist_ok=True)
    os.makedirs('claude_logs', exist_ok=True)
    os.makedirs('agent_profiles', exist_ok=True)
    
    # Run the app
    try:
        app = ChatInterface(args)
        app.run()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()