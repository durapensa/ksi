#!/usr/bin/env python3
"""
State Protocol - Parameters for state socket operations

Handles persistent agent memory and shared knowledge through simple KV operations.
Agents with SQLite access can perform complex queries directly.
Commands: set_agent_kv, get_agent_kv
"""

from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


# ============================================================================
# KEY-VALUE OPERATIONS
# ============================================================================

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


# ============================================================================
# STATE METADATA (for structured responses)
# ============================================================================

class StateEntryMetadata(BaseModel):
    """Metadata about a state entry"""
    key: str
    namespace: str  # Extracted from key prefix
    owner_agent_id: str
    scope: str
    created_at: str
    expires_at: Optional[str]
    size_bytes: Optional[int]


class StateOperationResult(BaseModel):
    """Result of a state operation"""
    success: bool
    key: str
    operation: Literal["set", "get", "delete"]
    metadata: Optional[StateEntryMetadata] = None
    error: Optional[str] = None


# ============================================================================
# FUTURE EXPANSION PLACEHOLDER
# ============================================================================
# As usage patterns emerge, we may add:
# - ListKeysParameters (with pattern matching)
# - DeleteKeyParameters
# - BulkOperationParameters
# - QueryParameters (for agents without direct SQLite access)
# 
# For now, keeping it simple as requested - agents can use SQLite CLI for complex queries