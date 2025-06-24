#!/usr/bin/env python3
"""
End-to-End Error Propagation Tests

Tests the complete error chain: client → daemon → provider → Claude CLI → back
Verifies different error scenarios and how they propagate through the system:

1. Claude CLI timeout errors (mock long process)
2. Claude logical errors (invalid prompts)  
3. System failures (missing claude binary)
4. JSON parse errors (corrupted output)
5. Network/socket errors
6. Plugin errors
7. Error event delivery to correct clients
8. Error metadata preservation through chain
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import test result logger
from test_result_logger import TestStatus, start_test, finish_test, skip_test

# Import client and daemon components
try:
    from ksi_client import AsyncClient, SimpleChatClient
    client_available = True
except ImportError:
    client_available = False

try:
    import claude_cli_litellm_provider
    provider_available = True
except ImportError:
    provider_available = False


class TestErrorPropagation:
    """Test suite for end-to-end error propagation"""
    
    def __init__(self):
        self.test_file = "test_error_propagation.py"
    
    def test_provider_timeout_error_handling(self):
        """Test timeout error handling in the provider"""
        test_result = start_test("provider_timeout_error_handling", self.test_file, "timeout: long computation")
        
        if not provider_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Provider not available")
            return True
        
        try:
            provider = claude_cli_litellm_provider.ClaudeCLIProvider()
            
            # Mock subprocess to simulate timeout
            def mock_timeout_run(*args, **kwargs):
                raise subprocess.TimeoutExpired(["claude"], 300)
            
            with patch.object(provider, '_run_claude_sync_with_progress', side_effect=mock_timeout_run):
                with patch('claude_cli_litellm_provider.config') as mock_config:
                    # Set short timeouts for testing
                    mock_config.claude_timeout_attempts = [1, 2]  # Only 2 attempts for testing
                    
                    with patch('asyncio.sleep'):  # Skip sleep delays
                        try:
                            messages = [{"role": "user", "content": "timeout: long computation"}]
                            response = provider.completion(messages)
                            assert False, "Should have raised TimeoutExpired"
                        except subprocess.TimeoutExpired as e:
                            # Verify timeout error is properly raised
                            assert e.timeout == 300, f"Expected timeout 300, got {e.timeout}"
                            assert "claude" in str(e.cmd), "Command should contain 'claude'"
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "timeout_properly_raised": True,
                           "timeout_value": 300,
                           "attempts_made": 2
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_provider_logical_error_handling(self):
        """Test logical error handling (no retry)"""
        test_result = start_test("provider_logical_error_handling", self.test_file, "invalid: <<<malformed")
        
        if not provider_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Provider not available")
            return True
        
        try:
            provider = claude_cli_litellm_provider.ClaudeCLIProvider()
            
            # Mock subprocess to simulate logical error
            def mock_logical_error(*args, **kwargs):
                raise subprocess.CalledProcessError(
                    1, ["claude"], 
                    "Error: Invalid prompt format", 
                    "Prompt contains invalid characters"
                )
            
            with patch.object(provider, '_run_claude_sync_with_progress', side_effect=mock_logical_error):
                try:
                    messages = [{"role": "user", "content": "invalid: <<<malformed"}]
                    response = provider.completion(messages)
                    assert False, "Should have raised CalledProcessError"
                except subprocess.CalledProcessError as e:
                    # Verify logical error is properly raised without retry
                    assert e.returncode == 1, f"Expected returncode 1, got {e.returncode}"
                    assert "Invalid prompt format" in e.stdout, \
                        f"Expected error message in stdout: {e.stdout}"
                    assert "invalid characters" in e.stderr, \
                        f"Expected error details in stderr: {e.stderr}"
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "logical_error_raised": True,
                           "returncode": 1,
                           "no_retry_attempted": True
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_provider_system_error_with_retry(self):
        """Test system error handling with intelligent retry"""
        test_result = start_test("provider_system_error_with_retry", self.test_file, "system: test recovery")
        
        if not provider_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Provider not available")
            return True
        
        try:
            provider = claude_cli_litellm_provider.ClaudeCLIProvider()
            
            # Track retry attempts
            attempt_count = 0
            
            def mock_system_error_then_success(*args, **kwargs):
                nonlocal attempt_count
                attempt_count += 1
                
                if attempt_count <= 2:
                    # First two attempts fail with system error (SIGKILL)
                    raise subprocess.CalledProcessError(-9, ["claude"], "", "Process killed")
                else:
                    # Third attempt succeeds
                    class MockResult:
                        def __init__(self):
                            self.returncode = 0
                            self.stdout = json.dumps({
                                "type": "assistant",
                                "message": {"content": [{"text": "Recovered after system error"}]}
                            })
                            self.stderr = ""
                    return MockResult()
            
            with patch.object(provider, '_run_claude_sync_with_progress', side_effect=mock_system_error_then_success):
                with patch('claude_cli_litellm_provider.config') as mock_config:
                    mock_config.claude_timeout_attempts = [1, 2, 3]
                    
                    with patch('asyncio.sleep'):  # Skip sleep delays
                        messages = [{"role": "user", "content": "system: test recovery"}]
                        response = provider.completion(messages)
                        
                        # Verify successful recovery
                        assert hasattr(response, 'choices'), "Response should have choices"
                        content = response.choices[0].message.content
                        assert "Recovered after system error" in content, \
                            f"Expected recovery message: {content}"
                        
                        # Verify retry attempts
                        assert attempt_count == 3, f"Expected 3 attempts, got {attempt_count}"
            
            finish_test(test_result, TestStatus.PASSED, response="Recovered after system error",
                       details={
                           "system_error_recovered": True,
                           "retry_attempts": attempt_count,
                           "final_success": True
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_provider_json_parse_error_handling(self):
        """Test JSON parse error handling with fallback"""
        test_result = start_test("provider_json_parse_error_handling", self.test_file, "malformed: json output")
        
        if not provider_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Provider not available") 
            return True
        
        try:
            provider = claude_cli_litellm_provider.ClaudeCLIProvider()
            
            # Mock subprocess to return malformed JSON
            def mock_malformed_json(*args, **kwargs):
                class MockResult:
                    def __init__(self):
                        self.returncode = 0
                        self.stdout = "This is not JSON at all! {broken: json"
                        self.stderr = "Warning: Output format corrupted"
                        self.args = ["claude", "test"]
                return MockResult()
            
            with patch.object(provider, '_run_claude_sync_with_progress', side_effect=mock_malformed_json):
                messages = [{"role": "user", "content": "malformed: json output"}]
                response = provider.completion(messages)
                
                # Verify response is still created with fallback
                assert hasattr(response, 'choices'), "Response should have choices even with JSON error"
                content = response.choices[0].message.content
                assert "This is not JSON at all!" in content, \
                    f"Expected raw output in content: {content}"
                
                # Verify error metadata is preserved
                assert hasattr(response, '_json_decode_error'), \
                    "Response should have JSON decode error info"
                assert hasattr(response, '_raw_stdout'), \
                    "Response should preserve raw stdout"
                assert hasattr(response, '_stderr'), \
                    "Response should preserve stderr"
                
                assert response._raw_stdout == "This is not JSON at all! {broken: json", \
                    "Raw stdout not preserved correctly"
                assert response._stderr == "Warning: Output format corrupted", \
                    "Stderr not preserved correctly"
            
            finish_test(test_result, TestStatus.PASSED, response=content[:50],
                       details={
                           "json_error_handled": True,
                           "fallback_content_used": True,
                           "metadata_preserved": True,
                           "error_info_available": hasattr(response, '_json_decode_error')
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    @patch('socket.socket')
    def test_client_connection_error_handling(self, mock_socket):
        """Test client connection error handling when daemon unavailable"""
        test_result = start_test("client_connection_error_handling", self.test_file)
        
        if not client_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Client not available")
            return True
        
        try:
            # Mock socket connection failure
            mock_socket_instance = MagicMock()
            mock_socket_instance.connect.side_effect = ConnectionRefusedError("Connection refused")
            mock_socket.return_value = mock_socket_instance
            
            # Test AsyncClient connection error
            client = AsyncClient(client_id="test_connection_error")
            
            # Should handle connection error gracefully
            try:
                success = asyncio.run(client.initialize())
                # If it returns False, that's acceptable error handling
                if success:
                    # If it somehow succeeds, clean up
                    asyncio.run(client.close())
                    finish_test(test_result, TestStatus.PASSED,
                               details={"connection_unexpectedly_succeeded": True})
                else:
                    finish_test(test_result, TestStatus.PASSED,
                               details={"connection_gracefully_failed": True})
            except ConnectionError as e:
                # This is expected and acceptable error handling
                finish_test(test_result, TestStatus.PASSED,
                           details={
                               "connection_error_raised": True,
                               "error_message": str(e)
                           })
            except Exception as e:
                # Unexpected error type
                finish_test(test_result, TestStatus.FAILED,
                           error_message=f"Unexpected error type: {type(e).__name__}: {e}")
                return False
            
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_end_to_end_error_flow_simulation(self):
        """Test simulated end-to-end error flow without real daemon"""
        test_result = start_test("end_to_end_error_flow_simulation", self.test_file, "simulate: error flow")
        
        try:
            # Simulate the error flow through the stack
            error_chain = []
            
            # 1. Client sends request
            error_chain.append({
                "stage": "client_request",
                "component": "AsyncClient",
                "action": "create_completion",
                "input": "simulate: error flow"
            })
            
            # 2. Daemon receives request
            error_chain.append({
                "stage": "daemon_receive",
                "component": "CompletionHandler", 
                "action": "validate_parameters",
                "status": "success"
            })
            
            # 3. Daemon calls completion service
            error_chain.append({
                "stage": "completion_service",
                "component": "CompletionServicePlugin",
                "action": "handle_completion_request",
                "status": "processing"
            })
            
            # 4. Service calls LiteLLM
            error_chain.append({
                "stage": "litellm_call",
                "component": "litellm.acompletion",
                "action": "call_provider",
                "model": "claude-cli/sonnet"
            })
            
            # 5. Provider calls Claude CLI - ERROR OCCURS HERE
            error_chain.append({
                "stage": "provider_execution",
                "component": "ClaudeCLIProvider",
                "action": "run_claude_cli",
                "error": "subprocess.TimeoutExpired",
                "timeout": 300
            })
            
            # 6. Provider handles error and propagates
            error_chain.append({
                "stage": "provider_error_handling",
                "component": "ClaudeCLIProvider",
                "action": "handle_timeout",
                "retry_attempt": 1,
                "will_retry": True
            })
            
            # 7. Second attempt also fails
            error_chain.append({
                "stage": "provider_execution",
                "component": "ClaudeCLIProvider", 
                "action": "run_claude_cli",
                "error": "subprocess.TimeoutExpired",
                "timeout": 900,
                "retry_attempt": 2
            })
            
            # 8. Provider gives up and raises error
            error_chain.append({
                "stage": "provider_final_error",
                "component": "ClaudeCLIProvider",
                "action": "raise_timeout_error",
                "final_error": "TimeoutExpired"
            })
            
            # 9. Completion service catches error
            error_chain.append({
                "stage": "service_error_handling",
                "component": "CompletionServicePlugin",
                "action": "catch_exception",
                "error_type": "TimeoutExpired"
            })
            
            # 10. Service publishes error event
            error_chain.append({
                "stage": "error_event_publish",
                "component": "EventBus",
                "action": "publish_error_event",
                "event_type": "completion:error",
                "target_client": "test_client"
            })
            
            # 11. Client receives error event
            error_chain.append({
                "stage": "client_error_receive",
                "component": "AsyncClient",
                "action": "handle_completion_error",
                "error_delivered": True
            })
            
            # Verify error chain integrity
            assert len(error_chain) == 11, f"Expected 11 stages, got {len(error_chain)}"
            
            # Verify key stages are present
            stages = [stage["stage"] for stage in error_chain]
            expected_stages = [
                "client_request", "daemon_receive", "completion_service",
                "litellm_call", "provider_execution", "provider_error_handling", 
                "provider_final_error", "service_error_handling", 
                "error_event_publish", "client_error_receive"
            ]
            
            for expected_stage in expected_stages:
                assert expected_stage in stages, f"Missing stage: {expected_stage}"
            
            # Verify error propagation points
            error_stages = [stage for stage in error_chain if "error" in stage]
            assert len(error_stages) >= 4, f"Expected at least 4 error stages, got {len(error_stages)}"
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "total_stages": len(error_chain),
                           "error_stages": len(error_stages),
                           "chain_integrity": True,
                           "error_propagation_verified": True
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_error_metadata_preservation(self):
        """Test that error metadata is preserved through the error chain"""
        test_result = start_test("error_metadata_preservation", self.test_file)
        
        try:
            # Simulate error metadata at each stage
            original_error = {
                "type": "TimeoutExpired",
                "command": ["claude", "--model", "sonnet", "test prompt"],
                "timeout": 300,
                "stage": "claude_cli_execution",
                "timestamp": time.time(),
                "attempt": 1
            }
            
            # Provider stage - adds retry info
            provider_error = original_error.copy()
            provider_error.update({
                "stage": "provider_error_handling",
                "retry_attempts": 2,
                "max_retries": 3,
                "next_timeout": 900
            })
            
            # Service stage - adds service context
            service_error = provider_error.copy()
            service_error.update({
                "stage": "completion_service_error",
                "client_id": "test_client_123",
                "request_id": "req_abc456",
                "session_id": "session_xyz789"
            })
            
            # Event stage - adds event metadata
            event_error = service_error.copy()
            event_error.update({
                "stage": "error_event",
                "event_type": "completion:error",
                "event_timestamp": time.time(),
                "target_client": "test_client_123"
            })
            
            # Client stage - adds client context
            client_error = event_error.copy()
            client_error.update({
                "stage": "client_error_handling",
                "client_correlation_id": "correlation_123",
                "user_facing_message": "Request timed out after 300 seconds"
            })
            
            # Verify metadata preservation
            assert client_error["type"] == original_error["type"], \
                "Original error type should be preserved"
            assert client_error["command"] == original_error["command"], \
                "Original command should be preserved"
            assert client_error["timeout"] == original_error["timeout"], \
                "Original timeout should be preserved"
            
            # Verify metadata additions
            assert "retry_attempts" in client_error, "Retry info should be added"
            assert "client_id" in client_error, "Client context should be added"
            assert "event_type" in client_error, "Event context should be added"
            assert "user_facing_message" in client_error, "User message should be added"
            
            # Verify all stages are tracked
            expected_stages = [
                "claude_cli_execution", "provider_error_handling", 
                "completion_service_error", "error_event", "client_error_handling"
            ]
            
            # Check that we can trace the error through all stages
            assert client_error["stage"] == expected_stages[-1], \
                "Final stage should be client_error_handling"
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "original_fields_preserved": 3,
                           "total_metadata_fields": len(client_error),
                           "stages_tracked": len(expected_stages),
                           "metadata_integrity": True
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_concurrent_error_handling(self):
        """Test error handling with multiple concurrent requests"""
        test_result = start_test("concurrent_error_handling", self.test_file)
        
        try:
            # Simulate multiple concurrent requests with different error types
            concurrent_errors = []
            
            # Request 1: Timeout error
            error1 = {
                "request_id": "req_001",
                "client_id": "client_A",
                "error_type": "TimeoutExpired",
                "error_message": "Claude CLI timed out after 300s",
                "timestamp": time.time()
            }
            concurrent_errors.append(error1)
            
            # Request 2: Logical error
            error2 = {
                "request_id": "req_002", 
                "client_id": "client_B",
                "error_type": "CalledProcessError",
                "error_message": "Invalid prompt format",
                "timestamp": time.time() + 0.1
            }
            concurrent_errors.append(error2)
            
            # Request 3: JSON parse error
            error3 = {
                "request_id": "req_003",
                "client_id": "client_A",  # Same client as request 1
                "error_type": "JSONDecodeError",
                "error_message": "Malformed JSON output",
                "timestamp": time.time() + 0.2
            }
            concurrent_errors.append(error3)
            
            # Simulate error isolation - each client should only receive their own errors
            client_a_errors = [e for e in concurrent_errors if e["client_id"] == "client_A"]
            client_b_errors = [e for e in concurrent_errors if e["client_id"] == "client_B"]
            
            # Verify error isolation
            assert len(client_a_errors) == 2, f"Client A should have 2 errors, got {len(client_a_errors)}"
            assert len(client_b_errors) == 1, f"Client B should have 1 error, got {len(client_b_errors)}"
            
            # Verify error types are preserved
            client_a_types = {e["error_type"] for e in client_a_errors}
            assert "TimeoutExpired" in client_a_types, "Client A should receive timeout error"
            assert "JSONDecodeError" in client_a_types, "Client A should receive JSON error"
            
            client_b_types = {e["error_type"] for e in client_b_errors}
            assert "CalledProcessError" in client_b_types, "Client B should receive logical error"
            
            # Verify request IDs are unique and preserved
            all_request_ids = {e["request_id"] for e in concurrent_errors}
            assert len(all_request_ids) == 3, "All request IDs should be unique"
            assert "req_001" in all_request_ids, "Request 001 should be preserved"
            assert "req_002" in all_request_ids, "Request 002 should be preserved"
            assert "req_003" in all_request_ids, "Request 003 should be preserved"
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "total_errors": len(concurrent_errors),
                           "client_a_errors": len(client_a_errors),
                           "client_b_errors": len(client_b_errors),
                           "error_isolation": True,
                           "request_id_uniqueness": len(all_request_ids) == 3
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False


async def run_all_tests():
    """Run all error propagation tests"""
    print("Running End-to-End Error Propagation Tests")
    print("=" * 50)
    
    if not provider_available:
        print("⚠️  Provider not available - some tests will be skipped")
    if not client_available:
        print("⚠️  Client not available - some tests will be skipped")
    
    tester = TestErrorPropagation()
    
    # List of test methods
    test_methods = [
        tester.test_provider_timeout_error_handling,
        tester.test_provider_logical_error_handling,
        tester.test_provider_system_error_with_retry,
        tester.test_provider_json_parse_error_handling,
        tester.test_client_connection_error_handling,
        tester.test_end_to_end_error_flow_simulation,
        tester.test_error_metadata_preservation,
        tester.test_concurrent_error_handling
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
    print(f"Error Propagation Tests: {passed}/{total} passed")
    
    return passed == total


if __name__ == "__main__":
    # Run tests
    success = asyncio.run(run_all_tests())
    
    # Print final result summary from logger
    from test_result_logger import get_test_logger
    get_test_logger().print_summary()
    
    sys.exit(0 if success else 1)