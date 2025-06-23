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

class SpawnParameters(BaseModel):
    """Parameters for SPAWN command"""
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


class ReloadParameters(BaseModel):
    """Parameters for RELOAD command"""
    module_name: str = "handler"


# Agent Management Commands

class RegisterAgentParameters(BaseModel):
    """Parameters for REGISTER_AGENT command"""
    agent_id: str
    role: str
    capabilities: Union[List[str], str] = Field(default_factory=list)
    
    @field_validator('capabilities')
    def normalize_capabilities(cls, v):
        if isinstance(v, str):
            return v.split(',') if v else []
        return v


class SpawnAgentParameters(BaseModel):
    """Parameters for SPAWN_AGENT command"""
    profile_name: str
    task: str
    context: str = ""
    agent_id: Optional[str] = None
    role: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)


class RouteTaskParameters(BaseModel):
    """Parameters for ROUTE_TASK command"""
    task: str
    required_capabilities: List[str]
    context: str = ""


# Message Bus Commands

class SubscribeParameters(BaseModel):
    """Parameters for SUBSCRIBE command"""
    agent_id: str
    event_types: List[str]
    
    @field_validator('event_types')
    def validate_event_types(cls, v):
        if not v:
            raise ValueError("At least one event type required")
        return v


class PublishParameters(BaseModel):
    """Parameters for PUBLISH command"""
    from_agent: str
    event_type: str
    payload: Dict[str, Any]


class AgentConnectionParameters(BaseModel):
    """Parameters for AGENT_CONNECTION command"""
    action: Literal["connect", "disconnect"]
    agent_id: str


# State Management Commands

class SetSharedParameters(BaseModel):
    """Parameters for SET_SHARED command"""
    key: str
    value: str


class GetSharedParameters(BaseModel):
    """Parameters for GET_SHARED command"""
    key: str


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


# Command Models with specific parameters

class SpawnCommand(BaseCommand):
    command: Literal["SPAWN"] = "SPAWN"
    parameters: SpawnParameters


class CleanupCommand(BaseCommand):
    command: Literal["CLEANUP"] = "CLEANUP"
    parameters: CleanupParameters


class ReloadCommand(BaseCommand):
    command: Literal["RELOAD"] = "RELOAD"
    parameters: ReloadParameters


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
    "SPAWN": SpawnParameters,
    "CLEANUP": CleanupParameters,
    "RELOAD": ReloadParameters,
    "REGISTER_AGENT": RegisterAgentParameters,
    "SPAWN_AGENT": SpawnAgentParameters,
    "ROUTE_TASK": RouteTaskParameters,
    "SUBSCRIBE": SubscribeParameters,
    "PUBLISH": PublishParameters,
    "AGENT_CONNECTION": AgentConnectionParameters,
    "SET_SHARED": SetSharedParameters,
    "GET_SHARED": GetSharedParameters,
    "LOAD_STATE": LoadStateParameters,
    "CREATE_IDENTITY": CreateIdentityParameters,
    "UPDATE_IDENTITY": UpdateIdentityParameters,
    "GET_IDENTITY": GetIdentityParameters,
    "REMOVE_IDENTITY": RemoveIdentityParameters,
    "GET_COMPOSITIONS": GetCompositionsParameters,
    "GET_COMPOSITION": GetCompositionParameters,
    "VALIDATE_COMPOSITION": ValidateCompositionParameters,
    "LIST_COMPONENTS": ListComponentsParameters,
    "COMPOSE_PROMPT": ComposePromptParameters,
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


class ResponseFactory:
    """Factory for creating responses"""
    
    @staticmethod
    def success(command: str, result: Any, processing_time_ms: Optional[float] = None) -> SuccessResponse:
        """Create a success response"""
        metadata = {}
        if processing_time_ms is not None:
            metadata['processing_time_ms'] = processing_time_ms
            
        return SuccessResponse(
            command=command,
            result=result,
            metadata=metadata if metadata else None
        )
    
    @staticmethod
    def error(command: str, error_code: str, message: str) -> ErrorResponse:
        """Create an error response"""
        return ErrorResponse(
            command=command,
            error=ErrorInfo(code=error_code, message=message)
        )


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