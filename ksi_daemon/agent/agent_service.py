#!/usr/bin/env python3
"""
Agent Service Module - Event-Based Version

Provides agent management without complex inheritance.
Handles agent lifecycle, identities, and routing through events.
Uses composition service for all profile/configuration needs.
"""

import asyncio
import json
import uuid
from typing import Any, Dict, TypedDict

from typing_extensions import NotRequired

from ksi_common import format_for_logging
from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import event_handler, get_router
from ksi_daemon.mcp import mcp_config_manager

# Module state
logger = get_bound_logger("agent_service", version="2.0.0")
agents: Dict[str, Dict[str, Any]] = {}  # agent_id -> agent_info
identities: Dict[str, Dict[str, Any]] = {}  # agent_id -> identity_info
agent_threads: Dict[str, asyncio.Task] = {}  # agent_id -> task

# Storage paths
identity_storage_path = config.identity_storage_path

# Event emitter reference (set during context)
event_emitter = None


# Per-plugin TypedDict definitions (optional type safety)
class AgentTerminateData(TypedDict):
    """Type-safe data for agent:terminate."""
    agent_id: str
    force: NotRequired[bool]

class AgentListData(TypedDict):
    """Type-safe data for agent:list."""
    status: NotRequired[str]

class AgentSendMessageData(TypedDict):
    """Type-safe data for agent:send_message."""
    agent_id: str
    message: Dict[str, Any]


# Helper functions
def load_identities():
    """Load agent identities from disk."""
    if identity_storage_path.exists():
        try:
            with open(identity_storage_path, 'r') as f:
                loaded_identities = json.load(f)
            if loaded_identities:
                identities.update(loaded_identities)
                logger.info(f"Loaded {len(identities)} agent identities")
        except Exception as e:
            logger.error(f"Failed to load identities: {e}")


def save_identities():
    """Save agent identities to disk."""
    try:
        # Ensure parent directory exists
        identity_storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(identity_storage_path, 'w') as f:
            json.dump(identities, f, indent=2)
        logger.debug(f"Saved {len(identities)} identities")
    except Exception as e:
        logger.error(f"Failed to save identities: {e}")


# System event handlers
@event_handler("system:context")
async def handle_context(context: Dict[str, Any]) -> None:
    """Receive plugin context with event emitter."""
    global event_emitter
    # Get router for event emission
    router = get_router()
    event_emitter = router.emit
    logger.info("Agent service received context, event_emitter configured")


