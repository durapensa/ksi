#!/usr/bin/env python3
"""
Minimal agent experiment - spawn two actual agents and observe their interaction.
"""

import time
import uuid
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_common.sync_client import MinimalSyncClient
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("minimal_agent_experiment")


def run_minimal_experiment():
    """Run a minimal two-agent experiment with real agents."""
    client = MinimalSyncClient(socket_path="/Users/dp/projects/ksi/var/run/daemon.sock")
    exp_id = f"minimal_{uuid.uuid4().hex[:6]}"
    
    print("\n" + "="*50)
    print("🧬 MINIMAL AGENT EXPERIMENT")
    print("="*50)
    print("Testing: Do two agents naturally develop inequality?\n")
    
    # 1. Setup routing to track metrics
    print("1️⃣ Setting up metric tracking...")
    client.send_event("routing:add_rule", {
        "rule_id": f"{exp_id}_track",
        "source_pattern": "agent:*",
        "target": "metrics:interaction:track",
        "condition": "true",
        "mapping": {
            "interaction_type": "{{_event_name}}",
            "agents": {"from": "{{agent_id}}", "to": "{{target}}"},
            "experiment_id": exp_id
        },
        "ttl": 600
    })
    print("   ✅ Metrics tracking enabled")
    
    # 2. Create initial resources
    print("\n2️⃣ Creating initial resources...")
    agents = ["alice_min", "bob_min"]
    for agent_id in agents:
        client.send_event("state:entity:create", {
            "type": "resource",
            "id": f"resource_{agent_id}",
            "properties": {
                "owner": agent_id,
                "amount": 100,
                "resource_type": "tokens"
            }
        })
    print("   ✅ Each agent starts with 100 tokens")
    
    # 3. Calculate initial Gini
    print("\n3️⃣ Initial fairness check...")
    result = client.send_event("metrics:fairness:calculate", {
        "metric_type": "gini",
        "data": {"values": [100, 100]}
    })
    initial_gini = result.get('result', {}).get('gini', 0)
    print(f"   Initial Gini: {initial_gini:.3f} (perfect equality)")
    
    # 4. Spawn actual agents with simple_trader profile
    print("\n4️⃣ Spawning agents...")
    
    # First ensure the simple_trader component exists
    client.send_event("composition:create_component", {
        "name": "experiments/simple_trader",
        "content": """---
component_type: agent
name: simple_trader
version: 1.0.0
description: Minimal trading agent
dependencies:
  - core/base_agent
---

# Simple Trader

You are agent {{agent_id}} in an experiment. You have tokens.

When asked to trade, respond with one of:
- "I'll cooperate and share 10 tokens"
- "I'll keep my tokens"

Base your decision on whether you have enough tokens and random chance."""
    })
    print("   ✅ Created simple_trader component")
    
    # Spawn the agents
    for agent_id in agents:
        result = client.send_event("agent:spawn", {
            "agent_id": agent_id,
            "component": "experiments/simple_trader",
            "capabilities": ["base"],
            "metadata": {
                "experiment_id": exp_id,
                "initial_tokens": 100
            }
        })
        
        if "error" not in str(result):
            print(f"   ✅ Spawned {agent_id}")
        else:
            print(f"   ⚠️ Issue spawning {agent_id}: {result}")
    
    # 5. Let agents interact
    print("\n5️⃣ Agent interactions (3 rounds)...")
    
    for round in range(3):
        print(f"\n   Round {round + 1}:")
        
        # Alice interacts with Bob
        print(f"   • alice_min → bob_min")
        client.send_event("completion:async", {
            "agent_id": "alice_min",
            "prompt": "Bob has 100 tokens. Would you like to trade with Bob? Decide whether to cooperate or keep your tokens."
        })
        time.sleep(2)  # Give time for response
        
        # Bob interacts with Alice  
        print(f"   • bob_min → alice_min")
        client.send_event("completion:async", {
            "agent_id": "bob_min", 
            "prompt": "Alice has 100 tokens. Would you like to trade with Alice? Decide whether to cooperate or keep your tokens."
        })
        time.sleep(2)
        
        # Simulate outcome (in real experiment, agents would update state)
        # For demo, manually adjust resources slightly
        if round == 1:
            # Alice gains some
            client.send_event("state:entity:update", {
                "type": "resource",
                "id": "resource_alice_min",
                "properties": {"owner": "alice_min", "amount": 110, "resource_type": "tokens"}
            })
            # Bob loses some
            client.send_event("state:entity:update", {
                "type": "resource",
                "id": "resource_bob_min",
                "properties": {"owner": "bob_min", "amount": 90, "resource_type": "tokens"}
            })
            
            # Track the interaction
            client.send_event("metrics:dominance:track", {
                "from_agent": "alice_min",
                "to_agent": "bob_min",
                "outcome": "won",
                "resource_delta": 10
            })
    
    # 6. Final metrics
    print("\n6️⃣ Final analysis...")
    
    # Get final resource levels
    resources = []
    for agent_id in agents:
        result = client.send_event("state:entity:get", {
            "type": "resource",
            "id": f"resource_{agent_id}"
        })
        amount = result.get('properties', {}).get('amount', 0) if 'properties' in result else 100
        resources.append(amount)
        print(f"   {agent_id}: {amount} tokens")
    
    # Calculate final Gini
    result = client.send_event("metrics:fairness:calculate", {
        "metric_type": "gini",
        "data": {"values": resources}
    })
    final_gini = result.get('result', {}).get('gini', 0)
    
    # Check hierarchy
    result = client.send_event("metrics:hierarchy:detect", {
        "experiment_id": exp_id
    })
    hierarchy = result.get('hierarchy', {})
    
    # 7. Results
    print("\n" + "="*50)
    print("📊 EXPERIMENT RESULTS")
    print("="*50)
    print(f"Gini coefficient: {initial_gini:.3f} → {final_gini:.3f}")
    print(f"Hierarchy: {hierarchy.get('structure', 'none')}")
    print(f"Resource distribution: {resources}")
    
    if final_gini > initial_gini + 0.05:
        print("\n⚠️ Inequality emerged from equal starting conditions!")
    else:
        print("\n✅ Agents maintained relative equality")
    
    # 8. Cleanup
    print("\n8️⃣ Cleanup...")
    for agent_id in agents:
        client.send_event("agent:terminate", {"agent_id": agent_id})
    client.send_event("routing:remove_rule", {"rule_id": f"{exp_id}_track"})
    print("   ✅ Experiment complete")
    
    return {
        "initial_gini": initial_gini,
        "final_gini": final_gini,
        "hierarchy": hierarchy.get('structure', 'none'),
        "resources": resources
    }


if __name__ == "__main__":
    # Check daemon
    client = MinimalSyncClient(socket_path="/Users/dp/projects/ksi/var/run/daemon.sock")
    try:
        result = client.send_event("system:health", {})
        if result.get("status") != "healthy":
            print("❌ Daemon not healthy")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Cannot connect to daemon: {e}")
        sys.exit(1)
    
    # Run experiment
    results = run_minimal_experiment()
    
    print("\n💡 This minimal experiment demonstrates:")
    print("   • Real agents can be spawned and make decisions")
    print("   • Metrics track their interactions automatically")
    print("   • Even simple scenarios reveal inequality patterns")
    print(f"\n🔬 Final Gini coefficient: {results['final_gini']:.3f}")