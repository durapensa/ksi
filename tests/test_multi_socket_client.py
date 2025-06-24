#!/usr/bin/env python3
"""
Comprehensive tests for the real MultiSocketAsyncClient implementation.

Tests the actual multi-socket architecture from ksi_client.async_client:
1. admin.sock - health_check(), get_processes(), shutdown_daemon(), get_message_bus_stats()
2. agents.sock - register_agent(), get_agents(), spawn_agent()  
3. messaging.sock - publish_event(), send_message(), event handlers (persistent connection)
4. state.sock - set_agent_kv(), get_agent_kv()
5. completion.sock - create_completion() (main async completion feature)

Tests both MultiSocketAsyncClient (full-featured) and SimpleChatClient (convenience wrapper).
"""

import asyncio
import json
import pytest
from pathlib import Path
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from actual ksi_client library
from ksi_client import AsyncClient, SimpleChatClient, SocketConnection, PendingCompletion, CommandBuilder, ConnectionManager, ResponseHandler


class TestMultiSocketArchitecture:
    """Test the real multi-socket architecture from ksi_client.async_client"""
    
    def test_socket_connection_dataclass(self):
        """Test SocketConnection dataclass from actual implementation"""
        
        socket_path = Path("sockets/test.sock")
        connection = SocketConnection(
            socket_name="test",
            socket_path=socket_path
        )
        
        # Test SocketConnection fields match actual implementation
        assert connection.socket_name == "test"
        assert connection.socket_path == socket_path
        assert connection.reader is None
        assert connection.writer is None
        assert connection.connected is False
    
    def test_pending_completion_dataclass(self):
        """Test PendingCompletion dataclass from actual implementation"""
        
        future = asyncio.Future()
        completion = PendingCompletion(
            request_id="req_test123",
            future=future
        )
        
        # Test PendingCompletion fields match actual implementation
        assert completion.request_id == "req_test123"
        assert completion.future is future
        assert completion.timeout_task is None
    
    def test_multi_socket_async_client_structure(self):
        """Test MultiSocketAsyncClient class structure matches actual implementation"""
        
        client = AsyncClient(client_id="test_socket_structure")
        
        # Should have all socket connections from actual config
        expected_sockets = ["admin", "agents", "messaging", "state", "completion"]
        
        assert len(client.sockets) == 5
        for socket_name in expected_sockets:
            assert socket_name in client.sockets
            socket_conn = client.sockets[socket_name]
            assert isinstance(socket_conn, SocketConnection)
            assert socket_conn.socket_name == socket_name
            assert str(socket_conn.socket_path).endswith(f"{socket_name}.sock")
        
        # Test client attributes from actual implementation
        assert hasattr(client, 'timeout')
        assert hasattr(client, 'messaging_connected')
        assert hasattr(client, 'event_handlers')
        assert hasattr(client, 'pending_completions')
        assert hasattr(client, '_initialized')
        
        # Initial state should match implementation
        assert client._initialized is False
        assert client.messaging_connected is False
        assert isinstance(client.event_handlers, dict)
        assert isinstance(client.pending_completions, dict)
    
    def test_simple_chat_client_inheritance(self):
        """Test SimpleChatClient inherits from MultiSocketAsyncClient properly"""
        
        client = SimpleChatClient(client_id="test_inheritance")
        
        # Should inherit all MultiSocketAsyncClient functionality
        assert hasattr(client, 'sockets')
        assert len(client.sockets) == 5
        assert hasattr(client, 'initialize')
        assert hasattr(client, 'create_completion')
        assert hasattr(client, 'health_check')
        assert hasattr(client, 'set_agent_kv')
        assert hasattr(client, 'publish_event')
        
        # Should have SimpleChatClient-specific attributes
        assert hasattr(client, 'current_session_id')
        assert hasattr(client, 'send_prompt')
        assert client.current_session_id is None
    
    def test_client_id_generation(self):
        """Test client ID auto-generation and custom assignment"""
        
        # Auto-generated client ID
        client1 = AsyncClient()
        assert client1.client_id is not None
        assert client1.client_id.startswith("client_")
        
        # Custom client ID
        client2 = AsyncClient(client_id="my_custom_client_id")
        assert client2.client_id == "my_custom_client_id"
        
        # Different auto-generated IDs
        client3 = AsyncClient()
        assert client1.client_id != client3.client_id


