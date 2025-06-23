#!/usr/bin/env python3
"""
Pydantic Models for Daemon Commands and Responses

Provides type-safe, auto-validating models for the JSON protocol v2.0
"""

from typing import Dict, Any, List, Optional, Union, Literal
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
import uuid
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from daemon.timestamp_utils import TimestampManager


class CommandType(str, Enum):
    """Command categories based on functional purpose"""
    PROCESS_CONTROL = "process_control"
    AGENT_MANAGEMENT = "agent_management"
    MESSAGE_BUS = "message_bus"
    STATE_MANAGEMENT = "state_management"
    IDENTITY_MANAGEMENT = "identity_management"
    SYSTEM_STATUS = "system_status"
    SYSTEM_CONTROL = "system_control"


class BaseCommand(BaseModel):
    """Base model for all commands"""
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    
    command: str
    version: Literal["2.0"] = Field(default="2.0")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = None
    
    @field_validator('metadata')
    def validate_metadata(cls, v):
        if v is not None:
            allowed_keys = {'timestamp', 'client_id', 'request_id'}
            extra_keys = set(v.keys()) - allowed_keys
            if extra_keys:
                raise ValueError(f"Unknown metadata keys: {extra_keys}")
        return v


# Process Control Commands

class CompletionParameters(BaseModel):
    """Parameters for COMPLETION command"""
    mode: Literal["sync", "async"]
    type: Literal["claude"] = "claude"
    prompt: str
    session_id: Optional[str] = None
    model: str = "sonnet"
    agent_id: Optional[str] = None
    enable_tools: bool = True


class CleanupParameters(BaseModel):
    """Parameters for CLEANUP command"""
    cleanup_type: Literal["logs", "sessions", "sockets", "all"]


class ReloadModuleParameters(BaseModel):
    """Parameters for RELOAD_MODULE command"""
    module_name: str = "handler"


# Agent Management Commands

class RegisterAgentParameters(BaseModel):
    """Parameters for REGISTER_AGENT command"""
    agent_id: str = Field(..., description="Unique identifier for the agent")
    role: str = Field(..., description="Agent's primary role (e.g., assistant, researcher, analyst)")
    capabilities: Union[List[str], str] = Field(default_factory=list, description="List of agent capabilities")
    
    @field_validator('capabilities')
    def normalize_capabilities(cls, v):
        if isinstance(v, str):
            return v.split(',') if v else []
        return v


class SpawnAgentParameters(BaseModel):
    """Parameters for SPAWN_AGENT command"""
    task: str  # Required - the initial task for the agent
    profile_name: Optional[str] = None  # Optional - fallback if composition selection fails
    agent_id: Optional[str] = None  # Optional - auto-generated if not provided
    context: str = ""  # Optional - additional context
    role: Optional[str] = None  # Optional - role hint for composition selection
    capabilities: List[str] = Field(default_factory=list)  # Optional - capabilities for composition selection
    model: str = "sonnet"  # Optional - Claude model to use


class RouteTaskParameters(BaseModel):
    """Parameters for ROUTE_TASK command"""
    task: str = Field(..., description="Task description to route")
    required_capabilities: List[str] = Field(default_factory=list, description="Required capabilities for the task")
    context: str = Field(default="", description="Additional context for the task")
    prefer_agent_id: Optional[str] = Field(None, description="Preferred agent ID if available")


# Message Bus Commands

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
            'CONVERSATION_INVITE', 'AGENT_STATUS', 'SYSTEM_EVENT'
        ]
        if v not in valid_types:
            # Allow custom event types but log a warning
            import logging
            logging.getLogger('daemon').warning(f"Non-standard event type: {v}")
        return v


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


# State Management Commands

