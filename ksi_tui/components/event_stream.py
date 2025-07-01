"""
EventStream - Smooth scrolling event log component for monitoring interfaces.

Features:
- Real-time event display with color coding
- Pattern-based filtering
- Smooth auto-scroll with user override
- Event severity indicators
- Expandable detail views
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Static, RichLog, Input, Button, Collapsible
from textual.reactive import reactive
from textual import events
from textual.worker import Worker, get_current_worker
import re


class EventSeverity(Enum):
    """Event severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Event:
    """Represents a single event in the stream."""
    timestamp: datetime
    event_name: str
    severity: EventSeverity
    client_id: Optional[str]
    data: Dict[str, Any]
    correlation_id: Optional[str] = None
    
    @property
    def formatted_time(self) -> str:
        """Format timestamp for display."""
        return self.timestamp.strftime("%H:%M:%S.%f")[:-3]


class EventFilter:
    """Manages event filtering logic."""
    
    def __init__(self):
        self.patterns: List[str] = []
        self.severity_filter: Optional[EventSeverity] = None
        self.client_filter: Optional[str] = None
        self._compiled_patterns: List[re.Pattern] = []
    
    def set_patterns(self, patterns: List[str]) -> None:
        """Set filter patterns (supports wildcards and regex)."""
        self.patterns = patterns
        self._compiled_patterns = []
        
        for pattern in patterns:
            # Convert wildcards to regex
            if "*" in pattern and not pattern.startswith("^"):
                regex_pattern = pattern.replace("*", ".*")
                regex_pattern = f"^{regex_pattern}$"
            else:
                regex_pattern = pattern
            
            try:
                self._compiled_patterns.append(re.compile(regex_pattern))
            except re.error:
                # Invalid regex, skip
                pass
    
    def matches(self, event: Event) -> bool:
        """Check if an event matches the current filters."""
        # Check severity filter
        if self.severity_filter and event.severity.value < self.severity_filter.value:
            return False
        
        # Check client filter
        if self.client_filter and event.client_id != self.client_filter:
            return False
        
        # Check patterns (if any)
        if self._compiled_patterns:
            for pattern in self._compiled_patterns:
                if pattern.search(event.event_name):
                    return True
            return False
        
        # No patterns means match all
        return True


