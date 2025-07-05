#!/usr/bin/env python3
"""
Test script for agent metadata tracking (Phase 1)
"""

import asyncio
import json
import subprocess
import time


async def send_socket_message(message):
    """Send message to daemon via Unix socket."""
    cmd = ['echo', json.dumps(message), '|', 'nc', '-U', 'var/run/daemon.sock']
    result = subprocess.run(' '.join(cmd), shell=True, capture_output=True, text=True)
    if result.stdout:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            print(f"Failed to parse response: {result.stdout}")
    return None


async def test_agent_metadata():
    """Test agent metadata tracking."""
    print("Testing Agent Metadata Tracking (Phase 1)")
    print("=" * 50)
    
    # 1. Spawn an originator agent
    print("\n1. Spawning originator agent...")
    originator_spawn = {
        "event": "agent:spawn",
        "data": {
            "agent_id": "test_originator_001",
            "profile": "base_single_agent",
            "agent_type": "originator",
            "purpose": "Test originator for metadata tracking"
        }
    }
    
    response = await send_socket_message(originator_spawn)
    if response and response.get("data"):
        print(f"✓ Originator spawned: {response['data']}")
        originator_id = response['data']['agent_id']
    else:
        print("✗ Failed to spawn originator")
        return
    
    # 2. Spawn construct agents
    print("\n2. Spawning construct agents...")
    construct_ids = []
    
    for i in range(3):
        construct_spawn = {
            "event": "agent:spawn",
            "data": {
                "agent_id": f"test_construct_{i:03d}",
                "profile": "base_single_agent",
                "originator_agent_id": originator_id,
                "purpose": f"Test construct {i} - observing aspect {i}"
            }
        }
        
        response = await send_socket_message(construct_spawn)
        if response and response.get("data"):
            print(f"✓ Construct {i} spawned: {response['data']}")
            construct_ids.append(response['data']['agent_id'])
        else:
            print(f"✗ Failed to spawn construct {i}")
    
    # 3. List all agents
    print("\n3. Listing all agents...")
    list_agents = {
        "event": "agent:list",
        "data": {}
    }
    
    response = await send_socket_message(list_agents)
    if response and response.get("data"):
        agents = response['data']['agents']
        print(f"✓ Found {len(agents)} agents:")
        for agent in agents:
            print(f"  - {agent['agent_id']}: type={agent.get('agent_type', 'unknown')}, "
                  f"originator={agent.get('originator_agent_id', 'None')}")
    
    # 4. List constructs for originator
    print(f"\n4. Listing constructs for originator {originator_id}...")
    list_constructs = {
        "event": "agent:list_constructs",
        "data": {
            "originator_agent_id": originator_id
        }
    }
    
    response = await send_socket_message(list_constructs)
    if response and response.get("data"):
        constructs = response['data']['constructs']
        print(f"✓ Found {len(constructs)} constructs:")
        for construct in constructs:
            print(f"  - {construct['agent_id']}: purpose={construct.get('purpose', 'None')}")
    
    # 5. Clean up - terminate agents
    print("\n5. Cleaning up agents...")
    for agent_id in [originator_id] + construct_ids:
        terminate = {
            "event": "agent:terminate",
            "data": {"agent_id": agent_id}
        }
        response = await send_socket_message(terminate)
        if response and response.get("data", {}).get("status") == "terminated":
            print(f"✓ Terminated {agent_id}")
        else:
            print(f"✗ Failed to terminate {agent_id}")
    
    print("\n✓ Phase 1 testing complete!")


if __name__ == "__main__":
    asyncio.run(test_agent_metadata())