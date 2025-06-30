#!/usr/bin/env python3
"""
Comprehensive test suite for the unified injection system.

Tests both direct and next mode injection with various positions.
"""

import asyncio
import json
import pytest
from pathlib import Path
from typing import Dict, Any, Optional
import tempfile

# Import the injection components
from ksi_daemon.plugins.injection.injection_types import (
    InjectionRequest,
    InjectionMode,
    InjectionPosition,
    InjectionResult,
    InjectionError
)


class MockStateManager:
    """Mock state manager for testing."""
    
    def __init__(self):
        self.state = {}
        self.composition_index = {}
    
    async def push(self, namespace: str, key: str, data: Dict[str, Any], ttl_seconds: Optional[int] = None) -> int:
        """Mock push to queue."""
        if namespace not in self.state:
            self.state[namespace] = {}
        if key not in self.state[namespace]:
            self.state[namespace][key] = []
        
        self.state[namespace][key].append(data)
        return len(self.state[namespace][key]) - 1
    
    async def pop(self, namespace: str, key: str) -> Optional[Dict[str, Any]]:
        """Mock pop from queue."""
        if namespace in self.state and key in self.state[namespace]:
            if self.state[namespace][key]:
                return self.state[namespace][key].pop(0)
        return None
    
    async def get_queue(self, namespace: str, key: str) -> list:
        """Mock get queue."""
        if namespace in self.state and key in self.state[namespace]:
            return self.state[namespace][key]
        return []
    
    async def queue_length(self, namespace: str, key: str) -> int:
        """Mock queue length."""
        if namespace in self.state and key in self.state[namespace]:
            return len(self.state[namespace][key])
        return 0


class MockEventEmitter:
    """Mock event emitter for testing."""
    
    def __init__(self):
        self.events = []
    
    async def emit(self, event_name: str, data: Dict[str, Any], context: Dict[str, Any] = None):
        """Record emitted events."""
        if context is None:
            context = {}
            
        self.events.append({
            "event": event_name,
            "data": data,
            "context": context
        })
        
        # Mock response for claude:completion:result
        if event_name == "claude:completion:result":
            return {
                "request_id": data.get("request_id"),
                "session_id": "test-session-123",
                "response": "Test response"
            }
        
        # Mock response for async_state:push (used by NEXT mode)
        if event_name == "async_state:push":
            return {
                "success": True,
                "position": 0,  # Code looks for "position" not "queue_position"
                "namespace": data.get("namespace"),
                "key": data.get("key")
            }
        
        return {}


