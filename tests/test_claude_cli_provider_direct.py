#!/usr/bin/env python3
"""
Direct tests for claude_cli_litellm_provider.py

Tests the LiteLLM provider functionality without actually spawning Claude CLI processes.
Uses mocking to simulate subprocess calls and verify provider behavior.

Key testing areas:
- Provider registration with LiteLLM
- Progressive timeout logic (5min → 15min → 30min) 
- Intelligent retry on different error types
- Metadata preservation (sessionId, stderr, Claude response format)
- Tool integration (allowedTools/disallowedTools parameter passing)
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import test result logger
from test_result_logger import TestStatus, start_test, finish_test, skip_test

# Import the provider (this registers it with LiteLLM)
import claude_cli_litellm_provider
import litellm


class TestClaudeCLIProviderDirect:
    """Direct tests for ClaudeCLIProvider functionality"""
    
    def __init__(self):
        self.test_file = "test_claude_cli_provider_direct.py"
        
    def test_provider_registration(self):
        """Test that the provider is properly registered with LiteLLM"""
        test_result = start_test("provider_registration", self.test_file)
        
        try:
            # Check that claude-cli provider is in the custom provider map
            claude_providers = [
                provider for provider in litellm.custom_provider_map 
                if provider.get("provider") == "claude-cli"
            ]
            
            assert len(claude_providers) > 0, "claude-cli provider not found in custom_provider_map"
            
            provider_entry = claude_providers[0]
            assert "custom_handler" in provider_entry, "Provider missing custom_handler"
            
            handler = provider_entry["custom_handler"]
            assert isinstance(handler, claude_cli_litellm_provider.ClaudeCLIProvider), \
                f"Handler is not ClaudeCLIProvider instance: {type(handler)}"
            
            finish_test(test_result, TestStatus.PASSED, 
                       details={"provider_count": len(claude_providers)})
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_command_building(self):
        """Test that commands are built correctly with various parameters"""
        test_result = start_test("command_building", self.test_file)
        
        try:
            # Test basic command
            cmd = claude_cli_litellm_provider.build_cmd(
                "quick: what's 2+2?",
                output_format="json",
                model_alias="sonnet"
            )
            
            expected_basic = ["claude", "-p", "--output-format", "json", "--model", "sonnet", "quick: what's 2+2?"]
            assert cmd == expected_basic, f"Basic command mismatch: {cmd} vs {expected_basic}"
            
            # Test command with tools
            cmd_with_tools = claude_cli_litellm_provider.build_cmd(
                "quick: name one color",
                output_format="json", 
                model_alias="sonnet",
                allowed_tools=["Bash", "Read"],
                disallowed_tools=["Write"]
            )
            
            assert "--allowedTools" in cmd_with_tools
            assert "Bash" in cmd_with_tools
            assert "Read" in cmd_with_tools
            assert "--disallowedTools" in cmd_with_tools
            assert "Write" in cmd_with_tools
            
            # Test command with session resumption
            cmd_with_session = claude_cli_litellm_provider.build_cmd(
                "continue conversation",
                output_format="json",
                model_alias="sonnet", 
                session_id="session_123"
            )
            
            assert "--resume" in cmd_with_session
            assert "session_123" in cmd_with_session
            
            # Test command with max turns
            cmd_with_turns = claude_cli_litellm_provider.build_cmd(
                "quick chat",
                output_format="json",
                model_alias="sonnet",
                max_turns=3
            )
            
            assert "--max-turns" in cmd_with_turns
            assert "3" in cmd_with_turns
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "basic_cmd_len": len(expected_basic),
                           "tools_cmd_len": len(cmd_with_tools),
                           "session_cmd_len": len(cmd_with_session),
                           "turns_cmd_len": len(cmd_with_turns)
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_openai_tools_conversion(self):
        """Test conversion of OpenAI tools format to CLI allowedTools"""
        test_result = start_test("openai_tools_conversion", self.test_file)
        
        try:
            # Test with standard OpenAI tools format
            openai_tools = [
                {"type": "function", "function": {"name": "Bash"}},
                {"type": "function", "function": {"name": "Read"}},
                {"type": "function", "function": {"name": "Edit"}},
                {"type": "invalid", "function": {"name": "ShouldBeIgnored"}},  # Invalid type
                {"type": "function", "function": {}},  # Missing name
            ]
            
            allowed_tools = claude_cli_litellm_provider.allowed_tools_from_openai(openai_tools)
            
            expected_tools = ["Bash", "Read", "Edit"]
            assert allowed_tools == expected_tools, f"Tools conversion failed: {allowed_tools} vs {expected_tools}"
            
            # Test with empty tools
            empty_tools = claude_cli_litellm_provider.allowed_tools_from_openai([])
            assert empty_tools == [], f"Empty tools should return empty list: {empty_tools}"
            
            # Test with None tools
            none_tools = claude_cli_litellm_provider.allowed_tools_from_openai(None)
            assert none_tools == [], f"None tools should return empty list: {none_tools}"
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "extracted_tools": allowed_tools,
                           "original_count": len(openai_tools),
                           "extracted_count": len(allowed_tools)
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_json_output_parsing(self):
        """Test parsing of Claude CLI JSON output"""
        test_result = start_test("json_output_parsing", self.test_file)
        
        try:
            # Test valid Claude JSON response
            claude_response = json.dumps({
                "type": "assistant",
                "message": {
                    "content": [
                        {"text": "The answer is "},
                        {"text": "4"},
                        {"text": "."}
                    ]
                },
                "sessionId": "session_abc123"
            })
            
            parsed_text = claude_cli_litellm_provider.parse_json_output(claude_response)
            expected_text = "The answer is 4."
            assert parsed_text == expected_text, f"Parsed text mismatch: '{parsed_text}' vs '{expected_text}'"
            
            # Test invalid JSON (should return raw string)
            invalid_json = "This is not JSON"
            parsed_invalid = claude_cli_litellm_provider.parse_json_output(invalid_json)
            assert parsed_invalid == invalid_json, f"Invalid JSON should return raw: '{parsed_invalid}'"
            
            # Test malformed Claude response (should return raw string)
            malformed_claude = json.dumps({"type": "unknown", "data": "something"})
            parsed_malformed = claude_cli_litellm_provider.parse_json_output(malformed_claude)
            assert parsed_malformed == malformed_claude, f"Malformed should return raw: '{parsed_malformed}'"
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "valid_parse_length": len(parsed_text),
                           "invalid_parse_length": len(parsed_invalid),
                           "malformed_parse_length": len(parsed_malformed)
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    @patch('subprocess.Popen')
    def test_successful_completion(self, mock_popen):
        """Test successful completion flow with mocked subprocess"""
        test_result = start_test("successful_completion", self.test_file, "quick: 1+1?")
        
        try:
            # Setup mock successful response
            claude_response = {
                "type": "assistant",
                "message": {"content": [{"text": "2"}]},
                "sessionId": "test_session_123"
            }
            
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.poll.return_value = 0
            mock_process.stdout = MagicMock()
            mock_process.stderr = MagicMock()
            mock_popen.return_value = mock_process
            
            # Mock the _run_claude_sync_with_progress to return successful result
            provider = claude_cli_litellm_provider.ClaudeCLIProvider()
            
            # Create mock result
            class MockResult:
                def __init__(self):
                    self.returncode = 0
                    self.stdout = json.dumps(claude_response)
                    self.stderr = ""
                    self.args = ["claude", "-p", "--output-format", "json", "--model", "sonnet", "quick: 1+1?"]
            
            with patch.object(provider, '_run_claude_sync_with_progress', return_value=MockResult()):
                # Test the completion
                messages = [{"role": "user", "content": "quick: 1+1?"}]
                response = provider.completion(messages)
                
                # Verify response structure
                assert hasattr(response, 'choices'), "Response missing choices"
                assert len(response.choices) > 0, "Response has no choices"
                assert hasattr(response.choices[0], 'message'), "Choice missing message"
                assert hasattr(response.choices[0].message, 'content'), "Message missing content"
                
                # Verify Claude metadata is preserved
                assert hasattr(response, '_claude_metadata'), "Response missing Claude metadata"
                assert response._claude_metadata == claude_response, "Claude metadata not preserved correctly"
                
                # Verify session ID is preserved
                assert hasattr(response, 'sessionId'), "Response missing sessionId"
                assert response.sessionId == "test_session_123", "Session ID not preserved"
                
                # Verify response content
                content = response.choices[0].message.content
                assert "2" in content, f"Expected '2' in response content: {content}"
                
            finish_test(test_result, TestStatus.PASSED, response="2",
                       details={
                           "session_id": "test_session_123",
                           "has_metadata": hasattr(response, '_claude_metadata'),
                           "content_length": len(content)
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    @patch('subprocess.Popen')
    def test_timeout_and_retry_logic(self, mock_popen):
        """Test progressive timeout and intelligent retry logic"""
        test_result = start_test("timeout_retry_logic", self.test_file, "quick: test timeout")
        
        try:
            provider = claude_cli_litellm_provider.ClaudeCLIProvider()
            
            # Mock timeout on first two attempts, success on third
            timeout_call_count = 0
            
            def mock_run_with_timeout(*args, **kwargs):
                nonlocal timeout_call_count
                timeout_call_count += 1
                
                if timeout_call_count <= 2:
                    # First two attempts timeout
                    raise subprocess.TimeoutExpired(["claude"], 300)
                else:
                    # Third attempt succeeds
                    class MockResult:
                        def __init__(self):
                            self.returncode = 0
                            self.stdout = json.dumps({
                                "type": "assistant",
                                "message": {"content": [{"text": "success after retry"}]}
                            })
                            self.stderr = ""
                    return MockResult()
            
            with patch.object(provider, '_run_claude_sync_with_progress', side_effect=mock_run_with_timeout):
                # This should succeed after 2 timeouts + 1 success
                messages = [{"role": "user", "content": "quick: test timeout"}]
                
                # Mock the config timeouts to be shorter for testing
                with patch('claude_cli_litellm_provider.config') as mock_config:
                    mock_config.claude_timeout_attempts = [1, 2, 3]  # Very short for testing
                    
                    # Patch asyncio.sleep to avoid actual delays
                    with patch('asyncio.sleep'):
                        response = provider.completion(messages)
                
                # Verify we got a response after retries
                assert hasattr(response, 'choices'), "Response missing choices after retry"
                content = response.choices[0].message.content
                assert "success after retry" in content, f"Unexpected content after retry: {content}"
                
                # Verify we made 3 attempts (2 timeouts + 1 success)
                assert timeout_call_count == 3, f"Expected 3 attempts, got {timeout_call_count}"
            
            finish_test(test_result, TestStatus.PASSED, response="success after retry",
                       details={
                           "attempts_made": timeout_call_count,
                           "final_success": True
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    @patch('subprocess.Popen')
    def test_error_handling_by_type(self, mock_popen):
        """Test different types of errors are handled appropriately"""
        test_result = start_test("error_handling_by_type", self.test_file)
        
        try:
            provider = claude_cli_litellm_provider.ClaudeCLIProvider()
            
            # Test 1: Logical error (shouldn't retry)
            def mock_logical_error(*args, **kwargs):
                raise subprocess.CalledProcessError(1, ["claude"], "Error: Invalid prompt", "Claude error")
            
            with patch.object(provider, '_run_claude_sync_with_progress', side_effect=mock_logical_error):
                try:
                    messages = [{"role": "user", "content": "invalid prompt"}]
                    provider.completion(messages)
                    assert False, "Should have raised CalledProcessError for logical error"
                except subprocess.CalledProcessError as e:
                    assert e.returncode == 1, f"Expected returncode 1, got {e.returncode}"
            
            # Test 2: System error (should retry)
            retry_count = 0
            def mock_system_error(*args, **kwargs):
                nonlocal retry_count
                retry_count += 1
                if retry_count <= 2:
                    # System kill signal (should retry)
                    raise subprocess.CalledProcessError(-9, ["claude"], "", "")
                else:
                    # Eventually succeed
                    class MockResult:
                        def __init__(self):
                            self.returncode = 0
                            self.stdout = json.dumps({
                                "type": "assistant", 
                                "message": {"content": [{"text": "recovered"}]}
                            })
                            self.stderr = ""
                    return MockResult()
            
            with patch.object(provider, '_run_claude_sync_with_progress', side_effect=mock_system_error):
                with patch('claude_cli_litellm_provider.config') as mock_config:
                    mock_config.claude_timeout_attempts = [1, 2, 3]
                    with patch('asyncio.sleep'):
                        messages = [{"role": "user", "content": "test system error"}]
                        response = provider.completion(messages)
                        
                        content = response.choices[0].message.content
                        assert "recovered" in content, f"Expected recovery after system error: {content}"
                        assert retry_count == 3, f"Expected 3 attempts for system error, got {retry_count}"
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "logical_error_handled": True,
                           "system_error_retries": retry_count,
                           "system_error_recovered": True
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_metadata_preservation(self):
        """Test that Claude CLI metadata is properly preserved in LiteLLM response"""
        test_result = start_test("metadata_preservation", self.test_file)
        
        try:
            provider = claude_cli_litellm_provider.ClaudeCLIProvider()
            
            # Create comprehensive Claude response with all metadata fields
            claude_response = {
                "type": "assistant",
                "message": {
                    "content": [{"text": "Test response"}],
                    "role": "assistant"
                },
                "sessionId": "preservation_test_123",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5
                },
                "stop_reason": "end_turn",
                "custom_field": "should_be_preserved"
            }
            
            # Mock successful result
            class MockResult:
                def __init__(self):
                    self.returncode = 0
                    self.stdout = json.dumps(claude_response)
                    self.stderr = "debug info from claude"
                    self.args = ["claude", "test"]
            
            mock_result = MockResult()
            
            # Test _process_claude_result directly
            response = provider._process_claude_result(mock_result, "sonnet", "test prompt")
            
            # Verify Claude metadata is attached
            assert hasattr(response, '_claude_metadata'), "Response missing _claude_metadata"
            assert response._claude_metadata == claude_response, "Claude metadata not preserved exactly"
            
            # Verify raw stdout is preserved
            assert hasattr(response, '_raw_stdout'), "Response missing _raw_stdout"
            assert response._raw_stdout == json.dumps(claude_response), "Raw stdout not preserved"
            
            # Verify stderr is preserved
            assert hasattr(response, '_stderr'), "Response missing _stderr"
            assert response._stderr == "debug info from claude", "Stderr not preserved"
            
            # Verify session ID is available at top level
            assert hasattr(response, 'sessionId'), "Response missing top-level sessionId"
            assert response.sessionId == "preservation_test_123", "Session ID not preserved at top level"
            
            # Verify custom fields are preserved in metadata
            assert response._claude_metadata.get('custom_field') == "should_be_preserved", \
                "Custom metadata field not preserved"
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "has_claude_metadata": True,
                           "has_raw_stdout": True,
                           "has_stderr": True,
                           "has_session_id": True,
                           "metadata_keys": list(response._claude_metadata.keys())
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_json_decode_error_handling(self):
        """Test handling of malformed JSON from Claude CLI"""
        test_result = start_test("json_decode_error_handling", self.test_file)
        
        try:
            provider = claude_cli_litellm_provider.ClaudeCLIProvider()
            
            # Create result with malformed JSON
            class MockResult:
                def __init__(self):
                    self.returncode = 0
                    self.stdout = "This is not valid JSON at all..."
                    self.stderr = "Warning: Output format may be corrupted"
                    self.args = ["claude", "test"]
            
            mock_result = MockResult()
            
            # Test _process_claude_result with malformed JSON
            response = provider._process_claude_result(mock_result, "sonnet", "test prompt")
            
            # Should still create a valid LiteLLM response
            assert hasattr(response, 'choices'), "Response missing choices even with JSON error"
            assert len(response.choices) > 0, "Response has no choices even with JSON error"
            
            # Should preserve raw output for debugging
            assert hasattr(response, '_raw_stdout'), "Response missing _raw_stdout for debugging"
            assert response._raw_stdout == "This is not valid JSON at all...", "Raw stdout not preserved for debugging"
            
            # Should preserve stderr for debugging
            assert hasattr(response, '_stderr'), "Response missing _stderr for debugging"
            assert response._stderr == "Warning: Output format may be corrupted", "Stderr not preserved for debugging"
            
            # Should include JSON decode error info
            assert hasattr(response, '_json_decode_error'), "Response missing _json_decode_error info"
            assert isinstance(response._json_decode_error, str), "JSON decode error should be string"
            
            # Content should be the raw text (fallback behavior)
            content = response.choices[0].message.content
            assert "This is not valid JSON at all..." in content, \
                f"Expected raw text in content, got: {content}"
            
            finish_test(test_result, TestStatus.PASSED, response=content[:50],
                       details={
                           "has_choices": True,
                           "has_error_info": True,
                           "fallback_content_length": len(content),
                           "error_message": response._json_decode_error
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False


async def run_all_tests():
    """Run all provider direct tests"""
    print("Running Claude CLI Provider Direct Tests")
    print("=" * 50)
    
    tester = TestClaudeCLIProviderDirect()
    
    # List of test methods
    test_methods = [
        tester.test_provider_registration,
        tester.test_command_building,
        tester.test_openai_tools_conversion,
        tester.test_json_output_parsing,
        tester.test_successful_completion,
        tester.test_timeout_and_retry_logic,
        tester.test_error_handling_by_type,
        tester.test_metadata_preservation,
        tester.test_json_decode_error_handling
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
    print(f"Provider Direct Tests: {passed}/{total} passed")
    
    return passed == total


if __name__ == "__main__":
    # Run tests
    success = asyncio.run(run_all_tests())
    
    # Print final result summary from logger
    from test_result_logger import get_test_logger
    get_test_logger().print_summary()
    
    sys.exit(0 if success else 1)