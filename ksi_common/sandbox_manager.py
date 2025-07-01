"""
Sandbox manager for KSI agent filesystem isolation.

Manages sandbox directory creation, cleanup, and sharing models.
Supports isolated, shared, and nested sandbox configurations.
"""

from __future__ import annotations

import shutil
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime

from ksi_common.config import config
from ksi_common.logging import get_bound_logger

logger = get_bound_logger(__name__)


class SandboxMode(str, Enum):
    """Sandbox sharing modes"""
    ISOLATED = "isolated"    # Completely separate sandbox
    SHARED = "shared"        # Share with session
    NESTED = "nested"        # Nested within parent


@dataclass
class SandboxConfig:
    """Configuration for a sandbox"""
    mode: SandboxMode = SandboxMode.ISOLATED
    parent_agent_id: Optional[str] = None
    session_id: Optional[str] = None
    parent_share: str = "read_only"  # read_only, read_write, none
    session_share: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "mode": self.mode.value,
            "parent_agent_id": self.parent_agent_id,
            "session_id": self.session_id,
            "parent_share": self.parent_share,
            "session_share": self.session_share
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> SandboxConfig:
        return cls(
            mode=SandboxMode(data["mode"]),
            parent_agent_id=data.get("parent_agent_id"),
            session_id=data.get("session_id"),
            parent_share=data.get("parent_share", "read_only"),
            session_share=data.get("session_share", False)
        )


@dataclass
class Sandbox:
    """Represents an agent sandbox"""
    agent_id: str
    path: Path
    config: SandboxConfig
    created_at: datetime
    
    @property
    def workspace_path(self) -> Path:
        """Get the workspace directory path"""
        return self.path / "workspace"
    
    @property
    def shared_path(self) -> Path:
        """Get the shared resources directory path"""
        return self.path / "shared"
    
    @property
    def exports_path(self) -> Path:
        """Get the exports directory path"""
        return self.path / "exports"
    
    @property
    def claude_path(self) -> Path:
        """Get the Claude session data directory path"""
        return self.path / ".claude"
    
    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "path": str(self.path),
            "config": self.config.to_dict(),
            "created_at": self.created_at.isoformat()
        }


