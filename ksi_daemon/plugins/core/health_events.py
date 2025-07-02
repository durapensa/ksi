#!/usr/bin/env python3
"""
Simple Health Check Plugin - Event-Based Version

Provides basic health check functionality for the KSI daemon.
Migrated to pure event system.
"""

import time
from typing import Dict, Any

from ksi_daemon.event_system import event_handler
from ksi_common.logging import get_bound_logger

# Logger
logger = get_bound_logger("health", version="1.0.0")

# Plugin info
PLUGIN_INFO = {
    "name": "health",
    "version": "1.0.0",
    "description": "Health check provider"
}

# Track startup time
startup_time = None


@event_handler("system:startup")
async def handle_startup(config: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize health check plugin."""
    global startup_time
    startup_time = time.time()
    logger.info("Health plugin initialized")
    return {"plugin.health": {"loaded": True}}


@event_handler("system:health")
async def handle_system_health(data: Dict[str, Any]) -> Dict[str, Any]:
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


@event_handler("system:shutdown")
async def handle_shutdown(data: Dict[str, Any]) -> None:
    """Clean up on shutdown."""
    logger.info("Health plugin shutting down")


# Module-level marker for plugin discovery
ksi_plugin = True