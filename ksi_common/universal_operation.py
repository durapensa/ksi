#!/usr/bin/env python3
"""
Universal operation decorator ensuring all KSI operations follow response architecture.

This module provides the @ksi_operation decorator that:
1. Ensures all operations return standardized responses
2. Catches and propagates all errors through system:error
3. Preserves context through all operations
4. Handles both sync and async operations
5. Supports async patterns with acknowledgment + delivery
"""

import asyncio
import uuid
import logging
from functools import wraps
from typing import Any, Dict, Optional, Callable

from ksi_common.event_response_builder import (
    event_response_builder, 
    error_response, 
    async_response
)

logger = logging.getLogger(__name__)


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return f"req_{uuid.uuid4().hex[:8]}"


def ksi_operation(operation_type: str = "handler", async_pattern: Optional[str] = None):
    """
    Universal decorator ensuring ALL operations follow response architecture.
    
    This decorator:
    - Wraps all returns in event_response_builder
    - Catches all exceptions and emits system:error events
    - Preserves _ksi_context through all operations
    - Handles async patterns with proper acknowledgment
    
    Args:
        operation_type: Type of operation (handler|transformer|service)
        async_pattern: If set, indicates async operation pattern (e.g., "completion")
        
    Returns:
        Decorated function with universal response handling
    """
    def decorator(func: Callable) -> Callable:
        
        @wraps(func)
        async def async_wrapper(data: Any, context: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
            """Async wrapper with universal response handling."""
            # Lazy import to avoid circular dependency
            from ksi_daemon.event_system import get_router
            router = get_router()
            emit = router.emit if router else None
            
            # Ensure context exists and has proper structure
            if context is None:
                context = {}
                logger.warning(f"No context provided to {func.__name__}, error propagation may not work")
            
            # Preserve original context for error propagation
            original_context = context.copy()
            
            try:
                # Run the actual operation
                result = await func(data, context, **kwargs)
                
                # Handle None returns
                if result is None:
                    result = {"status": "completed"}
                
                # For async patterns, ensure acknowledgment format
                if async_pattern == "completion":
                    # Check if it's already a proper async response
                    if not isinstance(result, dict):
                        result = {"status": "accepted"}
                    
                    if "request_id" not in result:
                        # Generate request_id if missing
                        request_id = data.get("request_id", generate_request_id())
                        result["request_id"] = request_id
                    
                    # Ensure async response format
                    if "_ksi_context" not in result:
                        result = async_response(
                            request_id=result.get("request_id"),
                            status=result.get("status", "processing"),
                            context=context
                        )
                
                # Ensure response uses standard builder
                elif not isinstance(result, dict) or "_ksi_context" not in result:
                    result = event_response_builder(result, context)
                
                # NEW: Emit success result for routing back to originator
                if emit and isinstance(result, dict) and result.get("status") in ["success", "completed", None]:
                    # Extract context for success routing
                    ksi_context_ref = None
                    if isinstance(data, dict):
                        ksi_context_ref = data.get("_ksi_context")
                    if not ksi_context_ref and context:
                        ksi_context_ref = context.get("_ksi_context")
                    if not ksi_context_ref:
                        ksi_context_ref = ""
                    
                    # Build success event for routing
                    success_event = {
                        "result_type": f"{operation_type}_success",
                        "result_data": result,
                        "source": {
                            "operation": func.__name__,
                            "module": func.__module__,
                            "operation_type": operation_type
                        },
                        "_ksi_context": ksi_context_ref
                    }
                    
                    # Emit to universal success handler for propagation
                    try:
                        await emit("system:result", success_event)
                    except Exception as emit_error:
                        logger.debug(f"Could not emit system:result: {emit_error}")
                
                return result
                
            except Exception as e:
                # Log the error locally
                logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                
                # Extract context for error routing
                # PYTHONIC CONTEXT REFACTOR: _ksi_context is now a reference string
                ksi_context_ref = None
                if isinstance(data, dict):
                    ksi_context_ref = data.get("_ksi_context")
                if not ksi_context_ref and context:
                    ksi_context_ref = context.get("_ksi_context")
                if not ksi_context_ref:
                    ksi_context_ref = ""
                
                # Build comprehensive error event
                error_event = {
                    "error_type": f"{operation_type}_failure",
                    "error_class": type(e).__name__,
                    "error_message": str(e),
                    "source": {
                        "operation": func.__name__,
                        "module": func.__module__,
                        "operation_type": operation_type
                    },
                    "original_data": data if isinstance(data, dict) else {"data": str(data)},
                    "_ksi_context": ksi_context_ref  # Pass the reference string as-is
                }
                
                # Debug log what we're emitting
                logger.info(f"Emitting system:error with data type: {type(error_event)}, keys: {list(error_event.keys())}")
                logger.info(f"_ksi_context value: {error_event.get('_ksi_context')}")
                
                # Emit to universal error handler for propagation
                if emit:
                    try:
                        await emit("system:error", error_event)
                    except Exception as emit_error:
                        logger.error(f"Failed to emit system:error: {emit_error}")
                
                # For async operations with agent context, also inject error directly
                # Need to extract client_id from context dict, not from _ksi_context
                client_id = context.get("_client_id", "") if context else ""
                if async_pattern == "completion" and client_id.startswith("agent_"):
                    agent_id = client_id[6:]
                    if emit:
                        try:
                            await emit("completion:inject", {
                                "agent_id": agent_id,
                                "messages": [{
                                    "role": "system",
                                    "content": f"ERROR in {func.__name__}: {e}\nType: {type(e).__name__}"
                                }]
                            })
                        except Exception as inject_error:
                            logger.error(f"Failed to inject error to agent: {inject_error}")
                
                # Return standardized error response for immediate consumption
                return error_response(
                    str(e), 
                    context=original_context,
                    details={
                        "error_type": type(e).__name__,
                        "operation": func.__name__,
                        "module": func.__module__
                    }
                )
        
        @wraps(func)
        def sync_wrapper(data: Any, context: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
            """Sync wrapper with universal response handling."""
            # Lazy import to avoid circular dependency
            from ksi_daemon.event_system import get_router
            router = get_router()
            emit = router.emit if router else None
            
            # Ensure context exists
            if context is None:
                context = {}
                logger.warning(f"No context provided to {func.__name__}, error propagation may not work")
            
            # Preserve original context
            original_context = context.copy()
            
            try:
                # Run the actual operation
                result = func(data, context, **kwargs)
                
                # Handle None returns
                if result is None:
                    result = {"status": "completed"}
                
                # Ensure response uses standard builder
                if not isinstance(result, dict) or "_ksi_context" not in result:
                    result = event_response_builder(result, context)
                
                return result
                
            except Exception as e:
                # Log the error locally
                logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                
                # Extract context for error routing
                # PYTHONIC CONTEXT REFACTOR: _ksi_context is now a reference string
                ksi_context_ref = None
                if isinstance(data, dict):
                    ksi_context_ref = data.get("_ksi_context")
                if not ksi_context_ref and context:
                    ksi_context_ref = context.get("_ksi_context")
                if not ksi_context_ref:
                    ksi_context_ref = ""
                
                # Build error event
                error_event = {
                    "error_type": f"{operation_type}_failure",
                    "error_class": type(e).__name__,
                    "error_message": str(e),
                    "source": {
                        "operation": func.__name__,
                        "module": func.__module__,
                        "operation_type": operation_type
                    },
                    "original_data": data if isinstance(data, dict) else {"data": str(data)},
                    "_ksi_context": ksi_context_ref  # Pass the reference string as-is
                }
                
                # Emit to universal error handler (sync emit if available)
                if emit:
                    try:
                        # Try to emit synchronously if possible
                        asyncio.create_task(emit("system:error", error_event))
                    except Exception as emit_error:
                        logger.error(f"Failed to emit system:error: {emit_error}")
                
                # Return standardized error response
                return error_response(
                    str(e),
                    context=original_context,
                    details={
                        "error_type": type(e).__name__,
                        "operation": func.__name__,
                        "module": func.__module__
                    }
                )
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator


# Export public API
__all__ = ['ksi_operation', 'generate_request_id']