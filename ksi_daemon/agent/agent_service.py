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
from typing import Any, Dict, TypedDict, List, Literal
import aiofiles

from typing_extensions import NotRequired, Required

from ksi_common import format_for_logging
from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc
from ksi_daemon.capability_enforcer import get_capability_enforcer
from ksi_daemon.event_system import event_handler, shutdown_handler, get_router
from ksi_daemon.mcp import mcp_config_manager
from ksi_daemon.agent.metadata import AgentMetadata
from ksi_daemon.evaluation.tournament_evaluation import process_agent_tournament_message, extract_evaluation_from_response
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
    originator_agent_id: NotRequired[str]  # ID of spawning agent
    purpose: NotRequired[str]  # Purpose description
    composition: NotRequired[str]  # Composition name
    model: NotRequired[str]  # Model to use
    enable_tools: NotRequired[bool]  # Enable tool usage
    agent_type: NotRequired[Literal["construct", "system", "user"]]  # Agent type
    permission_profile: NotRequired[str]  # Permission profile name
    sandbox_dir: NotRequired[str]  # Sandbox directory
    mcp_config_path: NotRequired[str]  # MCP configuration path
    conversation_id: NotRequired[str]  # Conversation ID


class AgentTerminateData(TypedDict):
    """Terminate an agent."""
    agent_id: Required[str]  # Agent ID to terminate
    force: NotRequired[bool]  # Force termination


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


class AgentListConstructsData(TypedDict):
    """List construct agents for an originator."""
    originator_id: Required[str]  # Originator agent ID
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
async def handle_context(context: SystemContextData) -> None:
    """Receive module context with event emitter."""
    global event_emitter
    # Get router for event emission
    router = get_router()
    event_emitter = router.emit
    logger.info("Agent service received context, event_emitter configured")


@event_handler("system:startup")
async def handle_startup(config_data: SystemStartupData) -> Dict[str, Any]:
    """Initialize agent service on startup."""
    await load_identities()
    
    logger.info(f"Agent service started - agents: {len(agents)}, "
                f"identities: {len(identities)}")
    
    return {
        "status": "agent_service_ready",
        "agents": len(agents),
        "identities": len(identities)
    }


@event_handler("system:ready")
async def handle_ready(data: SystemReadyData) -> Dict[str, Any]:
    """Load agents from graph database after all services are ready."""
    loaded_agents = 0
    
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
                    "originator_agent_id": None,
                    "agent_type": props.get("agent_type", "system"),
                    "purpose": props.get("purpose"),
                    "composed_prompt": None,
                    "message_queue": asyncio.Queue(),
                    "metadata": AgentMetadata(
                        agent_id=agent_id,
                        originator_agent_id=None,
                        agent_type=props.get("agent_type", "system"),
                        spawned_at=entity.get("created_at", time.time()),
                        purpose=props.get("purpose")
                    )
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
    
    # Save identities
    await save_identities()
    
    logger.info(f"Agent service stopped - {len(agents)} agents, "
                f"{len(identities)} identities")
    
    # Acknowledge shutdown to event system
    router = get_router()
    await router.acknowledge_shutdown("agent_service")


