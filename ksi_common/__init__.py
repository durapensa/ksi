"""KSI Common - Shared utilities for all KSI components.

This package contains shared utilities, constants, and protocols used across
ksi_daemon, ksi_client, and interfaces. It has no dependencies on
any other KSI packages to avoid circular imports.
"""

__version__ = "0.1.0"

# Core utilities
from .timestamps import TimestampManager
from .paths import KSIPaths
from .config import KSIBaseConfig, get_config, reload_config, config
from .constants import (
    DEFAULT_SOCKET_PATH,
    DEFAULT_SOCKET_TIMEOUT,
    DEFAULT_COMPLETION_TIMEOUT,
    EVENT_NAMESPACES,
)
# Protocol imports removed - protocols.py was dead code
from .exceptions import (
    KSIError,
    ConnectionError as KSIConnectionError,
    ProtocolError,
    TimeoutError as KSITimeoutError,
)
from .logging import (
    get_logger,
    configure_structlog,
    bind_connection_context,
    clear_context,
    operation_context,
    async_operation_context,
    command_context,
    agent_context,
    log_event,
    disable_console_logging,
)
from .completion_format import (
    CompletionResponse,
    ProviderHelpers,
    create_completion_response,
    parse_completion_response,
)

__all__ = [
    # Version
    "__version__",
    
    # Core classes
    "TimestampManager",
    "KSIPaths",
    "KSIBaseConfig",
    
    # Config functions
    "config",
    "get_config",
    "reload_config",
    
    # Constants
    "DEFAULT_SOCKET_PATH",
    "DEFAULT_SOCKET_TIMEOUT",
    "DEFAULT_COMPLETION_TIMEOUT",
    "EVENT_NAMESPACES",
    
    
    # Exceptions
    "KSIError",
    "KSIConnectionError",
    "ProtocolError",
    "KSITimeoutError",
    
    # Logging utilities
    "get_logger",
    "configure_structlog",
    "bind_connection_context",
    "clear_context",
    "operation_context",
    "async_operation_context",
    "command_context",
    "agent_context",
    "log_event",
    "disable_console_logging",
    
    # Completion format utilities
    "CompletionResponse",
    "ProviderHelpers",
    "create_completion_response",
    "parse_completion_response",
]