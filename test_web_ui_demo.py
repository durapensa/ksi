#!/usr/bin/env python3
"""
Demo script to generate interesting events for testing the enhanced Web UI.
This creates agents with hierarchical relationships to showcase the new features.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ksi_common.config import config

async def demo_hierarchical_agents():
    """Create a hierarchical agent structure to demonstrate enhanced UI features."""
    
    print("🎭 Web UI Demo: Creating Hierarchical Agent Structure")
    print("="*50)
    
    try:
        reader, writer = await asyncio.open_unix_connection(str(config.socket_path))
        
        # Create a root orchestration
        print("1️⃣ Creating root orchestration...")
        orch_cmd = {
            "event": "orchestration:create",
            "data": {
                "orchestration_id": "demo_orchestration",
                "description": "Demo hierarchical orchestration"
            }
        }
        
        writer.write((json.dumps(orch_cmd) + "\n").encode())
        await writer.drain()
        await asyncio.sleep(1)
        
        # Spawn a root agent (depth 0)
        print("2️⃣ Spawning root coordinator agent...")
        root_cmd = {
            "event": "agent:spawn_from_component",
            "data": {
                "component": "components/personas/managers/team_lead",
                "agent_id": "root_coordinator",
                "orchestration_id": "demo_orchestration",
                "orchestration_depth": 0
            }
        }
        
        writer.write((json.dumps(root_cmd) + "\n").encode())
        await writer.drain()
        await asyncio.sleep(2)
        
        # Spawn child agents (depth 1)
        print("3️⃣ Spawning analyst agents (depth 1)...")
        for i in range(2):
            child_cmd = {
                "event": "agent:spawn_from_component",
                "data": {
                    "component": "components/personas/analysts/data_analyst",
                    "agent_id": f"analyst_{i}",
                    "parent_agent_id": "root_coordinator",
                    "orchestration_id": "demo_orchestration",
                    "orchestration_depth": 1,
                    "event_subscription_level": 2  # Can see grandchildren
                }
            }
            
            writer.write((json.dumps(child_cmd) + "\n").encode())
            await writer.drain()
            await asyncio.sleep(1)
        
        # Spawn grandchild agents (depth 2)
        print("4️⃣ Spawning researcher agents (depth 2)...")
        for i in range(2):
            grandchild_cmd = {
                "event": "agent:spawn_from_component",
                "data": {
                    "component": "components/personas/specialists/researcher",
                    "agent_id": f"researcher_{i}",
                    "parent_agent_id": "analyst_0",
                    "orchestration_id": "demo_orchestration",
                    "orchestration_depth": 2,
                    "event_subscription_level": 1  # Only direct children
                }
            }
            
            writer.write((json.dumps(grandchild_cmd) + "\n").encode())
            await writer.drain()
            await asyncio.sleep(1)
        
        print("\n5️⃣ Generating some agent activity...")
        # Generate some events from agents
        for agent_id in ["root_coordinator", "analyst_0", "researcher_0"]:
            status_event = {
                "event": "agent:status",
                "data": {
                    "agent_id": agent_id,
                    "status": "active",
                    "message": f"{agent_id} is processing..."
                },
                "_agent_id": agent_id  # This simulates daemon metadata
            }
            
            writer.write((json.dumps(status_event) + "\n").encode())
            await writer.drain()
            await asyncio.sleep(0.5)
        
        print("\n✅ Demo setup complete!")
        print("\n📌 What to look for in the Web UI:")
        print("   - Agent nodes with different colors based on depth")
        print("   - Hierarchical layout showing parent-child relationships")
        print("   - Event log with agent IDs and orchestration context")
        print("   - Tooltips on events showing full metadata")
        print("   - Gold highlighting when agents generate events")
        
        # Wait a bit to let user observe
        print("\n⏱️  Waiting 15 seconds for observation...")
        await asyncio.sleep(15)
        
        # Clean up agents
        print("\n🧹 Cleaning up demo agents...")
        agents_to_terminate = [
            "root_coordinator", "analyst_0", "analyst_1", 
            "researcher_0", "researcher_1"
        ]
        
        for agent_id in agents_to_terminate:
            terminate_cmd = {
                "event": "agent:terminate",
                "data": {"agent_id": agent_id}
            }
            writer.write((json.dumps(terminate_cmd) + "\n").encode())
            await writer.drain()
            await asyncio.sleep(0.5)
        
        print("✅ Demo agents terminated")
        
        writer.close()
        await writer.wait_closed()
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        return False
    
    return True

async def main():
    print("🌐 Enhanced Web UI Demo")
    print("Make sure the web UI is open at http://localhost:8080")
    print()
    
    await demo_hierarchical_agents()
    
    print("\n🎯 Demo complete! Check your browser to see:")
    print("   1. Hierarchical agent graph with depth-based colors")
    print("   2. Rich event log with metadata")
    print("   3. Agent activity animations")

if __name__ == "__main__":
    asyncio.run(main())