class TestInjectionSystem:
    """Test cases for the unified injection system."""
    
    @pytest.fixture
    def mock_state_manager(self):
        """Create mock state manager."""
        return MockStateManager()
    
    @pytest.fixture
    def mock_event_emitter(self):
        """Create mock event emitter."""
        return MockEventEmitter()
    
    def test_injection_request_creation(self):
        """Test creating injection requests."""
        # Basic request
        req = InjectionRequest(
            content="Test injection",
            mode=InjectionMode.DIRECT,
            position=InjectionPosition.BEFORE_PROMPT
        )
        
        assert req.content == "Test injection"
        assert req.mode == InjectionMode.DIRECT
        assert req.position == InjectionPosition.BEFORE_PROMPT
        assert req.session_id is None
        assert req.priority == "normal"
        
        # Request with all fields
        req2 = InjectionRequest(
            content="Another injection",
            mode=InjectionMode.NEXT,
            position=InjectionPosition.SYSTEM_REMINDER,
            session_id="session-123",
            priority="high",
            metadata={"key": "value"}
        )
        
        assert req2.session_id == "session-123"
        assert req2.priority == "high"
        assert req2.metadata == {"key": "value"}
    
    def test_injection_modes(self):
        """Test injection mode enum."""
        assert InjectionMode.DIRECT.value == "direct"
        assert InjectionMode.NEXT.value == "next"
        
        # Test string conversion
        assert str(InjectionMode.DIRECT) == "InjectionMode.DIRECT"
    
    def test_injection_positions(self):
        """Test injection position enum."""
        positions = [
            InjectionPosition.BEFORE_PROMPT,
            InjectionPosition.AFTER_PROMPT,
            InjectionPosition.SYSTEM_REMINDER
        ]
        
        assert len(positions) == 3
        assert InjectionPosition.BEFORE_PROMPT.value == "before_prompt"
        assert InjectionPosition.AFTER_PROMPT.value == "after_prompt"
        assert InjectionPosition.SYSTEM_REMINDER.value == "system_reminder"
    
    @pytest.mark.asyncio
    async def test_direct_mode_injection(self, mock_state_manager, mock_event_emitter):
        """Test direct mode injection."""
        from ksi_daemon.plugins.injection.injection_router import process_injection
        
        # Mock the globals
        import ksi_daemon.plugins.injection.injection_router as router
        router.state_manager = mock_state_manager
        router.event_emitter = mock_event_emitter.emit
        
        # Create direct injection request
        request = InjectionRequest(
            content="Direct test content",
            mode=InjectionMode.DIRECT,
            position=InjectionPosition.BEFORE_PROMPT,
            session_id="test-session",
            metadata={"test": True}
        )
        
        # Process injection
        result = await process_injection(request)
        
        # Verify result
        assert isinstance(result, InjectionResult)
        assert result.success is True
        assert result.mode == InjectionMode.DIRECT
        assert result.position == InjectionPosition.BEFORE_PROMPT
        assert result.session_id == "test-session"
        
        # Verify event was emitted
        assert len(mock_event_emitter.events) == 1
        event = mock_event_emitter.events[0]
        assert event["event"] == "claude:completion:result"
        assert event["data"]["session_id"] == "test-session"
    
    @pytest.mark.asyncio
    async def test_next_mode_injection(self, mock_state_manager, mock_event_emitter):
        """Test next mode injection."""
        from ksi_daemon.plugins.injection.injection_router import process_injection
        
        # Mock the globals  
        import ksi_daemon.plugins.injection.injection_router as router
        router.state_manager = mock_state_manager
        router.event_emitter = mock_event_emitter.emit  # Next mode needs event emitter for async_state:push
        
        # Create next mode injection request
        request = InjectionRequest(
            content="Next mode content",
            mode=InjectionMode.NEXT,
            position=InjectionPosition.AFTER_PROMPT,
            session_id="test-session-2",
            priority="high"
        )
        
        # Process injection
        result = await process_injection(request)
        
        # Verify result
        assert isinstance(result, InjectionResult)
        assert result.success is True
        assert result.mode == InjectionMode.NEXT
        assert result.position == InjectionPosition.AFTER_PROMPT
        assert result.session_id == "test-session-2"
        assert result.queued is True
        assert result.queue_position == 0
        
        # Verify async_state:push event was emitted
        async_state_events = [e for e in mock_event_emitter.events if e["event"] == "async_state:push"]
        assert len(async_state_events) == 1
        
        event_data = async_state_events[0]["data"]
        assert event_data["namespace"] == "injection"
        assert event_data["key"] == "test-session-2"
        assert event_data["data"]["content"] == "Next mode content"
        assert event_data["data"]["position"] == "after_prompt"
    
    @pytest.mark.asyncio
    async def test_invalid_injection_request(self, mock_state_manager):
        """Test handling invalid injection requests."""
        from ksi_daemon.plugins.injection.injection_router import process_injection
        
        # Mock the globals
        import ksi_daemon.plugins.injection.injection_router as router
        router.state_manager = mock_state_manager
        
        # Test with invalid mode
        try:
            request = InjectionRequest(
                content="Test",
                mode="invalid",  # type: ignore
                position=InjectionPosition.BEFORE_PROMPT
            )
            pytest.fail("Should have raised ValueError")
        except ValueError:
            pass  # Expected
        
        # Test next mode without session_id
        request = InjectionRequest(
            content="Test",
            mode=InjectionMode.NEXT,
            position=InjectionPosition.BEFORE_PROMPT
        )
        
        result = await process_injection(request)
        assert isinstance(result, InjectionResult)
        assert result.success is False
        assert "session_id required" in result.error
    
    @pytest.mark.asyncio
    async def test_queue_management(self, mock_state_manager):
        """Test injection queue management."""
        # Queue multiple items
        for i in range(3):
            await mock_state_manager.push(
                "injection",
                "session-123",
                {
                    "content": f"Item {i}",
                    "position": "before_prompt",
                    "priority": "normal"
                }
            )
        
        # Check queue length
        length = await mock_state_manager.queue_length("injection", "session-123")
        assert length == 3
        
        # Pop items
        item1 = await mock_state_manager.pop("injection", "session-123")
        assert item1["content"] == "Item 0"
        
        item2 = await mock_state_manager.pop("injection", "session-123")
        assert item2["content"] == "Item 1"
        
        # Check remaining
        length = await mock_state_manager.queue_length("injection", "session-123")
        assert length == 1
    
    def test_injection_result_creation(self):
        """Test injection result object."""
        # Success result
        result = InjectionResult(
            success=True,
            mode=InjectionMode.DIRECT,
            position=InjectionPosition.SYSTEM_REMINDER,
            session_id="abc123",
            request_id="req123"
        )
        
        assert result.success is True
        assert result.error is None
        dict_result = result.to_dict()
        assert dict_result["success"] is True
        assert dict_result["mode"] == "direct"
        
        # Error result
        error_result = InjectionResult(
            success=False,
            mode=InjectionMode.NEXT,
            error="Test error",
            error_type=InjectionError.INVALID_MODE
        )
        
        assert error_result.success is False
        assert error_result.error == "Test error"
        assert error_result.error_type == InjectionError.INVALID_MODE
    
    @pytest.mark.asyncio
    async def test_system_reminder_position(self, mock_state_manager, mock_event_emitter):
        """Test system reminder injection position."""
        from ksi_daemon.plugins.injection.injection_router import process_injection
        
        # Mock the globals
        import ksi_daemon.plugins.injection.injection_router as router
        router.state_manager = mock_state_manager
        router.event_emitter = mock_event_emitter.emit
        
        # Create system reminder injection
        request = InjectionRequest(
            content="<system-reminder>Important note</system-reminder>",
            mode=InjectionMode.DIRECT,
            position=InjectionPosition.SYSTEM_REMINDER,
            session_id="reminder-session"
        )
        
        # Process injection
        result = await process_injection(request)
        
        # Verify result
        assert result.success is True
        assert result.position == InjectionPosition.SYSTEM_REMINDER
        
        # Verify event format
        event = mock_event_emitter.events[0]
        assert "<system-reminder>" in event["data"]["injection"]["content"]


class TestInjectionIntegration:
    """Integration tests for injection with completion service."""
    
    @pytest.mark.asyncio
    async def test_completion_with_injection(self):
        """Test completion request with injection."""
        # This would test the full flow with completion service
        # For now, we'll create a placeholder
        pass
    
    @pytest.mark.asyncio
    async def test_injection_priority_handling(self):
        """Test priority handling in injection queue."""
        # Test that high priority injections are processed first
        pass
    
    @pytest.mark.asyncio  
    async def test_injection_expiration(self):
        """Test that old injections expire properly."""
        # Test TTL functionality
        pass


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])