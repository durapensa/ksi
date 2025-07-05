#!/usr/bin/env python3
"""
Example of capability-decorated event handlers.

This shows how we could make events self-documenting about their
capability requirements and metadata.
"""

from typing import Dict, Any, Optional, List
from functools import wraps

# Enhanced event_handler decorator
def event_handler(
    event_name: str,
    *,
    capability: Optional[str] = None,
    requires_capabilities: Optional[List[str]] = None,
    description: Optional[str] = None,
    requires_auth: bool = True,
    resource_intensive: bool = False,
    mcp_visible: bool = True,
    priority: Optional[str] = None
):
    """
    Enhanced event handler decorator with capability metadata.
    
    Args:
        event_name: The event name (e.g., "agent:spawn")
        capability: Primary capability this event belongs to
        requires_capabilities: Other capabilities that must be enabled
        description: Human-readable description
        requires_auth: Whether authentication is required
        resource_intensive: Whether this uses significant resources
        mcp_visible: Whether to expose via MCP
        priority: Handler priority if multiple handlers exist
    """
    def decorator(func):
        # Store metadata on the function
        func._event_metadata = {
            "event": event_name,
            "capability": capability,
            "requires_capabilities": requires_capabilities or [],
            "description": description or func.__doc__,
            "requires_auth": requires_auth,
            "resource_intensive": resource_intensive,
            "mcp_visible": mcp_visible,
            "priority": priority
        }
        
        @wraps(func)
        async def wrapper(data: Dict[str, Any]) -> Any:
            # Could add capability checks here
            return await func(data)
            
        return wrapper
    return decorator


# Example: Message bus events
@event_handler("message:subscribe",
    capability="agent_messaging",
    description="Subscribe to a message channel",
    mcp_visible=True
)
async def handle_subscribe(data: Dict[str, Any]) -> Dict[str, Any]:
    """Subscribe agent to message channel for pub/sub communication."""
    channel = data.get("channel")
    # ... implementation
    return {"status": "subscribed", "channel": channel}


@event_handler("message:publish",
    capability="agent_messaging",
    description="Publish message to channel",
    requires_auth=True,
    mcp_visible=True
)
async def handle_publish(data: Dict[str, Any]) -> Dict[str, Any]:
    """Broadcast message to all subscribers of a channel."""
    # ... implementation
    pass


# Example: Agent lifecycle events
@event_handler("agent:spawn",
    capability="spawn_agents",
    requires_capabilities=["agent_messaging"],  # Need messaging for coordination
    description="Create a new child agent",
    resource_intensive=True,
    mcp_visible=True
)
async def handle_spawn_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """Spawn a new agent with specified profile and permissions."""
    # ... implementation
    pass


@event_handler("agent:terminate",
    capability="spawn_agents",
    description="Terminate an agent",
    requires_auth=True,
    mcp_visible=True
)
async def handle_terminate_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """Terminate agent and clean up resources."""
    # ... implementation
    pass


# Example: State management with read/write separation
@event_handler("state:get",
    capability="state_read",
    description="Read value from shared state",
    requires_auth=False,  # Read is less sensitive
    mcp_visible=True
)
async def handle_state_get(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get value from shared state store."""
    # ... implementation
    pass


@event_handler("state:set",
    capability="state_write",
    requires_capabilities=["state_read"],  # Write implies read
    description="Write value to shared state",
    requires_auth=True,
    mcp_visible=True
)
async def handle_state_set(data: Dict[str, Any]) -> Dict[str, Any]:
    """Set value in shared state store."""
    # ... implementation
    pass


# Example: System events that all agents need
@event_handler("system:health",
    capability="base",  # Part of base capability
    description="Check system health",
    requires_auth=False,
    mcp_visible=True
)
async def handle_health(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return system health status."""
    # ... implementation
    pass


# Discovery function to extract capability mappings
def discover_capability_mappings():
    """
    Scan all registered event handlers and build capability mapping.
    
    This would be called at daemon startup to build the registry.
    """
    capability_map = {}
    
    # In real implementation, would scan all loaded modules
    for handler in [handle_subscribe, handle_publish, handle_spawn_agent, 
                   handle_terminate_agent, handle_state_get, handle_state_set,
                   handle_health]:
        
        metadata = getattr(handler, '_event_metadata', {})
        if not metadata:
            continue
            
        capability = metadata.get('capability')
        if capability:
            if capability not in capability_map:
                capability_map[capability] = {
                    'events': [],
                    'description': f'Capability for {capability}',
                    'requires': set(),
                    'resource_intensive': False
                }
            
            # Add this event
            capability_map[capability]['events'].append({
                'name': metadata['event'],
                'description': metadata['description'],
                'mcp_visible': metadata.get('mcp_visible', True)
            })
            
            # Track dependencies
            for req in metadata.get('requires_capabilities', []):
                capability_map[capability]['requires'].add(req)
                
            # Track if any event is resource intensive
            if metadata.get('resource_intensive'):
                capability_map[capability]['resource_intensive'] = True
                
    return capability_map


# Alternative: Class-based approach for grouping related events
class MessageBusHandlers:
    """Message bus event handlers."""
    
    capability = "agent_messaging"
    description = "Inter-agent pub/sub messaging"
    
    @staticmethod
    @event_handler("message:subscribe")
    async def subscribe(data: Dict[str, Any]) -> Dict[str, Any]:
        """Subscribe to channel."""
        pass
    
    @staticmethod  
    @event_handler("message:publish")
    async def publish(data: Dict[str, Any]) -> Dict[str, Any]:
        """Publish to channel."""
        pass
    
    @staticmethod
    @event_handler("message:unsubscribe")
    async def unsubscribe(data: Dict[str, Any]) -> Dict[str, Any]:
        """Unsubscribe from channel."""
        pass


if __name__ == "__main__":
    # Example: Discover and print capability mappings
    import json
    
    mappings = discover_capability_mappings()
    print("Discovered Capability Mappings:")
    print(json.dumps(mappings, indent=2, default=str))