class TestAdminSocketOperations:
    """Test admin.sock functionality from actual implementation"""
    
    @pytest.mark.asyncio
    async def test_health_check_integration(self):
        """Test health_check() method with real daemon"""
        
        try:
            client = AsyncClient(client_id="admin_health_test")
            await client.initialize()
            
            # Test actual health_check implementation
            health = await client.health_check()
            
            # Should return dict with health information
            assert isinstance(health, dict)
            
            await client.close()
            
        except ConnectionError:
            pytest.skip("Daemon not running - admin socket test skipped")
        except Exception as e:
            pytest.fail(f"Health check failed: {e}")
    
    @pytest.mark.asyncio
    async def test_get_processes_integration(self):
        """Test get_processes() method with real daemon"""
        
        try:
            client = AsyncClient(client_id="admin_processes_test")
            await client.initialize()
            
            # Test actual get_processes implementation
            processes = await client.get_processes()
            
            # Should return list of process information
            assert isinstance(processes, list)
            
            await client.close()
            
        except ConnectionError:
            pytest.skip("Daemon not running - get processes test skipped")
        except Exception as e:
            pytest.fail(f"Get processes failed: {e}")
    
    @pytest.mark.asyncio
    async def test_get_message_bus_stats_integration(self):
        """Test get_message_bus_stats() method with real daemon"""
        
        try:
            client = AsyncClient(client_id="admin_bus_stats_test")
            await client.initialize()
            
            # Test actual get_message_bus_stats implementation
            stats = await client.get_message_bus_stats()
            
            # Should return dict with message bus statistics
            assert isinstance(stats, dict)
            
            await client.close()
            
        except ConnectionError:
            pytest.skip("Daemon not running - message bus stats test skipped")
        except Exception as e:
            pytest.fail(f"Message bus stats failed: {e}")


class TestAgentsSocketOperations:
    """Test agents.sock functionality from actual implementation"""
    
    @pytest.mark.asyncio
    async def test_register_agent_integration(self):
        """Test register_agent() method with real daemon"""
        
        try:
            client = AsyncClient(client_id="agents_register_test")
            await client.initialize()
            
            # Test actual register_agent implementation
            agent_id = f"test_agent_{uuid.uuid4().hex[:8]}"
            success = await client.register_agent(
                agent_id=agent_id,
                role="test_role",
                capabilities=["testing", "validation"]
            )
            
            # Should return boolean success
            assert isinstance(success, bool)
            
            await client.close()
            
        except ConnectionError:
            pytest.skip("Daemon not running - register agent test skipped")
        except Exception as e:
            pytest.fail(f"Register agent failed: {e}")
    
    @pytest.mark.asyncio
    async def test_get_agents_integration(self):
        """Test get_agents() method with real daemon"""
        
        try:
            client = AsyncClient(client_id="agents_get_test")
            await client.initialize()
            
            # Test actual get_agents implementation
            agents = await client.get_agents()
            
            # Should return dict with agent information
            assert isinstance(agents, dict)
            
            await client.close()
            
        except ConnectionError:
            pytest.skip("Daemon not running - get agents test skipped")
        except Exception as e:
            pytest.fail(f"Get agents failed: {e}")
    
    @pytest.mark.asyncio
    async def test_spawn_agent_integration(self):
        """Test spawn_agent() method with real daemon"""
        
        try:
            client = AsyncClient(client_id="agents_spawn_test")
            await client.initialize()
            
            # Test actual spawn_agent implementation
            agent_config = {
                "role": "test_spawned_agent",
                "capabilities": ["testing"]
            }
            
            process_id = await client.spawn_agent("test", agent_config)
            
            # Should return string process ID
            assert isinstance(process_id, str)
            assert len(process_id) > 0
            
            await client.close()
            
        except ConnectionError:
            pytest.skip("Daemon not running - spawn agent test skipped")
        except Exception as e:
            pytest.fail(f"Spawn agent failed: {e}")


