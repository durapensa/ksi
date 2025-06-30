#!/usr/bin/env python3
"""
Simplified plugin utilities for KSI plugins.

Provides helper functions and decorators without complex inheritance.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, Callable, List
import functools

# Import structured logging from ksi_common
from ksi_common import get_logger as get_structured_logger

# Simple plugin registry for metadata
plugin_registry: Dict[str, Dict[str, Any]] = {}


def plugin_metadata(name: str, version: str = "1.0.0", 
                   description: str = "", **kwargs):
    """
    Decorator to register plugin metadata.
    
    Usage:
        @plugin_metadata("my_plugin", version="1.0.0", description="Does things")
        def my_plugin_module():
            pass
    """
    def decorator(func_or_module):
        plugin_registry[name] = {
            "name": name,
            "version": version,
            "description": description,
            **kwargs
        }
        return func_or_module
    return decorator


def get_logger(plugin_name: str) -> 'structlog.stdlib.BoundLogger':
    """
    DEPRECATED: Import get_logger directly from ksi_common.logging instead.
    This wrapper will be removed soon.
    
    Get a structured logger for the plugin.
    """
    full_name = f"ksi.plugin.{plugin_name}"
    # Debug: print when plugin loggers are created
    print(f"[plugin_utils] Creating logger for plugin: {full_name}")
    return get_structured_logger(full_name)


def event_handler(*event_patterns: str):
    """
    Decorator to mark a function as handling specific events.
    
    Usage:
        @event_handler("completion:*", "system:health")
        async def handle_my_events(event_name, data, context):
            if event_name == "system:health":
                return {"status": "healthy"}
    """
    def decorator(func):
        func._event_patterns = event_patterns
        return func
    return decorator


def service_provider(service_name: str):
    """
    Decorator to mark a function as providing a service.
    
    Usage:
        @service_provider("completion")
        async def provide_completion_service():
            return CompletionService()
    """
    def decorator(func):
        func._provides_service = service_name
        return func
    return decorator


def matches_pattern(event_name: str, pattern: str) -> bool:
    """Check if an event name matches a pattern."""
    if "*" not in pattern:
        return event_name == pattern
    
    # Simple wildcard matching
    import fnmatch
    return fnmatch.fnmatch(event_name, pattern)


def extract_namespace(event_name: str) -> Optional[str]:
    """Extract namespace from event name."""
    if ":" in event_name:
        return event_name.split(":", 1)[0]
    return None


class SimpleEventEmitter:
    """Simple event emitter for plugins that need to emit events."""
    
    def __init__(self, emit_func: Callable):
        self.emit_func = emit_func
    
    async def emit(self, event_name: str, data: Dict[str, Any], 
                   correlation_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Emit an event."""
        return await self.emit_func(event_name, data, correlation_id)


# Helper functions for common plugin patterns

async def with_timeout(coro, timeout: float, error_msg: str = "Operation timed out"):
    """Run a coroutine with timeout."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        raise TimeoutError(error_msg)


def validate_data(data: Dict[str, Any], required_fields: List[str]) -> bool:
    """Validate that required fields are present in data."""
    return all(field in data for field in required_fields)


def safe_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely get a value from a dict with a default."""
    return data.get(key, default)


# Context helpers for plugins

class PluginContext:
    """Simple context object passed to plugins."""
    
    def __init__(self, config: Dict[str, Any], emit_func: Optional[Callable] = None):
        self.config = config
        self.emitter = SimpleEventEmitter(emit_func) if emit_func else None
    
    async def emit(self, event_name: str, data: Dict[str, Any], 
                   correlation_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Emit an event if emitter is available."""
        if self.emitter:
            return await self.emitter.emit(event_name, data, correlation_id)
        return None