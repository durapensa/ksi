#!/usr/bin/env python3
"""
KSI Plugin System Hook Specifications

Defines all hooks that plugins can implement to extend KSI daemon functionality.
Uses pluggy for plugin management (same system as pytest).

Hook Categories:
1. Lifecycle - Daemon startup/shutdown
2. Event - Event processing pipeline  
3. Transport - Connection and serialization
4. Service - Service registration and discovery
"""

from typing import Dict, Any, Optional, List, TYPE_CHECKING
import pluggy

if TYPE_CHECKING:
    from .plugin_types import EventContext, TransportConnection

# Create hook specification marker
hookspec = pluggy.HookspecMarker("ksi")


# =============================================================================
# Lifecycle Hooks
# =============================================================================

@hookspec
def ksi_startup(config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Called once during daemon startup.
    
    Args:
        config: Daemon configuration dictionary
        
    Returns:
        Optional dict with plugin configuration to merge
    """


@hookspec
def ksi_ready() -> None:
    """
    Called when daemon is fully initialized and ready to accept connections.
    """


@hookspec
def ksi_shutdown() -> None:
    """
    Called during daemon shutdown.
    Plugins should clean up resources here.
    """


@hookspec  
def ksi_plugin_context(context: Dict[str, Any]) -> None:
    """
    Pass runtime context to plugins.
    
    Args:
        context: Dictionary with runtime objects like event_router, emit_event
    """


@hookspec
def ksi_plugin_loaded(plugin_name: str, plugin_instance: Any) -> None:
    """
    Called when a plugin is successfully loaded.
    
    Args:
        plugin_name: Name of the loaded plugin
        plugin_instance: The plugin instance
    """


# =============================================================================
# Event Processing Hooks
# =============================================================================

@hookspec
def ksi_pre_event(event_name: str, data: Dict[str, Any], context: "EventContext") -> Optional[Dict[str, Any]]:
    """
    Pre-process events before main handling.
    Can modify event data or prevent processing by returning None.
    
    Args:
        event_name: Namespaced event name (e.g., "completion:request")
        data: Event data dictionary
        context: Event context with emit(), config, etc.
        
    Returns:
        Modified event data or None to cancel event
    """


@hookspec
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: "EventContext") -> Optional[Dict[str, Any]]:
    """
    Handle an event. First plugin to return non-None wins.
    
    Args:
        event_name: Namespaced event name (e.g., "completion:request")
        data: Event data dictionary
        context: Event context with emit(), subscribe(), etc.
        
    Returns:
        Response data or None if not handled
    """


@hookspec
def ksi_post_event(event_name: str, result: Optional[Dict[str, Any]], context: "EventContext") -> Optional[Dict[str, Any]]:
    """
    Post-process event results.
    Can modify or log results.
    
    Args:
        event_name: Namespaced event name
        result: Result from event handler (may be None)
        context: Event context
        
    Returns:
        Modified result or original if unchanged
    """


@hookspec
def ksi_event_error(event_name: str, error: Exception, context: "EventContext") -> Optional[Dict[str, Any]]:
    """
    Handle errors during event processing.
    
    Args:
        event_name: Event that caused the error
        error: The exception that occurred
        context: Event context
        
    Returns:
        Error response to send or None for default handling
    """


# =============================================================================
# Transport Hooks
# =============================================================================

@hookspec
def ksi_create_transport(transport_type: str, config: Dict[str, Any]) -> Optional["TransportConnection"]:
    """
    Create a transport instance.
    
    Args:
        transport_type: Type of transport (e.g., "unix", "socketio", "http")
        config: Transport-specific configuration
        
    Returns:
        Transport instance or None if not handled
    """


@hookspec
def ksi_handle_connection(transport: "TransportConnection", connection_info: Dict[str, Any]) -> None:
    """
    Handle new connection on a transport.
    
    Args:
        transport: The transport instance
        connection_info: Connection details (address, headers, etc.)
    """


@hookspec
def ksi_serialize_event(event: Dict[str, Any], transport_type: str) -> bytes:
    """
    Serialize event for specific transport.
    
    Args:
        event: Event dictionary to serialize
        transport_type: Target transport type
        
    Returns:
        Serialized event data
    """


@hookspec
def ksi_deserialize_event(data: bytes, transport_type: str) -> Dict[str, Any]:
    """
    Deserialize event from transport format.
    
    Args:
        data: Raw bytes from transport
        transport_type: Source transport type
        
    Returns:
        Event dictionary
    """


# =============================================================================
# Service Hooks
# =============================================================================

@hookspec
def ksi_provide_service(service_name: str) -> Optional[Any]:
    """
    Provide a service implementation.
    
    Args:
        service_name: Name of requested service (e.g., "completion", "state", "agent")
        
    Returns:
        Service instance or None if not provided
    """


@hookspec
def ksi_service_dependencies() -> List[str]:
    """
    Declare service dependencies for this plugin.
    
    Returns:
        List of required service names
    """


@hookspec
def ksi_register_namespace(namespace: str, description: str) -> None:
    """
    Register an event namespace handled by this plugin.
    
    Args:
        namespace: Namespace prefix (e.g., "completion", "agent")
        description: Human-readable description
    """


# =============================================================================
# Message Bus Hooks
# =============================================================================

@hookspec
def ksi_message_published(event_type: str, message: Dict[str, Any], subscribers: List[str]) -> None:
    """
    Called when a message is published to the bus.
    
    Args:
        event_type: Type of event published
        message: The message data
        subscribers: List of subscriber IDs
    """


@hookspec
def ksi_agent_connected(agent_id: str, capabilities: List[str]) -> None:
    """
    Called when an agent connects to the system.
    
    Args:
        agent_id: Unique agent identifier
        capabilities: List of agent capabilities
    """


@hookspec
def ksi_agent_disconnected(agent_id: str, reason: Optional[str]) -> None:
    """
    Called when an agent disconnects.
    
    Args:
        agent_id: Unique agent identifier
        reason: Disconnect reason if known
    """


# =============================================================================
# Extension Hooks
# =============================================================================

@hookspec
def ksi_register_commands() -> Dict[str, str]:
    """
    Register custom commands (for compatibility layer).
    
    Returns:
        Dict mapping command names to event names
        Example: {"MY_COMMAND": "myplugin:command"}
    """


@hookspec
def ksi_register_validators() -> Dict[str, Any]:
    """
    Register event validators (Pydantic models).
    
    Returns:
        Dict mapping event names to validator classes
    """


@hookspec
def ksi_metrics_collected(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Called when system metrics are collected.
    Plugins can add their own metrics.
    
    Args:
        metrics: Current metrics dictionary
        
    Returns:
        Updated metrics dictionary
    """