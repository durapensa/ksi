"""
KSI TUI Components - Reusable UI components for KSI applications.

This package provides a collection of beautiful, reusable Textual components
designed specifically for KSI's needs.
"""

from .message_bubble import (
    MessageBubble,
    MessageList,
    MessageType,
    MESSAGE_CSS,
)

from .event_stream import (
    EventStream,
    EventStreamWidget,
    Event,
    EventSeverity,
    EventFilter,
    EVENT_STREAM_CSS,
)

from .metrics_bar import (
    MetricsBar,
    MetricDisplay,
    Metric,
    MetricType,
    QuickStats,
    METRICS_CSS,
)

from .connection_status import (
    ConnectionStatus,
    ConnectionState,
    CONNECTION_STATUS_CSS,
)

# Collect all component CSS
ALL_COMPONENT_CSS = "\n".join([
    MESSAGE_CSS,
    EVENT_STREAM_CSS,
    METRICS_CSS,
    CONNECTION_STATUS_CSS,
])

__all__ = [
    # Message components
    "MessageBubble",
    "MessageList",
    "MessageType",
    "MESSAGE_CSS",
    
    # Event stream components
    "EventStream",
    "EventStreamWidget",
    "Event",
    "EventSeverity",
    "EventFilter",
    "EVENT_STREAM_CSS",
    
    # Metrics components
    "MetricsBar",
    "MetricDisplay",
    "Metric",
    "MetricType",
    "QuickStats",
    "METRICS_CSS",
    
    # Connection status
    "ConnectionStatus",
    "ConnectionState",
    "CONNECTION_STATUS_CSS",
    
    # Combined CSS
    "ALL_COMPONENT_CSS",
]