class SetAgentKVParameters(BaseModel):
    """Parameters for SET_AGENT_KV command"""
    key: str = Field(..., description="State key to set (suggest agent_id.purpose.detail format)")
    value: Any = Field(..., description="State value to store (any JSON-serializable value)")
    owner_agent_id: str = Field(default="system", description="Agent ID that owns this data")
    scope: str = Field(default="shared", description="Data scope: private, shared, or coordination")
    expires_at: Optional[str] = Field(default=None, description="ISO timestamp when this expires (optional)")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata (optional)")


class GetAgentKVParameters(BaseModel):
    """Parameters for GET_AGENT_KV command"""
    key: str = Field(..., description="State key to retrieve")


class LoadStateParameters(BaseModel):
    """Parameters for LOAD_STATE command"""
    state_data: Dict[str, Any]


# Identity Management Commands

class CreateIdentityParameters(BaseModel):
    """Parameters for CREATE_IDENTITY command"""
    agent_id: str
    display_name: Optional[str] = None
    role: Optional[str] = None
    personality_traits: Optional[List[str]] = None
    appearance: Optional[Dict[str, Any]] = None


class UpdateIdentityParameters(BaseModel):
    """Parameters for UPDATE_IDENTITY command"""
    agent_id: str
    updates: Dict[str, Any]
    
    @model_validator(mode='after')
    def validate_updates(self):
        protected_fields = {'identity_uuid', 'agent_id', 'created_at'}
        if any(field in self.updates for field in protected_fields):
            raise ValueError(f"Cannot update protected fields: {protected_fields}")
        return self


class GetIdentityParameters(BaseModel):
    """Parameters for GET_IDENTITY command"""
    agent_id: str


class RemoveIdentityParameters(BaseModel):
    """Parameters for REMOVE_IDENTITY command"""
    agent_id: str


class ListIdentitiesParameters(BaseModel):
    """Parameters for LIST_IDENTITIES command"""
    sort_by: Optional[str] = Field(default="created_at", description="Field to sort by")
    order: Optional[str] = Field(default="desc", description="Sort order: asc or desc")
    filter_role: Optional[str] = Field(default=None, description="Filter by role")
    filter_active: Optional[bool] = Field(default=None, description="Filter by active status")


# Composition Commands

class GetCompositionsParameters(BaseModel):
    """Parameters for GET_COMPOSITIONS command"""
    include_metadata: bool = True
    category: Optional[str] = None


class GetCompositionParameters(BaseModel):
    """Parameters for GET_COMPOSITION command"""
    name: str


class ValidateCompositionParameters(BaseModel):
    """Parameters for VALIDATE_COMPOSITION command"""
    name: str
    context: Dict[str, Any]


class ListComponentsParameters(BaseModel):
    """Parameters for LIST_COMPONENTS command"""
    directory: Optional[str] = None


class ComposePromptParameters(BaseModel):
    """Parameters for COMPOSE_PROMPT command"""
    composition: str
    context: Dict[str, Any]


# Commands with no parameters don't need parameter classes


# Command Models with specific parameters

class CleanupCommand(BaseCommand):
    command: Literal["CLEANUP"] = "CLEANUP"
    parameters: CleanupParameters


class ReloadModuleCommand(BaseCommand):
    command: Literal["RELOAD_MODULE"] = "RELOAD_MODULE"
    parameters: ReloadModuleParameters


# Response Models

class BaseResponse(BaseModel):
    """Base model for all responses"""
    model_config = ConfigDict(extra='forbid')
    
    status: Literal["success", "error"]
    command: str
    metadata: Optional[Dict[str, Any]] = None
    
    @field_validator('metadata')
    def add_timestamp(cls, v):
        if v is None:
            v = {}
        if 'timestamp' not in v:
            v['timestamp'] = TimestampManager.timestamp_utc()
        return v


class SuccessResponse(BaseResponse):
    """Success response model"""
    status: Literal["success"] = "success"
    result: Any


