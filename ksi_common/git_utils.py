#!/usr/bin/env python3
"""
Git Integration Utilities for KSI Submodule Management

This module provides git operations for managing KSI components in git submodules,
including commit, branch, merge, and synchronization operations.
"""

import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

from ksi_common.logging import get_bound_logger
from ksi_common.config import config
from ksi_common.timestamps import timestamp_utc

logger = get_bound_logger("git_utils")

# Try to import git libraries, with fallback support
try:
    import pygit2
    HAS_PYGIT2 = True
    logger.info("Using pygit2 for git operations")
except ImportError:
    HAS_PYGIT2 = False
    logger.warning("pygit2 not available, falling back to subprocess")

try:
    import git
    HAS_GITPYTHON = True
    logger.info("GitPython available as fallback")
except ImportError:
    HAS_GITPYTHON = False
    logger.warning("GitPython not available")


@dataclass
class GitOperationResult:
    """Result of a git operation."""
    success: bool
    message: str
    commit_hash: Optional[str] = None
    branch: Optional[str] = None
    files_changed: List[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.files_changed is None:
            self.files_changed = []


@dataclass
class GitRepositoryInfo:
    """Information about a git repository."""
    path: Path
    url: str
    branch: str
    is_submodule: bool
    last_commit: Optional[str] = None
    status: str = "unknown"
    has_changes: bool = False


class GitError(Exception):
    """Base exception for git operations."""
    pass


class GitSubmoduleManager:
    """Manages git submodules for KSI components."""
    
    def __init__(self):
        self.repo_root = Path.cwd()
        self.submodule_paths = {
            "compositions": config.compositions_dir,
            "evaluations": config.evaluations_dir,
            "capabilities": config.capabilities_dir,
        }
        
    def get_component_repo_path(self, component_type: str) -> Path:
        """Get the repository path for a component type."""
        if component_type not in self.submodule_paths:
            raise ValueError(f"Unknown component type: {component_type}")
        return self.submodule_paths[component_type]
    
    async def get_repository_info(self, component_type: str) -> GitRepositoryInfo:
        """Get information about a component repository."""
        repo_path = self.get_component_repo_path(component_type)
        
        try:
            if HAS_PYGIT2:
                return await self._get_repo_info_pygit2(repo_path, component_type)
            elif HAS_GITPYTHON:
                return await self._get_repo_info_gitpython(repo_path, component_type)
            else:
                return await self._get_repo_info_subprocess(repo_path, component_type)
        except Exception as e:
            logger.error(f"Failed to get repository info for {component_type}: {e}")
            return GitRepositoryInfo(
                path=repo_path,
                url="unknown",
                branch="unknown",
                is_submodule=True,
                status="error"
            )
    
    async def _get_repo_info_pygit2(self, repo_path: Path, component_type: str) -> GitRepositoryInfo:
        """Get repository info using pygit2."""
        try:
            repo = pygit2.Repository(str(repo_path))
            
            # Get current branch
            branch = repo.head.shorthand if repo.head else "unknown"
            
            # Get remote URL
            remote_url = "unknown"
            if "origin" in repo.remotes:
                remote_url = repo.remotes["origin"].url
            
            # Get last commit
            last_commit = str(repo.head.target) if repo.head else None
            
            # Check for changes
            has_changes = bool(repo.status())
            
            return GitRepositoryInfo(
                path=repo_path,
                url=remote_url,
                branch=branch,
                is_submodule=True,
                last_commit=last_commit,
                status="active",
                has_changes=has_changes
            )
        except Exception as e:
            logger.error(f"pygit2 error for {component_type}: {e}")
            raise GitError(f"Failed to access repository: {e}")
    
    async def _get_repo_info_gitpython(self, repo_path: Path, component_type: str) -> GitRepositoryInfo:
        """Get repository info using GitPython."""
        try:
            repo = git.Repo(str(repo_path))
            
            # Get current branch
            branch = repo.active_branch.name if repo.active_branch else "unknown"
            
            # Get remote URL
            remote_url = "unknown"
            if repo.remotes:
                remote_url = repo.remotes.origin.url
            
            # Get last commit
            last_commit = str(repo.head.commit.hexsha) if repo.head else None
            
            # Check for changes
            has_changes = bool(repo.git.status("--porcelain"))
            
            return GitRepositoryInfo(
                path=repo_path,
                url=remote_url,
                branch=branch,
                is_submodule=True,
                last_commit=last_commit,
                status="active",
                has_changes=has_changes
            )
        except Exception as e:
            logger.error(f"GitPython error for {component_type}: {e}")
            raise GitError(f"Failed to access repository: {e}")
    
    async def _get_repo_info_subprocess(self, repo_path: Path, component_type: str) -> GitRepositoryInfo:
        """Get repository info using subprocess."""
        try:
            # Get current branch
            branch_result = await self._run_git_command(
                ["branch", "--show-current"], 
                cwd=repo_path
            )
            branch = branch_result.message.strip() if branch_result.success else "unknown"
            
            # Get remote URL
            url_result = await self._run_git_command(
                ["remote", "get-url", "origin"], 
                cwd=repo_path
            )
            remote_url = url_result.message.strip() if url_result.success else "unknown"
            
            # Get last commit
            commit_result = await self._run_git_command(
                ["rev-parse", "HEAD"], 
                cwd=repo_path
            )
            last_commit = commit_result.message.strip() if commit_result.success else None
            
            # Check for changes
            status_result = await self._run_git_command(
                ["status", "--porcelain"], 
                cwd=repo_path
            )
            has_changes = bool(status_result.message.strip()) if status_result.success else False
            
            return GitRepositoryInfo(
                path=repo_path,
                url=remote_url,
                branch=branch,
                is_submodule=True,
                last_commit=last_commit,
                status="active",
                has_changes=has_changes
            )
        except Exception as e:
            logger.error(f"Subprocess error for {component_type}: {e}")
            raise GitError(f"Failed to access repository: {e}")
    
    async def save_component(self, component_type: str, name: str, content: Dict[str, Any], 
                           message: Optional[str] = None) -> GitOperationResult:
        """Save component with git commit."""
        try:
            repo_path = self.get_component_repo_path(component_type)
            
            # Determine file path based on component type
            if component_type == "compositions":
                # Need to determine subdirectory (profiles, orchestrations, prompts, etc.)
                subdir = self._determine_composition_subdir(content)
                file_path = repo_path / subdir / f"{name}.yaml"
            else:
                file_path = repo_path / f"{name}.yaml"
            
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write component file
            import yaml
            with open(file_path, 'w') as f:
                yaml.dump(content, f, default_flow_style=False, sort_keys=False)
            
            # Create commit message
            if not message:
                message = f"Update {component_type}: {name}"
            
            # Perform git operations
            if HAS_PYGIT2:
                result = await self._commit_pygit2(repo_path, file_path, message)
            elif HAS_GITPYTHON:
                result = await self._commit_gitpython(repo_path, file_path, message)
            else:
                result = await self._commit_subprocess(repo_path, file_path, message)
            
            if result.success:
                logger.info(f"Saved {component_type} component: {name}")
                result.files_changed = [str(file_path.relative_to(repo_path))]
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to save component {name}: {e}")
            return GitOperationResult(
                success=False,
                message=f"Failed to save component: {e}",
                error=str(e)
            )
    
    def _determine_composition_subdir(self, content: Dict[str, Any]) -> str:
        """Determine the subdirectory for a composition based on its content."""
        content_type = content.get("type", "")
        
        if content_type == "profile":
            return "profiles"
        elif content_type == "orchestration":
            return "orchestrations"
        elif content_type == "prompt":
            return "prompts"
        elif content_type == "fragment":
            return "fragments"
        elif content_type == "pattern":
            return "patterns"
        else:
            # Default to profiles for unknown types
            return "profiles"
    
    async def _commit_pygit2(self, repo_path: Path, file_path: Path, message: str) -> GitOperationResult:
        """Commit using pygit2."""
        try:
            repo = pygit2.Repository(str(repo_path))
            
            # Add file to index
            relative_path = str(file_path.relative_to(repo_path))
            repo.index.add(relative_path)
            repo.index.write()
            
            # Create signature
            signature = pygit2.Signature(
                "KSI System",
                "ksi@system.local",
                int(datetime.now().timestamp())
            )
            
            # Create commit
            tree = repo.index.write_tree()
            parents = [repo.head.target] if repo.head else []
            
            commit_hash = repo.create_commit(
                "HEAD",
                signature,
                signature,
                message,
                tree,
                parents
            )
            
            return GitOperationResult(
                success=True,
                message=f"Committed successfully: {message}",
                commit_hash=str(commit_hash)
            )
            
        except Exception as e:
            logger.error(f"pygit2 commit error: {e}")
            return GitOperationResult(
                success=False,
                message=f"Commit failed: {e}",
                error=str(e)
            )
    
    async def _commit_gitpython(self, repo_path: Path, file_path: Path, message: str) -> GitOperationResult:
        """Commit using GitPython."""
        try:
            repo = git.Repo(str(repo_path))
            
            # Add file to index
            relative_path = str(file_path.relative_to(repo_path))
            repo.index.add([relative_path])
            
            # Create commit
            commit = repo.index.commit(message)
            
            return GitOperationResult(
                success=True,
                message=f"Committed successfully: {message}",
                commit_hash=str(commit.hexsha)
            )
            
        except Exception as e:
            logger.error(f"GitPython commit error: {e}")
            return GitOperationResult(
                success=False,
                message=f"Commit failed: {e}",
                error=str(e)
            )
    
    async def _commit_subprocess(self, repo_path: Path, file_path: Path, message: str) -> GitOperationResult:
        """Commit using subprocess."""
        try:
            # Add file
            relative_path = str(file_path.relative_to(repo_path))
            add_result = await self._run_git_command(
                ["add", relative_path], 
                cwd=repo_path
            )
            
            if not add_result.success:
                return GitOperationResult(
                    success=False,
                    message=f"Git add failed: {add_result.error}",
                    error=add_result.error
                )
            
            # Commit
            commit_result = await self._run_git_command(
                ["commit", "-m", message], 
                cwd=repo_path
            )
            
            if not commit_result.success:
                return GitOperationResult(
                    success=False,
                    message=f"Git commit failed: {commit_result.error}",
                    error=commit_result.error
                )
            
            # Get commit hash
            hash_result = await self._run_git_command(
                ["rev-parse", "HEAD"], 
                cwd=repo_path
            )
            
            commit_hash = hash_result.message.strip() if hash_result.success else "unknown"
            
            return GitOperationResult(
                success=True,
                message=f"Committed successfully: {message}",
                commit_hash=commit_hash
            )
            
        except Exception as e:
            logger.error(f"Subprocess commit error: {e}")
            return GitOperationResult(
                success=False,
                message=f"Commit failed: {e}",
                error=str(e)
            )
    
    async def fork_component(self, component_type: str, source_name: str, target_name: str) -> GitOperationResult:
        """Fork component to new name with git branch."""
        try:
            repo_path = self.get_component_repo_path(component_type)
            
            # Determine source file path
            if component_type == "compositions":
                # Need to find the source file
                source_path = await self._find_composition_file(repo_path, source_name)
                if not source_path:
                    return GitOperationResult(
                        success=False,
                        message=f"Source component not found: {source_name}",
                        error="Source not found"
                    )
                
                # Determine target path (same subdirectory)
                target_path = source_path.parent / f"{target_name}.yaml"
            else:
                source_path = repo_path / f"{source_name}.yaml"
                target_path = repo_path / f"{target_name}.yaml"
            
            # Check if source exists
            if not source_path.exists():
                return GitOperationResult(
                    success=False,
                    message=f"Source component not found: {source_name}",
                    error="Source not found"
                )
            
            # Copy file
            shutil.copy2(source_path, target_path)
            
            # Update the content to reflect the new name
            import yaml
            with open(target_path, 'r') as f:
                content = yaml.safe_load(f)
            
            if content and isinstance(content, dict):
                content["name"] = target_name
                # Add fork metadata
                content.setdefault("metadata", {})
                content["metadata"]["forked_from"] = source_name
                content["metadata"]["forked_at"] = timestamp_utc()
                
                with open(target_path, 'w') as f:
                    yaml.dump(content, f, default_flow_style=False, sort_keys=False)
            
            # Commit the fork
            message = f"Fork {component_type}: {source_name} -> {target_name}"
            result = await self.save_component(component_type, target_name, content, message)
            
            if result.success:
                logger.info(f"Forked {component_type} component: {source_name} -> {target_name}")
                result.files_changed = [str(target_path.relative_to(repo_path))]
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to fork component {source_name}: {e}")
            return GitOperationResult(
                success=False,
                message=f"Failed to fork component: {e}",
                error=str(e)
            )
    
    async def _find_composition_file(self, repo_path: Path, name: str) -> Optional[Path]:
        """Find a composition file by name in any subdirectory."""
        subdirs = ["profiles", "orchestrations", "prompts", "fragments", "patterns"]
        
        for subdir in subdirs:
            file_path = repo_path / subdir / f"{name}.yaml"
            if file_path.exists():
                return file_path
        
        return None
    
    async def sync_submodules(self, component_type: Optional[str] = None) -> GitOperationResult:
        """Synchronize submodules with remote repositories."""
        try:
            if component_type:
                # Sync specific component
                repo_path = self.get_component_repo_path(component_type)
                result = await self._sync_single_submodule(repo_path)
            else:
                # Sync all submodules
                results = []
                for comp_type in self.submodule_paths:
                    repo_path = self.get_component_repo_path(comp_type)
                    result = await self._sync_single_submodule(repo_path)
                    results.append(result)
                
                # Combine results
                all_success = all(r.success for r in results)
                messages = [r.message for r in results]
                
                return GitOperationResult(
                    success=all_success,
                    message="; ".join(messages)
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to sync submodules: {e}")
            return GitOperationResult(
                success=False,
                message=f"Failed to sync submodules: {e}",
                error=str(e)
            )
    
    async def _sync_single_submodule(self, repo_path: Path) -> GitOperationResult:
        """Sync a single submodule."""
        try:
            # Pull latest changes
            pull_result = await self._run_git_command(
                ["pull", "origin", "main"], 
                cwd=repo_path
            )
            
            if pull_result.success:
                return GitOperationResult(
                    success=True,
                    message=f"Synced submodule: {repo_path.name}"
                )
            else:
                return GitOperationResult(
                    success=False,
                    message=f"Failed to sync submodule: {repo_path.name}",
                    error=pull_result.error
                )
                
        except Exception as e:
            logger.error(f"Failed to sync submodule {repo_path}: {e}")
            return GitOperationResult(
                success=False,
                message=f"Failed to sync submodule: {e}",
                error=str(e)
            )
    
    async def _run_git_command(self, args: List[str], cwd: Path) -> GitOperationResult:
        """Run a git command using subprocess."""
        try:
            cmd = ["git"] + args
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            return GitOperationResult(
                success=process.returncode == 0,
                message=stdout.decode().strip(),
                error=stderr.decode().strip() if stderr else None
            )
            
        except Exception as e:
            logger.error(f"Git command failed: {e}")
            return GitOperationResult(
                success=False,
                message="Command execution failed",
                error=str(e)
            )


# Global instance
git_manager = GitSubmoduleManager()


# Utility functions
async def save_component(component_type: str, name: str, content: Dict[str, Any], 
                        message: Optional[str] = None) -> GitOperationResult:
    """Save component with git commit."""
    return await git_manager.save_component(component_type, name, content, message)


async def fork_component(component_type: str, source_name: str, target_name: str) -> GitOperationResult:
    """Fork component to new name."""
    return await git_manager.fork_component(component_type, source_name, target_name)


async def sync_submodules(component_type: Optional[str] = None) -> GitOperationResult:
    """Synchronize submodules with remote repositories."""
    return await git_manager.sync_submodules(component_type)


async def get_repository_info(component_type: str) -> GitRepositoryInfo:
    """Get information about a component repository."""
    return await git_manager.get_repository_info(component_type)