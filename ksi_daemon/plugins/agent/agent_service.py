#!/usr/bin/env python3
"""
Agent Service Plugin

Provides agent management as a plugin service.
Handles agent lifecycle, profiles, identities, and routing through events.
"""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from datetime import datetime
import logging

from ...plugin_base import BasePlugin, hookimpl
from ...plugin_types import PluginMetadata, PluginCapabilities
from ...timestamp_utils import TimestampManager
from ...config import config
from ...file_operations import FileOperations

logger = logging.getLogger(__name__)


class AgentServicePlugin(BasePlugin):
    """Service plugin for agent management."""
    
    def __init__(self):
        super().__init__(
            metadata=PluginMetadata(
                name="agent_service",
                version="1.0.0",
                description="Agent management service with profiles and identities",
                author="KSI Team"
            ),
            capabilities=PluginCapabilities(
                event_namespaces=["/agent"],
                commands=[
                    # Agent lifecycle
                    "agent:spawn", "agent:terminate", "agent:restart",
                    # Agent registry
                    "agent:register", "agent:unregister", "agent:list",
                    # Agent profiles  
                    "agent:load_profile", "agent:save_profile", "agent:list_profiles",
                    # Agent identities
                    "agent:create_identity", "agent:update_identity", "agent:remove_identity",
                    "agent:list_identities", "agent:get_identity",
                    # Agent routing
                    "agent:route_task", "agent:get_capabilities",
                    # Agent messaging
                    "agent:send_message", "agent:broadcast",
                    # Agent state
                    "agent:get_state", "agent:update_state"
                ],
                provides_services=["agent_management", "agent_profiles", "agent_identities", "task_routing"]
            )
        )
        
        # Agent registries
        self.agents: Dict[str, Dict[str, Any]] = {}  # agent_id -> agent_info
        self.identities: Dict[str, Dict[str, Any]] = {}  # agent_id -> identity_info
        self.profiles: Dict[str, Dict[str, Any]] = {}  # profile_name -> profile_data
        
        # Plugin context
        self._event_bus = None
        self._completion_service = None
        self._state_service = None
        
        # Storage paths
        self.agent_profiles_dir = Path(config.agent_profiles_dir)
        self.agent_profiles_dir.mkdir(parents=True, exist_ok=True)
        self.identity_storage_path = config.identity_storage_path
        
        # Load persisted data
        self._load_profiles()
        self._load_identities()
    
    @hookimpl
    def ksi_startup(self):
        """Initialize agent service on startup."""
        logger.info("Agent service plugin starting")
        
        return {
            "status": "agent_service_ready",
            "agents": len(self.agents),
            "profiles": len(self.profiles),
            "identities": len(self.identities)
        }
    
    @hookimpl
    def ksi_plugin_context(self, context):
        """Receive plugin context with dependencies."""
        self._event_bus = context.get("event_bus")
        
        # Get references to other services we depend on
        services = context.get("services", {})
        self._completion_service = services.get("completion")
        self._state_service = services.get("state")
    
    @hookimpl
    def ksi_handle_event(self, event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
        """Handle agent-related events."""
        
        # Agent lifecycle events
        if event_name == "agent:spawn":
            return self._handle_spawn_agent(data)
        
        elif event_name == "agent:terminate":
            return self._handle_terminate_agent(data)
        
        elif event_name == "agent:restart":
            return self._handle_restart_agent(data)
        
        # Agent registry events
        elif event_name == "agent:register":
            return self._handle_register_agent(data)
        
        elif event_name == "agent:unregister":
            return self._handle_unregister_agent(data)
        
        elif event_name == "agent:list":
            return self._handle_list_agents(data)
        
        # Profile events
        elif event_name == "agent:load_profile":
            return self._handle_load_profile(data)
        
        elif event_name == "agent:save_profile":
            return self._handle_save_profile(data)
        
        elif event_name == "agent:list_profiles":
            return self._handle_list_profiles(data)
        
        # Identity events  
        elif event_name == "agent:create_identity":
            return self._handle_create_identity(data)
        
        elif event_name == "agent:update_identity":
            return self._handle_update_identity(data)
        
        elif event_name == "agent:remove_identity":
            return self._handle_remove_identity(data)
        
        elif event_name == "agent:list_identities":
            return self._handle_list_identities(data)
        
        elif event_name == "agent:get_identity":
            return self._handle_get_identity(data)
        
        # Task routing
        elif event_name == "agent:route_task":
            return self._handle_route_task(data)
        
        elif event_name == "agent:get_capabilities":
            return self._handle_get_capabilities(data)
        
        # Agent messaging
        elif event_name == "agent:send_message":
            return self._handle_send_message(data)
        
        elif event_name == "agent:broadcast":
            return self._handle_broadcast(data)
        
        # Agent state
        elif event_name == "agent:get_state":
            return self._handle_get_state(data)
        
        elif event_name == "agent:update_state":
            return self._handle_update_state(data)
        
        # Handle internal events
        elif event_name.startswith("agent:"):
            logger.debug(f"Unhandled agent event: {event_name}")
        
        return None
    
    @hookimpl
    def ksi_shutdown(self):
        """Clean up on shutdown."""
        logger.info("Agent service shutting down")
        
        # Save identities
        self._save_identities()
        
        # Terminate all active agents gracefully
        for agent_id in list(self.agents.keys()):
            self._terminate_agent(agent_id)
    
    # Agent lifecycle methods
    
    async def _handle_spawn_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Spawn a new agent process."""
        profile_name = data.get("profile_name")
        agent_id = data.get("agent_id") or f"{profile_name}_{uuid.uuid4().hex[:8]}"
        task = data.get("task", "")
        context = data.get("context", "")
        
        # Load profile
        profile = self.profiles.get(profile_name)
        if not profile:
            return {"error": f"Profile '{profile_name}' not found"}
        
        # Check if agent already exists
        if agent_id in self.agents:
            return {"error": f"Agent '{agent_id}' already exists"}
        
        # Request completion service to spawn Claude process
        if self._completion_service:
            spawn_event = await self._event_bus.emit(
                "completion:spawn_agent",
                {
                    "agent_id": agent_id,
                    "profile": profile,
                    "task": task,
                    "context": context
                }
            )
            
            if spawn_event and spawn_event.get("process_id"):
                # Register agent
                self.agents[agent_id] = {
                    "agent_id": agent_id,
                    "process_id": spawn_event["process_id"],
                    "profile": profile_name,
                    "role": profile.get("role", profile_name),
                    "capabilities": profile.get("capabilities", []),
                    "status": "active",
                    "created_at": TimestampManager.timestamp_utc(),
                    "task": task
                }
                
                # Emit agent spawned event
                await self._event_bus.emit(
                    "agent:spawned",
                    {"agent_id": agent_id, "profile": profile_name}
                )
                
                return {"agent_id": agent_id, "status": "spawned"}
        
        return {"error": "Failed to spawn agent process"}
    
    def _handle_terminate_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Terminate an agent."""
        agent_id = data.get("agent_id")
        
        if agent_id not in self.agents:
            return {"error": f"Agent '{agent_id}' not found"}
        
        return self._terminate_agent(agent_id)
    
    def _terminate_agent(self, agent_id: str) -> Dict[str, Any]:
        """Internal method to terminate an agent."""
        agent = self.agents.get(agent_id)
        if not agent:
            return {"error": f"Agent '{agent_id}' not found"}
        
        # Update status
        agent["status"] = "terminated"
        agent["terminated_at"] = TimestampManager.timestamp_utc()
        
        # Remove from active agents
        del self.agents[agent_id]
        
        # Emit termination event
        if self._event_bus:
            asyncio.create_task(
                self._event_bus.emit(
                    "agent:terminated",
                    {"agent_id": agent_id}
                )
            )
        
        return {"agent_id": agent_id, "status": "terminated"}
    
    async def _handle_restart_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Restart an agent."""
        agent_id = data.get("agent_id")
        
        agent = self.agents.get(agent_id)
        if not agent:
            return {"error": f"Agent '{agent_id}' not found"}
        
        # Store agent info
        profile_name = agent["profile"]
        task = agent.get("task", "")
        
        # Terminate existing agent
        self._terminate_agent(agent_id)
        
        # Spawn new instance
        return await self._handle_spawn_agent({
            "agent_id": agent_id,
            "profile_name": profile_name,
            "task": task
        })
    
    # Agent registry methods
    
    def _handle_register_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Register an agent manually."""
        agent_id = data.get("agent_id")
        agent_info = data.get("agent_info", {})
        
        if not agent_id:
            return {"error": "agent_id is required"}
        
        if agent_id in self.agents:
            return {"error": f"Agent '{agent_id}' already registered"}
        
        # Register agent
        self.agents[agent_id] = {
            **agent_info,
            "agent_id": agent_id,
            "status": "active",
            "registered_at": TimestampManager.timestamp_utc()
        }
        
        return {"agent_id": agent_id, "status": "registered"}
    
    def _handle_unregister_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Unregister an agent."""
        agent_id = data.get("agent_id")
        
        if agent_id not in self.agents:
            return {"error": f"Agent '{agent_id}' not found"}
        
        del self.agents[agent_id]
        return {"agent_id": agent_id, "status": "unregistered"}
    
    def _handle_list_agents(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """List all registered agents."""
        status_filter = data.get("status")
        
        agents = []
        for agent_id, agent_info in self.agents.items():
            if status_filter and agent_info.get("status") != status_filter:
                continue
            agents.append(agent_info)
        
        return {"agents": agents, "count": len(agents)}
    
    # Profile methods
    
    def _load_profiles(self):
        """Load agent profiles from disk."""
        for profile_file in self.agent_profiles_dir.glob("*.json"):
            try:
                profile_name = profile_file.stem
                profile_data = FileOperations.load_json(profile_file)
                if profile_data:
                    self.profiles[profile_name] = profile_data
                    logger.info(f"Loaded agent profile: {profile_name}")
            except Exception as e:
                logger.error(f"Failed to load profile {profile_file}: {e}")
    
    def _handle_load_profile(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Load a specific agent profile."""
        profile_name = data.get("profile_name")
        
        if not profile_name:
            return {"error": "profile_name is required"}
        
        profile = self.profiles.get(profile_name)
        if profile:
            return {"profile": profile}
        
        # Try loading from disk if not in memory
        profile_path = self.agent_profiles_dir / f"{profile_name}.json"
        if profile_path.exists():
            profile = FileOperations.load_json(profile_path)
            if profile:
                self.profiles[profile_name] = profile
                return {"profile": profile}
        
        return {"error": f"Profile '{profile_name}' not found"}
    
    def _handle_save_profile(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Save an agent profile."""
        profile_name = data.get("profile_name")
        profile_data = data.get("profile_data")
        
        if not profile_name or not profile_data:
            return {"error": "profile_name and profile_data are required"}
        
        # Save to memory
        self.profiles[profile_name] = profile_data
        
        # Save to disk
        profile_path = self.agent_profiles_dir / f"{profile_name}.json"
        success = FileOperations.save_json(profile_path, profile_data)
        
        if success:
            return {"profile_name": profile_name, "status": "saved"}
        else:
            return {"error": "Failed to save profile"}
    
    def _handle_list_profiles(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """List available agent profiles."""
        profiles = []
        for name, profile in self.profiles.items():
            profiles.append({
                "name": name,
                "role": profile.get("role", "unknown"),
                "capabilities": profile.get("capabilities", []),
                "description": profile.get("description", "")
            })
        
        return {"profiles": profiles, "count": len(profiles)}
    
    # Identity methods
    
    def _load_identities(self):
        """Load agent identities from storage."""
        if self.identity_storage_path.exists():
            identities = FileOperations.load_json(self.identity_storage_path, {})
            self.identities = identities
            logger.info(f"Loaded {len(identities)} agent identities")
    
    def _save_identities(self):
        """Save agent identities to storage."""
        success = FileOperations.save_json(self.identity_storage_path, self.identities)
        if success:
            logger.debug("Agent identities saved")
        else:
            logger.error("Failed to save agent identities")
    
    def _handle_create_identity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new agent identity."""
        agent_id = data.get("agent_id")
        display_name = data.get("display_name")
        personality_traits = data.get("personality_traits", [])
        role = data.get("role", "general")
        appearance = data.get("appearance", {})
        
        if not agent_id:
            return {"error": "agent_id is required"}
        
        if agent_id in self.identities:
            return {"error": f"Identity for agent '{agent_id}' already exists"}
        
        # Generate identity
        identity_uuid = str(uuid.uuid4())
        
        # Default display name
        if not display_name:
            display_name = f"{role.title()}-{agent_id[-4:]}"
        
        # Default personality traits based on role
        if not personality_traits:
            personality_traits = self._generate_default_traits(role)
        
        # Default appearance
        if not appearance:
            appearance = self._generate_default_appearance(role)
        
        identity = {
            "identity_uuid": identity_uuid,
            "agent_id": agent_id,
            "display_name": display_name,
            "role": role,
            "personality_traits": personality_traits,
            "appearance": appearance,
            "created_at": TimestampManager.timestamp_utc(),
            "last_active": TimestampManager.timestamp_utc(),
            "conversation_count": 0,
            "sessions": [],
            "preferences": {
                "communication_style": "professional",
                "verbosity": "moderate",
                "formality": "balanced"
            },
            "stats": {
                "messages_sent": 0,
                "conversations_participated": 0,
                "tasks_completed": 0,
                "tools_used": []
            }
        }
        
        self.identities[agent_id] = identity
        self._save_identities()
        
        return {"identity": identity}
    
    def _handle_update_identity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an agent identity."""
        agent_id = data.get("agent_id")
        updates = data.get("updates", {})
        
        if not agent_id:
            return {"error": "agent_id is required"}
        
        if agent_id not in self.identities:
            return {"error": f"Identity for agent '{agent_id}' not found"}
        
        # Update identity
        identity = self.identities[agent_id]
        
        # Update allowed fields
        allowed_fields = [
            "display_name", "personality_traits", "appearance",
            "preferences", "stats"
        ]
        
        for field in allowed_fields:
            if field in updates:
                identity[field] = updates[field]
        
        identity["last_active"] = TimestampManager.timestamp_utc()
        
        self._save_identities()
        
        return {"identity": identity}
    
    def _handle_remove_identity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove an agent identity."""
        agent_id = data.get("agent_id")
        
        if not agent_id:
            return {"error": "agent_id is required"}
        
        if agent_id not in self.identities:
            return {"error": f"Identity for agent '{agent_id}' not found"}
        
        del self.identities[agent_id]
        self._save_identities()
        
        return {"agent_id": agent_id, "status": "removed"}
    
    def _handle_list_identities(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """List all agent identities."""
        identities = []
        for agent_id, identity in self.identities.items():
            identities.append({
                "agent_id": agent_id,
                "identity_uuid": identity["identity_uuid"],
                "display_name": identity["display_name"],
                "role": identity["role"],
                "created_at": identity["created_at"],
                "last_active": identity["last_active"]
            })
        
        return {"identities": identities, "count": len(identities)}
    
    def _handle_get_identity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Get a specific agent identity."""
        agent_id = data.get("agent_id")
        
        if not agent_id:
            return {"error": "agent_id is required"}
        
        identity = self.identities.get(agent_id)
        if identity:
            return {"identity": identity}
        else:
            return {"error": f"Identity for agent '{agent_id}' not found"}
    
    # Task routing methods
    
    async def _handle_route_task(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Route a task to the most suitable agent."""
        task = data.get("task")
        required_capabilities = data.get("required_capabilities", [])
        preferred_role = data.get("preferred_role")
        
        if not task:
            return {"error": "task is required"}
        
        # Find suitable agents
        candidates = []
        for agent_id, agent in self.agents.items():
            if agent.get("status") != "active":
                continue
            
            # Check role preference
            if preferred_role and agent.get("role") == preferred_role:
                candidates.append((agent_id, agent, 10))  # High priority
                continue
            
            # Check capabilities
            agent_capabilities = set(agent.get("capabilities", []))
            required_set = set(required_capabilities)
            
            if required_set.issubset(agent_capabilities):
                # Score based on capability match
                score = len(required_set.intersection(agent_capabilities))
                candidates.append((agent_id, agent, score))
        
        if not candidates:
            return {"error": "No suitable agent found for task"}
        
        # Sort by score and select best
        candidates.sort(key=lambda x: x[2], reverse=True)
        selected_agent_id, selected_agent, score = candidates[0]
        
        # Send task to selected agent
        if self._event_bus:
            await self._event_bus.emit(
                "agent:task_assigned",
                {
                    "agent_id": selected_agent_id,
                    "task": task,
                    "score": score
                }
            )
        
        return {
            "agent_id": selected_agent_id,
            "agent_info": selected_agent,
            "score": score
        }
    
    def _handle_get_capabilities(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Get capabilities of agents."""
        agent_id = data.get("agent_id")
        
        if agent_id:
            # Get specific agent capabilities
            agent = self.agents.get(agent_id)
            if not agent:
                return {"error": f"Agent '{agent_id}' not found"}
            
            return {
                "agent_id": agent_id,
                "capabilities": agent.get("capabilities", []),
                "role": agent.get("role")
            }
        else:
            # Get all capabilities across agents
            all_capabilities = set()
            role_capabilities = {}
            
            for agent in self.agents.values():
                capabilities = agent.get("capabilities", [])
                all_capabilities.update(capabilities)
                
                role = agent.get("role", "unknown")
                if role not in role_capabilities:
                    role_capabilities[role] = set()
                role_capabilities[role].update(capabilities)
            
            return {
                "all_capabilities": list(all_capabilities),
                "by_role": {
                    role: list(caps) 
                    for role, caps in role_capabilities.items()
                }
            }
    
    # Agent messaging methods
    
    async def _handle_send_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message to a specific agent."""
        target_agent = data.get("target_agent")
        sender_agent = data.get("sender_agent", "system")
        message = data.get("message")
        message_type = data.get("message_type", "text")
        
        if not target_agent or not message:
            return {"error": "target_agent and message are required"}
        
        if target_agent not in self.agents:
            return {"error": f"Target agent '{target_agent}' not found"}
        
        # Emit message event
        if self._event_bus:
            await self._event_bus.emit(
                "agent:message",
                {
                    "from": sender_agent,
                    "to": target_agent,
                    "message": message,
                    "message_type": message_type,
                    "timestamp": TimestampManager.timestamp_utc()
                }
            )
        
        return {"status": "sent", "to": target_agent}
    
    async def _handle_broadcast(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Broadcast a message to all active agents."""
        sender_agent = data.get("sender_agent", "system")
        message = data.get("message")
        message_type = data.get("message_type", "text")
        filter_role = data.get("filter_role")
        filter_capabilities = data.get("filter_capabilities", [])
        
        if not message:
            return {"error": "message is required"}
        
        # Find target agents
        targets = []
        for agent_id, agent in self.agents.items():
            if agent.get("status") != "active":
                continue
            
            # Apply filters
            if filter_role and agent.get("role") != filter_role:
                continue
            
            if filter_capabilities:
                agent_caps = set(agent.get("capabilities", []))
                required_caps = set(filter_capabilities)
                if not required_caps.issubset(agent_caps):
                    continue
            
            targets.append(agent_id)
        
        # Broadcast to targets
        if self._event_bus:
            for target in targets:
                await self._event_bus.emit(
                    "agent:message",
                    {
                        "from": sender_agent,
                        "to": target,
                        "message": message,
                        "message_type": message_type,
                        "broadcast": True,
                        "timestamp": TimestampManager.timestamp_utc()
                    }
                )
        
        return {"status": "broadcast", "recipients": targets, "count": len(targets)}
    
    # Agent state methods
    
    async def _handle_get_state(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Get agent state from state service."""
        agent_id = data.get("agent_id")
        key = data.get("key")
        
        if not agent_id:
            return {"error": "agent_id is required"}
        
        # Delegate to state service
        if self._state_service:
            state_event = await self._event_bus.emit(
                "state:get",
                {
                    "namespace": f"agent:{agent_id}",
                    "key": key
                }
            )
            return state_event or {"error": "Failed to get state"}
        
        return {"error": "State service not available"}
    
    async def _handle_update_state(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update agent state via state service."""
        agent_id = data.get("agent_id")
        key = data.get("key")
        value = data.get("value")
        
        if not agent_id or not key:
            return {"error": "agent_id and key are required"}
        
        # Delegate to state service
        if self._state_service:
            state_event = await self._event_bus.emit(
                "state:set",
                {
                    "namespace": f"agent:{agent_id}",
                    "key": key,
                    "value": value
                }
            )
            return state_event or {"error": "Failed to update state"}
        
        return {"error": "State service not available"}
    
    # Helper methods
    
    def _generate_default_traits(self, role: str) -> List[str]:
        """Generate default personality traits based on role."""
        trait_map = {
            "analyst": ["analytical", "detail-oriented", "methodical", "objective"],
            "creative": ["innovative", "imaginative", "expressive", "open-minded"],
            "coordinator": ["organized", "diplomatic", "collaborative", "efficient"],
            "researcher": ["curious", "thorough", "skeptical", "knowledgeable"],
            "general": ["helpful", "professional", "adaptable", "reliable"]
        }
        
        return trait_map.get(role, trait_map["general"])
    
    def _generate_default_appearance(self, role: str) -> Dict[str, Any]:
        """Generate default appearance based on role."""
        appearance_map = {
            "analyst": {
                "avatar_style": "professional",
                "color_scheme": ["blue", "gray"],
                "icon": "chart-line"
            },
            "creative": {
                "avatar_style": "artistic",
                "color_scheme": ["purple", "orange"],
                "icon": "palette"
            },
            "coordinator": {
                "avatar_style": "business",
                "color_scheme": ["green", "teal"],
                "icon": "users"
            },
            "researcher": {
                "avatar_style": "academic",
                "color_scheme": ["brown", "amber"],
                "icon": "book"
            },
            "general": {
                "avatar_style": "default",
                "color_scheme": ["blue", "white"],
                "icon": "user"
            }
        }
        
        return appearance_map.get(role, appearance_map["general"])


# Module-level marker for plugin discovery
ksi_plugin = AgentServicePlugin