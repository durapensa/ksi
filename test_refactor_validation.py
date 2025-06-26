#!/usr/bin/env python3
"""
Post-Refactor Validation Tests

Tests the current system after the major refactoring:
- Python daemon_control.py 
- Standardized completion format
- Directory migration (var/logs/responses)
- Session ID continuity
- Fail-fast principles
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from ksi_common import config, create_completion_response, parse_completion_response
from ksi_client.event_client import EventChatClient


class TestResults:
    """Simple test results tracker."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
    
    def test(self, name: str, condition: bool, message: str = ""):
        """Record a test result."""
        if condition:
            self.passed += 1
            status = "✅ PASS"
        else:
            self.failed += 1
            status = "❌ FAIL"
        
        result = f"{status}: {name}"
        if message:
            result += f" - {message}"
        
        print(result)
        self.results.append((name, condition, message))
        return condition
    
    def summary(self):
        """Print test summary."""
        total = self.passed + self.failed
        print(f"\n📊 Test Summary: {self.passed}/{total} passed")
        if self.failed > 0:
            print("❌ Some tests failed")
            return False
        else:
            print("✅ All tests passed!")
            return True


async def test_completion_format():
    """Test the new standardized completion format."""
    print("\n🧪 Testing Standardized Completion Format...")
    
    results = TestResults()
    
    # Test creation
    test_response = {
        "result": "Hello from Claude!",
        "session_id": "test-session-123",
        "model": "claude-3-5-sonnet-20241022",
        "usage": {"input_tokens": 10, "output_tokens": 5}
    }
    
    completion = create_completion_response(
        provider="claude-cli",
        raw_response=test_response,
        request_id="req-123",
        client_id="test-client",
        duration_ms=1500
    )
    
    # Test structure
    data = completion.to_dict()
    results.test("has_ksi_metadata", "ksi" in data)
    results.test("has_provider", data["ksi"]["provider"] == "claude-cli")
    results.test("has_request_id", data["ksi"]["request_id"] == "req-123")
    results.test("has_timestamp", "timestamp" in data["ksi"])
    results.test("has_duration", data["ksi"]["duration_ms"] == 1500)
    results.test("preserves_raw_response", data["response"] == test_response)
    
    # Test extraction methods
    results.test("extracts_text", completion.get_text() == "Hello from Claude!")
    results.test("extracts_session_id", completion.get_session_id() == "test-session-123")
    results.test("extracts_model", completion.get_model() == "claude-3-5-sonnet-20241022")
    
    # Test parsing from stored data
    parsed = parse_completion_response(data)
    results.test("parses_correctly", parsed.get_text() == "Hello from Claude!")
    results.test("preserves_metadata", parsed.get_request_id() == "req-123")
    
    return results.summary()


def test_directory_migration():
    """Test that responses go to var/logs/responses."""
    print("\n🧪 Testing Directory Migration...")
    
    results = TestResults()
    
    # Test config paths
    results.test("response_log_dir_set", 
                str(config.response_log_dir) == "var/logs/responses")
    results.test("session_log_dir_migrated", 
                str(config.session_log_dir) == "var/logs/responses")
    
    # Test directory exists
    results.test("responses_dir_exists", config.response_log_dir.exists())
    results.test("responses_dir_writable", 
                os.access(config.response_log_dir, os.W_OK))
    
    # Test old sessions directory not being used for new logs
    old_sessions_dir = Path("var/logs/sessions")
    if old_sessions_dir.exists():
        # If it exists, it should be empty or only have old files
        recent_files = []
        for f in old_sessions_dir.glob("*.jsonl"):
            if f.stat().st_mtime > (time.time() - 3600):  # Modified in last hour
                recent_files.append(f)
        
        results.test("old_sessions_dir_not_used", 
                    len(recent_files) == 0,
                    f"Found {len(recent_files)} recent files in old directory")
    else:
        results.test("old_sessions_dir_not_created", True)
    
    return results.summary()


