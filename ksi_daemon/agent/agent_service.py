#!/usr/bin/env python3
"""
Agent Service Module - Event-Based Version

Provides agent management without complex inheritance.
Handles agent lifecycle, identities, and routing through events.
Uses composition service for all profile/configuration needs.
"""

import asyncio
import json
import time
import uuid
import fnmatch
from typing import Any, Dict, TypedDict, List, Literal
from datetime import datetime, timezone
import aiofiles

from typing_extensions import NotRequired, Required

from ksi_common import format_for_logging
from ksi_common.agent_context import propagate_agent_context
from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc
from ksi_daemon.capability_enforcer import get_capability_enforcer
from ksi_daemon.event_system import event_handler, shutdown_handler, get_router
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


# TypedDict definitions for event handlers

class SystemContextData(TypedDict):
    """System context with runtime references."""
    emit_event: NotRequired[Any]  # Event emitter function
    shutdown_event: NotRequired[Any]  # Shutdown event object


class SystemStartupData(TypedDict):
    """System startup configuration."""
    # No specific fields required for agent service
    pass


class SystemReadyData(TypedDict):
    """System ready notification."""
    # No specific fields for agent service
    pass


class SystemShutdownData(TypedDict):
    """System shutdown notification."""
    # No specific fields for shutdown
    pass


class ObservationReadyData(TypedDict):
    """Observation system ready notification."""
    status: NotRequired[str]  # Ready status
    ephemeral: NotRequired[bool]  # Ephemeral subscriptions flag
    message: NotRequired[str]  # Status message


class ObservationRestoredData(TypedDict):
    """Observation subscriptions restored from checkpoint."""
    subscriptions_restored: NotRequired[int]  # Number of subscriptions restored
    from_checkpoint: NotRequired[str]  # Checkpoint timestamp


class CheckpointCollectData(TypedDict):
    """Collect checkpoint data."""
    # No specific fields - collects all agent state
    pass


class CheckpointRestoreData(TypedDict):
    """Restore from checkpoint data."""
    agents: NotRequired[Dict[str, Any]]  # Agent state to restore
    identities: NotRequired[Dict[str, Any]]  # Agent identities to restore


class AgentSpawnData(TypedDict):
    """Spawn a new agent."""
    profile: Required[str]  # Profile name
    agent_id: NotRequired[str]  # Agent ID (auto-generated if not provided)
    # NOTE: session_id removed - managed entirely by completion system
    prompt: NotRequired[str]  # Initial prompt
    context: NotRequired[Dict[str, Any]]  # Additional context
    # Domain-specific fields removed - use metadata instead
    composition: NotRequired[str]  # Composition name
    model: NotRequired[str]  # Model to use
    enable_tools: NotRequired[bool]  # Enable tool usage
    # Agent types removed - handle via orchestration patterns
    permission_profile: NotRequired[str]  # Permission profile name
    sandbox_dir: NotRequired[str]  # Sandbox directory
    mcp_config_path: NotRequired[str]  # MCP configuration path
    conversation_id: NotRequired[str]  # Conversation ID


class AgentTerminateData(TypedDict):
    """Terminate agents - supports both single and bulk operations."""
    agent_id: NotRequired[str]  # Single agent ID to terminate
    agent_ids: NotRequired[List[str]]  # Multiple agent IDs to terminate
    pattern: NotRequired[str]  # Terminate agents matching pattern (e.g., "test_*")
    older_than_hours: NotRequired[float]  # Terminate agents older than X hours
    profile: NotRequired[str]  # Terminate agents with specific profile
    all: NotRequired[bool]  # Terminate all agents (use with caution)
    force: NotRequired[bool]  # Force termination
    dry_run: NotRequired[bool]  # Show what would be terminated without doing it


class AgentRestartData(TypedDict):
    """Restart an agent."""
    agent_id: Required[str]  # Agent ID to restart


class AgentRegisterData(TypedDict):
    """Register an external agent."""
    agent_id: Required[str]  # Agent ID to register
    profile: NotRequired[str]  # Agent profile
    capabilities: NotRequired[List[str]]  # Agent capabilities


class AgentUnregisterData(TypedDict):
    """Unregister an agent."""
    agent_id: Required[str]  # Agent ID to unregister


class AgentListData(TypedDict):
    """List agents."""
    status: NotRequired[str]  # Filter by status


# Construct-specific handlers removed - use orchestration patterns instead
    include_terminated: NotRequired[bool]  # Include terminated agents


class AgentCreateIdentityData(TypedDict):
    """Create a new agent identity."""
    agent_id: Required[str]  # Agent ID
    identity: Required[Dict[str, Any]]  # Identity information


