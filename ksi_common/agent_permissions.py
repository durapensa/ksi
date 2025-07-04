"""
Agent permissions system for KSI.

Provides permission profiles, validation, and enforcement for agent operations.
Integrates with claude-cli's filesystem sandboxing and tool restrictions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Union
import json
import yaml

from ksi_common.config import config
from ksi_common.logging import get_bound_logger

logger = get_bound_logger(__name__)


class PermissionLevel(str, Enum):
    """Agent permission levels"""
    RESTRICTED = "restricted"
    STANDARD = "standard"
    TRUSTED = "trusted"
    RESEARCHER = "researcher"
    CUSTOM = "custom"


@dataclass
class ToolPermissions:
    """Tool access permissions for an agent"""
    allowed: Optional[List[str]] = None  # None means all tools allowed
    disallowed: List[str] = field(default_factory=list)
    
    def get_effective_allowed_tools(self, all_tools: Optional[List[str]] = None) -> List[str]:
        """Get the effective list of allowed tools"""
        # Default tool list if none provided
        if all_tools is None:
            all_tools = [
                "Task", "Bash", "Glob", "Grep", "LS", "exit_plan_mode",
                "Read", "Edit", "MultiEdit", "Write", "NotebookRead", "NotebookEdit",
                "WebFetch", "TodoRead", "TodoWrite", "WebSearch"
            ]
        
        if self.allowed is None:
            # All tools allowed except those explicitly disallowed
            return [t for t in all_tools if t not in self.disallowed]
        else:
            # Only explicitly allowed tools, minus any disallowed
            return [t for t in self.allowed if t not in self.disallowed]
    
    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a specific tool is allowed"""
        if tool_name in self.disallowed:
            return False
        if self.allowed is None:
            return True
        return tool_name in self.allowed
    
    def merge_with(self, other: ToolPermissions) -> ToolPermissions:
        """Merge with another ToolPermissions, other takes precedence"""
        # For allowed tools, if either specifies a list, use intersection
        if self.allowed is not None and other.allowed is not None:
            new_allowed = list(set(self.allowed) & set(other.allowed))
        elif other.allowed is not None:
            new_allowed = other.allowed
        else:
            new_allowed = self.allowed
        
        # For disallowed, union both lists
        new_disallowed = list(set(self.disallowed) | set(other.disallowed))
        
        return ToolPermissions(allowed=new_allowed, disallowed=new_disallowed)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "disallowed": self.disallowed
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ToolPermissions:
        return cls(
            allowed=data.get("allowed"),
            disallowed=data.get("disallowed", [])
        )


