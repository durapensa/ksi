"""Git-based tracking for KSI component optimizations."""

import os
import json
import subprocess
from typing import Dict, List, Optional, Any
from datetime import datetime
import re

from ksi_common.config import config
from ksi_common.timestamps import timestamp_utc, created_at_timestamp


class OptimizationGitTracker:
    """Manages git operations for optimization tracking."""
    
    def __init__(self, repo_path: Optional[str] = None):
        """Initialize tracker with repository path."""
        self.repo_path = repo_path or config.compositions_dir
        self.optimization_branch_prefix = "optimization/"
        self.optimization_tag_prefix = "opt/"
    
    def _run_git_command(self, *args) -> str:
        """Run a git command in the repository."""
        cmd = ["git", "-C", self.repo_path] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Git command failed: {' '.join(cmd)}\n{result.stderr}")
        return result.stdout.strip()
    
    def create_optimization_branch(
        self,
        optimization_name: str,
        base_branch: str = "main"
    ) -> str:
        """Create a new branch for optimization experiments."""
        branch_name = f"{self.optimization_branch_prefix}{optimization_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Ensure we're on the base branch
        self._run_git_command("checkout", base_branch)
        
        # Create and checkout new branch
        self._run_git_command("checkout", "-b", branch_name)
        
        return branch_name
    
    def commit_optimization_result(
        self,
        component_path: str,
        optimized_content: str,
        optimization_metadata: Dict[str, Any],
        message: Optional[str] = None
    ) -> str:
        """Commit an optimization result with metadata."""
        # Write optimized content
        full_path = os.path.join(self.repo_path, component_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, 'w') as f:
            f.write(optimized_content)
        
        # Create metadata file
        metadata_path = f"{component_path}.optimization.json"
        full_metadata_path = os.path.join(self.repo_path, metadata_path)
        
        metadata = {
            "timestamp": timestamp_utc(),
            "component": component_path,
            **optimization_metadata
        }
        
        with open(full_metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Stage files
        self._run_git_command("add", component_path, metadata_path)
        
        # Create commit message
        if not message:
            optimizer = optimization_metadata.get("optimizer", "Unknown")
            improvement = optimization_metadata.get("improvement", 0)
            message = f"Optimize {component_path} with {optimizer} (+{improvement:.2%} improvement)"
        
        # Add optimization details to commit message
        full_message = f"{message}\n\n"
        full_message += f"Optimizer: {optimization_metadata.get('optimizer', 'Unknown')}\n"
        full_message += f"Original Score: {optimization_metadata.get('original_score', 'N/A')}\n"
        full_message += f"Optimized Score: {optimization_metadata.get('optimized_score', 'N/A')}\n"
        full_message += f"Improvement: {optimization_metadata.get('improvement', 0):.2%}\n"
        
        # Commit
        self._run_git_command("commit", "-m", full_message)
        
        # Get commit hash
        commit_hash = self._run_git_command("rev-parse", "HEAD")
        
        return commit_hash
    
    def tag_optimization_release(
        self,
        tag_name: str,
        component_paths: List[str],
        metadata: Dict[str, Any],
        message: Optional[str] = None
    ) -> str:
        """Create a git tag for an optimization release."""
        full_tag = f"{self.optimization_tag_prefix}{tag_name}"
        
        # Create tag metadata
        tag_metadata = {
            "timestamp": timestamp_utc(),
            "components": component_paths,
            "optimization_metadata": metadata,
        }
        
        # Create annotated tag with metadata
        if not message:
            message = f"Optimization release: {tag_name}"
        
        tag_message = f"{message}\n\n"
        tag_message += f"Components: {', '.join(component_paths)}\n"
        tag_message += f"Metadata: {json.dumps(tag_metadata, indent=2)}"
        
        self._run_git_command("tag", "-a", full_tag, "-m", tag_message)
        
        return full_tag
    
    def get_optimization_history(
        self,
        component_path: Optional[str] = None,
        branch: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get optimization history from git log."""
        cmd_args = ["log", "--format=%H|%aI|%s|%b", "--no-merges"]
        
        if branch:
            cmd_args.append(branch)
        
        if component_path:
            cmd_args.extend(["--", component_path])
        
        log_output = self._run_git_command(*cmd_args)
        
        history = []
        for line in log_output.split('\n'):
            if not line:
                continue
            
            parts = line.split('|', 3)
            if len(parts) >= 3:
                commit_hash, timestamp, subject = parts[:3]
                body = parts[3] if len(parts) > 3 else ""
                
                # Parse optimization metadata from commit message
                metadata = {}
                for match in re.finditer(r'(\w+): (.+)', body):
                    key, value = match.groups()
                    try:
                        # Try to parse numeric values
                        if '.' in value and value.replace('.', '').replace('-', '').isdigit():
                            metadata[key.lower()] = float(value)
                        elif value.replace('%', '').replace('.', '').isdigit():
                            metadata[key.lower()] = value
                        else:
                            metadata[key.lower()] = value
                    except:
                        metadata[key.lower()] = value
                
                history.append({
                    "commit": commit_hash,
                    "timestamp": timestamp,
                    "subject": subject,
                    "metadata": metadata
                })
        
        return history
    
    def compare_optimization_versions(
        self,
        component_path: str,
        commit1: str,
        commit2: str
    ) -> Dict[str, Any]:
        """Compare two versions of an optimized component."""
        # Get content at each commit
        content1 = self._run_git_command("show", f"{commit1}:{component_path}")
        content2 = self._run_git_command("show", f"{commit2}:{component_path}")
        
        # Get diff
        diff = self._run_git_command("diff", commit1, commit2, "--", component_path)
        
        # Get metadata if available
        try:
            metadata1_json = self._run_git_command("show", f"{commit1}:{component_path}.optimization.json")
            metadata1 = json.loads(metadata1_json)
        except:
            metadata1 = {}
        
        try:
            metadata2_json = self._run_git_command("show", f"{commit2}:{component_path}.optimization.json")
            metadata2 = json.loads(metadata2_json)
        except:
            metadata2 = {}
        
        return {
            "component_path": component_path,
            "version1": {
                "commit": commit1,
                "content": content1,
                "metadata": metadata1
            },
            "version2": {
                "commit": commit2,
                "content": content2,
                "metadata": metadata2
            },
            "diff": diff
        }
    
    def list_optimization_branches(self) -> List[str]:
        """List all optimization branches."""
        output = self._run_git_command("branch", "-r", "--list", f"*{self.optimization_branch_prefix}*")
        branches = []
        for line in output.split('\n'):
            if line.strip():
                # Remove 'origin/' prefix if present
                branch = line.strip().replace('origin/', '')
                branches.append(branch)
        return branches
    
    def list_optimization_tags(self) -> List[Dict[str, str]]:
        """List all optimization tags with metadata."""
        output = self._run_git_command("tag", "-l", f"{self.optimization_tag_prefix}*", "--format=%(refname:short)|%(creatordate:iso)|%(subject)")
        
        tags = []
        for line in output.split('\n'):
            if line.strip():
                parts = line.split('|', 2)
                if len(parts) >= 3:
                    tag, date, subject = parts
                    tags.append({
                        "tag": tag,
                        "date": date,
                        "subject": subject
                    })
        
        return tags
    
    def merge_optimization_branch(
        self,
        branch_name: str,
        target_branch: str = "main",
        squash: bool = True
    ) -> str:
        """Merge an optimization branch back to target."""
        # Checkout target branch
        self._run_git_command("checkout", target_branch)
        
        # Merge optimization branch
        if squash:
            self._run_git_command("merge", "--squash", branch_name)
            
            # Create merge commit
            message = f"Merge optimizations from {branch_name}"
            self._run_git_command("commit", "-m", message)
        else:
            self._run_git_command("merge", branch_name)
        
        # Get merge commit
        merge_commit = self._run_git_command("rev-parse", "HEAD")
        
        return merge_commit