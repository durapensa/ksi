#!/usr/bin/env python3
"""
Event Utilities - Common patterns for KSI event system

Provides consistent patterns for:
- Emitting events and handling responses
- Single response extraction from lists
- Error handling for event responses
- Event validation
- Working with event system's list-based results
"""

from typing import Any, Dict, List, Optional, Union, TypeVar, Callable
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("event_utils")

T = TypeVar('T')


class EventResult:
    """Wrapper for event system results handling single/multiple responses."""
    
    def __init__(self, result: Union[List[Any], Any]):
        """Initialize with event system result (list or single value)."""
        self._raw = result
        # Normalize to list format (event system should always return lists)
        if isinstance(result, list):
            self._results = result
        elif result is not None:
            self._results = [result]
        else:
            self._results = []
    
    @property
    def single(self) -> Optional[Dict[str, Any]]:
        """Get first result or None."""
        return self._results[0] if self._results else None
    
    @property
    def all(self) -> List[Any]:
        """Get all results as list."""
        return self._results
    
    @property
    def count(self) -> int:
        """Get number of results."""
        return len(self._results)
    
    @property
    def empty(self) -> bool:
        """Check if no results."""
        return len(self._results) == 0
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from first result dict."""
        if self.single and isinstance(self.single, dict):
            return self.single.get(key, default)
        return default
    
    @property
    def error(self) -> Optional[str]:
        """Get error from first result if any."""
        return self.get("error")
    
    @property
    def success(self) -> bool:
        """Check if first result indicates success (no error)."""
        return self.single is not None and not self.error
    
    @property
    def status(self) -> Optional[str]:
        """Get status from first result."""
        return self.get("status")
    
    def __bool__(self) -> bool:
        """Truthiness based on having results."""
        return not self.empty
    
    def __len__(self) -> int:
        """Length is number of results."""
        return self.count
    
    def __iter__(self):
        """Iterate over results."""
        return iter(self._results)
    
    def __getitem__(self, index: int) -> Any:
        """Get result by index."""
        return self._results[index]


async def emit_single(event_emitter: Callable, event: str, data: Any = None, 
                     context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Emit event and return single result.
    
    Args:
        event_emitter: The event emitter function (usually router.emit)
        event: Event name to emit
        data: Event data
        context: Event context
        
    Returns:
        First result dict or None if no results
        
    Note:
        Logs warning if multiple results returned (indicates unexpected multiple handlers)
    """
    results = await event_emitter(event, data, context)
    
    if not results:
        return None
    elif len(results) == 1:
        return results[0]
    else:
        logger.warning(f"emit_single() got {len(results)} results for {event}, expected 1. Using first result.")
        return results[0]


async def emit_for_single(event_emitter: Callable, event: str, data: Any = None,
                         context: Optional[Dict[str, Any]] = None) -> EventResult:
    """
    Emit event and return EventResult wrapper optimized for single results.
    
    Args:
        event_emitter: The event emitter function (usually router.emit)
        event: Event name to emit  
        data: Event data
        context: Event context
        
    Returns:
        EventResult wrapper for convenient access
    """
    results = await event_emitter(event, data, context)
    return EventResult(results)


def require_single_result(results: List[Any], event_name: str = "unknown") -> Dict[str, Any]:
    """
    Extract single result, raising error if not exactly one.
    
    Args:
        results: List of results from event system
        event_name: Event name for error messages
        
    Returns:
        Single result dict
        
    Raises:
        ValueError: If not exactly one result
    """
    if not results:
        raise ValueError(f"Expected exactly 1 result for {event_name}, got 0")
    elif len(results) > 1:
        raise ValueError(f"Expected exactly 1 result for {event_name}, got {len(results)}")
    
    return results[0]


def safe_get_from_results(results: List[Any], key: str, default: Any = None) -> Any:
    """
    Safely get a key from the first result dict.
    
    Args:
        results: List of results from event system
        key: Key to extract
        default: Default value if key not found
        
    Returns:
        Value from first result or default
    """
    if results and isinstance(results[0], dict):
        return results[0].get(key, default)
    return default


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


def get_nested_value(
    data: Dict[str, Any],
    path: str,
    default: Any = None,
    separator: str = "."
) -> Any:
    """
    Get value from nested dictionary using dot notation.
    
    Args:
        data: Dictionary to search
        path: Dot-separated path (e.g., "result.ksi.metadata")
        default: Default value if path not found
        separator: Path separator (default ".")
        
    Returns:
        Value at path or default
        
    Examples:
        >>> data = {"result": {"ksi": {"metadata": {"type": "test"}}}}
        >>> get_nested_value(data, "result.ksi.metadata.type")
        'test'
        >>> get_nested_value(data, "result.missing.path", "default")
        'default'
    """
    try:
        keys = path.split(separator)
        value = data
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
                
        return value
    except (AttributeError, TypeError):
        return default