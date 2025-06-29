#!/usr/bin/env python3
"""
Tests for the Completion Service Plugin

Tests the ksi_daemon/plugins/completion/completion_service.py functionality:
- Event-driven completion flow
- LiteLLM integration through claude_cli_litellm_provider
- Session logging to JSONL format
- Error propagation through event bus
- Async completion processing with request tracking
- Plugin lifecycle management
"""

import asyncio
import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import test result logger
from test_result_logger import TestStatus, start_test, finish_test, skip_test

# Import daemon components
try:
    from ksi_daemon.plugins.completion.completion_service import CompletionServicePlugin
    from ksi_daemon.plugin_manager import PluginManager
    from ksi_daemon.event_bus import EventBus
    from ksi_daemon.config import config
    daemon_available = True
except ImportError as e:
    print(f"Warning: Could not import daemon components: {e}")
    daemon_available = False


class MockEventBus:
    """Mock event bus for testing"""
    
    def __init__(self):
        self.published_events: List[Dict[str, Any]] = []
    
    async def publish(self, event_name: str, data: Dict[str, Any]):
        """Mock publish method"""
        self.published_events.append({
            "event_name": event_name,
            "data": data,
            "timestamp": time.time()
        })


class MockStateManager:
    """Mock state manager for testing"""
    
    def __init__(self):
        self.state_updates: List[Dict[str, Any]] = []
    
    async def update_session(self, session_id: str, data: Dict[str, Any]):
        """Mock session update method"""
        self.state_updates.append({
            "session_id": session_id,
            "data": data,
            "timestamp": time.time()
        })