class EventStreamWidget(Container):
    """Widget for displaying a filtered stream of events."""
    
    # Severity colors and icons
    SEVERITY_CONFIG = {
        EventSeverity.DEBUG: ("dim", "🔍"),
        EventSeverity.INFO: ("", "ℹ️"),
        EventSeverity.WARNING: ("yellow", "⚠️"),
        EventSeverity.ERROR: ("red", "❌"),
        EventSeverity.CRITICAL: ("bold red", "🚨"),
    }
    
    def __init__(
        self,
        *,
        max_events: int = 1000,
        auto_scroll: bool = True,
        show_filter: bool = True,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        """
        Initialize the event stream widget.
        
        Args:
            max_events: Maximum number of events to keep in memory
            auto_scroll: Whether to auto-scroll to new events
            show_filter: Whether to show the filter bar
            name: Widget name
            id: Widget ID
            classes: Additional CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.max_events = max_events
        self.auto_scroll = auto_scroll
        self.show_filter = show_filter
        
        # Event storage and filtering
        self.events: List[Event] = []
        self.filter = EventFilter()
        
        # Event handlers
        self._event_handler: Optional[Callable[[Event], None]] = None
    
    def compose(self) -> ComposeResult:
        """Compose the event stream UI."""
        with Vertical():
            # Optional filter bar
            if self.show_filter:
                with Horizontal(classes="event-filter-bar"):
                    yield Input(
                        placeholder="Filter events... (e.g., completion:*, agent:spawn)",
                        classes="event-filter-input",
                        id="event-filter"
                    )
                    yield Button("Clear", variant="warning", id="clear-events")
            
            # Event log
            yield RichLog(
                highlight=True,
                markup=True,
                wrap=False,
                max_lines=self.max_events,
                auto_scroll=self.auto_scroll,
                classes="event-log",
                id="event-log"
            )
    
    def add_event(
        self,
        event_name: str,
        data: Dict[str, Any],
        *,
        severity: EventSeverity = EventSeverity.INFO,
        client_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Add a new event to the stream.
        
        Args:
            event_name: Name of the event
            data: Event data dictionary
            severity: Event severity level
            client_id: Client that generated the event
            correlation_id: Correlation ID for tracing
            timestamp: Event timestamp (defaults to now)
        """
        event = Event(
            timestamp=timestamp or datetime.now(),
            event_name=event_name,
            severity=severity,
            client_id=client_id,
            data=data,
            correlation_id=correlation_id,
        )
        
        # Add to storage
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events.pop(0)
        
        # Display if it passes filters
        if self.filter.matches(event):
            self._display_event(event)
        
        # Call handler if set
        if self._event_handler:
            self._event_handler(event)
    
    def _display_event(self, event: Event) -> None:
        """Display an event in the log."""
        log = self.query_one("#event-log", RichLog)
        
        # Get severity config
        color, icon = self.SEVERITY_CONFIG.get(
            event.severity,
            ("", "•")
        )
        
        # Format the event line
        time_str = f"[dim]{event.formatted_time}[/]"
        severity_str = f"[{color}]{icon}[/]" if color else icon
        event_str = f"[cyan]{event.event_name}[/]"
        client_str = f"[yellow]{event.client_id}[/]" if event.client_id else ""
        
        # Build the log line
        parts = [time_str, severity_str, event_str]
        if client_str:
            parts.append(client_str)
        
        # Add correlation ID if present
        if event.correlation_id:
            parts.append(f"[dim]({event.correlation_id[:8]})[/]")
        
        log.write(" ".join(parts))
        
        # Add data preview if not empty
        if event.data:
            data_preview = self._format_data_preview(event.data)
            if data_preview:
                log.write(f"  [dim]{data_preview}[/]")
    
    def _format_data_preview(self, data: Dict[str, Any], max_length: int = 80) -> str:
        """Format event data for preview display."""
        # Extract interesting fields
        preview_fields = []
        
        for key in ["message", "prompt", "error", "status", "action"]:
            if key in data:
                value = str(data[key])
                if len(value) > 50:
                    value = value[:47] + "..."
                preview_fields.append(f"{key}: {value}")
        
        # If no specific fields, show first few items
        if not preview_fields and data:
            for key, value in list(data.items())[:3]:
                value_str = str(value)
                if len(value_str) > 30:
                    value_str = value_str[:27] + "..."
                preview_fields.append(f"{key}: {value_str}")
        
        preview = " | ".join(preview_fields)
        if len(preview) > max_length:
            preview = preview[:max_length-3] + "..."
        
        return preview
    
    def set_filter(self, patterns: List[str]) -> None:
        """Set event filter patterns and refresh display."""
        self.filter.set_patterns(patterns)
        self._refresh_display()
    
    def _refresh_display(self) -> None:
        """Refresh the event display with current filters."""
        log = self.query_one("#event-log", RichLog)
        log.clear()
        
        # Re-display all matching events
        for event in self.events:
            if self.filter.matches(event):
                self._display_event(event)
    
    def clear_events(self) -> None:
        """Clear all events from the stream."""
        self.events.clear()
        log = self.query_one("#event-log", RichLog)
        log.clear()
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle filter input changes."""
        if event.input.id == "event-filter":
            # Parse filter patterns (comma or space separated)
            patterns = [p.strip() for p in re.split(r'[,\s]+', event.value) if p.strip()]
            self.set_filter(patterns)
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "clear-events":
            self.clear_events()
    
    def set_event_handler(self, handler: Callable[[Event], None]) -> None:
        """Set a callback for when new events are added."""
        self._event_handler = handler


# CSS for EventStream components
EVENT_STREAM_CSS = """
/* Event stream container */
EventStreamWidget {
    height: 100%;
    border: round var(--surface1);
    background: var(--mantle);
}

/* Filter bar */
.event-filter-bar {
    height: 3;
    padding: 1;
    background: var(--surface0);
    border-bottom: tall var(--surface1);
}

.event-filter-input {
    width: 1fr;
    margin-right: 1;
}

/* Event log */
.event-log {
    height: 1fr;
    padding: 1;
    background: var(--base);
}

/* Event severity colors */
.event-debug {
    color: var(--overlay0);
}

.event-info {
    color: var(--text);
}

.event-warning {
    color: var(--yellow);
}

.event-error {
    color: var(--red);
}

.event-critical {
    color: var(--red);
    text-style: bold;
}
"""