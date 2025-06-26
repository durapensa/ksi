#!/usr/bin/env python3
"""
Agent Service Plugin

Provides agent management without complex inheritance.
Handles agent lifecycle, profiles, identities, and routing through events.
"""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from datetime import datetime
import logging
import pluggy

from ...plugin_utils import get_logger, plugin_metadata
from ksi_common import TimestampManager
from ...config import config
from ...file_operations import FileOperations

# Plugin metadata
plugin_metadata("agent_service", version="2.0.0",
                description="Simplified agent management service")

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Module state
logger = get_logger("agent_service")
agents: Dict[str, Dict[str, Any]] = {}  # agent_id -> agent_info
identities: Dict[str, Dict[str, Any]] = {}  # agent_id -> identity_info
profiles: Dict[str, Dict[str, Any]] = {}  # profile_name -> profile_data
agent_threads: Dict[str, asyncio.Task] = {}  # agent_id -> task

# Storage paths
agent_profiles_dir = Path(config.agent_profiles_dir)
agent_profiles_dir.mkdir(parents=True, exist_ok=True)
identity_storage_path = config.identity_storage_path

# Event emitter reference (set during context)
event_emitter = None


# Helper functions
def load_profiles():
    """Load agent profiles from disk."""
    for profile_file in agent_profiles_dir.glob("*.json"):
        try:
            profile_data = FileOperations.read_json_file(profile_file)
            if profile_data:
                profile_name = profile_file.stem
                profiles[profile_name] = profile_data
                logger.info(f"Loaded profile: {profile_name}")
        except Exception as e:
            logger.error(f"Failed to load profile {profile_file}: {e}")


def load_identities():
    """Load agent identities from disk."""
    if identity_storage_path.exists():
        try:
            loaded_identities = FileOperations.read_json_file(identity_storage_path)
            if loaded_identities:
                identities.update(loaded_identities)
                logger.info(f"Loaded {len(identities)} agent identities")
        except Exception as e:
            logger.error(f"Failed to load identities: {e}")


def save_identities():
    """Save agent identities to disk."""
    try:
        FileOperations.write_json_file(identity_storage_path, identities)
        logger.debug(f"Saved {len(identities)} identities")
    except Exception as e:
        logger.error(f"Failed to save identities: {e}")


# Hook implementations
@hookimpl
def ksi_startup(config):
    """Initialize agent service on startup."""
    load_profiles()
    load_identities()
    
    logger.info(f"Agent service started - agents: {len(agents)}, "
                f"profiles: {len(profiles)}, identities: {len(identities)}")
    
    return {
        "status": "agent_service_ready",
        "agents": len(agents),
        "profiles": len(profiles),
        "identities": len(identities)
    }