@event_handler("observation:ready")
async def reestablish_observations(data: ObservationReadyData) -> None:
    """Re-establish observations for all active agents after restart."""
    if not event_emitter:
        logger.warning("Cannot re-establish observations - no event emitter")
        return
        
    active_agents = [agent for agent in agents.values() if agent.get("status") == "active"]
    logger.info(f"Re-establishing observations for {len(active_agents)} active agents")
    
    for agent_info in active_agents:
        agent_id = agent_info["agent_id"]
        
        # Get agent's profile to find observation config
        if "composed_prompt" in agent_info:
            # Try to get observation config from the original profile
            # For now, we'll skip this as we don't store the full profile
            # In production, you'd want to store observation config in agent_info
            pass
            
        # Check if agent should observe children
        if agent_info.get("observe_children"):
            # Find all children of this agent
            rel_result = await event_emitter("state:relationships:query", {
                "from": agent_id,
                "type": "spawned"
            })
            
            if rel_result and isinstance(rel_result, list):
                rel_result = rel_result[0] if rel_result else {}
                
            relationships = rel_result.get("relationships", [])
            for rel in relationships:
                construct_id = rel.get("to")
                if construct_id:
                    await event_emitter("observation:subscribe", {
                        "observer": agent_id,
                        "target": construct_id,
                        "events": ["task:completed", "error:*"],
                        "filter": {}
                    })
                    logger.info(f"Re-established observation: {agent_id} -> {construct_id}")
        
        # Check if agent should observe parent
        if agent_info.get("originator_agent_id"):
            await event_emitter("observation:subscribe", {
                "observer": agent_id,
                "target": agent_info["originator_agent_id"],
                "events": ["directive:*", "task:assigned"],
                "filter": {}
            })
            logger.info(f"Re-established observation: {agent_id} -> {agent_info['originator_agent_id']}")


@event_handler("observation:restored")
async def handle_observation_restored(data: ObservationRestoredData) -> None:
    """Observations restored from checkpoint - no action needed."""
    restored_count = data.get("subscriptions_restored", 0)
    from_checkpoint = data.get("from_checkpoint", "unknown")
    
    logger.info(f"Observation subscriptions restored from checkpoint: {restored_count} subscriptions "
                f"from checkpoint at {from_checkpoint}")


# Session tracking is now handled by completion service ConversationTracker
# No longer need completion:result handler in agent service


@event_handler("checkpoint:collect")
async def handle_checkpoint_collect(data: CheckpointCollectData) -> Dict[str, Any]:
    """Collect agent state for checkpoint."""
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
                "originator_agent_id": agent_info.get("originator_agent_id"),
                "agent_type": agent_info.get("agent_type"),
                "purpose": agent_info.get("purpose"),
                "composed_prompt": agent_info.get("composed_prompt"),
                # Convert metadata to dict if it exists
                "metadata": agent_info.get("metadata").to_dict() if agent_info.get("metadata") else None
            }
            
            agent_state[agent_id] = checkpoint_info
        
        checkpoint_data = {
            "agents": agent_state,
            "identities": dict(identities),
            "active_agents": len([a for a in agents.values() if a.get("status") in ["ready", "active"]])
        }
        
        logger.info(f"Collected agent state for checkpoint: {len(agent_state)} agents")
        return checkpoint_data
        
    except Exception as e:
        logger.error(f"Failed to collect agent state for checkpoint: {e}")
        return {"error": str(e)}


@event_handler("checkpoint:restore")
async def handle_checkpoint_restore(data: CheckpointRestoreData) -> Dict[str, Any]:
    """Restore agent state from checkpoint."""
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
                # Recreate agent metadata if it exists
                metadata = None
                if agent_info.get("metadata"):
                    metadata_dict = agent_info["metadata"]
                    metadata = AgentMetadata(
                        agent_id=metadata_dict.get("agent_id"),
                        originator_agent_id=metadata_dict.get("originator_agent_id"),
                        agent_type=metadata_dict.get("agent_type", "system"),
                        purpose=metadata_dict.get("purpose")
                    )
                
                # Restore agent info
                restored_info = dict(agent_info)
                restored_info["message_queue"] = asyncio.Queue()
                restored_info["metadata"] = metadata
                
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
                            "agent_type": agents[agent_id].get("agent_type", "system"),
                            "purpose": agents[agent_id].get("purpose"),
                            "capabilities": agents[agent_id].get("config", {}).get("expanded_capabilities", []),
                            # session_id removed - completion system concept
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
        
    except Exception as e:
        logger.error(f"Failed to restore agent checkpoint: {e}")
        return {"error": str(e)}