class AgentUpdateIdentityData(TypedDict):
    """Update an agent identity."""
    agent_id: Required[str]  # Agent ID
    identity: Required[Dict[str, Any]]  # Updated identity information


class AgentRemoveIdentityData(TypedDict):
    """Remove an agent identity."""
    agent_id: Required[str]  # Agent ID


class AgentListIdentitiesData(TypedDict):
    """List agent identities."""
    # No specific fields - returns all identities
    pass


class AgentGetIdentityData(TypedDict):
    """Get a specific agent identity."""
    agent_id: Required[str]  # Agent ID


class AgentRouteTaskData(TypedDict):
    """Route a task to an appropriate agent."""
    task: Required[Dict[str, Any]]  # Task to route
    requirements: NotRequired[List[str]]  # Required capabilities
    exclude_agents: NotRequired[List[str]]  # Agents to exclude


class AgentGetCapabilitiesData(TypedDict):
    """Get agent capabilities."""
    agent_id: NotRequired[str]  # Specific agent ID (omit for all agents)


class AgentSendMessageData(TypedDict):
    """Send message to an agent."""
    agent_id: Required[str]  # Target agent ID
    message: Required[Dict[str, Any]]  # Message to send
    wait_for_response: NotRequired[bool]  # Wait for response
    timeout: NotRequired[float]  # Response timeout


class AgentBroadcastData(TypedDict):
    """Broadcast a message to all agents."""
    message: Required[Dict[str, Any]]  # Message to broadcast
    exclude_agents: NotRequired[List[str]]  # Agents to exclude
    agent_types: NotRequired[List[str]]  # Filter by agent types


class AgentUpdateCompositionData(TypedDict):
    """Update agent composition."""
    agent_id: Required[str]  # Agent ID
    composition: Required[str]  # New composition name


class AgentDiscoverPeersData(TypedDict):
    """Discover other agents and their capabilities."""
    agent_id: NotRequired[str]  # Requesting agent ID
    capabilities: NotRequired[List[str]]  # Required capabilities
    agent_types: NotRequired[List[str]]  # Filter by agent types


class AgentNegotiateRolesData(TypedDict):
    """Coordinate role negotiation between agents."""
    agents: Required[List[str]]  # Agent IDs to negotiate
    roles: Required[Dict[str, str]]  # Role assignments
    context: NotRequired[Dict[str, Any]]  # Negotiation context


# Helper functions
async def load_identities():
    """Load agent identities from disk."""
    if identity_storage_path.exists():
        try:
            async with aiofiles.open(identity_storage_path, 'r') as f:
                content = await f.read()
                loaded_identities = json.loads(content)
            if loaded_identities:
                identities.update(loaded_identities)
                logger.info(f"Loaded {len(identities)} agent identities")
        except Exception as e:
            logger.error(f"Failed to load identities: {e}")


async def save_identities():
    """Save agent identities to disk."""
    try:
        # Ensure parent directory exists
        identity_storage_path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(identities, indent=2)
        async with aiofiles.open(identity_storage_path, 'w') as f:
            await f.write(content)
        logger.debug(f"Saved {len(identities)} identities")
    except Exception as e:
        logger.error(f"Failed to save identities: {e}")