@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Handle agent-related events."""
    
    # Agent lifecycle events
    if event_name == "agent:spawn":
        return handle_spawn_agent(data)
    
    elif event_name == "agent:terminate":
        return handle_terminate_agent(data)
    
    elif event_name == "agent:restart":
        return handle_restart_agent(data)
    
    # Agent registry events
    elif event_name == "agent:register":
        return handle_register_agent(data)
    
    elif event_name == "agent:unregister":
        return handle_unregister_agent(data)
    
    elif event_name == "agent:list":
        return handle_list_agents(data)
    
    # Profile events
    elif event_name == "agent:load_profile":
        return handle_load_profile(data)
    
    elif event_name == "agent:save_profile":
        return handle_save_profile(data)
    
    elif event_name == "agent:list_profiles":
        return handle_list_profiles(data)
    
    # Identity events  
    elif event_name == "agent:create_identity":
        return handle_create_identity(data)
    
    elif event_name == "agent:update_identity":
        return handle_update_identity(data)
    
    elif event_name == "agent:remove_identity":
        return handle_remove_identity(data)
    
    elif event_name == "agent:list_identities":
        return handle_list_identities(data)
    
    elif event_name == "agent:get_identity":
        return handle_get_identity(data)
    
    # Task routing
    elif event_name == "agent:route_task":
        return handle_route_task(data)
    
    elif event_name == "agent:get_capabilities":
        return handle_get_capabilities(data)
    
    # Message handling
    elif event_name == "agent:send_message":
        return handle_send_message(data)
    
    elif event_name == "agent:broadcast":
        return handle_broadcast(data)
    
    return None


# Agent lifecycle handlers
def handle_spawn_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """Spawn a new agent thread with optional profile."""
    agent_id = data.get("agent_id") or f"agent_{uuid.uuid4().hex[:8]}"
    profile_name = data.get("profile")
    session_id = data.get("session_id")
    
    # Load profile if specified
    agent_config = {}
    if profile_name and profile_name in profiles:
        agent_config = profiles[profile_name].copy()
    
    # Override with provided config
    if "config" in data:
        agent_config.update(data["config"])
    
    # Create agent info
    agent_info = {
        "agent_id": agent_id,
        "profile": profile_name,
        "config": agent_config,
        "status": "initializing",
        "created_at": TimestampManager.format_for_logging(),
        "session_id": session_id,
        "message_queue": asyncio.Queue()
    }
    
    # Register agent
    agents[agent_id] = agent_info
    
    # Start agent thread
    agent_task = asyncio.create_task(run_agent_thread(agent_id))
    agent_threads[agent_id] = agent_task
    
    logger.info(f"Created agent thread {agent_id} with profile {profile_name}")
    
    return {
        "agent_id": agent_id,
        "status": "created",
        "profile": profile_name,
        "session_id": session_id
    }


def handle_terminate_agent(data: Dict[str, Any]) -> Dict[str, Any]:
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
    agent_info["terminated_at"] = TimestampManager.format_for_logging()
    
    # Remove from active agents
    del agents[agent_id]
    
    logger.info(f"Terminated agent {agent_id}")
    
    return {
        "agent_id": agent_id,
        "status": "terminated"
    }


def handle_restart_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """Restart an agent."""
    agent_id = data.get("agent_id")
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    if agent_id not in agents:
        return {"error": f"Agent {agent_id} not found"}
    
    # Get current agent info
    agent_info = agents[agent_id].copy()
    
    # Terminate existing
    terminate_result = handle_terminate_agent({"agent_id": agent_id})
    if "error" in terminate_result:
        return terminate_result
    
    # Spawn new with same config
    spawn_data = {
        "agent_id": agent_id,
        "profile": agent_info.get("profile"),
        "config": agent_info.get("config", {}),
        "session_id": agent_info.get("session_id")
    }
    
    return handle_spawn_agent(spawn_data)


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
        # Forward to completion service
        prompt = message.get("prompt", "")
        if prompt and event_emitter:
            await event_emitter("completion:request", {
                "prompt": prompt,
                "agent_id": agent_id,
                "session_id": agent_info.get("session_id"),
                "model": agent_info.get("config", {}).get("model", "sonnet")
            })
    
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
                    "timestamp": TimestampManager.format_for_logging()
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
                        "timestamp": TimestampManager.format_for_logging()
                    })


# Agent registry handlers
def handle_register_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """Register an external agent."""
    agent_id = data.get("agent_id")
    agent_info = data.get("info", {})
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    # Create registration info
    registration = {
        "agent_id": agent_id,
        "registered_at": TimestampManager.format_for_logging(),
        "status": "registered",
        **agent_info
    }
    
    agents[agent_id] = registration
    
    logger.info(f"Registered agent {agent_id}")
    
    return {
        "agent_id": agent_id,
        "status": "registered"
    }


def handle_unregister_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    """Unregister an agent."""
    agent_id = data.get("agent_id")
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    if agent_id in agents:
        del agents[agent_id]
        logger.info(f"Unregistered agent {agent_id}")
        return {"status": "unregistered"}
    
    return {"error": f"Agent {agent_id} not found"}


def handle_list_agents(data: Dict[str, Any]) -> Dict[str, Any]:
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


# Profile handlers
def handle_load_profile(data: Dict[str, Any]) -> Dict[str, Any]:
    """Load a specific profile."""
    profile_name = data.get("profile_name")
    
    if not profile_name:
        return {"error": "profile_name required"}
    
    profile_path = agent_profiles_dir / f"{profile_name}.json"
    
    if not profile_path.exists():
        return {"error": f"Profile {profile_name} not found"}
    
    try:
        profile_data = FileOperations.read_json_file(profile_path)
        if profile_data:
            profiles[profile_name] = profile_data
            return {
                "profile_name": profile_name,
                "profile": profile_data,
                "status": "loaded"
            }
    except Exception as e:
        return {"error": f"Failed to load profile: {e}"}
    
    return {"error": "Failed to load profile"}


def handle_save_profile(data: Dict[str, Any]) -> Dict[str, Any]:
    """Save a profile."""
    profile_name = data.get("profile_name")
    profile_data = data.get("profile")
    
    if not profile_name or not profile_data:
        return {"error": "profile_name and profile required"}
    
    profile_path = agent_profiles_dir / f"{profile_name}.json"
    
    try:
        FileOperations.write_json_file(profile_path, profile_data)
        profiles[profile_name] = profile_data
        logger.info(f"Saved profile {profile_name}")
        return {"status": "saved", "profile_name": profile_name}
    except Exception as e:
        return {"error": f"Failed to save profile: {e}"}


def handle_list_profiles(data: Dict[str, Any]) -> Dict[str, Any]:
    """List available profiles."""
    profile_list = []
    
    for name, profile in profiles.items():
        profile_list.append({
            "name": name,
            "description": profile.get("description", ""),
            "model": profile.get("model", ""),
            "capabilities": profile.get("capabilities", [])
        })
    
    return {
        "profiles": profile_list,
        "count": len(profile_list)
    }


# Identity handlers
def handle_create_identity(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new agent identity."""
    agent_id = data.get("agent_id") or f"agent_{uuid.uuid4().hex[:8]}"
    identity_data = data.get("identity", {})
    
    # Create identity
    identity = {
        "agent_id": agent_id,
        "created_at": TimestampManager.format_for_logging(),
        "updated_at": TimestampManager.format_for_logging(),
        **identity_data
    }
    
    identities[agent_id] = identity
    save_identities()
    
    logger.info(f"Created identity for agent {agent_id}")
    
    return {
        "agent_id": agent_id,
        "status": "created"
    }


