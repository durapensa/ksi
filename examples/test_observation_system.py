#!/usr/bin/env python3
"""
Test script for the agent observation system.

Tests observation subscription, event interception, and observer notifications.
"""

import asyncio
import json
from ksi_client import AsyncClient


async def test_observation():
    """Test the observation system with simulated agents."""
    async with AsyncClient() as client:
        print("=== Testing Agent Observation System ===\n")
        
        # 1. First, let's see if we have any active agents
        print("1. Checking active agents...")
        response = await client.emit_event("agent:list", {})
        agents = response.get("agents", {})
        print(f"   Active agents: {list(agents.keys())}")
        
        # 2. Create a subscription between agents (if we have any)
        # For testing, let's simulate an originator observing a construct
        originator_id = "test_originator_1"
        construct_id = "test_construct_1"
        
        print(f"\n2. Creating observation subscription...")
        print(f"   Observer: {originator_id}")
        print(f"   Target: {construct_id}")
        
        subscription_response = await client.emit_event("observation:subscribe", {
            "observer": originator_id,
            "target": construct_id,
            "events": ["message:*", "state:*", "error:*"],
            "filter": {
                "exclude": ["system:health"],
                "include_responses": True,
                "sampling_rate": 1.0
            }
        })
        
        if "error" in subscription_response:
            print(f"   Error: {subscription_response['error']}")
        else:
            print(f"   Subscription created: {subscription_response.get('subscription_id')}")
            print(f"   Status: {subscription_response.get('status')}")
        
        # 3. List active subscriptions
        print("\n3. Listing active subscriptions...")
        list_response = await client.emit_event("observation:list", {})
        subscriptions = list_response.get("subscriptions", [])
        print(f"   Total subscriptions: {list_response.get('count', 0)}")
        for sub in subscriptions:
            print(f"   - {sub['observer']} -> {sub['target']} (events: {sub['events']})")
        
        # 4. Simulate an event from the construct (with agent_id in context)
        print(f"\n4. Simulating event from {construct_id}...")
        
        # We need to emit an event with the construct's agent_id in the context
        # This would normally come from the agent itself
        test_event_response = await client.emit_event("message:test", {
            "agent_id": construct_id,  # Include agent_id so observation system knows the source
            "content": "Test message from construct",
            "timestamp": asyncio.get_event_loop().time()
        })
        print("   Event emitted")
        
        # 5. Check if any observe:begin or observe:end events were generated
        # In a real scenario, the originator would receive these
        print("\n5. Observation events would be sent to observers")
        print("   - observe:begin - notifies observer when target event starts")
        print("   - observe:end - notifies observer when target event completes")
        
        # 6. Test subscription query with filters
        print("\n6. Querying subscriptions with filters...")
        
        # Query by observer
        observer_query = await client.emit_event("observation:list", {
            "observer": originator_id
        })
        print(f"   Subscriptions by {originator_id}: {observer_query.get('count', 0)}")
        
        # Query by target
        target_query = await client.emit_event("observation:list", {
            "target": construct_id
        })
        print(f"   Observers of {construct_id}: {target_query.get('count', 0)}")
        
        # 7. Test unsubscribe
        if subscription_response.get("subscription_id"):
            print("\n7. Testing unsubscribe...")
            unsub_response = await client.emit_event("observation:unsubscribe", {
                "subscription_id": subscription_response["subscription_id"]
            })
            print(f"   Unsubscribed: {unsub_response.get('unsubscribed', 0)} subscriptions")
            print(f"   IDs: {unsub_response.get('subscription_ids', [])}")
        
        # 8. Verify subscriptions cleared
        print("\n8. Verifying subscriptions cleared...")
        final_list = await client.emit_event("observation:list", {})
        print(f"   Remaining subscriptions: {final_list.get('count', 0)}")
        
        print("\n=== Observation System Test Complete ===")


async def test_with_real_agents():
    """Test observation with real spawned agents."""
    async with AsyncClient() as client:
        print("\n=== Testing with Real Agents ===\n")
        
        # 1. Spawn an originator agent
        print("1. Spawning originator agent...")
        originator_response = await client.emit_event("agent:spawn", {
            "profile": "base_single_agent",
            "config": {
                "system_prompt": "You are an originator agent that observes other agents."
            }
        })
        
        if "error" in originator_response:
            print(f"   Error spawning originator: {originator_response['error']}")
            return
            
        originator_id = originator_response.get("agent_id")
        print(f"   Originator spawned: {originator_id}")
        
        # 2. Spawn a construct agent with originator relationship
        print("\n2. Spawning construct agent...")
        construct_response = await client.emit_event("agent:spawn", {
            "profile": "base_single_agent",
            "originator_agent_id": originator_id,
            "purpose": "test_observer",
            "config": {
                "system_prompt": "You are a construct agent being observed."
            }
        })
        
        if "error" in construct_response:
            print(f"   Error spawning construct: {construct_response['error']}")
            # Clean up originator
            await client.emit_event("agent:terminate", {"agent_id": originator_id})
            return
            
        construct_id = construct_response.get("agent_id")
        print(f"   Construct spawned: {construct_id}")
        print(f"   Originator relationship established")
        
        # 3. Set up observation
        print("\n3. Setting up observation...")
        subscription_response = await client.emit_event("observation:subscribe", {
            "observer": originator_id,
            "target": construct_id,
            "events": ["message:*", "completion:*"],
            "filter": {
                "include_responses": True
            }
        })
        
        subscription_id = subscription_response.get("subscription_id")
        print(f"   Subscription created: {subscription_id}")
        
        # 4. Send a message through the construct
        print("\n4. Sending message through construct...")
        message_response = await client.emit_event("message:send", {
            "agent_id": construct_id,
            "content": "Hello, I am being observed!"
        })
        print("   Message sent")
        
        # Give time for observation events to propagate
        await asyncio.sleep(0.5)
        
        # 5. Query agent relationships
        print("\n5. Querying agent relationships...")
        
        # List constructs of originator
        constructs_response = await client.emit_event("agent:list_constructs", {
            "originator_id": originator_id
        })
        print(f"   Originator's constructs: {constructs_response.get('constructs', [])}")
        
        # Get agent info with relationships
        info_response = await client.emit_event("agent:info", {
            "agent_id": construct_id
        })
        agent_info = info_response.get("agent", {})
        print(f"   Construct info:")
        print(f"     - Type: {agent_info.get('agent_type')}")
        print(f"     - Originator: {agent_info.get('originator_agent_id')}")
        print(f"     - Is construct: {agent_info.get('is_construct')}")
        
        # 6. Clean up
        print("\n6. Cleaning up...")
        
        # Unsubscribe
        await client.emit_event("observation:unsubscribe", {
            "subscription_id": subscription_id
        })
        print("   Unsubscribed")
        
        # Terminate agents
        await client.emit_event("agent:terminate", {"agent_id": construct_id})
        print(f"   Terminated construct: {construct_id}")
        
        await client.emit_event("agent:terminate", {"agent_id": originator_id})
        print(f"   Terminated originator: {originator_id}")
        
        print("\n=== Real Agent Test Complete ===")


async def main():
    """Run all observation tests."""
    # Test basic observation system
    await test_observation()
    
    # Uncomment to test with real agents
    # await test_with_real_agents()


if __name__ == "__main__":
    asyncio.run(main())