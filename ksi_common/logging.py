#!/usr/bin/env python3
"""
KSI Unified Logging Configuration and Context Management

Provides structured logging with automatic context propagation using structlog.
All KSI components (daemon, client, admin, interfaces) use this unified system
for consistent, structured logging with correlation support.
"""

import asyncio
import logging
import sys
import uuid
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Dict, Optional, List
from pathlib import Path

import structlog

# Global flag to track if structlog is configured
_STRUCTLOG_CONFIGURED = False


def configure_structlog(
    log_level: str = "INFO",
    log_format: str = "console",
    log_file: Optional[Path] = None,
    disable_console_in_tui: bool = True
) -> None:
    """
    Configure structlog for all KSI components.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format ("json" or "console")
        log_file: Optional log file path
        disable_console_in_tui: Disable console output in TUI environments
    """
    global _STRUCTLOG_CONFIGURED
    
    if _STRUCTLOG_CONFIGURED:
        return
    
    # Base processors that all loggers use
    processors = [
        structlog.contextvars.merge_contextvars,  # Auto-merge context vars
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    # Choose renderer based on format preference
    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Console format - human readable
        processors.extend([
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(colors=True)
        ])
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging backend
    handlers: List[logging.Handler] = []
    
    # Console handler (skip if in TUI environment)
    if not (disable_console_in_tui and any(mod.startswith('textual') for mod in sys.modules)):
        console_handler = logging.StreamHandler(sys.stdout)
        handlers.append(console_handler)
    
    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_file))
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=handlers,
        force=True  # Override any existing configuration
    )
    
    _STRUCTLOG_CONFIGURED = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance with automatic context support.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Structured logger instance
    """
    # Auto-configure if not already done
    if not _STRUCTLOG_CONFIGURED:
        # Use config from ksi_common if available
        try:
            from .config import config
            configure_structlog(
                log_level=config.log_level,
                log_format=config.log_format
            )
        except ImportError:
            # Fallback to defaults
            configure_structlog()
    
    return structlog.get_logger(name)


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
            logger = get_logger(__name__)
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


def log_event(logger: structlog.stdlib.BoundLogger, event_name: str, **event_data):
    """Log a structured event with automatic context inclusion."""
    # Remove 'event' key from event_data if it exists to avoid conflict
    # since we're passing event_name as first argument
    if 'event' in event_data:
        event_data.pop('event')
    logger.info(event_name, **event_data)


def disable_console_logging() -> None:
    """
    Disable console logging output.
    
    Useful for TUI applications where console output would corrupt the display.
    """
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and handler.stream in (sys.stdout, sys.stderr):
            root_logger.removeHandler(handler)


# Convenience logger for this module
logger = get_logger(__name__)