#!/usr/bin/env python3
"""
Test agent-to-agent messaging functionality
Verifies that agents can communicate via SEND_MESSAGE command
"""

import json
import socket
import time
import sys
import asyncio

def send_daemon_command(command):
    """Send command to daemon and get response"""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect('sockets/claude_daemon.sock')
        
        sock.sendall((json.dumps(command) + '\n').encode())
        
        response_data = b''
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response_data += chunk
            if b'\n' in response_data:
                break
        
        sock.close()
        return json.loads(response_data.decode().strip())
        
    except Exception as e:
        print(f"❌ Failed to send command: {e}")
        return None

def spawn_test_agents():
    """Spawn two test agents for messaging"""
    print("1. Spawning test agents...")
    
    # Spawn first agent - a conversationalist
    agent1_resp = send_daemon_command({
        "command": "SPAWN_AGENT",
        "parameters": {
            "task": "You are Agent Alpha. Engage in conversation and respond to messages from other agents.",
            "agent_id": "agent_alpha",
            "profile_name": "conversationalist"
        }
    })
    
    if not agent1_resp or agent1_resp.get('status') != 'success':
        print(f"❌ Failed to spawn agent_alpha: {agent1_resp}")
        return None, None
        
    print(f"✅ Spawned agent_alpha")
    
    # Spawn second agent - another conversationalist
    agent2_resp = send_daemon_command({
        "command": "SPAWN_AGENT",
        "parameters": {
            "task": "You are Agent Beta. Engage in conversation and respond to messages from other agents.",
            "agent_id": "agent_beta",
            "profile_name": "conversationalist"
        }
    })
    
    if not agent2_resp or agent2_resp.get('status') != 'success':
        print(f"❌ Failed to spawn agent_beta: {agent2_resp}")
        return "agent_alpha", None
        
    print(f"✅ Spawned agent_beta")
    
    return "agent_alpha", "agent_beta"

def test_direct_messaging(agent1_id, agent2_id):
    """Test direct message between two agents"""
    print("\n2. Testing direct messaging...")
    
    # Send message from agent1 to agent2
    msg_resp = send_daemon_command({
        "command": "SEND_MESSAGE",
        "parameters": {
            "from_agent": agent1_id,
            "to_agent": agent2_id,
            "message_type": "GREETING",
            "content": "Hello Agent Beta! This is Agent Alpha. How are you today?",
            "metadata": {
                "conversation_id": "test_001",
                "timestamp": time.time()
            }
        }
    })
    
    if not msg_resp or msg_resp.get('status') != 'success':
        print(f"❌ Failed to send direct message: {msg_resp}")
        return False
        
    result = msg_resp.get('result', {})
    print(f"✅ Direct message sent: {result.get('delivery')} delivery")
    print(f"   From: {result.get('from')} → To: {result.get('to')}")
    print(f"   Status: {result.get('status')}")
    
    return True

def test_broadcast_messaging(sender_id):
    """Test broadcast message to all agents"""
    print("\n3. Testing broadcast messaging...")
    
    # Broadcast from one agent to all others
    broadcast_resp = send_daemon_command({
        "command": "SEND_MESSAGE",
        "parameters": {
            "from_agent": sender_id,
            "content": "Attention all agents: This is a broadcast test message!",
            "message_type": "ANNOUNCEMENT"
        }
    })
    
    if not broadcast_resp or broadcast_resp.get('status') != 'success':
        print(f"❌ Failed to broadcast message: {broadcast_resp}")
        return False
        
    result = broadcast_resp.get('result', {})
    print(f"✅ Broadcast sent: delivered to {result.get('count')} agents")
    print(f"   Recipients: {', '.join(result.get('recipients', []))}")
    
    return True

def test_pubsub_messaging(agent1_id, agent2_id):
    """Test pub/sub messaging via event types"""
    print("\n4. Testing pub/sub messaging...")
    
    # Note: In-process agents might already be connected to message bus
    # Try subscribing directly, but handle the case where connection is needed
    subscribe_resp = send_daemon_command({
        "command": "SUBSCRIBE",
        "parameters": {
            "agent_id": agent2_id,
            "event_types": ["COLLABORATION_REQUEST", "TASK_ASSIGNMENT"]
        }
    })
    
    if not subscribe_resp or subscribe_resp.get('status') != 'success':
        print(f"⚠️  Subscribe failed (agents may not support pub/sub): {subscribe_resp}")
        # Continue with test anyway to see if publish works
    else:
        print(f"✅ Agent {agent2_id} subscribed to events")
    
    # Now publish a collaboration request
    pubsub_resp = send_daemon_command({
        "command": "SEND_MESSAGE",
        "parameters": {
            "from_agent": agent1_id,
            "event_types": ["COLLABORATION_REQUEST"],
            "content": "I need help analyzing some data. Any agents available to collaborate?",
            "metadata": {
                "task_type": "data_analysis",
                "urgency": "medium"
            }
        }
    })
    
    if not pubsub_resp or pubsub_resp.get('status') != 'success':
        print(f"❌ Failed to publish via event bus: {pubsub_resp}")
        return False
        
    result = pubsub_resp.get('result', {})
    print(f"✅ Published to event bus: {result.get('total_delivered')} deliveries")
    for detail in result.get('details', []):
        print(f"   Event: {detail['event_type']} → {detail['count']} subscribers")
    
    return True

def check_agent_responses():
    """Check if agents are processing messages (via logs or status)"""
    print("\n5. Checking agent activity...")
    
    # Get agent status
    agents_resp = send_daemon_command({"command": "GET_AGENTS"})
    
    if agents_resp and agents_resp.get('status') == 'success':
        agents = agents_resp.get('result', {}).get('agents', [])
        for agent in agents:
            # Handle both dict and string formats
            if isinstance(agent, dict):
                print(f"   Agent {agent.get('id', 'unknown')}: {agent.get('status', 'unknown')} (messages: {agent.get('messages_processed', 0)})")
            else:
                print(f"   Agent info: {agent}")
    
    # Note: In a real test, we'd wait and check for actual responses
    print("\n💡 Note: Agents process messages asynchronously. Check logs for actual Claude responses.")

def cleanup_agents():
    """Clean up test agents"""
    print("\n6. Cleaning up test agents...")
    
    cleanup_resp = send_daemon_command({
        "command": "CLEANUP",
        "parameters": {"type": "agents"}
    })
    
    if cleanup_resp and cleanup_resp.get('status') == 'success':
        print("✅ Test agents cleaned up")

def main():
    """Run agent messaging tests"""
    print("🔍 Testing Agent-to-Agent Messaging")
    print("=" * 50)
    
    # Spawn test agents
    agent1_id, agent2_id = spawn_test_agents()
    
    if not agent1_id or not agent2_id:
        print("❌ Failed to spawn test agents")
        return 1
    
    # Allow agents to initialize
    time.sleep(2)
    
    # Run tests
    tests_passed = 0
    total_tests = 3
    
    if test_direct_messaging(agent1_id, agent2_id):
        tests_passed += 1
        
    time.sleep(1)
    
    if test_broadcast_messaging(agent1_id):
        tests_passed += 1
        
    time.sleep(1)
    
    if test_pubsub_messaging(agent1_id, agent2_id):
        tests_passed += 1
    
    # Check activity
    check_agent_responses()
    
    # Cleanup
    cleanup_agents()
    
    # Summary
    print("\n" + "=" * 50)
    print(f"Tests passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("✅ All agent messaging tests PASSED")
        return 0
    else:
        print("❌ Some tests FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())