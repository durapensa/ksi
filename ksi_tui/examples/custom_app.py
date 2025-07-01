#!/usr/bin/env python3
"""
Example: Creating a custom KSI TUI application.

This example shows how to use the KSI TUI components and services
to build your own focused application.
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Button, Input

# Import KSI TUI components
from ksi_tui.components import (
    MessageList,
    ConnectionStatus,
    MetricsBar,
    Metric,
)
from ksi_tui.services import ChatService
from ksi_tui.themes import theme_manager


class CustomApp(App):
    """Example custom application using KSI TUI components."""
    
    # Use the KSI theme
    CSS = theme_manager.css + """
    /* Custom app styles */
    #main {
        padding: 1;
    }
    
    #chat-area {
        height: 1fr;
        border: round var(--surface1);
        margin-bottom: 1;
    }
    
    #input-area {
        height: 3;
        layout: horizontal;
    }
    
    #input {
        width: 1fr;
        margin-right: 1;
    }
    """
    
    def compose(self) -> ComposeResult:
        """Compose the UI using KSI components."""
        yield Header()
        
        with Container(id="main"):
            # Add a metrics bar at the top
            yield MetricsBar(
                metrics=[
                    Metric("Messages", 0, "msg", "count", icon="💬"),
                    Metric("Tokens", 0, "tok", "count", icon="🎯"),
                    Metric("Cost", 0, "USD", "currency", icon="💰"),
                ],
                layout="horizontal",
                show_progress=False,
                id="metrics"
            )
            
            # Chat area using MessageList component
            with Container(id="chat-area"):
                yield MessageList(id="messages")
            
            # Input area
            with Horizontal(id="input-area"):
                yield Input(placeholder="Type a message...", id="input")
                yield Button("Send", variant="primary", id="send")
        
        # Connection status at bottom
        yield ConnectionStatus(id="status", show_details=True)
        yield Footer()
    
    async def on_mount(self) -> None:
        """Initialize the app."""
        # Set up connection status
        status = self.query_one("#status", ConnectionStatus)
        status.set_connected(latency=25.5)
        
        # Add welcome message
        messages = self.query_one("#messages", MessageList)
        messages.add_message(
            "Welcome to the custom KSI app!",
            sender_type="system"
        )
        
        # Initialize metrics
        metrics = self.query_one("#metrics", MetricsBar)
        metrics.update_metrics({
            "Messages": 1,
            "Tokens": 0,
            "Cost": 0.0,
        })
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.value:
            # Add user message
            messages = self.query_one("#messages", MessageList)
            messages.add_message(event.value, sender_type="user")
            
            # Clear input
            event.input.value = ""
            
            # Update metrics
            metrics = self.query_one("#metrics", MetricsBar)
            metrics.update_metric("Messages", 2)
            
            # Simulate response
            messages.add_message(
                "This is a demo response!",
                sender_type="assistant"
            )
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "send":
            input_widget = self.query_one("#input", Input)
            if input_widget.value:
                # Trigger input submission
                input_widget.action_submit()


def main():
    """Run the example app."""
    app = CustomApp()
    app.run()


if __name__ == "__main__":
    main()