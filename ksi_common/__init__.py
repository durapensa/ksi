"""KSI Common - Shared utilities for all KSI components.

This package contains shared utilities, constants, and protocols used across
ksi_daemon, ksi_client, and interfaces. It has no dependencies on
any other KSI packages to avoid circular imports.
"""

__version__ = "0.1.0"

# Ensure project root is on sys.path for absolute imports
import sys
from pathlib import Path

# Find the project root (parent of ksi_common)
_ksi_common_dir = Path(__file__).parent
_project_root = _ksi_common_dir.parent

# Add to sys.path if not already there
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Core utilities
# Import timestamp functions directly
from .timestamps import (
    utc_now,
    timestamp_utc,
    timestamp_local_iso,
    filename_timestamp,
    display_timestamp,
    parse_iso_timestamp,
    utc_to_local,
    local_to_utc,
    format_for_logging,
    format_for_display,
    format_for_message_bus,
    get_timezone_offset,
    ensure_utc_suffix,
)
from .paths import KSIPaths
from .config import KSIBaseConfig, config
from .constants import (
    DEFAULT_SOCKET_PATH,
    DEFAULT_SOCKET_TIMEOUT,
    DEFAULT_COMPLETION_TIMEOUT,
    EVENT_NAMESPACES,
)
# Protocol imports removed - protocols.py was dead code
from .exceptions import (
    KSIError,
    KSIConnectionError,
    ProtocolError,
    KSITimeoutError,
)
from .logging import (
    configure_structlog,
    get_bound_logger,
    bind_request_context,
    clear_request_context,
    bind_connection_context,
    clear_context,
    operation_context,
    async_operation_context,
    command_context,
    agent_context,
    log_event,
    disable_console_logging,
)
from .async_utils import (
    run_sync,
    async_to_sync,
    ensure_event_loop,
    run_in_thread_pool,
    main_entry_point,
)
from .completion_format import (
    # Main functions
    create_standardized_response,
    create_completion_response,
    parse_completion_response,
    # Helper functions
    get_provider,
    get_raw_response,
    get_request_id,
    get_timestamp,
    get_duration_ms,
    get_client_id,
    get_response_text,
    get_response_session_id,
    get_response_usage,
    get_response_cost,
    get_response_model,
    # Provider extraction functions
    extract_text,
    extract_session_id,
    extract_usage,
    extract_cost,
    extract_model,
)

__all__ = [
    # Version
    "__version__",
    
    # Core classes
    "KSIPaths",
    "KSIBaseConfig",
    
    # Timestamp functions (module-level)
    "utc_now",
    "timestamp_utc",
    "timestamp_local_iso",
    "filename_timestamp",
    "display_timestamp",
    "parse_iso_timestamp",
    "utc_to_local",
    "local_to_utc",
    "format_for_logging",
    "format_for_display",
    "format_for_message_bus",
    "get_timezone_offset",
    "ensure_utc_suffix",
    
    # Config instance
    "config",
    
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
    "configure_structlog",
    "get_bound_logger",
    "bind_request_context",
    "clear_request_context",
    "bind_connection_context",
    "clear_context",
    "operation_context",
    "async_operation_context",
    "command_context",
    "agent_context",
    "log_event",
    "disable_console_logging",
    
    # Async utilities
    "run_sync",
    "async_to_sync",
    "ensure_event_loop",
    "run_in_thread_pool",
    "main_entry_point",
    
    # Completion format utilities
    "create_standardized_response",
    "create_completion_response",
    "parse_completion_response",
    "get_provider",
    "get_raw_response",
    "get_request_id",
    "get_timestamp",
    "get_duration_ms",
    "get_client_id",
    "get_response_text",
    "get_response_session_id",
    "get_response_usage",
    "get_response_cost",
    "get_response_model",
    "extract_text",
    "extract_session_id",
    "extract_usage",
    "extract_cost",
    "extract_model",
]