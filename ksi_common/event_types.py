"""
Common TypedDict definitions for KSI event data.

This module provides type definitions for event handlers across the system,
enabling type-safe parameter handling and better discovery.
"""

from typing import TypedDict, Optional, Dict, List, Any, Literal, Union
from typing_extensions import NotRequired, Required

# Base types for all events
class EventDataBase(TypedDict):
    """Base class for all event data."""
    _source: NotRequired[str]  # Event source metadata
    _timestamp: NotRequired[float]  # Event timestamp
    _correlation_id: NotRequired[str]  # For tracking related events


# Composition Service Types
class CompositionCreateBase(TypedDict):
    """Base parameters for composition creation."""
    name: NotRequired[str]  # Auto-generated if not provided
    type: NotRequired[Literal['profile', 'prompt', 'orchestration', 'evaluation']]
    description: NotRequired[str]
    author: NotRequired[str]
    metadata: NotRequired[Dict[str, Any]]
    overwrite: NotRequired[bool]  # For save operations


class CompositionCreateWithContent(CompositionCreateBase):
    """Create composition from full content."""
    content: Required[Dict[str, Any]]  # Full composition structure


class CompositionCreateProfile(CompositionCreateBase):
    """Create profile composition with components."""
    type: Required[Literal['profile']]
    model: NotRequired[str]
    capabilities: NotRequired[List[str]]
    tools: NotRequired[List[str]]
    role: NotRequired[str]
    prompt: NotRequired[str]  # Optional prompt component


class CompositionCreatePrompt(CompositionCreateBase):
    """Create prompt composition."""
    type: Required[Literal['prompt']]
    content: Required[str]  # The prompt text
    category: NotRequired[str]  # Categorization for prompts


# Union type for all composition creation variants
CompositionCreateData = Union[
    CompositionCreateWithContent,
    CompositionCreateProfile,
    CompositionCreatePrompt,
    CompositionCreateBase
]


class CompositionForkData(TypedDict):
    """Fork a composition to create a variant."""
    parent: Required[str]  # Name of parent composition
    name: Required[str]  # Name for forked composition
    reason: Required[str]  # Reason for forking
    modifications: NotRequired[Dict[str, Any]]  # Initial modifications
    author: NotRequired[str]  # Defaults to agent_id


class CompositionMergeData(TypedDict):
    """Merge improvements from fork back to parent."""
    source: Required[str]  # Name of source (fork)
    target: Required[str]  # Name of target (parent)
    strategy: Required[Literal['selective', 'full', 'metadata_only']]
    improvements: NotRequired[List[str]]  # List of improvements
    validation_results: NotRequired[Dict[str, Any]]  # Evaluation results


class CompositionDiffData(TypedDict):
    """Show differences between compositions."""
    left: Required[str]  # First composition
    right: Required[str]  # Second composition
    detail_level: NotRequired[Literal['summary', 'detailed', 'full']]


class CompositionTrackDecisionData(TypedDict):
    """Track orchestrator decisions for learning."""
    pattern: Required[str]  # Pattern name
    decision: Required[str]  # Decision made
    context: Required[Dict[str, Any]]  # Decision context
    outcome: Required[str]  # Decision outcome
    confidence: NotRequired[float]  # Confidence 0-1


class CompositionListData(TypedDict):
    """List compositions with filters."""
    type: NotRequired[Literal['all', 'profile', 'prompt', 'orchestration', 'evaluation']]
    include_validation: NotRequired[bool]
    metadata_filter: NotRequired[Dict[str, Any]]
    evaluation_detail: NotRequired[Literal['none', 'minimal', 'summary', 'detailed']]


class CompositionGetData(TypedDict):
    """Get a specific composition."""
    name: Required[str]
    type: NotRequired[str]
    resolve: NotRequired[bool]  # Resolve inheritance
    raw: NotRequired[bool]  # Return raw YAML


class CompositionValidateData(TypedDict):
    """Validate composition structure."""
    name: Required[str]
    type: NotRequired[str]


class CompositionEvaluateData(TypedDict):
    """Process evaluation results."""
    name: Required[str]
    type: NotRequired[str]
    test_suite: Required[str]
    model: NotRequired[str]
    test_options: NotRequired[Dict[str, Any]]


class CompositionComposeData(TypedDict):
    """Compose from components."""
    name: Required[str]
    type: NotRequired[str]
    variables: NotRequired[Dict[str, Any]]


class CompositionProfileData(TypedDict):
    """Compose a profile."""
    name: Required[str]
    variables: NotRequired[Dict[str, Any]]


# Result types
class CompositionResult(TypedDict):
    """Standard composition operation result."""
    status: Literal['success', 'error']
    name: NotRequired[str]
    composition: NotRequired[Dict[str, Any]]
    path: NotRequired[str]
    message: NotRequired[str]
    error: NotRequired[str]


# Orchestration Service Types
class OrchestrationStartData(TypedDict):
    """Start a new orchestration."""
    pattern: Required[str]  # Pattern name
    vars: NotRequired[Dict[str, Any]]  # Variables for the pattern


class OrchestrationMessageBase(TypedDict):
    """Base message routing data."""
    orchestration_id: Required[str]
    message: Required[Dict[str, Any]]


class OrchestrationMessageDirect(OrchestrationMessageBase):
    """Direct message to specific agent."""
    target_agent: Required[str]


class OrchestrationMessageBroadcast(OrchestrationMessageBase):
    """Broadcast to all agents."""
    broadcast: Required[Literal[True]]


OrchestrationMessageData = Union[
    OrchestrationMessageDirect,
    OrchestrationMessageBroadcast,
    OrchestrationMessageBase
]


class OrchestrationTerminateData(TypedDict):
    """Terminate an orchestration."""
    orchestration_id: Required[str]
    reason: NotRequired[str]


class OrchestrationRequestTerminationData(TypedDict):
    """Agent requests orchestration termination."""
    agent_id: Required[str]
    reason: NotRequired[str]


# Agent Service Types
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


# State Service Types
class StateSetData(TypedDict):
    """Set state value."""
    key: Required[str]
    value: Required[Any]
    namespace: NotRequired[str]
    ttl: NotRequired[float]


class StateGetData(TypedDict):
    """Get state value."""
    key: Required[str]
    namespace: NotRequired[str]
    default: NotRequired[Any]


class StateDeleteData(TypedDict):
    """Delete state value."""
    key: Required[str]
    namespace: NotRequired[str]


# Discovery Types
class SystemDiscoverData(TypedDict):
    """Discover available events."""
    namespace: NotRequired[str]
    event: NotRequired[str]
    module: NotRequired[str]
    detail: NotRequired[bool]
    format_style: NotRequired[Literal['verbose', 'compact', 'ultra_compact', 'mcp']]


class SystemHelpData(TypedDict):
    """Get help for specific event."""
    event: Required[str]


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