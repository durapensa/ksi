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
    # Module-level functions
    parse_response,
    check_success,
    get_error_message,
    get_result_data,
    send_command_once,
    # Event builder class (keeping as class for now)
    EventBuilder,
    # Convenience functions
    create_event,
    create_health_event,
    create_completion_event,
    create_agent_event,
    create_state_event,
    send_daemon_event,
    # Deprecated classes
    ConnectionManager, 
    ResponseHandler,
)

# Version info
__version__ = "1.0.0"
__all__ = [
    # Event-based clients - Primary interface
    "EventBasedClient",      # Event-driven client
    "EventChatClient",       # Simplified event chat client
    "MultiAgentClient",      # Multi-agent coordination client
    
    # Utilities (module-level functions)
    "parse_response",        # Parse JSON response
    "check_success",         # Check if response is success
    "get_error_message",     # Extract error message
    "get_result_data",       # Extract result data
    "send_command_once",     # Send single command
    
    # Event builder
    "EventBuilder",          # Event construction
    
    # Deprecated classes
    "ConnectionManager",     # DEPRECATED: Use module functions
    "ResponseHandler",       # DEPRECATED: Use module functions
    
    # Event convenience functions
    "create_event",
    "create_health_event",
    "create_completion_event",
    "create_agent_event",
    "create_state_event",
    "send_daemon_event",
]