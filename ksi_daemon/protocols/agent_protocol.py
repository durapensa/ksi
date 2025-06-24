#!/usr/bin/env python3
"""
Agent Protocol - Parameters for agent socket operations

Handles agent lifecycle and the unified persona system (identity + composition).
Commands: register_agent, spawn_agent, route_task, get_agents,
          create_identity, update_identity, get_identity, list_identities, remove_identity,
          get_compositions, get_composition, validate_composition, list_components, compose_prompt
"""

from typing import Dict, Any, List, Optional, Union, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================================
# AGENT LIFECYCLE MANAGEMENT
# ============================================================================

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
    """Parameters for SPAWN_AGENT command - includes intelligent composition selection"""
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


# GET_AGENTS - No parameters needed


# ============================================================================
# AGENT IDENTITY MANAGEMENT (Part of Persona System)
# ============================================================================

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


class ListIdentitiesParameters(BaseModel):
    """Parameters for LIST_IDENTITIES command"""
    sort_by: Optional[str] = Field(default="created_at", description="Field to sort by")
    order: Optional[str] = Field(default="desc", description="Sort order: asc or desc")
    filter_role: Optional[str] = Field(default=None, description="Filter by role")
    filter_active: Optional[bool] = Field(default=None, description="Filter by active status")


class RemoveIdentityParameters(BaseModel):
    """Parameters for REMOVE_IDENTITY command"""
    agent_id: str


# ============================================================================
# COMPOSITION SYSTEM (Part of Persona System)
# ============================================================================

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


# ============================================================================
# UNIFIED AGENT PROFILE OPERATIONS
# ============================================================================

class CreateAgentProfileParameters(BaseModel):
    """Parameters for creating a unified agent profile (identity + composition)"""
    agent_id: str
    display_name: str
    role: str
    composition_name: Optional[str] = None
    personality_traits: List[str] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    preferences: Dict[str, str] = Field(default_factory=dict)
    initial_task: Optional[str] = None
    initial_context: Optional[str] = None


class UpdateAgentProfileParameters(BaseModel):
    """Parameters for updating an agent profile"""
    agent_id: str
    updates: Dict[str, Any]
    
    @model_validator(mode='after')
    def validate_updates(self):
        protected_fields = {'agent_id', 'created_at'}
        if any(field in self.updates for field in protected_fields):
            raise ValueError(f"Cannot update protected fields: {protected_fields}")
        return self