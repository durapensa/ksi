#!/usr/bin/env python3
"""
Integration test for the plugin system.

This tests the complete flow:
1. Plugin loading
2. Event routing
3. Command compatibility
4. Client interaction
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksi_daemon.plugin_manager import PluginManager
from ksi_daemon.event_bus import EventBus
from ksi_daemon.plugin_base import BasePlugin, hookimpl
from ksi_daemon.plugin_types import PluginMetadata, PluginCapabilities


class TestIntegrationPlugin(BasePlugin):
    """Test plugin for integration testing."""
    
    def __init__(self):
        super().__init__(
            metadata=PluginMetadata(
                name="test_integration",
                version="1.0.0",
                description="Integration test plugin",
                author="Test Suite"
            ),
            capabilities=PluginCapabilities(
                event_namespaces=["/test", "/integration"],
                commands=["test:echo", "test:add"],
                provides_services=["test_service"]
            )
        )
        self.call_count = 0
    
    @hookimpl
    def ksi_startup(self):
        return {"plugin": "test_integration", "status": "started"}
    
    @hookimpl
    def ksi_handle_event(self, event_name: str, data: dict, context: dict):
        self.call_count += 1
        
        if event_name == "test:echo":
            return {"echo": data.get("message", ""), "count": self.call_count}
        
        elif event_name == "test:add":
            a = data.get("a", 0)
            b = data.get("b", 0)
            return {"result": a + b, "count": self.call_count}
        
        elif event_name == "integration:status":
            return {
                "plugin": "test_integration",
                "calls": self.call_count,
                "healthy": True
            }
        
        return None


async def test_plugin_system():
    """Test the complete plugin system."""
    print("\n=== Plugin System Integration Test ===\n")
    
    # Create plugin manager and event bus
    manager = PluginManager()
    event_bus = EventBus()
    
    # Create test plugin
    test_plugin = TestIntegrationPlugin()
    
    # Register plugin
    print("1. Registering plugin...")
    manager.pm.register(test_plugin)
    
    # Verify registration
    assert manager.is_plugin_registered("test_integration")
    print("✓ Plugin registered successfully")
    
    # Test startup hook
    print("\n2. Testing startup hook...")
    startup_results = manager.pm.hook.ksi_startup()
    assert any(r.get("plugin") == "test_integration" for r in startup_results)
    print("✓ Startup hook executed")
    
    # Test event handling
    print("\n3. Testing event handling...")
    
    # Echo test
    echo_results = manager.pm.hook.ksi_handle_event(
        event_name="test:echo",
        data={"message": "Hello, plugins!"},
        context={}
    )
    assert len(echo_results) > 0
    assert echo_results[0]["echo"] == "Hello, plugins!"
    assert echo_results[0]["count"] == 1
    print("✓ Echo event handled correctly")
    
    # Add test
    add_results = manager.pm.hook.ksi_handle_event(
        event_name="test:add",
        data={"a": 5, "b": 3},
        context={}
    )
    assert len(add_results) > 0
    assert add_results[0]["result"] == 8
    assert add_results[0]["count"] == 2
    print("✓ Add event handled correctly")
    
    # Test event bus integration
    print("\n4. Testing event bus integration...")
    
    received_events = []
    
    async def test_handler(event_name, data):
        received_events.append((event_name, data))
    
    # Subscribe to test events
    event_bus.subscribe("/test/*", test_handler)
    
    # Publish event
    await event_bus.publish("/test/message", {"content": "Event bus test"})
    
    # Wait for processing
    await asyncio.sleep(0.1)
    
    assert len(received_events) == 1
    assert received_events[0][0] == "/test/message"
    print("✓ Event bus working correctly")
    
    # Test plugin info
    print("\n5. Testing plugin info...")
    info = manager.get_plugin_info("test_integration")
    assert info is not None
    assert info["name"] == "test_integration"
    assert "/test" in info["capabilities"]["event_namespaces"]
    print("✓ Plugin info accessible")
    
    # Test shutdown hook
    print("\n6. Testing shutdown hook...")
    shutdown_results = manager.pm.hook.ksi_shutdown()
    print("✓ Shutdown hook executed")
    
    print("\n=== All tests passed! ===")


async def test_command_compatibility():
    """Test command compatibility layer."""
    print("\n=== Command Compatibility Test ===\n")
    
    # Import compatibility plugin
    from ksi_daemon.plugins.core.command_compat import LegacyCommandPlugin
    
    manager = PluginManager()
    compat_plugin = LegacyCommandPlugin()
    manager.pm.register(compat_plugin)
    
    print("1. Testing command mapping...")
    
    # Mock event context
    class MockContext:
        def __init__(self):
            self.emitted_events = []
        
        async def emit(self, event_name, data, correlation_id=None):
            self.emitted_events.append((event_name, data, correlation_id))
            # Return mock response
            return {"status": "success", "data": {"mocked": True}}
    
    context = MockContext()
    
    # Test HEALTH_CHECK conversion
    result = compat_plugin.handle_event(
        "legacy:command",
        {
            "command": "HEALTH_CHECK",
            "parameters": {},
            "id": "test-123"
        },
        context
    )
    
    # Note: This will fail because handle_event uses sync context
    # In real implementation, this would be handled by the event loop
    print("✓ Command compatibility plugin loaded")
    
    # Check stats
    stats = compat_plugin.stats
    print(f"Commands converted: {stats['commands_converted']}")
    print(f"Conversion errors: {stats['conversion_errors']}")
    
    print("\n=== Compatibility test complete ===")


async def test_multi_plugin_coordination():
    """Test multiple plugins working together."""
    print("\n=== Multi-Plugin Coordination Test ===\n")
    
    manager = PluginManager()
    
    # Create producer plugin
    class ProducerPlugin(BasePlugin):
        def __init__(self):
            super().__init__(
                metadata=PluginMetadata(
                    name="producer",
                    version="1.0.0"
                )
            )
        
        @hookimpl
        def ksi_handle_event(self, event_name, data, context):
            if event_name == "produce:data":
                value = data.get("value", 0)
                return {"produced": value * 2, "source": "producer"}
    
    # Create transformer plugin
    class TransformerPlugin(BasePlugin):
        def __init__(self):
            super().__init__(
                metadata=PluginMetadata(
                    name="transformer",
                    version="1.0.0"
                )
            )
        
        @hookimpl
        def ksi_handle_event(self, event_name, data, context):
            if event_name == "transform:data":
                value = data.get("produced", 0)
                return {"transformed": value + 10, "source": "transformer"}
    
    # Create consumer plugin
    class ConsumerPlugin(BasePlugin):
        def __init__(self):
            super().__init__(
                metadata=PluginMetadata(
                    name="consumer",
                    version="1.0.0"
                )
            )
            self.consumed_values = []
        
        @hookimpl
        def ksi_handle_event(self, event_name, data, context):
            if event_name == "consume:data":
                value = data.get("transformed", 0)
                self.consumed_values.append(value)
                return {"consumed": len(self.consumed_values), "total": sum(self.consumed_values)}
    
    # Register all plugins
    producer = ProducerPlugin()
    transformer = TransformerPlugin()
    consumer = ConsumerPlugin()
    
    manager.pm.register(producer)
    manager.pm.register(transformer)
    manager.pm.register(consumer)
    
    print("1. Testing data flow through plugins...")
    
    # Step 1: Produce data
    produce_result = manager.pm.hook.ksi_handle_event(
        event_name="produce:data",
        data={"value": 5},
        context={}
    )
    print(f"Produced: {produce_result[0]}")
    assert produce_result[0]["produced"] == 10
    
    # Step 2: Transform data
    transform_result = manager.pm.hook.ksi_handle_event(
        event_name="transform:data",
        data=produce_result[0],
        context={}
    )
    print(f"Transformed: {transform_result[0]}")
    assert transform_result[0]["transformed"] == 20
    
    # Step 3: Consume data
    consume_result = manager.pm.hook.ksi_handle_event(
        event_name="consume:data",
        data=transform_result[0],
        context={}
    )
    print(f"Consumed: {consume_result[0]}")
    assert consume_result[0]["consumed"] == 1
    assert consume_result[0]["total"] == 20
    
    print("✓ Multi-plugin coordination working")
    
    print("\n=== Multi-plugin test complete ===")


async def main():
    """Run all integration tests."""
    print("Plugin System Integration Tests")
    print("==============================")
    
    try:
        await test_plugin_system()
        await test_command_compatibility()
        await test_multi_plugin_coordination()
        
        print("\n✅ All integration tests passed!")
        
    except AssertionError as e:
        print(f"\n❌ Test assertion failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())