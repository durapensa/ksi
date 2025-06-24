#!/usr/bin/env python3
"""
Messaging Protocol - Parameters for messaging socket operations

Handles ephemeral real-time communication: agent-to-agent messages,
pub/sub events, and completion result callbacks.
Commands: subscribe, publish, send_message, agent_connection
"""

from typing import Dict, Any, List, Optional, Union, Literal
from pydantic import BaseModel, Field, field_validator
import logging


# ============================================================================
# PUB/SUB OPERATIONS
# ============================================================================

class SubscribeParameters(BaseModel):
    """Parameters for SUBSCRIBE command"""
    agent_id: str = Field(..., description="Agent ID to subscribe")
    event_types: List[str] = Field(..., description="List of event types to subscribe to")
    
    @field_validator('event_types')
    def validate_event_types(cls, v):
        if not v:
            raise ValueError("At least one event type required")
        return v


class PublishParameters(BaseModel):
    """Parameters for PUBLISH command"""
    from_agent: str = Field(..., description="Agent ID publishing the event")
    event_type: str = Field(..., description="Type of event to publish")
    payload: Dict[str, Any] = Field(..., description="Event payload data")
    
    @field_validator('event_type')
    def validate_event_type(cls, v):
        """Validate event type"""
        valid_types = [
            'DIRECT_MESSAGE', 'BROADCAST', 'TASK_ASSIGNMENT', 
            'CONVERSATION_INVITE', 'AGENT_STATUS', 'SYSTEM_EVENT',
            'COMPLETION_RESULT'  # Added for async completions
        ]
        if v not in valid_types:
            # Allow custom event types but log a warning
            logging.getLogger('daemon').warning(f"Non-standard event type: {v}")
        return v


# ============================================================================
# AGENT-TO-AGENT MESSAGING
# ============================================================================

class SendMessageParameters(BaseModel):
    """Parameters for SEND_MESSAGE command"""
    from_agent: str = Field(..., description="ID of the agent sending the message")
    to_agent: Optional[str] = Field(None, description="ID of specific target agent (None for broadcast)")
    message_type: str = Field("MESSAGE", description="Type of message (MESSAGE, TASK_ASSIGNMENT, etc.)")
    content: str = Field(..., description="Message content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata for the message")
    event_types: Optional[List[str]] = Field(None, description="Event types for pub/sub routing (alternative to to_agent)")


class AgentConnectionParameters(BaseModel):
    """Parameters for AGENT_CONNECTION command"""
    action: Literal["connect", "disconnect"] = Field(..., description="Action to perform: connect or disconnect")
    agent_id: str = Field(..., description="ID of agent to connect/disconnect")


# ============================================================================
# COMPLETION RESULT EVENTS (Async callbacks from completion.sock)
# ============================================================================

class CompletionResultEvent(BaseModel):
    """Event published when a completion request finishes"""
    type: Literal["COMPLETION_RESULT"] = "COMPLETION_RESULT"
    request_id: str
    client_id: str  # The client that requested the completion
    timestamp: str
    result: Union['CompletionSuccessData', 'CompletionErrorData']


class CompletionSuccessData(BaseModel):
    """Success data for completion result"""
    response: str
    session_id: str
    model: str
    usage: Optional[Dict[str, int]] = None
    duration_ms: int
    metadata: Optional[Dict[str, Any]] = None


class CompletionErrorData(BaseModel):
    """Error data for completion result"""
    error: str
    code: str
    details: Optional[str] = None


# ============================================================================
# EVENT TYPES AND MESSAGE FORMATS
# ============================================================================

class BaseEvent(BaseModel):
    """Base model for all events published to messaging socket"""
    type: str  # Event type
    from_agent: Optional[str] = None
    timestamp: str
    payload: Dict[str, Any]


class DirectMessage(BaseEvent):
    """Direct message between agents"""
    type: Literal["DIRECT_MESSAGE"] = "DIRECT_MESSAGE"
    to_agent: str
    content: str
    message_id: Optional[str] = None


class BroadcastMessage(BaseEvent):
    """Broadcast message to all subscribed agents"""
    type: Literal["BROADCAST"] = "BROADCAST"
    content: str
    topic: Optional[str] = None


class TaskAssignment(BaseEvent):
    """Task assignment event"""
    type: Literal["TASK_ASSIGNMENT"] = "TASK_ASSIGNMENT"
    to_agent: str
    task_id: str
    task_description: str
    priority: Optional[str] = "normal"
    deadline: Optional[str] = None


class AgentStatusUpdate(BaseEvent):
    """Agent status change notification"""
    type: Literal["AGENT_STATUS"] = "AGENT_STATUS"
    agent_id: str
    status: Literal["active", "busy", "inactive", "offline"]
    details: Optional[str] = None


class SystemEvent(BaseEvent):
    """System-wide event notification"""
    type: Literal["SYSTEM_EVENT"] = "SYSTEM_EVENT"
    event_name: str
    severity: Literal["info", "warning", "error", "critical"] = "info"
    details: Dict[str, Any]


# Forward reference resolution
CompletionResultEvent.model_rebuild()