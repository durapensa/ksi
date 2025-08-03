#!/usr/bin/env python3
"""
Agent Service Module - Event-Based Version

Provides agent management without complex inheritance.
Handles agent lifecycle, identities, and routing through events.
Uses composition service for all component/configuration needs.
"""

import asyncio
import json
import time
import uuid
import fnmatch
from functools import wraps
from typing import Any, Dict, TypedDict, List, Literal, Optional
from datetime import datetime, timezone
import aiofiles

from typing_extensions import NotRequired, Required

from ksi_common import format_for_logging
from ksi_common.agent_context import propagate_agent_context
from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc
from ksi_common.agent_utils import (
    query_agent_state, query_agent_metadata, query_agent_relationships, 
    unwrap_list_response, emit_agent_event, gather_agent_info
)
from ksi_common.composition_utils import render_component_to_agent_manifest
from ksi_common.task_management import create_tracked_task
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_common.response_patterns import validate_required_fields, entity_not_found_response, batch_operation_response, agent_responses
from ksi_common.json_utils import parse_json_parameter
from .identity_operations import (
    load_all_identities, save_identity, remove_identity, save_all_identities
)
from ksi_daemon.capability_enforcer import get_capability_enforcer
from ksi_daemon.event_system import event_handler as base_event_handler, shutdown_handler, get_router
from ksi_daemon.mcp import mcp_config_manager
# AgentMetadata removed - using state system storage
# NOTE: session_id is a completion system concept - agents have no awareness of sessions

# Module state
logger = get_bound_logger("agent_service", version="2.0.0")
agents: Dict[str, Dict[str, Any]] = {}  # agent_id -> agent_info
identities: Dict[str, Dict[str, Any]] = {}  # agent_id -> identity_info
agent_threads: Dict[str, asyncio.Task] = {}  # agent_id -> task

# Storage paths
identity_storage_path = config.identity_storage_path

# Event emitter reference (set during context)
event_emitter = None


