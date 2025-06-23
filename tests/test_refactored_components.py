#!/usr/bin/env python3
"""
Test suite for refactored daemon components

Tests the new Pydantic models, base manager, command registry, and utilities
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

# Import refactored components
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from daemon.models import (
    CommandFactory, ResponseFactory, BaseCommand,
    SpawnParameters, AgentInfo, IdentityInfo,
    COMMAND_PARAMETER_MAP
)
from daemon.command_validator_refactored import CommandValidator
from daemon.base_manager import BaseManager, with_error_handling, log_operation
from daemon.utils_refactored import UtilsManager
from daemon.file_operations import FileOperations, LogEntry
from daemon.command_registry import CommandRegistry, command_handler, CommandHandler


class TestPydanticModels:
    """Test Pydantic models for commands and responses"""
    
    def test_spawn_parameters_validation(self):
        """Test SPAWN command parameter validation"""
        # Valid parameters
        params = SpawnParameters(
            mode="async",
            type="claude",
            prompt="Test prompt"
        )
        assert params.mode == "async"
        assert params.model == "sonnet"  # default
        assert params.enable_tools is True  # default
        
        # Invalid mode
        with pytest.raises(ValueError):
            SpawnParameters(mode="invalid", type="claude", prompt="test")
    
    def test_command_factory(self):
        """Test command creation with factory"""
        cmd = CommandFactory.create_command("SPAWN", {
            "mode": "sync",
            "type": "claude",
            "prompt": "Hello, world!"
        })
        
        assert cmd.command == "SPAWN"
        assert cmd.version == "2.0"
        assert cmd.parameters["mode"] == "sync"
    
    def test_response_factory(self):
        """Test response creation"""
        # Success response
        response = ResponseFactory.success("TEST", {"result": "data"}, processing_time_ms=10.5)
        assert response.status == "success"
        assert response.result == {"result": "data"}
        assert response.metadata["processing_time_ms"] == 10.5
        
        # Error response
        error = ResponseFactory.error("TEST", "ERROR_CODE", "Error message")
        assert error.status == "error"
        assert error.error.code == "ERROR_CODE"
        assert error.error.message == "Error message"
    
    def test_agent_info_defaults(self):
        """Test AgentInfo model with defaults"""
        agent = AgentInfo(role="researcher", capabilities=["search", "analyze"])
        
        assert agent.role == "researcher"
        assert agent.status == "active"
        assert agent.model == "sonnet"
        assert len(agent.agent_id) > 0
        assert agent.created_at.endswith("Z")
    
    def test_identity_info_validation(self):
        """Test IdentityInfo model"""
        identity = IdentityInfo(
            agent_id="test-agent",
            display_name="Test Assistant",
            personality_traits=["helpful", "thorough"]
        )
        
        assert identity.role == "general"  # default
        assert identity.stats["messages_sent"] == 0
        assert identity.preferences["communication_style"] == "professional"


class TestCommandValidator:
    """Test the refactored command validator"""
    
    def test_validate_valid_command(self):
        """Test validation of valid commands"""
        validator = CommandValidator()
        
        # Valid command
        is_valid, error, parsed = validator.validate_command({
            "command": "CLEANUP",
            "version": "2.0",
            "parameters": {
                "cleanup_type": "logs"
            }
        })
        
        assert is_valid is True
        assert error is None
        assert parsed["command"] == "CLEANUP"
    
    def test_validate_invalid_command(self):
        """Test validation of invalid commands"""
        validator = CommandValidator()
        
        # Invalid cleanup type
        is_valid, error, parsed = validator.validate_command({
            "command": "CLEANUP",
            "version": "2.0",
            "parameters": {"cleanup_type": "invalid_type"}
        })
        
        assert is_valid is False
        assert "cleanup_type" in error
    
    def test_validate_parameter_types(self):
        """Test parameter type validation"""
        validator = CommandValidator()
        
        # Invalid parameter type
        is_valid, error, parsed = validator.validate_command({
            "command": "SUBSCRIBE",
            "version": "2.0",
            "parameters": {
                "agent_id": "test",
                "event_types": "not_a_list"  # Should be list
            }
        })
        
        assert is_valid is False
        assert "event_types" in error
    
    def test_command_help(self):
        """Test getting command help"""
        validator = CommandValidator()
        
        help_info = validator.get_command_help("SPAWN")
        assert help_info["command"] == "SPAWN"
        assert "mode" in help_info["parameters"]
        assert help_info["parameters"]["mode"]["enum"] == ["sync", "async"]


class TestBaseManager:
    """Test the base manager functionality"""
    
    def test_base_manager_initialization(self, tmp_path):
        """Test base manager creates directories"""
        test_dirs = [str(tmp_path / "dir1"), str(tmp_path / "dir2")]
        
        class TestManager(BaseManager):
            def _initialize(self):
                self.data = {}
            
            def serialize_state(self):
                return {"data": self.data}
            
            def deserialize_state(self, state):
                self.data = state.get("data", {})
        
        manager = TestManager("test", test_dirs)
        
        # Check directories were created
        assert Path(test_dirs[0]).exists()
        assert Path(test_dirs[1]).exists()
    
    def test_json_operations(self, tmp_path):
        """Test JSON save/load operations"""
        class TestManager(BaseManager):
            def _initialize(self):
                pass
            def serialize_state(self):
                return {}
            def deserialize_state(self, state):
                pass
        
        manager = TestManager("test", [str(tmp_path)])
        
        # Save and load JSON
        test_data = {"key": "value", "number": 42}
        json_path = str(tmp_path / "test.json")
        
        manager.save_json_file(json_path, test_data)
        loaded = manager.load_json_file(json_path)
        
        assert loaded == test_data
    
    def test_error_handling_decorator(self):
        """Test error handling decorator"""
        class TestManager(BaseManager):
            def _initialize(self):
                self.call_count = 0
            
            def serialize_state(self):
                return {}
            
            def deserialize_state(self, state):
                pass
            
            @with_error_handling("test_operation")
            def failing_operation(self):
                self.call_count += 1
                raise ValueError("Test error")
        
        manager = TestManager("test", [])
        
        # Should raise but log the error
        with pytest.raises(ValueError):
            manager.failing_operation()
        
        assert manager.call_count == 1


class TestUtilsRefactored:
    """Test the refactored utils manager"""
    
    def test_cleanup_strategies(self, tmp_path):
        """Test cleanup with strategy pattern"""
        # Create test files
        logs_dir = tmp_path / "claude_logs"
        logs_dir.mkdir()
        (logs_dir / "test1.jsonl").write_text("{}")
        (logs_dir / "test2.jsonl").write_text("{}")
        (logs_dir / "latest.jsonl").write_text("{}")
        
        # Mock state manager
        state_manager = Mock()
        state_manager.clear_sessions.return_value = 3
        
        # Change to test directory
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            utils = UtilsManager(state_manager)
            
            # Test logs cleanup
            result = utils.cleanup("logs")
            assert "2" in result  # Should remove 2 files (not latest.jsonl)
            
            # Test sessions cleanup
            result = utils.cleanup("sessions")
            assert "3" in result
            
            # Test unknown cleanup type
            result = utils.cleanup("unknown")
            assert "Unknown cleanup type" in result
            
        finally:
            os.chdir(original_cwd)
    
    def test_module_reload(self, tmp_path):
        """Test module reloading"""
        # Create test module
        modules_dir = tmp_path / "claude_modules"
        modules_dir.mkdir()
        
        module_file = modules_dir / "test_module.py"
        module_file.write_text("""
