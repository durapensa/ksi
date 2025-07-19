#!/usr/bin/env python3
"""Test native WebSocket transport with Web UI by generating events."""

import asyncio
import json
from ksi_client import KSIClient

async def test_ui_events():
    """Generate test events for UI visualization."""
    client = KSIClient()
    
    print("🎭 Testing Native WebSocket with Web UI...")
    print("👀 Watch the UI at http://localhost:8080")
    print()
    
    # 1. Spawn a test agent
    print("1️⃣ Spawning test agent...")
    response = await client.send_event("agent:spawn_from_component", {
        "component": "personas/analysts/data_analyst",
        "name": "ui-test-analyst",
        "metadata": {
            "purpose": "Test native WebSocket UI"
        }
    })
    
    if response and response.get("agent_id"):
        agent_id = response["agent_id"]
        print(f"✓ Agent spawned: {agent_id}")
        
        # Wait for UI to update
        await asyncio.sleep(2)
        
        # 2. Send some completion requests
        print("\n2️⃣ Sending completion requests...")
        for i in range(3):
            comp_response = await client.send_event("completion:async", {
                "agent_id": agent_id,
                "prompt": f"Test message {i+1}: Analyze the native WebSocket transport",
                "model": "claude-3-haiku-20240307"
            })
            print(f"  → Completion {i+1}: {comp_response.get('session_id', 'no session')}")
            await asyncio.sleep(1)
        
        # 3. Create state entities
        print("\n3️⃣ Creating state entities...")
        entity_response = await client.send_event("state:entity:create", {
            "entity_type": "test_node",
            "data": {
                "name": "WebSocket Test Node",
                "transport": "native",
                "timestamp": asyncio.get_event_loop().time()
            }
        })
        print(f"  → Entity created: {entity_response}")
        
        # 4. Send orchestration message
        print("\n4️⃣ Sending orchestration message...")
        msg_response = await client.send_event("orchestration:message", {
            "orchestration_id": "test-orchestration",
            "source": agent_id,
            "target": "ui-visualizer",
            "message": "Native WebSocket is working perfectly!"
        })
        print(f"  → Message sent: {msg_response}")
        
        # 5. Wait a bit then terminate
        print("\n⏳ Waiting 5 seconds before cleanup...")
        await asyncio.sleep(5)
        
        print("\n5️⃣ Terminating test agent...")
        term_response = await client.send_event("agent:terminate", {
            "agent_id": agent_id
        })
        print(f"  → Agent terminated: {term_response}")
        
    else:
        print("✗ Failed to spawn agent")
    
    print("\n✅ Test complete! Check the Web UI for visualization")

if __name__ == "__main__":
    asyncio.run(test_ui_events())