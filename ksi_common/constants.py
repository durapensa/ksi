"""Shared constants and configuration defaults for KSI."""

from pathlib import Path
import shutil

# Socket configuration
DEFAULT_SOCKET_PATH = "var/run/daemon.sock"
DEFAULT_SOCKET_TIMEOUT = 5.0
DEFAULT_SOCKET_BUFFER_SIZE = 65536

# WebSocket Bridge configuration
DEFAULT_WEBSOCKET_HOST = "localhost"
DEFAULT_WEBSOCKET_PORT = 8765
# Default CORS origins for ksi_web_ui development
DEFAULT_WEBSOCKET_CORS_ORIGINS = ["http://localhost:8080", "http://localhost:3000", "file://"]

# Timeout defaults
DEFAULT_COMPLETION_TIMEOUT = 300.0  # 5 minutes for completions
DEFAULT_REQUEST_TIMEOUT = 30.0      # 30 seconds for normal requests
DEFAULT_SHUTDOWN_TIMEOUT = 10.0     # 10 seconds for graceful shutdown
DEFAULT_EVALUATION_COMPLETION_TIMEOUT = 300  # 5 minutes for evaluation completions

# Completion concurrency limits
DEFAULT_MAX_CONCURRENT_COMPLETIONS = 4  # Maximum concurrent completion requests

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

# Database filenames
DEFAULT_STATE_DB_NAME = "ksi_state.db"
DEFAULT_CHECKPOINT_DB_NAME = "checkpoint.db"
DEFAULT_EVENTS_DB_NAME = "events.db"
DEFAULT_COMPOSITION_INDEX_DB_NAME = "composition_index.db"
DEFAULT_EVALUATION_INDEX_DB_NAME = "evaluation_index.db"

# File patterns
RESPONSE_LOG_PATTERN = "*.jsonl"
MESSAGE_BUS_LOG = "message_bus.jsonl"
DEFAULT_PID_FILE = "ksi_daemon.pid"

# Logging configuration
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "console"  # or "json"

# Agent defaults
DEFAULT_AGENT_PROFILE = "ksi-developer"
DEFAULT_MODEL = "claude-cli/claude-sonnet-4-20250514"

# Claude CLI configuration
DEFAULT_CLAUDE_BIN = None  # Set via KSI_CLAUDE_BIN environment variable

# Gemini CLI configuration
# Try to auto-discover gemini from PATH
try:
    DEFAULT_GEMINI_BIN = shutil.which("gemini")
except Exception:
    DEFAULT_GEMINI_BIN = None  # Fall back to None if discovery fails

# Protocol version
PROTOCOL_VERSION = "1.0"