@event_handler("system:startup")
async def handle_startup(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize agent service on startup."""
    load_identities()
    
    logger.info(f"Agent service started - agents: {len(agents)}, "
                f"identities: {len(identities)}")
    
    return {
        "status": "agent_service_ready",
        "agents": len(agents),
        "identities": len(identities)
    }


@event_handler("system:shutdown")
async def handle_shutdown(data: Dict[str, Any]) -> None:
    """Clean up on shutdown."""
    # Cancel all agent threads
    for agent_id, task in list(agent_threads.items()):
        task.cancel()
    
    # Save identities
    save_identities()
    
    logger.info(f"Agent service stopped - {len(agents)} agents, "
                f"{len(identities)} identities")


# Agent lifecycle handlers
@event_handler("agent:spawn")
async def handle_spawn_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """Spawn a new agent thread with optional profile."""
    agent_id = data.get("agent_id") or f"agent_{uuid.uuid4().hex[:8]}"
    profile_name = data.get("profile") or data.get("profile_name")
    composition_name = data.get("composition")  # Direct composition reference
    session_id = data.get("session_id")
    
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
            # Extract config from composed profile
            agent_config = {
                "model": profile.get("model", "sonnet"),
                "capabilities": profile.get("capabilities", []),
                "role": profile.get("role", "assistant"),
                "enable_tools": profile.get("enable_tools", False),
                "tools": profile.get("tools", [])
            }
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
        "session_id": session_id,
        "message_queue": asyncio.Queue(),
        "permission_profile": permission_profile,
        "sandbox_dir": sandbox_dir,
        "mcp_config_path": str(mcp_config_path) if mcp_config_path else None,
        "conversation_id": conversation_id if 'conversation_id' in locals() else None
    }
    
    # Register agent
    agents[agent_id] = agent_info
    
    # Start agent thread
    agent_task = asyncio.create_task(run_agent_thread(agent_id))
    agent_threads[agent_id] = agent_task
    
    logger.info(f"Created agent thread {agent_id} with composition {compose_name}")
    
    return {
        "agent_id": agent_id,
        "status": "created",
        "profile": profile_name,
        "composition": compose_name,
        "session_id": session_id,
        "config": agent_config
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
    
    # Remove from active agents
    del agents[agent_id]
    
    logger.info(f"Terminated agent {agent_id}")
    
    return {
        "agent_id": agent_id,
        "status": "terminated"
    }


@event_handler("agent:restart")
async def handle_restart_agent(data: Dict[str, Any]) -> Dict[str, Any]:
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
    spawn_data = {
        "agent_id": agent_id,
        "profile": agent_info.get("profile"),
        "config": agent_info.get("config", {}),
        "session_id": agent_info.get("session_id")
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
            # Get agent permissions
            perm_result = await event_emitter("permission:get_agent", {
                "agent_id": agent_id
            })
            
            permissions = {}
            if perm_result and "permissions" in perm_result:
                # Get allowed tools for claude-cli
                perms = perm_result["permissions"]
                if "tools" in perms and "allowed" in perms["tools"]:
                    permissions["allowed_tools"] = perms["tools"]["allowed"]
                permissions["profile"] = perms.get("level", "unknown")
            
            # Prepare completion request with permission context
            completion_data = {
                "prompt": prompt,
                "agent_id": agent_id,
                "client_id": agent_id,  # Use agent_id as client_id
                "session_id": agent_info.get("session_id"),
                "model": f"claude-cli/{agent_info.get('config', {}).get('model', 'sonnet')}",
                "priority": "normal",
                "request_id": f"{agent_id}_{message.get('request_id', uuid.uuid4().hex[:8])}"
            }
            
            # Add KSI parameters via extra_body for LiteLLM
            if agent_info.get("sandbox_dir") or permissions or agent_info.get("mcp_config_path"):
                completion_data["extra_body"] = {
                    "ksi": {
                        "agent_id": agent_id,
                        "sandbox_dir": agent_info.get("sandbox_dir"),
                        "permissions": permissions,
                        "session_id": agent_info.get("session_id"),
                        "mcp_config_path": agent_info.get("mcp_config_path")
                    }
                }
            
            await event_emitter("completion:async", completion_data)
    
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
async def handle_register_agent(data: Dict[str, Any]) -> Dict[str, Any]:
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
async def handle_unregister_agent(data: Dict[str, Any]) -> Dict[str, Any]:
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
        
        agent_list.append({
            "agent_id": agent_id,
            "status": info.get("status"),
            "profile": info.get("profile"),
            "created_at": info.get("created_at")
        })
    
    return {
        "agents": agent_list,
        "count": len(agent_list)
    }


# Identity handlers
@event_handler("agent:create_identity")
async def handle_create_identity(data: Dict[str, Any]) -> Dict[str, Any]:
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
    save_identities()
    
    logger.info(f"Created identity for agent {agent_id}")
    
    return {
        "agent_id": agent_id,
        "status": "created"
    }


@event_handler("agent:update_identity")
async def handle_update_identity(data: Dict[str, Any]) -> Dict[str, Any]:
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
    
    save_identities()
    
    logger.info(f"Updated identity for agent {agent_id}")
    
    return {
        "agent_id": agent_id,
        "status": "updated"
    }


@event_handler("agent:remove_identity")
async def handle_remove_identity(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove an agent identity."""
    agent_id = data.get("agent_id")
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    if agent_id in identities:
        del identities[agent_id]
        save_identities()
        logger.info(f"Removed identity for agent {agent_id}")
        return {"status": "removed"}
    
    return {"error": f"Identity for {agent_id} not found"}


@event_handler("agent:list_identities")
async def handle_list_identities(data: Dict[str, Any]) -> Dict[str, Any]:
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
async def handle_get_identity(data: Dict[str, Any]) -> Dict[str, Any]:
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
async def handle_route_task(data: Dict[str, Any]) -> Dict[str, Any]:
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
async def handle_get_capabilities(data: Dict[str, Any]) -> Dict[str, Any]:
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
    
    # Add message to agent's queue
    queue = agents[agent_id].get("message_queue")
    if queue:
        await queue.put(message)
        return {"status": "sent", "agent_id": agent_id}
    
    return {"error": "Agent message queue not available"}


@event_handler("agent:broadcast")
async def handle_broadcast(data: Dict[str, Any]) -> Dict[str, Any]:
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
async def handle_update_composition(data: Dict[str, Any]) -> Dict[str, Any]:
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
async def handle_discover_peers(data: Dict[str, Any]) -> Dict[str, Any]:
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
async def handle_negotiate_roles(data: Dict[str, Any]) -> Dict[str, Any]:
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


