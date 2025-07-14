#!/usr/bin/env python3
"""
Utilities for consuming event responses in KSI.

Event responses follow a standard transport envelope format:
{
    "event": "event_name",
    "data": <response_data>,
    "count": <number_of_responses>,
    "correlation_id": <optional_id>,
    "timestamp": <event_time>
}

This module provides helpers to extract data from these responses.
"""
from typing import Any, Dict, List, Optional, Union, TypeVar

T = TypeVar('T')


def get_response_data(response: Dict[str, Any]) -> Any:
    """Extract the data payload from an event response.
    
    Handles the transport envelope and returns the actual response data.
    For single responses (count=1), returns the unwrapped object.
    For multiple responses, returns the array.
    
    Args:
        response: The full event response with transport envelope
        
    Returns:
        The data payload (could be dict, list, str, etc.)
    """
    if not isinstance(response, dict):
        return response
        
    # Extract data from transport envelope
    data = response.get("data")
    
    # If no envelope, assume response IS the data
    if "event" not in response and "data" not in response:
        return response
        
    return data


def get_single_response(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract a single response, handling multi-response format.
    
    If multiple handlers responded, returns the first non-error response.
    
    Args:
        response: The full event response
        
    Returns:
        The first valid response dict, or None
    """
    data = get_response_data(response)
    
    if data is None:
        return None
        
    # If data is a list (multiple handlers), get first valid response
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "error" not in item:
                return item
        # No valid responses, return first item anyway
        return data[0] if data else None
        
    # Single response
    return data if isinstance(data, dict) else None


def extract_field(response: Dict[str, Any], field: str, default: T = None) -> Union[T, Any]:
    """Extract a specific field from an event response.
    
    Handles transport envelope, multi-response format, and nested fields.
    
    Args:
        response: The full event response
        field: Field name to extract (supports dot notation like "result.session_id")
        default: Default value if field not found
        
    Returns:
        The field value or default
    """
    # Get the actual response data
    data = get_single_response(response)
    
    if not isinstance(data, dict):
        return default
        
    # Handle dot notation for nested fields
    if "." in field:
        parts = field.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current
    
    # Simple field lookup
    return data.get(field, default)


def extract_originator(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract originator information from an event response.
    
    Looks for originator info in both the envelope and response data.
    
    Args:
        response: The full event response
        
    Returns:
        Dict with originator fields (originator_id, agent_id, session_id, etc.) or None
    """
    originator = {}
    
    # Check envelope level first
    if isinstance(response, dict):
        for field in ["originator_id", "agent_id", "session_id", "correlation_id"]:
            if field in response:
                originator[field] = response[field]
    
    # Check response data
    data = get_single_response(response)
    if isinstance(data, dict):
        # Direct originator dict
        if "originator" in data and isinstance(data["originator"], dict):
            originator.update(data["originator"])
        
        # Individual fields
        for field in ["originator_id", "agent_id", "session_id", "correlation_id"]:
            if field in data and field not in originator:
                originator[field] = data[field]
    
    return originator if originator else None


def has_error(response: Dict[str, Any]) -> bool:
    """Check if an event response contains an error.
    
    Args:
        response: The full event response
        
    Returns:
        True if response contains an error
    """
    # Check envelope level
    if isinstance(response, dict) and "error" in response:
        return True
        
    # Check response data
    data = get_response_data(response)
    
    if isinstance(data, dict) and "error" in data:
        return True
        
    if isinstance(data, list):
        # All responses are errors
        return all(isinstance(item, dict) and "error" in item for item in data)
        
    return False


def get_error_message(response: Dict[str, Any]) -> Optional[str]:
    """Extract error message from an event response.
    
    Args:
        response: The full event response
        
    Returns:
        Error message string or None
    """
    # Check envelope level
    if isinstance(response, dict) and "error" in response:
        return str(response["error"])
        
    # Check response data
    data = get_response_data(response)
    
    if isinstance(data, dict) and "error" in data:
        return str(data["error"])
        
    if isinstance(data, list):
        # Get first error
        for item in data:
            if isinstance(item, dict) and "error" in item:
                return str(item["error"])
                
    return None


def get_handler_info(response: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Extract handler information from response.
    
    Args:
        response: The full event response
        
    Returns:
        Dict with handler name and event_processed status, or None
    """
    data = get_single_response(response)
    
    if not isinstance(data, dict):
        return None
        
    info = {}
    if "handler" in data:
        info["handler"] = data["handler"]
    if "event_processed" in data:
        info["event_processed"] = data["event_processed"]
    if "event" in data:
        info["event"] = data["event"]
        
    return info if info else None


# Specific field extractors for common patterns
def get_request_id(response: Dict[str, Any]) -> Optional[str]:
    """Extract request_id from completion:async or similar responses."""
    return extract_field(response, "request_id")


def get_agent_id(response: Dict[str, Any]) -> Optional[str]:
    """Extract agent_id from agent:spawn or similar responses."""
    return extract_field(response, "agent_id")


def get_session_id(response: Dict[str, Any]) -> Optional[str]:
    """Extract session_id from responses."""
    # Check multiple possible locations
    session_id = extract_field(response, "session_id")
    if not session_id:
        session_id = extract_field(response, "result.session_id")
    return session_id


def get_status(response: Dict[str, Any]) -> Optional[str]:
    """Extract status field from responses."""
    return extract_field(response, "status")