# Agent lifecycle handlers
@event_handler("agent:spawn")
async def handle_spawn_agent(data: AgentSpawnData) -> Dict[str, Any]:
    """Spawn a new agent thread with optional profile."""
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
        })
        
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
            return {
                "error": f"Dynamic composition selection failed: {select_result.get('error', 'Unknown error')}",
                "status": "failed"
            }
            
    elif composition_name:
        # Direct composition reference (hint mode)
        compose_name = composition_name
    elif profile_name:
        # Use specified profile
        compose_name = profile_name
    else:
        # No profile specified - fail fast
        return {
            "error": "No profile or composition specified",
            "status": "failed"
        }
    
    # Compose profile using composition service
    agent_config = {}
    composed_prompt = None
    
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
        })
        
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
            # Extract system prompt from system_context component
            composed_prompt = None
            if "system_context" in profile and isinstance(profile["system_context"], dict):
                composed_prompt = profile["system_context"].get("prompt")
            
            # Fallback to old location for backward compatibility
            if not composed_prompt:
                composed_prompt = profile.get("composed_prompt")
        else:
            # Fail fast - no fallbacks
            error_msg = compose_result.get("error", f"Failed to compose profile: {compose_name}")
            logger.error(error_msg)
            return {
                "error": error_msg,
                "status": "failed",
                "requested_profile": compose_name
            }
    else:
        # No composition service available
        logger.error("Composition service not available - event_emitter is None")
        return {
            "error": "Composition service not available - event system not initialized",
            "status": "failed"
        }
    
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
        })
        
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
        })
        
        if sandbox_result and isinstance(sandbox_result, list):
            sandbox_result = sandbox_result[0] if sandbox_result else {}
        
        if sandbox_result and "sandbox" in sandbox_result:
            sandbox_dir = sandbox_result["sandbox"]["path"]
            logger.info(f"Created sandbox for agent {agent_id}: {sandbox_dir}")
        else:
            logger.warning(f"Failed to create sandbox for agent {agent_id}")
    
    # Extract originator information
    originator_agent_id = data.get("originator_agent_id")
    purpose = data.get("purpose")
    
    # Determine agent type
    if originator_agent_id:
        agent_type = "construct"
    elif data.get("agent_type") == "originator":
        agent_type = "originator"
    else:
        agent_type = "system"
    
    # Create agent metadata
    metadata = AgentMetadata(
        agent_id=agent_id,
        originator_agent_id=originator_agent_id,
        agent_type=agent_type,
        purpose=purpose
    )
    
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
        "composed_prompt": composed_prompt,
        "status": "initializing",
        "created_at": format_for_logging(),
        # NOTE: session_id removed - agents have no awareness of sessions
        # All session management is handled by the completion system
        "message_queue": asyncio.Queue(),
        "permission_profile": permission_profile,
        "sandbox_dir": sandbox_dir,
        "mcp_config_path": str(mcp_config_path) if mcp_config_path else None,
        "conversation_id": conversation_id if 'conversation_id' in locals() else None,
        "metadata": metadata,
        "originator_agent_id": originator_agent_id,  # Quick access
        "agent_type": agent_type,  # Quick access
        "purpose": purpose  # Quick access
    }
    
    # Register agent
    agents[agent_id] = agent_info
    
    # Create agent entity in graph database
    if event_emitter:
        # Create agent entity
        entity_props = {
            "status": "active",
            "profile": profile_name or compose_name,
            "agent_type": agent_type,
            "purpose": purpose,
            "capabilities": expanded_capabilities,
            # session_id intentionally omitted from entity - managed by completion system
            "permission_profile": permission_profile,
            "sandbox_dir": sandbox_dir,
            "mcp_config_path": str(mcp_config_path) if mcp_config_path else None
        }
        
        entity_result = await event_emitter("state:entity:create", {
            "id": agent_id,
            "type": "agent",
            "properties": entity_props
        })
        
        if entity_result and isinstance(entity_result, list):
            entity_result = entity_result[0] if entity_result else {}
        
        if entity_result and "error" not in entity_result:
            logger.debug(f"Created agent entity {agent_id}")
        else:
            logger.warning(f"Failed to create agent entity: {entity_result}")
        
        # Create relationship if this is a construct
        if originator_agent_id:
            rel_result = await event_emitter("state:relationship:create", {
                "from": originator_agent_id,
                "to": agent_id,
                "type": "spawned",
                "metadata": {
                    "purpose": purpose,
                    "spawned_at": metadata.spawned_at
                }
            })
            
            if rel_result and isinstance(rel_result, list):
                rel_result = rel_result[0] if rel_result else {}
            
            if rel_result and rel_result.get("status") == "created":
                logger.info(f"Created spawned relationship: {originator_agent_id} -> {agent_id}")
            else:
                logger.warning(f"Failed to create relationship: {rel_result}")
    
    # Start agent thread
    agent_task = asyncio.create_task(run_agent_thread(agent_id))
    agent_threads[agent_id] = agent_task
    
    logger.info(f"Created agent thread {agent_id} with composition {compose_name}")
    
    # Set up observations based on agent profile
    if event_emitter and compose_result and "profile" in compose_result:
        observation_config = compose_result["profile"].get("observation_config", {})
        subscriptions = observation_config.get("subscriptions", [])
        
        if subscriptions:
            # Wait for observation system to be ready (with timeout)
            max_retries = 5
            observation_ready = False
            for i in range(max_retries):
                try:
                    ready_check = await event_emitter("system:service:status", {"service": "observation"})
                    if ready_check and isinstance(ready_check, list):
                        ready_check = ready_check[0] if ready_check else {}
                    if ready_check.get("status") == "ready":
                        observation_ready = True
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.5 * (i + 1))  # Exponential backoff
            
            if observation_ready:
                # Set up each subscription
                for sub_config in subscriptions:
                    target_pattern = sub_config.get("target_pattern", "")
                    
                    # Resolve target pattern to actual agent IDs
                    target_ids = []
                    if "*" in target_pattern:
                        # Special patterns
                        if target_pattern == "parent":
                            # Observe parent/originator
                            if originator_agent_id:
                                target_ids = [originator_agent_id]
                        elif target_pattern == "children" or target_pattern == "child_*":
                            # Will be set up when children are spawned
                            # Store pattern for later use
                            agent_info["observe_children"] = True
                            continue
                        else:
                            # Query agents matching pattern
                            agents_result = await event_emitter("agent:list", {"pattern": target_pattern})
                            if agents_result and isinstance(agents_result, list):
                                agents_result = agents_result[0] if agents_result else {}
                            target_ids = [a["id"] for a in agents_result.get("agents", [])]
                    else:
                        # Specific agent ID
                        target_ids = [target_pattern]
                    
                    # Subscribe to each target
                    for target_id in target_ids:
                        if target_id and target_id != agent_id:  # Don't observe self
                            result = await event_emitter("observation:subscribe", {
                                "observer": agent_id,
                                "target": target_id,
                                "events": sub_config.get("events", ["*"]),
                                "filter": sub_config.get("filter", {})
                            })
                            
                            if result and isinstance(result, list):
                                result = result[0] if result else {}
                                
                            if result.get("error"):
                                logger.warning(f"Failed to subscribe {agent_id} to {target_id}: {result['error']}")
                            else:
                                logger.info(f"Agent {agent_id} now observing {target_id}")
            else:
                logger.warning(f"Observation system not ready for agent {agent_id} subscriptions")
    
    # Send initial prompt if provided - construct complete first message
    initial_prompt = data.get("prompt")
    if initial_prompt and event_emitter:
        logger.info(f"Sending initial prompt to agent {agent_id}")
        
        # Construct complete first message: agent prompt + initial user prompt
        complete_first_message = ""
        
        # Add agent prompt if available
        if composed_prompt:
            complete_first_message += composed_prompt + "\n\n"
        
        # Add initial user prompt  
        complete_first_message += initial_prompt
        
        # Send complete message through agent:send_message channel
        initial_result = await event_emitter("agent:send_message", {
            "agent_id": agent_id,
            "message": {
                "role": "user", 
                "content": complete_first_message
            }
        })
        
        if initial_result and isinstance(initial_result, list):
            initial_result = initial_result[0] if initial_result else {}
        
        logger.info(f"Initial prompt sent to agent {agent_id}: {initial_result.get('status', 'unknown')}")
    
    return {
        "agent_id": agent_id,
        "status": "created",
        "profile": profile_name,
        "composition": compose_name,
        # session_id intentionally omitted - managed by completion system
        "config": agent_config,
        "originator_agent_id": originator_agent_id,
        "agent_type": agent_type,
        "purpose": purpose,
        "metadata": metadata.to_dict()
    }


