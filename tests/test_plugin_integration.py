#!/usr/bin/env python3
"""
Plugin System Integration Tests

Comprehensive tests for the KSI plugin system with all core plugins.
Tests event routing, service interaction, and plugin lifecycle.
"""

import asyncio
import json
import tempfile
from pathlib import Path
import pytest
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_daemon.core_plugin import PluginDaemon
from ksi_daemon.event_bus import EventBus
from ksi_daemon.plugin_manager import PluginManager


class TestPluginIntegration:
    """Integration tests for the complete plugin system."""
    
    @pytest.fixture
    async def daemon(self):
        """Create a test daemon instance."""
        # Use temporary directory for test data
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "daemon": {
                    "plugin_dirs": [
                        str(Path(__file__).parent.parent / "ksi_daemon" / "plugins")
                    ],
                    "max_event_history": 100
                },
                "transports": {
                    "unix": {
                        "enabled": False  # Disable for tests
                    }
                },
                "plugins": {
                    "state_service": {
                        "state_dir": str(Path(tmpdir) / "state")
                    },
                    "agent_service": {
                        "profiles_dir": str(Path(tmpdir) / "profiles"),
                        "identities_file": str(Path(tmpdir) / "identities.json")
                    }
                }
            }
            
            daemon = PluginDaemon(config)
            await daemon.initialize()
            yield daemon
            await daemon.shutdown()
    
    @pytest.mark.asyncio
    async def test_plugin_loading(self, daemon):
        """Test that all core plugins load successfully."""
        # Check plugin manager exists
        assert daemon.plugin_manager is not None
        
        # Get loaded plugins
        plugins = daemon.plugin_manager.get_loaded_plugins()
        
        # Verify core plugins are loaded
        plugin_names = [p.metadata.name for p in plugins]
        assert "state_service" in plugin_names
        assert "agent_service" in plugin_names
        assert "completion_service" in plugin_names
    
    @pytest.mark.asyncio
    async def test_event_routing(self, daemon):
        """Test event routing between plugins."""
        event_bus = daemon.event_bus
        
        # Test state service event
        result = await event_bus.emit("state:set", {
            "namespace": "test",
            "key": "foo",
            "value": "bar"
        })
        
        assert result is not None
        assert result.get("status") == "ok"
        
        # Verify state was set
        get_result = await event_bus.emit("state:get", {
            "namespace": "test",
            "key": "foo"
        })
        
        assert get_result is not None
        assert get_result.get("value") == "bar"
    
    @pytest.mark.asyncio
    async def test_agent_lifecycle(self, daemon):
        """Test agent management lifecycle."""
        event_bus = daemon.event_bus
        
        # Verify test profile exists in composition system
        profile_result = await event_bus.emit("composition:profile", {
            "name": "claude_agent_default"  # Use existing migrated profile
        })
        
        assert profile_result is not None
        assert profile_result.get("status") == "success"
        assert "profile" in profile_result
        
        # Create agent identity
        identity_result = await event_bus.emit("agent:create_identity", {
            "agent_id": "test_001",
            "role": "analyst",
            "display_name": "Test Analyst"
        })
        
        assert identity_result is not None
        assert "identity" in identity_result
        assert identity_result["identity"]["agent_id"] == "test_001"
        
        # List agents (should be empty initially)
        list_result = await event_bus.emit("agent:list", {})
        assert list_result is not None
        assert list_result.get("count") == 0
        
        # Register an agent manually (since we can't spawn real processes in tests)
        register_result = await event_bus.emit("agent:register", {
            "agent_id": "test_001",
            "agent_info": {
                "profile": "test_agent",
                "role": "analyst",
                "capabilities": ["analysis", "reporting"],
                "status": "active"
            }
        })
        
        assert register_result is not None
        assert register_result.get("status") == "registered"
        
        # List agents again
        list_result = await event_bus.emit("agent:list", {})
        assert list_result.get("count") == 1
        assert list_result["agents"][0]["agent_id"] == "test_001"
    
    @pytest.mark.asyncio
    async def test_task_routing(self, daemon):
        """Test task routing to agents based on capabilities."""
        event_bus = daemon.event_bus
        
        # Register multiple agents with different capabilities
        agents = [
            {
                "agent_id": "analyst_001",
                "info": {
                    "role": "analyst",
                    "capabilities": ["analysis", "data_processing", "reporting"],
                    "status": "active"
                }
            },
            {
                "agent_id": "creative_001",
                "info": {
                    "role": "creative",
                    "capabilities": ["writing", "design", "brainstorming"],
                    "status": "active"
                }
            },
            {
                "agent_id": "researcher_001",
                "info": {
                    "role": "researcher",
                    "capabilities": ["research", "fact_checking", "analysis"],
                    "status": "active"
                }
            }
        ]
        
        for agent in agents:
            await event_bus.emit("agent:register", {
                "agent_id": agent["agent_id"],
                "agent_info": agent["info"]
            })
        
        # Test routing by capability
        route_result = await event_bus.emit("agent:route_task", {
            "task": "Analyze this dataset",
            "required_capabilities": ["analysis", "data_processing"]
        })
        
        assert route_result is not None
        assert route_result.get("agent_id") == "analyst_001"
        assert route_result.get("score") > 0
        
        # Test routing by role preference
        route_result = await event_bus.emit("agent:route_task", {
            "task": "Write a creative story",
            "preferred_role": "creative"
        })
        
        assert route_result.get("agent_id") == "creative_001"
    
    @pytest.mark.asyncio
    async def test_agent_messaging(self, daemon):
        """Test inter-agent messaging."""
        event_bus = daemon.event_bus
        
        # Register test agents
        await event_bus.emit("agent:register", {
            "agent_id": "sender_001",
            "agent_info": {"role": "general", "status": "active"}
        })
        
        await event_bus.emit("agent:register", {
            "agent_id": "receiver_001",
            "agent_info": {"role": "general", "status": "active"}
        })
        
        # Track messages
        messages_received = []
        
        async def message_handler(event_name, data, context):
            if event_name == "agent:message":
                messages_received.append(data)
        
        # Subscribe to agent messages
        await event_bus.subscribe(
            subscriber="test",
            patterns=["agent:message"],
            handler=message_handler
        )
        
        # Send a message
        send_result = await event_bus.emit("agent:send_message", {
            "sender_agent": "sender_001",
            "target_agent": "receiver_001",
            "message": "Hello from sender!",
            "message_type": "text"
        })
        
        assert send_result is not None
        assert send_result.get("status") == "sent"
        
        # Allow time for async message delivery
        await asyncio.sleep(0.1)
        
        # Verify message was received
        assert len(messages_received) == 1
        assert messages_received[0]["from"] == "sender_001"
        assert messages_received[0]["to"] == "receiver_001"
        assert messages_received[0]["message"] == "Hello from sender!"
    
    @pytest.mark.asyncio
    async def test_agent_state_integration(self, daemon):
        """Test agent state management integration."""
        event_bus = daemon.event_bus
        
        # Register an agent
        await event_bus.emit("agent:register", {
            "agent_id": "stateful_001",
            "agent_info": {"role": "general", "status": "active"}
        })
        
        # Update agent state
        state_result = await event_bus.emit("agent:update_state", {
            "agent_id": "stateful_001",
            "key": "current_task",
            "value": {"task": "Processing data", "progress": 0.5}
        })
        
        assert state_result is not None
        assert state_result.get("status") == "ok"
        
        # Get agent state
        get_result = await event_bus.emit("agent:get_state", {
            "agent_id": "stateful_001",
            "key": "current_task"
        })
        
        assert get_result is not None
        assert get_result.get("value") == {"task": "Processing data", "progress": 0.5}
    
    @pytest.mark.asyncio
    async def test_plugin_shutdown(self, daemon):
        """Test graceful plugin shutdown."""
        # Register some test data
        await daemon.event_bus.emit("state:set", {
            "namespace": "test",
            "key": "shutdown_test",
            "value": "data"
        })
        
        await daemon.event_bus.emit("agent:register", {
            "agent_id": "shutdown_test",
            "agent_info": {"status": "active"}
        })
        
        # Shutdown daemon
        await daemon.shutdown()
        
        # Verify shutdown completed without errors
        assert daemon.shutdown_event.is_set()
    
    @pytest.mark.asyncio
    async def test_event_history(self, daemon):
        """Test event history tracking."""
        event_bus = daemon.event_bus
        
        # Emit several events
        events_to_emit = [
            ("state:set", {"namespace": "test", "key": "a", "value": 1}),
            ("state:set", {"namespace": "test", "key": "b", "value": 2}),
            ("agent:list", {}),
            ("state:get", {"namespace": "test", "key": "a"})
        ]
        
        for event_name, data in events_to_emit:
            await event_bus.emit(event_name, data)
        
        # Get event history
        history = event_bus.get_event_history()
        
        # Verify events were recorded
        assert len(history) >= len(events_to_emit)
        
        # Check event structure
        for record in history:
            assert hasattr(record, 'metadata')
            assert hasattr(record, 'event_name')
            assert hasattr(record, 'data')
            assert record.metadata.timestamp is not None
    
    @pytest.mark.asyncio
    async def test_service_dependencies(self, daemon):
        """Test service dependencies between plugins."""
        event_bus = daemon.event_bus
        
        # Agent service depends on state service
        # Create an agent with state
        await event_bus.emit("agent:register", {
            "agent_id": "dependent_001",
            "agent_info": {"status": "active"}
        })
        
        # Update state through agent service
        result = await event_bus.emit("agent:update_state", {
            "agent_id": "dependent_001",
            "key": "dependency_test",
            "value": "working"
        })
        
        assert result is not None
        assert result.get("status") == "ok"
        
        # Verify state was actually stored
        state_result = await event_bus.emit("state:get", {
            "namespace": "agent:dependent_001",
            "key": "dependency_test"
        })
        
        assert state_result is not None
        assert state_result.get("value") == "working"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])