class ErrorInfo(BaseModel):
    """Error information model"""
    code: str
    message: str
    timestamp: Optional[str] = None
    
    @field_validator('timestamp', mode='before')
    def set_timestamp(cls, v):
        if v is None:
            return TimestampManager.timestamp_utc()
        return v


class ErrorResponse(BaseResponse):
    """Error response model"""
    status: Literal["error"] = "error"
    error: ErrorInfo


# Command Factory

COMMAND_PARAMETER_MAP = {
    "COMPLETION": CompletionParameters,
    "CLEANUP": CleanupParameters,
    "RELOAD_MODULE": ReloadModuleParameters,
    "REGISTER_AGENT": RegisterAgentParameters,
    "SPAWN_AGENT": SpawnAgentParameters,
    "ROUTE_TASK": RouteTaskParameters,
    "SUBSCRIBE": SubscribeParameters,
    "PUBLISH": PublishParameters,
    "SEND_MESSAGE": SendMessageParameters,
    "AGENT_CONNECTION": AgentConnectionParameters,
    "SET_AGENT_KV": SetAgentKVParameters,
    "GET_AGENT_KV": GetAgentKVParameters,
    "LOAD_STATE": LoadStateParameters,
    "CREATE_IDENTITY": CreateIdentityParameters,
    "UPDATE_IDENTITY": UpdateIdentityParameters,
    "GET_IDENTITY": GetIdentityParameters,
    "LIST_IDENTITIES": ListIdentitiesParameters,
    "REMOVE_IDENTITY": RemoveIdentityParameters,
    "GET_COMPOSITIONS": GetCompositionsParameters,
    "GET_COMPOSITION": GetCompositionParameters,
    "VALIDATE_COMPOSITION": ValidateCompositionParameters,
    "LIST_COMPONENTS": ListComponentsParameters,
    "COMPOSE_PROMPT": ComposePromptParameters,
    # Commands without parameters don't need parameter classes
}


class CommandFactory:
    """Factory for creating and validating commands"""
    
    @staticmethod
    def create_command(command_name: str, parameters: Dict[str, Any], 
                      metadata: Optional[Dict[str, Any]] = None) -> BaseCommand:
        """Create a validated command instance"""
        param_class = COMMAND_PARAMETER_MAP.get(command_name)
        if not param_class:
            # For commands without specific parameter models
            return BaseCommand(
                command=command_name,
                parameters=parameters,
                metadata=metadata
            )
        
        # Validate parameters
        validated_params = param_class(**parameters)
        
        return BaseCommand(
            command=command_name,
            parameters=validated_params.model_dump(),
            metadata=metadata
        )
    
    @staticmethod
    def parse_command(command_data: Union[str, Dict[str, Any]]) -> BaseCommand:
        """Parse and validate a command from JSON or dict"""
        if isinstance(command_data, str):
            import json
            command_data = json.loads(command_data)
        
        command_name = command_data.get('command')
        parameters = command_data.get('parameters', {})
        
        return CommandFactory.create_command(
            command_name,
            parameters,
            command_data.get('metadata')
        )


