#!/usr/bin/env python3
"""
Error propagation and routing for fail-fast architecture.

This module provides automatic error routing based on KSI context chains,
ensuring that processing failures immediately propagate to originating agents.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# Error type registry for standardized error handling
ERROR_TYPES = {
    "template_resolution": {
        "severity": "error",
        "recoverable": False,
        "description": "Template variable cannot be resolved"
    },
    "condition_evaluation": {
        "severity": "error", 
        "recoverable": False,
        "description": "Condition references missing field"
    },
    "transformation": {
        "severity": "error",
        "recoverable": True,
        "description": "Event transformation failed"
    },
    "transformer": {
        "severity": "error",
        "recoverable": False,
        "description": "Dynamic transformer execution failed"
    },
    "transformer_failure": {
        "severity": "error",
        "recoverable": False,
        "description": "Transformer failed during template resolution or mapping"
    },
    "validation": {
        "severity": "warning",
        "recoverable": True,
        "description": "Data validation failed"
    },
    "handler_execution": {
        "severity": "error",
        "recoverable": True,
        "description": "Event handler raised exception"
    },
    "type_mismatch": {
        "severity": "error",
        "recoverable": False,
        "description": "Type coercion failed"
    },
    "context_missing": {
        "severity": "critical",
        "recoverable": False,
        "description": "Required context not provided"
    }
}


async def handle_error_events(event: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Central error event handler that routes errors to originating agents.
    
    This handler catches all error:* events and:
    1. Extracts the KSI context to identify the originator
    2. Routes the error to the originating agent
    3. Logs the error for monitoring
    4. Optionally triggers recovery mechanisms
    """
    from ksi_daemon.module_manager import get_event_emitter
    
    error_type = event.split(':', 1)[1] if ':' in event else 'unknown'
    context = data.get('_ksi_context', {})
    client_id = context.get('_client_id')
    
    # Log the error with full context
    logger.error(f"Error event {event}: {data.get('error_message', 'Unknown error')}", extra={
        'error_type': error_type,
        'client_id': client_id,
        'correlation_id': context.get('_correlation_id'),
        'root_event': context.get('_root_event_id'),
        'depth': context.get('_event_depth', 0)
    })
    
    # Route to originating agent if identified
    if client_id and client_id.startswith('agent_'):
        agent_error = {
            "agent_id": client_id.replace('agent_', ''),  # Remove prefix
            "error_type": error_type,
            "error": data,
            "failed_operation": context.get('_root_event_id'),
            "processing_depth": context.get('_event_depth', 0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "_ksi_context": context  # Preserve full context chain
        }
        
        # Emit agent-specific error event
        emit = get_event_emitter()
        if emit:
            await emit("agent:error", agent_error)
            logger.info(f"Routed error to agent {client_id}")
    
    # Also emit to monitor for system-wide observability
    monitor_event = {
        "error_type": error_type,
        "severity": ERROR_TYPES.get(error_type, {}).get('severity', 'error'),
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "_ksi_context": context
    }
    
    emit = get_event_emitter()
    if emit:
        await emit("monitor:error", monitor_event)
    
    # Check if error is recoverable and trigger recovery if needed
    error_info = ERROR_TYPES.get(error_type, {})
    if error_info.get('recoverable', False):
        recovery_event = {
            "error_type": error_type,
            "original_error": data,
            "recovery_strategy": "retry",  # Could be enhanced with different strategies
            "_ksi_context": context
        }
        
        if emit:
            await emit("error:recovery:attempt", recovery_event)
    
    return {
        "status": "error_handled",
        "routed_to": client_id if client_id else "monitor_only",
        "error_type": error_type,
        "recoverable": error_info.get('recoverable', False)
    }


async def emit_error_event(error_type: str, error_message: str, 
                          details: Dict[str, Any] = None,
                          context: Dict[str, Any] = None) -> None:
    """
    Emit a standardized error event with proper context.
    
    Args:
        error_type: Type of error (e.g., 'template_resolution', 'validation')
        error_message: Human-readable error message
        details: Additional error details (missing variables, etc.)
        context: KSI context for error routing
    """
    from ksi_daemon.module_manager import get_event_emitter
    
    emit = get_event_emitter()
    if not emit:
        logger.error(f"Cannot emit error event - no emitter available: {error_message}")
        return
    
    error_event = {
        "error_type": error_type,
        "error_message": error_message,
        "details": details or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "_ksi_context": context or {}
    }
    
    await emit(f"error:{error_type}", error_event)


def create_error_response(error_type: str, error_message: str,
                         details: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Create a standardized error response for handlers.
    
    Args:
        error_type: Type of error
        error_message: Human-readable error message
        details: Additional error details
        
    Returns:
        Standardized error response dict
    """
    return {
        "status": "error",
        "error_type": error_type,
        "error": error_message,
        "details": details or {},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# Register error handlers when module is loaded
def register_error_handlers():
    """Register all error event handlers with the event system."""
    from ksi_daemon.module_manager import register_handler
    
    # Register wildcard handler for all error events
    register_handler("error:*", handle_error_events, {
        "description": "Routes errors to originating agents using context chain",
        "parameters": {
            "error_type": "str",
            "error_message": "str",
            "details": "dict",
            "_ksi_context": "dict"
        }
    })
    
    logger.info("Error propagation handlers registered")


# Auto-register when imported
try:
    register_error_handlers()
except Exception as e:
    logger.warning(f"Could not auto-register error handlers: {e}")