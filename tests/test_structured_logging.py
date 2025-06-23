#!/usr/bin/env python3
"""
Test structured logging implementation with contextvars and event taxonomy.

Tests:
- Context propagation through async operations
- Event taxonomy usage
- Functional domain identification
- Context managers
- Log output structure
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import structlog
from io import StringIO

# Add daemon directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from daemon.logging_config import (
    get_logger, bind_socket_context, clear_context, 
    command_context, agent_context, log_event
)
from daemon.event_taxonomy import AGENT_EVENTS, SOCKET_EVENTS, format_agent_event
from daemon.config import config


class StructuredLogCapture:
    """Capture structured log output for testing."""
    
    def __init__(self):
        self.logs = []
        self.original_processors = None
        
    def __enter__(self):
        # Configure structlog to capture logs
        self.original_processors = structlog.get_config()
        
        def capture_processor(logger, method_name, event_dict):
            self.logs.append(event_dict.copy())
            return event_dict
            
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                capture_processor,
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        return self
        
    def __exit__(self, *args):
        # Restore original configuration
        if self.original_processors:
            config.configure_structlog()
    
    def get_events(self, event_name=None):
        """Get captured events, optionally filtered by name."""
        if event_name:
            return [log for log in self.logs if log.get('event') == event_name]
        return self.logs


async def test_context_propagation():
    """Test that context propagates through async operations."""
    print("\n1. Testing context propagation...")
    
    with StructuredLogCapture() as capture:
        # Bind initial context
        bind_socket_context("agents", request_id="test-123", agent_id="agent-001")
        
        logger = get_logger("test")
        
        # Log in main context
        log_event(logger, "test.main", detail="main context")
        
        # Async function that should inherit context
        async def nested_operation():
            log_event(logger, "test.nested", detail="nested context")
            
        await nested_operation()
        
        # Clear context
        clear_context()
        
        # Log without context
        log_event(logger, "test.no_context", detail="no context")
    
    # Verify results
    events = capture.get_events()
    assert len(events) == 3, f"Expected 3 events, got {len(events)}"
    
    # Check context propagation
    assert events[0]["request_id"] == "test-123"
    assert events[0]["agent_id"] == "agent-001"
    assert events[0]["functional_domain"] == "agents"
    
    assert events[1]["request_id"] == "test-123"
    assert events[1]["agent_id"] == "agent-001"
    
    # Check context was cleared
    assert "request_id" not in events[2]
    assert "agent_id" not in events[2]
    
    print("✓ Context propagation working correctly")


async def test_command_context_manager():
    """Test command context manager with timing."""
    print("\n2. Testing command context manager...")
    
    with StructuredLogCapture() as capture:
        logger = get_logger("test")
        
        async with command_context("SPAWN_AGENT", {"agent_id": "test-001"}) as command_id:
            log_event(logger, "test.inside_command", command_id=command_id)
            await asyncio.sleep(0.1)  # Simulate work
    
    events = capture.get_events()
    
    # Should have the test event and command.completed
    test_events = [e for e in events if e.get('event') == 'test.inside_command']
    completed_events = [e for e in events if e.get('event') == 'command.completed']
    
    assert len(test_events) == 1
    assert len(completed_events) == 1
    
    # Check timing was recorded
    assert completed_events[0]["duration_ms"] >= 100
    assert completed_events[0]["command_name"] == "SPAWN_AGENT"
    
    print("✓ Command context manager working with timing")


async def test_agent_context_manager():
    """Test agent context manager."""
    print("\n3. Testing agent context manager...")
    
    with StructuredLogCapture() as capture:
        logger = get_logger("test")
        
        async with agent_context("agent-123", "session-456"):
            log_event(logger, "agent.test_operation")
    
    events = capture.get_events("agent.test_operation")
    assert len(events) == 1
    assert events[0]["agent_id"] == "agent-123"
    assert events[0]["session_id"] == "session-456"
    
    print("✓ Agent context manager working correctly")


def test_functional_domain_identification():
    """Test functional domain identification for different command types."""
    print("\n4. Testing functional domain identification...")
    
    from daemon.core import KSIDaemonCore
    daemon = KSIDaemonCore("/tmp/test.sock")
    
    # Test each domain
    test_cases = [
        ("HEALTH_CHECK", {}, "admin"),
        ("SPAWN_AGENT", {"agent_id": "test"}, "agents"),
        ("PUBLISH", {"event": "test"}, "messaging"),
        ("SET_AGENT_KV", {"key": "test"}, "state"),
        ("COMPLETION", {"prompt": "test"}, "completion"),
        ("UNKNOWN_COMMAND", {}, "admin"),  # Default
    ]
    
    for command, params, expected_domain in test_cases:
        domain = daemon._determine_functional_domain(command, params)
        assert domain == expected_domain, f"Command {command} should map to {expected_domain}, got {domain}"
    
    print("✓ Functional domain identification working correctly")


def test_event_taxonomy():
    """Test event taxonomy usage."""
    print("\n5. Testing event taxonomy...")
    
    # Test format functions
    agent_event = format_agent_event("agent.spawned", "agent-001", profile="test")
    assert agent_event["event"] == "agent.spawned"
    assert agent_event["agent_id"] == "agent-001"
    assert agent_event["profile"] == "test"
    
    # Test event descriptions
    from daemon.event_taxonomy import get_event_description, validate_event_name
    
    assert validate_event_name("agent.spawned") == True
    assert validate_event_name("invalid.event") == False
    
    desc = get_event_description("socket.connected")
    assert "connected" in desc.lower()
    
    print("✓ Event taxonomy working correctly")


def test_structured_log_output():
    """Test that logs are properly structured JSON."""
    print("\n6. Testing structured log output...")
    
    # Configure for JSON output
    config.log_format = "json"
    config.configure_structlog()
    
    with StructuredLogCapture() as capture:
        logger = get_logger("test")
        
        bind_socket_context("admin", request_id="req-123")
        log_event(logger, "daemon.health_check", 
                 status="healthy",
                 agents_count=5,
                 uptime_seconds=3600)
    
    events = capture.get_events()
    assert len(events) == 1
    
    event = events[0]
    assert event["event"] == "daemon.health_check"
    assert event["status"] == "healthy"
    assert event["agents_count"] == 5
    assert event["request_id"] == "req-123"
    assert event["functional_domain"] == "admin"
    
    # Verify it's valid JSON when rendered
    json_output = json.dumps(event)
    parsed = json.loads(json_output)
    assert parsed["event"] == "daemon.health_check"
    
    print("✓ Structured JSON output working correctly")


async def main():
    """Run all tests."""
    print("Testing KSI Daemon Structured Logging Implementation")
    print("=" * 50)
    
    try:
        # Run async tests
        await test_context_propagation()
        await test_command_context_manager()
        await test_agent_context_manager()
        
        # Run sync tests
        test_functional_domain_identification()
        test_event_taxonomy()
        test_structured_log_output()
        
        print("\n" + "=" * 50)
        print("✅ All structured logging tests passed!")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)