class SocketResponse:
    """Factory for creating socket protocol responses"""
    
    @staticmethod
    def success(command: str, result: Any, processing_time_ms: Optional[float] = None) -> Dict[str, Any]:
        """Create a success response"""
        metadata = {"timestamp": TimestampManager.timestamp_utc()}
        if processing_time_ms is not None:
            metadata['processing_time_ms'] = processing_time_ms
            
        response = SuccessResponse(
            command=command,
            result=result if result is not None else {},
            metadata=metadata
        )
        return response.model_dump()
    
    @staticmethod
    def error(command: str, error_code: str, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create an error response"""
        response = ErrorResponse(
            command=command,
            error=ErrorInfo(code=error_code, message=message)
        )
        return response.model_dump()
    
    @staticmethod
    def help(commands: List[Dict[str, Any]], aliases: Dict[str, str]) -> Dict[str, Any]:
        """Create a HELP/GET_COMMANDS response"""
        from .command_response_models import HelpCommandItem, HelpResponse
        # Convert dicts to HelpCommandItem models
        command_items = [
            HelpCommandItem(**cmd) for cmd in commands
        ]
        response = HelpResponse(
            commands=command_items,
            aliases=aliases,
            command="GET_COMMANDS"
        )
        return response.model_dump()
    
    @staticmethod
    def health_check(uptime: int = 0, managers: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a HEALTH_CHECK response"""
        result = {
            "status": "healthy",
            "uptime": uptime,
            "managers": managers or {}
        }
        return SocketResponse.success("HEALTH_CHECK", result)
    
    @staticmethod
    def get_processes(processes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a GET_PROCESSES response"""
        result = {
            "processes": processes,
            "total": len(processes)
        }
        return SocketResponse.success("GET_PROCESSES", result)
    
    @staticmethod
    def get_agents(agents: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Create a GET_AGENTS response"""
        return SocketResponse.success("GET_AGENTS", {"agents": agents})
    
    @staticmethod
    def get_agent_kv(key: str, value: Any, found: bool) -> Dict[str, Any]:
        """Create a GET_AGENT_KV response"""
        return SocketResponse.success("GET_AGENT_KV", {
            "key": key,
            "value": value,
            "found": found
        })
    
    @staticmethod
    def set_agent_kv(key: str) -> Dict[str, Any]:
        """Create a SET_AGENT_KV response"""
        return SocketResponse.success("SET_AGENT_KV", {
            "key": key,
            "status": "set"
        })
    
    @staticmethod
    def cleanup(cleanup_type: str, details: str) -> Dict[str, Any]:
        """Create a CLEANUP response"""
        return SocketResponse.success("CLEANUP", {
            "status": "cleaned",
            "cleanup_type": cleanup_type,
            "details": details
        })
    
    @staticmethod
    def list_items(command: str, items: List[Dict[str, Any]], total: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a list response for commands that return collections"""
        result = {
            "items": items,
            "total": total if total is not None else len(items)
        }
        if metadata:
            result["metadata"] = metadata
        return SocketResponse.success(command, result)


# State Models

class AgentInfo(BaseModel):
    """Agent information model"""
    model_config = ConfigDict(extra='allow')
    
    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    role: str
    capabilities: List[str] = Field(default_factory=list)
    status: Literal["active", "busy", "inactive"] = "active"
    created_at: str = Field(default_factory=lambda: TimestampManager.timestamp_utc())
    sessions: List[str] = Field(default_factory=list)
    
    # Optional fields from different contexts
    profile: Optional[str] = None
    composition: Optional[str] = None
    model: str = "sonnet"
    process_id: Optional[str] = None
    initial_task: Optional[str] = None
    initial_context: Optional[str] = None
    last_active: Optional[str] = None


class IdentityInfo(BaseModel):
    """Identity information model"""
    identity_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    display_name: str
    role: str = "general"
    personality_traits: List[str] = Field(default_factory=list)
    appearance: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: TimestampManager.timestamp_utc())
    last_active: str = Field(default_factory=lambda: TimestampManager.timestamp_utc())
    conversation_count: int = 0
    sessions: List[Dict[str, str]] = Field(default_factory=list)
    preferences: Dict[str, str] = Field(default_factory=lambda: {
        'communication_style': 'professional',
        'verbosity': 'moderate',
        'formality': 'balanced'
    })
    stats: Dict[str, Any] = Field(default_factory=lambda: {
        'messages_sent': 0,
        'conversations_participated': 0,
        'tasks_completed': 0,
        'tools_used': []
    })


class ProcessInfo(BaseModel):
    """Process information model"""
    process_id: str
    type: Literal["claude", "agent_process"] = "claude"
    agent_id: Optional[str] = None
    model: str = "sonnet"
    started_at: str
    session_id: Optional[str] = None
    prompt: Optional[str] = None
    profile: Optional[str] = None