@event_handler("agent:terminate")
async def handle_terminate_agent(data: AgentTerminateData) -> Dict[str, Any]:
    """Terminate an agent thread."""
    agent_id = data.get("agent_id")
    
    if not agent_id:
        return {"error": "agent_id required"}
    
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
            "force": data.get("force", False)
        })
        
        # Remove permissions
        await event_emitter("permission:remove_agent", {
            "agent_id": agent_id
        })
    
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
        })
        
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
        })
    
    # Remove from active agents
    del agents[agent_id]
    
    logger.info(f"Terminated agent {agent_id}")
    
    return {
        "agent_id": agent_id,
        "status": "terminated"
    }


@event_handler("agent:restart")
async def handle_restart_agent(data: AgentRestartData) -> Dict[str, Any]:
    """Restart an agent."""
    agent_id = data.get("agent_id")
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    if agent_id not in agents:
        return {"error": f"Agent {agent_id} not found"}
    
    # Get current agent info
    agent_info = agents[agent_id].copy()
    
    # Terminate existing
    terminate_result = await handle_terminate_agent({"agent_id": agent_id})
    if "error" in terminate_result:
        return terminate_result
    
    # Spawn new with same config
    # Only pass agent_id and profile - completion system handles session continuity
    spawn_data = {
        "agent_id": agent_id,
        "profile": agent_info.get("profile")
        # config and session_id omitted - profile contains config, completion tracks sessions
    }
    
    return await handle_spawn_agent(spawn_data)


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
            await event_emitter("completion:async", completion_data)
    
    elif msg_type == "tournament_match":
        # Handle tournament evaluation request
        tournament_request = await process_agent_tournament_message(agent_id, message)
        if tournament_request and event_emitter:
            # Send completion request for tournament evaluation
            match_id = tournament_request.get('match_id')
            prompt = tournament_request.get('prompt')
            
            if prompt and match_id:
                completion_data = {
                    "messages": [{"role": "user", "content": prompt}],
                    "agent_id": agent_id,
                    "originator_id": agent_id,
                    # session_id removed - not an agent concern
                    "model": f"claude-cli/{agent_info.get('config', {}).get('model', 'sonnet')}",
                    "priority": "normal",
                    "request_id": f"tournament_{match_id}",
                    "metadata": {
                        "type": "tournament_evaluation",
                        "match_id": match_id
                    }
                }
                
                # Add KSI parameters
                ksi_body = {
                    "agent_id": agent_id,
                    "sandbox_dir": agent_info.get("sandbox_dir"),
                    "permissions": {
                        "allowed_tools": agent_info.get("config", {}).get("allowed_claude_tools", []),
                        "profile": agent_info.get("permission_profile", "standard")
                    },
                    "allowed_events": agent_info.get("config", {}).get("allowed_events", [])
                    # session_id removed - completion concept
                }
                
                completion_data["extra_body"] = {"ksi": ksi_body}
                logger.info(f"Agent {agent_id} processing tournament match {match_id}")
                
                # Session continuity is now handled automatically by completion service
                # Send completion request
                result = await event_emitter("completion:async", completion_data)
                
                # Store match_id in agent info for response handling
                agent_info["pending_tournament_match"] = match_id
    
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
async def handle_register_agent(data: AgentRegisterData) -> Dict[str, Any]:
    """Register an external agent."""
    agent_id = data.get("agent_id")
    agent_info = data.get("info", {})
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    # Create registration info
    registration = {
        "agent_id": agent_id,
        "registered_at": format_for_logging(),
        "status": "registered",
        **agent_info
    }
    
    agents[agent_id] = registration
    
    logger.info(f"Registered agent {agent_id}")
    
    return {
        "agent_id": agent_id,
        "status": "registered"
    }


