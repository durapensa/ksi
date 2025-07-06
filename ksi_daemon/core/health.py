#!/usr/bin/env python3
"""
Simple Health Check Module - Event-Based Version

Provides basic health check functionality for the KSI daemon.
Migrated to pure event system.
"""

import time
from typing import Dict, Any

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


@event_handler("system:startup")
async def handle_startup(config: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize health check plugin."""
    global startup_time
    startup_time = time.time()
    logger.info("Health module initialized")
    return {"module.health": {"loaded": True}}


# Health handler moved to daemon_core.py to avoid duplicate responses


@event_handler("system:shutdown")
async def handle_shutdown(data: Dict[str, Any]) -> None:
    """Clean up on shutdown."""
    logger.info("Health module shutting down")


