#!/usr/bin/env python3
"""
Simple Health Check Plugin

Provides basic health check functionality for the KSI daemon.
"""

import time
import pluggy

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Plugin info
PLUGIN_INFO = {
    "name": "simple_health",
    "version": "1.0.0",
    "description": "Simple health check provider"
}

# Track startup time
startup_time = None


@hookimpl
def ksi_startup(config):
    """Initialize health check plugin."""
    global startup_time
    startup_time = time.time()
    return {"plugin.simple_health": {"loaded": True}}


@hookimpl
def ksi_handle_event(event_name, data, context):
    """Handle health check events."""
    if event_name == "system:health":
        uptime = time.time() - startup_time if startup_time else 0
        
        return {
            "status": "healthy",
            "uptime": uptime,
            "version": "2.0.0",
            "plugin": "simple_health"
        }
    
    return None


@hookimpl
def ksi_shutdown():
    """Clean up on shutdown."""
    pass


# Module-level marker for plugin discovery
ksi_plugin = True