#!/usr/bin/env python3
"""
Runtime Configuration Event Handlers

Event-based runtime configuration management for KSI daemon.
Provides dynamic config overrides without requiring daemon restarts.
"""

from typing import Dict, Any, TypedDict, Optional
from typing_extensions import NotRequired

from ksi_daemon.event_system import event_handler
from ksi_daemon.config_manager import (
    set_runtime_config, 
    get_runtime_config, 
    query_runtime_config,
    reset_runtime_config,
    get_runtime_config_keys
)
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("runtime_config", version="1.0.0")

# TypedDict definitions for event parameters
class RuntimeConfigSetData(TypedDict):
    """Type-safe data for runtime:config:set."""
    key: str
    value: Any

class RuntimeConfigGetData(TypedDict):
    """Type-safe data for runtime:config:get."""
    key: NotRequired[str]  # Optional - if not provided, returns all

class RuntimeConfigQueryData(TypedDict):
    """Type-safe data for runtime:config:query."""
    key: NotRequired[str]  # Optional - if not provided, returns all available keys

class RuntimeConfigResetData(TypedDict):
    """Type-safe data for runtime:config:reset."""
    key: NotRequired[str]  # Optional - if not provided, resets all


@event_handler("runtime:config:set")
async def handle_runtime_config_set(data: RuntimeConfigSetData) -> Dict[str, Any]:
    """
    Set runtime configuration override.
    
    Args:
        key (str): Configuration key to set (required)
        value (any): Value to set (required)
    
    Returns:
        Status of the configuration change
        
    Example:
        {"key": "error_verbosity", "value": "verbose"}
    """
    key = data.get("key")
    value = data.get("value")
    
    if not key:
        return {"error": "Missing required parameter: key"}
    
    if value is None:
        return {"error": "Missing required parameter: value"}
    
    success = set_runtime_config(key, value)
    
    if success:
        return {
            "status": "updated",
            "key": key,
            "value": value
        }
    else:
        return {"error": f"Failed to set runtime config: {key}={value}"}


@event_handler("runtime:config:get")
async def handle_runtime_config_get(data: RuntimeConfigGetData) -> Dict[str, Any]:
    """
    Get runtime configuration value(s).
    
    Args:
        key (str): Configuration key to get (optional - if not provided, returns all)
    
    Returns:
        Current configuration value(s) with metadata
        
    Examples:
        {"key": "error_verbosity"}  # Get specific key
        {}                          # Get all runtime config
    """
    key = data.get("key")
    
    if key:
        # Get specific key
        value = get_runtime_config(key)
        if value is None and key not in get_runtime_config_keys():
            return {"error": f"Unknown config key: {key}"}
        
        # Check if it's a runtime override or default
        from ksi_daemon.config_manager import _runtime_overrides
        source = "runtime" if key in _runtime_overrides else "default"
        
        return {
            "key": key,
            "value": value,
            "source": source
        }
    else:
        # Get all runtime-configurable settings
        all_keys = get_runtime_config_keys()
        from ksi_daemon.config_manager import _runtime_overrides
        
        result = {}
        for config_key in all_keys:
            value = get_runtime_config(config_key)
            source = "runtime" if config_key in _runtime_overrides else "default"
            result[config_key] = {
                "value": value,
                "source": source
            }
        
        return {"runtime_config": result}


@event_handler("runtime:config:query")
async def handle_runtime_config_query(data: RuntimeConfigQueryData) -> Dict[str, Any]:
    """
    Query available runtime configuration options.
    
    Args:
        key (str): Configuration key to query (optional - if not provided, returns all available)
    
    Returns:
        Configuration schema and current values
        
    Examples:
        {"key": "error_verbosity"}  # Query specific key schema
        {}                          # Query all available keys
    """
    key = data.get("key")
    
    return query_runtime_config(key)


@event_handler("runtime:config:reset")
async def handle_runtime_config_reset(data: RuntimeConfigResetData) -> Dict[str, Any]:
    """
    Reset runtime configuration to defaults.
    
    Args:
        key (str): Configuration key to reset (optional - if not provided, resets all)
    
    Returns:
        Status of the reset operation
        
    Examples:
        {"key": "error_verbosity"}  # Reset specific key
        {}                          # Reset all runtime config
    """
    key = data.get("key")
    
    success = reset_runtime_config(key)
    
    if success:
        if key:
            return {
                "status": "reset",
                "key": key,
                "message": f"Runtime config '{key}' reset to default"
            }
        else:
            return {
                "status": "reset",
                "message": "All runtime config reset to defaults"
            }
    else:
        if key:
            return {"error": f"Failed to reset runtime config: {key}"}
        else:
            return {"error": "Failed to reset runtime config"}