#!/usr/bin/env python3
"""Test advanced composition features are working correctly."""

import asyncio
import json

async def test_composition_features():
    """Test all advanced composition features."""
    import subprocess
    
    print("Testing Advanced Composition Features\n")
    print("=" * 50)
    
    # Test 1: composition:select
    print("\n1. Testing composition:select...")
    cmd = ['echo', json.dumps({
        "event": "composition:select",
        "data": {
            "agent_id": "test_agent_1",
            "role": "researcher",
            "capabilities": ["information_gathering", "fact_checking"],
            "task": "Research the history of artificial intelligence",
            "max_suggestions": 3
        }
    })]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    p = subprocess.Popen(['nc', '-U', 'var/run/daemon.sock'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    output, _ = p.communicate(result.stdout)
    response = json.loads(output.strip())
    
    if response.get("data", {}).get("status") == "success":
        print("✓ composition:select working")
        print(f"  Selected: {response['data']['selected']} (score: {response['data']['score']})")
        print(f"  Reasons: {response['data']['reasons']}")
    else:
        print("✗ composition:select failed:", response)
    
    # Test 2: composition:create
    print("\n2. Testing composition:create...")
    cmd = ['echo', json.dumps({
        "event": "composition:create",
        "data": {
            "name": "test_dynamic_comp",
            "type": "profile",
            "role": "analyst",
            "model": "sonnet",
            "capabilities": ["data_analysis", "visualization"],
            "prompt": "You are a specialized data analyst.",
            "metadata": {
                "self_modifiable": True,
                "spawns_agents": False
            }
        }
    })]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    p = subprocess.Popen(['nc', '-U', 'var/run/daemon.sock'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    output, _ = p.communicate(result.stdout)
    response = json.loads(output.strip())
    
    if response.get("data", {}).get("status") == "success":
        print("✓ composition:create working")
        print(f"  Created: {response['data']['name']}")
        print(f"  Type: {response['data']['composition']['type']}")
    else:
        print("✗ composition:create failed:", response)
    
    # Test 3: agent:spawn with dynamic mode
    print("\n3. Testing agent:spawn with dynamic mode...")
    cmd = ['echo', json.dumps({
        "event": "agent:spawn",
        "data": {
            "agent_id": "test_dynamic_agent",
            "spawn_mode": "dynamic",
            "selection_context": {
                "role": "analyzer",
                "task": "Analyze market trends",
                "required_capabilities": ["data_analysis", "pattern_recognition"]
            },
            "task": "Analyze cryptocurrency market trends"
        }
    })]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    p = subprocess.Popen(['nc', '-U', 'var/run/daemon.sock'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    output, _ = p.communicate(result.stdout)
    response = json.loads(output.strip())
    
    if response.get("data", {}).get("status") == "created":
        print("✓ agent:spawn with dynamic mode working")
        print(f"  Agent ID: {response['data']['agent_id']}")
        print(f"  Composition: {response['data']['composition']}")
        if '_composition_selection' in response['data']:
            sel = response['data']['_composition_selection']
            print(f"  Selected: {sel['selected']} (score: {sel['score']})")
    else:
        print("✗ agent:spawn with dynamic mode failed:", response)
    
    # Test 4: agent:discover_peers
    print("\n4. Testing agent:discover_peers...")
    cmd = ['echo', json.dumps({
        "event": "agent:discover_peers",
        "data": {
            "agent_id": "test_dynamic_agent",
            "capabilities": ["data_analysis"]
        }
    })]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    p = subprocess.Popen(['nc', '-U', 'var/run/daemon.sock'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    output, _ = p.communicate(result.stdout)
    response = json.loads(output.strip())
    
    if response.get("data", {}).get("status") == "success":
        print("✓ agent:discover_peers working")
        print(f"  Found {response['data']['discovered_count']} peers")
    else:
        print("✗ agent:discover_peers failed:", response)
    
    # Test 5: agent:update_composition (will fail without self_modifiable agent)
    print("\n5. Testing agent:update_composition...")
    cmd = ['echo', json.dumps({
        "event": "agent:update_composition",
        "data": {
            "agent_id": "test_dynamic_agent",
            "new_composition": "debater",
            "reason": "Testing composition update"
        }
    })]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    p = subprocess.Popen(['nc', '-U', 'var/run/daemon.sock'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    output, _ = p.communicate(result.stdout)
    response = json.loads(output.strip())
    
    if response.get("data", {}).get("status") == "updated":
        print("✓ agent:update_composition working")
        print(f"  New composition: {response['data']['new_composition']}")
    elif "does not allow self-modification" in response.get("data", {}).get("error", ""):
        print("✓ agent:update_composition working (correctly denied - composition not self-modifiable)")
    else:
        print("✗ agent:update_composition failed:", response)
    
    # Cleanup
    print("\n6. Cleaning up test agent...")
    cmd = ['echo', json.dumps({
        "event": "agent:terminate",
        "data": {"agent_id": "test_dynamic_agent"}
    })]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    p = subprocess.Popen(['nc', '-U', 'var/run/daemon.sock'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    output, _ = p.communicate(result.stdout)
    
    print("\n" + "=" * 50)
    print("Advanced Composition Features Test Complete!")


if __name__ == "__main__":
    asyncio.run(test_composition_features())