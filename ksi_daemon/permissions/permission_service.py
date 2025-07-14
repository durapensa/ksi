#!/usr/bin/env python3
"""
Permission Service Module - Event-Based Version

Provides permission resolution, validation, and sandbox management for agents.
Integrates with the composition system to apply permissions from profiles.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, TypedDict, Literal
from typing_extensions import NotRequired, Required

from ksi_common.agent_permissions import (
    PermissionManager, AgentPermissions, PermissionLevel,
    ToolPermissions, FilesystemPermissions, ResourceLimits, Capabilities
)
from ksi_common.sandbox_manager import (
    SandboxManager, SandboxConfig, SandboxMode
)
from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_common.event_parser import event_format_linter
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_daemon.event_system import event_handler

logger = get_bound_logger(__name__)

# Global instances
permission_manager: Optional[PermissionManager] = None
sandbox_manager: Optional[SandboxManager] = None


class SystemStartupData(TypedDict):
    """System startup configuration."""
    # No specific fields required for this handler
    pass


@event_handler("system:startup")
async def handle_startup(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Initialize the permission service."""
    global permission_manager, sandbox_manager
    
    data = event_format_linter(raw_data, SystemStartupData)
    
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
    
    return event_response_builder({"permission_service": {"loaded": True}}, context)


class PermissionGetProfileData(TypedDict):
    """Get details of a specific permission profile."""
    level: Required[str]  # Permission level/profile name (restricted, standard, trusted, researcher)


