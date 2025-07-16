#!/usr/bin/env python3
"""
File Utilities - Common file operations for KSI system

Provides consistent patterns for:
- YAML file loading/saving with error handling
- Creating timestamped filenames
- Ensuring directories exist
- Atomic file writes
"""

from pathlib import Path
from typing import Any, Dict, Optional, Union
import tempfile
import shutil

# Import new centralized utilities
from ksi_common.yaml_utils import YAMLProcessor
from ksi_common.json_utils import JSONProcessor
from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import filename_timestamp

logger = get_bound_logger("file_utils")

# Create global processor instances for file operations
_yaml_processor = YAMLProcessor()
_json_processor = JSONProcessor()


def load_yaml_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load YAML file with consistent error handling.
    
    Args:
        file_path: Path to YAML file
        
    Returns:
        Parsed YAML content
        
    Raises:
        FileNotFoundError: If file doesn't exist
        YAMLParseError: If YAML parsing fails
    """
    return _yaml_processor.load_file(file_path)


def save_yaml_file(
    file_path: Union[str, Path], 
    data: Any,
    create_dirs: bool = True,
    atomic: bool = True
) -> Path:
    """
    Save data to YAML file with consistent formatting.
    
    Args:
        file_path: Target file path
        data: Data to save
        create_dirs: Create parent directories if needed
        atomic: Use atomic write (write to temp file then rename)
        
    Returns:
        Path to saved file
    """
    _yaml_processor.save_file(file_path, data, create_dirs=create_dirs, atomic=atomic)
    return Path(file_path)


def load_json_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load JSON file with consistent error handling.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Parsed JSON content
        
    Raises:
        FileNotFoundError: If file doesn't exist
        JSONParseError: If JSON parsing fails
    """
    return _json_processor.load_file(file_path)


def save_json_file(
    file_path: Union[str, Path],
    data: Any,
    create_dirs: bool = True,
    atomic: bool = True
) -> Path:
    """
    Save data to JSON file with consistent formatting.
    
    Args:
        file_path: Target file path
        data: Data to save
        create_dirs: Create parent directories if needed
        atomic: Use atomic write
        
    Returns:
        Path to saved file
    """
    _json_processor.save_file(file_path, data, create_dirs=create_dirs, atomic=atomic)
    return Path(file_path)


def create_timestamped_filename(
    base_name: str,
    extension: str = "yaml",
    use_utc: bool = True,
    include_seconds: bool = True
) -> str:
    """
    Create a timestamped filename.
    
    Args:
        base_name: Base name for the file
        extension: File extension (without dot)
        use_utc: Use UTC timestamp (recommended)
        include_seconds: Include seconds in timestamp
        
    Returns:
        Filename like "base_name_20250709_142355.yaml"
    """
    timestamp = filename_timestamp(utc=use_utc, include_seconds=include_seconds)
    return f"{base_name}_{timestamp}.{extension}"


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Ensure directory exists, creating if needed.
    
    Args:
        path: Directory path
        
    Returns:
        Path object for the directory
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def safe_file_operation(operation, *args, **kwargs):
    """
    Execute file operation with consistent error handling.
    
    Args:
        operation: Function to execute
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Result of operation
        
    Raises:
        Original exception with added context
    """
    try:
        return operation(*args, **kwargs)
    except Exception as e:
        # Add context about which operation failed
        logger.error(f"File operation {operation.__name__} failed: {e}")
        raise


# Convenience functions for evaluation results
def save_evaluation_result(
    result_data: Dict[str, Any],
    result_type: str,
    base_dir: Path,
    use_timestamp: bool = True
) -> Path:
    """
    Save evaluation result with standard naming.
    
    Args:
        result_data: Result data to save
        result_type: Type of result (e.g., "bootstrap", "tournament", "iteration")
        base_dir: Base directory for results
        use_timestamp: Include timestamp in filename
        
    Returns:
        Path to saved file
    """
    ensure_directory(base_dir)
    
    if use_timestamp:
        filename = create_timestamped_filename(f"{result_type}_results")
    else:
        filename = f"{result_type}_results.yaml"
    
    file_path = base_dir / filename
    return save_yaml_file(file_path, result_data, atomic=True)


def load_test_suite(suite_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load test suite with validation.
    
    Args:
        suite_path: Path to test suite YAML
        
    Returns:
        Test suite data
        
    Raises:
        ValueError: If test suite is invalid
    """
    data = load_yaml_file(suite_path)
    
    # Basic validation
    if 'tests' not in data:
        raise ValueError(f"Test suite missing 'tests' field: {suite_path}")
    
    if not isinstance(data['tests'], list):
        raise ValueError(f"Test suite 'tests' must be a list: {suite_path}")
    
    return data