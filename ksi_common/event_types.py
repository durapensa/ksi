"""
Common TypedDict definitions for KSI event data.

This module provides type definitions for event handlers across the system,
enabling type-safe parameter handling and better discovery.

NOTE: This file is being phased out. TypedDict definitions should be
co-located with their event handlers in the same module.
"""

from typing import TypedDict, Optional, Dict, List, Any, Literal
from typing_extensions import NotRequired, Required

# Base types for all events
class EventDataBase(TypedDict):
    """Base class for all event data."""
    _source: NotRequired[str]  # Event source metadata
    _timestamp: NotRequired[float]  # Event timestamp
    _correlation_id: NotRequired[str]  # For tracking related events


# Agent Service Types (NOT YET MIGRATED)
class AgentSpawnData(TypedDict):
    """Spawn a new agent."""
    profile: Required[str]
    agent_id: NotRequired[str]  # Auto-generated if not provided
    session_id: NotRequired[str]
    prompt: NotRequired[str]
    context: NotRequired[Dict[str, Any]]
    originator_agent_id: NotRequired[str]
    purpose: NotRequired[str]


class AgentSendMessageData(TypedDict):
    """Send message to an agent."""
    agent_id: Required[str]
    message: Required[Dict[str, Any]]
    wait_for_response: NotRequired[bool]
    timeout: NotRequired[float]


class AgentTerminateData(TypedDict):
    """Terminate an agent."""
    agent_id: Required[str]
    reason: NotRequired[str]


# Common result types
class SuccessResult(TypedDict):
    """Generic success result."""
    status: Literal['success']
    message: NotRequired[str]


class ErrorResult(TypedDict):
    """Generic error result."""
    status: Literal['error']
    error: str
    details: NotRequired[Dict[str, Any]]