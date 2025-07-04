#!/usr/bin/env python3
"""
Permission Service Module - Event-Based Version

Provides permission resolution, validation, and sandbox management for agents.
Integrates with the composition system to apply permissions from profiles.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any

from ksi_common.agent_permissions import (
    PermissionManager, AgentPermissions, PermissionLevel,
    ToolPermissions, FilesystemPermissions, ResourceLimits, Capabilities
)
from ksi_common.sandbox_manager import (
    SandboxManager, SandboxConfig, SandboxMode
)
from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import event_handler

logger = get_bound_logger(__name__)

# Global instances
permission_manager: Optional[PermissionManager] = None
sandbox_manager: Optional[SandboxManager] = None


@event_handler("system:startup")
async def handle_startup(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize the permission service."""
    global permission_manager, sandbox_manager
    
    logger.info("Initializing permission service")
    
    # Initialize managers
    permission_manager = PermissionManager(
        permissions_dir=config.permissions_dir
    )
    sandbox_manager = SandboxManager(
        sandbox_root=config.sandbox_dir
    )
    
    # Log loaded profiles
    profiles = list(permission_manager.profiles.keys())
    logger.info(f"Loaded {len(profiles)} permission profiles", profiles=[p.value for p in profiles])
    
    return {"permission_service": {"loaded": True}}


