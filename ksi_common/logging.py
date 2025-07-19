#!/usr/bin/env python3
"""
KSI Unified Logging Configuration and Context Management

Provides structured logging with automatic context propagation using structlog.
All KSI components (daemon, client, admin, interfaces) use this unified system
for consistent, structured logging with correlation support.
"""

import asyncio
import logging
import logging.handlers
import os
import sys
import uuid
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Dict, Optional
from pathlib import Path

import structlog

# Global flag to track if structlog has been configured
_STRUCTLOG_CONFIGURED = False


def configure_structlog(
    log_level: str = "INFO",
    log_format: str = "console",
    log_file: Optional[Path] = None,
    disable_console_in_tui: bool = True,
    force_disable_console: bool = False
) -> None:
    """
    Configure structlog for all KSI components with stdlib integration.
    
    This configuration uses Python's standard library logging integration,
    which allows dynamic log level changes at runtime.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format ("json" or "console")
        log_file: Optional log file path
        disable_console_in_tui: Disable console output in TUI environments
        force_disable_console: Force disable console output (e.g., daemon mode)
    """
    global _STRUCTLOG_CONFIGURED
    
    # Prevent double configuration - first call wins
    # Exception: allow reconfiguration in daemon mode to disable console handlers
    if _STRUCTLOG_CONFIGURED and not force_disable_console:
        return
    
    # Configure Python's standard library logging first
    log_level_numeric = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create handler based on configuration
    if log_file:
        # Ensure log directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)
        # Use regular FileHandler for daemon mode (rotation handled externally)
        # RotatingFileHandler has issues with forking/daemonization
        handler = logging.FileHandler(str(log_file), mode='a')
    elif force_disable_console:
        handler = logging.NullHandler()
    else:
        handler = logging.StreamHandler(sys.stdout)
    
    # Set handler level
    handler.setLevel(log_level_numeric)
    
    # Configure structlog processors
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    
    # Shared processors for both structlog and stdlib logs
    shared_processors = [
        timestamper,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.contextvars.merge_contextvars,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            timestamper,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.contextvars.merge_contextvars,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Create ProcessorFormatter
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer() if log_format == "json" else structlog.dev.ConsoleRenderer(colors=False),
        foreign_pre_chain=shared_processors,
    )
    
    # Apply formatter to handler
    handler.setFormatter(formatter)
    
    # Configure standard library logging
    logging.basicConfig(
        level=log_level_numeric,
        handlers=[handler],
        force=True,  # Remove existing handlers
    )
    
    # Also configure asyncio and warnings to use JSON formatting
    if log_format == "json":
        import warnings
        
        # Capture warnings through logging
        logging.captureWarnings(True)
        
        # Set asyncio logger to only show warnings
        logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    # Mark as configured
    _STRUCTLOG_CONFIGURED = True


# Note: Removed get_logger() function. Use structlog.get_logger() directly.
# Applications should call configure_structlog() at startup.
# Libraries and modules should just use structlog.get_logger() without configuration.


def bind_connection_context(
    request_id: Optional[str] = None, 
    connection_id: Optional[str] = None,
    **extra_context
) -> str:
    """
    Bind context for socket connections.
    
    Used for tracking requests and connections in the event-driven architecture.
    """
    if request_id is None:
        request_id = str(uuid.uuid4())
    if connection_id is None:
        connection_id = str(uuid.uuid4())
    
    context = {
        "request_id": request_id,
        "connection_id": connection_id,
        **extra_context
    }
    structlog.contextvars.bind_contextvars(**context)
    return request_id


def clear_context() -> None:
    """Clear all context variables."""
    structlog.contextvars.clear_contextvars()


def get_bound_logger(component: str, **default_context):
    """
    Get a bound logger with component identity and optional default context.
    
    This is the preferred way to create loggers in KSI modules and components.
    Uses the single "ksi" logger with component context bound at creation time.
    
    Best practice usage:
        # In module
        logger = get_bound_logger("completion_service", version="3.0.0")
        
        # For request context (when available)
        bind_request_context(session_id=session_id, request_id=request_id)
        
        # All subsequent logging includes both component and request context
        logger.info("Processing completion", model="claude-3")
    
    Args:
        component: Component name (e.g., "monitor", "completion_service")
        **default_context: Default context to bind to this logger instance
        
    Returns:
        Bound logger with component context
    """
    if not _STRUCTLOG_CONFIGURED:
        # Auto-configure with minimal settings for module import compatibility
        # The daemon entry point will reconfigure with proper settings
        # Respect environment variable for log level
        log_level = os.environ.get('KSI_LOG_LEVEL', 'INFO')
        log_format = os.environ.get('KSI_LOG_FORMAT', 'console')
        configure_structlog(log_level=log_level, log_format=log_format)
    
    base_logger = structlog.get_logger("ksi")
    return base_logger.bind(component=component, **default_context)


