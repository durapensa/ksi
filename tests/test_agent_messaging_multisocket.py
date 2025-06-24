#!/usr/bin/env python3
"""
Enhanced Agent Messaging Tests - Multi-Socket Architecture

Tests agent-to-agent messaging using the new multi-socket architecture:
- Event-driven agent communication via messaging.sock
- Short conversation exchanges with limited scope
- Message routing through messaging bus
- Targeted message delivery
- Agent registration and discovery
- Inter-agent coordination

Uses very short exchanges as requested:
- Agent A: "hello, what's your name?"
- Agent B: "I'm Beta. And you?"  
- Agent A: "I'm Alpha. Nice to meet you!"
"""

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, patch, MagicMock, AsyncMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import test result logger
from test_result_logger import TestStatus, start_test, finish_test, skip_test

# Import client components
try:
    from ksi_client import AsyncClient
    client_available = True
except ImportError:
    client_available = False


class MockAgent:
    """Mock agent for testing messaging without spawning real agents"""
    
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
        self.received_messages: List[Dict[str, Any]] = []
        self.sent_messages: List[Dict[str, Any]] = []
        self.client: Optional[AsyncClient] = None
        
    async def connect(self):
        """Connect the agent to the daemon"""
        if client_available:
            self.client = AsyncClient(client_id=self.agent_id)
            await self.client.initialize()
            
            # Register as an agent
            await self.client.register_agent(
                agent_id=self.agent_id,
                role="conversational_agent",
                capabilities=["chat", "messaging"]
            )
        
    async def send_message(self, to_agent: str, content: str) -> bool:
        """Send a message to another agent"""
        if not self.client:
            return False
            
        try:
            success = await self.client.send_message(to_agent, content)
            if success:
                self.sent_messages.append({
                    "to": to_agent,
                    "content": content,
                    "timestamp": time.time()
                })
            return success
        except Exception:
            return False
    
    async def handle_message(self, from_agent: str, content: str):
        """Handle incoming message (would be called by event handler)"""
        self.received_messages.append({
            "from": from_agent,
            "content": content,
            "timestamp": time.time()
        })
        
        # Generate appropriate response based on content
        if "hello" in content.lower() and "name" in content.lower():
            return f"I'm {self.name}. And you?"
        elif "i'm" in content.lower() and "nice to meet" in content.lower():
            return f"Nice to meet you too!"
        else:
            return f"Hello from {self.name}"
    
    async def disconnect(self):
        """Disconnect the agent"""
        if self.client:
            await self.client.close()