@event_handler("agent:unregister")
async def handle_unregister_agent(data: AgentUnregisterData) -> Dict[str, Any]:
    """Unregister an agent."""
    agent_id = data.get("agent_id")
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    if agent_id in agents:
        del agents[agent_id]
        logger.info(f"Unregistered agent {agent_id}")
        return {"status": "unregistered"}
    
    return {"error": f"Agent {agent_id} not found"}


@event_handler("agent:list")
async def handle_list_agents(data: AgentListData) -> Dict[str, Any]:
    """List registered agents."""
    filter_status = data.get("status")
    
    agent_list = []
    for agent_id, info in agents.items():
        if filter_status and info.get("status") != filter_status:
            continue
        
        agent_entry = {
            "agent_id": agent_id,
            "status": info.get("status"),
            "profile": info.get("profile"),
            "created_at": info.get("created_at"),
            "agent_type": info.get("agent_type", "system"),
            "originator_agent_id": info.get("originator_agent_id"),
            "purpose": info.get("purpose")
        }
        
        # Include full metadata if available
        if "metadata" in info and isinstance(info["metadata"], AgentMetadata):
            agent_entry["metadata"] = info["metadata"].to_dict()
            
        agent_list.append(agent_entry)
    
    return {
        "agents": agent_list,
        "count": len(agent_list)
    }


