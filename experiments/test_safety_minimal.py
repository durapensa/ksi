#!/usr/bin/env python3
"""
Minimal test of safety utilities with cleanup.
"""

import asyncio
import json
from safety_utils import ExperimentSafetyGuard, SafeSpawnContext
from ksi_socket_utils import KSISocketClient


async def cleanup_existing_agents():
    """Clean up any existing agents before test."""
    client = KSISocketClient("../var/run/daemon.sock")
    
    print("Cleaning up existing agents...")
    agents = await client.get_agent_list()
    
    for agent in agents:
        agent_id = agent['agent_id']
        print(f"  Terminating {agent_id}...")
        try:
            await client.terminate_agent(agent_id)
        except Exception as e:
            print(f"    Error: {e}")
    
    print(f"Cleaned up {len(agents)} agents")


async def test_safety_controlled():
    """Test safety with controlled environment."""
    
    # Clean up first
    await cleanup_existing_agents()
    await asyncio.sleep(2)  # Let cleanup settle
    
    # Create safety guard with small limits
    safety = ExperimentSafetyGuard(
        max_agents=3,
        max_spawn_depth=2,
        max_children_per_agent=2,
        agent_timeout=60,  # 1 minute
        spawn_cooldown=0.5
    )
    
    async with SafeSpawnContext(safety) as ctx:
        print("\n=== Testing Safety Guard ===")
        print(f"Limits: {json.dumps(safety.to_dict(), indent=2)}")
        
        # Test 1: Spawn root agent
        print("\n1. Spawning root agent...")
        try:
            result = await ctx.spawn_agent(
                profile="base_single_agent",
                prompt="You are agent #1. Say 'Hello from agent 1'"
            )
            agent1_id = result.get("data", {}).get("agent_id")
            print(f"✓ Spawned {agent1_id}")
        except Exception as e:
            print(f"✗ Failed: {e}")
            return
        
        # Test 2: Spawn second agent
        print("\n2. Spawning second agent (after cooldown)...")
        await asyncio.sleep(0.6)  # Wait for cooldown
        try:
            result = await ctx.spawn_agent(
                profile="base_single_agent",
                prompt="You are agent #2. Say 'Hello from agent 2'"
            )
            agent2_id = result.get("data", {}).get("agent_id")
            print(f"✓ Spawned {agent2_id}")
        except Exception as e:
            print(f"✗ Failed: {e}")
        
        # Test 3: Spawn third agent (should succeed)
        print("\n3. Spawning third agent (after cooldown)...")
        await asyncio.sleep(0.6)  # Wait for cooldown
        try:
            result = await ctx.spawn_agent(
                profile="base_single_agent",
                prompt="You are agent #3. Say 'Hello from agent 3'"
            )
            agent3_id = result.get("data", {}).get("agent_id")
            print(f"✓ Spawned {agent3_id}")
        except Exception as e:
            print(f"✗ Failed: {e}")
        
        # Test 4: Try to spawn fourth agent (should fail)
        print("\n4. Trying to spawn fourth agent (should fail due to limit)...")
        await asyncio.sleep(0.6)  # Wait for cooldown
        try:
            result = await ctx.spawn_agent(
                profile="base_single_agent",
                prompt="You are agent #4"
            )
            print(f"✗ Unexpected success!")
        except RuntimeError as e:
            print(f"✓ Expected failure: {e}")
        
        # Test 5: Check spawn tree
        print("\n5. Safety Report:")
        report = safety.get_safety_report()
        print(json.dumps(report, indent=2))
        
        # Test 6: Test rate limiting
        print("\n6. Testing rate limiting...")
        try:
            # Terminate one to make room
            await safety.terminate_agent(agent1_id, "Making room for rate limit test")
            await asyncio.sleep(0.1)
            
            # Try rapid spawns
            print("  Attempting rapid spawns...")
            await ctx.spawn_agent(
                profile="base_single_agent",
                prompt="Rapid spawn 1"
            )
            # This should fail due to cooldown
            await ctx.spawn_agent(
                profile="base_single_agent",
                prompt="Rapid spawn 2"
            )
            print("✗ Rate limiting not working!")
        except RuntimeError as e:
            print(f"✓ Rate limiting working: {e}")
        
        # Wait a bit
        print("\n7. Letting agents run for 10 seconds...")
        await asyncio.sleep(10)
        
        # Final report
        print("\n8. Final Safety Report:")
        report = safety.get_safety_report()
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(test_safety_controlled())