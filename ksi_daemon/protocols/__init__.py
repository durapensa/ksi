#!/usr/bin/env python3
"""
Unified Protocol Models - Central export point for all socket protocols

Organized by socket domain for the multi-socket architecture:
- admin.sock: System administration and monitoring
- agents.sock: Agent lifecycle and persona management
- messaging.sock: Ephemeral communication and events
- state.sock: Persistent agent memory and shared knowledge
- completion.sock: LLM completion requests
"""

# Foundation exports
from .foundation_protocol import (
    BaseCommand, BaseResponse, SuccessResponse, ErrorResponse, ErrorInfo,
    SocketResponse, CommandFactory
)

# Entity models exports
from .entity_models_protocol import (
    ProcessInfo, AgentInfo, IdentityInfo, AgentProfile, HelpCommandItem
)

# Admin protocol exports
from .admin_protocol import (
    CleanupParameters, ReloadModuleParameters, LoadStateParameters,
    HealthCheckResponse, ProcessInfoDetailed, MessageBusStats
)

# Agent protocol exports
from .agent_protocol import (
    RegisterAgentParameters, SpawnAgentParameters, RouteTaskParameters,
    CreateIdentityParameters, UpdateIdentityParameters, GetIdentityParameters,
    ListIdentitiesParameters, RemoveIdentityParameters,
    GetCompositionsParameters, GetCompositionParameters, ValidateCompositionParameters,
    ListComponentsParameters, ComposePromptParameters,
    CreateAgentProfileParameters, UpdateAgentProfileParameters
)

# Messaging protocol exports
from .messaging_protocol import (
    SubscribeParameters, PublishParameters, SendMessageParameters, AgentConnectionParameters,
    CompletionResultEvent, CompletionSuccessData, CompletionErrorData,
    BaseEvent, DirectMessage, BroadcastMessage, TaskAssignment, AgentStatusUpdate, SystemEvent
)

# State protocol exports
from .state_protocol import (
    SetAgentKVParameters, GetAgentKVParameters,
    StateEntryMetadata, StateOperationResult
)

# Completion protocol exports
from .completion_protocol import (
    CompletionParameters, CompletionAcknowledgment,
    ModelConfig, CompletionQueueStatus
)


# ============================================================================
# COMMAND PARAMETER MAPPING
# ============================================================================

COMMAND_PARAMETER_MAP = {
    # Admin socket commands
    "CLEANUP": CleanupParameters,
    "RELOAD_MODULE": ReloadModuleParameters,
    "LOAD_STATE": LoadStateParameters,
    # Commands without parameters: HEALTH_CHECK, GET_COMMANDS, HELP, GET_PROCESSES,
    # MESSAGE_BUS_STATS, SHUTDOWN, RELOAD_DAEMON
    
    # Agent socket commands
    "REGISTER_AGENT": RegisterAgentParameters,
    "SPAWN_AGENT": SpawnAgentParameters,
    "ROUTE_TASK": RouteTaskParameters,
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
    # Commands without parameters: GET_AGENTS
    
    # Messaging socket commands
    "SUBSCRIBE": SubscribeParameters,
    "PUBLISH": PublishParameters,
    "SEND_MESSAGE": SendMessageParameters,
    "AGENT_CONNECTION": AgentConnectionParameters,
    
    # State socket commands
    "SET_AGENT_KV": SetAgentKVParameters,
    "GET_AGENT_KV": GetAgentKVParameters,
    
    # Completion socket commands
    "COMPLETION": CompletionParameters,
}


# ============================================================================
# SOCKET COMMAND MAPPING (for routing and validation)
# ============================================================================

SOCKET_COMMANDS = {
    "admin": [
        "HEALTH_CHECK", "GET_COMMANDS", "HELP", "GET_PROCESSES",
        "MESSAGE_BUS_STATS", "SHUTDOWN", "RELOAD_DAEMON",
        "CLEANUP", "RELOAD_MODULE", "LOAD_STATE"
    ],
    "agents": [
        "REGISTER_AGENT", "SPAWN_AGENT", "ROUTE_TASK", "GET_AGENTS",
        "CREATE_IDENTITY", "UPDATE_IDENTITY", "GET_IDENTITY",
        "LIST_IDENTITIES", "REMOVE_IDENTITY",
        "GET_COMPOSITIONS", "GET_COMPOSITION", "VALIDATE_COMPOSITION",
        "LIST_COMPONENTS", "COMPOSE_PROMPT"
    ],
    "messaging": [
        "SUBSCRIBE", "PUBLISH", "SEND_MESSAGE", "AGENT_CONNECTION"
    ],
    "state": [
        "SET_AGENT_KV", "GET_AGENT_KV"
    ],
    "completion": [
        "COMPLETION"
    ]
}


__all__ = [
    # Foundation
    "BaseCommand", "BaseResponse", "SuccessResponse", "ErrorResponse", "ErrorInfo",
    "SocketResponse", "CommandFactory",
    
    # Entities
    "ProcessInfo", "AgentInfo", "IdentityInfo", "AgentProfile", "HelpCommandItem",
    
    # Admin
    "CleanupParameters", "ReloadModuleParameters", "LoadStateParameters",
    "HealthCheckResponse", "ProcessInfoDetailed", "MessageBusStats",
    
    # Agent
    "RegisterAgentParameters", "SpawnAgentParameters", "RouteTaskParameters",
    "CreateIdentityParameters", "UpdateIdentityParameters", "GetIdentityParameters",
    "ListIdentitiesParameters", "RemoveIdentityParameters",
    "GetCompositionsParameters", "GetCompositionParameters", "ValidateCompositionParameters",
    "ListComponentsParameters", "ComposePromptParameters",
    "CreateAgentProfileParameters", "UpdateAgentProfileParameters",
    
    # Messaging
    "SubscribeParameters", "PublishParameters", "SendMessageParameters", "AgentConnectionParameters",
    "CompletionResultEvent", "CompletionSuccessData", "CompletionErrorData",
    "BaseEvent", "DirectMessage", "BroadcastMessage", "TaskAssignment", "AgentStatusUpdate", "SystemEvent",
    
    # State
    "SetAgentKVParameters", "GetAgentKVParameters",
    "StateEntryMetadata", "StateOperationResult",
    
    # Completion
    "CompletionParameters", "CompletionAcknowledgment",
    "ModelConfig", "CompletionQueueStatus",
    
    # Mappings
    "COMMAND_PARAMETER_MAP", "SOCKET_COMMANDS"
]