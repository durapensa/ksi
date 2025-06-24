#!/usr/bin/env python3
"""
Event Schemas for KSI Plugin System

Pydantic models for event validation. Events are validated before routing
to ensure data consistency across plugins.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


# =============================================================================
# Base Event Models
# =============================================================================

class BaseEventData(BaseModel):
    """Base model for all event data."""
    
    class Config:
        extra = "allow"  # Allow additional fields


class RequestEvent(BaseEventData):
    """Base model for request events."""
    request_id: Optional[str] = Field(None, description="Unique request identifier")
    timeout: Optional[float] = Field(30.0, description="Request timeout in seconds")


class ResponseEvent(BaseEventData):
    """Base model for response events."""
    request_id: Optional[str] = Field(None, description="Original request identifier")
    success: bool = Field(True, description="Whether the operation succeeded")
    error: Optional[str] = Field(None, description="Error message if failed")


# =============================================================================
# Completion Events
# =============================================================================

class CompletionRequest(RequestEvent):
    """completion:request event data."""
    prompt: str = Field(..., description="The prompt to complete")
    model: str = Field("sonnet", description="Model to use")
    temperature: float = Field(0.7, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens to generate")
    session_id: Optional[str] = Field(None, description="Session ID for context")
    agent_id: Optional[str] = Field(None, description="Agent making the request")
    client_id: Optional[str] = Field(None, description="Client ID for response routing")
    stream: bool = Field(False, description="Whether to stream the response")


class CompletionResponse(ResponseEvent):
    """completion:response event data."""
    result: str = Field(..., description="The completion result")
    model: str = Field(..., description="Model used")
    usage: Optional[Dict[str, int]] = Field(None, description="Token usage statistics")
    session_id: Optional[str] = Field(None, description="Session ID")
    duration_ms: Optional[int] = Field(None, description="Processing duration")


class CompletionProgress(BaseEventData):
    """completion:progress event data."""
    request_id: str = Field(..., description="Request being processed")
    status: str = Field(..., description="Current status")
    progress: Optional[float] = Field(None, description="Progress percentage (0-100)")
    message: Optional[str] = Field(None, description="Status message")


# =============================================================================
# Agent Events
# =============================================================================

class AgentSpawnRequest(RequestEvent):
    """agent:spawn event data."""
    agent_type: str = Field(..., description="Type of agent to spawn")
    agent_id: Optional[str] = Field(None, description="Specific agent ID")
    config: Dict[str, Any] = Field(default_factory=dict, description="Agent configuration")
    capabilities: List[str] = Field(default_factory=list, description="Agent capabilities")


class AgentSpawnResponse(ResponseEvent):
    """agent:spawn_complete event data."""
    agent_id: str = Field(..., description="Spawned agent ID")
    process_id: Optional[str] = Field(None, description="System process ID")
    capabilities: List[str] = Field(default_factory=list, description="Agent capabilities")


class AgentStatusEvent(BaseEventData):
    """agent:status event data."""
    agent_id: str = Field(..., description="Agent ID")
    status: str = Field(..., description="Current status (ready, busy, error)")
    info: Dict[str, Any] = Field(default_factory=dict, description="Additional status info")


class AgentTerminateRequest(RequestEvent):
    """agent:terminate event data."""
    agent_id: str = Field(..., description="Agent to terminate")
    reason: Optional[str] = Field(None, description="Termination reason")
    force: bool = Field(False, description="Force immediate termination")


# =============================================================================
# Message/Communication Events
# =============================================================================

class MessageEvent(BaseEventData):
    """message:send event data."""
    from_agent: str = Field(..., description="Sender agent ID")
    to_agent: Optional[str] = Field(None, description="Target agent ID (None for broadcast)")
    message_type: str = Field("text", description="Type of message")
    content: Any = Field(..., description="Message content")
    reply_to: Optional[str] = Field(None, description="Message being replied to")


class SubscribeRequest(RequestEvent):
    """message:subscribe event data."""
    agent_id: str = Field(..., description="Subscribing agent")
    event_types: List[str] = Field(..., description="Event types to subscribe to")
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional filters")


class PublishEvent(BaseEventData):
    """message:publish event data."""
    event_type: str = Field(..., description="Type of event to publish")
    payload: Dict[str, Any] = Field(..., description="Event payload")
    target: Optional[str] = Field(None, description="Specific target (None for broadcast)")


# =============================================================================
# State Management Events
# =============================================================================

class StateSetRequest(RequestEvent):
    """state:set event data."""
    namespace: str = Field(..., description="State namespace")
    key: str = Field(..., description="State key")
    value: Any = Field(..., description="Value to store")
    ttl: Optional[int] = Field(None, description="TTL in seconds")


class StateGetRequest(RequestEvent):
    """state:get event data."""
    namespace: str = Field(..., description="State namespace")
    key: str = Field(..., description="State key")
    default: Any = Field(None, description="Default if not found")


class StateGetResponse(ResponseEvent):
    """state:get_response event data."""
    namespace: str = Field(..., description="State namespace")
    key: str = Field(..., description="State key")
    value: Any = Field(None, description="Retrieved value")
    found: bool = Field(..., description="Whether key was found")


# =============================================================================
# System Events
# =============================================================================

class SystemShutdownEvent(BaseEventData):
    """system:shutdown event data."""
    reason: str = Field("manual", description="Shutdown reason")
    grace_period: float = Field(5.0, description="Grace period in seconds")
    save_state: bool = Field(True, description="Whether to save state")


class SystemHealthRequest(RequestEvent):
    """system:health event data."""
    include_plugins: bool = Field(True, description="Include plugin health")
    include_services: bool = Field(True, description="Include service health")


class SystemHealthResponse(ResponseEvent):
    """system:health_response event data."""
    status: str = Field(..., description="Overall health status")
    uptime: float = Field(..., description="Uptime in seconds")
    plugins: Optional[Dict[str, Any]] = Field(None, description="Plugin health info")
    services: Optional[Dict[str, Any]] = Field(None, description="Service health info")
    stats: Dict[str, Any] = Field(default_factory=dict, description="System statistics")


class SystemReloadRequest(RequestEvent):
    """system:reload event data."""
    plugin_name: Optional[str] = Field(None, description="Specific plugin to reload")
    preserve_state: bool = Field(True, description="Preserve plugin state")


# =============================================================================
# Transport Events
# =============================================================================

class ConnectionEvent(BaseEventData):
    """transport:connection event data."""
    transport_type: str = Field(..., description="Transport type (unix, socketio, etc)")
    connection_id: str = Field(..., description="Unique connection ID")
    action: str = Field(..., description="Action (connect, disconnect)")
    info: Dict[str, Any] = Field(default_factory=dict, description="Connection info")


class TransportErrorEvent(BaseEventData):
    """transport:error event data."""
    transport_type: str = Field(..., description="Transport type")
    error: str = Field(..., description="Error message")
    connection_id: Optional[str] = Field(None, description="Affected connection")
    fatal: bool = Field(False, description="Whether error is fatal")


# =============================================================================
# Event Registry
# =============================================================================

# Map event names to their schemas
EVENT_SCHEMAS = {
    # Completion events
    "completion:request": CompletionRequest,
    "completion:response": CompletionResponse,
    "completion:progress": CompletionProgress,
    
    # Agent events
    "agent:spawn": AgentSpawnRequest,
    "agent:spawn_complete": AgentSpawnResponse,
    "agent:status": AgentStatusEvent,
    "agent:terminate": AgentTerminateRequest,
    
    # Message events
    "message:send": MessageEvent,
    "message:subscribe": SubscribeRequest,
    "message:publish": PublishEvent,
    
    # State events
    "state:set": StateSetRequest,
    "state:get": StateGetRequest,
    "state:get_response": StateGetResponse,
    
    # System events
    "system:shutdown": SystemShutdownEvent,
    "system:health": SystemHealthRequest,
    "system:health_response": SystemHealthResponse,
    "system:reload": SystemReloadRequest,
    
    # Transport events
    "transport:connection": ConnectionEvent,
    "transport:error": TransportErrorEvent
}


def get_schema(event_name: str) -> Optional[type[BaseModel]]:
    """Get schema for an event name."""
    return EVENT_SCHEMAS.get(event_name)


def validate_event(event_name: str, data: Dict[str, Any]) -> BaseModel:
    """
    Validate event data against its schema.
    
    Args:
        event_name: Name of the event
        data: Event data to validate
        
    Returns:
        Validated model instance
        
    Raises:
        ValueError: If no schema found
        ValidationError: If validation fails
    """
    schema = get_schema(event_name)
    if not schema:
        raise ValueError(f"No schema found for event: {event_name}")
    
    return schema(**data)