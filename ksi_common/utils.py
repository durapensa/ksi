"""Common utilities for KSI.

Provides utility functions used across KSI components.
"""

import json
import uuid
from typing import Dict, Any, Optional, Union
from pathlib import Path


def generate_id(prefix: Optional[str] = None) -> str:
    """Generate a unique ID with optional prefix.
    
    Args:
        prefix: Optional prefix for the ID
        
    Returns:
        Unique ID string
    """
    unique_part = uuid.uuid4().hex[:8]
    if prefix:
        return f"{prefix}_{unique_part}"
    return unique_part


def generate_session_id() -> str:
    """Generate a unique session ID.
    
    Returns:
        Full UUID string suitable for session tracking
    """
    return str(uuid.uuid4())


def generate_correlation_id() -> str:
    """Generate a correlation ID for request/response tracking.
    
    Returns:
        Full UUID string
    """
    return str(uuid.uuid4())


def safe_json_loads(data: Union[str, bytes], default: Any = None) -> Any:
    """Safely parse JSON with fallback.
    
    Args:
        data: JSON string or bytes to parse
        default: Default value on parse failure
        
    Returns:
        Parsed JSON or default value
    """
    try:
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        return json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        return default


def safe_json_dumps(data: Any, default: str = "{}") -> str:
    """Safely serialize to JSON with fallback.
    
    Args:
        data: Data to serialize
        default: Default string on serialization failure
        
    Returns:
        JSON string or default
    """
    try:
        return json.dumps(data)
    except (TypeError, ValueError):
        return default


def format_bytes(num_bytes: int) -> str:
    """Format bytes into human-readable string.
    
    Args:
        num_bytes: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if num_bytes < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate string to maximum length with suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncated
        
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    
    if max_length <= len(suffix):
        return suffix[:max_length]
    
    return text[:max_length - len(suffix)] + suffix


def ensure_list(value: Any) -> list:
    """Ensure value is a list.
    
    Args:
        value: Value to ensure is a list
        
    Returns:
        Value as list (wrapped if necessary)
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def merge_dicts(base: Dict[str, Any], updates: Dict[str, Any], 
                deep: bool = False) -> Dict[str, Any]:
    """Merge two dictionaries.
    
    Args:
        base: Base dictionary
        updates: Updates to apply
        deep: Whether to do deep merge (recursive)
        
    Returns:
        Merged dictionary (new instance)
    """
    result = base.copy()
    
    if not deep:
        result.update(updates)
        return result
    
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value, deep=True)
        else:
            result[key] = value
    
    return result


def read_json_file(path: Union[str, Path], default: Any = None) -> Any:
    """Read and parse JSON file.
    
    Args:
        path: Path to JSON file
        default: Default value if file doesn't exist or parse fails
        
    Returns:
        Parsed JSON or default
    """
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return default


def write_json_file(path: Union[str, Path], data: Any, 
                   indent: int = 2, ensure_dir: bool = True) -> bool:
    """Write data to JSON file.
    
    Args:
        path: Path to write to
        data: Data to serialize
        indent: JSON indentation
        ensure_dir: Whether to create parent directory
        
    Returns:
        True if successful
    """
    try:
        path = Path(path)
        if ensure_dir:
            path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=indent)
        return True
    except (IOError, TypeError, ValueError):
        return False