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
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class SystemShutdownData(TypedDict):
    """System shutdown notification."""
    # No specific fields for shutdown
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("system:startup")
async def handle_startup(data: SystemStartupData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Initialize health check plugin."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder
    
    global startup_time
    startup_time = time.time()
    logger.info("Health module initialized")
    return event_response_builder(
        {"module.health": {"loaded": True}},
        context=context
    )


# Health handler moved to daemon_core.py to avoid duplicate responses


@event_handler("system:shutdown")
async def handle_shutdown(data: SystemShutdownData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Clean up on shutdown."""
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    from ksi_common.event_response_builder import event_response_builder
    
    logger.info("Health module shutting down")
    return event_response_builder(
        {"health_module_shutdown": True},
        context=context
    )


