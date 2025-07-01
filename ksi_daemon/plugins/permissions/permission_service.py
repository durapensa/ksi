"""
Permission service plugin for KSI.

Provides permission resolution, validation, and sandbox management for agents.
Integrates with the composition system to apply permissions from profiles.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml

import pluggy

from ksi_common.agent_permissions import (
    PermissionManager, AgentPermissions, PermissionLevel,
    ToolPermissions, FilesystemPermissions, ResourceLimits, Capabilities
)
from ksi_common.sandbox_manager import (
    SandboxManager, SandboxConfig, SandboxMode
)
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

hookimpl = pluggy.HookimplMarker("ksi")
logger = get_bound_logger(__name__)

# Global instances
permission_manager: Optional[PermissionManager] = None
sandbox_manager: Optional[SandboxManager] = None


@hookimpl
def ksi_startup(config):
    """Initialize the permission service"""
    global permission_manager, sandbox_manager
    
    logger.info("Initializing permission service")
    
    # Initialize managers
    permission_manager = PermissionManager(
        permissions_dir=Path("var/lib/permissions")
    )
    sandbox_manager = SandboxManager(
        sandbox_root=Path("var/sandbox")
    )
    
    # Log loaded profiles
    profiles = list(permission_manager.profiles.keys())
    logger.info(f"Loaded {len(profiles)} permission profiles", profiles=[p.value for p in profiles])
    
    return True


@hookimpl
def ksi_handle_event(event_name: str, data: dict, context: dict):
    """Handle permission-related events"""
    
    if event_name == "permission:get_profile":
        return handle_get_profile(data)
    
    elif event_name == "permission:set_agent":
        return handle_set_agent_permissions(data)
    
    elif event_name == "permission:validate_spawn":
        return handle_validate_spawn(data)
    
    elif event_name == "permission:get_agent":
        return handle_get_agent_permissions(data)
    
    elif event_name == "permission:remove_agent":
        return handle_remove_agent_permissions(data)
    
    elif event_name == "permission:list_profiles":
        return handle_list_profiles(data)
    
    elif event_name == "sandbox:create":
        return handle_create_sandbox(data)
    
    elif event_name == "sandbox:get":
        return handle_get_sandbox(data)
    
    elif event_name == "sandbox:remove":
        return handle_remove_sandbox(data)
    
    elif event_name == "sandbox:list":
        return handle_list_sandboxes(data)
    
    elif event_name == "sandbox:stats":
        return handle_sandbox_stats(data)
    
    return None


def handle_get_profile(data: dict) -> dict:
    """Get a permission profile by level"""
    level = data.get("level")
    if not level:
        return {"error": "Missing required parameter: level"}
    
    profile = permission_manager.get_profile(level)
    if not profile:
        return {"error": f"Profile not found: {level}"}
    
    return {
        "profile": profile.to_dict()
    }


def handle_set_agent_permissions(data: dict) -> dict:
    """Set permissions for an agent"""
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


def handle_validate_spawn(data: dict) -> dict:
    """Validate if a parent can spawn a child with given permissions"""
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


def handle_get_agent_permissions(data: dict) -> dict:
    """Get permissions for an agent"""
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


def handle_remove_agent_permissions(data: dict) -> dict:
    """Remove permissions for an agent"""
    agent_id = data.get("agent_id")
    if not agent_id:
        return {"error": "Missing required parameter: agent_id"}
    
    permission_manager.remove_agent_permissions(agent_id)
    
    return {
        "agent_id": agent_id,
        "status": "removed"
    }


def handle_list_profiles(data: dict) -> dict:
    """List available permission profiles"""
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


def handle_create_sandbox(data: dict) -> dict:
    """Create a sandbox for an agent"""
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


def handle_get_sandbox(data: dict) -> dict:
    """Get sandbox information for an agent"""
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


def handle_remove_sandbox(data: dict) -> dict:
    """Remove a sandbox"""
    agent_id = data.get("agent_id")
    if not agent_id:
        return {"error": "Missing required parameter: agent_id"}
    
    force = data.get("force", False)
    success = sandbox_manager.remove_sandbox(agent_id, force=force)
    
    return {
        "agent_id": agent_id,
        "removed": success
    }


def handle_list_sandboxes(data: dict) -> dict:
    """List all active sandboxes"""
    sandboxes = sandbox_manager.list_sandboxes()
    
    return {
        "sandboxes": [s.to_dict() for s in sandboxes],
        "count": len(sandboxes)
    }


def handle_sandbox_stats(data: dict) -> dict:
    """Get sandbox statistics"""
    stats = sandbox_manager.get_sandbox_stats()
    return {"stats": stats}


@hookimpl
def ksi_plugin_info():
    """Return plugin information"""
    return {
        "name": "permission_service",
        "version": "1.0.0",
        "description": "Agent permission and sandbox management service",
        "events": [
            {
                "name": "permission:get_profile",
                "description": "Get a permission profile",
                "params": {
                    "level": "Permission level (restricted, standard, trusted, researcher)"
                }
            },
            {
                "name": "permission:set_agent",
                "description": "Set permissions for an agent",
                "params": {
                    "agent_id": "Agent identifier",
                    "profile": "Base profile to use (optional)",
                    "permissions": "Full permission object (optional)",
                    "overrides": "Permission overrides to apply (optional)"
                }
            },
            {
                "name": "permission:validate_spawn",
                "description": "Validate if parent can spawn child with permissions",
                "params": {
                    "parent_id": "Parent agent ID",
                    "child_permissions": "Requested child permissions"
                }
            },
            {
                "name": "permission:get_agent",
                "description": "Get permissions for an agent",
                "params": {
                    "agent_id": "Agent identifier"
                }
            },
            {
                "name": "permission:remove_agent",
                "description": "Remove permissions for an agent",
                "params": {
                    "agent_id": "Agent identifier"
                }
            },
            {
                "name": "permission:list_profiles",
                "description": "List available permission profiles",
                "params": {}
            },
            {
                "name": "sandbox:create",
                "description": "Create a sandbox for an agent",
                "params": {
                    "agent_id": "Agent identifier",
                    "config": "Sandbox configuration"
                }
            },
            {
                "name": "sandbox:get",
                "description": "Get sandbox information",
                "params": {
                    "agent_id": "Agent identifier"
                }
            },
            {
                "name": "sandbox:remove",
                "description": "Remove a sandbox",
                "params": {
                    "agent_id": "Agent identifier",
                    "force": "Force removal even with nested children"
                }
            },
            {
                "name": "sandbox:list",
                "description": "List all active sandboxes",
                "params": {}
            },
            {
                "name": "sandbox:stats",
                "description": "Get sandbox statistics",
                "params": {}
            }
        ]
    }


# Mark as a KSI plugin
ksi_plugin = True