#!/usr/bin/env python3
"""
Tests for the KSI agent permissions system.

Tests permission profiles, validation, sandbox management, and integration.
"""

import asyncio
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ksi_common.agent_permissions import (
    PermissionManager, AgentPermissions, PermissionLevel,
    ToolPermissions, FilesystemPermissions, ResourceLimits, Capabilities
)
from ksi_common.sandbox_manager import (
    SandboxManager, SandboxConfig, SandboxMode
)


class TestPermissions(unittest.TestCase):
    """Test permission profiles and validation"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.permissions_dir = Path(self.temp_dir) / "permissions"
        self.permissions_dir.mkdir(parents=True)
        
        # Create test profiles
        (self.permissions_dir / "profiles").mkdir()
        test_profile = {
            "tools": {
                "allowed": ["Read", "Write"],
                "disallowed": ["Bash"]
            },
            "filesystem": {
                "sandbox_root": "./workspace",
                "read_paths": ["./workspace"],
                "write_paths": ["./workspace"],
                "max_file_size_mb": 10,
                "max_total_size_mb": 100,
                "allow_symlinks": False
            },
            "resources": {
                "max_tokens_per_request": 50000,
                "max_total_tokens": 500000,
                "max_requests_per_minute": 30
            },
            "capabilities": {
                "multi_agent_todo": False,
                "agent_messaging": False,
                "spawn_agents": False,
                "network_access": False
            }
        }
        
        with open(self.permissions_dir / "profiles" / "test.yaml", "w") as f:
            import yaml
            yaml.dump(test_profile, f)
        
        self.manager = PermissionManager(self.permissions_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_load_profiles(self):
        """Test loading permission profiles from disk"""
        # Should have loaded the test profile as CUSTOM level
        # Since "test" is not a valid PermissionLevel enum value, it gets loaded as CUSTOM
        profiles = list(self.manager.profiles.keys())
        self.assertGreater(len(profiles), 0)
        
        # Check that at least one profile was loaded
        if profiles:
            first_profile = self.manager.profiles[profiles[0]]
            self.assertIsNotNone(first_profile)
            self.assertEqual(first_profile.level, PermissionLevel.CUSTOM)
        
    def test_tool_permissions(self):
        """Test tool permission checking"""
        tools = ToolPermissions(
            allowed=["Read", "Write", "Edit"],
            disallowed=["Bash"]
        )
        
        self.assertTrue(tools.is_tool_allowed("Read"))
        self.assertTrue(tools.is_tool_allowed("Write"))
        self.assertFalse(tools.is_tool_allowed("Bash"))
        self.assertFalse(tools.is_tool_allowed("Task"))  # Not in allowed list
        
        # Test with None allowed (all tools allowed except disallowed)
        tools_all = ToolPermissions(allowed=None, disallowed=["Bash"])
        self.assertTrue(tools_all.is_tool_allowed("Read"))
        self.assertTrue(tools_all.is_tool_allowed("Task"))
        self.assertFalse(tools_all.is_tool_allowed("Bash"))
    
    def test_filesystem_permissions(self):
        """Test filesystem path validation"""
        fs_perms = FilesystemPermissions(
            sandbox_root="./workspace",
            read_paths=["./workspace", "./shared"],
            write_paths=["./workspace"]
        )
        
        sandbox_dir = Path("/tmp/sandbox")
        
        # Test read permissions
        self.assertTrue(fs_perms.validate_path(Path("workspace/file.txt"), write=False, sandbox_dir=sandbox_dir))
        self.assertTrue(fs_perms.validate_path(Path("shared/data.txt"), write=False, sandbox_dir=sandbox_dir))
        self.assertFalse(fs_perms.validate_path(Path("../../../etc/passwd"), write=False, sandbox_dir=sandbox_dir))
        
        # Test write permissions
        self.assertTrue(fs_perms.validate_path(Path("workspace/output.txt"), write=True, sandbox_dir=sandbox_dir))
        self.assertFalse(fs_perms.validate_path(Path("shared/data.txt"), write=True, sandbox_dir=sandbox_dir))
    
    def test_permission_merging(self):
        """Test merging permissions (taking more restrictive)"""
        perm1 = AgentPermissions(
            level=PermissionLevel.STANDARD,
            tools=ToolPermissions(allowed=["Read", "Write", "Edit"], disallowed=["Bash"]),
            filesystem=FilesystemPermissions(max_file_size_mb=100),
            resources=ResourceLimits(max_tokens_per_request=100000),
            capabilities=Capabilities(network_access=True, spawn_agents=True)
        )
        
        perm2 = AgentPermissions(
            level=PermissionLevel.RESTRICTED,
            tools=ToolPermissions(allowed=["Read"], disallowed=["Bash", "Write"]),
            filesystem=FilesystemPermissions(max_file_size_mb=50),
            resources=ResourceLimits(max_tokens_per_request=50000),
            capabilities=Capabilities(network_access=False, spawn_agents=False)
        )
        
        merged = perm1.merge_with(perm2)
        
        # Should take intersection of allowed tools
        self.assertEqual(merged.tools.allowed, ["Read"])
        # Should take union of disallowed tools
        self.assertIn("Bash", merged.tools.disallowed)
        self.assertIn("Write", merged.tools.disallowed)
        # Should take minimum limits
        self.assertEqual(merged.filesystem.max_file_size_mb, 50)
        self.assertEqual(merged.resources.max_tokens_per_request, 50000)
        # Should take more restrictive capabilities
        self.assertFalse(merged.capabilities.network_access)
        self.assertFalse(merged.capabilities.spawn_agents)
    
    def test_spawn_permission_validation(self):
        """Test parent-child permission validation"""
        parent = AgentPermissions(
            level=PermissionLevel.TRUSTED,
            tools=ToolPermissions(allowed=None, disallowed=["Task"]),
            filesystem=FilesystemPermissions(max_file_size_mb=100),
            resources=ResourceLimits(max_tokens_per_request=100000),
            capabilities=Capabilities(spawn_agents=True, network_access=True)
        )
        
        # Valid child - subset of parent permissions
        valid_child = AgentPermissions(
            level=PermissionLevel.STANDARD,
            tools=ToolPermissions(allowed=["Read", "Write"], disallowed=["Bash"]),
            filesystem=FilesystemPermissions(max_file_size_mb=50),
            resources=ResourceLimits(max_tokens_per_request=50000),
            capabilities=Capabilities(spawn_agents=False, network_access=True)
        )
        
        self.assertTrue(parent.can_spawn_child(valid_child))
        
        # Invalid child - exceeds parent limits
        invalid_child = AgentPermissions(
            level=PermissionLevel.TRUSTED,
            tools=ToolPermissions(allowed=None, disallowed=[]),  # Allows more tools
            filesystem=FilesystemPermissions(max_file_size_mb=200),  # Exceeds parent
            resources=ResourceLimits(max_tokens_per_request=200000),  # Exceeds parent
            capabilities=Capabilities(spawn_agents=True, network_access=True)
        )
        
        self.assertFalse(parent.can_spawn_child(invalid_child))
        
        # Parent without spawn capability cannot spawn
        non_spawner = AgentPermissions(
            level=PermissionLevel.STANDARD,
            tools=ToolPermissions(allowed=["Read"]),
            filesystem=FilesystemPermissions(),
            resources=ResourceLimits(),
            capabilities=Capabilities(spawn_agents=False)
        )
        
        self.assertFalse(non_spawner.can_spawn_child(valid_child))


class TestSandboxManager(unittest.TestCase):
    """Test sandbox creation and management"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sandbox_root = Path(self.temp_dir) / "sandbox"
        self.manager = SandboxManager(self.sandbox_root)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_create_isolated_sandbox(self):
        """Test creating an isolated sandbox"""
        config = SandboxConfig(mode=SandboxMode.ISOLATED)
        sandbox = self.manager.create_sandbox("agent_1", config)
        
        self.assertEqual(sandbox.agent_id, "agent_1")
        self.assertEqual(sandbox.config.mode, SandboxMode.ISOLATED)
        self.assertTrue(sandbox.path.exists())
        self.assertTrue(sandbox.workspace_path.exists())
        self.assertTrue(sandbox.shared_path.exists())
        self.assertTrue(sandbox.exports_path.exists())
        self.assertTrue(sandbox.claude_path.exists())
        
        # Check metadata
        metadata_file = sandbox.path / ".sandbox_metadata.json"
        self.assertTrue(metadata_file.exists())
        with open(metadata_file) as f:
            metadata = json.load(f)
        self.assertEqual(metadata["agent_id"], "agent_1")
    
    def test_create_shared_sandbox(self):
        """Test creating a shared session sandbox"""
        config = SandboxConfig(
            mode=SandboxMode.SHARED,
            session_id="session_123",
            session_share=True
        )
        
        # Create first agent in shared sandbox
        sandbox1 = self.manager.create_sandbox("agent_1", config)
        expected_path = self.sandbox_root / "shared" / "session_123"
        self.assertEqual(sandbox1.path, expected_path)
        
        # Create second agent in same shared sandbox
        sandbox2 = self.manager.create_sandbox("agent_2", config)
        self.assertEqual(sandbox2.path, expected_path)
        
        # Both agents share the same workspace
        self.assertEqual(sandbox1.workspace_path, sandbox2.workspace_path)
    
    def test_create_nested_sandbox(self):
        """Test creating a nested sandbox"""
        # Create parent
        parent_config = SandboxConfig(mode=SandboxMode.ISOLATED)
        parent_sandbox = self.manager.create_sandbox("parent", parent_config)
        
        # Create child nested in parent
        child_config = SandboxConfig(
            mode=SandboxMode.NESTED,
            parent_agent_id="parent",
            parent_share="read_only"
        )
        child_sandbox = self.manager.create_sandbox("child", child_config)
        
        expected_path = parent_sandbox.path / "nested" / "child"
        self.assertEqual(child_sandbox.path, expected_path)
        self.assertTrue(child_sandbox.path.exists())
        
        # Check parent link
        parent_link = child_sandbox.path / "parent"
        self.assertTrue(parent_link.exists())
        self.assertTrue(parent_link.is_symlink())
    
    def test_remove_sandbox(self):
        """Test removing sandboxes"""
        config = SandboxConfig(mode=SandboxMode.ISOLATED)
        sandbox = self.manager.create_sandbox("agent_1", config)
        path = sandbox.path
        
        # Remove sandbox
        success = self.manager.remove_sandbox("agent_1")
        self.assertTrue(success)
        self.assertFalse(path.exists())
        self.assertIsNone(self.manager.get_sandbox("agent_1"))
    
    def test_sandbox_stats(self):
        """Test getting sandbox statistics"""
        # Create various sandboxes
        self.manager.create_sandbox("isolated_1", SandboxConfig(mode=SandboxMode.ISOLATED))
        self.manager.create_sandbox("isolated_2", SandboxConfig(mode=SandboxMode.ISOLATED))
        
        shared_config = SandboxConfig(mode=SandboxMode.SHARED, session_id="session_1")
        self.manager.create_sandbox("shared_1", shared_config)
        self.manager.create_sandbox("shared_2", shared_config)
        
        stats = self.manager.get_sandbox_stats()
        self.assertEqual(stats["total_sandboxes"], 4)
        self.assertEqual(stats["isolated"], 2)
        self.assertEqual(stats["shared"], 2)
        self.assertEqual(stats["by_session"]["session_1"], 2)


