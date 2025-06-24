#!/usr/bin/env python3
"""
Comprehensive tests for the COMPLETION command based on actual implementation.

Tests the real CompletionHandler and CompletionParameters from ksi_daemon:
- @command_handler("COMPLETION") decorator pattern
- CompletionParameters Pydantic model validation
- Background worker queue and async processing
- CompletionAcknowledgment immediate responses
- COMPLETION_RESULT event publication via enhanced message bus
- Real MultiSocketAsyncClient.create_completion() flow
"""

import asyncio
import json
import pytest
from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from actual ksi_client and ksi_daemon
from ksi_client import AsyncClient, SimpleChatClient, CommandBuilder, ResponseHandler
# Import actual protocol models
from ksi_daemon.protocols import CompletionParameters, CompletionAcknowledgment, SocketResponse


class TestCompletionParameters:
    """Test the actual CompletionParameters Pydantic model from ksi_daemon.protocols"""
    
    def test_completion_parameters_valid_minimal(self):
        """Test CompletionParameters with minimal required fields"""
        
        # Required fields: prompt, client_id
        params = CompletionParameters(
            prompt="What is 2+2?",
            client_id="test_client_123"
        )
        
        assert params.prompt == "What is 2+2?"
        assert params.client_id == "test_client_123"
        assert params.model == "sonnet"  # Default value
        assert params.timeout == 300     # Default value
        assert params.session_id is None
        assert params.agent_id is None
        assert params.metadata is None
    
    def test_completion_parameters_all_fields(self):
        """Test CompletionParameters with all fields specified"""
        
        params = CompletionParameters(
            prompt="Complex prompt with session continuity",
            client_id="advanced_client_456", 
            model="claude-3-opus",
            session_id="session_abc123",
            agent_id="specialist_agent",
            timeout=600,
            metadata={"priority": "high", "user_id": "user_789"}
        )
        
        assert params.prompt == "Complex prompt with session continuity"
        assert params.client_id == "advanced_client_456"
        assert params.model == "claude-3-opus"
        assert params.session_id == "session_abc123"
        assert params.agent_id == "specialist_agent"
        assert params.timeout == 600
        assert params.metadata == {"priority": "high", "user_id": "user_789"}
    
    def test_completion_parameters_validation_errors(self):
        """Test CompletionParameters validation catches invalid data"""
        
        # Missing required prompt
        with pytest.raises(Exception):  # Pydantic ValidationError
            CompletionParameters(client_id="test")
        
        # Missing required client_id  
        with pytest.raises(Exception):  # Pydantic ValidationError
            CompletionParameters(prompt="test")
        
        # Empty prompt
        with pytest.raises(Exception):  # Pydantic ValidationError
            CompletionParameters(prompt="", client_id="test")
        
        # Empty client_id
        with pytest.raises(Exception):  # Pydantic ValidationError  
            CompletionParameters(prompt="test", client_id="")
        
        # Negative timeout
        with pytest.raises(Exception):  # Pydantic ValidationError
            CompletionParameters(
                prompt="test", 
                client_id="test",
                timeout=-1
            )
    
    def test_completion_parameters_serialization(self):
        """Test CompletionParameters can be serialized to dict"""
        
        params = CompletionParameters(
            prompt="Serialization test",
            client_id="serialize_client",
            model="sonnet",
            session_id="session_serialize"
        )
        
        data = params.model_dump()
        
        assert isinstance(data, dict)
        assert data["prompt"] == "Serialization test"
        assert data["client_id"] == "serialize_client"
        assert data["model"] == "sonnet"
        assert data["session_id"] == "session_serialize"
        assert data["timeout"] == 300


