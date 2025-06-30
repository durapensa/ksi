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


def generate_correlation_id() -> str:
    """Generate a correlation ID for request/response tracking.
    
    Returns:
        Full UUID string
    """
    return str(uuid.uuid4())


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