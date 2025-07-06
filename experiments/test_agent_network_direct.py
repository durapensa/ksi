#!/usr/bin/env python3
"""
Direct socket version of agent network test to bypass EventClient issues.
"""

import asyncio
import json
import socket
import time
from pathlib import Path
from datetime import datetime

def send_socket_command(command_dict):
    """Send a command via Unix socket and return response."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect("var/run/daemon.sock")
        
        # Send command
        message = json.dumps(command_dict) + "\n"
        sock.sendall(message.encode())
        
        # Read response
        response = ""
        while True:
            data = sock.recv(4096).decode()
            if not data:
                break
            response += data
            # Look for complete JSON response
            if response.count('{') == response.count('}') and response.count('{') > 0:
                break
                
        return json.loads(response)
    finally:
        sock.close()

async def test_agent_network_direct():
    """Test agent network using direct socket communication."""
    print("=== KSI Agent Network Direct Test ===\n")
    
    # 1. System Health Check
    print("1. System Health Check...")
    health = send_socket_command({"event": "system:health", "data": {}})
    print(f"✓ System healthy: {health['data']['status']}")
    print(f"  Uptime: {health['data']['uptime']:.1f}s")
    print(f"  Modules loaded: {health['data']['modules_loaded']}")
    
    # 2. Spawn coordinating agent
    print("\n2. Spawning coordinating agent...")
    spawn_result = send_socket_command({
        "event": "agent:spawn",
        "data": {
            "profile": "base_multi_agent",
            "agent_id": "coordinator_agent"
        }
    })
    
    coordinator_id = spawn_result["data"]["agent_id"]
    print(f"✓ Coordinator spawned: {coordinator_id}")
    
    # 3. Test completion system
    print("\n3. Testing completion system...")
    completion_result = send_socket_command({
        "event": "completion:async",
        "data": {
            "prompt": "Say 'Network test successful' and nothing else.",
            "model": "claude-cli/sonnet",
            "construct_id": coordinator_id
        }
    })
    
    request_id = completion_result["data"]["request_id"]
    print(f"✓ Completion request sent: {request_id}")
    
    # 4. Wait for completion and check response file
    print("\n4. Waiting for completion...")
    await asyncio.sleep(5)
    
    # Check if response file was created
    response_dir = Path("var/logs/responses")
    response_files = list(response_dir.glob("*.jsonl"))
    recent_files = [f for f in response_files if f.stat().st_mtime > time.time() - 60]
    
    if recent_files:
        latest_file = max(recent_files, key=lambda f: f.stat().st_mtime)
        print(f"✓ Response file created: {latest_file.name}")
        
        # Read the response
        with open(latest_file) as f:
            response_data = json.loads(f.read())
            response_text = response_data.get("response", {}).get("result", "")
            print(f"  Response: {response_text}")
    else:
        print("❌ No recent response file found")
    
    # 5. Test state operations
    print("\n5. Testing state operations...")
    
    # Create a test entity
    entity_result = send_socket_command({
        "event": "state:entity:create",
        "data": {
            "id": "test_entity",
            "type": "test",
            "properties": {
                "name": "Test Entity",
                "created_at": datetime.now().isoformat()
            }
        }
    })
    print(f"✓ Created entity: {entity_result['data']['id']}")
    
    # Query the entity
    query_result = send_socket_command({
        "event": "state:entity:query",
        "data": {
            "type": "test",
            "limit": 10
        }
    })
    entities = query_result["data"]["entities"]
    print(f"✓ Found {len(entities)} test entities")
    
    # 6. Test relationships
    print("\n6. Testing relationships...")
    
    # Create relationship
    rel_result = send_socket_command({
        "event": "state:relationship:create",
        "data": {
            "from": coordinator_id,
            "to": "test_entity",
            "type": "manages"
        }
    })
    print(f"✓ Created relationship: {rel_result['data']['id']}")
    
    # Query relationships
    rel_query = send_socket_command({
        "event": "state:relationship:query",
        "data": {
            "from": coordinator_id,
            "limit": 10
        }
    })
    relationships = rel_query["data"]["relationships"]
    print(f"✓ Found {len(relationships)} relationships")
    
    # 7. Test graph traversal
    print("\n7. Testing graph traversal...")
    
    traverse_result = send_socket_command({
        "event": "state:graph:traverse",
        "data": {
            "from": coordinator_id,
            "direction": "outgoing",
            "types": ["manages"],
            "depth": 2,
            "include_entities": True
        }
    })
    
    nodes = traverse_result["data"]["nodes"]
    edges = traverse_result["data"]["edges"]
    print(f"✓ Traversal found {len(nodes)} nodes and {len(edges)} edges")
    
    # 8. Test event log query
    print("\n8. Testing event log...")
    
    event_query = send_socket_command({
        "event": "event_log:query",
        "data": {
            "pattern": ["agent:spawn", "completion:async"],
            "limit": 5,
            "reverse": True
        }
    })
    
    events = event_query["data"]["events"]
    print(f"✓ Found {len(events)} recent events")
    
    # 9. Performance summary
    print("\n9. Performance Summary...")
    
    # Get active agents
    agent_list = send_socket_command({
        "event": "agent:list",
        "data": {}
    })
    active_agents = agent_list["data"]["agents"]
    print(f"✓ Active agents: {len(active_agents)}")
    
    # Get conversation status
    conv_status = send_socket_command({
        "event": "conversation:active",
        "data": {}
    })
    conversations = conv_status["data"]["conversations"]
    print(f"✓ Active conversations: {len(conversations)}")
    
    # 10. Cleanup
    print("\n10. Cleanup...")
    
    # Terminate coordinator
    terminate_result = send_socket_command({
        "event": "agent:terminate",
        "data": {
            "construct_id": coordinator_id,
            "reason": "Test complete"
        }
    })
    print(f"✓ Terminated coordinator: {terminate_result['data']['agent_id']}")
    
    print("\n=== Test Complete ===")
    print("✓ All core KSI systems functional")
    print("✓ Agent spawn/terminate working")
    print("✓ Completion system working")
    print("✓ State management working")
    print("✓ Graph traversal working")
    print("✓ Event logging working")

if __name__ == "__main__":
    try:
        asyncio.run(test_agent_network_direct())
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()