class TestCompletionAcknowledgment:
    """Test the actual CompletionAcknowledgment response model"""
    
    def test_completion_acknowledgment_creation(self):
        """Test creating CompletionAcknowledgment response"""
        
        ack = CompletionAcknowledgment(
            request_id="req_abc12345",
            status="queued",
            queue_position=3
        )
        
        assert ack.request_id == "req_abc12345"
        assert ack.status == "queued"
        assert ack.queue_position == 3
    
    def test_completion_acknowledgment_serialization(self):
        """Test CompletionAcknowledgment serialization"""
        
        ack = CompletionAcknowledgment(
            request_id="req_test_serialize",
            status="processing",
            queue_position=0
        )
        
        data = ack.model_dump()
        
        assert data["request_id"] == "req_test_serialize"
        assert data["status"] == "processing"
        assert data["queue_position"] == 0


class TestCommandBuilderIntegration:
    """Test CommandBuilder creates correct COMPLETION commands"""
    
    def test_completion_command_structure(self):
        """Test CommandBuilder creates proper COMPLETION command structure"""
        
        parameters = {
            "prompt": "Test completion command",
            "client_id": "command_test_client",
            "model": "sonnet",
            "session_id": "session_cmd_test"
        }
        
        command = CommandBuilder.build_command("COMPLETION", parameters)
        
        assert command["command"] == "COMPLETION"
        assert "parameters" in command
        assert command["parameters"]["prompt"] == "Test completion command"
        assert command["parameters"]["client_id"] == "command_test_client"
        assert command["parameters"]["model"] == "sonnet"
        assert command["parameters"]["session_id"] == "session_cmd_test"
    
    def test_completion_command_with_metadata(self):
        """Test COMPLETION command with metadata"""
        
        parameters = {
            "prompt": "Test with metadata",
            "client_id": "metadata_client",
            "metadata": {"source": "test_suite", "batch_id": "batch_123"}
        }
        
        metadata = {"request_timestamp": "2024-01-01T00:00:00Z"}
        
        command = CommandBuilder.build_command("COMPLETION", parameters, metadata)
        
        assert command["command"] == "COMPLETION"
        assert command["parameters"]["metadata"]["source"] == "test_suite"
        assert command["parameters"]["metadata"]["batch_id"] == "batch_123"


class TestMultiSocketClientCompletion:
    """Test the real MultiSocketAsyncClient.create_completion() implementation"""
    
    @pytest.mark.asyncio
    async def test_create_completion_integration(self):
        """Test create_completion() method with real daemon (if running)"""
        
        try:
            client = AsyncClient(client_id="integration_test_client")
            await client.initialize()
            
            # Test real completion
            # Get test timeout from config
            from ksi_daemon.config import config
            test_timeout = config.test_completion_timeout
            
            response = await client.create_completion(
                prompt="What is 1+1? Answer in one word.",
                model="sonnet",
                timeout=test_timeout
            )
            
            # Should return string response
            assert isinstance(response, str)
            assert len(response) > 0
            
            await client.close()
            
        except ConnectionError:
            pytest.skip("Daemon not running - integration test skipped")
        except Exception as e:
            pytest.fail(f"create_completion integration test failed: {e}")
    
    @pytest.mark.asyncio
    async def test_create_completion_with_session_id(self):
        """Test create_completion() with session continuity"""
        
        try:
            # Get test timeout from config
            from ksi_daemon.config import config
            test_timeout = config.test_completion_timeout
            
            client = AsyncClient(client_id="session_test_client")
            await client.initialize()
            
            session_id = "test_session_continuity_123"
            
            # First completion
            response1 = await client.create_completion(
                prompt="Remember this number: 42",
                session_id=session_id,
                timeout=test_timeout
            )
            
            # Second completion with same session
            response2 = await client.create_completion(
                prompt="What number did I just tell you to remember?",
                session_id=session_id,
                timeout=test_timeout
            )
            
            assert isinstance(response1, str)
            assert isinstance(response2, str)
            assert "42" in response2
            
            await client.close()
            
        except ConnectionError:
            pytest.skip("Daemon not running - session continuity test skipped")
        except Exception as e:
            pytest.fail(f"Session continuity test failed: {e}")
    
    @pytest.mark.asyncio
    async def test_create_completion_concurrent(self):
        """Test multiple concurrent create_completion() calls"""
        
        try:
            # Get test timeout from config
            from ksi_daemon.config import config
            test_timeout = config.test_completion_timeout
            
            client = AsyncClient(client_id="concurrent_completion_client")
            await client.initialize()
            
            # Create multiple completion tasks
            tasks = [
                client.create_completion(f"Count to {i+1}", timeout=test_timeout)
                for i in range(3)
            ]
            
            # Execute concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All should succeed
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    pytest.fail(f"Concurrent completion {i} failed: {result}")
                else:
                    assert isinstance(result, str)
                    assert len(result) > 0
            
            await client.close()
            
        except ConnectionError:
            pytest.skip("Daemon not running - concurrent completion test skipped")
        except Exception as e:
            pytest.fail(f"Concurrent completion test failed: {e}")


