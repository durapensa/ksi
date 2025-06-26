#!/usr/bin/env python3
"""
KSI Daemon Logging Configuration - Compatibility Wrapper

This module now redirects to ksi_common.logging for unified structured logging
across all KSI components. Kept for backward compatibility during migration.
"""

# Import everything from the common logging module
from ksi_common.logging import (
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

# Re-export everything for backward compatibility
__all__ = [
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
]

# Convenience logger for this module
logger = get_logger(__name__)