# Enhanced event handler with agent-specific patterns
def event_handler(event_name, schema=None, require_agent=True, auto_response=True, **kwargs):
    """
    Agent-enhanced event handler with automatic parsing and validation.
    
    Args:
        event_name: Event name to handle
        schema: TypedDict schema for automatic parsing (optional)
        require_agent: Whether to validate agent_id exists (default: True)
        auto_response: Whether to auto-wrap responses (default: True)
        **kwargs: Additional arguments passed to base event handler
        
    Usage:
        @event_handler("agent:list", schema=AgentListData, require_agent=False)
        async def handle_list_agents(data, context):
            return {"agents": [...]}  # Auto-wrapped with event_response_builder
    """
    def decorator(func):
        @base_event_handler(event_name, **kwargs)
        @wraps(func)
        async def wrapper(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            # BREAKING CHANGE: Direct typed data access, _ksi_context contains system metadata
            from ksi_common.event_response_builder import event_response_builder, error_response
            from ksi_common.response_patterns import validate_required_fields, entity_not_found_response, batch_operation_response, agent_responses
            
            try:
                # Data is already properly typed from event system - no parsing needed
                # Schema parameter is now used only for documentation/type hints
                
                # Validate agent exists if required
                if require_agent and "agent_id" in data:
                    agent_id = data["agent_id"]
                    if not agent_id:
                        return error_response("agent_id required", context)
                    if agent_id not in agents:
                        return entity_not_found_response("agent", agent_id, context)
                
                # Call the handler
                result = await func(data, context)
                
                # Auto-wrap response if needed
                if auto_response and isinstance(result, dict) and "status" not in result and "error" not in result:
                    return event_response_builder(result, context)
                return result
                
            except Exception as e:
                logger.error(f"Agent event handler {func.__name__} failed: {e}")
                return error_response(f"Handler failed: {str(e)}", context)
        return wrapper
    return decorator


# TypedDict definitions for event handlers

class SystemContextData(TypedDict):
    """System context with runtime references."""
    emit_event: NotRequired[Any]  # Event emitter function
    shutdown_event: NotRequired[Any]  # Shutdown event object
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class SystemStartupData(TypedDict):
    """System startup configuration."""
    # No specific fields required for agent service
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class SystemReadyData(TypedDict):
    """System ready notification."""
    # No specific fields for agent service
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class SystemShutdownData(TypedDict):
    """System shutdown notification."""
    # No specific fields for shutdown
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class ObservationReadyData(TypedDict):
    """Observation system ready notification."""
    status: NotRequired[str]  # Ready status
    ephemeral: NotRequired[bool]  # Ephemeral subscriptions flag
    message: NotRequired[str]  # Status message
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class ObservationRestoredData(TypedDict):
    """Observation subscriptions restored from checkpoint."""
    subscriptions_restored: NotRequired[int]  # Number of subscriptions restored
    from_checkpoint: NotRequired[str]  # Checkpoint timestamp
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class CheckpointCollectData(TypedDict):
    """Collect checkpoint data."""
    # No specific fields - collects all agent state
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class CheckpointRestoreData(TypedDict):
    """Restore from checkpoint data."""
    agents: NotRequired[Dict[str, Any]]  # Agent state to restore
    identities: NotRequired[Dict[str, Any]]  # Agent identities to restore
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class AgentSpawnData(TypedDict):
    """Spawn a new agent."""
    component: Required[str]  # Component name - matches relative path without extension (e.g., "components/agents/hello_agent" for components/agents/hello_agent.md)
    agent_id: NotRequired[str]  # Agent ID (auto-generated if not provided)
    variables: NotRequired[Dict[str, Any]]  # Variables for component template substitution
    # NOTE: session_id removed - managed entirely by completion system
    prompt: NotRequired[str]  # Initial prompt to send after spawn
    context: NotRequired[Dict[str, Any]]  # Additional context
    model: NotRequired[str]  # Model to use (overrides component default)
    enable_tools: NotRequired[bool]  # Enable tool usage (overrides component default)
    permission_profile: NotRequired[str]  # Permission profile name
    sandbox_dir: NotRequired[str]  # Sandbox directory
    mcp_config_path: NotRequired[str]  # MCP configuration path
    conversation_id: NotRequired[str]  # Conversation ID
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class AgentTerminateData(TypedDict):
    """Terminate agents - supports both single and bulk operations."""
    agent_id: NotRequired[str]  # Single agent ID to terminate
    agent_ids: NotRequired[List[str]]  # Multiple agent IDs to terminate
    pattern: NotRequired[str]  # Terminate agents matching pattern (e.g., "test_*")
    older_than_hours: NotRequired[float]  # Terminate agents older than X hours
    component: NotRequired[str]  # Terminate agents with specific component
    all: NotRequired[bool]  # Terminate all agents (use with caution)
    force: NotRequired[bool]  # Force termination
    dry_run: NotRequired[bool]  # Show what would be terminated without doing it
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class AgentRestartData(TypedDict):
    """Restart an agent."""
    agent_id: Required[str]  # Agent ID to restart
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class AgentRegisterData(TypedDict):
    """Register an external agent."""
    agent_id: Required[str]  # Agent ID to register
    component: NotRequired[str]  # Agent component
    capabilities: NotRequired[List[str]]  # Agent capabilities
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class AgentUnregisterData(TypedDict):
    """Unregister an agent."""
    agent_id: Required[str]  # Agent ID to unregister
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class AgentListData(TypedDict):
    """List agents."""
    status: NotRequired[str]  # Filter by status
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


# Construct-specific handlers removed - use orchestration patterns instead
    include_terminated: NotRequired[bool]  # Include terminated agents
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class AgentCreateIdentityData(TypedDict):
    """Create a new agent identity."""
    agent_id: Required[str]  # Agent ID
    identity: Required[Dict[str, Any]]  # Identity information
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class AgentUpdateIdentityData(TypedDict):
    """Update an agent identity."""
    agent_id: Required[str]  # Agent ID
    identity: Required[Dict[str, Any]]  # Updated identity information
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class AgentRemoveIdentityData(TypedDict):
    """Remove an agent identity."""
    agent_id: Required[str]  # Agent ID
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class AgentListIdentitiesData(TypedDict):
    """List agent identities."""
    # No specific fields - returns all identities
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class AgentRouteTaskData(TypedDict):
    """Route a task to an appropriate agent."""
    task: Required[Dict[str, Any]]  # Task to route
    requirements: NotRequired[List[str]]  # Required capabilities
    exclude_agents: NotRequired[List[str]]  # Agents to exclude
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class AgentSendMessageData(TypedDict):
    """Send message to an agent."""
    agent_id: Required[str]  # Target agent ID
    message: Required[Dict[str, Any]]  # Message to send
    wait_for_response: NotRequired[bool]  # Wait for response
    timeout: NotRequired[float]  # Response timeout
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class AgentBroadcastData(TypedDict):
    """Broadcast a message to all agents."""
    message: Required[Dict[str, Any]]  # Message to broadcast
    exclude_agents: NotRequired[List[str]]  # Agents to exclude
    agent_types: NotRequired[List[str]]  # Filter by agent types
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class AgentUpdateCompositionData(TypedDict):
    """Update agent composition."""
    agent_id: Required[str]  # Agent ID
    composition: Required[str]  # New composition name
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class AgentDiscoverPeersData(TypedDict):
    """Discover other agents and their capabilities."""
    agent_id: NotRequired[str]  # Requesting agent ID
    capabilities: NotRequired[List[str]]  # Required capabilities
    agent_types: NotRequired[List[str]]  # Filter by agent types
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class AgentNegotiateRolesData(TypedDict):
    """Coordinate role negotiation between agents."""
    agents: Required[List[str]]  # Agent IDs to negotiate
    roles: Required[Dict[str, str]]  # Role assignments
    context: NotRequired[Dict[str, Any]]  # Negotiation context
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


class AgentInfoData(TypedDict):
    """Get comprehensive information about an agent."""
    agent_id: Required[str]  # Agent ID to get info for
    include: NotRequired[List[Literal['state', 'identity', 'relationships', 'metadata', 'messages', 'observations', 'events']]]  # What to include (default: ['state', 'identity'])
    depth: NotRequired[int]  # Graph traversal depth for relationships (default: 1, max: 3)
    event_limit: NotRequired[int]  # Max number of recent events to include (default: 10)
    message_limit: NotRequired[int]  # Max number of recent messages to include (default: 10)
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


# Helper functions


async def route_to_originator(agent_id: str, event_name: str, event_data: Dict[str, Any]) -> None:
    """Route an event result back to the originator of an agent spawn chain."""
    if not event_emitter:
        logger.warning("Cannot route to originator: event_emitter not available")
        return
    
    agent_info = agents.get(agent_id)
    if not agent_info:
        logger.warning(f"Cannot route to originator: agent {agent_id} not found")
        return
    
    originator_context = agent_info.get("originator_context")
    if not originator_context:
        # No originator context - event was not spawned through streaming architecture
        return
    
    originator_type = originator_context.get("type")
    originator_id = originator_context.get("id")
    
    try:
        if originator_type == "agent":
            # Route back to originating agent via completion:async
            return_path = originator_context.get("return_path", "completion:async")
            
            # Inject event result into originating agent's completion stream
            await event_emitter(return_path, {
                "agent_id": originator_id,
                "event_result": {
                    "source_agent": agent_id,
                    "event": event_name,
                    "data": event_data,
                    "timestamp": timestamp_utc(),
                    "chain_id": originator_context.get("chain_id")
                }
            })
            logger.debug(f"Routed event {event_name} from {agent_id} to agent {originator_id}")
            
        elif originator_type == "external":
            # Route to external originator via monitor:event_chain_result
            await event_emitter("monitor:event_chain_result", {
                "originator_id": originator_id,
                "source_agent": agent_id,
                "event": event_name,
                "data": event_data,
                "timestamp": timestamp_utc(),
                "chain_id": originator_context.get("chain_id")
            })
            logger.debug(f"Routed event {event_name} from {agent_id} to external {originator_id}")
            
        elif originator_type == "system":
            # Route to system monitoring/logging
            await event_emitter("monitor:system_event", {
                "source_agent": agent_id,
                "event": event_name,
                "data": event_data,
                "timestamp": timestamp_utc(),
                "chain_id": originator_context.get("chain_id")
            })
            logger.debug(f"Routed event {event_name} from {agent_id} to system monitoring")
            
        else:
            logger.warning(f"Unknown originator type: {originator_type}")
            
    except Exception as e:
        logger.error(f"Failed to route event {event_name} from {agent_id} to originator: {e}")


async def agent_emit_event(agent_id: str, event_name: str, event_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
    """Agent-aware event emitter that routes ALL results back to originator.
    
    This function replaces direct event_emitter calls for agents, ensuring that
    ALL event results (success and errors) flow back to the originating agent or external system.
    """
    if not event_emitter:
        logger.error(f"Agent {agent_id} cannot emit event {event_name}: event_emitter not available")
        return {"error": "Event emitter not available"}
    
    try:
        # Emit the event normally
        logger.info(f"DEBUG: agent_emit_event calling event_emitter for {event_name}")
        result = await event_emitter(event_name, event_data, context)
        logger.info(f"DEBUG: event_emitter returned for {event_name}: {result}")
        
        # Route result back to originator (for ALL events)
        await route_to_originator(agent_id, event_name, result)
        
        # Also route through hierarchical system based on subscription levels
        from ksi_daemon.core.hierarchical_routing import route_hierarchical_event
        await route_hierarchical_event(agent_id, event_name, result)
        
        return result
        
    except Exception as e:
        error_result = {"error": str(e), "event": event_name}
        logger.error(f"Agent {agent_id} event {event_name} failed: {e}")
        
        # Route error back to originator too
        await route_to_originator(agent_id, event_name, error_result)
        
        # Also route error through hierarchical system
        from ksi_daemon.core.hierarchical_routing import route_hierarchical_event
        await route_hierarchical_event(agent_id, event_name, error_result)
        
        return error_result


# System event handlers
@event_handler("system:context", schema=SystemContextData, require_agent=False, auto_response=False)
async def handle_context(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
    """Receive module context with event emitter."""
    global event_emitter
    # Get router for event emission
    router = get_router()
    event_emitter = router.emit
    logger.info("Agent service received context, event_emitter configured")
    
    # Initialize hierarchical routing system
    from ksi_daemon.core.hierarchical_routing import set_event_emitter
    set_event_emitter(event_emitter)
    logger.info("Hierarchical routing system initialized")


@event_handler("system:startup", schema=SystemStartupData, require_agent=False)
async def handle_startup(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Initialize agent service on startup."""
    
    # Load existing identities
    loaded_identities = await load_all_identities(identity_storage_path)
    identities.update(loaded_identities)
    
    logger.info(f"Agent service started - agents: {len(agents)}, "
                f"identities: {len(identities)}")
    
    return {
        "status": "agent_service_ready",
        "agents": len(agents),
        "identities": len(identities)
    }


@event_handler("system:ready", schema=SystemReadyData, require_agent=False)
async def handle_ready(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load agents from graph database after all services are ready."""
    loaded_agents = 0
    
    # Load service-specific transformers now that event_emitter is available
    if event_emitter:
        from ksi_common.service_transformer_manager import auto_load_service_transformers
        transformer_result = await auto_load_service_transformers("agent_service", event_emitter)
        if transformer_result.get("status") == "success":
            logger.info(f"Loaded {transformer_result.get('total_loaded', 0)} agent service transformers from {transformer_result.get('files_loaded', 0)} files")
        else:
            logger.warning(f"Issue loading agent service transformers: {transformer_result}")
    
    if not event_emitter:
        logger.error("Event emitter not available, cannot load agents from state")
        return {"loaded_agents": 0}
    
    try:
        # Query all suspended agents from graph database
        logger.debug("Querying for suspended agents...")
        result = await event_emitter("state:entity:query", {
            "type": "agent",
            "where": {"status": "suspended"}
        })
        logger.debug(f"Query result: {result}")
        
        # Handle both single dict and list of dicts responses
        if isinstance(result, list) and result:
            result = result[0]
        
        if result and "entities" in result:
            for entity in result["entities"]:
                # Check which field contains the agent ID
                agent_id = entity.get("id") or entity.get("entity_id") or entity.get("name")
                if not agent_id:
                    logger.warning(f"Entity missing ID field: {entity}")
                    continue
                props = entity.get("properties", {})
                
                # Skip if agent already exists (shouldn't happen but be safe)
                if agent_id in agents:
                    continue
                
                # Reconstruct agent info from entity properties
                agent_info = {
                    "agent_id": agent_id,
                    "component": props.get("component") or props.get("profile"),  # Support legacy
                    "composition": props.get("composition", props.get("component", props.get("profile"))),  # Fallback chain
                    "config": {
                        "model": props.get("model", config.completion_default_model),  # Use stored model or system default
                        "role": "assistant",
                        "enable_tools": props.get("enable_tools", False),
                        "expanded_capabilities": props.get("capabilities", []),
                        "allowed_events": props.get("allowed_events", []),  # Use stored allowed_events
                        "allowed_claude_tools": props.get("allowed_claude_tools", [])  # Use stored allowed_claude_tools
                    },
                    "status": props.get("status", "ready"),
                    "created_at": entity.get("created_at_iso"),
                    # NOTE: session_id removed - agents have no awareness of sessions
                    "permission_profile": props.get("permission_profile", "standard"),
                    "sandbox_dir": props.get("sandbox_dir"),
                    "sandbox_uuid": props.get("sandbox_uuid"),  # Must use stored value
                    "mcp_config_path": props.get("mcp_config_path"),
                    "conversation_id": None,
                    "message_queue": asyncio.Queue(),
                    # Metadata stored in state system
                    "metadata_namespace": f"metadata:agent:{agent_id}"
                }
                
                # Register agent
                agents[agent_id] = agent_info
                
                # Start agent thread
                task = create_tracked_task("agent_service", run_agent_thread(agent_id), task_name=f"agent_thread_{agent_id}")
                agent_threads[agent_id] = task
                
                # Mark agent as active again
                try:
                    await event_emitter("state:entity:update", {
                        "id": agent_id,
                        "properties": {"status": "active"}
                    })
                except Exception as e:
                    logger.error(f"Failed to mark agent {agent_id} as active: {e}")
                
                loaded_agents += 1
                logger.debug(f"Loaded agent {agent_id} from graph database")
                
    except Exception as e:
        logger.error(f"Failed to load agents from graph database: {e}", exc_info=True)
    
    logger.info(f"Loaded {loaded_agents} agents from state (total: {len(agents)})")
    
    # Re-establish observation subscriptions for loaded agents
    # TODO: Implement reestablish_observations when needed
    # if loaded_agents > 0:
    #     await reestablish_observations({})
    
    return {
        "agents_loaded": loaded_agents,
        "total_agents": len(agents)
    }


@shutdown_handler("agent_service")
async def handle_shutdown(data: SystemShutdownData) -> None:
    """Clean up on shutdown - update state before terminating."""
    # First, mark all agents as suspended in the graph
    if event_emitter:
        # Collect all update operations
        update_tasks = []
        for agent_id in list(agents.keys()):
            try:
                # The event_emitter returns the result from handlers
                task = event_emitter("state:entity:update", {
                    "id": agent_id,
                    "properties": {"status": "suspended"}
                })
                update_tasks.append(task)
                logger.debug(f"Marking agent {agent_id} as suspended")
            except Exception as e:
                logger.error(f"Failed to update agent {agent_id} status: {e}")
        
        # Wait for all state updates to complete
        if update_tasks:
            results = await asyncio.gather(*update_tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to suspend agent: {result}")
                else:
                    logger.debug(f"Agent suspension confirmed")
    
    # Then cancel all agent threads
    for agent_id, task in list(agent_threads.items()):
        task.cancel()
    
    # Save all identities
    await save_all_identities(identity_storage_path, identities)
    
    logger.info(f"Agent service stopped - {len(agents)} agents, "
                f"{len(identities)} identities")
    
    # Acknowledge shutdown to event system
    router = get_router()
    await router.acknowledge_shutdown("agent_service")


# Observation patterns removed - orchestration handles agent relationships


# Observation handlers removed - orchestration patterns handle subscriptions


# Session tracking is now handled by completion service ConversationTracker
# No longer need completion:result handler in agent service


@event_handler("checkpoint:collect", schema=CheckpointCollectData, require_agent=False)
async def handle_checkpoint_collect(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Collect agent state for checkpoint."""
    # Prepare agent state for checkpointing
    agent_state = {}
    
    for agent_id, agent_info in agents.items():
        # Skip terminated agents
        if agent_info.get("status") == "terminated":
            continue
            
        # Create a serializable copy of agent info
        checkpoint_info = {
            "agent_id": agent_id,
            "component": agent_info.get("component") or agent_info.get("profile"),  # Support legacy
            "composition": agent_info.get("composition"),
            "config": agent_info.get("config", {}),
            "status": agent_info.get("status"),
            "created_at": agent_info.get("created_at"),
            # session_id removed - managed by completion system
            "permission_profile": agent_info.get("permission_profile"),
            "sandbox_dir": agent_info.get("sandbox_dir"),
            "sandbox_uuid": agent_info.get("sandbox_uuid"),  # Include sandbox UUID
            "mcp_config_path": agent_info.get("mcp_config_path"),
            "conversation_id": agent_info.get("conversation_id"),
            # Metadata stored in state system
            "metadata_namespace": f"metadata:agent:{agent_id}"
        }
        
        agent_state[agent_id] = checkpoint_info
    
    checkpoint_data = {
        "agents": agent_state,
        "identities": dict(identities),
        "active_agents": len([a for a in agents.values() if a.get("status") in ["ready", "active"]])
    }
    
    logger.info(f"Collected agent state for checkpoint: {len(agent_state)} agents")
    return checkpoint_data


@event_handler("checkpoint:restore", schema=CheckpointRestoreData, require_agent=False)
async def handle_checkpoint_restore(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Restore agent state from checkpoint."""
    # Extract agent data from checkpoint
    checkpoint_agents = data.get("agents", {})
    checkpoint_identities = data.get("identities", {})
    
    restored_agents = 0
    failed_restorations = []
    
    # Restore identities first
    identities.clear()
    identities.update(checkpoint_identities)
    
    # Restore agents
    for agent_id, agent_info in checkpoint_agents.items():
        try:
            # Metadata will be restored from state system separately
            
            # Restore agent info
            restored_info = dict(agent_info)
            restored_info["message_queue"] = asyncio.Queue()
            # Metadata is in state system, not in memory
            
            # Register restored agent
            agents[agent_id] = restored_info
            
            # Restart agent thread
            agent_task = create_tracked_task("agent_service", run_agent_thread(agent_id), task_name=f"agent_thread_{agent_id}")
            agent_threads[agent_id] = agent_task
            
            restored_agents += 1
            logger.debug(f"Restored agent {agent_id}")
            
        except Exception as e:
            logger.error(f"Failed to restore agent {agent_id}: {e}")
            failed_restorations.append({"agent_id": agent_id, "error": str(e)})
    
    # Update agent entities in graph database if we have event_emitter
    if event_emitter and restored_agents > 0:
        for agent_id in agents.keys():
            try:
                await event_emitter("state:entity:create", {
                    "id": agent_id,
                    "type": "agent",
                    "properties": {
                        "status": agents[agent_id].get("status", "active"),
                        "component": agents[agent_id].get("component") or agents[agent_id].get("profile"),  # Support legacy
                        "capabilities": agents[agent_id].get("config", {}).get("expanded_capabilities", []),
                        # Domain fields removed - use metadata
                        "permission_profile": agents[agent_id].get("permission_profile"),
                        "sandbox_dir": agents[agent_id].get("sandbox_dir"),
                        "mcp_config_path": agents[agent_id].get("mcp_config_path")
                    }
                })
            except Exception as e:
                logger.warning(f"Failed to restore agent entity {agent_id}: {e}")
    
    result = {
        "restored_agents": restored_agents,
        "restored_identities": len(checkpoint_identities),
        "failed_restorations": failed_restorations
    }
    
    logger.info(f"Agent checkpoint restore complete: {restored_agents} agents restored")
    return result


# Agent lifecycle handlers
@event_handler("agent:spawn", schema=AgentSpawnData, require_agent=False)
async def handle_spawn_agent(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Spawn a new agent with a component.
    
    The 'component' parameter is REQUIRED and expects a component name from the composition system.
    The name matches the relative path without extension:
    - "components/core/base_agent" → components/core/base_agent.md
    - "components/agents/hello_agent" → components/agents/hello_agent.md
    
    Variables can be passed for template substitution in the component.
    To discover available components: ksi send composition:discover --type component
    """
    
    # Note: context and selection_context are system-internal parameters,
    # not CLI parameters, so they don't need JSON string parsing
    
    agent_id = data.get("agent_id") or f"agent_{uuid.uuid4().hex[:8]}"
    component_name = data.get("component")  # Required field
    # NOTE: session_id is intentionally NOT extracted from spawn data
    # Session management is handled entirely by the completion system
    
    if not component_name:
        return error_response(
            "component is required for agent spawn",
            context=context
        )
    
    # Check for dynamic spawn mode
    spawn_mode = data.get("spawn_mode", "fixed")
    selection_context = data.get("selection_context", {})
    
    # Determine what component to use
    if spawn_mode == "dynamic" and event_emitter:
        # Use composition selection service to dynamically choose component
        logger.debug("Using dynamic composition selection")
        
        select_result = await event_emitter("composition:select", {
            "agent_id": agent_id,
            "role": selection_context.get("role"),
            "capabilities": selection_context.get("required_capabilities", []),
            "task": data.get("task"),
            "context": selection_context,
            "max_suggestions": 3
        }, propagate_agent_context(context))
        
        select_result = unwrap_list_response(select_result)
        
        if select_result and select_result.get("status") == "success":
            compose_name = select_result["selected"]
            logger.info(f"Dynamically selected composition: {compose_name} (score: {select_result['score']})")
            
            # Store selection metadata
            data["_composition_selection"] = {
                "selected": compose_name,
                "score": select_result["score"],
                "reasons": select_result["reasons"],
                "suggestions": select_result.get("suggestions", [])
            }
        else:
            return error_response(
                f"Dynamic composition selection failed: {select_result.get('error', 'Unknown error')}",
                context=context
            )
    else:
        # Use specified component
        compose_name = component_name
    
    # Always render component to manifest
    agent_config = {}
    system_prompt = None
    
    if compose_name:
        logger.debug(f"Using render_component_to_agent_manifest for: {compose_name}")
        # Prepare variables for composition
        comp_vars = {
            "agent_id": agent_id,
            "enable_tools": data.get("enable_tools", False)
        }
        
        # Add variables from spawn data (new unified approach)
        if "variables" in data:
            comp_vars.update(data["variables"])
        
        # Add any additional context from data
        if "context" in data:
            comp_vars.update(data["context"])
        
        try:
            # Use the proper utility to render component to agent manifest
            manifest_data = render_component_to_agent_manifest(
                component_name=compose_name,
                variables=comp_vars,
                agent_id=agent_id
            )
            
            # Set up component data from manifest
            component_data = manifest_data
            security_profile = manifest_data.get("security_profile")
            
            # Extract system_prompt from manifest if present
            system_prompt = None
            if manifest_data and 'components' in manifest_data:
                for component in manifest_data.get('components', []):
                    if component.get('name') == 'generated_content':
                        inline_data = component.get('inline', {})
                        system_prompt = inline_data.get('system_prompt')
                        if system_prompt:
                            logger.debug(f"Extracted system_prompt from manifest for agent {agent_id}")
                            break
            
        except Exception as e:
            logger.error(f"Failed to render component to manifest: {e}")
            return error_response(
                f"Failed to render component {compose_name}: {str(e)}",
                context=context
            )
        
    # Process component data from manifest
    else:
        return error_response(
            "No component specified for agent spawn",
            context=context
        )
    
    # Get permission profile from spawn request first (can override component)
    requested_permission_profile = data.get("permission_profile", "standard")
    
    # We always have component_data from manifest rendering
    if component_data:
        # Validate and resolve capabilities for agent spawn
        enforcer = get_capability_enforcer()
        
        # Get capabilities from metadata or directly from component (handle both formats)
        if isinstance(component_data, dict) and "metadata" in component_data:
            # New format: capabilities in metadata
            component_capabilities = component_data.get("metadata", {}).get("capabilities", {})
        else:
            # Legacy format: capabilities directly on component
            component_capabilities = component_data.get("capabilities", {})
        
        # Use requested permission profile if provided, otherwise fall back to component's security_profile
        effective_profile = requested_permission_profile if data.get("permission_profile") else security_profile
        
        # Validate and resolve capabilities for agent spawn
        resolved = enforcer.validate_agent_spawn(component_capabilities, effective_profile)
        allowed_events = resolved["allowed_events"]
        allowed_claude_tools = resolved["allowed_claude_tools"]
        expanded_capabilities = resolved["expanded_capabilities"]
        
        logger.info(
            f"Resolved capabilities for agent {agent_id}",
            capabilities=expanded_capabilities,
            event_count=len(allowed_events),
            claude_tool_count=len(allowed_claude_tools)
        )
        
        # Extract config from component
        agent_config = {
            "model": component_data.get("model", config.completion_default_model),
            "role": component_data.get("role", "assistant"),
            "enable_tools": component_data.get("enable_tools", False),
            "expanded_capabilities": expanded_capabilities,
            "allowed_events": allowed_events,
            "allowed_claude_tools": allowed_claude_tools
        }
        
        logger.debug("Successfully processed component manifest")
    
    # Override with provided config
    if "config" in data:
        agent_config.update(data["config"])
    
    # Set up permissions and sandbox
    permission_profile = requested_permission_profile
    sandbox_config = data.get("sandbox_config", {})
    sandbox_dir = None
    
    # Get permissions from component if available (either from composition result or in-memory data)
    if "compose_result" in locals() and compose_result and compose_result.get("status") == "success":
        composition = compose_result.get("composition", {})
        metadata = composition.get("metadata", {})
        
        # Check for security_profile first (v3 compositional capability system)
        if "security_profile" in metadata:
            permission_profile = metadata["security_profile"]
            logger.info(f"Using security_profile {permission_profile} from composed component")
        # Fall back to legacy permissions dict
        elif "permissions" in metadata:
            profile_perms = metadata.get("permissions", {})
            if "profile" in profile_perms:
                permission_profile = profile_perms["profile"]
        if "sandbox" in metadata:
            sandbox_config.update(metadata["sandbox"])
    elif "component_data" in locals() and component_data:
        # Use permission data from in-memory component if available
        if "security_profile" in component_data:
            permission_profile = component_data["security_profile"]
            logger.info(f"Using security_profile {permission_profile} from in-memory component")
        # Fall back to legacy permissions dict
        elif "permissions" in component_data:
            component_perms = component_data.get("permissions", {})
            if "profile" in component_perms:
                permission_profile = component_perms["profile"]
        if "sandbox" in component_data:
            sandbox_config.update(component_data["sandbox"])
    
    # Set agent permissions
    if event_emitter:
        perm_result = await event_emitter("permission:set_agent", {
            "agent_id": agent_id,
            "profile": permission_profile,
            "overrides": data.get("permission_overrides", {})
        }, propagate_agent_context(context))
        
        perm_result = unwrap_list_response(perm_result)
        
        if perm_result and "error" in perm_result:
            logger.error(f"Failed to set permissions: {perm_result['error']}")
            # Use restricted permissions as fallback
            permission_profile = "restricted"
    
    # Create sandbox
    if event_emitter:
        sandbox_result = await event_emitter("sandbox:create", {
            "agent_id": agent_id,
            "config": sandbox_config
        }, propagate_agent_context(context))
        
        sandbox_result = unwrap_list_response(sandbox_result)
        
        if sandbox_result and "sandbox" in sandbox_result:
            sandbox_dir = sandbox_result["sandbox"]["path"]
            logger.info(f"Created sandbox for agent {agent_id}: {sandbox_dir}")
        else:
            logger.warning(f"Failed to create sandbox for agent {agent_id}")
    
    # Extract metadata to store in state system
    metadata = data.get("metadata", {})
    
    # Extract originator context from data for event streaming
    originator_context = data.get("context", {}).get("_originator")
    
    # Create MCP config for agent if MCP is enabled
    mcp_config_path = None
    if config.mcp_enabled:
        try:
            # Get current conversation ID or generate one
            conversation_id = data.get("conversation_id") or f"conv_{uuid.uuid4().hex[:8]}"
            
            # Get agent permissions (already fetched above)
            agent_permissions = {
                "profile": permission_profile,
                "allowed_tools": agent_config.get("tools", []),
                "capabilities": agent_config.get("capabilities", [])
            }
            
            mcp_config_path = mcp_config_manager.create_agent_config(
                agent_id=agent_id,
                conversation_id=conversation_id,
                permissions=agent_permissions
            )
            
            logger.info(f"Created MCP config for agent {agent_id} at {mcp_config_path}")
        except Exception as e:
            logger.error(f"Failed to create MCP config for agent {agent_id}: {e}")
            # Continue without MCP - not a fatal error
    
    # Extract context from spawn data
    context_data = data.get('context', {})
    parent_agent_id = context_data.get('parent_agent_id')
    event_subscription_level = context_data.get('event_subscription_level', 1)
    
    # Create agent info
    agent_info = {
        "agent_id": agent_id,
        "component": compose_name,
        "composition": compose_name,
        "config": agent_config,
        "status": "initializing",
        "created_at": format_for_logging(),
        # NOTE: session_id removed - agents have no awareness of sessions
        # All session management is handled by the completion system
        "message_queue": asyncio.Queue(),
        "permission_profile": permission_profile,
        "sandbox_dir": sandbox_dir,
        "sandbox_uuid": str(uuid.uuid4()),  # Persistent sandbox identifier
        "mcp_config_path": str(mcp_config_path) if mcp_config_path else None,
        "conversation_id": conversation_id if 'conversation_id' in locals() else None,
        # Metadata will be stored in state system, not in memory
        "metadata_namespace": f"metadata:agent:{agent_id}",
        # Originator context for event streaming
        "originator_context": originator_context,
        # Agent context tracking
        "parent_agent_id": parent_agent_id,
        "event_subscription_level": event_subscription_level
    }
    
    # Store system_prompt if extracted from manifest
    if 'system_prompt' in locals() and system_prompt:
        agent_info['system_prompt'] = system_prompt
    
    # Register agent
    agents[agent_id] = agent_info
    
    # Agent entity creation is now handled by transformer listening to agent:spawned event
    # This follows the source event pattern - services emit what happened, transformers handle downstream
    
    # Store metadata in state system namespace
    if metadata and event_emitter:
        metadata_result = await event_emitter("state:set", {
            "namespace": f"metadata:agent:{agent_id}",
            "data": metadata
        }, propagate_agent_context(context))
        if metadata_result and isinstance(metadata_result, list):
            metadata_result = metadata_result[0] if metadata_result else {}
        
        if metadata_result.get("error"):
            logger.warning(f"Failed to store agent metadata: {metadata_result}")
        else:
            logger.debug(f"Stored metadata for agent {agent_id}")
    
    # Relationship creation removed - handle via orchestration patterns
    
    # Start agent thread
    agent_task = create_tracked_task("agent_service", run_agent_thread(agent_id), task_name=f"agent_thread_{agent_id}")
    agent_threads[agent_id] = agent_task
    
    logger.info(f"Created agent thread {agent_id} with composition {compose_name}")
    
    # Observation patterns removed - handle via orchestration
    
    # Send initial context - system_prompt and/or interaction_prompt
    initial_content = None
    interaction_prompt = data.get("prompt")
    system_prompt = agent_info.get('system_prompt')
    
    # Determine what to send as initial context
    if system_prompt and interaction_prompt:
        # Combine system prompt with interaction
        initial_content = f"{system_prompt}\n\n{interaction_prompt}"
        initial_role = "user"  # Combined content uses user role
    elif system_prompt:
        # Just system prompt from component
        initial_content = system_prompt
        initial_role = "system"  # Pure system prompt uses system role
    elif interaction_prompt:
        # Just interaction prompt from spawn request
        initial_content = interaction_prompt
        initial_role = "user"
    
    if initial_content and event_emitter:
        logger.info(f"Sending initial context to agent {agent_id} (role: {initial_role})")
        
        # Send as direct message - simpler and more reliable than composition:agent_context
        initial_result = await event_emitter("agent:send_message", {
            "agent_id": agent_id,
            "message": {
                "role": initial_role,
                "content": initial_content
            }
        }, propagate_agent_context(context))
        
        if initial_result and isinstance(initial_result, list):
            initial_result = initial_result[0] if initial_result else {}
        
        logger.info(f"Initial context sent to agent {agent_id}: {initial_result.get('status', 'unknown')}")
        
        if system_prompt:
            logger.debug(f"System prompt from component applied to agent {agent_id}")
    
    # Emit agent:spawned event - transformers will handle downstream notifications
    if event_emitter:
        spawn_data = {
            "agent_id": agent_id,
            "component": compose_name,
            "composition": compose_name,
            "sandbox_uuid": agent_info["sandbox_uuid"],
            "sandbox_dir": sandbox_dir,
            "permission_profile": permission_profile,
            "capabilities": expanded_capabilities,
            "created_at": timestamp_utc(),
            "spawned_by": context.get("_agent_id") if context else "system",
            # Include config values needed for restoration
            "model": agent_config.get("model", config.completion_default_model),
            "enable_tools": agent_config.get("enable_tools", False),
            "allowed_events": agent_config.get("allowed_events", []),
            "allowed_claude_tools": agent_config.get("allowed_claude_tools", []),
            "mcp_config_path": agent_info.get("mcp_config_path")
        }
        
        # Include parent agent context if present
        if parent_agent_id:
            spawn_data.update({
                "parent_agent_id": parent_agent_id
            })
        
        await agent_emit_event(agent_id, "agent:spawned", spawn_data, propagate_agent_context(context))
        logger.info(f"Emitted agent:spawned event for {agent_id}")
    
    return event_response_builder(
        {
            "agent_id": agent_id,
            "status": "created",
            "component": compose_name,
            "composition": compose_name,
            # session_id intentionally omitted - managed by completion system
            "config": agent_config,
            "metadata_namespace": f"metadata:agent:{agent_id}"
        },
        context=context
    )


@event_handler("agent:terminate", schema=AgentTerminateData)
async def handle_terminate_agent(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Terminate agents - supports both single and bulk operations."""
    
    # Determine which agents to terminate
    target_agent_ids = await _resolve_target_agents(data)
    
    if not target_agent_ids:
        return error_response(
            "No agents found matching criteria",
            context=context
        )
    
    dry_run = data.get("dry_run", False)
    force = data.get("force", False)
    
    if dry_run:
        return event_response_builder(
            {
                "dry_run": True,
                "agents_to_terminate": target_agent_ids,
                "count": len(target_agent_ids)
            },
            context=context
        )
    
    # Terminate each agent
    terminated_agents = []
    failed_agents = []
    
    for agent_id in target_agent_ids:
        try:
            result = await _terminate_single_agent(agent_id, force, context)
            if result["status"] == "terminated":
                terminated_agents.append(agent_id)
            else:
                failed_agents.append({"agent_id": agent_id, "error": result.get("error")})
        except Exception as e:
            logger.error(f"Failed to terminate agent {agent_id}: {e}")
            failed_agents.append({"agent_id": agent_id, "error": str(e)})
    
    logger.info(f"Bulk termination complete: {len(terminated_agents)} terminated, {len(failed_agents)} failed")
    
    # Always return bulk format using batch operation response
    failed_errors = {item["agent_id"]: item["error"] for item in failed_agents if "error" in item}
    return batch_operation_response(
        terminated_agents,
        [item["agent_id"] for item in failed_agents],
        "terminate",
        context,
        errors=failed_errors if failed_errors else None
    )


async def _resolve_target_agents(data: AgentTerminateData) -> List[str]:
    """Resolve which agents to terminate based on criteria."""
    target_agent_ids = []
    
    # Single agent
    if "agent_id" in data:
        agent_id = data["agent_id"]
        if agent_id in agents:
            target_agent_ids.append(agent_id)
    
    # Multiple agents
    if "agent_ids" in data:
        for agent_id in data["agent_ids"]:
            if agent_id in agents:
                target_agent_ids.append(agent_id)
    
    # Pattern matching
    if "pattern" in data:
        pattern = data["pattern"]
        for agent_id in agents:
            if fnmatch.fnmatch(agent_id, pattern):
                target_agent_ids.append(agent_id)
    
    # Age-based termination
    if "older_than_hours" in data:
        hours = float(data["older_than_hours"])  # Ensure it's a float
        cutoff_time = time.time() - (hours * 3600)
        
        for agent_id, agent_info in agents.items():
            created_at_str = agent_info.get("created_at")
            if created_at_str:
                try:
                    # Parse ISO timestamp
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    created_timestamp = created_at.timestamp()
                    if created_timestamp < cutoff_time:
                        target_agent_ids.append(agent_id)
                except Exception as e:
                    logger.warning(f"Failed to parse timestamp for agent {agent_id}: {e}")
    
    # Component-based termination
    if "component" in data or "profile" in data:  # Support legacy
        target_component = data.get("component") or data.get("profile")
        for agent_id, agent_info in agents.items():
            agent_component = agent_info.get("component") or agent_info.get("profile")
            if agent_component == target_component:
                target_agent_ids.append(agent_id)
    
    # All agents (dangerous!)
    if data.get("all"):
        target_agent_ids.extend(list(agents.keys()))
    
    # Remove duplicates while preserving order
    return list(dict.fromkeys(target_agent_ids))


async def _terminate_single_agent(agent_id: str, force: bool = False, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Terminate a single agent."""
    if agent_id not in agents:
        return {"error": f"Agent {agent_id} not found"}
    
    agent_info = agents[agent_id]
    
    # Cancel agent thread if running
    if agent_id in agent_threads:
        agent_threads[agent_id].cancel()
        del agent_threads[agent_id]
    
    # Update status
    agent_info["status"] = "terminated"
    agent_info["terminated_at"] = format_for_logging()
    
    # Emit agent:terminated event - transformers will handle downstream cleanup
    if event_emitter:
        # Prepare termination data for the event
        termination_data = {
            "agent_id": agent_id,
            "force": force,
            "terminated_at": time.time(),  # numeric for DB storage
            "terminated_at_iso": timestamp_utc(),  # ISO for display
            "component": agent_info.get("component") or agent_info.get("profile"),  # Support legacy
            "sandbox_dir": agent_info.get("sandbox_dir")
        }
        
        # Emit the source event that transformers will route
        await agent_emit_event(agent_id, "agent:terminated", termination_data, propagate_agent_context(context))
        logger.info(f"Emitted agent:terminated event for {agent_id}")
    
    # Clean up MCP config if present (local operation, not event-driven)
    if config.mcp_enabled:
        try:
            mcp_config_manager.cleanup_agent_config(agent_id)
            logger.debug(f"Cleaned up MCP config for agent {agent_id}")
        except Exception as e:
            logger.error(f"Failed to clean up MCP config for agent {agent_id}: {e}")
    
    # Remove agent from active agents dictionary (local operation)
    del agents[agent_id]
    logger.info(f"Agent {agent_id} terminated and removed from active agents")
    
    logger.debug(f"Terminated agent {agent_id}")
    
    return {
        "agent_id": agent_id,
        "status": "terminated"
    }


@event_handler("agent:restart", schema=AgentRestartData)
async def handle_restart_agent(data: AgentRestartData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Restart an agent."""
    agent_id = data["agent_id"]  # Validated by enhanced event_handler
    
    # Get current agent info
    agent_info = agents[agent_id].copy()
    
    # Terminate existing
    terminate_result = await handle_terminate_agent({"agent_id": agent_id}, context)
    if "error" in terminate_result:
        return terminate_result
    
    # Spawn new with same config
    # Only pass agent_id and component - completion system handles session continuity
    spawn_data = {
        "agent_id": agent_id,
        "component": agent_info.get("component") or agent_info.get("profile")  # Support legacy
        # config and session_id omitted - component contains config, completion tracks sessions
    }
    
    return await handle_spawn_agent(spawn_data, context)


async def run_agent_thread(agent_id: str):
    """Run agent thread that handles messages and coordination."""
    if agent_id not in agents:
        logger.error(f"Agent {agent_id} not found")
        return
    
    agent_info = agents[agent_id]
    message_queue = agent_info.get("message_queue")
    
    try:
        # Mark agent as ready
        agent_info["status"] = "ready"
        logger.info(f"Agent thread {agent_id} started")
        
        # Process messages
        while True:
            try:
                # Wait for message with timeout
                message = await asyncio.wait_for(message_queue.get(), timeout=60.0)
                
                if message.get("type") == "terminate":
                    break
                
                # Handle different message types
                await handle_agent_message(agent_id, message)
                
            except asyncio.TimeoutError:
                # Periodic health check
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in agent {agent_id} thread: {e}")
                
    except Exception as e:
        logger.error(f"Agent thread {agent_id} crashed: {e}")
        agent_info["status"] = "failed"
        agent_info["error"] = str(e)
    finally:
        agent_info["status"] = "stopped"
        logger.info(f"Agent thread {agent_id} stopped")


async def handle_agent_message(agent_id: str, message: Dict[str, Any]):
    """Handle a message sent to an agent."""
    agent_info = agents.get(agent_id)
    if not agent_info:
        return
    
    msg_type = message.get("type")
    
    if msg_type == "completion":
        # Forward to completion service using new async interface
        prompt = message.get("prompt", "")
        if prompt and event_emitter:
            # Use resolved tool lists from agent config (no need to query permissions again)
            agent_config = agent_info.get("config", {})
            permissions = {
                "allowed_tools": agent_config.get("allowed_claude_tools", []),
                "profile": agent_info.get("permission_profile", "standard")
            }
            
            logger.debug(
                f"Agent {agent_id} completion with tools",
                claude_tools=len(permissions["allowed_tools"]),
                ksi_events=len(agent_config.get("allowed_events", [])),
                profile=permissions["profile"]
            )
            
            # Prepare completion request with permission context
            completion_data = {
                "messages": [{"role": "user", "content": prompt}],
                "agent_id": agent_id,
                "originator_id": agent_id,  # Use agent_id as originator_id
                # session_id removed - completion system tracks this
                # model removed - agent session already has model from spawn
                "priority": "normal",
                "request_id": f"{agent_id}_{message.get('request_id', uuid.uuid4().hex[:8])}"
            }
            
            # Always add KSI parameters via extra_body for LiteLLM
            # This ensures all agent-specific context is passed through
            ksi_body = {
                "agent_id": agent_id,
                "sandbox_dir": agent_info.get("sandbox_dir"),
                "sandbox_uuid": agent_info.get("sandbox_uuid"),  # Pass sandbox UUID
                "permissions": permissions,
                "allowed_events": agent_config.get("allowed_events", [])  # Add resolved events
                # session_id removed - completion system manages
            }
            
            # Only include mcp_config_path if it's actually set
            mcp_path = agent_info.get("mcp_config_path")
            if mcp_path:
                ksi_body["mcp_config_path"] = mcp_path
                
            completion_data["extra_body"] = {"ksi": ksi_body}
            logger.debug(f"Agent {agent_id} sending completion with MCP config: {agent_info.get('mcp_config_path')}")
            
            # Session continuity is now handled automatically by completion service
            # Mark this as agent-originated for observation
            completion_result = await agent_emit_event(agent_id, "completion:async", completion_data, {
                "_agent_id": agent_id  # Agent is the originator
            })
            
            # Note: route_to_originator is now handled automatically in agent_emit_event
    
    # Remove tournament-specific handling - this belongs in orchestration patterns
    # Agents should be domain-agnostic infrastructure
    
    elif msg_type == "direct_message":
        # Inter-agent messaging
        target_agent = message.get("to")
        if target_agent and target_agent in agents:
            target_queue = agents[target_agent].get("message_queue")
            if target_queue:
                await target_queue.put({
                    "type": "message",
                    "from": agent_id,
                    "content": message.get("content"),
                    "timestamp": format_for_logging()
                })
    
    elif msg_type == "broadcast":
        # Broadcast to all agents
        content = message.get("content")
        for other_id, other_info in agents.items():
            if other_id != agent_id:
                other_queue = other_info.get("message_queue")
                if other_queue:
                    await other_queue.put({
                        "type": "broadcast",
                        "from": agent_id,
                        "content": content,
                        "timestamp": format_for_logging()
                    })


# Agent registry handlers
@event_handler("agent:register", schema=AgentRegisterData, require_agent=False)
async def handle_register_agent(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Register an external agent."""
    agent_id = data.get("agent_id")
    agent_info = data.get("info", {})
    
    if not agent_id:
        return error_response("agent_id required", context)
    
    # Create registration info
    registration = {
        "agent_id": agent_id,
        "registered_at": format_for_logging(),
        "status": "registered",
        **agent_info
    }
    
    agents[agent_id] = registration
    
    logger.info(f"Registered agent {agent_id}")
    
    return event_response_builder({
        "agent_id": agent_id,
        "status": "registered"
    }, context)


@event_handler("agent:unregister", schema=AgentUnregisterData)
async def handle_unregister_agent(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Unregister an agent."""
    agent_id = data.get("agent_id")
    
    if not agent_id:
        return error_response("agent_id required", context)
    
    if agent_id in agents:
        del agents[agent_id]
        logger.info(f"Unregistered agent {agent_id}")
        return event_response_builder({"status": "unregistered"}, context)
    
    return entity_not_found_response("agent", agent_id, context)


@event_handler("agent:list", schema=AgentListData, require_agent=False)
async def handle_list_agents(data: AgentListData, context: Optional[Dict[str, Any]] = None):
    """List registered agents."""
    filter_status = data.get("status")
    include_metadata = data.get("include_metadata", False)
    
    agent_list = []
    for agent_id, info in agents.items():
        if filter_status and info.get("status") != filter_status:
            continue
        
        agent_entry = {
            "agent_id": agent_id,
            "status": info.get("status"),
            "component": info.get("component") or info.get("profile"),  # Support legacy
            "created_at": info.get("created_at"),
            "metadata_namespace": f"metadata:agent:{agent_id}"
        }
        
        # Optionally fetch metadata from state system
        if include_metadata and event_emitter:
            metadata_result = await agent_emit_event(agent_id, "state:get", {
                "namespace": f"metadata:agent:{agent_id}"
            }, propagate_agent_context(context))
            metadata_result = unwrap_list_response(metadata_result)
            
            if metadata_result and "data" in metadata_result:
                agent_entry["metadata"] = metadata_result["data"]
            
        agent_list.append(agent_entry)
    
    return {
        "agents": agent_list,
        "count": len(agent_list)
    }


@event_handler("agent:info", schema=AgentInfoData)
async def handle_agent_info(data: AgentInfoData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get comprehensive information about an agent using graph traversal."""
    agent_id = data["agent_id"]  # Validated by enhanced event_handler
    include = data.get("include", ["state", "identity"])
    depth = min(data.get("depth", 1), 3)  # Cap at 3 levels
    event_limit = data.get("event_limit", 10)
    message_limit = data.get("message_limit", 10)
    
    # Start building comprehensive info
    agent_info = agents[agent_id]
    result = {
        "agent_id": agent_id,
        "status": agent_info.get("status"),
        "component": agent_info.get("component") or agent_info.get("profile"),  # Support legacy
        "composition": agent_info.get("composition"),
        "created_at": agent_info.get("created_at"),
        "sandbox_dir": agent_info.get("sandbox_dir"),
        "sandbox_uuid": agent_info.get("sandbox_uuid"),
        "permission_profile": agent_info.get("permission_profile"),
        "mcp_config_path": agent_info.get("mcp_config_path"),
        "conversation_id": agent_info.get("conversation_id")
    }
    
    # Add config information
    if agent_info.get("config"):
        result["config"] = agent_info["config"]  # Include full config with model
        result["capabilities"] = agent_info["config"].get("capabilities", [])
        result["expanded_capabilities"] = agent_info["config"].get("expanded_capabilities", [])
    
    # Include state entity information
    if "state" in include:
        if event_emitter:
            try:
                logger.debug(f"Fetching state entity for agent {agent_id}")
                state_result = await event_emitter("state:entity:get", {
                    "id": agent_id,
                    "include": ["properties", "relationships"]
                })
                # Handle list-wrapped results
                if isinstance(state_result, list) and state_result:
                    state_result = state_result[0]
                logger.debug(f"State result for {agent_id}: {state_result}")
                if state_result and state_result.get("status") == "success":
                    result["state_entity"] = state_result
            except Exception as e:
                logger.warning(f"Failed to get state entity for {agent_id}: {e}")
        else:
            logger.warning(f"Cannot fetch state entity - event_emitter is None")
    
    # Include identity
    if "identity" in include and agent_id in identities:
        result["identity"] = identities[agent_id]
    
    # Include relationships via graph traversal
    if "relationships" in include and event_emitter:
        try:
            traverse_result = await event_emitter("state:graph:traverse", {
                "from_id": agent_id,
                "direction": "both",
                "depth": depth,
                "include_entities": True
            })
            # Handle list-wrapped results
            if isinstance(traverse_result, list) and traverse_result:
                traverse_result = traverse_result[0]
            if traverse_result and traverse_result.get("status") == "success":
                result["graph"] = traverse_result.get("graph", {})
                result["traversal_depth"] = depth
        except Exception as e:
            logger.warning(f"Failed to traverse graph for {agent_id}: {e}")
    
    # Include metadata from state system
    if "metadata" in include and event_emitter:
        try:
            metadata_result = await event_emitter("state:get", {
                "namespace": f"metadata:agent:{agent_id}"
            })
            # Handle list-wrapped results
            if isinstance(metadata_result, list) and metadata_result:
                metadata_result = metadata_result[0]
            if metadata_result and metadata_result.get("status") == "success":
                result["metadata"] = metadata_result.get("data", {})
        except Exception as e:
            logger.warning(f"Failed to get metadata for {agent_id}: {e}")
    
    
    # Include recent messages
    if "messages" in include and event_emitter:
        try:
            # Query message entities related to this agent
            msg_result = await event_emitter("state:entity:query", {
                "type": "message",
                "where": {
                    "$or": [
                        {"from_agent": agent_id},
                        {"to_agent": agent_id}
                    ]
                },
                "order_by": "created_at DESC",
                "limit": message_limit,
                "include": ["properties"]
            })
            # Handle list-wrapped results
            if isinstance(msg_result, list) and msg_result:
                msg_result = msg_result[0]
            if msg_result and msg_result.get("status") == "success":
                result["recent_messages"] = msg_result.get("entities", [])
        except Exception as e:
            logger.warning(f"Failed to query messages for {agent_id}: {e}")
    
    # Include observations (subscriptions)
    if "observations" in include and event_emitter:
        try:
            obs_result = await event_emitter("observation:list_subscriptions", {
                "filter_agent_id": agent_id
            })
            # Handle list-wrapped results
            if isinstance(obs_result, list) and obs_result:
                obs_result = obs_result[0]
            if obs_result and obs_result.get("status") == "success":
                result["subscriptions"] = obs_result.get("subscriptions", [])
        except Exception as e:
            logger.warning(f"Failed to get observations for {agent_id}: {e}")
    
    # Include recent events from event log
    if "events" in include and event_emitter:
        try:
            events_result = await event_emitter("event_log:query", {
                "filters": {
                    "_agent_id": agent_id
                },
                "order_by": "timestamp DESC",
                "limit": event_limit
            })
            # Handle list-wrapped results
            if isinstance(events_result, list) and events_result:
                events_result = events_result[0]
            if events_result and events_result.get("status") == "success":
                result["recent_events"] = events_result.get("events", [])
        except Exception as e:
            logger.warning(f"Failed to query events for {agent_id}: {e}")
    
    return event_response_builder(result, context=context)


# Construct-specific handlers removed - use orchestration patterns


# Identity handlers
@event_handler("agent:create_identity", schema=AgentCreateIdentityData, require_agent=False)
async def handle_create_identity(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a new agent identity."""
    agent_id = data.get("agent_id") or f"agent_{uuid.uuid4().hex[:8]}"
    identity_data = data.get("identity", {})
    
    # Create identity
    identity = {
        "agent_id": agent_id,
        "created_at": format_for_logging(),
        "updated_at": format_for_logging(),
        **identity_data
    }
    
    identities[agent_id] = identity
    
    # Save identity to disk
    success = await save_identity(identity_storage_path, agent_id, identity)
    if not success:
        return error_response("Failed to save identity", context)
    
    logger.info(f"Created identity for agent {agent_id}")
    
    return event_response_builder(
        {
            "agent_id": agent_id,
            "status": "created"
        },
        context=context
    )


@event_handler("agent:update_identity", schema=AgentUpdateIdentityData)
async def handle_update_identity(data: AgentUpdateIdentityData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Update an agent identity."""
    agent_id = data["agent_id"]  # Validated by enhanced event_handler
    updates = data.get("updates", {})
    
    if agent_id not in identities:
        return error_response(
            f"Identity for {agent_id} not found",
            context=context
        )
    
    # Update identity
    identities[agent_id].update(updates)
    identities[agent_id]["updated_at"] = format_for_logging()
    
    # Save updated identity to disk
    success = await save_identity(identity_storage_path, agent_id, identities[agent_id])
    if not success:
        return error_response("Failed to save updated identity", context)
    
    logger.info(f"Updated identity for agent {agent_id}")
    
    return event_response_builder(
        {
            "agent_id": agent_id,
            "status": "updated"
        },
        context=context
    )


@event_handler("agent:remove_identity", schema=AgentRemoveIdentityData)
async def handle_remove_identity(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Remove an agent identity."""
    agent_id = data.get("agent_id")
    
    if not agent_id:
        return error_response(
            "agent_id required",
            context=context
        )
    
    if agent_id in identities:
        del identities[agent_id]
        
        # Remove identity file from disk
        await remove_identity(identity_storage_path, agent_id)
            
        logger.info(f"Removed identity for agent {agent_id}")
        return event_response_builder(
            {"status": "removed"},
            context=context
        )
    
    return error_response(
        f"Identity for {agent_id} not found",
        context=context
    )


@event_handler("agent:list_identities", schema=AgentListIdentitiesData, require_agent=False)
async def handle_list_identities(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """List agent identities."""
    identity_list = []
    
    for agent_id, identity in identities.items():
        identity_list.append({
            "agent_id": agent_id,
            "name": identity.get("name", ""),
            "role": identity.get("role", ""),
            "created_at": identity.get("created_at")
        })
    
    return {
        "identities": identity_list,
        "count": len(identity_list)
    }


# Task routing handlers
@event_handler("agent:route_task", schema=AgentRouteTaskData, require_agent=False)
async def handle_route_task(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Route a task to an appropriate agent."""
    # Simple routing: find first available agent
    for agent_id, info in agents.items():
        if info.get("status") == "ready":
            logger.info(f"Routing task to agent {agent_id}")
            return event_response_builder({
                "agent_id": agent_id,
                "status": "routed"
            }, context)
    
    return error_response("No available agents", context)


# Message handling functions
@event_handler("agent:send_message", schema=AgentSendMessageData)
async def handle_send_message(data: AgentSendMessageData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Send a message to an agent."""
    agent_id = data["agent_id"]  # Validated by enhanced event_handler
    message = data.get("message", {})
    
    # Handle case where message comes as a JSON string from CLI
    if isinstance(message, str):
        try:
            # Create a temporary dict to use parse_json_parameter
            temp_data = {"message": message}
            parsed = parse_json_parameter(temp_data, "message", merge_into_data=False)
            if parsed is not None:
                message = parsed
            else:
                return error_response("Invalid message format. Expected JSON object, got string that couldn't be parsed as JSON", context)
        except Exception as e:
            return error_response(f"Invalid message format. Expected JSON object, got string: {e}", context)
    
    # Check if this is a completion message (either format)
    is_completion = False
    prompt = None
    
    # Format 1: {"type": "completion", "prompt": "..."}
    if message.get("type") == "completion" and message.get("prompt"):
        is_completion = True
        prompt = message.get("prompt")
    
    # Format 2: {"role": "user", "content": "..."} - standard chat format
    elif message.get("role") and message.get("content"):
        is_completion = True
        prompt = message.get("content")
    
    # If it's a completion message, emit directly to completion service
    if is_completion and prompt and event_emitter:
        agent_info = agents[agent_id]
        agent_config = agent_info.get("config", {})
        
        # Agents have no awareness of sessions - completion system handles all tracking
        # All subsequent messages after spawn are just user content
        # (Agent prompt was included only in initial message at spawn time)
        
        messages = [{"role": message.get("role", "user"), "content": prompt}]
        
        # Prepare completion request
        completion_data = {
            "messages": messages,
            "agent_id": agent_id,
            "originator_id": agent_id,
            # session_id not included - agents have no session awareness
            # model not included - agent session already has model from spawn
            "priority": "normal",
            "request_id": f"{agent_id}_{message.get('request_id', uuid.uuid4().hex[:8])}"
        }
        
        # Add KSI parameters
        completion_data["extra_body"] = {
            "ksi": {
                "conversation_id": f"agent_conversation_{agent_id}",
                "tools": agent_config.get("allowed_claude_tools", []),
                "agent_id": agent_id,
                "sandbox_dir": agent_info.get("sandbox_dir"),
                "sandbox_uuid": agent_info.get("sandbox_uuid"),  # Pass sandbox UUID
                "construct_id": agent_info.get("construct_id"),
                "agent_role": agent_config.get("role", "assistant"),
                "enable_tools": agent_config.get("enable_tools", True)
            }
        }
        
        # Emit completion event directly
        # Mark this as agent-originated for observation  
        result = await agent_emit_event(agent_id, "completion:async", completion_data, 
                                    propagate_agent_context(context))
        
        # Handle list response format
        if result and isinstance(result, list):
            result = result[0] if result else {}
        
        # Agents have no awareness of sessions - completion system handles everything
        
        return event_response_builder({
            "status": "sent_to_completion", 
            "agent_id": agent_id,
            "request_id": result.get("request_id") if result else None
        }, context)
    
    # For non-completion messages, use the queue as before
    queue = agents[agent_id].get("message_queue")
    if queue:
        await queue.put(message)
        return event_response_builder({"status": "sent", "agent_id": agent_id}, context)
    
    return error_response("Agent message queue not available", context)


@event_handler("agent:broadcast", schema=AgentBroadcastData, require_agent=False)
async def handle_broadcast(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Broadcast a message to all agents."""
    message = data.get("message", {})
    sender = data.get("sender", "system")
    
    sent_count = 0
    for agent_id, agent_info in agents.items():
        queue = agent_info.get("message_queue")
        if queue:
            await queue.put({
                "type": "broadcast",
                "from": sender,
                **message
            })
            sent_count += 1
    
    return event_response_builder({
        "status": "broadcast",
        "agents_reached": sent_count,
        "total_agents": len(agents)
    }, context)


# Dynamic composition handlers
@event_handler("agent:update_composition", schema=AgentUpdateCompositionData)
async def handle_update_composition(data: AgentUpdateCompositionData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Handle agent composition update request."""
    agent_id = data["agent_id"]  # Validated by enhanced event_handler
    new_composition = data.get("new_composition")
    reason = data.get("reason", "Adaptation required")
    
    if not new_composition:
        return error_response("new_composition required", context)
    
    # Check if agent can self-modify
    agent_info = agents[agent_id]
    current_config = agent_info.get("config", {})
    
    if not event_emitter:
        return error_response("Event emitter not available", context)
    
    # First, check if current composition allows modification
    current_comp = agent_info.get("composition", agent_info.get("component", agent_info.get("profile")))
    if current_comp:
        # Get composition metadata
        comp_result = await agent_emit_event(agent_id, "composition:get", {
            "name": current_comp
        }, propagate_agent_context(context))
        
        if comp_result and isinstance(comp_result, list):
            comp_result = comp_result[0] if comp_result else {}
        
        if comp_result and comp_result.get("status") == "success":
            metadata = comp_result["composition"].get("metadata", {})
            if not metadata.get("self_modifiable", False):
                return error_response("Current composition does not allow self-modification", context, {"status": "denied"})
    
    # Compose new component
    compose_result = await agent_emit_event(agent_id, "composition:compose", {
        "name": new_composition,
        "variables": {
            "agent_id": agent_id,
            "previous_role": current_config.get("role"),
            "adaptation_reason": reason
        }
    }, propagate_agent_context(context))
    
    if compose_result and isinstance(compose_result, list):
        compose_result = compose_result[0] if compose_result else {}
    
    if compose_result and compose_result.get("status") == "success":
        new_profile = compose_result["composition"]
        
        # Update agent configuration
        agent_info["config"] = {
            "model": new_profile.get("model", config.completion_default_model),
            "capabilities": new_profile.get("capabilities", []),
            "role": new_profile.get("role", "assistant"),
            "enable_tools": new_profile.get("enable_tools", False),
            "tools": new_profile.get("tools", [])
        }
        agent_info["composition"] = new_composition
        agent_info["composition_history"] = agent_info.get("composition_history", [])
        agent_info["composition_history"].append({
            "timestamp": format_for_logging(),
            "from": current_comp,
            "to": new_composition,
            "reason": reason
        })
        
        # Notify agent of update via message queue
        queue = agent_info.get("message_queue")
        if queue:
            await queue.put({
                "type": "composition_updated",
                "new_composition": new_composition,
                "new_config": agent_info["config"],
                # Agent prompt now handled by composition:agent_context
            })
        
        logger.info(f"Agent {agent_id} updated composition to {new_composition}")
        
        return event_response_builder({
            "status": "updated",
            "agent_id": agent_id,
            "new_composition": new_composition,
            "new_capabilities": agent_info["config"]["capabilities"]
        }, context)
    else:
        return error_response(f"Failed to compose new component: {compose_result.get('error', 'Unknown error')}", context, {"status": "failed"})


@event_handler("agent:discover_peers", schema=AgentDiscoverPeersData, require_agent=False)
async def handle_discover_peers(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Discover other agents and their capabilities."""
    requesting_agent = data.get("agent_id")
    capability_filter = data.get("capabilities", [])
    role_filter = data.get("roles", [])
    
    discovered = []
    
    for agent_id, agent_info in agents.items():
        if agent_id == requesting_agent:
            continue  # Skip self
        
        agent_config = agent_info.get("config", {})
        agent_caps = agent_config.get("capabilities", [])
        agent_role = agent_config.get("role")
        
        # Apply filters
        if capability_filter:
            if not any(cap in agent_caps for cap in capability_filter):
                continue
        
        if role_filter:
            if agent_role not in role_filter:
                continue
        
        discovered.append({
            "agent_id": agent_id,
            "role": agent_role,
            "capabilities": agent_caps,
            "composition": agent_info.get("composition"),
            "status": agent_info.get("status", "active")
        })
    
    return event_response_builder({
        "status": "success",
        "requesting_agent": requesting_agent,
        "discovered_count": len(discovered),
        "peers": discovered
    }, context)


@event_handler("agent:negotiate_roles", schema=AgentNegotiateRolesData, require_agent=False)
async def handle_negotiate_roles(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Coordinate role negotiation between agents."""
    participants = data.get("participants", [])
    negotiation_type = data.get("type", "collaborative")
    negotiation_context = data.get("context", {})  # Renamed to avoid conflict
    
    if not participants or len(participants) < 2:
        return error_response("At least 2 participants required for negotiation", context)
    
    # Verify all participants exist
    missing_agents = [aid for aid in participants if aid not in agents]
    if missing_agents:
        return error_response(f"Agents not found: {', '.join(missing_agents)}", context)
    
    # Create negotiation session
    negotiation_id = f"neg_{uuid.uuid4().hex[:8]}"
    
    # Send negotiation request to all participants
    for agent_id in participants:
        agent_info = agents[agent_id]
        queue = agent_info.get("message_queue")
        if queue:
            await queue.put({
                "type": "role_negotiation",
                "negotiation_id": negotiation_id,
                "participants": participants,
                "negotiation_type": negotiation_type,
                "context": negotiation_context,
                "your_current_role": agent_info.get("config", {}).get("role"),
                "your_capabilities": agent_info.get("config", {}).get("capabilities", [])
            })
    
    logger.info(f"Started role negotiation {negotiation_id} with {len(participants)} agents")
    
    return event_response_builder({
        "status": "initiated",
        "negotiation_id": negotiation_id,
        "participants": participants,
        "type": negotiation_type
    }, context)


@event_handler("agent:needs_continuation", require_agent=False)
async def handle_agent_needs_continuation(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Handle agent continuation requests for step-wise execution."""
    # Extract agent_id from context
    ksi_context = data.get("_ksi_context", {})
    agent_id = ksi_context.get("_agent_id") if ksi_context else None
    
    # Validate agent exists
    if not agent_id:
        return error_response("No agent_id in continuation request", context)
    
    if agent_id not in agents:
        return entity_not_found_response("agent", agent_id, context)
    
    agent_info = agents[agent_id]
    queue = agent_info.get("message_queue")
    
    if not queue:
        return error_response(f"No message queue for agent {agent_id}", context)
    
    # Queue a continuation message
    reason = data.get("reason", "Continue with next step")
    await queue.put({
        "type": "completion",
        "prompt": f"Continue with: {reason}",
        "request_id": f"cont_{uuid.uuid4().hex[:8]}",
        "timestamp": timestamp_utc()
    })
    
    logger.info(f"Queued continuation for agent {agent_id}: {reason}")
    
    return event_response_builder({
        "status": "queued",
        "agent_id": agent_id,
        "reason": reason
    }, context)


# KSI System Integration Event Handlers (Phase 4)

class AgentSpawnFromComponentData(TypedDict):
    """Spawn agent from component."""
    component: Required[str]  # Component name - matches relative path without extension (e.g., "components/agents/hello_agent" for components/agents/hello_agent.md)
    agent_id: NotRequired[str]  # Agent ID (auto-generated if not provided)
    variables: NotRequired[Dict[str, Any]]  # Variables for component rendering
    prompt: NotRequired[str]  # Initial prompt
    context: NotRequired[Dict[str, Any]]  # Additional context
    model: NotRequired[str]  # Model to use
    enable_tools: NotRequired[bool]  # Enable tool usage
    permission_profile: NotRequired[str]  # Permission profile name
    sandbox_dir: NotRequired[str]  # Sandbox directory
    mcp_config_path: NotRequired[str]  # MCP configuration path
    conversation_id: NotRequired[str]  # Conversation ID
    track_component_usage: NotRequired[bool]  # Track component usage (default: True)
    originator: NotRequired[Dict[str, Any]]  # Originator context for event streaming
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("agent:spawn_from_component", schema=AgentSpawnFromComponentData, require_agent=False)
async def handle_spawn_from_component(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """DEPRECATED: Use agent:spawn instead.
    
    This event is deprecated as of 2025-01-27. The agent:spawn event now supports
    variables directly, making this separate event unnecessary.
    
    Migration:
    - Change event name from 'agent:spawn_from_component' to 'agent:spawn'
    - All parameters remain the same
    """
    logger.warning(
        "agent:spawn_from_component is DEPRECATED. Use agent:spawn instead. "
        "This event will be removed in a future version."
    )
    
    # Forward to the unified spawn handler
    # Remove the track_component_usage field as it's no longer needed
    spawn_data = data.copy()
    spawn_data.pop('track_component_usage', None)
    spawn_data.pop('originator', None)  # Handle differently in new path
    
    return await handle_spawn_agent(spawn_data, context)
    
    # DEPRECATED CODE BELOW - Remove in future version
    return  # Never reached
    try:
        component_name = data['component']
        agent_id = data.get('agent_id', f"agent_{uuid.uuid4().hex[:8]}")
        variables = data.get('variables', {})
        # Add agent_id to variables for template substitution
        variables['agent_id'] = agent_id
        track_usage = data.get('track_component_usage', True)
        
        # Compose component directly for in-memory agent manifest
        if not event_emitter:
            return error_response("Event emitter not available", context)
        
        # Prepare variables for composition
        comp_vars = {
            "agent_id": agent_id,
            "enable_tools": data.get("enable_tools", False)
        }
        comp_vars.update(variables)
        
        # Add any additional context from data
        if "context" in data:
            comp_vars.update(data["context"])
        
        # Create in-memory agent manifest using shared composition utilities
        try:
            manifest_data = render_component_to_agent_manifest(
                component_name=component_name,
                variables=comp_vars,
                agent_id=agent_id
            )
            logger.info(f"Successfully created in-memory agent manifest for {agent_id} from component {component_name}")
        except Exception as e:
            return error_response(f"Failed to create agent manifest from component {component_name}: {e}", context)
        
        # Override with provided config
        if "config" in data:
            manifest_data.update(data["config"])
        
        # Extract originator context for event streaming
        originator = data.get('originator')
        
        # Prepare agent spawn data with in-memory manifest data
        # Create a temporary virtual component name for internal use
        virtual_manifest_name = f"virtual_manifest_{agent_id}"
        
        spawn_data = {
            "agent_id": agent_id,
            "component": virtual_manifest_name,  # Use virtual manifest name
            "prompt": data.get('prompt', ''),
            "context": data.get('context', {}),
            "model": data.get('model'),
            "enable_tools": data.get('enable_tools'),
            "permission_profile": data.get('permission_profile'),
            "sandbox_dir": data.get('sandbox_dir'),
            "mcp_config_path": data.get('mcp_config_path'),
            "conversation_id": data.get('conversation_id'),
            "_in_memory_manifest_data": manifest_data  # Pass manifest data directly
        }
        
        # Add originator to spawn data context for event streaming
        if originator:
            spawn_context = spawn_data.get('context', {})
            spawn_context['_originator'] = originator
            spawn_data['context'] = spawn_context
        
        # Remove None values
        spawn_data = {k: v for k, v in spawn_data.items() if v is not None}
        
        # Create propagated context with originator
        propagated_context = context.copy() if context else {}
        if originator:
            propagated_context['_originator'] = originator
        
        # Spawn agent using the in-memory config
        spawn_result = await handle_spawn_agent(spawn_data, propagated_context)
        
        # Debug: Log the spawn result type and content
        logger.info(f"Spawn result type: {type(spawn_result)}, content: {spawn_result}")
        
        # Handle both dict and non-dict responses
        if isinstance(spawn_result, dict):
            # Check for various success status values
            status = spawn_result.get('status', '')
            if status not in ['success', 'created', 'spawned']:
                # Only treat as error if there's an actual error or failed status
                if status == 'failed' or 'error' in spawn_result:
                    return error_response(f"Failed to spawn agent: {spawn_result.get('error', 'Unknown error')}", context)
            # Extract agent_id from spawn result
            spawned_agent_id = spawn_result.get('agent_id', agent_id)
            if spawned_agent_id:
                agent_id = spawned_agent_id
        else:
            # Non-dict response - assume it's an error or check for specific format
            return error_response(f"Failed to spawn agent: {spawn_result}", context)
        
        # Track component usage if enabled
        if track_usage and event_emitter:
            try:
                await agent_emit_event(agent_id, "composition:track_usage", {
                    "component": component_name,
                    "usage_context": "agent_spawn",
                    "metadata": {
                        "agent_id": agent_id,
                        "manifest_type": "in_memory_component_composition",
                        "variables": comp_vars,
                        "spawn_timestamp": timestamp_utc()
                    }
                }, context)
            except Exception as track_error:
                logger.warning(f"Failed to track component usage: {track_error}")
        
        # Add component metadata to response
        if isinstance(spawn_result, dict):
            response = spawn_result.copy()
            response.update({
                "source_component": component_name,
                "agent_manifest": "in_memory",  # No temp files created
                "variables_used": comp_vars,
                "manifest_type": "in_memory_component_composition",
                "component_metadata": {"created_from_shared_utility": True}
            })
            # Ensure status is set to success if we got here
            if response.get('status') in ['created', 'spawned']:
                response['spawn_status'] = response['status']  # Keep original status
                response['status'] = 'success'  # Set overall status to success
        else:
            response = {
                "status": "success",
                "agent_id": agent_id,
                "spawn_result": spawn_result,
                "source_component": component_name,
                "agent_manifest": "in_memory",
                "variables_used": comp_vars,
                "manifest_type": "in_memory_component_composition",
                "component_metadata": {"created_from_shared_utility": True}
            }
        
        logger.info(f"Spawned agent {agent_id} from component {component_name} using in-memory manifest")
        
        return event_response_builder(response, context)
        
    except Exception as e:
        logger.error(f"Agent spawn from component failed: {e}")
        return error_response(f"Agent spawn from component failed: {e}", context)


class AgentConversationSummaryData(TypedDict):
    """Get agent conversation summary."""
    agent_id: Required[str]  # Agent ID to get summary for
    include_fields: NotRequired[Optional[List[str]]]  # Fields to include in context data
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("agent:conversation_summary", schema=AgentConversationSummaryData)
async def handle_agent_conversation_summary(data: AgentConversationSummaryData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get a summary of an agent's current conversation with resolved contexts.
    
    This uses an internal event to communicate with the completion service,
    maintaining module independence while providing conversation tracking data.
    """
    # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
    agent_id = data["agent_id"]  # Validated by enhanced event_handler
    include_fields = data.get("include_fields")
    
    # Use internal event to get conversation summary from completion service
    # This avoids cross-module imports and maintains architectural boundaries
    summary_result = await agent_emit_event(
        "system",  # System-level event
        "completion:get_conversation_summary",
        {
            "agent_id": agent_id,
            "include_fields": include_fields
        },
        context
    )
    
    # Handle the case where agent_emit_event returns a list
    if isinstance(summary_result, list):
        if len(summary_result) > 0 and isinstance(summary_result[0], dict):
            summary_result = summary_result[0]
        else:
            return error_response("Unexpected response format from completion service", context)
    
    if summary_result.get("status") == "error":
        return error_response(f"Failed to get conversation summary: {summary_result.get('error', 'Unknown error')}", context)
    
    # Return the summary data directly
    return event_response_builder(summary_result, context)


class AgentConversationResetData(TypedDict):
    """Reset agent conversation data structure."""
    agent_id: Required[str]  # Agent ID to reset conversation for
    depth: NotRequired[int]  # Number of contexts to keep (0 = full reset)
    _ksi_context: NotRequired[Dict[str, Any]]  # System metadata


@event_handler("agent:conversation_reset", schema=AgentConversationResetData)
async def handle_agent_conversation_reset(data: AgentConversationResetData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Reset an agent's conversation, optionally keeping recent context.
    
    This allows an agent to start fresh or partially reset their conversation.
    Uses an internal event to communicate with the completion service.
    
    Args:
        agent_id: Agent to reset
        depth: Number of recent contexts to keep (0 = full reset, default)
    """
    agent_id = data["agent_id"]  # Validated by enhanced event_handler
    depth = data.get("depth", 0)  # Default to full reset
    
    # Use internal event to reset conversation in completion service
    reset_result = await agent_emit_event(
        "system",  # System-level event
        "completion:reset_conversation",
        {
            "agent_id": agent_id,
            "depth": depth
        },
        context
    )
    
    # Handle the case where agent_emit_event returns a list
    if isinstance(reset_result, list):
        if len(reset_result) > 0 and isinstance(reset_result[0], dict):
            reset_result = reset_result[0]
        else:
            return error_response("Unexpected response format from completion service", context)
    
    if reset_result.get("status") == "error":
        return error_response(f"Failed to reset conversation: {reset_result.get('error', 'Unknown error')}", context)
    
    # Log the reset for monitoring
    logger.info(
        f"Reset conversation for agent {agent_id}",
        had_session=reset_result.get("had_active_session", False),
        reset_type=reset_result.get("reset_type", "full"),
        contexts_kept=reset_result.get("contexts_kept", 0)
    )
    
    # Return the reset confirmation
    return event_response_builder(reset_result, context)


# Agent State Entity Creation Handler (workaround for transformer issue)
class AgentSpawnedData(TypedDict):
    """Agent spawned event data."""
    agent_id: Required[str]
    component: Required[str]
    sandbox_uuid: Required[str]
    composition: NotRequired[str]
    capabilities: NotRequired[List[str]]
    _ksi_context: NotRequired[Dict[str, Any]]


@event_handler("agent:spawned", schema=AgentSpawnedData)
async def handle_agent_spawned(data: AgentSpawnedData, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create state entity when agent is spawned.
    
    This is a workaround for the transformer not working properly.
    It ensures agents have state entities which are required for the completion system.
    """
    agent_id = data["agent_id"]
    
    # Create state entity for the agent
    entity_result = await event_emitter("state:entity:create", {
        "type": "agent",
        "id": agent_id,
        "properties": {
            "agent_id": agent_id,
            "component": data["component"],
            "composition": data.get("composition", data["component"]),
            "status": "active",
            "sandbox_uuid": data["sandbox_uuid"],
            "capabilities": data.get("capabilities", []),
            "created_at": timestamp_utc()
        }
    }, context)
    
    if isinstance(entity_result, list) and entity_result:
        entity_result = entity_result[0]
    
    logger.info(f"Created state entity for agent {agent_id}")
    
    return event_response_builder({
        "status": "handled",
        "agent_id": agent_id,
        "entity_created": entity_result.get("status") == "success" if entity_result else False
    }, context)