@event_handler("permission:get_profile")
async def handle_get_profile(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get details of a specific permission profile.
    
    Args:
        level (str): The permission level/profile name (one of: restricted, standard, trusted, researcher)
    
    Returns:
        profile: The permission profile details
    """
    data = event_format_linter(raw_data, PermissionGetProfileData)
    
    level = data.get("level")
    if not level:
        return error_response("Missing required parameter: level", context)
    
    profile = permission_manager.get_profile(level)
    if not profile:
        return error_response(f"Profile not found: {level}", context)
    
    return event_response_builder({
        "profile": profile.to_dict()
    }, context)


class PermissionSetAgentData(TypedDict):
    """Set permissions for an agent."""
    agent_id: Required[str]  # The agent ID to set permissions for
    profile: NotRequired[str]  # Base profile to use (default: restricted)
    permissions: NotRequired[Dict[str, Any]]  # Full permission object
    overrides: NotRequired[Dict[str, Any]]  # Permission overrides to apply


@event_handler("permission:set_agent")
async def handle_set_agent_permissions(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
    data = event_format_linter(raw_data, PermissionSetAgentData)
    
    agent_id = data.get("agent_id")
    if not agent_id:
        return error_response("Missing required parameter: agent_id", context)
    
    # Get permissions from data
    perm_data = data.get("permissions")
    if not perm_data:
        # Try to load from profile
        profile_level = data.get("profile", "restricted")
        profile = permission_manager.get_profile(profile_level)
        if not profile:
            return error_response(f"Profile not found: {profile_level}", context)
        permissions = profile
    else:
        # Create permissions from data
        try:
            permissions = AgentPermissions.from_dict(perm_data)
        except Exception as e:
            return error_response(f"Invalid permissions data: {str(e)}", context)
    
    # Apply any overrides
    overrides = data.get("overrides", {})
    if overrides:
        permissions = apply_permission_overrides(permissions, overrides)
    
    # Set permissions
    permission_manager.set_agent_permissions(agent_id, permissions)
    
    return event_response_builder({
        "agent_id": agent_id,
        "permissions": permissions.to_dict()
    }, context)


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


class PermissionValidateSpawnData(TypedDict):
    """Validate if originator can spawn construct with given permissions."""
    originator_id: Required[str]  # The originating agent ID
    construct_permissions: Required[Dict[str, Any]]  # The requested permissions for the construct agent


@event_handler("permission:validate_spawn")
async def handle_validate_spawn(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Validate if originator can spawn construct with given permissions.
    
    Args:
        originator_id (str): The originating agent ID
        construct_permissions (dict): The requested permissions for the construct agent
    
    Returns:
        valid: Whether the spawn is allowed
        originator_id: The originating agent ID
    """
    data = event_format_linter(raw_data, PermissionValidateSpawnData)
    
    originator_id = data.get("originator_id")
    construct_permissions = data.get("construct_permissions")
    
    if not originator_id or not construct_permissions:
        return error_response("Missing required parameters: originator_id, construct_permissions", context)
    
    try:
        construct_perms = AgentPermissions.from_dict(construct_permissions)
    except Exception as e:
        return error_response(f"Invalid construct permissions: {str(e)}", context)
    
    valid = permission_manager.validate_spawn_permissions(originator_id, construct_perms)
    
    return event_response_builder({
        "valid": valid,
        "originator_id": originator_id
    }, context)


class PermissionGetAgentData(TypedDict):
    """Get permissions for a specific agent."""
    agent_id: Required[str]  # The agent ID to query permissions for


@event_handler("permission:get_agent")
async def handle_get_agent_permissions(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get permissions for a specific agent.
    
    Args:
        agent_id (str): The agent ID to query permissions for
    
    Returns:
        agent_id: The agent ID
        permissions: The agent's permissions
    """
    data = event_format_linter(raw_data, PermissionGetAgentData)
    
    agent_id = data.get("agent_id")
    if not agent_id:
        return error_response("Missing required parameter: agent_id", context)
    
    permissions = permission_manager.get_agent_permissions(agent_id)
    if not permissions:
        return error_response(f"No permissions found for agent: {agent_id}", context)
    
    return event_response_builder({
        "agent_id": agent_id,
        "permissions": permissions.to_dict()
    }, context)


class PermissionRemoveAgentData(TypedDict):
    """Remove permissions for an agent."""
    agent_id: Required[str]  # The agent ID to remove permissions for


@event_handler("permission:remove_agent")
async def handle_remove_agent_permissions(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Remove permissions for an agent.
    
    Args:
        agent_id (str): The agent ID to remove permissions for
    
    Returns:
        agent_id: The agent ID
        status: Removal status (removed)
    """
    data = event_format_linter(raw_data, PermissionRemoveAgentData)
    
    agent_id = data.get("agent_id")
    if not agent_id:
        return error_response("Missing required parameter: agent_id", context)
    
    permission_manager.remove_agent_permissions(agent_id)
    
    return event_response_builder({
        "agent_id": agent_id,
        "status": "removed"
    }, context)


class PermissionListProfilesData(TypedDict):
    """List available permission profiles."""
    # No specific fields - returns all profiles
    pass


@event_handler("permission:list_profiles")
async def handle_list_profiles(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """List available permission profiles.
    
    Returns:
        profiles: Dictionary containing all permission profiles with their tools and capabilities
    """
    data = event_format_linter(raw_data, PermissionListProfilesData)
    
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
    
    return event_response_builder({"profiles": profiles}, context)


class SandboxCreateConfig(TypedDict):
    """Sandbox configuration."""
    mode: NotRequired[Literal['isolated', 'shared', 'readonly']]  # Sandbox isolation mode (default: isolated)
    originator_agent_id: NotRequired[str]  # Originator agent for nested sandboxes
    session_id: NotRequired[str]  # Session ID for shared sandboxes
    originator_share: NotRequired[str]  # Originator sharing mode
    session_share: NotRequired[bool]  # Enable session sharing


class SandboxCreateData(TypedDict):
    """Create a new sandbox for an agent."""
    agent_id: Required[str]  # The agent ID
    config: NotRequired[SandboxCreateConfig]  # Sandbox configuration


@event_handler("sandbox:create")
async def handle_create_sandbox(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a new sandbox for an agent.
    
    Args:
        agent_id (str): The agent ID
        config (dict): Sandbox configuration (optional)
            mode (str): Sandbox isolation mode (optional, default: isolated, allowed: isolated, shared, readonly)
            originator_agent_id (str): Originator agent for nested sandboxes (optional)
            session_id (str): Session ID for shared sandboxes (optional)
            originator_share (str): Originator sharing mode (optional)
            session_share (bool): Enable session sharing (optional)
    
    Returns:
        agent_id: The agent ID
        sandbox: The created sandbox details
    """
    data = event_format_linter(raw_data, SandboxCreateData)
    
    agent_id = data.get("agent_id")
    if not agent_id:
        return error_response("Missing required parameter: agent_id", context)
    
    # Get sandbox configuration
    config_data = data.get("config", {})
    sandbox_config = SandboxConfig(
        mode=SandboxMode(config_data.get("mode", "isolated")),
        originator_agent_id=config_data.get("originator_agent_id"),
        session_id=config_data.get("session_id"),
        originator_share=config_data.get("originator_share", "read_only"),
        session_share=config_data.get("session_share", False)
    )
    
    try:
        sandbox = sandbox_manager.create_sandbox(agent_id, sandbox_config)
        return event_response_builder({
            "agent_id": agent_id,
            "sandbox": sandbox.to_dict()
        }, context)
    except Exception as e:
        logger.error("Failed to create sandbox", agent_id=agent_id, error=str(e))
        return error_response(f"Failed to create sandbox: {str(e)}", context)


class SandboxGetData(TypedDict):
    """Get sandbox information for an agent."""
    agent_id: Required[str]  # The agent ID


@event_handler("sandbox:get")
async def handle_get_sandbox(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get sandbox information for an agent.
    
    Args:
        agent_id (str): The agent ID
    
    Returns:
        agent_id: The agent ID
        sandbox: The sandbox details
    """
    data = event_format_linter(raw_data, SandboxGetData)
    
    agent_id = data.get("agent_id")
    if not agent_id:
        return error_response("Missing required parameter: agent_id", context)
    
    sandbox = sandbox_manager.get_sandbox(agent_id)
    if not sandbox:
        return error_response(f"No sandbox found for agent: {agent_id}", context)
    
    return event_response_builder({
        "agent_id": agent_id,
        "sandbox": sandbox.to_dict()
    }, context)


class SandboxRemoveData(TypedDict):
    """Remove an agent's sandbox."""
    agent_id: Required[str]  # The agent ID
    force: NotRequired[bool]  # Force removal even with nested children (default: false)


@event_handler("sandbox:remove")
async def handle_remove_sandbox(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Remove an agent's sandbox.
    
    Args:
        agent_id (str): The agent ID
        force (bool): Force removal even with nested children (optional, default: false)
    
    Returns:
        agent_id: The agent ID
        removed: Whether the sandbox was removed
    """
    data = event_format_linter(raw_data, SandboxRemoveData)
    
    agent_id = data.get("agent_id")
    if not agent_id:
        return error_response("Missing required parameter: agent_id", context)
    
    force = data.get("force", False)
    success = sandbox_manager.remove_sandbox(agent_id, force=force)
    
    return event_response_builder({
        "agent_id": agent_id,
        "removed": success
    }, context)


class SandboxListData(TypedDict):
    """List all active sandboxes."""
    # No specific fields - returns all sandboxes
    pass


@event_handler("sandbox:list")
async def handle_list_sandboxes(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """List all active sandboxes.
    
    Returns:
        sandboxes: List of active sandbox details
        count: Total number of sandboxes
    """
    data = event_format_linter(raw_data, SandboxListData)
    
    sandboxes = sandbox_manager.list_sandboxes()
    
    return event_response_builder({
        "sandboxes": [s.to_dict() for s in sandboxes],
        "count": len(sandboxes)
    }, context)


class SandboxStatsData(TypedDict):
    """Get sandbox statistics."""
    # No specific fields - returns overall stats
    pass


@event_handler("sandbox:stats")
async def handle_sandbox_stats(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get sandbox statistics.
    
    Returns:
        stats: Sandbox usage statistics
    """
    data = event_format_linter(raw_data, SandboxStatsData)
    
    stats = sandbox_manager.get_sandbox_stats()
    return event_response_builder({"stats": stats}, context)


