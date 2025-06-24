#!/usr/bin/env python3
"""
Comprehensive test suite for the KSI plugin system.

Tests cover:
- Plugin discovery and loading
- Hook execution and ordering
- Event bus functionality
- Namespace isolation
- Correlation ID handling
- Plugin lifecycle management
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest
from unittest.mock import Mock, patch, AsyncMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksi_daemon.plugin_loader import PluginLoader
from ksi_daemon.plugin_manager import PluginManager
from ksi_daemon.event_bus import EventBus
from ksi_daemon.plugin_types import PluginMetadata, PluginCapabilities
from ksi_daemon.plugin_base import BasePlugin, hookimpl
import ksi_daemon.hookspecs as hookspecs


# Test Plugin Fixtures
class TestPlugin(BasePlugin):
    """Simple test plugin for basic functionality."""
    
    def __init__(self):
        super().__init__(
            metadata=PluginMetadata(
                name="test_plugin",
                version="1.0.0",
                description="Test plugin for unit tests",
                author="Test Suite"
            ),
            capabilities=PluginCapabilities(
                event_namespaces=["/test"],
                commands=["test:ping", "test:echo"],
                provides_services=["test_service"]
            )
        )
        self.startup_called = False
        self.shutdown_called = False
        self.events_received = []
    
    @hookimpl
    def ksi_startup(self):
        self.startup_called = True
        return {"status": "test_plugin_started"}
    
    @hookimpl
    def ksi_shutdown(self):
        self.shutdown_called = True
        return {"status": "test_plugin_stopped"}
    
    @hookimpl
    def ksi_handle_event(self, event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
        self.events_received.append((event_name, data, context))
        
        if event_name == "test:ping":
            return {"pong": True, "echo": data.get("message", "")}
        elif event_name == "test:echo":
            return {"echoed": data}
        
        return None


class OrderTestPlugin(BasePlugin):
    """Plugin to test hook ordering."""
    
    def __init__(self):
        super().__init__(
            metadata=PluginMetadata(
                name="order_test_plugin",
                version="1.0.0",
                description="Plugin for testing hook order",
                author="Test Suite"
            )
        )
    
    @hookimpl(tryfirst=True)
    def ksi_handle_event(self, event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
        if event_name == "order:test":
            return {"order": "first", "value": data.get("value", 0) + 1}


class ErrorTestPlugin(BasePlugin):
    """Plugin that raises errors for testing error handling."""
    
    @hookimpl
    def ksi_startup(self):
        raise RuntimeError("Startup error test")
    
    @hookimpl
    def ksi_handle_event(self, event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
        if event_name == "error:test":
            raise ValueError("Event handling error test")


# Test Suite
class TestPluginLoader:
    """Test plugin discovery and loading functionality."""
    
    def test_plugin_discovery(self):
        """Test that plugins can be discovered from a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test plugin file
            plugin_path = Path(tmpdir) / "test_discovery.py"
            plugin_path.write_text('''
from ksi_daemon.plugin_base import BasePlugin, hookimpl
from ksi_daemon.plugin_types import PluginMetadata

class DiscoveryTestPlugin(BasePlugin):
    def __init__(self):
        super().__init__(
            metadata=PluginMetadata(
                name="discovery_test",
                version="1.0.0",
                description="Discovery test plugin"
            )
        )
    
    @hookimpl
    def ksi_startup(self):
        return {"discovered": True}
''')
            
            loader = PluginLoader()
            loader.plugin_dirs = [tmpdir]
            plugins = loader.discover_plugins()
            
            assert len(plugins) > 0
            assert any(p.__name__ == "test_discovery" for p in plugins)
    
    def test_plugin_loading(self):
        """Test loading a plugin module."""
        loader = PluginLoader()
        
        # Create plugin instance
        plugin = TestPlugin()
        
        # Verify plugin has correct hooks
        assert hasattr(plugin, "ksi_startup")
        assert hasattr(plugin, "ksi_shutdown")
        assert hasattr(plugin, "ksi_handle_event")
    
    def test_invalid_plugin_handling(self):
        """Test handling of invalid plugin files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create invalid plugin file
            invalid_path = Path(tmpdir) / "invalid_plugin.py"
            invalid_path.write_text("invalid python syntax {{")
            
            loader = PluginLoader()
            loader.plugin_dirs = [tmpdir]
            
            # Should not crash, just skip invalid plugins
            plugins = loader.discover_plugins()
            assert all(p.__name__ != "invalid_plugin" for p in plugins)


class TestPluginManager:
    """Test plugin management and lifecycle."""
    
    @pytest.fixture
    def plugin_manager(self):
        """Create a plugin manager instance."""
        return PluginManager()
    
    def test_plugin_registration(self, plugin_manager):
        """Test registering plugins with the manager."""
        plugin = TestPlugin()
        plugin_manager.pm.register(plugin)
        
        assert plugin in plugin_manager.pm.get_plugins()
        assert plugin_manager.is_plugin_registered("test_plugin")
    
    def test_plugin_lifecycle(self, plugin_manager):
        """Test plugin startup and shutdown lifecycle."""
        plugin = TestPlugin()
        plugin_manager.pm.register(plugin)
        
        # Test startup
        startup_results = plugin_manager.pm.hook.ksi_startup()
        assert plugin.startup_called
        assert any(r.get("status") == "test_plugin_started" for r in startup_results)
        
        # Test shutdown
        shutdown_results = plugin_manager.pm.hook.ksi_shutdown()
        assert plugin.shutdown_called
        assert any(r.get("status") == "test_plugin_stopped" for r in shutdown_results)
    
    def test_hook_ordering(self, plugin_manager):
        """Test that hook ordering works correctly."""
        order_plugin = OrderTestPlugin()
        test_plugin = TestPlugin()
        
        plugin_manager.pm.register(order_plugin)
        plugin_manager.pm.register(test_plugin)
        
        # OrderTestPlugin should run first due to tryfirst=True
        results = plugin_manager.pm.hook.ksi_handle_event(
            event_name="order:test",
            data={"value": 0},
            context={}
        )
        
        # First result should be from OrderTestPlugin
        assert results[0]["order"] == "first"
        assert results[0]["value"] == 1
    
    def test_error_handling(self, plugin_manager):
        """Test that plugin errors are handled gracefully."""
        error_plugin = ErrorTestPlugin()
        plugin_manager.pm.register(error_plugin)
        
        # Startup error should be caught
        with pytest.raises(RuntimeError):
            plugin_manager.pm.hook.ksi_startup()
        
        # Event handling error should be caught
        with pytest.raises(ValueError):
            plugin_manager.pm.hook.ksi_handle_event(
                event_name="error:test",
                data={},
                context={}
            )
    
    def test_plugin_capabilities(self, plugin_manager):
        """Test querying plugin capabilities."""
        plugin = TestPlugin()
        plugin_manager.pm.register(plugin)
        
        # Get plugin info
        info = plugin_manager.get_plugin_info("test_plugin")
        assert info is not None
        assert info["name"] == "test_plugin"
        assert info["version"] == "1.0.0"
        assert "/test" in info["capabilities"]["event_namespaces"]
        assert "test:ping" in info["capabilities"]["commands"]


class TestEventBus:
    """Test event bus functionality."""
    
    @pytest.fixture
    def event_bus(self):
        """Create an event bus instance."""
        return EventBus()
    
    @pytest.mark.asyncio
    async def test_event_publish_subscribe(self, event_bus):
        """Test basic publish/subscribe functionality."""
        received_events = []
        
        async def handler(event_name, data):
            received_events.append((event_name, data))
        
        # Subscribe to events
        event_bus.subscribe("/test/event", handler)
        
        # Publish event
        await event_bus.publish("/test/event", {"message": "hello"})
        
        # Allow event to be processed
        await asyncio.sleep(0.1)
        
        assert len(received_events) == 1
        assert received_events[0][0] == "/test/event"
        assert received_events[0][1]["message"] == "hello"
    
    @pytest.mark.asyncio
    async def test_namespace_isolation(self, event_bus):
        """Test that namespaces are properly isolated."""
        test_events = []
        other_events = []
        
        async def test_handler(event_name, data):
            test_events.append((event_name, data))
        
        async def other_handler(event_name, data):
            other_events.append((event_name, data))
        
        # Subscribe to different namespaces
        event_bus.subscribe("/test/*", test_handler)
        event_bus.subscribe("/other/*", other_handler)
        
        # Publish to different namespaces
        await event_bus.publish("/test/event1", {"type": "test"})
        await event_bus.publish("/other/event1", {"type": "other"})
        await event_bus.publish("/test/event2", {"type": "test2"})
        
        await asyncio.sleep(0.1)
        
        # Verify isolation
        assert len(test_events) == 2
        assert len(other_events) == 1
        assert all(e[1]["type"].startswith("test") for e in test_events)
        assert other_events[0][1]["type"] == "other"
    
    @pytest.mark.asyncio
    async def test_correlation_ids(self, event_bus):
        """Test correlation ID handling for request/response patterns."""
        responses = {}
        
        async def response_handler(event_name, data):
            if "correlation_id" in data:
                responses[data["correlation_id"]] = data
        
        event_bus.subscribe("/response/*", response_handler)
        
        # Send request with correlation ID
        correlation_id = "test-correlation-123"
        await event_bus.publish("/request/test", {
            "correlation_id": correlation_id,
            "query": "test"
        })
        
        # Simulate response
        await event_bus.publish("/response/test", {
            "correlation_id": correlation_id,
            "result": "success"
        })
        
        await asyncio.sleep(0.1)
        
        assert correlation_id in responses
        assert responses[correlation_id]["result"] == "success"
    
    @pytest.mark.asyncio
    async def test_wildcard_subscriptions(self, event_bus):
        """Test wildcard pattern matching in subscriptions."""
        all_events = []
        
        async def catch_all(event_name, data):
            all_events.append(event_name)
        
        # Subscribe to all events under /test
        event_bus.subscribe("/test/**", catch_all)
        
        # Publish various events
        await event_bus.publish("/test/level1", {})
        await event_bus.publish("/test/level1/level2", {})
        await event_bus.publish("/test/level1/level2/level3", {})
        await event_bus.publish("/other/event", {})  # Should not match
        
        await asyncio.sleep(0.1)
        
        assert len(all_events) == 3
        assert all(e.startswith("/test/") for e in all_events)
    
    @pytest.mark.asyncio
    async def test_event_history(self, event_bus):
        """Test event history tracking."""
        # Publish some events
        await event_bus.publish("/test/event1", {"order": 1})
        await event_bus.publish("/test/event2", {"order": 2})
        await event_bus.publish("/test/event3", {"order": 3})
        
        # Get history
        history = event_bus.get_event_history(namespace="/test")
        
        assert len(history) == 3
        assert history[0]["data"]["order"] == 1
        assert history[2]["data"]["order"] == 3
    
    @pytest.mark.asyncio
    async def test_concurrent_event_handling(self, event_bus):
        """Test handling multiple concurrent events."""
        processing_times = []
        
        async def slow_handler(event_name, data):
            start = asyncio.get_event_loop().time()
            await asyncio.sleep(0.1)  # Simulate processing
            processing_times.append(asyncio.get_event_loop().time() - start)
        
        event_bus.subscribe("/concurrent/*", slow_handler)
        
        # Publish multiple events concurrently
        tasks = [
            event_bus.publish(f"/concurrent/event{i}", {"id": i})
            for i in range(5)
        ]
        
        start_time = asyncio.get_event_loop().time()
        await asyncio.gather(*tasks)
        await asyncio.sleep(0.2)  # Wait for processing
        total_time = asyncio.get_event_loop().time() - start_time
        
        # If handled concurrently, total time should be ~0.1s, not 0.5s
        assert total_time < 0.3
        assert len(processing_times) == 5


class TestIntegration:
    """Integration tests for the complete plugin system."""
    
    @pytest.mark.asyncio
    async def test_plugin_event_integration(self):
        """Test plugins working with event bus."""
        manager = PluginManager()
        event_bus = EventBus()
        
        # Create and register plugin
        plugin = TestPlugin()
        manager.pm.register(plugin)
        
        # Connect plugin to event bus
        async def plugin_event_handler(event_name, data):
            results = manager.pm.hook.ksi_handle_event(
                event_name=event_name,
                data=data,
                context={"source": "event_bus"}
            )
            # Publish results back
            if results:
                await event_bus.publish(f"/response{event_name}", results[0])
        
        event_bus.subscribe("/test/*", plugin_event_handler)
        
        # Test ping/pong through event bus
        response_received = asyncio.Event()
        response_data = {}
        
        async def response_handler(event_name, data):
            response_data.update(data)
            response_received.set()
        
        event_bus.subscribe("/response/test/*", response_handler)
        
        # Send ping
        await event_bus.publish("/test/ping", {"message": "hello"})
        
        # Wait for response
        await response_received.wait()
        
        assert response_data["pong"] is True
        assert response_data["echo"] == "hello"
    
    @pytest.mark.asyncio
    async def test_multi_plugin_coordination(self):
        """Test multiple plugins coordinating through events."""
        manager = PluginManager()
        event_bus = EventBus()
        
        # Create producer plugin
        class ProducerPlugin(BasePlugin):
            @hookimpl
            def ksi_handle_event(self, event_name, data, context):
                if event_name == "produce:data":
                    return {"produced": data["count"] * 2}
        
        # Create consumer plugin  
        class ConsumerPlugin(BasePlugin):
            def __init__(self):
                super().__init__()
                self.consumed = []
            
            @hookimpl
            def ksi_handle_event(self, event_name, data, context):
                if event_name == "consume:data":
                    self.consumed.append(data["produced"])
                    return {"consumed": len(self.consumed)}
        
        producer = ProducerPlugin()
        consumer = ConsumerPlugin()
        
        manager.pm.register(producer)
        manager.pm.register(consumer)
        
        # Test coordination
        # 1. Produce data
        produce_result = manager.pm.hook.ksi_handle_event(
            event_name="produce:data",
            data={"count": 5},
            context={}
        )
        
        # 2. Consume produced data
        consume_result = manager.pm.hook.ksi_handle_event(
            event_name="consume:data",
            data=produce_result[0],
            context={}
        )
        
        assert produce_result[0]["produced"] == 10
        assert consume_result[0]["consumed"] == 1
        assert consumer.consumed[0] == 10


# Performance Tests
class TestPerformance:
    """Performance benchmarks for the plugin system."""
    
    @pytest.mark.asyncio
    async def test_event_routing_performance(self):
        """Test event routing meets <1ms latency target."""
        event_bus = EventBus()
        latencies = []
        
        async def measure_handler(event_name, data):
            latency = asyncio.get_event_loop().time() - data["timestamp"]
            latencies.append(latency * 1000)  # Convert to ms
        
        event_bus.subscribe("/perf/*", measure_handler)
        
        # Send many events
        for i in range(100):
            await event_bus.publish(f"/perf/test{i}", {
                "timestamp": asyncio.get_event_loop().time()
            })
        
        await asyncio.sleep(0.1)
        
        # Check latencies
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        
        assert avg_latency < 1.0  # Average under 1ms
        assert max_latency < 5.0  # Max under 5ms
        print(f"Event routing - Avg: {avg_latency:.2f}ms, Max: {max_latency:.2f}ms")
    
    def test_plugin_loading_performance(self):
        """Test plugin loading performance."""
        import time
        
        manager = PluginManager()
        
        # Create many plugins
        plugins = [TestPlugin() for _ in range(50)]
        
        start = time.time()
        for plugin in plugins:
            manager.pm.register(plugin)
        load_time = (time.time() - start) * 1000
        
        assert load_time < 100  # Should load 50 plugins in under 100ms
        print(f"Loaded 50 plugins in {load_time:.2f}ms")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])