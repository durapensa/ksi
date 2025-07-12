#!/usr/bin/env python3
"""
Simple Health Check Module - Event-Based Version

Provides basic health check functionality for the KSI daemon.
Migrated to pure event system.
"""

import time
from typing import Dict, Any, TypedDict

from ksi_daemon.event_system import event_handler
from ksi_common.logging import get_bound_logger

# Logger
logger = get_bound_logger("health", version="1.0.0")

# Module info
MODULE_INFO = {
    "name": "health",
    "version": "1.0.0",
    "description": "Health check provider"
}

# Track startup time
startup_time = None


# TypedDict definitions for event handlers

class SystemStartupData(TypedDict):
    """System startup configuration."""
    # No specific fields required for health module
    pass


class SystemShutdownData(TypedDict):
    """System shutdown notification."""
    # No specific fields for shutdown
    pass


@event_handler("system:startup")
async def handle_startup(config: SystemStartupData) -> Dict[str, Any]:
    """Initialize health check plugin."""
    global startup_time
    startup_time = time.time()
    logger.info("Health module initialized")
    return {"module.health": {"loaded": True}}


# Health handler moved to daemon_core.py to avoid duplicate responses


@event_handler("system:shutdown")
async def handle_shutdown(data: SystemShutdownData) -> None:
    """Clean up on shutdown."""
    logger.info("Health module shutting down")


