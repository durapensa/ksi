"""Shared constants and configuration defaults for KSI."""

from pathlib import Path

# Socket configuration
DEFAULT_SOCKET_PATH = "var/run/daemon.sock"
DEFAULT_SOCKET_TIMEOUT = 5.0
DEFAULT_SOCKET_BUFFER_SIZE = 65536

# Timeout defaults
DEFAULT_COMPLETION_TIMEOUT = 300.0  # 5 minutes for completions
DEFAULT_REQUEST_TIMEOUT = 30.0      # 30 seconds for normal requests
DEFAULT_SHUTDOWN_TIMEOUT = 10.0     # 10 seconds for graceful shutdown

# Directory structure (relative to working directory)
DEFAULT_VAR_DIR = "var"
DEFAULT_LOG_DIR = "var/logs"
DEFAULT_RESPONSE_LOG_DIR = "var/logs/responses"
DEFAULT_DAEMON_LOG_DIR = "var/logs/daemon"
DEFAULT_STATE_DIR = "var/state"
DEFAULT_DB_DIR = "var/db"
DEFAULT_RUN_DIR = "var/run"
DEFAULT_EXPORT_DIR = "var/state/exports"

# Event namespace prefixes
EVENT_NAMESPACES = {
    "system": "Core system events (health, shutdown, discovery)",
    "transport": "Transport layer events (connection, disconnection)",
    "completion": "LLM completion events (request, response)",
    "agent": "Agent lifecycle events (spawn, terminate, status)",
    "state": "State management events (get, set, delete)",
    "message": "Inter-agent messaging events (publish, subscribe)",
    "conversation": "Conversation history events (list, search, export)",
    "admin": "Administrative events (monitoring, control)",
    "monitor": "Monitoring-specific events",
    "metrics": "Performance and telemetry events",
    "debug": "Debugging and diagnostic events",
}

# Message bus event types
MESSAGE_BUS_EVENTS = [
    "DIRECT_MESSAGE",
    "BROADCAST",
    "CONVERSATION_MESSAGE",
    "CONVERSATION_INVITE",
    "TASK_ASSIGNMENT",
    "STATUS_UPDATE",
]

# File patterns
RESPONSE_LOG_PATTERN = "*.jsonl"
MESSAGE_BUS_LOG = "message_bus.jsonl"
DEFAULT_PID_FILE = "ksi_daemon.pid"

# Logging configuration
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "console"  # or "json"

# Agent defaults
DEFAULT_AGENT_PROFILE = "ksi-developer"
DEFAULT_MODEL = "claude-sonnet-4-20250514"

# Protocol version
PROTOCOL_VERSION = "1.0"