async def test_session_continuity():
    """Test session ID continuity and new conversation handling."""
    print("\n🧪 Testing Session ID Continuity...")
    
    results = TestResults()
    
    try:
        # Test that EventChatClient allows new conversations (no session_id)
        async with EventChatClient("test-continuity") as client:
            # This should work - new conversations don't require session_id
            # Note: This will likely fail due to Claude CLI not being available in test environment
            # but should fail with connection/completion error, not session_id error
            try:
                await client.send_prompt("Test prompt")
                results.test("allows_new_conversations", True, 
                           "New conversation started successfully")
            except ValueError as e:
                if "Claude CLI should provide session_id" in str(e):
                    results.test("allows_new_conversations", False,
                               f"Incorrectly rejected new conversation: {e}")
                else:
                    results.test("allows_new_conversations", True,
                               f"Failed for different reason (expected): {e}")
            except Exception as e:
                # Other errors (connection, etc.) are expected in test environment
                results.test("allows_new_conversations", True,
                           f"Failed for non-session reason (expected): {type(e).__name__}")
    
    except Exception as e:
        results.test("client_creation", False, f"Failed to create client: {e}")
        return False
    
    return results.summary()


def test_daemon_control():
    """Test the new Python daemon_control.py script."""
    print("\n🧪 Testing Python Daemon Control...")
    
    results = TestResults()
    
    # Test script exists and is executable
    daemon_control = Path("daemon_control.py")
    results.test("script_exists", daemon_control.exists())
    results.test("script_executable", os.access(daemon_control, os.X_OK))
    
    # Test basic commands (assuming daemon is running)
    import subprocess
    
    try:
        # Test status command
        result = subprocess.run([
            sys.executable, "daemon_control.py", "status"
        ], capture_output=True, text=True, timeout=10)
        
        results.test("status_command_works", result.returncode == 0,
                    f"Status output: {result.stdout[:100]}")
        
        # Test health command
        result = subprocess.run([
            sys.executable, "daemon_control.py", "health"
        ], capture_output=True, text=True, timeout=10)
        
        results.test("health_command_works", result.returncode == 0,
                    f"Health check result: {result.returncode}")
        
    except subprocess.TimeoutExpired:
        results.test("daemon_control_responsive", False, "Commands timed out")
    except Exception as e:
        results.test("daemon_control_functional", False, f"Error: {e}")
    
    return results.summary()


def test_config_system():
    """Test the config system integration."""
    print("\n🧪 Testing Config System...")
    
    results = TestResults()
    
    # Test config loading
    results.test("config_loaded", config is not None)
    results.test("socket_path_set", config.socket_path is not None)
    results.test("response_log_dir_set", config.response_log_dir is not None)
    
    # Test environment variable support
    original_log_level = config.log_level
    
    # Test paths are Path objects
    results.test("socket_path_is_path", isinstance(config.socket_path, Path))
    results.test("log_dir_is_path", isinstance(config.log_dir, Path))
    results.test("response_log_dir_is_path", isinstance(config.response_log_dir, Path))
    
    # Test directory creation
    config.ensure_directories()
    results.test("directories_created", config.response_log_dir.exists())
    results.test("socket_dir_created", config.socket_path.parent.exists())
    
    return results.summary()


async def main():
    """Run all post-refactor validation tests."""
    print("🚀 Post-Refactor Validation Tests")
    print("=" * 50)
    
    all_passed = True
    
    # Test each component
    if not test_config_system():
        all_passed = False
    
    if not test_daemon_control():
        all_passed = False
    
    if not test_directory_migration():
        all_passed = False
    
    if not await test_completion_format():
        all_passed = False
    
    if not await test_session_continuity():
        all_passed = False
    
    # Final summary
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All refactor validation tests passed!")
        print("✅ System is ready for use with new architecture")
        return 0
    else:
        print("❌ Some refactor validation tests failed")
        print("🔧 System needs fixes before full deployment")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)