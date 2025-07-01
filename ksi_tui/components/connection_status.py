"""
ConnectionStatus - Real-time connection status indicator.

Features:
- Animated connection state display
- Automatic reconnection indication
- Latency display
- Error state handling
- Compact and informative
"""

from typing import Optional, Literal
from datetime import datetime, timedelta
from enum import Enum

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static
from textual.reactive import reactive
from textual.timer import Timer


class ConnectionState(Enum):
    """Connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class ConnectionStatus(Horizontal):
    """Displays connection status with visual indicators."""
    
    # State configuration
    STATE_CONFIG = {
        ConnectionState.DISCONNECTED: {
            "icon": "⚪",
            "text": "Disconnected",
            "color": "dim",
            "pulse": False,
        },
        ConnectionState.CONNECTING: {
            "icon": "🟡",
            "text": "Connecting...",
            "color": "yellow",
            "pulse": True,
        },
        ConnectionState.CONNECTED: {
            "icon": "🟢",
            "text": "Connected",
            "color": "green",
            "pulse": False,
        },
        ConnectionState.RECONNECTING: {
            "icon": "🟠",
            "text": "Reconnecting...",
            "color": "yellow",
            "pulse": True,
        },
        ConnectionState.ERROR: {
            "icon": "🔴",
            "text": "Error",
            "color": "red",
            "pulse": False,
        },
    }
    
    # Reactive properties
    state: reactive[ConnectionState] = reactive(ConnectionState.DISCONNECTED)
    latency: reactive[Optional[float]] = reactive(None)
    last_error: reactive[Optional[str]] = reactive(None)
    
    def __init__(
        self,
        *,
        show_latency: bool = True,
        show_details: bool = True,
        compact: bool = False,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        """
        Initialize connection status.
        
        Args:
            show_latency: Whether to show latency when connected
            show_details: Whether to show detailed status text
            compact: Use compact display mode
            name: Widget name
            id: Widget ID
            classes: Additional CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.show_latency = show_latency
        self.show_details = show_details
        self.compact = compact
        
        # Animation state
        self._pulse_timer: Optional[Timer] = None
        self._pulse_on = True
        
        # Connection tracking
        self._connected_since: Optional[datetime] = None
        self._last_activity: Optional[datetime] = None
        self._reconnect_count = 0
    
    def compose(self) -> ComposeResult:
        """Compose the status display."""
        yield Static("", id="status-icon", classes="connection-icon")
        
        if not self.compact:
            yield Static("", id="status-text", classes="connection-text")
            
            if self.show_latency:
                yield Static("", id="status-latency", classes="connection-latency")
            
            if self.show_details:
                yield Static("", id="status-details", classes="connection-details")
    
    def watch_state(self, old_state: ConnectionState, new_state: ConnectionState) -> None:
        """React to state changes."""
        config = self.STATE_CONFIG[new_state]
        
        # Update icon
        icon_widget = self.query_one("#status-icon", Static)
        icon_widget.update(config["icon"])
        icon_widget.remove_class("pulse")
        
        # Update text if not compact
        if not self.compact:
            text_widget = self.query_one("#status-text", Static)
            text_widget.update(config["text"])
            text_widget.set_classes(f"connection-text status-{config['color']}")
        
        # Handle pulse animation
        if config["pulse"]:
            self._start_pulse()
            icon_widget.add_class("pulse")
        else:
            self._stop_pulse()
        
        # Track connection time
        if new_state == ConnectionState.CONNECTED:
            self._connected_since = datetime.now()
            self._reconnect_count = 0
        elif old_state == ConnectionState.CONNECTED:
            self._connected_since = None
            if new_state == ConnectionState.RECONNECTING:
                self._reconnect_count += 1
        
        # Update details
        self._update_details()
    
    def watch_latency(self, old_latency: Optional[float], new_latency: Optional[float]) -> None:
        """React to latency changes."""
        if self.show_latency and not self.compact:
            latency_widget = self.query_one("#status-latency", Static)
            
            if new_latency is not None:
                # Format latency with color coding
                if new_latency < 50:
                    color = "green"
                elif new_latency < 150:
                    color = "yellow"
                else:
                    color = "red"
                
                latency_widget.update(f"[{color}]{new_latency:.0f}ms[/]")
                latency_widget.display = True
            else:
                latency_widget.display = False
        
        self._last_activity = datetime.now()
    
    def _update_details(self) -> None:
        """Update the details display."""
        if not self.show_details or self.compact:
            return
        
        details_widget = self.query_one("#status-details", Static)
        details = []
        
        # Connection duration
        if self._connected_since and self.state == ConnectionState.CONNECTED:
            duration = datetime.now() - self._connected_since
            details.append(f"up {self._format_duration(duration)}")
        
        # Reconnection count
        if self._reconnect_count > 0:
            details.append(f"{self._reconnect_count} reconnects")
        
        # Last error
        if self.last_error and self.state == ConnectionState.ERROR:
            details.append(f"[red]{self.last_error}[/]")
        
        # Last activity
        if self._last_activity and self.state == ConnectionState.CONNECTED:
            idle = datetime.now() - self._last_activity
            if idle > timedelta(seconds=30):
                details.append(f"idle {self._format_duration(idle)}")
        
        details_text = " • ".join(details) if details else ""
        details_widget.update(details_text)
        details_widget.display = bool(details_text)
    
    def _format_duration(self, duration: timedelta) -> str:
        """Format a duration for display."""
        total_seconds = int(duration.total_seconds())
        
        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes}m"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"
        else:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            return f"{days}d {hours}h"
    
    def _start_pulse(self) -> None:
        """Start pulse animation."""
        if not self._pulse_timer:
            self._pulse_timer = self.set_interval(0.5, self._pulse)
    
    def _stop_pulse(self) -> None:
        """Stop pulse animation."""
        if self._pulse_timer:
            self._pulse_timer.stop()
            self._pulse_timer = None
            
            # Reset icon opacity
            icon_widget = self.query_one("#status-icon", Static)
            icon_widget.styles.opacity = 1.0
    
    def _pulse(self) -> None:
        """Pulse animation callback."""
        icon_widget = self.query_one("#status-icon", Static)
        self._pulse_on = not self._pulse_on
        icon_widget.styles.opacity = 1.0 if self._pulse_on else 0.3
    
    def set_connected(self, latency: Optional[float] = None) -> None:
        """Set status to connected."""
        self.state = ConnectionState.CONNECTED
        self.latency = latency
        self.last_error = None
    
    def set_disconnected(self) -> None:
        """Set status to disconnected."""
        self.state = ConnectionState.DISCONNECTED
        self.latency = None
    
    def set_connecting(self) -> None:
        """Set status to connecting."""
        self.state = ConnectionState.CONNECTING
        self.latency = None
    
    def set_reconnecting(self) -> None:
        """Set status to reconnecting."""
        self.state = ConnectionState.RECONNECTING
        self.latency = None
    
    def set_error(self, error: str) -> None:
        """Set status to error."""
        self.state = ConnectionState.ERROR
        self.latency = None
        self.last_error = error
    
    def update_latency(self, latency: float) -> None:
        """Update latency measurement."""
        if self.state == ConnectionState.CONNECTED:
            self.latency = latency


# CSS for connection status
CONNECTION_STATUS_CSS = """
/* Connection status container */
ConnectionStatus {
    height: 1;
    width: auto;
    layout: horizontal;
    padding: 0 1;
}

/* Icon styles */
.connection-icon {
    width: 2;
    text-align: center;
}

.connection-icon.pulse {
    /* Pulse handled by opacity changes in code */
}

/* Text styles */
.connection-text {
    width: auto;
    margin: 0 1;
}

.status-green {
    color: var(--green);
}

.status-yellow {
    color: var(--yellow);
}

.status-red {
    color: var(--red);
}

.status-dim {
    color: var(--overlay0);
}

/* Latency display */
.connection-latency {
    width: auto;
    margin-right: 1;
}

/* Details display */
.connection-details {
    width: auto;
    color: var(--subtext0);
    text-style: italic;
}

/* Compact mode */
ConnectionStatus.compact {
    width: 2;
    padding: 0;
}
"""