class TestStateSocketOperations:
    """Test state.sock functionality from actual implementation"""
    
    @pytest.mark.asyncio
    async def test_agent_kv_operations_integration(self):
        """Test set_agent_kv() and get_agent_kv() methods with real daemon"""
        
        try:
            client = AsyncClient(client_id="state_kv_test")
            await client.initialize()
            
            agent_id = f"test_agent_{uuid.uuid4().hex[:8]}"
            test_key = "test_key"
            test_value = {"data": "test_data", "number": 42, "list": [1, 2, 3]}
            
            # Test actual set_agent_kv implementation
            success = await client.set_agent_kv(agent_id, test_key, test_value)
            assert success is True
            
            # Test actual get_agent_kv implementation
            retrieved_value = await client.get_agent_kv(agent_id, test_key)
            assert retrieved_value == test_value
            
            # Test getting non-existent key
            missing_value = await client.get_agent_kv(agent_id, "nonexistent_key")
            assert missing_value is None
            
            await client.close()
            
        except ConnectionError:
            pytest.skip("Daemon not running - state KV test skipped")
        except Exception as e:
            pytest.fail(f"Agent KV operations failed: {e}")
    
    @pytest.mark.asyncio
    async def test_state_isolation_integration(self):
        """Test that state is properly isolated between agents"""
        
        try:
            client = AsyncClient(client_id="state_isolation_test")
            await client.initialize()
            
            agent1_id = f"agent1_{uuid.uuid4().hex[:8]}"
            agent2_id = f"agent2_{uuid.uuid4().hex[:8]}"
            key = "shared_key"
            value1 = "agent1_value"
            value2 = "agent2_value"
            
            # Set different values for same key on different agents
            await client.set_agent_kv(agent1_id, key, value1)
            await client.set_agent_kv(agent2_id, key, value2)
            
            # Verify state isolation
            retrieved1 = await client.get_agent_kv(agent1_id, key)
            retrieved2 = await client.get_agent_kv(agent2_id, key)
            
            assert retrieved1 == value1
            assert retrieved2 == value2
            assert retrieved1 != retrieved2
            
            await client.close()
            
        except ConnectionError:
            pytest.skip("Daemon not running - state isolation test skipped")
        except Exception as e:
            pytest.fail(f"State isolation test failed: {e}")


class TestMessagingSocketOperations:
    """Test messaging.sock functionality from actual implementation"""
    
    @pytest.mark.asyncio
    async def test_publish_event_integration(self):
        """Test publish_event() method with real daemon"""
        
        try:
            client = AsyncClient(client_id="messaging_publish_test")
            await client.initialize()
            
            # Test actual publish_event implementation
            event_type = "TEST_EVENT"
            payload = {
                "message": "Test event payload",
                "timestamp": "2024-01-01T00:00:00Z",
                "data": {"key": "value"}
            }
            
            success = await client.publish_event(event_type, payload)
            assert success is True
            
            await client.close()
            
        except ConnectionError:
            pytest.skip("Daemon not running - publish event test skipped")
        except Exception as e:
            pytest.fail(f"Event publishing failed: {e}")
    
    @pytest.mark.asyncio
    async def test_send_message_integration(self):
        """Test send_message() method with real daemon"""
        
        try:
            client = AsyncClient(client_id="messaging_send_test")
            await client.initialize()
            
            # Test actual send_message implementation
            to_agent = "target_agent"
            content = "Test direct message content"
            metadata = {"priority": "high", "type": "test"}
            
            success = await client.send_message(to_agent, content, metadata)
            assert success is True
            
            await client.close()
            
        except ConnectionError:
            pytest.skip("Daemon not running - send message test skipped")
        except Exception as e:
            pytest.fail(f"Direct messaging failed: {e}")
    
    def test_event_handler_management(self):
        """Test event handler registration and removal"""
        
        client = AsyncClient(client_id="event_handler_test")
        
        # Test adding event handlers
        test_events = []
        
        def sync_handler(event):
            test_events.append(event)
        
        async def async_handler(event):
            test_events.append({"async": True, "event": event})
        
        # Test actual add_event_handler implementation
        client.add_event_handler("TEST_EVENT", sync_handler)
        client.add_event_handler("ASYNC_TEST_EVENT", async_handler)
        
        # Verify handlers are registered
        assert "TEST_EVENT" in client.event_handlers
        assert "ASYNC_TEST_EVENT" in client.event_handlers
        assert len(client.event_handlers["TEST_EVENT"]) == 1
        assert len(client.event_handlers["ASYNC_TEST_EVENT"]) == 1
        
        # Test actual remove_event_handler implementation
        client.remove_event_handler("TEST_EVENT", sync_handler)
        assert len(client.event_handlers["TEST_EVENT"]) == 0


