#!/usr/bin/env python3
"""
Event Utilities - Common patterns for KSI event system

Provides consistent patterns for:
- Emitting events and handling responses
- Single response extraction
- Error handling for event responses
- Event validation
"""

from typing import Any, Dict, List, Optional, Union, TypeVar, Callable
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("event_utils")

T = TypeVar('T')


def extract_single_response(
    result: Union[List[Dict[str, Any]], Dict[str, Any], None]
) -> Dict[str, Any]:
    """
    Extract single response from event result.
    
    Many event handlers return a list but we expect a single response.
    This utility handles that pattern consistently.
    
    Args:
        result: Event response (list, dict, or None)
        
    Returns:
        Single response dict (empty dict if no response)
    """
    if result is None:
        return {}
    
    if isinstance(result, list):
        return result[0] if result else {}
    
    return result


def is_success_response(response: Dict[str, Any]) -> bool:
    """
    Check if event response indicates success.
    
    Args:
        response: Event response
        
    Returns:
        True if successful (no error and status is not failed)
    """
    if not response:
        return False
    
    # Check for explicit error
    if "error" in response:
        return False
    
    # Check status field if present
    status = response.get("status")
    if status and status in ["error", "failed"]:
        return False
    
    return True


def get_response_error(response: Dict[str, Any]) -> Optional[str]:
    """
    Extract error message from response.
    
    Args:
        response: Event response
        
    Returns:
        Error message if present, None otherwise
    """
    if not response:
        return None
    
    # Direct error field
    if "error" in response:
        return str(response["error"])
    
    # Status with message
    if response.get("status") in ["error", "failed"]:
        return response.get("message", "Unknown error")
    
    return None


async def emit_and_extract(
    event_emitter: Callable,
    event: str,
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Emit event and extract single response.
    
    Common pattern combining emit_event with single response extraction.
    
    Args:
        event_emitter: The emit_event function
        event: Event name
        data: Event data
        
    Returns:
        Single response dict
    """
    result = await event_emitter(event, data)
    return extract_single_response(result)


async def emit_and_check(
    event_emitter: Callable,
    event: str,
    data: Dict[str, Any]
) -> tuple[bool, Dict[str, Any]]:
    """
    Emit event and check for success.
    
    Args:
        event_emitter: The emit_event function
        event: Event name
        data: Event data
        
    Returns:
        Tuple of (success, response)
    """
    response = await emit_and_extract(event_emitter, event, data)
    success = is_success_response(response)
    return success, response


def validate_event_data(
    event: str,
    data: Dict[str, Any],
    required_fields: List[str]
) -> Optional[str]:
    """
    Validate event data has required fields.
    
    Args:
        event: Event name (for error messages)
        data: Event data to validate
        required_fields: List of required field names
        
    Returns:
        Error message if validation fails, None if valid
    """
    missing = [field for field in required_fields if field not in data]
    
    if missing:
        return f"{event} missing required fields: {', '.join(missing)}"
    
    return None


def build_error_response(
    error: Union[str, Exception],
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build standardized error response.
    
    Args:
        error: Error message or exception
        details: Additional error details
        
    Returns:
        Error response dict
    """
    response = {
        "status": "error",
        "error": str(error)
    }
    
    if details:
        response["details"] = details
    
    return response


def build_success_response(
    data: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Build standardized success response.
    
    Args:
        data: Response data
        message: Success message
        **kwargs: Additional fields
        
    Returns:
        Success response dict
    """
    response = {"status": "success"}
    
    if message:
        response["message"] = message
    
    if data:
        response.update(data)
    
    response.update(kwargs)
    
    return response


class EventResponseHandler:
    """
    Context manager for consistent event response handling.
    
    Usage:
        async with EventResponseHandler("my_event") as handler:
            # Do work
            result = await some_operation()
            return handler.success({"result": result})
    """
    
    def __init__(self, event_name: str):
        self.event_name = event_name
        self.start_time = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.error(f"{self.event_name} failed: {exc_val}")
        return False
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.error(f"{self.event_name} failed: {exc_val}")
        return False
    
    def success(self, data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Build success response."""
        return build_success_response(data, **kwargs)
    
    def error(self, error: Union[str, Exception], **kwargs) -> Dict[str, Any]:
        """Build error response."""
        return build_error_response(error, **kwargs)


def merge_event_responses(responses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge multiple event responses into one.
    
    Useful for aggregating results from multiple handlers.
    
    Args:
        responses: List of responses to merge
        
    Returns:
        Merged response
    """
    if not responses:
        return {}
    
    # If only one response, return it
    if len(responses) == 1:
        return responses[0]
    
    # Check if any failed
    errors = []
    results = []
    
    for response in responses:
        if not is_success_response(response):
            error = get_response_error(response)
            if error:
                errors.append(error)
        else:
            results.append(response)
    
    # If any errors, return error response
    if errors:
        return build_error_response(
            f"Multiple errors: {'; '.join(errors)}",
            {"error_count": len(errors), "success_count": len(results)}
        )
    
    # Merge successful responses
    merged = {"status": "success", "merged_count": len(results)}
    
    # Merge data from all responses
    for response in results:
        for key, value in response.items():
            if key == "status":
                continue
            
            if key not in merged:
                merged[key] = value
            elif isinstance(merged[key], list) and isinstance(value, list):
                merged[key].extend(value)
            elif isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key].update(value)
    
    return merged