#!/usr/bin/env python3
"""
KSI Daemon Logging Configuration and Context Management

Provides structured logging with automatic context propagation using structlog.contextvars.
Supports async-safe context binding for correlation across complex daemon operations.
"""

import asyncio
import uuid
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Dict, Optional
import structlog

from .config import config


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance with automatic context support."""
    return config.get_structured_logger(name)


def bind_socket_context(
    functional_domain: str,
    request_id: Optional[str] = None, 
    connection_id: Optional[str] = None,
    **extra_context
) -> str:
    """
    Bind context for socket connections with functional domain identification.
    
    Functional Domains (separate sockets):
    - 'admin': System operations (health, shutdown, cleanup) - admin.sock
    - 'agents': Agent lifecycle & persona (spawn, identity, composition) - agents.sock  
    - 'messaging': Ephemeral communication (pub/sub, send_message) - messaging.sock
    - 'state': Persistent KV store (set_agent_kv, get_agent_kv) - state.sock
    - 'completion': LLM interactions (completion) - completion.sock
    """
    if request_id is None:
        request_id = str(uuid.uuid4())
    if connection_id is None:
        connection_id = str(uuid.uuid4())
    
    context = {
        "request_id": request_id,
        "connection_id": connection_id,
        "functional_domain": functional_domain,
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


# Convenience logger for this module
logger = get_logger(__name__)