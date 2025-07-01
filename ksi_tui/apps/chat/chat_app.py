"""
KSI Chat - A beautiful, focused chat interface for Claude conversations.

Features:
- Clean, distraction-free interface
- Session management with easy switching
- Real-time connection status
- Keyboard-first design
- Beautiful message rendering
"""

from typing import Optional, List
from datetime import datetime
import asyncio

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Input, Button, Label, LoadingIndicator
from textual.message import Message
from textual import events, work
from textual.worker import Worker, WorkerState

# Import our components and services
from ksi_tui.components import (
    MessageList,
    ConnectionStatus,
    MessageType,
)
from ksi_tui.services import (
    ChatService,
    ChatMessage,
    ChatSession,
    ChatError,
    ConnectionError as ServiceConnectionError,
)
from ksi_tui.themes import theme_manager


class ChatInput(Input):
    """Enhanced input with better keyboard handling."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.history: List[str] = []
        self.history_index = -1
    
    def on_key(self, event: events.Key) -> None:
        """Handle special keys for history navigation."""
        if event.key == "up":
            if self.history and self.history_index < len(self.history) - 1:
                self.history_index += 1
                self.value = self.history[-(self.history_index + 1)]
                self.cursor_position = len(self.value)
                event.prevent_default()
        elif event.key == "down":
            if self.history_index > 0:
                self.history_index -= 1
                self.value = self.history[-(self.history_index + 1)]
                self.cursor_position = len(self.value)
                event.prevent_default()
            elif self.history_index == 0:
                self.history_index = -1
                self.value = ""
                event.prevent_default()
    
    def add_to_history(self, text: str) -> None:
        """Add text to history."""
        if text and (not self.history or self.history[-1] != text):
            self.history.append(text)
            if len(self.history) > 100:  # Keep last 100 entries
                self.history.pop(0)
        self.history_index = -1


class SessionInfo(Container):
    """Displays current session information."""
    
    def compose(self) -> ComposeResult:
        """Compose the session info display."""
        with Horizontal(classes="session-info"):
            yield Label("Session:", classes="session-label")
            yield Label("New Session", id="session-id", classes="session-value")
            yield Button("New", id="new-session", classes="session-button")
            yield Button("Switch", id="switch-session", classes="session-button")


class ChatApp(App):
    """The main chat application."""
    
    CSS = theme_manager.css + """
    /* App-specific styles */
    ChatApp {
        background: var(--base);
    }
    
    /* Header */
    Header {
        background: var(--mantle);
        color: var(--text);
    }
    
    /* Main layout */
    #main-container {
        height: 100%;
        background: var(--base);
    }
    
    /* Session info bar */
    .session-info {
        height: 3;
        background: var(--surface0);
        border-bottom: tall var(--surface1);
        padding: 1;
        align: center middle;
    }
    
    .session-label {
        width: auto;
        margin-right: 1;
        color: var(--subtext0);
    }
    
    .session-value {
        width: auto;
        margin-right: 2;
        color: var(--lavender);
        text-style: bold;
    }
    
    .session-button {
        width: auto;
        height: 1;
        min-width: 8;
        margin: 0 1;
    }
    
    /* Message area */
    #message-container {
        height: 1fr;
        background: var(--base);
        border: round var(--surface0);
        margin: 1;
    }
    
    MessageList {
        padding: 1;
        scrollbar-size: 1 1;
    }
    
    /* Input area */
    #input-container {
        height: 5;
        padding: 0 1 1 1;
    }
    
    #input-wrapper {
        height: 3;
        layout: horizontal;
        align: center middle;
    }
    
    #message-input {
        width: 1fr;
        height: 3;
        margin-right: 1;
    }
    
    #send-button {
        width: 10;
        height: 3;
    }
    
    /* Connection status */
    #connection-container {
        dock: bottom;
        height: 1;
        background: var(--surface0);
        border-top: tall var(--surface1);
        padding: 0 1;
        align: left middle;
    }
    
    /* Loading state */
    .thinking-indicator {
        dock: bottom;
        height: 1;
        background: var(--surface0);
        align: center middle;
        display: none;
    }
    
    .thinking-indicator.visible {
        display: block;
    }
    
    /* Animations */
    @keyframes pulse {
        0% { opacity: 1.0; }
        50% { opacity: 0.5; }
        100% { opacity: 1.0; }
    }
    
    .thinking {
        animation: pulse 1.5s ease-in-out infinite;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+n", "new_session", "New Session", priority=True),
        Binding("ctrl+s", "switch_session", "Switch Session"),
        Binding("ctrl+e", "export_session", "Export"),
        Binding("ctrl+l", "clear_messages", "Clear"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("f1", "help", "Help"),
    ]
    
    def __init__(
        self,
        client_id: str = "ksi-chat",
        model: str = "sonnet",
    ):
        """Initialize the chat app."""
        super().__init__()
        self.client_id = client_id
        self.model = model
        
        # Services
        self.chat_service = ChatService(
            client_id=client_id,
            model=model,
        )
        
        # State
        self.current_session_id: Optional[str] = None
        self.is_thinking = False
        self._send_worker: Optional[Worker] = None
    
    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield Header(show_clock=True)
        
        with Container(id="main-container"):
            # Session info
            yield SessionInfo()
            
            # Message area
            with ScrollableContainer(id="message-container"):
                yield MessageList(id="messages")
            
            # Thinking indicator
            with Container(classes="thinking-indicator", id="thinking"):
                yield Label("Claude is thinking...", classes="thinking")
            
            # Input area
            with Container(id="input-container"):
                with Horizontal(id="input-wrapper"):
                    yield ChatInput(
                        placeholder="Type your message...",
                        id="message-input",
                    )
                    yield Button(
                        "Send",
                        id="send-button",
                        variant="primary",
                        disabled=True,
                    )
        
        # Connection status
        with Container(id="connection-container"):
            yield ConnectionStatus(id="connection-status", compact=False)
        
        yield Footer()
    
    async def on_mount(self) -> None:
        """Initialize when app starts."""
        # Set window title
        self.title = "KSI Chat"
        self.sub_title = "Chat with Claude"
        
        # Focus input
        self.query_one("#message-input").focus()
        
        # Connect to daemon
        await self._connect_to_daemon()
    
    @work(exclusive=True)
    async def _connect_to_daemon(self) -> None:
        """Connect to the KSI daemon."""
        status = self.query_one("#connection-status", ConnectionStatus)
        status.set_connecting()
        
        try:
            await self.chat_service.connect()
            status.set_connected()
            
            # Enable send button
            self.query_one("#send-button", Button).disabled = False
            
            # Add system message
            self._add_system_message("Connected to KSI daemon. Ready to chat!")
            
            # Load last session if available
            sessions = await self.chat_service.list_sessions(limit=1)
            if sessions:
                await self._resume_session(sessions[0].session_id)
            
        except ServiceConnectionError as e:
            status.set_error(str(e))
            self._add_system_message(f"Failed to connect: {e}")
        except Exception as e:
            status.set_error("Connection failed")
            self._add_system_message(f"Unexpected error: {e}")
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.value.strip():
            self._send_message(event.value)
            event.input.value = ""
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "send-button":
            input_widget = self.query_one("#message-input", ChatInput)
            if input_widget.value.strip():
                self._send_message(input_widget.value)
                input_widget.value = ""
        elif event.button.id == "new-session":
            self.action_new_session()
        elif event.button.id == "switch-session":
            self.action_switch_session()
    
    @work(exclusive=True, thread=True)
    async def _send_message(self, content: str) -> None:
        """Send a message to Claude."""
        # Add to history
        input_widget = self.query_one("#message-input", ChatInput)
        input_widget.add_to_history(content)
        
        # Disable input while processing
        input_widget.disabled = True
        send_button = self.query_one("#send-button", Button)
        send_button.disabled = True
        
        # Show thinking indicator
        self._set_thinking(True)
        
        try:
            # Send message
            response, session_id = await self.chat_service.send_message(content)
            
            # Update session
            if session_id != self.current_session_id:
                self.current_session_id = session_id
                self._update_session_display(session_id)
            
            # Message display is handled by the service callbacks
            
        except ChatError as e:
            self._add_system_message(f"Error: {e}", is_error=True)
        except Exception as e:
            self._add_system_message(f"Unexpected error: {e}", is_error=True)
        finally:
            # Re-enable input
            input_widget.disabled = False
            send_button.disabled = False
            input_widget.focus()
            
            # Hide thinking indicator
            self._set_thinking(False)
    
    def _set_thinking(self, thinking: bool) -> None:
        """Show/hide thinking indicator."""
        self.is_thinking = thinking
        indicator = self.query_one("#thinking", Container)
        if thinking:
            indicator.add_class("visible")
        else:
            indicator.remove_class("visible")
    
    def _add_system_message(self, content: str, is_error: bool = False) -> None:
        """Add a system message."""
        messages = self.query_one("#messages", MessageList)
        message_type = "error" if is_error else "system"
        messages.add_message(
            content=content,
            sender_type=message_type,
            sender_name="System",
        )
    
    def _update_session_display(self, session_id: str) -> None:
        """Update the session ID display."""
        session_label = self.query_one("#session-id", Label)
        # Show shortened session ID
        display_id = f"{session_id[:8]}..." if len(session_id) > 8 else session_id
        session_label.update(display_id)
    
    async def _resume_session(self, session_id: str) -> None:
        """Resume a previous session."""
        try:
            # Load session messages
            messages = await self.chat_service.get_session_messages(session_id)
            
            # Clear current messages
            message_list = self.query_one("#messages", MessageList)
            message_list.clear_messages()
            
            # Add historical messages
            for msg in messages:
                sender_type = "user" if msg.sender == "user" else "assistant"
                message_list.add_message(
                    content=msg.content,
                    sender_type=sender_type,
                    timestamp=msg.timestamp,
                )
            
            # Update state
            self.current_session_id = session_id
            self._update_session_display(session_id)
            
            self._add_system_message(f"Resumed session: {session_id[:8]}...")
            
        except Exception as e:
            self._add_system_message(f"Failed to resume session: {e}", is_error=True)
    
    def action_new_session(self) -> None:
        """Start a new session."""
        # Clear messages
        message_list = self.query_one("#messages", MessageList)
        message_list.clear_messages()
        
        # Reset session
        self.current_session_id = None
        self._update_session_display("New Session")
        
        # Start new session in service
        asyncio.create_task(self.chat_service.start_new_session())
        
        self._add_system_message("Started new session")
    
    def action_switch_session(self) -> None:
        """Switch to a different session."""
        # TODO: Implement session picker dialog
        self._add_system_message("Session switching coming soon!")
    
    def action_export_session(self) -> None:
        """Export current session."""
        if self.current_session_id:
            asyncio.create_task(self._export_session())
        else:
            self._add_system_message("No active session to export", is_error=True)
    
    async def _export_session(self) -> None:
        """Export the current session."""
        try:
            path = await self.chat_service.export_session(
                self.current_session_id,
                format="markdown"
            )
            if path:
                self._add_system_message(f"Session exported to: {path}")
            else:
                self._add_system_message("Export failed", is_error=True)
        except Exception as e:
            self._add_system_message(f"Export error: {e}", is_error=True)
    
    def action_clear_messages(self) -> None:
        """Clear message display (not the session)."""
        message_list = self.query_one("#messages", MessageList)
        message_list.clear_messages()
        self._add_system_message("Display cleared (session unchanged)")
    
    def action_help(self) -> None:
        """Show help information."""
        help_text = """**Keyboard Shortcuts:**
• Ctrl+N - New session
• Ctrl+S - Switch session  
• Ctrl+E - Export session
• Ctrl+L - Clear display
• Ctrl+Q - Quit
• F1 - This help

**Tips:**
• Use ↑/↓ to navigate input history
• Click messages while holding Ctrl to copy
• Sessions are automatically saved"""
        
        self._add_system_message(help_text)
    
    def action_quit(self) -> None:
        """Quit the application."""
        asyncio.create_task(self._cleanup_and_exit())
    
    async def _cleanup_and_exit(self) -> None:
        """Clean up and exit."""
        try:
            await self.chat_service.disconnect()
        except Exception:
            pass
        self.exit()
    
    async def on_mount(self) -> None:
        """Setup when app is mounted."""
        # Set up message handler
        def handle_message(msg: ChatMessage):
            # This runs in the service thread, so we need to post to main thread
            self.call_from_thread(self._display_message, msg)
        
        self.chat_service.add_message_handler(handle_message)
        
        # Call parent mount
        await super().on_mount()
    
    def _display_message(self, msg: ChatMessage) -> None:
        """Display a message in the UI."""
        messages = self.query_one("#messages", MessageList)
        
        # Map sender to message type
        if msg.sender == "user":
            sender_type = "user"
        elif msg.sender == "assistant":
            sender_type = "assistant"
        else:
            sender_type = "system"
        
        messages.add_message(
            content=msg.content,
            sender_type=sender_type,
            timestamp=msg.timestamp,
        )


def main():
    """Run the chat application."""
    app = ChatApp()
    app.run()


if __name__ == "__main__":
    main()