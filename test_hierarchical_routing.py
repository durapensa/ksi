#!/usr/bin/env python3
"""
Test hierarchical event routing with subscription levels
"""

import asyncio
import json
import sys
from pathlib import Path

# Add KSI to path
sys.path.insert(0, str(Path(__file__).parent))

from ksi_client import EventClient


async def test_hierarchical_routing():
    """Test hierarchical event routing."""
    async with EventClient(client_id="test_hierarchical_routing") as client:
        print("Testing Hierarchical Event Routing\n" + "="*50)
        
        # Create a test orchestration pattern
        pattern = {
            "name": "test_hierarchical_pattern",
            "description": "Test pattern for hierarchical routing",
            "event_propagation": {
                "subscription_level": -1,  # Orchestration receives ALL events
                "error_handling": "bubble"
            },
            "agents": {
                "coordinator": {
                    "profile": "components/core/base_agent",
                    "prompt_template": "You are a coordinator that spawns child agents",
                    "vars": {
                        "event_subscription_level": 2  # Receive events from children and grandchildren
                    }
                },
                "worker1": {
                    "profile": "components/core/base_agent", 
                    "prompt_template": "You are worker 1",
                    "vars": {
                        "event_subscription_level": 1  # Only direct children
                    }
                },
                "worker2": {
                    "profile": "components/core/base_agent",
                    "prompt_template": "You are worker 2", 
                    "vars": {
                        "event_subscription_level": 0  # No child events
                    }
                }
            },
            "initialization": {
                "strategy": "broadcast",
                "message": "Test hierarchical routing by emitting events"
            }
        }
        
        # Save pattern
        print("1. Creating test pattern...")
        result = await client.send_single("composition:create", {
            "name": "orchestrations/test_hierarchical_routing",
            "type": "orchestration",
            "content": json.dumps(pattern, indent=2),
            "description": "Test pattern for hierarchical routing"
        })
        print(f"   Pattern created: {result.get('status')}")
        
        # Spawn orchestration
        print("\n2. Spawning orchestration...")
        spawn_result = await client.send_single("orchestration:spawn", {
            "pattern": "orchestrations/test_hierarchical_routing"
        })
        
        orchestration_id = spawn_result.get("orchestration_id")
        print(f"   Orchestration ID: {orchestration_id}")
        
        # Wait for initialization
        await asyncio.sleep(2)
        
        # Get orchestration status
        print("\n3. Checking orchestration status...")
        status_result = await client.send_single("orchestration:status", {
            "orchestration_id": orchestration_id
        })
        print(f"   Status: {status_result.get('status')}")
        print(f"   Agents: {status_result.get('agents')}")
        
        # Simulate agent events
        print("\n4. Simulating agent events...")
        
        # Worker1 emits an event
        worker1_id = status_result.get("agents", {}).get("worker1", {}).get("agent_id")
        if worker1_id:
            print(f"   Worker1 ({worker1_id}) emitting test event...")
            event_result = await client.send_single("agent:send_message", {
                "agent_id": worker1_id,
                "message": "Test message from worker1"
            })
            print(f"   Result: {event_result}")
        
        # Let events propagate
        await asyncio.sleep(2)
        
        # Check orchestration received events
        print("\n5. Checking orchestration received events...")
        instance_result = await client.send_single("orchestration:get_instance", {
            "orchestration_id": orchestration_id
        })
        
        received_events = instance_result.get("instance", {}).get("received_events", [])
        print(f"   Orchestration received {len(received_events)} events")
        for event in received_events[-5:]:  # Last 5 events
            print(f"   - {event.get('event')} from {event.get('source_agent')}")
        
        # Terminate orchestration
        print("\n6. Terminating orchestration...")
        term_result = await client.send_single("orchestration:terminate", {
            "orchestration_id": orchestration_id
        })
        print(f"   Result: {term_result.get('status')}")
        
        print("\nTest complete!")


if __name__ == "__main__":
    asyncio.run(test_hierarchical_routing())