def handle_update_identity(data: Dict[str, Any]) -> Dict[str, Any]:
    """Update an agent identity."""
    agent_id = data.get("agent_id")
    updates = data.get("updates", {})
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    if agent_id not in identities:
        return {"error": f"Identity for {agent_id} not found"}
    
    # Update identity
    identities[agent_id].update(updates)
    identities[agent_id]["updated_at"] = TimestampManager.format_for_logging()
    
    save_identities()
    
    logger.info(f"Updated identity for agent {agent_id}")
    
    return {
        "agent_id": agent_id,
        "status": "updated"
    }


def handle_remove_identity(data: Dict[str, Any]) -> Dict[str, Any]:
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


def handle_list_identities(data: Dict[str, Any]) -> Dict[str, Any]:
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


def handle_get_identity(data: Dict[str, Any]) -> Dict[str, Any]:
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
def handle_route_task(data: Dict[str, Any]) -> Dict[str, Any]:
    """Route a task to an appropriate agent."""
    task = data.get("task", {})
    requirements = task.get("requirements", [])
    
    # Simple routing: find first available agent
    for agent_id, info in agents.items():
        if info.get("status") == "ready":
            logger.info(f"Routing task to agent {agent_id}")
            return {
                "agent_id": agent_id,
                "status": "routed"
            }
    
    return {"error": "No available agents"}


def handle_get_capabilities(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get capabilities of an agent or all agents."""
    agent_id = data.get("agent_id")
    
    if agent_id:
        if agent_id not in agents:
            return {"error": f"Agent {agent_id} not found"}
        
        agent_info = agents[agent_id]
        profile_name = agent_info.get("profile")
        
        capabilities = []
        if profile_name and profile_name in profiles:
            capabilities = profiles[profile_name].get("capabilities", [])
        
        return {
            "agent_id": agent_id,
            "capabilities": capabilities
        }
    
    # Return all agent capabilities
    all_capabilities = {}
    for aid, info in agents.items():
        profile_name = info.get("profile")
        if profile_name and profile_name in profiles:
            all_capabilities[aid] = profiles[profile_name].get("capabilities", [])
    
    return {"capabilities": all_capabilities}


@hookimpl
def ksi_plugin_context(context):
    """Receive plugin context with event emitter."""
    global event_emitter
    event_emitter = context.get("emit_event")


@hookimpl
def ksi_shutdown():
    """Clean up on shutdown."""
    # Cancel all agent threads
    for agent_id, task in list(agent_threads.items()):
        task.cancel()
    
    # Save identities
    save_identities()
    
    logger.info(f"Agent service stopped - {len(agents)} agents, "
                f"{len(profiles)} profiles, {len(identities)} identities")
    
    return {
        "status": "agent_service_stopped",
        "agents": len(agents),
        "profiles": len(profiles),
        "identities": len(identities)
    }


# Message handling functions
def handle_send_message(data: Dict[str, Any]) -> Dict[str, Any]:
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
        asyncio.create_task(queue.put(message))
        return {"status": "sent", "agent_id": agent_id}
    
    return {"error": "Agent message queue not available"}


def handle_broadcast(data: Dict[str, Any]) -> Dict[str, Any]:
    """Broadcast a message to all agents."""
    message = data.get("message", {})
    sender = data.get("sender", "system")
    
    sent_count = 0
    for agent_id, agent_info in agents.items():
        queue = agent_info.get("message_queue")
        if queue:
            asyncio.create_task(queue.put({
                "type": "broadcast",
                "from": sender,
                **message
            }))
            sent_count += 1
    
    return {
        "status": "broadcast",
        "agents_reached": sent_count,
        "total_agents": len(agents)
    }


# Module-level marker for plugin discovery
ksi_plugin = True