def handle_output(output, daemon):
    return "Module loaded"
""")
        
        # Change to test directory
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            utils = UtilsManager()
            utils.reload_module("test_module")
            
            assert utils.loaded_module is not None
            assert hasattr(utils.loaded_module, "handle_output")
            
        finally:
            os.chdir(original_cwd)


class TestFileOperations:
    """Test centralized file operations"""
    
    def test_save_load_json(self, tmp_path):
        """Test JSON save and load with atomic writes"""
        test_file = tmp_path / "test.json"
        test_data = {"key": "value", "list": [1, 2, 3]}
        
        # Save
        assert FileOperations.save_json(test_file, test_data)
        
        # Load
        loaded = FileOperations.load_json(test_file)
        assert loaded == test_data
        
        # Load non-existent with default
        default = {"default": True}
        loaded = FileOperations.load_json(tmp_path / "missing.json", default)
        assert loaded == default
    
    def test_jsonl_operations(self, tmp_path):
        """Test JSONL append and read"""
        jsonl_file = tmp_path / "test.jsonl"
        
        # Append entries
        FileOperations.append_jsonl(jsonl_file, {"entry": 1})
        FileOperations.append_jsonl(jsonl_file, {"entry": 2})
        
        # Read all
        entries = FileOperations.read_jsonl(jsonl_file)
        assert len(entries) == 2
        assert entries[0]["entry"] == 1
        assert entries[1]["entry"] == 2
    
    def test_clean_directory(self, tmp_path):
        """Test directory cleaning"""
        # Create test files
        (tmp_path / "file1.txt").write_text("test")
        (tmp_path / "file2.txt").write_text("test")
        (tmp_path / "keep.txt").write_text("test")
        
        # Clean with exclusion
        removed = FileOperations.clean_directory(
            tmp_path, 
            pattern="*.txt",
            exclude=["keep.txt"]
        )
        
        assert removed == 2
        assert (tmp_path / "keep.txt").exists()
        assert not (tmp_path / "file1.txt").exists()
    
    def test_log_entry_creation(self):
        """Test log entry helpers"""
        # Human entry
        entry = LogEntry.human("User input", session_id="123")
        assert entry["type"] == "human"
        assert entry["content"] == "User input"
        assert entry["session_id"] == "123"
        assert "timestamp" in entry
        
        # System entry
        entry = LogEntry.system("System event")
        assert entry["type"] == "system"
        
        # Error entry
        entry = LogEntry.error("Error occurred", details={"code": 500})
        assert entry["type"] == "error"
        assert entry["details"]["code"] == 500


class TestCommandRegistry:
    """Test command registry pattern"""
    
    def test_command_registration(self):
        """Test command handler registration"""
        # Clear registry first
        CommandRegistry._handlers.clear()
        
        @command_handler("TEST_COMMAND")
        class TestHandler(CommandHandler):
            async def handle(self, parameters, writer, full_command):
                return ResponseFactory.success("TEST_COMMAND", {"executed": True})
        
        # Check registration
        assert "TEST_COMMAND" in CommandRegistry.list_commands()
        assert CommandRegistry.get_handler("TEST_COMMAND") == TestHandler
    
    def test_handler_context_access(self):
        """Test handler access to managers"""
        @command_handler("CONTEXT_TEST")
        class ContextTestHandler(CommandHandler):
            async def handle(self, parameters, writer, full_command):
                # Should have access to managers
                return ResponseFactory.success("CONTEXT_TEST", {
                    "has_state_manager": self.state_manager is not None,
                    "has_process_manager": self.process_manager is not None
                })
        
        # Create mock context
        mock_context = Mock()
        mock_context.state_manager = Mock()
        mock_context.process_manager = None
        
        handler = ContextTestHandler(mock_context)
        assert handler.state_manager is not None
        assert handler.process_manager is None


@pytest.mark.asyncio
class TestAsyncComponents:
    """Test async components"""
    
    async def test_command_handler_async(self):
        """Test async command handler"""
        @command_handler("ASYNC_TEST")
        class AsyncTestHandler(CommandHandler):
            async def handle(self, parameters, writer, full_command):
                # Simulate async operation
                import asyncio
                await asyncio.sleep(0.01)
                return ResponseFactory.success("ASYNC_TEST", {"async": True})
        
        # Mock context and writer
        mock_context = Mock()
        mock_writer = AsyncMock()
        
        handler = AsyncTestHandler(mock_context)
        response = await handler.handle({}, mock_writer, {})
        
        assert response.status == "success"
        assert response.result["async"] is True


def test_migration_compatibility():
    """Test that new components are compatible with existing code patterns"""
    
    # Test that we can create commands the old way and validate with new validator
    old_style_command = {
        "command": "SPAWN",
        "version": "2.0",
        "parameters": {
            "mode": "sync",
            "type": "claude",
            "prompt": "Test"
        }
    }
    
    validator = CommandValidator()
    is_valid, error, parsed = validator.validate_command(old_style_command)
    assert is_valid is True
    
    # Test that new responses match old format
    response = ResponseFactory.success("TEST", {"data": "value"})
    response_dict = response.model_dump()
    
    # Should have old format fields
    assert response_dict["status"] == "success"
    assert response_dict["command"] == "TEST"
    assert response_dict["result"]["data"] == "value"
    assert "metadata" in response_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])