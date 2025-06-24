#!/usr/bin/env python3
"""
KSI Client Library - Clean client interface for KSI daemon

This package provides a clean, standalone client library for interacting
with the KSI multi-socket daemon architecture.

Usage:
    # Simple chat interface
    from ksi_client import SimpleChatClient
    
    async def main():
        async with SimpleChatClient() as client:
            response, session_id = await client.send_prompt("What is 2+2?")
            print(response)
    
    # Full-featured async client  
    from ksi_client import AsyncClient
    
    async def main():
        client = AsyncClient(client_id="my-app")
        await client.initialize()
        
        # Health check
        health = await client.health_check()
        
        # Create completion
        response = await client.create_completion("Explain quantum computing")
        
        await client.close()

    # Command building utilities
    from ksi_client import CommandBuilder, ResponseHandler
"""

# Import and re-export main client classes
from .async_client import (
    MultiSocketAsyncClient as AsyncClient,  # Renamed for clarity
    SimpleChatClient,
    SocketConnection,
    PendingCompletion
)

# Import and re-export utilities
from .utils import (
    CommandBuilder,
    ConnectionManager, 
    ResponseHandler
)

# Version info
__version__ = "1.0.0"
__all__ = [
    # Main client classes
    "AsyncClient",           # Primary full-featured client
    "SimpleChatClient",      # Simplified chat interface
    "SocketConnection",      # Connection management
    "PendingCompletion",     # Completion tracking
    
    # Utilities
    "CommandBuilder",        # JSON command construction
    "ConnectionManager",     # Low-level connection handling
    "ResponseHandler",       # Response parsing
]