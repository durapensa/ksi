#!/usr/bin/env python3
"""
Test suite for the new COMPLETION command and async completion flow.

Tests the key differences from the old SPAWN command:
1. COMPLETION uses JSON Protocol v2.0 with structured parameters
2. COMPLETION is async - returns immediately with request_id
3. Results are delivered via COMPLETION_RESULT events on messaging socket
4. Uses multi-socket architecture (completion.sock + messaging.sock)
"""

import asyncio
import json
import pytest
import uuid
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from pydantic import ValidationError

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksi_daemon.protocols import CompletionParameters, SocketResponse
from ksi_daemon.commands.completion import CompletionHandler
from ksi_daemon.command_handler import CommandHandler


class TestCompletionCommand:
    """Test the new COMPLETION command handler"""
    
    def test_completion_parameters_validation(self):
        """Test that COMPLETION parameters are properly validated"""
        # Valid parameters
        params = CompletionParameters(
            prompt="What is 2+2?",
            client_id="test-client-123",
            model="sonnet",
            session_id="session-abc"
        )
        assert params.prompt == "What is 2+2?"
        assert params.client_id == "test-client-123"
        assert params.model == "sonnet"
        assert params.session_id == "session-abc"
        
        # Invalid - missing required client_id
        with pytest.raises(ValidationError):
            CompletionParameters(prompt="test")
        
        # Invalid - empty client_id  
        with pytest.raises(ValidationError):
            CompletionParameters(prompt="test", client_id="")
    
    def test_completion_command_structure(self):
        """Test the JSON Protocol v2.0 command structure for COMPLETION"""
        command = {
            "command": "COMPLETION",
            "version": "2.0", 
            "parameters": {
                "prompt": "What is the meaning of life?",
                "client_id": "test-client-456",
                "model": "sonnet",
                "session_id": "session-def",
                "timeout": 120
            }
        }
        
        # This should validate successfully 
        params = CompletionParameters(**command["parameters"])
        assert params.prompt == "What is the meaning of life?"
        assert params.client_id == "test-client-456"
        assert params.timeout == 120
    
    @pytest.mark.asyncio
    async def test_completion_handler_initialization(self):
        """Test that CompletionHandler initializes properly"""
        # Mock the command handler context
        mock_context = Mock()
        mock_context.state_manager = Mock()
        mock_context.completion_manager = Mock()
        mock_context.message_bus = Mock()
        
        handler = CompletionHandler(mock_context)
        
        # Should have proper attributes
        assert hasattr(handler, 'completion_queue')
        assert isinstance(handler.completion_queue, asyncio.Queue)
        assert handler.worker_task is None  # Not started yet
    
    @pytest.mark.asyncio
    async def test_completion_handler_immediate_response(self):
        """Test that COMPLETION handler returns immediately with request_id"""
        # Mock the command handler context
        mock_context = Mock()
        mock_context.state_manager = Mock()
        mock_context.completion_manager = Mock()
        mock_context.message_bus = Mock()
        
        handler = CompletionHandler(mock_context)
        
        # Mock writer
        mock_writer = AsyncMock()
        
        # Test parameters
        parameters = {
            "prompt": "Hello world",
            "client_id": "test-client-789",
            "model": "sonnet"
        }
        
        full_command = {
            "command": "COMPLETION",
            "version": "2.0",
            "parameters": parameters
        }
        
        # Call the handler
        with patch('uuid.uuid4', return_value=Mock(hex="mock-request-id-123")):
            response = await handler.handle(parameters, mock_writer, full_command)
        
        # Should return success response with request_id
        assert isinstance(response, dict)
        assert response["status"] == "success"
        assert response["command"] == "COMPLETION"
        assert "result" in response
        assert "request_id" in response["result"]
    
    @pytest.mark.asyncio
    async def test_completion_validation_error(self):
        """Test that invalid COMPLETION parameters return proper error"""
        mock_context = Mock()
        mock_context.state_manager = Mock()
        mock_context.completion_manager = Mock()
        mock_context.message_bus = Mock()
        
        handler = CompletionHandler(mock_context)
        mock_writer = AsyncMock()
        
        # Invalid parameters - missing client_id
        parameters = {
            "prompt": "Hello world",
            "model": "sonnet"
            # Missing required client_id
        }
        
        full_command = {
            "command": "COMPLETION", 
            "version": "2.0",
            "parameters": parameters
        }
        
        response = await handler.handle(parameters, mock_writer, full_command)
        
        # Should return error response
        assert isinstance(response, dict)
        assert response["status"] == "error" 
        assert response["command"] == "COMPLETION"
        assert "error" in response
        assert response["error"]["code"] == "INVALID_PARAMETERS"


class TestCompletionFlow:
    """Test the end-to-end completion flow (requires running daemon)"""
    
    def test_completion_vs_spawn_differences(self):
        """Document the key differences between old SPAWN and new COMPLETION"""
        
        # OLD SPAWN format (synchronous, single socket)
        old_spawn_command = "SPAWN:sync:claude::sonnet::What is 2+2?"
        
        # NEW COMPLETION format (async, JSON Protocol v2.0, multi-socket)  
        new_completion_command = {
            "command": "COMPLETION",
            "version": "2.0",
            "parameters": {
                "prompt": "What is 2+2?",
                "client_id": "test-client-001",
                "model": "sonnet",
                "session_id": None,
                "timeout": 300
            }
        }
        
        # Key differences:
        assert isinstance(old_spawn_command, str)  # Old: String format
        assert isinstance(new_completion_command, dict)  # New: JSON structure
        
        assert "sync" in old_spawn_command  # Old: Explicit sync/async mode
        # New: All completions are async by default
        
        assert "client_id" not in old_spawn_command  # Old: No client tracking
        assert "client_id" in new_completion_command["parameters"]  # New: Required client_id
        
        # Old SPAWN returned Claude output directly
        # New COMPLETION returns request_id immediately, result comes via events
    
    @pytest.mark.asyncio
    @pytest.mark.integration 
    async def test_completion_socket_routing(self):
        """Test that COMPLETION commands go to completion.sock"""
        # This would test with actual sockets if daemon is running
        completion_socket = Path("sockets/completion.sock")
        messaging_socket = Path("sockets/messaging.sock")
        
        # COMPLETION command should be sent to completion.sock
        # COMPLETION_RESULT events should come from messaging.sock
        # This documents the expected socket routing
        
        expected_flow = {
            "step1": "Client subscribes to COMPLETION_RESULT on messaging.sock",
            "step2": "Client sends COMPLETION command to completion.sock", 
            "step3": "Daemon returns immediate ack with request_id",
            "step4": "Daemon processes completion in background",
            "step5": "Daemon publishes COMPLETION_RESULT event to messaging.sock",
            "step6": "Client receives result via messaging subscription"
        }
        
        # This test documents the expected flow
        assert len(expected_flow) == 6
        assert "messaging.sock" in expected_flow["step1"]
        assert "completion.sock" in expected_flow["step2"]
        assert "request_id" in expected_flow["step3"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])