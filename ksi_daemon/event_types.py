#!/usr/bin/env python3
"""
TypedDict definitions for KSI event data structures.

This module provides type-safe data structures for common KSI events,
enabling better IDE support, type checking, and automatic discovery.
"""

from typing import TypedDict, Optional, Dict, Any, List
from typing_extensions import NotRequired

# State Events

class StateGetData(TypedDict):
    """Data structure for state:get event."""
    key: str
    namespace: NotRequired[str]

class StateSetData(TypedDict):
    """Data structure for state:set event."""
    key: str
    value: Any
    namespace: NotRequired[str]
    metadata: NotRequired[Dict[str, Any]]

class StateDeleteData(TypedDict):
    """Data structure for state:delete event."""
    key: str
    namespace: NotRequired[str]

class StateListData(TypedDict):
    """Data structure for state:list event."""
    namespace: NotRequired[str]
    pattern: NotRequired[str]

# Completion Events

class CompletionAsyncData(TypedDict):
    """Data structure for completion:async event."""
    prompt: str
    model: str
    request_id: NotRequired[str]
    session_id: NotRequired[str]
    temperature: NotRequired[float]
    max_tokens: NotRequired[int]
    priority: NotRequired[str]
    injection_config: NotRequired[Dict[str, Any]]
    agent_config: NotRequired[Dict[str, Any]]

class CompletionCancelData(TypedDict):
    """Data structure for completion:cancel event."""
    request_id: str

# Agent Events

class AgentSpawnData(TypedDict):
    """Data structure for agent:spawn event."""
    agent_id: str
    profile: NotRequired[str]
    profile_name: NotRequired[str]
    composition: NotRequired[Dict[str, Any]]
    session_id: NotRequired[str]
    spawn_mode: NotRequired[str]
    selection_context: NotRequired[Dict[str, Any]]
    task: NotRequired[str]
    enable_tools: NotRequired[bool]
    context: NotRequired[Dict[str, Any]]
    config: NotRequired[Dict[str, Any]]
    permission_profile: NotRequired[str]
    sandbox_config: NotRequired[Dict[str, Any]]

class AgentTerminateData(TypedDict):
    """Data structure for agent:terminate event."""
    agent_id: str
    force: NotRequired[bool]

class AgentSendMessageData(TypedDict):
    """Data structure for agent:send_message event."""
    agent_id: str
    message: Dict[str, Any]

# Conversation Events

class ConversationGetData(TypedDict):
    """Data structure for conversation:get event."""
    session_id: str
    limit: NotRequired[int]
    offset: NotRequired[int]

class ConversationListData(TypedDict):
    """Data structure for conversation:list event."""
    limit: NotRequired[int]
    offset: NotRequired[int]
    sort_by: NotRequired[str]
    reverse: NotRequired[bool]

class ConversationSearchData(TypedDict):
    """Data structure for conversation:search event."""
    query: str
    limit: NotRequired[int]
    search_in: NotRequired[List[str]]

# System Events

class SystemDiscoverData(TypedDict):
    """Data structure for system:discover event."""
    namespace: NotRequired[str]
    include_internal: NotRequired[bool]

class SystemHelpData(TypedDict):
    """Data structure for system:help event."""
    event: str

# Permission Events

class PermissionGetAgentData(TypedDict):
    """Data structure for permission:get_agent event."""
    agent_id: str

class PermissionSetAgentData(TypedDict):
    """Data structure for permission:set_agent event."""
    agent_id: str
    permissions: NotRequired[Dict[str, Any]]
    profile: NotRequired[str]