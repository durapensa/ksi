"""KSI Common - Shared utilities for all KSI components.

This package contains shared utilities, constants, and protocols used across
ksi_daemon, ksi_client, ksi_admin, and interfaces. It has no dependencies on
any other KSI packages to avoid circular imports.
"""

__version__ = "0.1.0"

# Core utilities
from .timestamps import TimestampManager
from .paths import KSIPaths
from .constants import (
    DEFAULT_SOCKET_PATH,
    DEFAULT_SOCKET_TIMEOUT,
    DEFAULT_COMPLETION_TIMEOUT,
    EVENT_NAMESPACES,
)
from .protocols import (
    SystemEvents,
    AgentEvents,
    CompletionEvents,
    StateEvents,
    MessageEvents,
    ConversationEvents,
)
from .exceptions import (
    KSIError,
    ConnectionError as KSIConnectionError,
    ProtocolError,
    TimeoutError as KSITimeoutError,
)

__all__ = [
    # Version
    "__version__",
    
    # Core classes
    "TimestampManager",
    "KSIPaths",
    
    # Constants
    "DEFAULT_SOCKET_PATH",
    "DEFAULT_SOCKET_TIMEOUT",
    "DEFAULT_COMPLETION_TIMEOUT",
    "EVENT_NAMESPACES",
    
    # Protocol events
    "SystemEvents",
    "AgentEvents",
    "CompletionEvents",
    "StateEvents",
    "MessageEvents",
    "ConversationEvents",
    
    # Exceptions
    "KSIError",
    "KSIConnectionError",
    "ProtocolError",
    "KSITimeoutError",
]