@event_handler("agent:list_constructs")
async def handle_list_constructs(data: AgentListConstructsData) -> Dict[str, Any]:
    """List construct agents for a specific originator."""
    originator_id = data.get("originator_agent_id")
    
    if not originator_id:
        return {"error": "originator_agent_id required"}
    
    if not event_emitter:
        return {"error": "Event system not available"}
    
    # Query relationships to find constructs
    rel_result = await event_emitter("state:relationship:query", {
        "from": originator_id,
        "type": "spawned"
    })
    
    if rel_result and isinstance(rel_result, list):
        rel_result = rel_result[0] if rel_result else {}
    
    if not rel_result or "error" in rel_result:
        return {"error": "Failed to query relationships", "details": rel_result}
    
    relationships = rel_result.get("relationships", [])
    constructs = []
    
    # Get details for each construct
    for rel in relationships:
        construct_id = rel["to"]
        
        # Get construct entity
        entity_result = await event_emitter("state:entity:get", {
            "id": construct_id,
            "include": ["properties"]
        })
        
        if entity_result and isinstance(entity_result, list):
            entity_result = entity_result[0] if entity_result else {}
        
        if entity_result and "error" not in entity_result:
            props = entity_result.get("properties", {})
            construct_entry = {
                "agent_id": construct_id,
                "status": props.get("status", "unknown"),
                "purpose": props.get("purpose") or rel.get("metadata", {}).get("purpose"),
                "profile": props.get("profile"),
                "created_at": entity_result.get("created_at"),
                "created_at_iso": entity_result.get("created_at_iso"),
                "spawned_at": rel.get("metadata", {}).get("spawned_at", entity_result.get("created_at")),
                "spawned_at_iso": rel.get("created_at_iso")
            }
            constructs.append(construct_entry)
    
    return {
        "originator_agent_id": originator_id,
        "constructs": constructs,
        "count": len(constructs)
    }


# Identity handlers
@event_handler("agent:create_identity")
async def handle_create_identity(data: AgentCreateIdentityData) -> Dict[str, Any]:
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
    await save_identities()
    
    logger.info(f"Created identity for agent {agent_id}")
    
    return {
        "agent_id": agent_id,
        "status": "created"
    }


@event_handler("agent:update_identity")
async def handle_update_identity(data: AgentUpdateIdentityData) -> Dict[str, Any]:
    """Update an agent identity."""
    agent_id = data.get("agent_id")
    updates = data.get("updates", {})
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    if agent_id not in identities:
        return {"error": f"Identity for {agent_id} not found"}
    
    # Update identity
    identities[agent_id].update(updates)
    identities[agent_id]["updated_at"] = format_for_logging()
    
    await save_identities()
    
    logger.info(f"Updated identity for agent {agent_id}")
    
    return {
        "agent_id": agent_id,
        "status": "updated"
    }


