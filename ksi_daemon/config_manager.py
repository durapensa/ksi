#!/usr/bin/env python3
"""
Runtime Configuration Manager

Function-based runtime configuration system for KSI daemon.
Provides dynamic config overrides without requiring daemon restarts.
"""

from typing import Dict, Any, Optional, List, Union
from ksi_common.logging import get_bound_logger
from ksi_common.config import config
from ksi_common.event_utils import build_error_response

logger = get_bound_logger("config_manager")

# Module-level runtime overrides storage
_runtime_overrides: Dict[str, Any] = {}

# Runtime-configurable settings schema
RUNTIME_CONFIG_SCHEMA = {
    "error_verbosity": {
        "type": "str",
        "values": ["minimal", "medium", "verbose"],
        "default": "medium",
        "description": "Error message verbosity level"
    },
    "log_level": {
        "type": "str", 
        "values": ["DEBUG", "INFO", "WARNING", "ERROR"],
        "default": "INFO",
        "description": "Logging level for daemon components"
    },
    "completion_timeout_default": {
        "type": "int",
        "range": [60, 1800],  # 1 minute to 30 minutes
        "default": 300,
        "description": "Default completion timeout in seconds"
    }
}


def set_runtime_config(key: str, value: Any) -> bool:
    """
    Set a runtime configuration override.
    
    Args:
        key: Configuration key to set
        value: Value to set
        
    Returns:
        True if successfully set, False if invalid key/value
    """
    if key not in RUNTIME_CONFIG_SCHEMA:
        logger.warning(f"Unknown runtime config key: {key}")
        return False
    
    schema = RUNTIME_CONFIG_SCHEMA[key]
    
    # Type validation
    expected_type_str = schema["type"]
    type_map = {"str": str, "int": int, "float": float, "bool": bool}
    expected_type = type_map.get(expected_type_str)
    
    if expected_type and not isinstance(value, expected_type):
        # Try type conversion for common cases
        try:
            if expected_type == int:
                value = int(value)
            elif expected_type == str:
                value = str(value)
            elif expected_type == float:
                value = float(value)
            elif expected_type == bool:
                value = bool(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid type for {key}: expected {expected_type_str}, got {type(value).__name__}")
            return False
    
    # Value validation
    if "values" in schema:
        if value not in schema["values"]:
            logger.warning(f"Invalid value for {key}: {value}, allowed: {schema['values']}")
            return False
    
    if "range" in schema:
        min_val, max_val = schema["range"]
        if not (min_val <= value <= max_val):
            logger.warning(f"Value for {key} out of range: {value}, allowed: {min_val}-{max_val}")
            return False
    
    # Store the override
    _runtime_overrides[key] = value
    logger.info(f"Runtime config updated: {key} = {value}")
    
    # Apply immediately to running system
    _apply_runtime_config(key, value)
    
    return True


def get_runtime_config(key: str, fallback: Any = None) -> Any:
    """
    Get runtime config value (override or base config).
    
    Args:
        key: Configuration key to get
        fallback: Fallback value if key not found anywhere
        
    Returns:
        Current value (runtime override, base config, or fallback)
    """
    # Check runtime overrides first
    if key in _runtime_overrides:
        return _runtime_overrides[key]
    
    # Fall back to base config
    if hasattr(config, key):
        return getattr(config, key)
    
    # Fall back to schema default
    if key in RUNTIME_CONFIG_SCHEMA:
        return RUNTIME_CONFIG_SCHEMA[key]["default"]
    
    # Final fallback
    return fallback


def query_runtime_config(key: Optional[str] = None) -> Dict[str, Any]:
    """
    Query available runtime configuration options.
    
    Args:
        key: Optional specific key to query, if None returns all
        
    Returns:
        Configuration schema and current values
    """
    if key is not None:
        if key not in RUNTIME_CONFIG_SCHEMA:
            return build_error_response(f"Unknown config key: {key}")
        
        schema = RUNTIME_CONFIG_SCHEMA[key].copy()
        schema["current"] = get_runtime_config(key)
        schema["source"] = "runtime" if key in _runtime_overrides else "default"
        return {"key": key, **schema}
    
    # Return all runtime-configurable keys
    result = {}
    for config_key, schema in RUNTIME_CONFIG_SCHEMA.items():
        schema_copy = schema.copy()
        schema_copy["current"] = get_runtime_config(config_key)
        schema_copy["source"] = "runtime" if config_key in _runtime_overrides else "default"
        result[config_key] = schema_copy
    
    return {"runtime_config": result}


def reset_runtime_config(key: Optional[str] = None) -> bool:
    """
    Reset runtime config to defaults.
    
    Args:
        key: Optional specific key to reset, if None resets all
        
    Returns:
        True if reset successfully
    """
    if key is not None:
        if key in _runtime_overrides:
            del _runtime_overrides[key]
            logger.info(f"Runtime config reset: {key}")
            
            # Reapply default value
            default_value = RUNTIME_CONFIG_SCHEMA[key]["default"]
            _apply_runtime_config(key, default_value)
            return True
        return False
    
    # Reset all overrides
    keys_to_reset = list(_runtime_overrides.keys())
    _runtime_overrides.clear()
    
    # Reapply defaults
    for reset_key in keys_to_reset:
        default_value = RUNTIME_CONFIG_SCHEMA[reset_key]["default"]
        _apply_runtime_config(reset_key, default_value)
    
    logger.info(f"All runtime config reset ({len(keys_to_reset)} keys)")
    return True


def _apply_runtime_config(key: str, value: Any) -> None:
    """
    Apply runtime configuration immediately to running system.
    
    Args:
        key: Configuration key
        value: New value to apply
    """
    # Special handling for specific config keys
    if key == "log_level":
        # TODO: Apply log level change to running loggers
        logger.debug(f"Applied log_level change: {value}")
    
    elif key == "error_verbosity":
        # Event system will pick this up via get_runtime_config()
        logger.debug(f"Applied error_verbosity change: {value}")
    
    elif key == "completion_timeout_default":
        # Completion service will pick this up via get_runtime_config()
        logger.debug(f"Applied completion_timeout_default change: {value}")
    
    # Note: For some config changes, components will need to check
    # get_runtime_config() to pick up new values dynamically


def get_all_runtime_overrides() -> Dict[str, Any]:
    """Get all current runtime overrides (for debugging)."""
    return _runtime_overrides.copy()


def get_runtime_config_keys() -> List[str]:
    """Get list of all runtime-configurable keys."""
    return list(RUNTIME_CONFIG_SCHEMA.keys())