class TestCompletionSocketOperations:
    """Test completion.sock functionality from actual implementation"""
    
    @pytest.mark.asyncio
    async def test_create_completion_integration(self):
        """Test create_completion() method with real daemon"""
        
        try:
            client = AsyncClient(client_id="completion_integration_test")
            await client.initialize()
            
            # Test actual create_completion implementation
            response = await client.create_completion(
                prompt="What is 2+2? Answer in one word.",
                model="sonnet",
                timeout=30
            )
            
            # Should return string response
            assert isinstance(response, str)
            assert len(response) > 0
            
            await client.close()
            
        except ConnectionError:
            pytest.skip("Daemon not running - completion integration test skipped")
        except Exception as e:
            pytest.fail(f"Create completion failed: {e}")
    
    @pytest.mark.asyncio
    async def test_create_completion_with_session_integration(self):
        """Test create_completion() with session continuity"""
        
        try:
            client = AsyncClient(client_id="completion_session_test")
            await client.initialize()
            
            session_id = f"session_{uuid.uuid4().hex[:8]}"
            
            # First completion
            response1 = await client.create_completion(
                prompt="Remember this number: 99",
                session_id=session_id,
                timeout=30
            )
            
            # Second completion with same session
            response2 = await client.create_completion(
                prompt="What number did I ask you to remember?",
                session_id=session_id,
                timeout=30
            )
            
            assert isinstance(response1, str)
            assert isinstance(response2, str)
            assert "99" in response2
            
            await client.close()
            
        except ConnectionError:
            pytest.skip("Daemon not running - completion session test skipped")
        except Exception as e:
            pytest.fail(f"Completion with session failed: {e}")
    
    @pytest.mark.asyncio
    async def test_create_completion_concurrent(self):
        """Test multiple concurrent create_completion() calls"""
        
        try:
            client = AsyncClient(client_id="completion_concurrent_test")
            await client.initialize()
            
            # Create multiple completion tasks
            tasks = [
                client.create_completion(f"Count to {i+1}", timeout=30)
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
            pytest.fail(f"Concurrent completions failed: {e}")


class TestClientLifecycleManagement:
    """Test client initialization, cleanup, and lifecycle from actual implementation"""
    
    @pytest.mark.asyncio
    async def test_client_initialization_sequence(self):
        """Test proper client initialization sequence"""
        
        try:
            client = AsyncClient(client_id="lifecycle_init_test")
            
            # Should not be initialized initially
            assert client._initialized is False
            assert client.messaging_connected is False
            
            # Test actual initialize() implementation
            success = await client.initialize()
            assert success is True
            assert client._initialized is True
            assert client.messaging_connected is True
            
            # Should have active event listener
            assert client._listen_task is not None
            assert not client._listen_task.done()
            
            await client.close()
            
        except ConnectionError:
            pytest.skip("Daemon not running - initialization test skipped")
        except Exception as e:
            pytest.fail(f"Client initialization failed: {e}")
    
    @pytest.mark.asyncio
    async def test_client_cleanup_sequence(self):
        """Test proper client cleanup sequence"""
        
        try:
            client = AsyncClient(client_id="lifecycle_cleanup_test")
            await client.initialize()
            
            # Should be initialized
            assert client._initialized is True
            assert client.messaging_connected is True
            
            # Test actual close() implementation
            await client.close()
            
            # Should be cleaned up
            assert client._initialized is False
            assert client.messaging_connected is False
            assert len(client.pending_completions) == 0
            
            # Event listener should be cancelled
            if client._listen_task:
                assert client._listen_task.done() or client._listen_task.cancelled()
            
        except ConnectionError:
            pytest.skip("Daemon not running - cleanup test skipped")
        except Exception as e:
            pytest.fail(f"Client cleanup failed: {e}")
    
    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test AsyncClient as async context manager"""
        
        try:
            async with AsyncClient(client_id="context_manager_test") as client:
                # Should be initialized
                assert client._initialized is True
                
                # Should be able to use client
                health = await client.health_check()
                assert isinstance(health, dict)
            
            # Should be cleaned up after context exit
            assert client._initialized is False
            assert client.messaging_connected is False
            
        except ConnectionError:
            pytest.skip("Daemon not running - context manager test skipped")
        except Exception as e:
            pytest.fail(f"Context manager usage failed: {e}")


class TestUtilityClasses:
    """Test utility classes from ksi_client.utils"""
    
    def test_command_builder_functionality(self):
        """Test CommandBuilder utility functions"""
        
        # Test basic command building
        command = CommandBuilder.build_command("TEST_COMMAND", {"key": "value"})
        
        assert command["command"] == "TEST_COMMAND"
        assert command["parameters"]["key"] == "value"
        
        # Test command with metadata
        command_with_meta = CommandBuilder.build_command(
            "TEST_COMMAND", 
            {"param": "value"}, 
            {"timestamp": "2024-01-01T00:00:00Z"}
        )
        
        assert command_with_meta["command"] == "TEST_COMMAND"
        assert command_with_meta["parameters"]["param"] == "value"
    
    def test_response_handler_functionality(self):
        """Test ResponseHandler utility functions"""
        
        # Test success response
        success_response = {
            "status": "success",
            "command": "TEST",
            "result": {"data": "test_value"}
        }
        
        assert ResponseHandler.check_success(success_response) is True
        assert ResponseHandler.get_result_data(success_response) == {"data": "test_value"}
        
        # Test error response
        error_response = {
            "status": "error",
            "command": "TEST",
            "error": {"code": "TEST_ERROR", "message": "Test error message"}
        }
        
        assert ResponseHandler.check_success(error_response) is False
        assert ResponseHandler.get_error_message(error_response) == "Test error message"


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases from actual implementation"""
    
    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """Test graceful handling when daemon is not available"""
        
        client = AsyncClient(client_id="error_handling_test")
        
        # Should handle connection error gracefully
        try:
            success = await client.initialize()
            if success:
                # Daemon is running, clean up
                await client.close()
        except ConnectionError:
            # Expected when daemon not running
            pass
        except Exception as e:
            pytest.fail(f"Unexpected error type: {e}")
    
    def test_invalid_socket_usage(self):
        """Test error handling for invalid socket operations"""
        
        client = AsyncClient(client_id="invalid_socket_test")
        
        # Should raise ValueError for invalid socket name
        with pytest.raises(ValueError, match="Invalid socket name"):
            asyncio.run(client.send_command("invalid_socket", "TEST_COMMAND"))
        
        # Should raise ValueError for messaging socket direct commands
        with pytest.raises(ValueError, match="persistent messaging methods"):
            asyncio.run(client.send_command("messaging", "TEST_COMMAND"))
    
    def test_socket_path_configuration(self):
        """Test socket path configuration from actual implementation"""
        
        client = AsyncClient(client_id="socket_path_test")
        
        # Should use correct socket paths
        expected_paths = {
            "admin": "sockets/admin.sock",
            "agents": "sockets/agents.sock", 
            "messaging": "sockets/messaging.sock",
            "state": "sockets/state.sock",
            "completion": "sockets/completion.sock"
        }
        
        for socket_name, expected_path in expected_paths.items():
            socket_conn = client.sockets[socket_name]
            assert str(socket_conn.socket_path).endswith(expected_path)


# Integration test runner for development
async def run_integration_tests():
    """Run integration tests that require a running daemon"""
    
    print("Running MultiSocketAsyncClient integration tests...")
    print("Note: These tests require ksi-daemon.py to be running")
    
    test_classes = [
        TestMultiSocketArchitecture(),
        TestAdminSocketOperations(),
        TestStateSocketOperations(),
        TestMessagingSocketOperations(),
        TestCompletionSocketOperations(),
        TestClientLifecycleManagement(),
        TestUtilityClasses(),
        TestErrorHandlingAndEdgeCases()
    ]
    
    # Run unit tests (no daemon required)
    unit_test_methods = [
        ("Architecture structure", lambda: test_classes[0].test_multi_socket_async_client_structure()),
        ("Socket connection dataclass", lambda: test_classes[0].test_socket_connection_dataclass()),
        ("Client ID generation", lambda: test_classes[0].test_client_id_generation()),
        ("Event handler management", lambda: test_classes[3].test_event_handler_management()),
        ("CommandBuilder functionality", lambda: test_classes[6].test_command_builder_functionality()),
        ("ResponseHandler functionality", lambda: test_classes[6].test_response_handler_functionality()),
        ("Invalid socket usage", lambda: test_classes[7].test_invalid_socket_usage()),
        ("Socket path configuration", lambda: test_classes[7].test_socket_path_configuration()),
    ]
    
    results = {}
    
    print("\n=== Unit Tests (no daemon required) ===")
    for test_name, test_func in unit_test_methods:
        try:
            test_func()
            print(f"✓ {test_name}")
            results[test_name] = True
        except Exception as e:
            print(f"✗ {test_name}: {e}")
            results[test_name] = False
    
    # Try integration tests that require daemon
    print("\n=== Integration Tests (require daemon) ===")
    integration_test_methods = [
        ("Admin health check", test_classes[1].test_health_check_integration),
        ("State KV operations", test_classes[2].test_agent_kv_operations_integration),
        ("Messaging publish event", test_classes[3].test_publish_event_integration),
        ("Completion integration", test_classes[4].test_create_completion_integration),
        ("Client lifecycle", test_classes[5].test_client_initialization_sequence),
    ]
    
    for test_name, test_method in integration_test_methods:
        try:
            await test_method()
            print(f"✓ {test_name}")
            results[test_name] = True
        except Exception as e:
            print(f"✗ {test_name}: {e}")
            results[test_name] = False
    
    # Summary
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed < total:
        print("Note: Integration tests may fail if daemon is not running")
    
    return results


if __name__ == "__main__":
    # Run integration tests if called directly
    asyncio.run(run_integration_tests())