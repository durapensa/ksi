#!/usr/bin/env python3
"""Test parallel completion processing with multiple agents."""

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ksi_client import EventClient

async def spawn_test_agent(client, name):
    """Spawn a test agent."""
    result = await client.send_single("agent:spawn", {
        "profile": "base_single_agent",
        "agent_id": f"test_{name}_{uuid.uuid4().hex[:6]}"
    })
    return result.get("agent_id")

async def send_message(client, agent_id, message):
    """Send a message to an agent."""
    return await client.send_single("agent:send_message", {
        "agent_id": agent_id,
        "message": {"role": "user", "content": message}
    })

async def test_parallel_processing():
    """Test that multiple agents can process in parallel."""
    async with EventClient() as client:
        print("Testing parallel completion processing...")
        
        # Spawn 3 test agents
        agents = []
        for i in range(3):
            agent_id = await spawn_test_agent(client, f"parallel_{i}")
            agents.append(agent_id)
            print(f"Spawned agent: {agent_id}")
        
        # Send messages to all agents simultaneously
        print("\nSending messages to all agents...")
        tasks = []
        for i, agent_id in enumerate(agents):
            task = send_message(client, agent_id, 
                f"Test message {i}. Please emit this JSON event: "
                f'{{"event": "test:parallel", "data": {{"agent": "{agent_id}", "test_id": {i}}}}}')
            tasks.append(task)
        
        # Wait for all to complete
        results = await asyncio.gather(*tasks)
        
        print("\nResults:")
        for i, result in enumerate(results):
            print(f"Agent {i}: {result}")
        
        # Check completion status
        status = await client.send_single("completion:status", {})
        print(f"\nCompletion queues: {status.get('queues', {})}")
        
        # Cleanup - terminate agents
        print("\nCleaning up agents...")
        for agent_id in agents:
            await client.send_single("agent:terminate", {"agent_id": agent_id})

if __name__ == "__main__":
    asyncio.run(test_parallel_processing())