class TestPermissionIntegration(unittest.TestCase):
    """Test integration between permissions and sandboxes"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.permissions_dir = Path(self.temp_dir) / "permissions"
        self.sandbox_root = Path(self.temp_dir) / "sandbox"
        
        self.perm_manager = PermissionManager(self.permissions_dir)
        self.sandbox_manager = SandboxManager(self.sandbox_root)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_agent_lifecycle(self):
        """Test full agent lifecycle with permissions and sandbox"""
        agent_id = "test_agent"
        
        # Set agent permissions
        permissions = AgentPermissions(
            level=PermissionLevel.STANDARD,
            tools=ToolPermissions(allowed=["Read", "Write"], disallowed=["Bash"]),
            filesystem=FilesystemPermissions(),
            resources=ResourceLimits(),
            capabilities=Capabilities()
        )
        self.perm_manager.set_agent_permissions(agent_id, permissions)
        
        # Create sandbox
        sandbox = self.sandbox_manager.create_sandbox(
            agent_id,
            SandboxConfig(mode=SandboxMode.ISOLATED)
        )
        
        # Verify setup
        self.assertIsNotNone(self.perm_manager.get_agent_permissions(agent_id))
        self.assertIsNotNone(self.sandbox_manager.get_sandbox(agent_id))
        
        # Get claude-cli args
        cli_args = self.perm_manager.get_claude_cli_args(agent_id)
        self.assertEqual(cli_args["allowed_tools"], ["Read", "Write"])
        
        # Clean up
        self.perm_manager.remove_agent_permissions(agent_id)
        self.sandbox_manager.remove_sandbox(agent_id)
        
        # Verify cleanup
        self.assertIsNone(self.perm_manager.get_agent_permissions(agent_id))
        self.assertIsNone(self.sandbox_manager.get_sandbox(agent_id))


if __name__ == '__main__':
    unittest.main()