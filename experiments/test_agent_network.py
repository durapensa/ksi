#!/usr/bin/env python3
"""
Test agent network dynamics with KSI.
Demonstrates spawn patterns, graph relationships, and event observation.
"""

import asyncio
import json
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_client import EventClient

async def create_agent_network():
    """Create a simple agent network and observe its behavior."""
    
    async with EventClient() as client:
        print("=== KSI Agent Network Experiment ===\n")
        
        # 1. Spawn an originator agent
        print("1. Spawning originator agent...")
        originator_result = await client.send_single("agent:spawn", {
            "profile": "base_multi_agent",
            "prompt": """You are a research coordinator. Your task is to:
            1. Introduce yourself briefly
            2. Spawn 2 researcher agents with different focus areas
            3. Create a knowledge entity to track your research topic
            4. Report success when done
            
            Keep responses concise.""",
            "metadata": {
                "role": "coordinator",
                "experiment": "agent_network_test"
            }
        })
        
        originator_id = originator_result.get("construct_id")
        print(f"✓ Originator spawned: {originator_id}")
        
        # 2. Wait a moment for the agent to work
        print("\n2. Waiting for agent to complete tasks...")
        await asyncio.sleep(10)
        
        # 3. Query the agent network
        print("\n3. Querying agent network...")
        
        # Get all agents
        agents = await client.send_single("agent:list", {})
        print(f"✓ Active agents: {len(agents.get('agents', []))}")
        
        # Query relationships
        relationships = await client.send_single("state:relationship:query", {
            "from": originator_id,
            "type": "spawned"
        })
        
        spawned_count = len(relationships.get("relationships", []))
        print(f"✓ Agents spawned by originator: {spawned_count}")
        
        # 4. Traverse the agent network
        print("\n4. Traversing agent network...")
        graph_result = await client.send_single("state:graph:traverse", {
            "from": originator_id,
            "direction": "outgoing",
            "types": ["spawned"],
            "depth": 2,
            "include_entities": True
        })
        
        nodes = graph_result.get("nodes", {})
        edges = graph_result.get("edges", [])
        print(f"✓ Network nodes: {len(nodes)}")
        print(f"✓ Network edges: {len(edges)}")
        
        # 5. Check for knowledge entities
        print("\n5. Querying knowledge entities...")
        knowledge = await client.send_single("state:entity:query", {
            "type": "knowledge",
            "include": ["properties"]
        })
        
        knowledge_count = len(knowledge.get("entities", []))
        print(f"✓ Knowledge entities created: {knowledge_count}")
        
        # 6. Analyze event patterns
        print("\n6. Analyzing event patterns...")
        
        # Query recent events from our agents
        event_query = await client.send_single("monitor:query", {
            "pattern": ["agent:*", "completion:*"],
            "originator": originator_id,
            "limit": 20
        })
        
        events = event_query.get("events", [])
        event_types = {}
        for event in events:
            event_type = event.get("event_name", "").split(":")[0]
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        print(f"✓ Recent events: {len(events)}")
        print(f"✓ Event types: {json.dumps(event_types, indent=2)}")
        
        # 7. Test observation
        print("\n7. Setting up observation...")
        
        # Subscribe to events from spawned agents
        for rel in relationships.get("relationships", [])[:2]:  # First 2 spawned agents
            target_id = rel.get("to")
            if target_id:
                sub_result = await client.send_single("observation:subscribe", {
                    "observer": "experiment_observer",
                    "target": target_id,
                    "events": ["completion:*", "agent:*"],
                    "filter": {
                        "rate_limit": {
                            "max_events": 10,
                            "window_seconds": 60
                        }
                    }
                })
                print(f"✓ Subscribed to agent: {target_id}")
        
        # 8. Get conversation history
        print("\n8. Checking conversation activity...")
        conversations = await client.send_single("conversation:active", {})
        active_count = len(conversations.get("conversations", []))
        print(f"✓ Active conversations: {active_count}")
        
        # 9. Summary
        print("\n=== Experiment Summary ===")
        print(f"• Originator agent: {originator_id}")
        print(f"• Total agents created: {len(agents.get('agents', []))}")
        print(f"• Agent relationships: {spawned_count}")
        print(f"• Knowledge entities: {knowledge_count}")
        print(f"• Events generated: {len(events)}")
        print(f"• Active conversations: {active_count}")
        
        # Optional: Terminate agents
        print("\n10. Cleanup (optional - press Ctrl+C to skip)...")
        try:
            await asyncio.sleep(2)
            
            # Terminate spawned agents first
            for rel in relationships.get("relationships", []):
                target_id = rel.get("to")
                if target_id:
                    await client.send_single("agent:terminate", {
                        "construct_id": target_id,
                        "reason": "Experiment complete"
                    })
                    print(f"✓ Terminated agent: {target_id}")
            
            # Terminate originator
            await client.send_single("agent:terminate", {
                "construct_id": originator_id,
                "reason": "Experiment complete"
            })
            print(f"✓ Terminated originator: {originator_id}")
            
        except KeyboardInterrupt:
            print("\n✓ Skipping cleanup - agents remain active")

if __name__ == "__main__":
    # Ensure daemon is running
    print("Checking daemon status...")
    try:
        asyncio.run(create_agent_network())
    except ConnectionError:
        print("\n❌ Error: KSI daemon is not running")
        print("Start it with: ./daemon_control.py start")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)