@event_handler("agent:remove_identity")
async def handle_remove_identity(data: AgentRemoveIdentityData) -> Dict[str, Any]:
    """Remove an agent identity."""
    agent_id = data.get("agent_id")
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    if agent_id in identities:
        del identities[agent_id]
        await save_identities()
        logger.info(f"Removed identity for agent {agent_id}")
        return {"status": "removed"}
    
    return {"error": f"Identity for {agent_id} not found"}


@event_handler("agent:list_identities")
async def handle_list_identities(data: AgentListIdentitiesData) -> Dict[str, Any]:
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


@event_handler("agent:get_identity")
async def handle_get_identity(data: AgentGetIdentityData) -> Dict[str, Any]:
    """Get a specific agent identity."""
    agent_id = data.get("agent_id")
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    if agent_id in identities:
        return {
            "agent_id": agent_id,
            "identity": identities[agent_id]
        }
    
    return {"error": f"Identity for {agent_id} not found"}


# Task routing handlers
@event_handler("agent:route_task")
async def handle_route_task(data: AgentRouteTaskData) -> Dict[str, Any]:
    """Route a task to an appropriate agent."""
    # Simple routing: find first available agent
    for agent_id, info in agents.items():
        if info.get("status") == "ready":
            logger.info(f"Routing task to agent {agent_id}")
            return {
                "agent_id": agent_id,
                "status": "routed"
            }
    
    return {"error": "No available agents"}


@event_handler("agent:get_capabilities")
async def handle_get_capabilities(data: AgentGetCapabilitiesData) -> Dict[str, Any]:
    """Get capabilities of an agent or all agents."""
    agent_id = data.get("agent_id")
    
    if agent_id:
        if agent_id not in agents:
            return {"error": f"Agent {agent_id} not found"}
        
        agent_info = agents[agent_id]
        
        # Get capabilities from agent config (composed at spawn time)
        capabilities = agent_info.get("config", {}).get("capabilities", [])
        
        return {
            "agent_id": agent_id,
            "capabilities": capabilities
        }
    
    # Return all agent capabilities
    all_capabilities = {}
    for aid, info in agents.items():
        # Get capabilities from agent config (composed at spawn time)
        all_capabilities[aid] = info.get("config", {}).get("capabilities", [])
    
    return {"capabilities": all_capabilities}


# Message handling functions
@event_handler(
    "agent:send_message",
)
async def handle_send_message(data: AgentSendMessageData) -> Dict[str, Any]:
    """Send a message to an agent."""
    agent_id = data.get("agent_id")
    message = data.get("message", {})
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    if agent_id not in agents:
        return {"error": f"Agent {agent_id} not found"}
    
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
        result = await event_emitter("completion:async", completion_data)
        
        # Handle list response format
        if result and isinstance(result, list):
            result = result[0] if result else {}
        
        # Agents have no awareness of sessions - completion system handles everything
        
        return {
            "status": "sent_to_completion", 
            "agent_id": agent_id,
            "request_id": result.get("request_id") if result else None
        }
    
    # For non-completion messages, use the queue as before
    queue = agents[agent_id].get("message_queue")
    if queue:
        await queue.put(message)
        return {"status": "sent", "agent_id": agent_id}
    
    return {"error": "Agent message queue not available"}


@event_handler("agent:broadcast")
async def handle_broadcast(data: AgentBroadcastData) -> Dict[str, Any]:
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
    
    return {
        "status": "broadcast",
        "agents_reached": sent_count,
        "total_agents": len(agents)
    }


