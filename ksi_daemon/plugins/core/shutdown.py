#!/usr/bin/env python3
"""
Simple Shutdown Plugin

Handles graceful shutdown of the daemon.
"""

import asyncio
import logging
import pluggy

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

logger = logging.getLogger(__name__)

# Module state
shutdown_event = None


@hookimpl
def ksi_startup(config):
    """Initialize shutdown plugin."""
    global shutdown_event
    shutdown_event = asyncio.Event()
    logger.info("Simple shutdown plugin started")
    return {"plugin.simple_shutdown": {"loaded": True}}


@hookimpl
def ksi_handle_event(event_name, data, context):
    """Handle shutdown events."""
    if event_name == "system:shutdown":
        logger.info("Shutdown requested")
        
        # Signal daemon to shutdown
        if shutdown_event:
            shutdown_event.set()
        
        return {
            "status": "shutdown_initiated",
            "message": "Daemon shutdown requested"
        }
    
    return None


@hookimpl
def ksi_shutdown():
    """Clean up on shutdown."""
    logger.info("Simple shutdown plugin stopped")
    return {"status": "simple_shutdown_stopped"}


# Module-level marker for plugin discovery
ksi_plugin = True