@dataclass
class FilesystemPermissions:
    """Filesystem access permissions for an agent"""
    sandbox_root: str = "./workspace"
    read_paths: List[str] = field(default_factory=lambda: ["./workspace"])
    write_paths: List[str] = field(default_factory=lambda: ["./workspace"])
    max_file_size_mb: int = 10
    max_total_size_mb: int = 100
    allow_symlinks: bool = False
    
    def validate_path(self, path: Path, write: bool = False, sandbox_dir: Optional[Path] = None) -> bool:
        """Validate if a path is allowed for read/write"""
        if sandbox_dir is None:
            # Can't validate without knowing the sandbox location
            return True
        
        # Resolve path relative to sandbox
        try:
            if path.is_absolute():
                resolved = path.resolve()
            else:
                resolved = (sandbox_dir / path).resolve()
            
            # Check if path is within allowed directories
            paths_to_check = self.write_paths if write else self.read_paths
            
            for allowed_path in paths_to_check:
                # Resolve allowed path relative to sandbox
                if allowed_path.startswith("../"):
                    # Parent directory access
                    allowed_resolved = (sandbox_dir / allowed_path).resolve()
                elif allowed_path.startswith("./"):
                    # Relative to sandbox
                    allowed_resolved = (sandbox_dir / allowed_path[2:]).resolve()
                else:
                    # Assume relative to sandbox
                    allowed_resolved = (sandbox_dir / allowed_path).resolve()
                
                # Check if resolved path is within allowed path
                try:
                    resolved.relative_to(allowed_resolved)
                    return True
                except ValueError:
                    continue
            
            return False
            
        except Exception as e:
            logger.warning("Path validation error", path=str(path), error=str(e))
            return False
    
    def merge_with(self, other: FilesystemPermissions) -> FilesystemPermissions:
        """Merge with another FilesystemPermissions, other takes precedence"""
        return FilesystemPermissions(
            sandbox_root=other.sandbox_root,
            read_paths=list(set(self.read_paths) & set(other.read_paths)) if other.read_paths else self.read_paths,
            write_paths=list(set(self.write_paths) & set(other.write_paths)) if other.write_paths else self.write_paths,
            max_file_size_mb=min(self.max_file_size_mb, other.max_file_size_mb),
            max_total_size_mb=min(self.max_total_size_mb, other.max_total_size_mb),
            allow_symlinks=self.allow_symlinks and other.allow_symlinks
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sandbox_root": self.sandbox_root,
            "read_paths": self.read_paths,
            "write_paths": self.write_paths,
            "max_file_size_mb": self.max_file_size_mb,
            "max_total_size_mb": self.max_total_size_mb,
            "allow_symlinks": self.allow_symlinks
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FilesystemPermissions:
        return cls(**data)


@dataclass
class ResourceLimits:
    """Resource usage limits for an agent"""
    max_tokens_per_request: int = 100000
    max_total_tokens: int = 1000000
    max_requests_per_minute: int = 60
    
    def merge_with(self, other: ResourceLimits) -> ResourceLimits:
        """Merge with another ResourceLimits, taking minimums"""
        return ResourceLimits(
            max_tokens_per_request=min(self.max_tokens_per_request, other.max_tokens_per_request),
            max_total_tokens=min(self.max_total_tokens, other.max_total_tokens),
            max_requests_per_minute=min(self.max_requests_per_minute, other.max_requests_per_minute)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_tokens_per_request": self.max_tokens_per_request,
            "max_total_tokens": self.max_total_tokens,
            "max_requests_per_minute": self.max_requests_per_minute
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ResourceLimits:
        return cls(**data)


@dataclass
class Capabilities:
    """Special capabilities for an agent"""
    multi_agent_todo: bool = False
    agent_messaging: bool = False
    spawn_agents: bool = False
    network_access: bool = False
    
    def merge_with(self, other: Capabilities) -> Capabilities:
        """Merge with another Capabilities, other takes precedence (more restrictive)"""
        return Capabilities(
            multi_agent_todo=self.multi_agent_todo and other.multi_agent_todo,
            agent_messaging=self.agent_messaging and other.agent_messaging,
            spawn_agents=self.spawn_agents and other.spawn_agents,
            network_access=self.network_access and other.network_access
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "multi_agent_todo": self.multi_agent_todo,
            "agent_messaging": self.agent_messaging,
            "spawn_agents": self.spawn_agents,
            "network_access": self.network_access
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Capabilities:
        return cls(**data)


@dataclass
class AgentPermissions:
    """Complete permission set for an agent"""
    level: PermissionLevel
    tools: ToolPermissions
    filesystem: FilesystemPermissions
    resources: ResourceLimits
    capabilities: Capabilities
    
    def can_spawn_child(self, child_permissions: AgentPermissions) -> bool:
        """Check if this agent can spawn a child with given permissions"""
        if not self.capabilities.spawn_agents:
            return False
        
        # Child cannot have more permissions than parent
        # Check tool permissions
        child_tools = child_permissions.tools.get_effective_allowed_tools()
        parent_tools = self.tools.get_effective_allowed_tools()
        if not all(tool in parent_tools for tool in child_tools):
            return False
        
        # Check filesystem permissions (simplified check)
        if child_permissions.filesystem.max_file_size_mb > self.filesystem.max_file_size_mb:
            return False
        if child_permissions.filesystem.max_total_size_mb > self.filesystem.max_total_size_mb:
            return False
        
        # Check resource limits
        if child_permissions.resources.max_tokens_per_request > self.resources.max_tokens_per_request:
            return False
        if child_permissions.resources.max_total_tokens > self.resources.max_total_tokens:
            return False
        
        # Check capabilities
        if child_permissions.capabilities.network_access and not self.capabilities.network_access:
            return False
        if child_permissions.capabilities.spawn_agents and not self.capabilities.spawn_agents:
            return False
        
        return True
    
    def merge_with(self, other: AgentPermissions) -> AgentPermissions:
        """Merge with another AgentPermissions, taking more restrictive options"""
        return AgentPermissions(
            level=PermissionLevel.CUSTOM,  # Merged permissions are custom
            tools=self.tools.merge_with(other.tools),
            filesystem=self.filesystem.merge_with(other.filesystem),
            resources=self.resources.merge_with(other.resources),
            capabilities=self.capabilities.merge_with(other.capabilities)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "tools": self.tools.to_dict(),
            "filesystem": self.filesystem.to_dict(),
            "resources": self.resources.to_dict(),
            "capabilities": self.capabilities.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentPermissions:
        return cls(
            level=PermissionLevel(data["level"]),
            tools=ToolPermissions.from_dict(data["tools"]),
            filesystem=FilesystemPermissions.from_dict(data["filesystem"]),
            resources=ResourceLimits.from_dict(data["resources"]),
            capabilities=Capabilities.from_dict(data["capabilities"])
        )
    
    @classmethod
    def from_yaml(cls, file_path: Path) -> AgentPermissions:
        """Load permissions from a YAML file"""
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Extract level from filename or use custom
        level_str = file_path.stem
        try:
            level = PermissionLevel(level_str)
        except ValueError:
            level = PermissionLevel.CUSTOM
        
        return cls(
            level=level,
            tools=ToolPermissions.from_dict(data.get("tools", {})),
            filesystem=FilesystemPermissions.from_dict(data.get("filesystem", {})),
            resources=ResourceLimits.from_dict(data.get("resources", {})),
            capabilities=Capabilities.from_dict(data.get("capabilities", {}))
        )


class PermissionManager:
    """Manages agent permissions and profiles"""
    
    def __init__(self, permissions_dir: Optional[Path] = None):
        self.permissions_dir = permissions_dir or config.permissions_dir
        self.profiles: Dict[PermissionLevel, AgentPermissions] = {}
        self.agent_permissions: Dict[str, AgentPermissions] = {}
        self._load_profiles()
    
    def _load_profiles(self) -> None:
        """Load permission profiles from disk"""
        profiles_dir = self.permissions_dir / "profiles"
        if not profiles_dir.exists():
            logger.warning("Permissions profiles directory not found", path=str(profiles_dir))
            return
        
        for profile_file in profiles_dir.glob("*.yaml"):
            try:
                permissions = AgentPermissions.from_yaml(profile_file)
                self.profiles[permissions.level] = permissions
                logger.info("Loaded permission profile", profile=permissions.level.value)
            except Exception as e:
                logger.error("Failed to load permission profile", file=str(profile_file), error=str(e))
    
    def get_profile(self, level: Union[PermissionLevel, str]) -> Optional[AgentPermissions]:
        """Get a permission profile by level"""
        if isinstance(level, str):
            try:
                level = PermissionLevel(level)
            except ValueError:
                logger.error("Invalid permission level", level=level)
                return None
        
        return self.profiles.get(level)
    
    def set_agent_permissions(self, agent_id: str, permissions: AgentPermissions) -> None:
        """Set permissions for a specific agent"""
        self.agent_permissions[agent_id] = permissions
        logger.info(
            "Set agent permissions",
            agent_id=agent_id,
            level=permissions.level.value,
            allowed_tools=permissions.tools.allowed,
            disallowed_tools=permissions.tools.disallowed
        )
    
    def get_agent_permissions(self, agent_id: str) -> Optional[AgentPermissions]:
        """Get permissions for a specific agent"""
        return self.agent_permissions.get(agent_id)
    
    def remove_agent_permissions(self, agent_id: str) -> None:
        """Remove permissions for an agent (e.g., on termination)"""
        if agent_id in self.agent_permissions:
            del self.agent_permissions[agent_id]
            logger.info("Removed agent permissions", agent_id=agent_id)
    
    def validate_spawn_permissions(self, parent_id: str, child_permissions: AgentPermissions) -> bool:
        """Validate if a parent can spawn a child with given permissions"""
        parent_perms = self.get_agent_permissions(parent_id)
        if not parent_perms:
            logger.error("Parent agent not found", parent_id=parent_id)
            return False
        
        if not parent_perms.can_spawn_child(child_permissions):
            logger.warning(
                "Parent cannot spawn child with requested permissions",
                parent_id=parent_id,
                child_level=child_permissions.level.value
            )
            return False
        
        return True
    
    def get_claude_cli_args(self, agent_id: str) -> Dict[str, Any]:
        """Get claude-cli compatible arguments for an agent's permissions"""
        permissions = self.get_agent_permissions(agent_id)
        if not permissions:
            # Default to restricted if no permissions set
            permissions = self.get_profile(PermissionLevel.RESTRICTED)
            if not permissions:
                logger.error("No permissions found for agent", agent_id=agent_id)
                return {}
        
        result = {}
        
        # Get effective allowed tools
        allowed_tools = permissions.tools.get_effective_allowed_tools()
        if allowed_tools:
            result["allowed_tools"] = allowed_tools
        
        # Note: disallowed_tools is a future enhancement in claude-cli
        # For now, we only use allowed_tools
        
        return result
    
    def export_permissions(self, file_path: Path) -> None:
        """Export all agent permissions to a file"""
        data = {
            agent_id: perms.to_dict()
            for agent_id, perms in self.agent_permissions.items()
        }
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info("Exported agent permissions", path=str(file_path), count=len(data))
    
    def import_permissions(self, file_path: Path) -> None:
        """Import agent permissions from a file"""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        for agent_id, perm_data in data.items():
            self.agent_permissions[agent_id] = AgentPermissions.from_dict(perm_data)
        
        logger.info("Imported agent permissions", path=str(file_path), count=len(data))


# Global permission manager instance
permission_manager = PermissionManager()