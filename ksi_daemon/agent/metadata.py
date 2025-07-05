#!/usr/bin/env python3
"""
Agent Metadata Module

Provides type-safe metadata for agent relationships and tracking.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional
import time


@dataclass
class AgentMetadata:
    """Metadata for tracking agent relationships and type information."""
    
    agent_id: str
    originator_agent_id: Optional[str] = None
    agent_type: Literal["originator", "construct", "system"] = "system"
    spawned_at: float = field(default_factory=time.time)
    purpose: Optional[str] = None
    
    @property
    def is_construct(self) -> bool:
        """Check if this agent is a construct (has an originator)."""
        return self.originator_agent_id is not None
        
    @property
    def is_originator(self) -> bool:
        """Check if this agent is an originator type."""
        return self.agent_type == "originator"
    
    @property
    def is_system(self) -> bool:
        """Check if this agent is a system type."""
        return self.agent_type == "system" and self.originator_agent_id is None
    
    def to_dict(self) -> dict:
        """Convert metadata to dictionary for storage/serialization."""
        return {
            "agent_id": self.agent_id,
            "originator_agent_id": self.originator_agent_id,
            "agent_type": self.agent_type,
            "spawned_at": self.spawned_at,
            "purpose": self.purpose
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AgentMetadata":
        """Create metadata from dictionary."""
        return cls(
            agent_id=data["agent_id"],
            originator_agent_id=data.get("originator_agent_id"),
            agent_type=data.get("agent_type", "system"),
            spawned_at=data.get("spawned_at", time.time()),
            purpose=data.get("purpose")
        )