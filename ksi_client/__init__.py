#!/usr/bin/env python3
"""
KSI Client Library - Event-driven client interface for KSI daemon

This package provides a clean, event-driven client library for interacting
with the KSI plugin-based daemon architecture.

Usage:
    # Simple chat interface (event-based)
    from ksi_client import EventChatClient
    
    async def main():
        async with EventChatClient() as client:
            response, session_id = await client.send_prompt("What is 2+2?")
            print(response)
    
    # Full-featured event client  
    from ksi_client import EventBasedClient
    
    async def main():
        client = EventBasedClient(client_id="my-app")
        await client.connect()
        
        # Health check via event
        health = await client.emit_event("system:health")
        
        # Create completion via event (sync interface)
        response = await client.create_completion_sync("Explain quantum computing")
        
        await client.disconnect()
"""

# Import event-based clients as primary interface
from .event_client import (
    EventBasedClient,
    EventChatClient,
    MultiAgentClient
)

# Import and re-export utilities
from .utils import (
    ConnectionManager, 
    ResponseHandler,
    EventBuilder,
    create_event,
    create_health_event,
    create_completion_event,
    create_agent_event,
    create_state_event,
    send_daemon_event
)

# Version info
__version__ = "1.0.0"
__all__ = [
    # Event-based clients - Primary interface
    "EventBasedClient",      # Event-driven client
    "EventChatClient",       # Simplified event chat client
    "MultiAgentClient",      # Multi-agent coordination client
    
    # Utilities
    "EventBuilder",          # Event construction
    "ConnectionManager",     # Low-level connection handling
    "ResponseHandler",       # Response parsing
    
    # Event convenience functions
    "create_event",
    "create_health_event",
    "create_completion_event",
    "create_agent_event",
    "create_state_event",
    "send_daemon_event",
]