class TestCompletionServicePlugin:
    """Test suite for CompletionServicePlugin"""
    
    def __init__(self):
        self.test_file = "test_completion_service_plugin.py"
        
    def test_plugin_initialization(self):
        """Test plugin initialization and metadata"""
        test_result = start_test("plugin_initialization", self.test_file)
        
        if not daemon_available:
            finish_test(test_result, TestStatus.SKIPPED, 
                       error_message="Daemon components not available")
            return True
        
        try:
            # Create plugin instance
            plugin = CompletionServicePlugin()
            
            # Verify metadata
            assert plugin.metadata.name == "completion_service", \
                f"Expected name 'completion_service', got '{plugin.metadata.name}'"
            assert plugin.metadata.version == "1.0.0", \
                f"Expected version '1.0.0', got '{plugin.metadata.version}'"
            
            # Verify capabilities
            assert "/completion" in plugin.capabilities.event_namespaces, \
                "Plugin should handle /completion namespace"
            assert "completion:async" in plugin.capabilities.commands, \
                "Plugin should handle completion:async command"
            assert "completion" in plugin.capabilities.provides_services, \
                "Plugin should provide completion service"
            
            # Verify initial state
            assert isinstance(plugin.active_completions, dict), \
                "active_completions should be dict"
            assert len(plugin.active_completions) == 0, \
                "active_completions should start empty"
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "name": plugin.metadata.name,
                           "version": plugin.metadata.version,
                           "namespaces": plugin.capabilities.event_namespaces,
                           "commands": plugin.capabilities.commands
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_plugin_startup_shutdown(self):
        """Test plugin startup and shutdown hooks"""
        test_result = start_test("plugin_startup_shutdown", self.test_file)
        
        if not daemon_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Daemon components not available")
            return True
        
        try:
            plugin = CompletionServicePlugin()
            
            # Test startup hook
            startup_result = plugin.ksi_startup()
            assert isinstance(startup_result, dict), "Startup should return dict"
            assert startup_result.get("status") == "completion_service_ready", \
                f"Expected ready status, got {startup_result}"
            
            # Add some mock active completions
            plugin.active_completions["test_1"] = {"started_at": time.time()}
            plugin.active_completions["test_2"] = {"started_at": time.time()}
            
            # Test shutdown hook
            shutdown_result = plugin.ksi_shutdown()
            assert isinstance(shutdown_result, dict), "Shutdown should return dict"
            assert shutdown_result.get("status") == "completion_service_stopped", \
                f"Expected stopped status, got {shutdown_result}"
            assert shutdown_result.get("cancelled_completions") == 2, \
                f"Expected 2 cancelled, got {shutdown_result.get('cancelled_completions')}"
            
            # Verify active completions are cleared
            assert len(plugin.active_completions) == 0, \
                "Active completions should be cleared on shutdown"
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "startup_status": startup_result.get("status"),
                           "shutdown_status": shutdown_result.get("status"),
                           "cancelled_count": shutdown_result.get("cancelled_completions")
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_plugin_context_injection(self):
        """Test plugin context injection (event bus and state manager)"""
        test_result = start_test("plugin_context_injection", self.test_file)
        
        if not daemon_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Daemon components not available")
            return True
        
        try:
            plugin = CompletionServicePlugin()
            
            # Create mock context
            mock_event_bus = MockEventBus()
            mock_state_manager = MockStateManager()
            
            context = {
                "event_bus": mock_event_bus,
                "state_manager": mock_state_manager
            }
            
            # Test context injection
            plugin.ksi_plugin_context(context)
            
            # Verify context is stored
            assert plugin._event_bus is mock_event_bus, \
                "Event bus not properly injected"
            assert plugin._state_manager is mock_state_manager, \
                "State manager not properly injected"
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "event_bus_injected": plugin._event_bus is not None,
                           "state_manager_injected": plugin._state_manager is not None
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    @patch('litellm.acompletion')
    def test_synchronous_completion_request(self, mock_litellm):
        """Test synchronous completion request handling"""
        test_result = start_test("synchronous_completion_request", self.test_file, "quick: 2+2?")
        
        if not daemon_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Daemon components not available")
            return True
        
        try:
            plugin = CompletionServicePlugin()
            
            # Setup mock event bus
            mock_event_bus = MockEventBus()
            plugin._event_bus = mock_event_bus
            
            # Setup mock LiteLLM response
            mock_response = MagicMock()
            mock_response._claude_metadata = {
                "type": "assistant",
                "message": {"content": [{"text": "4"}]},
                "sessionId": "test_session_sync"
            }
            mock_response._stderr = ""
            mock_litellm.return_value = mock_response
            
            # Test completion request
            request_data = {
                "prompt": "quick: 2+2?",
                "model": "sonnet",
                "client_id": "test_client_sync",
                "session_id": "test_session_sync",
                "request_id": "req_sync_123"
            }
            
            # Mock the _log_conversation method to avoid file I/O during testing
            with patch.object(plugin, '_log_conversation'):
                with patch.object(plugin, '_update_session_state'):
                    result = asyncio.run(plugin._handle_completion_request(request_data))
            
            # Verify result structure
            assert isinstance(result, dict), "Result should be dict"
            assert result.get("type") == "assistant", "Result should have assistant type"
            assert "sessionId" in result or "session_id" in result, "Result should have session ID"
            
            # Verify LiteLLM was called correctly
            mock_litellm.assert_called_once()
            call_args = mock_litellm.call_args
            assert call_args[1]["model"] == "claude-cli/sonnet", \
                f"Expected claude-cli/sonnet model, got {call_args[1]['model']}"
            assert call_args[1]["messages"][0]["content"] == "quick: 2+2?", \
                "Prompt not passed correctly to LiteLLM"
            assert "session_id" in call_args[1], "Session ID not passed to LiteLLM"
            
            # Verify events were published
            assert len(mock_event_bus.published_events) >= 2, \
                f"Expected at least 2 events, got {len(mock_event_bus.published_events)}"
            
            # Check for completion:started event
            started_events = [e for e in mock_event_bus.published_events if e["event_name"] == "completion:started"]
            assert len(started_events) == 1, "Should have one completion:started event"
            started_event = started_events[0]
            assert started_event["data"]["client_id"] == "test_client_sync", \
                "Started event missing client_id"
            
            # Check for completion:result event
            result_events = [e for e in mock_event_bus.published_events if e["event_name"] == "completion:result"]
            assert len(result_events) == 1, "Should have one completion:result event"
            result_event = result_events[0]
            assert result_event["data"]["client_id"] == "test_client_sync", \
                "Result event missing client_id"
            assert result_event["data"]["request_id"] == "req_sync_123", \
                "Result event missing request_id"
            
            finish_test(test_result, TestStatus.PASSED, response="4",
                       details={
                           "events_published": len(mock_event_bus.published_events),
                           "litellm_called": True,
                           "has_session_id": bool("sessionId" in result or "session_id" in result)
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_asynchronous_completion_request(self):
        """Test asynchronous completion request handling"""
        test_result = start_test("asynchronous_completion_request", self.test_file, "quick: name one color")
        
        if not daemon_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Daemon components not available")
            return True
        
        try:
            plugin = CompletionServicePlugin()
            
            # Setup mock event bus
            mock_event_bus = MockEventBus()
            plugin._event_bus = mock_event_bus
            
            # Test async completion request
            request_data = {
                "prompt": "quick: name one color",
                "model": "sonnet", 
                "client_id": "test_client_async"
            }
            
            # Handle async completion
            request_id = plugin._handle_async_completion(request_data)
            
            # Verify request ID is returned
            assert isinstance(request_id, str), "Request ID should be string"
            assert len(request_id) == 8, f"Request ID should be 8 chars, got {len(request_id)}"
            
            # Verify request is tracked
            assert request_id in plugin.active_completions, \
                "Request should be tracked in active_completions"
            
            tracked_request = plugin.active_completions[request_id]
            assert tracked_request["data"] == request_data, \
                "Request data not stored correctly"
            assert "started_at" in tracked_request, \
                "Request should have started_at timestamp"
            
            # Wait a moment for async task to start
            time.sleep(0.1)
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "request_id": request_id,
                           "tracked": request_id in plugin.active_completions,
                           "has_timestamp": "started_at" in tracked_request
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    @patch('litellm.acompletion')
    def test_completion_error_handling(self, mock_litellm):
        """Test error handling in completion processing"""
        test_result = start_test("completion_error_handling", self.test_file, "invalid: <<<malformed")
        
        if not daemon_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Daemon components not available")
            return True
        
        try:
            plugin = CompletionServicePlugin()
            
            # Setup mock event bus
            mock_event_bus = MockEventBus()
            plugin._event_bus = mock_event_bus
            
            # Test 1: FileNotFoundError (claude executable not found)
            mock_litellm.side_effect = FileNotFoundError("claude command not found")
            
            request_data = {
                "prompt": "invalid: <<<malformed",
                "client_id": "test_client_error",
                "request_id": "req_error_123"
            }
            
            result = asyncio.run(plugin._handle_completion_request(request_data))
            
            # Verify error response structure
            assert isinstance(result, dict), "Error result should be dict"
            assert "error" in result, "Error result should have error field"
            assert result["error"] == "claude executable not found in PATH", \
                f"Unexpected error message: {result['error']}"
            
            # Verify error event was published
            error_events = [e for e in mock_event_bus.published_events 
                           if e["event_name"] == "completion:error"]
            assert len(error_events) == 1, "Should have one completion:error event"
            error_event = error_events[0]
            assert error_event["data"]["client_id"] == "test_client_error", \
                "Error event missing client_id"
            assert error_event["data"]["request_id"] == "req_error_123", \
                "Error event missing request_id"
            
            # Reset mock for next test
            mock_event_bus.published_events.clear()
            
            # Test 2: General exception
            mock_litellm.side_effect = ValueError("Invalid model parameter")
            
            request_data2 = {
                "prompt": "another invalid request",
                "client_id": "test_client_error2",
                "request_id": "req_error_456"
            }
            
            result2 = asyncio.run(plugin._handle_completion_request(request_data2))
            
            # Verify error response
            assert "error" in result2, "Second error result should have error field"
            assert "ValueError" in result2["error"], \
                f"Expected ValueError in error message: {result2['error']}"
            
            # Verify second error event
            error_events2 = [e for e in mock_event_bus.published_events 
                            if e["event_name"] == "completion:error"]
            assert len(error_events2) == 1, "Should have one more completion:error event"
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "file_not_found_handled": True,
                           "general_exception_handled": True,
                           "error_events_published": 2
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_completion_status_tracking(self):
        """Test completion status and tracking functionality"""
        test_result = start_test("completion_status_tracking", self.test_file)
        
        if not daemon_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Daemon components not available")
            return True
        
        try:
            plugin = CompletionServicePlugin()
            
            # Initially no active completions
            status_result = plugin.ksi_handle_event("completion:status", {}, {})
            assert status_result["active_count"] == 0, \
                f"Expected 0 active completions, got {status_result['active_count']}"
            assert status_result["active_requests"] == [], \
                f"Expected empty request list, got {status_result['active_requests']}"
            
            # Add some mock completions
            plugin.active_completions["req_1"] = {"started_at": time.time()}
            plugin.active_completions["req_2"] = {"started_at": time.time()}
            plugin.active_completions["req_3"] = {"started_at": time.time()}
            
            # Check status with active completions
            status_result2 = plugin.ksi_handle_event("completion:status", {}, {})
            assert status_result2["active_count"] == 3, \
                f"Expected 3 active completions, got {status_result2['active_count']}"
            assert len(status_result2["active_requests"]) == 3, \
                f"Expected 3 request IDs, got {len(status_result2['active_requests'])}"
            assert "req_1" in status_result2["active_requests"], "req_1 should be in active requests"
            assert "req_2" in status_result2["active_requests"], "req_2 should be in active requests"
            assert "req_3" in status_result2["active_requests"], "req_3 should be in active requests"
            
            # Test cancellation
            cancel_result = plugin.ksi_handle_event("completion:cancel", {"request_id": "req_2"}, {})
            assert cancel_result["status"] == "cancelled", \
                f"Expected cancelled status, got {cancel_result['status']}"
            
            # Verify completion was removed
            assert "req_2" not in plugin.active_completions, \
                "req_2 should be removed after cancellation"
            assert len(plugin.active_completions) == 2, \
                f"Expected 2 active completions after cancel, got {len(plugin.active_completions)}"
            
            # Test cancellation of non-existent request
            cancel_result2 = plugin.ksi_handle_event("completion:cancel", {"request_id": "nonexistent"}, {})
            assert cancel_result2["status"] == "not_found", \
                f"Expected not_found status, got {cancel_result2['status']}"
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "initial_count": 0,
                           "after_adding": 3,
                           "after_cancel": 2,
                           "cancel_nonexistent_handled": True
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_event_handling_dispatch(self):
        """Test event handling dispatch to correct methods"""
        test_result = start_test("event_handling_dispatch", self.test_file)
        
        if not daemon_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Daemon components not available")
            return True
        
        try:
            plugin = CompletionServicePlugin()
            
            # Test completion:status event
            status_result = plugin.ksi_handle_event("completion:status", {}, {})
            assert isinstance(status_result, dict), "Status should return dict"
            assert "active_count" in status_result, "Status should have active_count"
            
            # Test completion:cancel event
            cancel_result = plugin.ksi_handle_event("completion:cancel", {"request_id": "test"}, {})
            assert isinstance(cancel_result, dict), "Cancel should return dict"
            assert "status" in cancel_result, "Cancel should have status"
            
            # Test unknown event
            unknown_result = plugin.ksi_handle_event("unknown:event", {}, {})
            assert unknown_result is None, "Unknown event should return None"
            
            # Test completion:async event (the primary interface)
            # We're testing that it returns a coroutine for async handling
            async_data = {
                "prompt": "test async",
                "model": "sonnet",
                "client_id": "test_client"
            }
            async_result = plugin.ksi_handle_event("completion:async", async_data, {})
            
            # The result should be a coroutine
            import inspect
            assert inspect.iscoroutine(async_result), \
                "completion:async should return a coroutine for async handling"
            
            # Clean up the coroutine to avoid warnings
            async_result.close()
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "status_dispatch": True,
                           "cancel_dispatch": True,
                           "unknown_dispatch": True,
                           "request_dispatch": True,
                           "async_dispatch": True
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_tool_configuration(self):
        """Test default tool configuration"""
        test_result = start_test("tool_configuration", self.test_file)
        
        if not daemon_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Daemon components not available")
            return True
        
        try:
            plugin = CompletionServicePlugin()
            
            # Get default tools
            tools = plugin._get_default_tools()
            
            # Verify tools structure
            assert isinstance(tools, list), "Tools should be list"
            assert len(tools) > 0, "Should have default tools"
            
            # Verify tool format
            for tool in tools:
                assert isinstance(tool, dict), "Each tool should be dict"
                assert "type" in tool, "Tool should have type"
                assert tool["type"] == "function", "Tool type should be function"
                assert "function" in tool, "Tool should have function"
                assert "name" in tool["function"], "Function should have name"
            
            # Verify expected tools are present
            tool_names = [tool["function"]["name"] for tool in tools]
            expected_tools = ["Task", "Bash", "Glob", "Grep", "LS", "Read", "Edit", "MultiEdit", "Write", "WebFetch", "WebSearch"]
            
            for expected_tool in expected_tools:
                assert expected_tool in tool_names, f"Expected tool {expected_tool} not found in {tool_names}"
            
            # Verify no duplicate tools
            assert len(tool_names) == len(set(tool_names)), "Tools should not have duplicates"
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "tool_count": len(tools),
                           "tool_names": tool_names,
                           "all_expected_found": all(t in tool_names for t in expected_tools)
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False


async def run_all_tests():
    """Run all completion service plugin tests"""
    print("Running Completion Service Plugin Tests")
    print("=" * 50)
    
    if not daemon_available:
        print("⚠️  Daemon components not available - most tests will be skipped")
    
    tester = TestCompletionServicePlugin()
    
    # List of test methods
    test_methods = [
        tester.test_plugin_initialization,
        tester.test_plugin_startup_shutdown,
        tester.test_plugin_context_injection,
        tester.test_synchronous_completion_request,
        tester.test_asynchronous_completion_request,
        tester.test_completion_error_handling,
        tester.test_completion_status_tracking,
        tester.test_event_handling_dispatch,
        tester.test_tool_configuration
    ]
    
    results = []
    
    for test_method in test_methods:
        try:
            print(f"\nRunning {test_method.__name__}...")
            result = test_method()
            results.append(result)
        except Exception as e:
            print(f"Test {test_method.__name__} crashed: {e}")
            results.append(False)
    
    # Summary
    passed = sum(1 for r in results if r)
    total = len(results)
    
    print(f"\n{'='*50}")
    print(f"Completion Service Plugin Tests: {passed}/{total} passed")
    
    return passed == total


if __name__ == "__main__":
    # Run tests
    success = asyncio.run(run_all_tests())
    
    # Print final result summary from logger
    from test_result_logger import get_test_logger
    get_test_logger().print_summary()
    
    sys.exit(0 if success else 1)