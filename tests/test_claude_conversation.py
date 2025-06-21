#!/usr/bin/env python3
"""
Test script for Claude-to-Claude conversation system
"""

import asyncio
import socket
import json
import time
import sys
from pathlib import Path

SOCKET_PATH = 'sockets/claude_daemon.sock'

def send_command(command: str) -> str:
    """Send command to daemon and get response"""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(SOCKET_PATH)
        if not command.endswith('\n'):
            command += '\n'
        sock.sendall(command.encode())
        sock.shutdown(socket.SHUT_WR)
        
        response = b''
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        
        return response.decode().strip()
    finally:
        sock.close()

async def test_simple_conversation():
    """Test a simple conversation between two Claude agents"""
    print("=== Testing Claude-to-Claude Conversation ===\n")
    
    # Check daemon health
    print("1. Checking daemon health...")
    response = send_command("HEALTH_CHECK")
    print(f"   Daemon status: {response}")
    
    # Get current agents
    print("\n2. Current agents:")
    response = send_command("GET_AGENTS")
    agents = json.loads(response)
    print(f"   Registered agents: {len(agents.get('agents', {}))}")
    
    # Spawn two agents with different profiles
    print("\n3. Spawning conversation agents...")
    
    # Agent 1: Analyst
    response = send_command("SPAWN_AGENT:analyst:Analyze the concept of artificial general intelligence:You are participating in a thoughtful discussion:analyst_test_1")
    print(f"   Agent 1 spawn result: {response}")
    
    await asyncio.sleep(2)
    
    # Agent 2: Researcher  
    response = send_command("SPAWN_AGENT:researcher:Research perspectives on artificial general intelligence:You are participating in a thoughtful discussion:researcher_test_1")
    print(f"   Agent 2 spawn result: {response}")
    
    await asyncio.sleep(2)
    
    # Check agents again
    print("\n4. Updated agents:")
    response = send_command("GET_AGENTS")
    agents = json.loads(response)
    print(f"   Total agents: {len(agents.get('agents', {}))}")
    for agent_id, info in agents.get('agents', {}).items():
        print(f"   - {agent_id}: {info.get('role')} ({info.get('status')})")
    
    # Send message between agents
    print("\n5. Testing inter-agent communication...")
    message = "What are your thoughts on the timeline for achieving AGI? I'm particularly interested in the technical challenges."
    response = send_command(f"SEND_MESSAGE:analyst_test_1:researcher_test_1:{message}")
    print(f"   Message result: {response}")
    
    # Test shared state
    print("\n6. Testing shared state...")
    response = send_command("SET_SHARED:conversation_topic:artificial general intelligence")
    print(f"   Set shared state: {response}")
    
    response = send_command("GET_SHARED:conversation_topic")
    print(f"   Get shared state: {response}")
    
    # Check message bus stats
    print("\n7. Message bus statistics:")
    response = send_command("MESSAGE_BUS_STATS")
    try:
        stats = json.loads(response)
        print(f"   Connected agents: {stats.get('connected_agents', [])}")
        print(f"   Subscriptions: {stats.get('subscriptions', {})}")
        print(f"   Offline queues: {stats.get('offline_queues', {})}")
    except:
        print(f"   Raw response: {response}")
    
    print("\n=== Test Complete ===")

async def test_with_persistent_agents():
    """Test with persistent agent connections"""
    print("\n=== Testing with Persistent Agent Connections ===\n")
    
    # Start two persistent agents as subprocesses
    import subprocess
    
    print("1. Starting persistent Claude agents...")
    
    # Start analyst agent
    analyst_proc = await asyncio.create_subprocess_exec(
        sys.executable, 'claude_agent.py', '--id', 'persistent_analyst', '--profile', 'analyst',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    # Start researcher agent
    researcher_proc = await asyncio.create_subprocess_exec(
        sys.executable, 'claude_agent.py', '--id', 'persistent_researcher', '--profile', 'researcher',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    print("   Agents started, waiting for connection...")
    await asyncio.sleep(3)
    
    # Check message bus
    print("\n2. Checking message bus connections...")
    response = send_command("MESSAGE_BUS_STATS")
    try:
        stats = json.loads(response)
        print(f"   Connected agents: {stats.get('connected_agents', [])}")
    except:
        print(f"   Raw response: {response}")
    
    # Send task via message bus
    print("\n3. Publishing task via message bus...")
    task_payload = {
        'to': 'persistent_analyst',
        'task': 'Analyze the implications of quantum computing on cryptography',
        'context': 'Focus on near-term (5-10 year) practical impacts'
    }
    response = send_command(f"PUBLISH:orchestrator:TASK_ASSIGNMENT:{json.dumps(task_payload)}")
    print(f"   Publish result: {response}")
    
    # Broadcast message
    print("\n4. Broadcasting message to all agents...")
    broadcast_payload = {
        'content': 'All agents: Please share your perspective on the future of AI safety research.'
    }
    response = send_command(f"PUBLISH:orchestrator:BROADCAST:{json.dumps(broadcast_payload)}")
    print(f"   Broadcast result: {response}")
    
    # Let conversation run
    print("\n5. Letting agents converse for 10 seconds...")
    await asyncio.sleep(10)
    
    # Clean up
    print("\n6. Cleaning up...")
    analyst_proc.terminate()
    researcher_proc.terminate()
    await analyst_proc.wait()
    await researcher_proc.wait()
    
    print("\n=== Persistent Agent Test Complete ===")

async def main():
    """Main test runner"""
    # Ensure daemon is running
    if not Path(SOCKET_PATH).exists():
        print("Starting daemon...")
        import subprocess
        subprocess.Popen([sys.executable, 'daemon.py'], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
        await asyncio.sleep(3)
    
    # Run tests
    await test_simple_conversation()
    await test_with_persistent_agents()

if __name__ == '__main__':
    asyncio.run(main())