"""
MessageBubble - Beautiful message display component for chat interfaces.

Features:
- Automatic sender-based styling
- Timestamp display
- Copy to clipboard support
- Syntax highlighting for code blocks
- Smooth animations
"""

from datetime import datetime
from typing import Optional, Literal

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Static
from textual.reactive import reactive
from textual import events
from textual.events import Click


MessageType = Literal["user", "assistant", "system", "error"]


class MessageBubble(Container):
    """A beautiful message bubble with sender info and timestamp."""
    
    # CSS classes for different message types
    BUBBLE_CLASSES = {
        "user": ["message", "message-user"],
        "assistant": ["message", "message-assistant"], 
        "system": ["message", "message-system"],
        "error": ["message", "message-error"],
    }
    
    # Sender display names
    SENDER_NAMES = {
        "user": "You",
        "assistant": "Claude",
        "system": "System",
        "error": "Error",
    }
    
    # Reactive properties
    sender_type: reactive[MessageType] = reactive("user")
    
    def __init__(
        self,
        content: str,
        sender_type: MessageType = "user",
        sender_name: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        """
        Initialize a message bubble.
        
        Args:
            content: The message content (supports markdown)
            sender_type: Type of sender (user, assistant, system, error)
            sender_name: Custom sender name (optional)
            timestamp: Message timestamp (defaults to now)
            name: Widget name
            id: Widget ID
            classes: Additional CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.content = content
        self.sender_type = sender_type
        self.sender_name = sender_name or self.SENDER_NAMES.get(sender_type, "Unknown")
        self.timestamp = timestamp or datetime.now()
        
        # Apply minimal CSS classes
        bubble_classes = self.BUBBLE_CLASSES.get(sender_type, ["message"])
        for css_class in bubble_classes:
            self.add_class(css_class)
    
    def compose(self) -> ComposeResult:
        """Compose the message bubble with minimal layout."""
        # Single static widget with sender and content
        yield Static(f"[{self.sender_name}] {self.content}", markup=False)
    
    def _format_timestamp(self, timestamp: datetime) -> str:
        """Format timestamp for display."""
        # If today, show time only
        if timestamp.date() == datetime.now().date():
            return timestamp.strftime("%H:%M:%S")
        # Otherwise show date and time
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    
    async def on_click(self, event: Click) -> None:
        """Handle click events for copying content."""
        if event.ctrl:
            # Copy content to clipboard
            try:
                import pyperclip
                pyperclip.copy(self.content)
                self.notify("Message copied to clipboard", severity="information")
            except ImportError:
                # pyperclip not available, try native clipboard
                self.app.copy_to_clipboard(self.content)
                self.notify("Message copied to clipboard", severity="information")


class MessageList(Container):
    """Container for displaying a list of messages with auto-scroll."""
    
    def __init__(
        self,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        """Initialize the message list."""
        super().__init__(name=name, id=id, classes=classes)
        self.can_focus = True
        # Track if we should auto-scroll
        self._auto_scroll = True
    
    def add_message(
        self,
        content: str,
        sender_type: MessageType = "user",
        sender_name: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> MessageBubble:
        """
        Add a new message to the list.
        
        Args:
            content: Message content
            sender_type: Type of sender
            sender_name: Custom sender name
            timestamp: Message timestamp
            
        Returns:
            The created MessageBubble widget
        """
        bubble = MessageBubble(
            content=content,
            sender_type=sender_type,
            sender_name=sender_name,
            timestamp=timestamp,
        )
        
        self.mount(bubble)
        
        # Auto-scroll to bottom if enabled
        if self._auto_scroll:
            self.scroll_end(animate=True)
        
        return bubble
    
    def clear_messages(self) -> None:
        """Clear all messages from the list."""
        self.remove_children()
    
    def watch_scroll_y(self, scroll_y: float) -> None:
        """Track scroll position to determine auto-scroll behavior."""
        # If user scrolls up, disable auto-scroll
        # If they scroll to bottom, re-enable it
        viewport = self.size.height
        max_scroll = self.virtual_size.height - viewport
        
        # Consider "at bottom" if within 10 lines of the end
        self._auto_scroll = (max_scroll - scroll_y) < 10


# Convenience CSS for message components - simplified to avoid spacing issues
MESSAGE_CSS = """
/* Message list container */
MessageList {
    height: 100%;
    overflow-y: scroll;
}

/* Message bubble base - minimal styling */
.message {
    width: 100%;
}
"""