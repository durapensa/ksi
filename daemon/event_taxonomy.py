#!/usr/bin/env python3
"""
KSI Daemon Event Taxonomy

Defines structured event names and categories for consistent logging across the daemon.
Events follow a hierarchical naming convention: category.action[.detail]

Categories:
- daemon: Core daemon lifecycle events
- socket: Network connection events  
- command: Command processing events
- agent: Agent lifecycle and operations
- claude: Claude process management
- message_bus: Event-driven messaging
- hot_reload: Zero-downtime reloading
"""

from typing import Dict, List, Set
from enum import Enum


class EventCategory(str, Enum):
    """Main event categories in KSI daemon."""
    DAEMON = "daemon"
    SOCKET = "socket" 
    COMMAND = "command"
    AGENT = "agent"
    CLAUDE = "claude"
    MESSAGE_BUS = "message_bus"
    HOT_RELOAD = "hot_reload"


# Daemon Lifecycle Events
DAEMON_EVENTS = {
    "daemon.startup": "Daemon process starting",
    "daemon.ready": "Daemon ready to accept connections",
    "daemon.shutdown": "Daemon shutdown initiated", 
    "daemon.shutdown_complete": "Daemon shutdown completed",
    "daemon.health_check": "Health check performed",
    "daemon.collision_detected": "Another daemon instance detected",
    "daemon.pid_file_created": "PID file written",
    "daemon.pid_file_cleaned": "PID file removed",
}

# Socket Connection Events  
SOCKET_EVENTS = {
    "socket.connected": "Client connected to daemon socket",
    "socket.disconnected": "Client disconnected from daemon socket",
    "socket.invalid_json": "Invalid JSON received on socket",
    "socket.error": "Socket operation error",
    "socket.timeout": "Socket operation timeout",
}

# Command Processing Events
COMMAND_EVENTS = {
    "command.received": "Command received and parsed",
    "command.processed": "Command processing completed", 
    "command.completed": "Command execution finished with timing",
    "command.error": "Command processing error",
    "command.validation_failed": "Command parameter validation failed",
    "command.unknown": "Unknown command received",
}

# Agent Lifecycle Events
AGENT_EVENTS = {
    "agent.spawned": "Agent process created",
    "agent.registered": "Agent registered in system", 
    "agent.terminated": "Agent process terminated",
    "agent.connection_persistent": "Agent established persistent connection",
    "agent.connection_closed": "Agent persistent connection closed",
    "agent.disconnected": "Agent disconnected from message bus",
    "agent.timeout": "Agent operation timeout",
    "agent.error": "Agent operation error",
}

# Claude Process Events
CLAUDE_EVENTS = {
    "claude.process_started": "Claude CLI process spawned",
    "claude.process_completed": "Claude CLI process finished",
    "claude.process_timeout": "Claude CLI process timeout",
    "claude.process_error": "Claude CLI process error", 
    "claude.session_created": "New Claude session started",
    "claude.session_resumed": "Existing Claude session resumed",
}

# Message Bus Events
MESSAGE_BUS_EVENTS = {
    "message_bus.agent_connected": "Agent connected to message bus",
    "message_bus.agent_disconnected": "Agent disconnected from message bus",
    "message_bus.subscribed": "Agent subscribed to event types",
    "message_bus.unsubscribed": "Agent unsubscribed from event types", 
    "message_bus.message_published": "Message published to event type",
    "message_bus.message_delivered": "Message delivered to subscriber",
    "message_bus.message_queued": "Message queued for offline agent",
    "message_bus.stats_collected": "Message bus statistics gathered",
}

# Hot Reload Events
HOT_RELOAD_EVENTS = {
    "hot_reload.initiated": "Hot reload process started",
    "hot_reload.state_serialized": "Daemon state serialized for transfer",
    "hot_reload.state_transferred": "State transferred to new daemon",
    "hot_reload.completed": "Hot reload process completed",
    "hot_reload.failed": "Hot reload process failed",
    "hot_reload.new_daemon_spawned": "New daemon instance spawned",
}

# All events combined
ALL_EVENTS: Dict[str, str] = {
    **DAEMON_EVENTS,
    **SOCKET_EVENTS, 
    **COMMAND_EVENTS,
    **AGENT_EVENTS,
    **CLAUDE_EVENTS,
    **MESSAGE_BUS_EVENTS,
    **HOT_RELOAD_EVENTS,
}


def get_event_category(event_name: str) -> str:
    """Extract category from event name."""
    return event_name.split('.', 1)[0] if '.' in event_name else event_name


def get_events_by_category(category: EventCategory) -> Dict[str, str]:
    """Get all events for a specific category."""
    return {k: v for k, v in ALL_EVENTS.items() if k.startswith(category.value)}


def validate_event_name(event_name: str) -> bool:
    """Check if event name is in the defined taxonomy."""
    return event_name in ALL_EVENTS


def get_event_description(event_name: str) -> str:
    """Get description for an event name."""
    return ALL_EVENTS.get(event_name, f"Unknown event: {event_name}")


def get_all_event_names() -> Set[str]:
    """Get set of all defined event names."""
    return set(ALL_EVENTS.keys())


# Convenience functions for common event patterns
def format_agent_event(event_name: str, agent_id: str, **context) -> Dict[str, any]:
    """Format agent-related event with standard context."""
    return {
        "event": event_name,
        "agent_id": agent_id,
        **context
    }


def format_command_event(event_name: str, command_name: str, **context) -> Dict[str, any]:
    """Format command-related event with standard context."""
    return {
        "event": event_name, 
        "command_name": command_name,
        **context
    }


def format_claude_event(event_name: str, session_id: str = None, **context) -> Dict[str, any]:
    """Format Claude process event with standard context."""
    event_data = {"event": event_name, **context}
    if session_id:
        event_data["session_id"] = session_id
    return event_data