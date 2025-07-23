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
from ksi_common.validation_utils import Validator

logger = get_bound_logger("runtime_config", version="1.0.0")

# TypedDict definitions for event parameters
class RuntimeConfigSetData(TypedDict):
    """Type-safe data for runtime:config:set."""
    key: str
    value: Any
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata

class RuntimeConfigGetData(TypedDict):
    """Type-safe data for runtime:config:get."""
    key: NotRequired[str]  # Optional - if not provided, returns all
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata

class RuntimeConfigQueryData(TypedDict):
    """Type-safe data for runtime:config:query."""
    key: NotRequired[str]  # Optional - if not provided, returns all available keys
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata

class RuntimeConfigResetData(TypedDict):
    """Type-safe data for runtime:config:reset."""
    key: NotRequired[str]  # Optional - if not provided, resets all
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("runtime:config:set")
async def handle_runtime_config_set(data: RuntimeConfigSetData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Set runtime configuration override.
    """
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    key = data.get("key")
    value = data.get("value")
    
    success = set_runtime_config(key, value)
    
    if success:
        return event_response_builder(
            {
                "status": "updated",
                "key": key,
                "value": value
            },
            context=context
        )
    else:
        return error_response(
            f"Failed to set runtime config: {key}={value}",
            context=context
        )


@event_handler("runtime:config:get")
async def handle_runtime_config_get(data: RuntimeConfigGetData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Get runtime configuration value(s).
    """
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    key = data.get("key")
    
    if key:
        # Get specific key
        value = get_runtime_config(key)
        if value is None and key not in get_runtime_config_keys():
            return error_response(
                f"Unknown config key: {key}",
                context=context
            )
        
        # Check if it's a runtime override or default
        from ksi_daemon.config_manager import _runtime_overrides
        source = "runtime" if key in _runtime_overrides else "default"
        
        return event_response_builder(
            {
                "key": key,
                "value": value,
                "source": source
            },
            context=context
        )
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
        
        return event_response_builder(
            {"runtime_config": result},
            context=context
        )


@event_handler("runtime:config:query")
async def handle_runtime_config_query(data: RuntimeConfigQueryData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Query available runtime configuration options.
    """
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder
    key = data.get("key")
    
    result = query_runtime_config(key)
    return event_response_builder(
        result,
        context=context
    )


@event_handler("runtime:config:reset")
async def handle_runtime_config_reset(data: RuntimeConfigResetData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Reset runtime configuration to defaults.
    """
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder, error_response
    key = data.get("key")
    
    success = reset_runtime_config(key)
    
    if success:
        if key:
            return event_response_builder(
                {
                    "status": "reset",
                    "key": key,
                    "message": f"Runtime config '{key}' reset to default"
                },
                context=context
            )
        else:
            return event_response_builder(
                {
                    "status": "reset",
                    "message": "All runtime config reset to defaults"
                },
                context=context
            )
    else:
        if key:
            return error_response(
                f"Failed to reset runtime config: {key}",
                context=context
            )
        else:
            return error_response(
                "Failed to reset runtime config",
                context=context
            )