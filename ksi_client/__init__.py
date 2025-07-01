#!/usr/bin/env python3
"""
KSI Client Library - Adaptive, self-discovering event client

This package provides a minimal, adaptive client for the KSI daemon that:
- Automatically starts the daemon if needed
- Discovers available events and permissions
- Provides type-safe access to all daemon functionality
- Enforces security through permission profiles

Usage:
    from ksi_client import EventClient
    
    async with EventClient() as client:
        # All events are discovered and available
        # Note: Use async_ because async is a Python keyword  
        response = await client.completion.async_(
            prompt="Hello!",
            agent_config={"permission_profile": "restricted"}
        )
        
        # Show available tools for a profile
        tools = client.get_profile_tools("restricted")
        print(f"AI has access to: {tools['allowed']}")
"""

from .client import EventClient
from .exceptions import (
    KSIError,
    KSIConnectionError,
    KSIDaemonError,
    KSITimeoutError,
    KSIDiscoveryError,
    KSIValidationError,
    KSIEventError,
    KSIPermissionError,
)

# Version info
__version__ = "2.0.0"

# Primary export is just EventClient
__all__ = [
    # Main client
    "EventClient",
    
    # Exceptions
    "KSIError",
    "KSIConnectionError",
    "KSIDaemonError", 
    "KSITimeoutError",
    "KSIDiscoveryError",
    "KSIValidationError",
    "KSIEventError",
    "KSIPermissionError",
]