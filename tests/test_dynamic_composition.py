#!/usr/bin/env python3
"""
Test dynamic composition selection and agent self-modification
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ksi_client import EventClient


async def test_composition_selection():
    """Test dynamic composition selection"""
    async with EventClient(
        client_id="test_dynamic_composition",
        socket_path="var/run/daemon.sock"
    ) as client:
    
        print("Testing Composition Selection...")
        
        # Test 1: Select composition for research task
        result = await client.send_event("composition:select", {
        "agent_id": "test_agent_1",
        "role": "researcher",
        "capabilities": ["information_gathering", "fact_checking"],
        "task": "Research the history of artificial intelligence",
        "max_suggestions": 3
    })
    
        print(f"\nResearch Task Selection:")
        print(f"  Selected: {result.get('selected')}")
        print(f"  Score: {result.get('score')}")
        print(f"  Reasons: {result.get('reasons')}")
        if result.get('suggestions'):
            print(f"  Alternatives:")
            for sug in result['suggestions']:
                print(f"    - {sug['name']} (score: {sug['score']})")
        
        # Test 2: Select composition for collaborative task
        result = await client.send_event("composition:select", {
        "agent_id": "test_agent_2",
        "role": "collaborator",
        "task": "Work with team to solve complex problem",
        "context": {
            "existing_agents": ["researcher_1", "analyst_1"],
            "team_size": 3
        },
        "max_suggestions": 2
    })
    
        print(f"\nCollaborative Task Selection:")
        print(f"  Selected: {result.get('selected')}")
        print(f"  Score: {result.get('score')}")
        
        # Test 3: Create dynamic composition
        result = await client.send_event("composition:create", {
        "name": "custom_analyst",
        "type": "profile",
        "role": "data_analyst",
        "model": "sonnet",
        "capabilities": ["data_analysis", "visualization", "reporting"],
        "prompt": "You are a specialized data analyst focused on clear insights.",
        "metadata": {
            "self_modifiable": True,
            "spawns_agents": False
        }
    })
    
        print(f"\nDynamic Composition Creation:")
        print(f"  Status: {result.get('status')}")
        print(f"  Name: {result.get('name')}")


async def test_agent_self_modification():
    """Test agent composition updates"""
    async with EventClient(
        client_id="test_agent_modification",
        socket_path="var/run/daemon.sock"
    ) as client:
        
        print("\n\nTesting Agent Self-Modification...")
        
        # First spawn an agent with adaptive_researcher
        spawn_result = await client.send_event("agent:spawn", {
        "composition": "adaptive_researcher",
        "agent_id": "test_researcher_1",
        "task": "Research emerging technologies"
    })
    
        if spawn_result.get('process_id'):
            print(f"Spawned agent: {spawn_result['agent_id']}")
            
            # Wait for agent to initialize
            await asyncio.sleep(2)
            
            # Test composition update
            update_result = await client.send_event("agent:update_composition", {
            "agent_id": "test_researcher_1",
            "new_composition": "debater",
            "reason": "Switching to argumentation mode for analysis"
        })
        
            print(f"\nComposition Update:")
            print(f"  Status: {update_result.get('status')}")
            print(f"  New composition: {update_result.get('new_composition')}")
            print(f"  New capabilities: {update_result.get('new_capabilities')}")
            
            # Terminate test agent
            await client.send_event("agent:terminate", {"agent_id": "test_researcher_1"})


async def test_dynamic_spawning():
    """Test dynamic spawn modes"""
    async with EventClient(
        client_id="test_dynamic_spawning",
        socket_path="var/run/daemon.sock"
    ) as client:
        
        print("\n\nTesting Dynamic Spawning...")
        
        # Test dynamic spawn mode
        spawn_result = await client.send_event("agent:spawn", {
        "agent_id": "dynamic_agent_1",
        "spawn_mode": "dynamic",
        "selection_context": {
            "role": "analyzer",
            "task": "Analyze market trends",
            "required_capabilities": ["data_analysis", "pattern_recognition"]
        },
        "task": "Analyze cryptocurrency market trends"
    })
    
        print(f"\nDynamic Spawn Result:")
        print(f"  Status: {spawn_result.get('status')}")
        if '_composition_selection' in spawn_result:
            sel = spawn_result['_composition_selection']
            print(f"  Selected: {sel['selected']} (score: {sel['score']})")
            print(f"  Reasons: {sel['reasons']}")
        
        # Cleanup
        if spawn_result.get('process_id'):
            await client.send_event("agent:terminate", {"agent_id": "dynamic_agent_1"})


async def main():
    """Run all tests"""
    try:
        await test_composition_selection()
        await test_agent_self_modification()
        await test_dynamic_spawning()
        print("\n\nAll tests completed!")
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())