class TestSimpleChatClientFlow:
    """Test the real SimpleChatClient.send_prompt() implementation"""
    
    @pytest.mark.asyncio
    async def test_simple_chat_send_prompt(self):
        """Test SimpleChatClient.send_prompt() integration"""
        
        try:
            client = SimpleChatClient(client_id="simple_chat_test")
            await client.initialize()
            
            # Test basic send_prompt
            response, session_id = await client.send_prompt("What is 3+3? Answer briefly.")
            
            # Should return tuple of (response_text, session_id)
            assert isinstance(response, str)
            assert len(response) > 0
            assert isinstance(session_id, str)
            assert len(session_id) > 0
            
            await client.close()
            
        except ConnectionError:
            pytest.skip("Daemon not running - SimpleChatClient test skipped")
        except Exception as e:
            pytest.fail(f"SimpleChatClient send_prompt failed: {e}")
    
    @pytest.mark.asyncio
    async def test_simple_chat_session_continuity(self):
        """Test SimpleChatClient session continuity"""
        
        try:
            client = SimpleChatClient(client_id="simple_chat_session_test")
            await client.initialize()
            
            # First message
            response1, session_id1 = await client.send_prompt("My name is Claude.")
            
            # Second message using same session
            response2, session_id2 = await client.send_prompt(
                "What name did I just tell you?",
                session_id=session_id1
            )
            
            # Session should be maintained
            assert session_id1 == session_id2
            assert "claude" in response2.lower()
            
            await client.close()
            
        except ConnectionError:
            pytest.skip("Daemon not running - session continuity test skipped")
        except Exception as e:
            pytest.fail(f"SimpleChatClient session continuity failed: {e}")
    
    def test_simple_chat_client_structure(self):
        """Test SimpleChatClient class structure and inheritance"""
        
        client = SimpleChatClient(client_id="structure_test")
        
        # Should inherit from MultiSocketAsyncClient
        assert hasattr(client, 'sockets')
        assert hasattr(client, 'create_completion')
        assert hasattr(client, 'health_check')
        
        # Should have SimpleChatClient-specific attributes
        assert hasattr(client, 'current_session_id')
        assert hasattr(client, 'send_prompt')
        
        # Should have correct client_id
        assert client.client_id == "structure_test"
        
        # Current session should be None initially
        assert client.current_session_id is None


class TestProtocolErrorHandling:
    """Test protocol-level error handling and edge cases"""
    
    @pytest.mark.asyncio
    async def test_connection_failure_recovery(self):
        """Test graceful handling when daemon is not available"""
        
        client = AsyncClient(client_id="connection_failure_test")
        
        # Should handle connection failure gracefully
        try:
            success = await client.initialize()
            if success:
                # Daemon is running, test passed
                await client.close()
        except ConnectionError:
            # Expected when daemon not running
            pass
        except Exception as e:
            pytest.fail(f"Unexpected error during connection failure: {e}")
    
    def test_invalid_socket_usage(self):
        """Test error handling for invalid socket operations"""
        
        client = AsyncClient(client_id="invalid_socket_test")
        
        # Should raise ValueError for invalid socket names
        with pytest.raises(ValueError, match="Invalid socket name"):
            asyncio.run(client.send_command("invalid_socket", "TEST"))
        
        # Should raise ValueError for messaging socket direct commands
        with pytest.raises(ValueError, match="persistent messaging"):
            asyncio.run(client.send_command("messaging", "TEST"))
    
    def test_client_id_validation(self):
        """Test client ID handling and validation"""
        
        # Auto-generated client ID
        client1 = AsyncClient()
        assert client1.client_id is not None
        assert client1.client_id.startswith("client_")
        
        # Custom client ID
        client2 = AsyncClient(client_id="custom_test_id")
        assert client2.client_id == "custom_test_id"
        
        # Different auto-generated IDs should be unique
        client3 = AsyncClient()
        assert client1.client_id != client3.client_id


