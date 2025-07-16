#!/usr/bin/env python3

"""
Timestamp Utilities - Centralized timestamp generation and formatting
Ensures consistent timezone handling across the entire KSI system

Standard: All internal timestamps use UTC with 'Z' suffix (ISO 8601)
Display: Local time conversion available for user-facing output
"""

from datetime import datetime, timezone
import time
from typing import Optional, Union


def utc_now() -> datetime:
    """Get current UTC datetime with timezone awareness"""
    return datetime.now(timezone.utc)


def timestamp_utc() -> str:
    """
    Generate ISO 8601 UTC timestamp with 'Z' suffix
    Standard format for all internal logging and storage
    
    Returns:
        str: e.g., "2025-06-20T23:17:27.832348Z"
    """
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def timestamp_local_iso() -> str:
    """
    Generate ISO 8601 local timestamp with timezone offset
    For backward compatibility where local time is expected
    
    Returns:
        str: e.g., "2025-06-20T19:17:27.832348-04:00"
    """
    return datetime.now().astimezone().isoformat()


def filename_timestamp(utc: bool = False) -> str:
    """
    Generate timestamp suitable for filenames
    
    Args:
        utc: If True, use UTC time. If False, use local time.
        
    Returns:
        str: e.g., "20250620_191724" or with 'Z' suffix for UTC
    """
    dt = datetime.now(timezone.utc) if utc else datetime.now()
    # Modified to match the version from chat_textual.py
    return dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ' if utc else '%Y-%m-%d_%H-%M-%S')


def display_timestamp(format: str = '%Y-%m-%d %H:%M:%S', utc: bool = False) -> str:
    """
    Generate human-readable timestamp for display
    
    Args:
        format: strftime format string
        utc: If True, show UTC time. If False, show local time.
        
    Returns:
        str: Formatted timestamp
    """
    dt = datetime.now(timezone.utc) if utc else datetime.now()
    return dt.strftime(format)


def parse_iso_timestamp(timestamp_str: str) -> datetime:
    """
    Parse ISO 8601 timestamp with proper timezone handling
    Handles both 'Z' suffix and timezone offsets
    
    Args:
        timestamp_str: ISO 8601 timestamp string
        
    Returns:
        datetime: Timezone-aware datetime object
    """
    # Handle 'Z' suffix for UTC
    if timestamp_str.endswith('Z'):
        timestamp_str = timestamp_str[:-1] + '+00:00'
    
    # Parse with timezone
    try:
        return datetime.fromisoformat(timestamp_str)
    except ValueError:
        # Fallback for timestamps without timezone
        dt = datetime.fromisoformat(timestamp_str)
        # Assume local time if no timezone specified
        return dt.astimezone()


def utc_to_local(utc_timestamp: Union[str, datetime]) -> datetime:
    """
    Convert UTC timestamp to local timezone
    
    Args:
        utc_timestamp: UTC datetime or ISO string
        
    Returns:
        datetime: Local timezone datetime
    """
    if isinstance(utc_timestamp, str):
        utc_timestamp = parse_iso_timestamp(utc_timestamp)
    
    # Ensure UTC timezone if not specified
    if utc_timestamp.tzinfo is None:
        utc_timestamp = utc_timestamp.replace(tzinfo=timezone.utc)
    
    return utc_timestamp.astimezone()


def local_to_utc(local_timestamp: Union[str, datetime]) -> datetime:
    """
    Convert local timestamp to UTC
    
    Args:
        local_timestamp: Local datetime or ISO string
        
    Returns:
        datetime: UTC datetime
    """
    if isinstance(local_timestamp, str):
        local_timestamp = parse_iso_timestamp(local_timestamp)
    
    # Ensure local timezone if not specified
    if local_timestamp.tzinfo is None:
        local_timestamp = local_timestamp.astimezone()
    
    return local_timestamp.astimezone(timezone.utc)


def format_for_logging() -> str:
    """Standard timestamp format for log entries"""
    return timestamp_utc()


def format_for_display(include_seconds: bool = True) -> str:
    """Standard timestamp format for user display"""
    fmt = '%H:%M:%S' if include_seconds else '%H:%M'
    return display_timestamp(fmt)


def format_for_message_bus() -> str:
    """Standard timestamp format for message bus"""
    return timestamp_utc()


def get_timezone_offset() -> str:
    """
    Get current timezone offset from UTC
    
    Returns:
        str: e.g., "-04:00" for EDT
    """
    local_time = datetime.now().astimezone()
    return local_time.strftime('%z')


def ensure_utc_suffix(timestamp_str: str) -> str:
    """
    Ensure timestamp has proper UTC indicator
    Adds 'Z' if missing and timestamp appears to be UTC
    
    Args:
        timestamp_str: Timestamp string
        
    Returns:
        str: Timestamp with proper UTC indicator
    """
    if timestamp_str.endswith('Z') or '+' in timestamp_str or '-' in timestamp_str[-6:]:
        return timestamp_str
    
    # Check if it looks like a UTC timestamp without suffix
    if 'T' in timestamp_str and timestamp_str.count(':') >= 2:
        return timestamp_str + 'Z'
    
    return timestamp_str


def created_at_timestamp() -> str:
    """
    Generate a creation timestamp for metadata.
    Returns UTC timestamp in ISO format suitable for component metadata.
    
    Returns:
        str: ISO 8601 UTC timestamp with Z suffix
    """
    return timestamp_utc()


def numeric_to_iso(timestamp: float) -> str:
    """
    Convert numeric timestamp (Unix epoch) to ISO 8601 UTC format with 'Z' suffix
    
    Args:
        timestamp: Numeric timestamp from time.time()
        
    Returns:
        str: ISO 8601 UTC timestamp, e.g., "2025-06-20T23:17:27.832348Z"
    """
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace('+00:00', 'Z')


def sanitize_for_json(data: Union[dict, list, str, int, float, bool, None]) -> Union[dict, list, str, int, float, bool, None]:
    """
    Recursively convert date/datetime objects to ISO strings for JSON serialization.
    
    This function handles the common issue where YAML parsing converts date strings
    like "2025-01-16" to Python date objects, which then fail JSON serialization.
    
    Args:
        data: Any data structure that may contain date/datetime objects
        
    Returns:
        The same data structure with date/datetime objects converted to ISO strings
        
    Example:
        >>> from datetime import date, datetime
        >>> data = {"created": date(2025, 1, 16), "updated": datetime.now()}
        >>> sanitized = sanitize_for_json(data)
        >>> # {"created": "2025-01-16", "updated": "2025-01-16T12:34:56.789Z"}
    """
    from datetime import date, datetime
    
    if isinstance(data, datetime):
        # Convert datetime to ISO string with Z suffix
        return data.isoformat().replace('+00:00', 'Z') if data.tzinfo else data.isoformat() + 'Z'
    elif isinstance(data, date):
        # Convert date to ISO string
        return data.isoformat()
    elif isinstance(data, dict):
        # Recursively process dictionary values
        return {key: sanitize_for_json(value) for key, value in data.items()}
    elif isinstance(data, list):
        # Recursively process list items
        return [sanitize_for_json(item) for item in data]
    elif isinstance(data, tuple):
        # Convert tuples to lists and process
        return [sanitize_for_json(item) for item in data]
    else:
        # Return primitive types as-is
        return data


