#!/usr/bin/env python3
"""
Simple Health Check Plugin

Provides basic health check functionality for the KSI daemon.
"""

import time
import pluggy
from ksi_common.logging import get_bound_logger
from ksi_daemon.plugin_utils import event_handler, create_ksi_describe_events_hook

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Logger
logger = get_bound_logger("health", version="1.0.0")

# Plugin info
PLUGIN_INFO = {
    "name": "health",
    "version": "1.0.0",
    "description": "Health check provider"
}

# Reload configuration
_reloadable = True
_reload_strategy = "stateless"

# Track startup time
startup_time = None


@hookimpl
def ksi_startup(config):
    """Initialize health check plugin."""
    global startup_time
    startup_time = time.time()
    return {"plugin.health": {"loaded": True}}


@event_handler("system:health")
def handle_system_health(data):
    """Check daemon health status.
    
    Returns:
        Dictionary with health status, uptime, and version information
    """
    logger.info("Processing health check")
    
    uptime = time.time() - startup_time if startup_time else 0
    
    return {
        "status": "healthy",
        "uptime": uptime,
        "version": "2.0.0",
        "plugin": "health"
    }


@hookimpl
def ksi_handle_event(event_name, data, context):
    """Handle health check events using decorated handlers."""
    import sys
    module = sys.modules[__name__]
    
    # Look for decorated handlers
    import inspect
    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj) and hasattr(obj, '_ksi_event_name'):
            if obj._ksi_event_name == event_name:
                return obj(data)
    
    return None


@hookimpl
def ksi_shutdown():
    """Clean up on shutdown."""
    pass


# Module-level marker for plugin discovery
ksi_plugin = True

# Enable event discovery
ksi_describe_events = create_ksi_describe_events_hook(__name__)