class SandboxManager:
    """Manages agent sandboxes"""
    
    def __init__(self, sandbox_root: Optional[Path] = None):
        self.sandbox_root = sandbox_root or Path("var/sandbox")
        self.shared_root = self.sandbox_root / "shared"
        self.agents_root = self.sandbox_root / "agents"
        self.sandboxes: Dict[str, Sandbox] = {}
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """Ensure sandbox directories exist"""
        self.sandbox_root.mkdir(parents=True, exist_ok=True)
        self.shared_root.mkdir(exist_ok=True)
        self.agents_root.mkdir(exist_ok=True)
        
        # Create shared resources directory
        shared_resources = self.sandbox_root / "_shared"
        shared_resources.mkdir(exist_ok=True)
        (shared_resources / "knowledge").mkdir(exist_ok=True)
        (shared_resources / "templates").mkdir(exist_ok=True)
    
    def create_sandbox(self, agent_id: str, config: SandboxConfig) -> Sandbox:
        """Create a new sandbox for an agent"""
        # Determine sandbox path based on mode
        if config.mode == SandboxMode.SHARED and config.session_id:
            # Shared session sandbox
            sandbox_path = self.shared_root / config.session_id
        elif config.mode == SandboxMode.NESTED and config.parent_agent_id:
            # Nested within parent sandbox
            parent_sandbox = self.get_sandbox(config.parent_agent_id)
            if not parent_sandbox:
                raise ValueError(f"Parent agent {config.parent_agent_id} not found")
            sandbox_path = parent_sandbox.path / "nested" / agent_id
        else:
            # Isolated sandbox
            sandbox_path = self.agents_root / agent_id
        
        # Create sandbox structure
        sandbox_path.mkdir(parents=True, exist_ok=True)
        (sandbox_path / "workspace").mkdir(exist_ok=True)
        (sandbox_path / "shared").mkdir(exist_ok=True)
        (sandbox_path / "exports").mkdir(exist_ok=True)
        (sandbox_path / ".claude").mkdir(exist_ok=True)
        
        # Set up shared resources symlinks
        self._setup_shared_resources(sandbox_path, config)
        
        # Create sandbox metadata
        metadata = {
            "agent_id": agent_id,
            "config": config.to_dict(),
            "created_at": datetime.now().isoformat()
        }
        with open(sandbox_path / ".sandbox_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
        
        # Create and register sandbox
        sandbox = Sandbox(
            agent_id=agent_id,
            path=sandbox_path,
            config=config,
            created_at=datetime.now()
        )
        self.sandboxes[agent_id] = sandbox
        
        logger.info(
            "Created sandbox",
            agent_id=agent_id,
            mode=config.mode.value,
            path=str(sandbox_path)
        )
        
        return sandbox
    
    def _setup_shared_resources(self, sandbox_path: Path, config: SandboxConfig) -> None:
        """Set up shared resource symlinks"""
        shared_dir = sandbox_path / "shared"
        
        # Link to global shared resources
        global_shared = self.sandbox_root / "_shared"
        for resource in ["knowledge", "templates"]:
            resource_path = global_shared / resource
            if resource_path.exists():
                link_path = shared_dir / resource
                if not link_path.exists():
                    link_path.symlink_to(resource_path)
        
        # If nested, optionally link to parent workspace
        if config.mode == SandboxMode.NESTED and config.parent_agent_id:
            parent_sandbox = self.get_sandbox(config.parent_agent_id)
            if parent_sandbox and config.parent_share != "none":
                parent_link = sandbox_path / "parent"
                if not parent_link.exists():
                    parent_link.symlink_to(parent_sandbox.workspace_path)
                    
                    # Make it read-only if specified
                    if config.parent_share == "read_only":
                        # Note: Actual read-only enforcement would require OS-level permissions
                        # For now, this is a logical flag
                        with open(sandbox_path / ".parent_access", "w") as f:
                            f.write("read_only")
        
        # If session shared, create session shared link
        if config.session_share and config.session_id:
            session_shared = self.shared_root / config.session_id / "shared"
            if session_shared.exists():
                session_link = shared_dir / "session"
                if not session_link.exists():
                    session_link.symlink_to(session_shared)
    
    def get_sandbox(self, agent_id: str) -> Optional[Sandbox]:
        """Get a sandbox by agent ID"""
        return self.sandboxes.get(agent_id)
    
    def get_sandbox_path(self, agent_id: str) -> Optional[Path]:
        """Get the sandbox path for an agent"""
        sandbox = self.get_sandbox(agent_id)
        return sandbox.path if sandbox else None
    
    def remove_sandbox(self, agent_id: str, force: bool = False) -> bool:
        """Remove a sandbox and clean up resources"""
        sandbox = self.get_sandbox(agent_id)
        if not sandbox:
            logger.warning("Sandbox not found", agent_id=agent_id)
            return False
        
        # Check if sandbox has nested children
        if not force:
            nested_dir = sandbox.path / "nested"
            if nested_dir.exists() and any(nested_dir.iterdir()):
                logger.error(
                    "Cannot remove sandbox with nested children",
                    agent_id=agent_id,
                    nested_count=len(list(nested_dir.iterdir()))
                )
                return False
        
        # Remove from tracking
        del self.sandboxes[agent_id]
        
        # Remove directory if it's agent-specific
        if sandbox.config.mode != SandboxMode.SHARED:
            try:
                shutil.rmtree(sandbox.path)
                logger.info("Removed sandbox", agent_id=agent_id, path=str(sandbox.path))
                return True
            except Exception as e:
                logger.error("Failed to remove sandbox", agent_id=agent_id, error=str(e))
                return False
        else:
            # For shared sandboxes, just remove the agent's tracking
            logger.info("Removed agent from shared sandbox", agent_id=agent_id)
            return True
    
    def list_sandboxes(self) -> List[Sandbox]:
        """List all active sandboxes"""
        return list(self.sandboxes.values())
    
    def get_session_agents(self, session_id: str) -> List[str]:
        """Get all agents sharing a session sandbox"""
        agents = []
        for agent_id, sandbox in self.sandboxes.items():
            if sandbox.config.session_id == session_id:
                agents.append(agent_id)
        return agents
    
    def get_nested_agents(self, parent_agent_id: str) -> List[str]:
        """Get all agents nested under a parent"""
        agents = []
        for agent_id, sandbox in self.sandboxes.items():
            if sandbox.config.parent_agent_id == parent_agent_id:
                agents.append(agent_id)
        return agents
    
    def cleanup_orphaned_sandboxes(self) -> int:
        """Clean up sandboxes without active agents"""
        cleaned = 0
        
        # Check agent sandboxes
        if self.agents_root.exists():
            for sandbox_dir in self.agents_root.iterdir():
                if sandbox_dir.is_dir():
                    agent_id = sandbox_dir.name
                    if agent_id not in self.sandboxes:
                        # Check metadata to see if it's old
                        metadata_file = sandbox_dir / ".sandbox_metadata.json"
                        if metadata_file.exists():
                            try:
                                with open(metadata_file) as f:
                                    metadata = json.load(f)
                                created_at = datetime.fromisoformat(metadata["created_at"])
                                age = datetime.now() - created_at
                                
                                # Remove if older than 24 hours
                                if age.total_seconds() > 86400:
                                    shutil.rmtree(sandbox_dir)
                                    logger.info("Cleaned orphaned sandbox", path=str(sandbox_dir))
                                    cleaned += 1
                            except Exception as e:
                                logger.error("Error cleaning sandbox", path=str(sandbox_dir), error=str(e))
        
        return cleaned
    
    def get_sandbox_stats(self) -> Dict:
        """Get statistics about sandbox usage"""
        stats = {
            "total_sandboxes": len(self.sandboxes),
            "isolated": 0,
            "shared": 0,
            "nested": 0,
            "by_session": {},
            "by_parent": {}
        }
        
        for sandbox in self.sandboxes.values():
            if sandbox.config.mode == SandboxMode.ISOLATED:
                stats["isolated"] += 1
            elif sandbox.config.mode == SandboxMode.SHARED:
                stats["shared"] += 1
                session_id = sandbox.config.session_id
                if session_id:
                    stats["by_session"][session_id] = stats["by_session"].get(session_id, 0) + 1
            elif sandbox.config.mode == SandboxMode.NESTED:
                stats["nested"] += 1
                parent_id = sandbox.config.parent_agent_id
                if parent_id:
                    stats["by_parent"][parent_id] = stats["by_parent"].get(parent_id, 0) + 1
        
        return stats


# Global sandbox manager instance
sandbox_manager = SandboxManager()