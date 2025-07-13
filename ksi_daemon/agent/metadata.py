#!/usr/bin/env python3
"""
Agent Metadata Module

Provides generic metadata storage for agents.
Domain-specific patterns should be implemented via orchestration.
"""

from typing import Dict, Any, Optional
import time


class AgentMetadata:
    """Generic metadata container for agents.
    
    This is a simple dict wrapper that allows orchestration patterns
    to store any domain-specific information they need.
    """
    
    def __init__(self, agent_id: str, **kwargs):
        """Initialize with agent_id and any additional metadata."""
        self.data = {
            "agent_id": agent_id,
            "created_at": kwargs.get("created_at", time.time()),
            **kwargs
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get metadata value."""
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set metadata value."""
        self.data[key] = value
    
    def update(self, **kwargs) -> None:
        """Update multiple metadata values."""
        self.data.update(kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        return dict(self.data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMetadata":
        """Create metadata from dictionary."""
        agent_id = data.pop("agent_id", None)
        if not agent_id:
            raise ValueError("agent_id required in metadata")
        return cls(agent_id=agent_id, **data)