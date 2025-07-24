#!/usr/bin/env python3
"""
Simple Health Check Module - Event-Based Version

Provides basic health check functionality for the KSI daemon.
Migrated to pure event system.
"""

import time
from typing import Dict, Any, Optional, TypedDict
from typing_extensions import NotRequired

from ksi_daemon.event_system import event_handler
from ksi_common.logging import get_bound_logger
from ksi_common.service_lifecycle import service_startup, service_shutdown

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


@service_startup("health", load_transformers=False)
async def handle_startup(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Initialize health check plugin."""
    global startup_time
    startup_time = time.time()
    return {"loaded": True}


# Health handler moved to daemon_core.py to avoid duplicate responses


@service_shutdown("health")
async def handle_shutdown(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
    """Clean up on shutdown."""
    pass  # Health module has no cleanup needed