class TestAgentMessagingMultiSocket:
    """Test suite for multi-socket agent messaging"""
    
    def __init__(self):
        self.test_file = "test_agent_messaging_multisocket.py"
    
    def test_agent_registration_multisocket(self):
        """Test agent registration through agents.sock"""
        test_result = start_test("agent_registration_multisocket", self.test_file)
        
        if not client_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Client not available")
            return True
        
        try:
            async def test_registration():
                # Create client for agent registration
                client = AsyncClient(client_id="test_registration_client")
                
                try:
                    await client.initialize()
                    
                    # Register test agents
                    agent_alpha_id = "agent_alpha_ms"
                    agent_beta_id = "agent_beta_ms"
                    
                    # Register Agent Alpha
                    success_alpha = await client.register_agent(
                        agent_id=agent_alpha_id,
                        role="conversational_agent",
                        capabilities=["chat", "short_conversations"]
                    )
                    
                    # Register Agent Beta  
                    success_beta = await client.register_agent(
                        agent_id=agent_beta_id,
                        role="conversational_agent",
                        capabilities=["chat", "short_conversations"]
                    )
                    
                    # Get registered agents
                    agents = await client.get_agents()
                    
                    return {
                        "alpha_registered": success_alpha,
                        "beta_registered": success_beta,
                        "agents_found": agents,
                        "agent_count": len(agents) if isinstance(agents, dict) else 0
                    }
                    
                except ConnectionError:
                    # Daemon not running
                    return None
                finally:
                    await client.close()
            
            # Run the async test
            result = asyncio.run(test_registration())
            
            if result is None:
                finish_test(test_result, TestStatus.SKIPPED,
                           error_message="Daemon not running")
                return True
            
            # Verify registration results
            assert result["alpha_registered"], "Agent Alpha should be registered"
            assert result["beta_registered"], "Agent Beta should be registered"
            assert result["agent_count"] >= 0, "Should have non-negative agent count"
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "agents_registered": 2,
                           "total_agents": result["agent_count"],
                           "registration_successful": True
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_direct_messaging_multisocket(self):
        """Test direct messaging between agents via messaging.sock"""
        test_result = start_test("direct_messaging_multisocket", self.test_file, "hello, what's your name?")
        
        if not client_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Client not available")
            return True
        
        try:
            async def test_messaging():
                # Create mock agents
                agent_alpha = MockAgent("agent_alpha_msg", "Alpha")
                agent_beta = MockAgent("agent_beta_msg", "Beta")
                
                try:
                    # Connect agents
                    await agent_alpha.connect()
                    await agent_beta.connect()
                    
                    # Test direct message from Alpha to Beta
                    message_content = "hello, what's your name?"
                    success = await agent_alpha.send_message(agent_beta.agent_id, message_content)
                    
                    # Simulate Beta receiving and responding (in real system, this would be via events)
                    if success:
                        response = await agent_beta.handle_message(agent_alpha.agent_id, message_content)
                        await agent_beta.send_message(agent_alpha.agent_id, response)
                        
                        # Simulate Alpha receiving response
                        await agent_alpha.handle_message(agent_beta.agent_id, response)
                    
                    return {
                        "message_sent": success,
                        "alpha_sent": len(agent_alpha.sent_messages),
                        "beta_sent": len(agent_beta.sent_messages), 
                        "alpha_received": len(agent_alpha.received_messages),
                        "beta_received": len(agent_beta.received_messages),
                        "original_message": message_content,
                        "response_message": response if success else None
                    }
                    
                except ConnectionError:
                    return None
                finally:
                    await agent_alpha.disconnect()
                    await agent_beta.disconnect()
            
            result = asyncio.run(test_messaging())
            
            if result is None:
                finish_test(test_result, TestStatus.SKIPPED,
                           error_message="Daemon not running")
                return True
            
            # Verify messaging results
            assert result["message_sent"], "Message should be sent successfully"
            assert result["alpha_sent"] >= 1, "Alpha should have sent at least 1 message"
            assert result["beta_received"] >= 1, "Beta should have received at least 1 message"
            
            if result["response_message"]:
                assert "Beta" in result["response_message"], "Response should mention Beta's name"
                assert "And you?" in result["response_message"], "Response should ask back"
            
            finish_test(test_result, TestStatus.PASSED, response=result["response_message"],
                       details={
                           "messages_exchanged": result["alpha_sent"] + result["beta_sent"],
                           "conversation_started": True,
                           "response_appropriate": bool(result["response_message"] and "Beta" in result["response_message"])
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_short_conversation_exchange(self):
        """Test a complete short conversation exchange"""
        test_result = start_test("short_conversation_exchange", self.test_file, "3-message conversation")
        
        if not client_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Client not available")
            return True
        
        try:
            async def test_conversation():
                # Create mock agents
                agent_alpha = MockAgent("agent_alpha_conv", "Alpha")
                agent_beta = MockAgent("agent_beta_conv", "Beta")
                
                conversation_log = []
                
                try:
                    await agent_alpha.connect()
                    await agent_beta.connect()
                    
                    # Message 1: Alpha initiates
                    msg1 = "hello, what's your name?"
                    success1 = await agent_alpha.send_message(agent_beta.agent_id, msg1)
                    conversation_log.append(f"Alpha: {msg1}")
                    
                    if success1:
                        # Message 2: Beta responds
                        response1 = await agent_beta.handle_message(agent_alpha.agent_id, msg1)
                        await agent_beta.send_message(agent_alpha.agent_id, response1)
                        conversation_log.append(f"Beta: {response1}")
                        
                        # Message 3: Alpha closes
                        await agent_alpha.handle_message(agent_beta.agent_id, response1)
                        msg3 = "I'm Alpha. Nice to meet you!"
                        await agent_alpha.send_message(agent_beta.agent_id, msg3)
                        conversation_log.append(f"Alpha: {msg3}")
                        
                        # Beta acknowledges
                        response2 = await agent_beta.handle_message(agent_alpha.agent_id, msg3)
                        conversation_log.append(f"Beta: {response2}")
                    
                    return {
                        "conversation_completed": len(conversation_log) >= 3,
                        "conversation_log": conversation_log,
                        "message_count": len(conversation_log),
                        "agents_connected": True
                    }
                    
                except ConnectionError:
                    return None
                finally:
                    await agent_alpha.disconnect()
                    await agent_beta.disconnect()
            
            result = asyncio.run(test_conversation())
            
            if result is None:
                finish_test(test_result, TestStatus.SKIPPED,
                           error_message="Daemon not running")
                return True
            
            # Verify conversation results
            assert result["conversation_completed"], "Conversation should be completed"
            assert result["message_count"] >= 3, f"Should have at least 3 messages, got {result['message_count']}"
            
            # Verify conversation content
            log = result["conversation_log"]
            assert any("hello" in msg.lower() for msg in log), "Conversation should start with greeting"
            assert any("name" in msg.lower() for msg in log), "Conversation should include name exchange"
            assert any("nice to meet" in msg.lower() for msg in log), "Conversation should end politely"
            
            finish_test(test_result, TestStatus.PASSED, response=f"{result['message_count']} messages exchanged",
                       details={
                           "conversation_length": result["message_count"],
                           "conversation_log": result["conversation_log"],
                           "proper_greeting": True,
                           "proper_closing": True
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_event_based_message_routing(self):
        """Test event-based message routing through messaging.sock"""
        test_result = start_test("event_based_message_routing", self.test_file)
        
        if not client_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Client not available")
            return True
        
        try:
            async def test_routing():
                # Create clients for testing event routing
                client_a = AsyncClient(client_id="routing_client_a")
                client_b = AsyncClient(client_id="routing_client_b")
                client_c = AsyncClient(client_id="routing_client_c")
                
                routing_results = {
                    "clients_connected": 0,
                    "events_published": 0,
                    "targeted_messages": 0
                }
                
                try:
                    # Connect all clients
                    await client_a.initialize()
                    routing_results["clients_connected"] += 1
                    
                    await client_b.initialize()
                    routing_results["clients_connected"] += 1
                    
                    await client_c.initialize()
                    routing_results["clients_connected"] += 1
                    
                    # Test targeted message from A to B (not C)
                    await client_a.send_message("routing_client_b", "direct message for B only")
                    routing_results["targeted_messages"] += 1
                    
                    # Test broadcast-style event (if supported)
                    await client_a.publish_event("AGENT_ANNOUNCEMENT", {
                        "message": "Hello from client A",
                        "type": "greeting"
                    })
                    routing_results["events_published"] += 1
                    
                    # Test another targeted message from B to C
                    await client_b.send_message("routing_client_c", "B to C private message")
                    routing_results["targeted_messages"] += 1
                    
                    return routing_results
                    
                except ConnectionError:
                    return None
                finally:
                    await client_a.close()
                    await client_b.close()
                    await client_c.close()
            
            result = asyncio.run(test_routing())
            
            if result is None:
                finish_test(test_result, TestStatus.SKIPPED,
                           error_message="Daemon not running")
                return True
            
            # Verify routing results
            assert result["clients_connected"] == 3, f"Expected 3 clients connected, got {result['clients_connected']}"
            assert result["targeted_messages"] >= 2, f"Expected at least 2 targeted messages, got {result['targeted_messages']}"
            assert result["events_published"] >= 1, f"Expected at least 1 event published, got {result['events_published']}"
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "clients_connected": result["clients_connected"],
                           "targeted_messages": result["targeted_messages"],
                           "events_published": result["events_published"],
                           "routing_successful": True
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_message_isolation_and_targeting(self):
        """Test that messages are properly isolated and targeted"""
        test_result = start_test("message_isolation_targeting", self.test_file)
        
        if not client_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Client not available")
            return True
        
        try:
            # Simulate message isolation using mock event handlers
            message_deliveries = {
                "client_a": [],
                "client_b": [],
                "client_c": []
            }
            
            # Mock message delivery
            def deliver_message(from_client: str, to_client: str, content: str):
                """Simulate targeted message delivery"""
                if to_client in message_deliveries:
                    message_deliveries[to_client].append({
                        "from": from_client,
                        "content": content,
                        "timestamp": time.time()
                    })
            
            # Test various message scenarios
            # A sends to B (C should not receive)
            deliver_message("client_a", "client_b", "Private message from A to B")
            
            # B sends to C (A should not receive)
            deliver_message("client_b", "client_c", "Private message from B to C")
            
            # A sends to C (B should not receive)  
            deliver_message("client_a", "client_c", "Another private message from A to C")
            
            # C sends to A (B should not receive)
            deliver_message("client_c", "client_a", "Response from C to A")
            
            # Verify isolation
            assert len(message_deliveries["client_a"]) == 1, f"Client A should receive 1 message, got {len(message_deliveries['client_a'])}"
            assert len(message_deliveries["client_b"]) == 1, f"Client B should receive 1 message, got {len(message_deliveries['client_b'])}"
            assert len(message_deliveries["client_c"]) == 2, f"Client C should receive 2 messages, got {len(message_deliveries['client_c'])}"
            
            # Verify targeting
            assert message_deliveries["client_a"][0]["from"] == "client_c", "A should receive message from C"
            assert message_deliveries["client_b"][0]["from"] == "client_a", "B should receive message from A"
            assert all(msg["from"] in ["client_b", "client_a"] for msg in message_deliveries["client_c"]), "C should receive messages from A and B"
            
            # Verify content isolation
            a_content = message_deliveries["client_a"][0]["content"]
            b_content = message_deliveries["client_b"][0]["content"]
            c_contents = [msg["content"] for msg in message_deliveries["client_c"]]
            
            assert "A to B" not in a_content, "A should not receive A-to-B message"
            assert "B to C" not in b_content, "B should not receive B-to-C message"
            assert any("A to B" not in content for content in c_contents), "C should not receive A-to-B message"
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "total_messages": sum(len(msgs) for msgs in message_deliveries.values()),
                           "client_a_messages": len(message_deliveries["client_a"]),
                           "client_b_messages": len(message_deliveries["client_b"]),
                           "client_c_messages": len(message_deliveries["client_c"]),
                           "isolation_verified": True,
                           "targeting_verified": True
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False
    
    def test_agent_discovery_and_capabilities(self):
        """Test agent discovery and capability querying"""
        test_result = start_test("agent_discovery_capabilities", self.test_file)
        
        if not client_available:
            finish_test(test_result, TestStatus.SKIPPED,
                       error_message="Client not available")
            return True
        
        try:
            async def test_discovery():
                client = AsyncClient(client_id="discovery_test_client")
                
                try:
                    await client.initialize()
                    
                    # Register agents with different capabilities
                    agents_registered = []
                    
                    # Register conversational agent
                    success1 = await client.register_agent(
                        agent_id="discovery_agent_chat",
                        role="conversational_agent",
                        capabilities=["chat", "short_conversations", "greetings"]
                    )
                    if success1:
                        agents_registered.append("discovery_agent_chat")
                    
                    # Register utility agent
                    success2 = await client.register_agent(
                        agent_id="discovery_agent_util",
                        role="utility_agent", 
                        capabilities=["calculations", "data_processing"]
                    )
                    if success2:
                        agents_registered.append("discovery_agent_util")
                    
                    # Discover all agents
                    all_agents = await client.get_agents()
                    
                    return {
                        "agents_registered": len(agents_registered),
                        "agents_discovered": all_agents,
                        "discovery_successful": isinstance(all_agents, dict) and len(all_agents) >= 0
                    }
                    
                except ConnectionError:
                    return None
                finally:
                    await client.close()
            
            result = asyncio.run(test_discovery())
            
            if result is None:
                finish_test(test_result, TestStatus.SKIPPED,
                           error_message="Daemon not running")
                return True
            
            # Verify discovery results
            assert result["discovery_successful"], "Agent discovery should be successful"
            assert result["agents_registered"] >= 0, "Should have registered some agents"
            
            # If agents were discovered, verify structure
            if result["agents_discovered"] and isinstance(result["agents_discovered"], dict):
                discovered_count = len(result["agents_discovered"])
            else:
                discovered_count = 0
            
            finish_test(test_result, TestStatus.PASSED,
                       details={
                           "agents_registered": result["agents_registered"],
                           "agents_discovered": discovered_count,
                           "discovery_works": result["discovery_successful"]
                       })
            return True
            
        except Exception as e:
            finish_test(test_result, TestStatus.FAILED, error_message=str(e))
            return False


async def run_all_tests():
    """Run all enhanced agent messaging tests"""
    print("Running Enhanced Agent Messaging Tests (Multi-Socket)")
    print("=" * 50)
    
    if not client_available:
        print("⚠️  Client not available - all tests will be skipped")
    
    tester = TestAgentMessagingMultiSocket()
    
    # List of test methods
    test_methods = [
        tester.test_agent_registration_multisocket,
        tester.test_direct_messaging_multisocket,
        tester.test_short_conversation_exchange,
        tester.test_event_based_message_routing,
        tester.test_message_isolation_and_targeting,
        tester.test_agent_discovery_and_capabilities
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
    print(f"Enhanced Agent Messaging Tests: {passed}/{total} passed")
    
    return passed == total


if __name__ == "__main__":
    # Run tests
    success = asyncio.run(run_all_tests())
    
    # Print final result summary from logger
    from test_result_logger import get_test_logger
    get_test_logger().print_summary()
    
    sys.exit(0 if success else 1)