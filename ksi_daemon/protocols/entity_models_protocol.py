#!/usr/bin/env python3
"""
Entity Models Protocol - Shared data models used across all sockets

Contains the core entity models that represent system objects.
"""

from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
import uuid
from ..timestamp_utils import TimestampManager


# ============================================================================
# PROCESS ENTITY
# ============================================================================

class ProcessInfo(BaseModel):
    """Information about a running process"""
    process_id: str
    type: Literal["claude", "agent_process"] = "claude"
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    pid: Optional[int] = None
    status: str = "running"
    created_at: Optional[str] = None
    started_at: Optional[str] = None  # Alternative field name
    model: Optional[str] = None
    prompt: Optional[str] = None
    profile: Optional[str] = None
    
    @field_validator('started_at', mode='before')
    def sync_timestamps(cls, v, info):
        # Ensure created_at and started_at are synchronized
        if v is None and info.data.get('created_at'):
            return info.data['created_at']
        return v


# ============================================================================
# AGENT ENTITY
# ============================================================================

class AgentInfo(BaseModel):
    """Information about a registered agent"""
    model_config = ConfigDict(extra='allow')
    
    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    role: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    status: Literal["active", "busy", "inactive"] = "active"
    created_at: str = Field(default_factory=lambda: TimestampManager.timestamp_utc())
    sessions: List[str] = Field(default_factory=list)
    
    # Extended fields for agent profiles
    profile: Optional[str] = None
    composition: Optional[str] = None
    model: str = "sonnet"
    process_id: Optional[str] = None
    initial_task: Optional[str] = None
    initial_context: Optional[str] = None
    last_active: Optional[str] = None


# ============================================================================
# IDENTITY ENTITY (Part of Agent Profile System)
# ============================================================================

class IdentityInfo(BaseModel):
    """Identity information model - part of the agent persona system"""
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


# ============================================================================
# AGENT PROFILE (Unified Identity + Composition)
# ============================================================================

class AgentProfile(BaseModel):
    """Unified agent profile combining identity and composition for the persona system"""
    agent_id: str
    
    # Identity aspects
    display_name: str
    role: str
    personality_traits: List[str] = Field(default_factory=list)
    preferences: Dict[str, str] = Field(default_factory=dict)
    
    # Composition aspects
    composition_name: Optional[str] = None
    composition_version: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    
    # Runtime information
    status: Literal["active", "busy", "inactive"] = "active"
    sessions: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: TimestampManager.timestamp_utc())
    last_active: Optional[str] = None
    
    # Statistics
    stats: Dict[str, Any] = Field(default_factory=lambda: {
        'messages_sent': 0,
        'tasks_completed': 0,
        'compositions_used': []
    })


# ============================================================================
# HELPER MODELS FOR SPECIALIZED RESPONSES
# ============================================================================

class HelpCommandItem(BaseModel):
    """Individual command in HELP response"""
    command: str
    source: str = "registry"
    description: str = "Command registered"
    parameters: Dict[str, Any] = Field(default_factory=dict)