# System event handlers
@event_handler("system:context")
async def handle_context(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
    """Receive module context with event emitter."""
    from ksi_common.event_parser import event_format_linter
    data = event_format_linter(raw_data, SystemContextData)
    global event_emitter
    # Get router for event emission
    router = get_router()
    event_emitter = router.emit
    logger.info("Agent service received context, event_emitter configured")


@event_handler("system:startup")
async def handle_startup(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Initialize agent service on startup."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder
    data = event_format_linter(raw_data, SystemStartupData)
    await load_identities()
    
    logger.info(f"Agent service started - agents: {len(agents)}, "
                f"identities: {len(identities)}")
    
    return event_response_builder(
        {
            "status": "agent_service_ready",
            "agents": len(agents),
            "identities": len(identities)
        },
        context=context
    )


@event_handler("system:ready")
async def handle_ready(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load agents from graph database after all services are ready."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder
    data = event_format_linter(raw_data, SystemReadyData)
    loaded_agents = 0
    
    if not event_emitter:
        logger.error("Event emitter not available, cannot load agents from state")
        return event_response_builder(
            {"loaded_agents": 0},
            context=context
        )
    
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
                agent_id = entity["id"]
                props = entity.get("properties", {})
                
                # Skip if agent already exists (shouldn't happen but be safe)
                if agent_id in agents:
                    continue
                
                # Reconstruct agent info from entity properties
                agent_info = {
                    "agent_id": agent_id,
                    "profile": props.get("profile"),
                    "composition": props.get("profile"),  # Often same as profile
                    "config": {
                        "model": "sonnet",  # Default, may need to store this
                        "role": "assistant",
                        "enable_tools": False,
                        "expanded_capabilities": props.get("capabilities", []),
                        "allowed_events": [],  # Would need to reconstruct from capabilities
                        "allowed_claude_tools": []
                    },
                    "status": props.get("status", "ready"),
                    "created_at": entity.get("created_at_iso"),
                    # NOTE: session_id removed - agents have no awareness of sessions
                    "permission_profile": props.get("permission_profile", "standard"),
                    "sandbox_dir": props.get("sandbox_dir"),
                    "mcp_config_path": props.get("mcp_config_path"),
                    "conversation_id": None,
                    "message_queue": asyncio.Queue(),
                    # Metadata stored in state system
                    "metadata_namespace": f"metadata:agent:{agent_id}"
                }
                
                # Register agent
                agents[agent_id] = agent_info
                
                # Start agent thread
                task = asyncio.create_task(run_agent_thread(agent_id))
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
    if loaded_agents > 0:
        await reestablish_observations({})
    
    return event_response_builder(
        {
            "agents_loaded": loaded_agents,
            "total_agents": len(agents)
        },
        context=context
    )


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
    
    # Save identities
    await save_identities()
    
    logger.info(f"Agent service stopped - {len(agents)} agents, "
                f"{len(identities)} identities")
    
    # Acknowledge shutdown to event system
    router = get_router()
    await router.acknowledge_shutdown("agent_service")


# Observation patterns removed - orchestration handles agent relationships


# Observation handlers removed - orchestration patterns handle subscriptions


# Session tracking is now handled by completion service ConversationTracker
# No longer need completion:result handler in agent service


@event_handler("checkpoint:collect")
async def handle_checkpoint_collect(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Collect agent state for checkpoint."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, CheckpointCollectData)
    try:
        # Prepare agent state for checkpointing
        agent_state = {}
        
        for agent_id, agent_info in agents.items():
            # Skip terminated agents
            if agent_info.get("status") == "terminated":
                continue
                
            # Create a serializable copy of agent info
            checkpoint_info = {
                "agent_id": agent_id,
                "profile": agent_info.get("profile"),
                "composition": agent_info.get("composition"),
                "config": agent_info.get("config", {}),
                "status": agent_info.get("status"),
                "created_at": agent_info.get("created_at"),
                # session_id removed - managed by completion system
                "permission_profile": agent_info.get("permission_profile"),
                "sandbox_dir": agent_info.get("sandbox_dir"),
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
        return event_response_builder(
            checkpoint_data,
            context=context
        )
        
    except Exception as e:
        logger.error(f"Failed to collect agent state for checkpoint: {e}")
        return error_response(
            str(e),
            context=context
        )


@event_handler("checkpoint:restore")
async def handle_checkpoint_restore(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Restore agent state from checkpoint."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, CheckpointRestoreData)
    try:
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
                agent_task = asyncio.create_task(run_agent_thread(agent_id))
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
                            "profile": agents[agent_id].get("profile"),
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
        return event_response_builder(
            result,
            context=context
        )
        
    except Exception as e:
        logger.error(f"Failed to restore agent checkpoint: {e}")
        return error_response(
            str(e),
            context=context
        )


# Agent lifecycle handlers
@event_handler("agent:spawn")
async def handle_spawn_agent(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Spawn a new agent thread with optional profile."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, AgentSpawnData)
    agent_id = data.get("agent_id") or f"agent_{uuid.uuid4().hex[:8]}"
    profile_name = data.get("profile") or data.get("profile_name")
    composition_name = data.get("composition")  # Direct composition reference
    # NOTE: session_id is intentionally NOT extracted from spawn data
    # Session management is handled entirely by the completion system
    
    # Check for dynamic spawn mode
    spawn_mode = data.get("spawn_mode", "fixed")
    selection_context = data.get("selection_context", {})
    
    # Determine what to compose
    if spawn_mode == "dynamic" and event_emitter:
        # Use composition selection service
        logger.debug("Using dynamic composition selection")
        
        select_result = await event_emitter("composition:select", {
            "agent_id": agent_id,
            "role": selection_context.get("role"),
            "capabilities": selection_context.get("required_capabilities", []),
            "task": data.get("task"),
            "context": selection_context,
            "max_suggestions": 3
        }, propagate_agent_context(context))
        
        if select_result and isinstance(select_result, list):
            # Handle multiple responses - take first one
            select_result = select_result[0] if select_result else {}
        
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
            
    elif composition_name:
        # Direct composition reference (hint mode)
        compose_name = composition_name
    elif profile_name:
        # Use specified profile
        compose_name = profile_name
    else:
        # No profile specified - fail fast
        return error_response(
            "No profile or composition specified",
            context=context
        )
    
    # Compose profile using composition service
    agent_config = {}
    
    if event_emitter:
        logger.debug(f"Using composition service to compose profile: {compose_name}")
        # Prepare variables for composition
        comp_vars = {
            "agent_id": agent_id,
            "enable_tools": data.get("enable_tools", False)
        }
        
        # Add any additional context from data
        if "context" in data:
            comp_vars.update(data["context"])
        
        # Try to compose profile
        compose_result = await event_emitter("composition:profile", {
            "name": compose_name,
            "variables": comp_vars
        }, propagate_agent_context(context))
        
        if compose_result and isinstance(compose_result, list):
            # Handle multiple responses - take first one
            compose_result = compose_result[0] if compose_result else {}
        
        if compose_result and compose_result.get("status") == "success":
            profile = compose_result["profile"]
            
            # Validate and resolve capabilities for agent spawn
            enforcer = get_capability_enforcer()
            
            # Extract capabilities from composed profile
            # Only look for the top-level "capabilities" component (dict of boolean flags)
            profile_capabilities = profile.get("capabilities", {})
            
            # Validate and resolve capabilities for agent spawn
            resolved = enforcer.validate_agent_spawn(profile_capabilities)
            allowed_events = resolved["allowed_events"]
            allowed_claude_tools = resolved["allowed_claude_tools"]
            expanded_capabilities = resolved["expanded_capabilities"]
            
            logger.info(
                f"Resolved capabilities for agent {agent_id}",
                capabilities=expanded_capabilities,
                event_count=len(allowed_events),
                claude_tool_count=len(allowed_claude_tools)
            )
            
            # Extract config from composed profile
            agent_config = {
                "model": profile.get("model", "sonnet"),
                "role": profile.get("role", "assistant"),
                "enable_tools": profile.get("enable_tools", False),
                "expanded_capabilities": expanded_capabilities,
                "allowed_events": allowed_events,
                "allowed_claude_tools": allowed_claude_tools
            }
        else:
            # Fail fast - no fallbacks
            error_msg = compose_result.get("error", f"Failed to compose profile: {compose_name}")
            logger.error(error_msg)
            return error_response(
                error_msg,
                context=context
            )
    else:
        # No composition service available
        logger.error("Composition service not available - event_emitter is None")
        return error_response(
            "Composition service not available - event system not initialized",
            context=context
        )
    
    # Override with provided config
    if "config" in data:
        agent_config.update(data["config"])
    
    # Set up permissions and sandbox
    permission_profile = data.get("permission_profile", "standard")
    sandbox_config = data.get("sandbox_config", {})
    sandbox_dir = None
    
    # Get permissions from composed profile if available
    if compose_result and "profile" in compose_result:
        profile_perms = compose_result["profile"].get("permissions", {})
        if "profile" in profile_perms:
            permission_profile = profile_perms["profile"]
        if "sandbox" in compose_result["profile"]:
            sandbox_config.update(compose_result["profile"]["sandbox"])
    
    # Set agent permissions
    if event_emitter:
        perm_result = await event_emitter("permission:set_agent", {
            "agent_id": agent_id,
            "profile": permission_profile,
            "overrides": data.get("permission_overrides", {})
        }, propagate_agent_context(context))
        
        if perm_result and isinstance(perm_result, list):
            perm_result = perm_result[0] if perm_result else {}
        
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
        
        if sandbox_result and isinstance(sandbox_result, list):
            sandbox_result = sandbox_result[0] if sandbox_result else {}
        
        if sandbox_result and "sandbox" in sandbox_result:
            sandbox_dir = sandbox_result["sandbox"]["path"]
            logger.info(f"Created sandbox for agent {agent_id}: {sandbox_dir}")
        else:
            logger.warning(f"Failed to create sandbox for agent {agent_id}")
    
    # Extract metadata to store in state system
    metadata = data.get("metadata", {})
    
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
    
    # Create agent info
    agent_info = {
        "agent_id": agent_id,
        "profile": profile_name or compose_name,
        "composition": composition_name or compose_name,
        "config": agent_config,
        "status": "initializing",
        "created_at": format_for_logging(),
        # NOTE: session_id removed - agents have no awareness of sessions
        # All session management is handled by the completion system
        "message_queue": asyncio.Queue(),
        "permission_profile": permission_profile,
        "sandbox_dir": sandbox_dir,
        "mcp_config_path": str(mcp_config_path) if mcp_config_path else None,
        "conversation_id": conversation_id if 'conversation_id' in locals() else None,
        # Metadata will be stored in state system, not in memory
        "metadata_namespace": f"metadata:agent:{agent_id}\""
    }
    
    # Register agent
    agents[agent_id] = agent_info
    
    # Create agent entity in graph database
    if event_emitter:
        # Create agent entity
        # Store core properties in entity
        entity_props = {
            "status": "active",
            "profile": profile_name or compose_name,
            "capabilities": expanded_capabilities,
            "permission_profile": permission_profile,
            "sandbox_dir": sandbox_dir,
            "mcp_config_path": str(mcp_config_path) if mcp_config_path else None
        }
        
        entity_result = await event_emitter("state:entity:create", {
            "id": agent_id,
            "type": "agent",
            "properties": entity_props
        }, propagate_agent_context(context))
        
        if entity_result and isinstance(entity_result, list):
            entity_result = entity_result[0] if entity_result else {}
        
        if entity_result and "error" not in entity_result:
            logger.debug(f"Created agent entity {agent_id}")
        else:
            logger.warning(f"Failed to create agent entity: {entity_result}")
        
        # Store metadata in state system namespace
        if metadata:
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
    agent_task = asyncio.create_task(run_agent_thread(agent_id))
    agent_threads[agent_id] = agent_task
    
    logger.info(f"Created agent thread {agent_id} with composition {compose_name}")
    
    # Observation patterns removed - handle via orchestration
    
    # Send initial prompt if provided - use composition system for proper message construction
    interaction_prompt = data.get("prompt")
    if interaction_prompt and event_emitter:
        logger.info(f"Sending initial prompt to agent {agent_id}")
        
        # Use composition service to create self-configuring agent context
        compose_result = await event_emitter("composition:agent_context", {
            "profile": compose_name,
            "agent_id": agent_id,
            "interaction_prompt": interaction_prompt,
            "orchestration": data.get("orchestration"),  # Include orchestration context if available
            "variables": data.get("variables", {})
        }, propagate_agent_context(context))
        
        if compose_result and isinstance(compose_result, list):
            compose_result = compose_result[0] if compose_result else {}
        
        if compose_result and compose_result.get("status") == "success":
            agent_context_message = compose_result["agent_context_message"]
            
            # Send self-configuring context message through agent:send_message channel
            initial_result = await event_emitter("agent:send_message", {
                "agent_id": agent_id,
                "message": {
                    "role": "user", 
                    "content": agent_context_message
                }
            }, propagate_agent_context(context))
            
            if initial_result and isinstance(initial_result, list):
                initial_result = initial_result[0] if initial_result else {}
            
            logger.info(f"Self-configuring context sent to agent {agent_id}: {initial_result.get('status', 'unknown')}")
            logger.debug(f"Redactions applied: {compose_result.get('redaction_applied', [])}")
        else:
            logger.error(f"Failed to compose agent context for agent {agent_id}: {compose_result.get('error', 'Unknown error')}")
            # Fallback to simple message with basic instructions
            fallback_message = f"""You are agent {agent_id} in the KSI system.

I encountered an error loading your composition configuration. 

{f"Your initial task: {interaction_prompt}" if interaction_prompt else "Please await further instructions."}

Please proceed as a basic autonomous agent with full autonomy to execute tasks and emit JSON events."""
            
            initial_result = await event_emitter("agent:send_message", {
                "agent_id": agent_id,
                "message": {
                    "role": "user", 
                    "content": fallback_message
                }
            }, propagate_agent_context(context))
            
            if initial_result and isinstance(initial_result, list):
                initial_result = initial_result[0] if initial_result else {}
            
            logger.warning(f"Used fallback self-configuring message for agent {agent_id}")
    
    return event_response_builder(
        {
            "agent_id": agent_id,
            "status": "created",
            "profile": profile_name,
            "composition": compose_name,
            # session_id intentionally omitted - managed by completion system
            "config": agent_config,
            "metadata_namespace": f"metadata:agent:{agent_id}"
        },
        context=context
    )


@event_handler("agent:terminate")
async def handle_terminate_agent(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Terminate agents - supports both single and bulk operations."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, AgentTerminateData)
    
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
    
    # Return single agent format for backward compatibility
    if len(target_agent_ids) == 1 and not data.get("agent_ids") and not data.get("pattern") and not data.get("older_than_hours") and not data.get("profile") and not data.get("all"):
        if terminated_agents:
            return event_response_builder(
                {"agent_id": terminated_agents[0], "status": "terminated"},
                context=context
            )
        elif failed_agents:
            return error_response(
                failed_agents[0].get("error", "Termination failed"),
                context=context
            )
    
    # Return bulk format
    return event_response_builder(
        {
            "terminated": terminated_agents,
            "failed": failed_agents,
            "count_terminated": len(terminated_agents),
            "count_failed": len(failed_agents)
        },
        context=context
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
    
    # Profile-based termination
    if "profile" in data:
        target_profile = data["profile"]
        for agent_id, agent_info in agents.items():
            if agent_info.get("profile") == target_profile:
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
    
    # Clean up sandbox and permissions asynchronously
    if event_emitter:
        # Remove sandbox
        await event_emitter("sandbox:remove", {
            "agent_id": agent_id,
            "force": force
        }, propagate_agent_context(context))
        
        # Remove permissions
        await event_emitter("permission:remove_agent", {
            "agent_id": agent_id
        }, propagate_agent_context(context))
    
    # Clean up MCP config if present
    if config.mcp_enabled:
        try:
            mcp_config_manager.cleanup_agent_config(agent_id)
            logger.debug(f"Cleaned up MCP config for agent {agent_id}")
        except Exception as e:
            logger.error(f"Failed to clean up MCP config for agent {agent_id}: {e}")
    
    # Update agent entity status in state
    if event_emitter:
        update_result = await event_emitter("state:entity:update", {
            "id": agent_id,
            "properties": {
                "status": "terminated",
                "terminated_at": time.time(),  # numeric for DB storage
                "terminated_at_iso": timestamp_utc()  # ISO for display
            }
        }, propagate_agent_context(context))
        
        if update_result and isinstance(update_result, list):
            update_result = update_result[0] if update_result else {}
        
        if update_result and update_result.get("status") == "updated":
            logger.debug(f"Updated agent entity {agent_id} to terminated")
        else:
            logger.warning(f"Failed to update agent entity status: {update_result}")
        
        # IMPORTANT: Clean up agent session in ConversationTracker
        # This ensures new agents with the same ID start fresh
        await event_emitter("completion:clear_agent_session", {
            "agent_id": agent_id
        }, propagate_agent_context(context))
    
    # Remove from active agents
    del agents[agent_id]
    
    logger.debug(f"Terminated agent {agent_id}")
    
    return {
        "agent_id": agent_id,
        "status": "terminated"
    }


@event_handler("agent:restart")
async def handle_restart_agent(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Restart an agent."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, AgentRestartData)
    agent_id = data.get("agent_id")
    
    if not agent_id:
        return error_response(
            "agent_id required",
            context=context
        )
    
    if agent_id not in agents:
        return error_response(
            f"Agent {agent_id} not found",
            context=context
        )
    
    # Get current agent info
    agent_info = agents[agent_id].copy()
    
    # Terminate existing
    terminate_result = await handle_terminate_agent({"agent_id": agent_id}, context)
    if "error" in terminate_result:
        return terminate_result
    
    # Spawn new with same config
    # Only pass agent_id and profile - completion system handles session continuity
    spawn_data = {
        "agent_id": agent_id,
        "profile": agent_info.get("profile")
        # config and session_id omitted - profile contains config, completion tracks sessions
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
                "model": f"claude-cli/{agent_info.get('config', {}).get('model', 'sonnet')}",
                "priority": "normal",
                "request_id": f"{agent_id}_{message.get('request_id', uuid.uuid4().hex[:8])}"
            }
            
            # Always add KSI parameters via extra_body for LiteLLM
            # This ensures all agent-specific context is passed through
            ksi_body = {
                "agent_id": agent_id,
                "sandbox_dir": agent_info.get("sandbox_dir"),
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
            await event_emitter("completion:async", completion_data, {
                "_agent_id": agent_id  # Agent is the originator
            })
    
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
@event_handler("agent:register")
async def handle_register_agent(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Register an external agent."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, AgentRegisterData)
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


@event_handler("agent:unregister")
async def handle_unregister_agent(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Unregister an agent."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, AgentUnregisterData)
    agent_id = data.get("agent_id")
    
    if not agent_id:
        return error_response("agent_id required", context)
    
    if agent_id in agents:
        del agents[agent_id]
        logger.info(f"Unregistered agent {agent_id}")
        return event_response_builder({"status": "unregistered"}, context)
    
    return error_response(f"Agent {agent_id} not found", context)


@event_handler("agent:list")
async def handle_list_agents(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """List registered agents."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder
    data = event_format_linter(raw_data, AgentListData)
    filter_status = data.get("status")
    include_metadata = data.get("include_metadata", False)
    
    agent_list = []
    for agent_id, info in agents.items():
        if filter_status and info.get("status") != filter_status:
            continue
        
        agent_entry = {
            "agent_id": agent_id,
            "status": info.get("status"),
            "profile": info.get("profile"),
            "created_at": info.get("created_at"),
            "metadata_namespace": f"metadata:agent:{agent_id}"
        }
        
        # Optionally fetch metadata from state system
        if include_metadata and event_emitter:
            metadata_result = await event_emitter("state:get", {
                "namespace": f"metadata:agent:{agent_id}"
            }, propagate_agent_context(context))
            if metadata_result and isinstance(metadata_result, list):
                metadata_result = metadata_result[0] if metadata_result else {}
            
            if metadata_result and "data" in metadata_result:
                agent_entry["metadata"] = metadata_result["data"]
            
        agent_list.append(agent_entry)
    
    return event_response_builder(
        {
            "agents": agent_list,
            "count": len(agent_list)
        },
        context=context
    )


# Construct-specific handlers removed - use orchestration patterns


# Identity handlers
@event_handler("agent:create_identity")
async def handle_create_identity(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a new agent identity."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder
    data = event_format_linter(raw_data, AgentCreateIdentityData)
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
    await save_identities()
    
    logger.info(f"Created identity for agent {agent_id}")
    
    return event_response_builder(
        {
            "agent_id": agent_id,
            "status": "created"
        },
        context=context
    )


@event_handler("agent:update_identity")
async def handle_update_identity(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Update an agent identity."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, AgentUpdateIdentityData)
    agent_id = data.get("agent_id")
    updates = data.get("updates", {})
    
    if not agent_id:
        return error_response(
            "agent_id required",
            context=context
        )
    
    if agent_id not in identities:
        return error_response(
            f"Identity for {agent_id} not found",
            context=context
        )
    
    # Update identity
    identities[agent_id].update(updates)
    identities[agent_id]["updated_at"] = format_for_logging()
    
    await save_identities()
    
    logger.info(f"Updated identity for agent {agent_id}")
    
    return event_response_builder(
        {
            "agent_id": agent_id,
            "status": "updated"
        },
        context=context
    )


@event_handler("agent:remove_identity")
async def handle_remove_identity(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Remove an agent identity."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, AgentRemoveIdentityData)
    agent_id = data.get("agent_id")
    
    if not agent_id:
        return error_response(
            "agent_id required",
            context=context
        )
    
    if agent_id in identities:
        del identities[agent_id]
        await save_identities()
        logger.info(f"Removed identity for agent {agent_id}")
        return event_response_builder(
            {"status": "removed"},
            context=context
        )
    
    return error_response(
        f"Identity for {agent_id} not found",
        context=context
    )


@event_handler("agent:list_identities")
async def handle_list_identities(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """List agent identities."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder
    data = event_format_linter(raw_data, AgentListIdentitiesData)
    identity_list = []
    
    for agent_id, identity in identities.items():
        identity_list.append({
            "agent_id": agent_id,
            "name": identity.get("name", ""),
            "role": identity.get("role", ""),
            "created_at": identity.get("created_at")
        })
    
    return event_response_builder(
        {
            "identities": identity_list,
            "count": len(identity_list)
        },
        context=context
    )


@event_handler("agent:get_identity")
async def handle_get_identity(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get a specific agent identity."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    data = event_format_linter(raw_data, AgentGetIdentityData)
    agent_id = data.get("agent_id")
    
    if not agent_id:
        return error_response(
            "agent_id required",
            context=context
        )
    
    if agent_id in identities:
        return event_response_builder(
            {
                "agent_id": agent_id,
                "identity": identities[agent_id]
            },
            context=context
        )
    
    return error_response(
        f"Identity for {agent_id} not found",
        context=context
    )


# Task routing handlers
@event_handler("agent:route_task")
async def handle_route_task(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Route a task to an appropriate agent."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, AgentRouteTaskData)
    # Simple routing: find first available agent
    for agent_id, info in agents.items():
        if info.get("status") == "ready":
            logger.info(f"Routing task to agent {agent_id}")
            return event_response_builder({
                "agent_id": agent_id,
                "status": "routed"
            }, context)
    
    return error_response("No available agents", context)


@event_handler("agent:get_capabilities")
async def handle_get_capabilities(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get capabilities of an agent or all agents."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, AgentGetCapabilitiesData)
    agent_id = data.get("agent_id")
    
    if agent_id:
        if agent_id not in agents:
            return error_response(f"Agent {agent_id} not found", context)
        
        agent_info = agents[agent_id]
        
        # Get capabilities from agent config (composed at spawn time)
        capabilities = agent_info.get("config", {}).get("capabilities", [])
        
        return event_response_builder({
            "agent_id": agent_id,
            "capabilities": capabilities
        }, context)
    
    # Return all agent capabilities
    all_capabilities = {}
    for aid, info in agents.items():
        # Get capabilities from agent config (composed at spawn time)
        all_capabilities[aid] = info.get("config", {}).get("capabilities", [])
    
    return event_response_builder({"capabilities": all_capabilities}, context)


# Message handling functions
@event_handler(
    "agent:send_message",
)
async def handle_send_message(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Send a message to an agent."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, AgentSendMessageData)
    agent_id = data.get("agent_id")
    message = data.get("message", {})
    
    if not agent_id:
        return error_response("agent_id required", context)
    
    if agent_id not in agents:
        return error_response(f"Agent {agent_id} not found", context)
    
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
            "model": f"claude-cli/{agent_config.get('model', 'sonnet')}",
            "priority": "normal",
            "request_id": f"{agent_id}_{message.get('request_id', uuid.uuid4().hex[:8])}"
        }
        
        # Add KSI parameters
        completion_data["extra_body"] = {
            "ksi": {
                "conversation_id": f"agent_conversation_{agent_id}",
                "tools": agent_config.get("allowed_claude_tools", []),
                "agent_id": agent_id,
                "construct_id": agent_info.get("construct_id"),
                "agent_role": agent_config.get("role", "assistant"),
                "enable_tools": agent_config.get("enable_tools", True)
            }
        }
        
        # Emit completion event directly
        # Mark this as agent-originated for observation  
        result = await event_emitter("completion:async", completion_data, 
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


@event_handler("agent:broadcast")
async def handle_broadcast(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Broadcast a message to all agents."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder
    
    data = event_format_linter(raw_data, AgentBroadcastData)
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
@event_handler("agent:update_composition")
async def handle_update_composition(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Handle agent composition update request."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, AgentUpdateCompositionData)
    agent_id = data.get("agent_id")
    new_composition = data.get("new_composition")
    reason = data.get("reason", "Adaptation required")
    
    if not agent_id:
        return error_response("agent_id required", context)
    
    if not new_composition:
        return error_response("new_composition required", context)
    
    if agent_id not in agents:
        return error_response(f"Agent {agent_id} not found", context)
    
    # Check if agent can self-modify
    agent_info = agents[agent_id]
    current_config = agent_info.get("config", {})
    
    if not event_emitter:
        return error_response("Event emitter not available", context)
    
    # First, check if current composition allows modification
    current_comp = agent_info.get("composition", agent_info.get("profile"))
    if current_comp:
        # Get composition metadata
        comp_result = await event_emitter("composition:get", {
            "name": current_comp
        }, propagate_agent_context(context))
        
        if comp_result and isinstance(comp_result, list):
            comp_result = comp_result[0] if comp_result else {}
        
        if comp_result and comp_result.get("status") == "success":
            metadata = comp_result["composition"].get("metadata", {})
            if not metadata.get("self_modifiable", False):
                return error_response("Current composition does not allow self-modification", context, {"status": "denied"})
    
    # Compose new profile
    compose_result = await event_emitter("composition:profile", {
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
        new_profile = compose_result["profile"]
        
        # Update agent configuration
        agent_info["config"] = {
            "model": new_profile.get("model", "sonnet"),
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
        return error_response(f"Failed to compose new profile: {compose_result.get('error', 'Unknown error')}", context, {"status": "failed"})


@event_handler("agent:discover_peers")
async def handle_discover_peers(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Discover other agents and their capabilities."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder
    
    data = event_format_linter(raw_data, AgentDiscoverPeersData)
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


@event_handler("agent:negotiate_roles")
async def handle_negotiate_roles(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Coordinate role negotiation between agents."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, AgentNegotiateRolesData)
    participants = data.get("participants", [])
    negotiation_type = data.get("type", "collaborative")
    negotiation_context = data.get("context", {})  # Renamed to avoid conflict
    
    if not participants or len(participants) < 2:
        return error_response("At least 2 participants required for negotiation", context)
    
    # Verify all participants exist
    for agent_id in participants:
        if agent_id not in agents:
            return error_response(f"Agent {agent_id} not found", context)
    
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


@event_handler("agent:needs_continuation")
async def handle_agent_needs_continuation(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Handle agent continuation requests for step-wise execution."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, dict)  # Simple dict for this handler
    # Extract agent_id from event metadata
    agent_id = data.get("_agent_id")  # This is set by event extraction
    if not agent_id:
        return error_response("No agent_id in continuation request", context)
    
    if agent_id not in agents:
        return error_response(f"Agent {agent_id} not found", context)
    
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


