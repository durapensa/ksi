#!/usr/bin/env python3
"""
Daemon Client Package - Safe client-side utilities for JSON Protocol v2.0

This package provides client-safe utilities that can be imported by external clients
without pulling in server-side dependencies. It establishes clear boundaries between
client and server code.

Usage:
    from . import CommandBuilder, SyncClient, AsyncClient
    from .utils import create_spawn_command, send_daemon_command
"""

# Import and re-export client-safe utilities
from .utils import (
    CommandBuilder,
    ResponseHandler, 
    ConnectionManager,
    create_spawn_command,  # Deprecated
    create_completion_command,  # New
    create_publish_command,
    create_subscribe_command,
    create_agent_connection_command,
    send_daemon_command
)

# Import client classes when they exist
try:
    from .async_client import AsyncClient  
except ImportError:
    AsyncClient = None

try:
    from .multi_socket_client import MultiSocketAsyncClient, SimpleChatClient
except ImportError:
    MultiSocketAsyncClient = None
    SimpleChatClient = None

__all__ = [
    # Core utilities
    'CommandBuilder',
    'ResponseHandler',
    'ConnectionManager',
    
    # Convenience functions
    'create_spawn_command',  # Deprecated
    'create_completion_command',  # New
    'create_publish_command', 
    'create_subscribe_command',
    'create_agent_connection_command',
    'send_daemon_command',
    
    # Client classes (if available)
    'AsyncClient',  # Deprecated - single socket only
    'MultiSocketAsyncClient',  # New multi-socket architecture
    'SimpleChatClient'  # Simplified chat interface
]

# Version info
__version__ = "2.0"
__protocol_version__ = "2.0"