# Dynamic composition handlers
@event_handler("agent:update_composition")
async def handle_update_composition(data: AgentUpdateCompositionData) -> Dict[str, Any]:
    """Handle agent composition update request."""
    agent_id = data.get("agent_id")
    new_composition = data.get("new_composition")
    reason = data.get("reason", "Adaptation required")
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    if not new_composition:
        return {"error": "new_composition required"}
    
    if agent_id not in agents:
        return {"error": f"Agent {agent_id} not found"}
    
    # Check if agent can self-modify
    agent_info = agents[agent_id]
    current_config = agent_info.get("config", {})
    
    if not event_emitter:
        return {"error": "Event emitter not available"}
    
    # First, check if current composition allows modification
    current_comp = agent_info.get("composition", agent_info.get("profile"))
    if current_comp:
        # Get composition metadata
        comp_result = await event_emitter("composition:get", {
            "name": current_comp
        })
        
        if comp_result and isinstance(comp_result, list):
            comp_result = comp_result[0] if comp_result else {}
        
        if comp_result and comp_result.get("status") == "success":
            metadata = comp_result["composition"].get("metadata", {})
            if not metadata.get("self_modifiable", False):
                return {
                    "error": "Current composition does not allow self-modification",
                    "status": "denied"
                }
    
    # Compose new profile
    compose_result = await event_emitter("composition:profile", {
        "name": new_composition,
        "variables": {
            "agent_id": agent_id,
            "previous_role": current_config.get("role"),
            "adaptation_reason": reason
        }
    })
    
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
                "prompt": new_profile.get("composed_prompt")
            })
        
        logger.info(f"Agent {agent_id} updated composition to {new_composition}")
        
        return {
            "status": "updated",
            "agent_id": agent_id,
            "new_composition": new_composition,
            "new_capabilities": agent_info["config"]["capabilities"]
        }
    else:
        return {
            "error": f"Failed to compose new profile: {compose_result.get('error', 'Unknown error')}",
            "status": "failed"
        }


@event_handler("agent:discover_peers")
async def handle_discover_peers(data: AgentDiscoverPeersData) -> Dict[str, Any]:
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
    
    return {
        "status": "success",
        "requesting_agent": requesting_agent,
        "discovered_count": len(discovered),
        "peers": discovered
    }


@event_handler("agent:negotiate_roles")
async def handle_negotiate_roles(data: AgentNegotiateRolesData) -> Dict[str, Any]:
    """Coordinate role negotiation between agents."""
    participants = data.get("participants", [])
    negotiation_type = data.get("type", "collaborative")
    context = data.get("context", {})
    
    if not participants or len(participants) < 2:
        return {"error": "At least 2 participants required for negotiation"}
    
    # Verify all participants exist
    for agent_id in participants:
        if agent_id not in agents:
            return {"error": f"Agent {agent_id} not found"}
    
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
                "context": context,
                "your_current_role": agent_info.get("config", {}).get("role"),
                "your_capabilities": agent_info.get("config", {}).get("capabilities", [])
            })
    
    logger.info(f"Started role negotiation {negotiation_id} with {len(participants)} agents")
    
    return {
        "status": "initiated",
        "negotiation_id": negotiation_id,
        "participants": participants,
        "type": negotiation_type
    }


@event_handler("agent:needs_continuation")
async def handle_agent_needs_continuation(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle agent continuation requests for step-wise execution."""
    # Extract agent_id from event metadata
    agent_id = data.get("_agent_id")  # This is set by event extraction
    if not agent_id:
        return {"error": "No agent_id in continuation request"}
    
    if agent_id not in agents:
        return {"error": f"Agent {agent_id} not found"}
    
    agent_info = agents[agent_id]
    queue = agent_info.get("message_queue")
    
    if not queue:
        return {"error": f"No message queue for agent {agent_id}"}
    
    # Queue a continuation message
    reason = data.get("reason", "Continue with next step")
    await queue.put({
        "type": "completion",
        "prompt": f"Continue with: {reason}",
        "request_id": f"cont_{uuid.uuid4().hex[:8]}",
        "timestamp": timestamp_utc()
    })
    
    logger.info(f"Queued continuation for agent {agent_id}: {reason}")
    
    return {
        "status": "queued",
        "agent_id": agent_id,
        "reason": reason
    }