def bind_request_context(
    request_id: Optional[str] = None,
    session_id: Optional[str] = None, 
    correlation_id: Optional[str] = None,
    client_id: Optional[str] = None,
    **extra_context
) -> None:
    """
    Bind request-level context for the current execution context.
    
    This context will be included in all log entries within the current
    async/thread execution context. Use this for request tracing.
    
    Args:
        request_id: Unique request identifier
        session_id: Session identifier for conversation continuity
        correlation_id: Cross-request correlation identifier
        client_id: Client identifier
        **extra_context: Additional request-specific context
    """
    context = {}
    
    if request_id:
        context["request_id"] = request_id
    if session_id:
        context["session_id"] = session_id
    if correlation_id:
        context["correlation_id"] = correlation_id
    if client_id:
        context["client_id"] = client_id
    
    context.update(extra_context)
    
    if context:
        structlog.contextvars.bind_contextvars(**context)


def clear_request_context() -> None:
    """Clear all request-level context variables."""
    structlog.contextvars.clear_contextvars()


# Backwards compatibility - deprecated but functional during migration
def get_ksi_logger(component: str, **context):
    """
    DEPRECATED: Use get_bound_logger() instead.
    
    This function is maintained for backwards compatibility during migration.
    It will be removed in a future version.
    """
    import warnings
    warnings.warn(
        "get_ksi_logger() is deprecated. Use get_bound_logger() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return get_bound_logger(component, **context)


@contextmanager
def operation_context(**context):
    """Context manager for temporary operation-specific context."""
    # Store current context vars that we'll modify
    to_unbind = []
    
    # Bind new context
    for key, value in context.items():
        structlog.contextvars.bind_contextvars(**{key: value})
        to_unbind.append(key)
    
    try:
        yield
    finally:
        # Unbind the context we added
        if to_unbind:
            structlog.contextvars.unbind_contextvars(*to_unbind)


@asynccontextmanager
async def async_operation_context(**context):
    """Async context manager for temporary operation-specific context."""
    # Store current context vars that we'll modify
    to_unbind = []
    
    # Bind new context
    for key, value in context.items():
        structlog.contextvars.bind_contextvars(**{key: value})
        to_unbind.append(key)
    
    try:
        yield
    finally:
        # Unbind the context we added
        if to_unbind:
            structlog.contextvars.unbind_contextvars(*to_unbind)


@asynccontextmanager
async def command_context(command_name: str, parameters: Optional[Dict[str, Any]] = None):
    """Context manager for command execution with automatic timing."""
    import time
    
    start_time = time.time()
    command_id = str(uuid.uuid4())
    
    context = {
        "command_name": command_name,
        "command_id": command_id
    }
    
    if parameters:
        # Add parameter summary (avoid logging sensitive data)
        context["parameter_count"] = len(parameters)
        if "agent_id" in parameters:
            context["agent_id"] = parameters["agent_id"]
        if "session_id" in parameters:
            context["session_id"] = parameters["session_id"]
    
    async with async_operation_context(**context):
        try:
            yield command_id
        finally:
            # Log command completion with timing
            duration_ms = (time.time() - start_time) * 1000
            logger = structlog.get_logger(__name__)
            logger.info("command.completed", 
                       command_name=command_name,
                       command_id=command_id,
                       duration_ms=duration_ms)


@asynccontextmanager  
async def agent_context(agent_id: str, session_id: Optional[str] = None):
    """Context manager for agent operations."""
    context = {"agent_id": agent_id}
    if session_id:
        context["session_id"] = session_id
        
    async with async_operation_context(**context):
        yield


def log_event(logger, event_name: str, **event_data):
    """Log a structured event with automatic context inclusion."""
    # Remove 'event' key from event_data if it exists to avoid conflict
    # since we're passing event_name as first argument
    if 'event' in event_data:
        event_data.pop('event')
    logger.info(event_name, **event_data)


def disable_console_logging() -> None:
    """
    Disable console logging output.
    
    With stdlib integration, this removes console handlers.
    """
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
            root_logger.removeHandler(handler)


def set_log_level(level: str, logger_name: Optional[str] = None) -> None:
    """
    Dynamically change log level at runtime.
    
    Args:
        level: New log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        logger_name: Optional logger name to change (None for root logger)
    """
    target_logger = logging.getLogger(logger_name)
    target_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Also update handler levels to ensure they don't filter
    if logger_name is None:  # Root logger
        for handler in target_logger.handlers:
            handler.setLevel(getattr(logging, level.upper(), logging.INFO))