@event_handler("permission:get_profile")
async def handle_get_profile(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get details of a specific permission profile.
    
    Args:
        level (str): The permission level/profile name (one of: restricted, standard, trusted, researcher)
    
    Returns:
        profile: The permission profile details
    """
    level = data.get("level")
    if not level:
        return {"error": "Missing required parameter: level"}
    
    profile = permission_manager.get_profile(level)
    if not profile:
        return {"error": f"Profile not found: {level}"}
    
    return {
        "profile": profile.to_dict()
    }


@event_handler("permission:set_agent")
async def handle_set_agent_permissions(data: Dict[str, Any]) -> Dict[str, Any]:
    """Set permissions for an agent.
    
    Args:
        agent_id (str): The agent ID to set permissions for
        profile (str): Base profile to use (optional, defaults: restricted)
        permissions (dict): Full permission object (optional)
        overrides (dict): Permission overrides to apply (optional)
    
    Returns:
        agent_id: The agent ID
        permissions: The applied permissions
    """
    agent_id = data.get("agent_id")
    if not agent_id:
        return {"error": "Missing required parameter: agent_id"}
    
    # Get permissions from data
    perm_data = data.get("permissions")
    if not perm_data:
        # Try to load from profile
        profile_level = data.get("profile", "restricted")
        profile = permission_manager.get_profile(profile_level)
        if not profile:
            return {"error": f"Profile not found: {profile_level}"}
        permissions = profile
    else:
        # Create permissions from data
        try:
            permissions = AgentPermissions.from_dict(perm_data)
        except Exception as e:
            return {"error": f"Invalid permissions data: {str(e)}"}
    
    # Apply any overrides
    overrides = data.get("overrides", {})
    if overrides:
        permissions = apply_permission_overrides(permissions, overrides)
    
    # Set permissions
    permission_manager.set_agent_permissions(agent_id, permissions)
    
    return {
        "agent_id": agent_id,
        "permissions": permissions.to_dict()
    }


def apply_permission_overrides(permissions: AgentPermissions, overrides: dict) -> AgentPermissions:
    """Apply permission overrides to a base permission set"""
    # Create a mutable copy
    perm_dict = permissions.to_dict()
    
    # Apply tool overrides
    if "tools" in overrides:
        tool_overrides = overrides["tools"]
        if "allowed_add" in tool_overrides:
            # Add to allowed tools
            current_allowed = perm_dict["tools"]["allowed"] or []
            perm_dict["tools"]["allowed"] = list(set(current_allowed + tool_overrides["allowed_add"]))
        
        if "allowed_remove" in tool_overrides:
            # Remove from allowed tools
            current_allowed = perm_dict["tools"]["allowed"] or []
            perm_dict["tools"]["allowed"] = [t for t in current_allowed if t not in tool_overrides["allowed_remove"]]
        
        if "disallowed_add" in tool_overrides:
            # Add to disallowed tools
            current_disallowed = perm_dict["tools"]["disallowed"] or []
            perm_dict["tools"]["disallowed"] = list(set(current_disallowed + tool_overrides["disallowed_add"]))
    
    # Apply filesystem overrides
    if "filesystem" in overrides:
        fs_overrides = overrides["filesystem"]
        if "read_paths_add" in fs_overrides:
            perm_dict["filesystem"]["read_paths"] = list(set(
                perm_dict["filesystem"]["read_paths"] + fs_overrides["read_paths_add"]
            ))
        if "write_paths_add" in fs_overrides:
            perm_dict["filesystem"]["write_paths"] = list(set(
                perm_dict["filesystem"]["write_paths"] + fs_overrides["write_paths_add"]
            ))
    
    # Apply resource overrides (take maximum of base and override)
    if "resources" in overrides:
        for key, value in overrides["resources"].items():
            if key in perm_dict["resources"]:
                perm_dict["resources"][key] = max(perm_dict["resources"][key], value)
    
    # Apply capability overrides
    if "capabilities" in overrides:
        perm_dict["capabilities"].update(overrides["capabilities"])
    
    # Create new permissions object
    return AgentPermissions.from_dict(perm_dict)


@event_handler("permission:validate_spawn")
async def handle_validate_spawn(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate if parent can spawn child with given permissions.
    
    Args:
        parent_id (str): The parent agent ID
        child_permissions (dict): The requested permissions for the child agent
    
    Returns:
        valid: Whether the spawn is allowed
        parent_id: The parent agent ID
    """
    parent_id = data.get("parent_id")
    child_permissions = data.get("child_permissions")
    
    if not parent_id or not child_permissions:
        return {"error": "Missing required parameters: parent_id, child_permissions"}
    
    try:
        child_perms = AgentPermissions.from_dict(child_permissions)
    except Exception as e:
        return {"error": f"Invalid child permissions: {str(e)}"}
    
    valid = permission_manager.validate_spawn_permissions(parent_id, child_perms)
    
    return {
        "valid": valid,
        "parent_id": parent_id
    }


@event_handler("permission:get_agent")
async def handle_get_agent_permissions(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get permissions for a specific agent.
    
    Args:
        agent_id (str): The agent ID to query permissions for
    
    Returns:
        agent_id: The agent ID
        permissions: The agent's permissions
    """
    agent_id = data.get("agent_id")
    if not agent_id:
        return {"error": "Missing required parameter: agent_id"}
    
    permissions = permission_manager.get_agent_permissions(agent_id)
    if not permissions:
        return {"error": f"No permissions found for agent: {agent_id}"}
    
    return {
        "agent_id": agent_id,
        "permissions": permissions.to_dict()
    }


@event_handler("permission:remove_agent")
async def handle_remove_agent_permissions(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove permissions for an agent.
    
    Args:
        agent_id (str): The agent ID to remove permissions for
    
    Returns:
        agent_id: The agent ID
        status: Removal status (removed)
    """
    agent_id = data.get("agent_id")
    if not agent_id:
        return {"error": "Missing required parameter: agent_id"}
    
    permission_manager.remove_agent_permissions(agent_id)
    
    return {
        "agent_id": agent_id,
        "status": "removed"
    }


@event_handler("permission:list_profiles")
async def handle_list_profiles(data: Dict[str, Any]) -> Dict[str, Any]:
    """List available permission profiles.
    
    Returns:
        profiles: Dictionary containing all permission profiles with their tools and capabilities
    """
    profiles = {}
    for level, profile in permission_manager.profiles.items():
        profiles[level.value] = {
            "level": level.value,
            "tools": {
                "allowed": profile.tools.allowed,
                "disallowed": profile.tools.disallowed
            },
            "capabilities": profile.capabilities.to_dict()
        }
    
    return {"profiles": profiles}


@event_handler("sandbox:create")
async def handle_create_sandbox(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new sandbox for an agent.
    
    Args:
        agent_id (str): The agent ID
        config (dict): Sandbox configuration (optional)
            mode (str): Sandbox isolation mode (optional, default: isolated, allowed: isolated, shared, readonly)
            parent_agent_id (str): Parent agent for nested sandboxes (optional)
            session_id (str): Session ID for shared sandboxes (optional)
            parent_share (str): Parent sharing mode (optional)
            session_share (bool): Enable session sharing (optional)
    
    Returns:
        agent_id: The agent ID
        sandbox: The created sandbox details
    """
    agent_id = data.get("agent_id")
    if not agent_id:
        return {"error": "Missing required parameter: agent_id"}
    
    # Get sandbox configuration
    config_data = data.get("config", {})
    sandbox_config = SandboxConfig(
        mode=SandboxMode(config_data.get("mode", "isolated")),
        parent_agent_id=config_data.get("parent_agent_id"),
        session_id=config_data.get("session_id"),
        parent_share=config_data.get("parent_share", "read_only"),
        session_share=config_data.get("session_share", False)
    )
    
    try:
        sandbox = sandbox_manager.create_sandbox(agent_id, sandbox_config)
        return {
            "agent_id": agent_id,
            "sandbox": sandbox.to_dict()
        }
    except Exception as e:
        logger.error("Failed to create sandbox", agent_id=agent_id, error=str(e))
        return {"error": f"Failed to create sandbox: {str(e)}"}


@event_handler("sandbox:get")
async def handle_get_sandbox(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get sandbox information for an agent.
    
    Args:
        agent_id (str): The agent ID
    
    Returns:
        agent_id: The agent ID
        sandbox: The sandbox details
    """
    agent_id = data.get("agent_id")
    if not agent_id:
        return {"error": "Missing required parameter: agent_id"}
    
    sandbox = sandbox_manager.get_sandbox(agent_id)
    if not sandbox:
        return {"error": f"No sandbox found for agent: {agent_id}"}
    
    return {
        "agent_id": agent_id,
        "sandbox": sandbox.to_dict()
    }


@event_handler("sandbox:remove")
async def handle_remove_sandbox(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove an agent's sandbox.
    
    Args:
        agent_id (str): The agent ID
        force (bool): Force removal even with nested children (optional, default: false)
    
    Returns:
        agent_id: The agent ID
        removed: Whether the sandbox was removed
    """
    agent_id = data.get("agent_id")
    if not agent_id:
        return {"error": "Missing required parameter: agent_id"}
    
    force = data.get("force", False)
    success = sandbox_manager.remove_sandbox(agent_id, force=force)
    
    return {
        "agent_id": agent_id,
        "removed": success
    }


@event_handler("sandbox:list")
async def handle_list_sandboxes(data: Dict[str, Any]) -> Dict[str, Any]:
    """List all active sandboxes.
    
    Returns:
        sandboxes: List of active sandbox details
        count: Total number of sandboxes
    """
    sandboxes = sandbox_manager.list_sandboxes()
    
    return {
        "sandboxes": [s.to_dict() for s in sandboxes],
        "count": len(sandboxes)
    }


@event_handler("sandbox:stats")
async def handle_sandbox_stats(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get sandbox statistics.
    
    Returns:
        stats: Sandbox usage statistics
    """
    stats = sandbox_manager.get_sandbox_stats()
    return {"stats": stats}