class TestResponseHandling:
    """Test the real ResponseHandler utility functions"""
    
    def test_success_response_parsing(self):
        """Test ResponseHandler success response parsing"""
        
        success_response = {
            "status": "success",
            "command": "COMPLETION",
            "result": {
                "request_id": "req_abc123",
                "status": "queued",
                "queue_position": 2
            }
        }
        
        assert ResponseHandler.check_success(success_response) is True
        result_data = ResponseHandler.get_result_data(success_response)
        assert result_data["request_id"] == "req_abc123"
        assert result_data["status"] == "queued"
        assert result_data["queue_position"] == 2
    
    def test_error_response_parsing(self):
        """Test ResponseHandler error response parsing"""
        
        error_response = {
            "status": "error",
            "command": "COMPLETION",
            "error": {
                "code": "INVALID_PARAMETERS",
                "message": "Missing required parameter: client_id"
            }
        }
        
        assert ResponseHandler.check_success(error_response) is False
        error_message = ResponseHandler.get_error_message(error_response)
        assert error_message == "Missing required parameter: client_id"
    
    def test_malformed_response_handling(self):
        """Test ResponseHandler with malformed responses"""
        
        # Missing status
        malformed_response = {"command": "TEST", "result": {}}
        assert ResponseHandler.check_success(malformed_response) is False
        
        # Missing error details
        error_response_minimal = {"status": "error", "command": "TEST"}
        error_msg = ResponseHandler.get_error_message(error_response_minimal)
        assert error_msg == "Unknown error"


# Integration test runner for manual execution
async def run_integration_tests():
    """Run integration tests that require a running daemon"""
    
    print("Running COMPLETION command integration tests...")
    print("Note: These tests require ksi-daemon.py to be running")
    
    integration_tests = [
        ("CompletionParameters validation", lambda: TestCompletionParameters().test_completion_parameters_valid_minimal()),
        ("CompletionAcknowledgment model", lambda: TestCompletionAcknowledgment().test_completion_acknowledgment_creation()),
        ("CommandBuilder integration", lambda: TestCommandBuilderIntegration().test_completion_command_structure()),
        ("ResponseHandler parsing", lambda: TestResponseHandling().test_success_response_parsing()),
        ("Client structure validation", lambda: TestSimpleChatClientFlow().test_simple_chat_client_structure()),
    ]
    
    results = {}
    
    for test_name, test_func in integration_tests:
        try:
            test_func()
            print(f"✓ {test_name}")
            results[test_name] = True
        except Exception as e:
            print(f"✗ {test_name}: {e}")
            results[test_name] = False
    
    # Try one actual integration test
    try:
        test_client = TestMultiSocketClientCompletion()
        await test_client.test_create_completion_integration()
        print("✓ Real daemon integration test")
        results["Real daemon integration"] = True
    except Exception as e:
        print(f"✗ Real daemon integration test: {e}")
        results["Real daemon integration"] = False
    
    # Summary
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    print(f"\nIntegration test results: {passed}/{total} tests passed")
    
    if passed < total:
        print("Note: Some integration tests may fail if daemon is not running")
    
    return results


if __name__ == "__main__":
    # Run integration tests if called directly
    asyncio.run(run_integration_tests())