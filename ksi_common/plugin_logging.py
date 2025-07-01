#!/usr/bin/env python3
"""
Plugin Logging Context Management for KSI

Provides optimized logging context management for the KSI plugin system based on
comprehensive analysis of contextvars vs bound loggers approaches.

Key findings from analysis:
- Module-level contextvars have race conditions in function-based plugin systems
- Hook-level contextvar binding works but has performance overhead  
- Bound loggers provide best performance and isolation for plugin identity
- contextvars are best for request-level tracing (correlation IDs, session IDs)

Recommended pattern:
- Use bound loggers for plugin identity (component-level context)
- Use contextvars for cross-cutting request/trace context
- Combine both for complete logging visibility
"""

import contextvars
from typing import Optional, Dict, Any
import structlog

# Use structlog's contextvar system for automatic integration
# This ensures the contextvars are automatically included in log records

def get_plugin_logger(plugin_name: str, **extra_context):
    """
    Get a properly configured logger for a KSI plugin.
    
    This is the recommended way to create plugin loggers. It provides:
    - Plugin identity isolation via bound logger
    - Automatic contextvar integration for request tracing
    - Consistent logger naming convention
    - Additional static context binding
    
    Args:
        plugin_name: Name of the plugin (e.g., "completion_service", "agent_service")
        **extra_context: Additional static context to bind to this logger
        
    Returns:
        Bound logger with plugin context
        
    Example:
        # In plugin module:
        logger = get_plugin_logger("completion_service", version="3.0.0")
        
        # In hook implementation:
        logger.info("processing_completion", 
                   prompt_length=len(prompt),
                   model=model_name)
    """
    # Create base logger with plugin identity
    base_logger = structlog.get_logger("ksi.plugin")
    
    # Bind plugin identity and any extra static context
    context = {"plugin_name": plugin_name, **extra_context}
    return base_logger.bind(**context)


def bind_request_context(
    correlation_id: Optional[str] = None,
    session_id: Optional[str] = None, 
    request_id: Optional[str] = None,
    client_id: Optional[str] = None
) -> None:
    """
    Bind request-level context that will be automatically included in all log records.
    
    This should be called by the event router when processing events to provide
    cross-cutting request tracing context. All plugins will automatically inherit
    this context in their log records via structlog's contextvars integration.
    
    Args:
        correlation_id: Correlation ID for distributed tracing
        session_id: Session ID for conversation continuity
        request_id: Individual request identifier
        client_id: Client/connection identifier
        
    Example:
        # In event router:
        bind_request_context(
            correlation_id=trace_correlation_id,
            session_id=data.get("session_id"),
            request_id=str(uuid.uuid4()),
            client_id=context.get("client_id")
        )
    """
    # Use structlog's contextvar binding for automatic inclusion in logs
    context = {}
    if correlation_id is not None:
        context["correlation_id"] = correlation_id
    if session_id is not None:
        context["session_id"] = session_id  
    if request_id is not None:
        context["request_id"] = request_id
    if client_id is not None:
        context["client_id"] = client_id
    
    if context:
        structlog.contextvars.bind_contextvars(**context)


def clear_request_context() -> None:
    """
    Clear all request-level context variables.
    
    This should be called at the end of request processing to prevent
    context leakage between requests.
    """
    structlog.contextvars.clear_contextvars()


def get_current_request_context() -> Dict[str, Any]:
    """
    Get the current request context as a dictionary.
    
    Returns:
        Dictionary of current request context values (excluding None values)
    """
    # Note: structlog doesn't provide a direct way to get current contextvar values
    # This is a limitation of the structlog contextvar API
    # For debugging purposes, we could implement our own tracking if needed
    return {}


class RequestContextManager:
    """
    Context manager for temporary request context binding.
    
    Useful for scoping request context to specific operations.
    
    Example:
        with RequestContextManager(correlation_id="abc123", session_id="sess_456"):
            # All logging within this scope includes the bound context
            logger.info("operation_started")
            await process_request()
            logger.info("operation_completed")
        # Context is restored when exiting
    """
    
    def __init__(self, 
                 correlation_id: Optional[str] = None,
                 session_id: Optional[str] = None,
                 request_id: Optional[str] = None, 
                 client_id: Optional[str] = None):
        self.context = {}
        if correlation_id is not None:
            self.context['correlation_id'] = correlation_id
        if session_id is not None:
            self.context['session_id'] = session_id
        if request_id is not None:
            self.context['request_id'] = request_id
        if client_id is not None:
            self.context['client_id'] = client_id
    
    def __enter__(self):
        # Use structlog's bound_contextvars context manager
        if self.context:
            self.cm = structlog.contextvars.bound_contextvars(**self.context)
            return self.cm.__enter__()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, 'cm'):
            return self.cm.__exit__(exc_type, exc_val, exc_tb)


# Backward compatibility: maintain existing logger creation pattern
def get_ksi_plugin_logger(plugin_name: str):
    """
    Backward compatibility alias for get_plugin_logger.
    
    Deprecated: Use get_plugin_logger() instead.
    """
    return get_plugin_logger(plugin_name)


# Migration helper: convert existing logger patterns
def migrate_plugin_logger(old_logger_name: str):
    """
    Migration helper to convert existing plugin logger patterns to new system.
    
    Args:
        old_logger_name: Old logger name like "ksi.plugin.completion_service"
        
    Returns:
        New bound logger with proper plugin context
        
    Example:
        # Old pattern:
        logger = structlog.get_logger("ksi.plugin.completion_service")
        
        # New pattern:
        logger = migrate_plugin_logger("ksi.plugin.completion_service")
        # or better:
        logger = get_plugin_logger("completion_service")
    """
    # Extract plugin name from old logger name
    if old_logger_name.startswith("ksi.plugin."):
        plugin_name = old_logger_name[11:]  # Remove "ksi.plugin." prefix
    else:
        plugin_name = old_logger_name
    
    return get_plugin_logger(plugin_name)