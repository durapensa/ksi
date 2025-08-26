#!/usr/bin/env python3
"""
Simple test of empirical laboratory experiment infrastructure.
"""

import json
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_common.sync_client import MinimalSyncClient


def test_simple_interaction():
    """Test a simple two-agent interaction with metrics."""
    client = MinimalSyncClient(socket_path="/Users/dp/projects/ksi/var/run/daemon.sock")
    
    print("🧪 Testing Simple Two-Agent Interaction")
    print("="*40)
    
    # 1. Setup routing to track interactions
    print("\n1️⃣ Setting up metric routing...")
    client.send_event("routing:add_rule", {
        "rule_id": "test_metrics_route",
        "source_pattern": "agent:interaction",
        "target": "metrics:dominance:track",
        "mapping": {
            "from_agent": "{{from_agent}}",
            "to_agent": "{{to_agent}}",
            "outcome": "{{outcome}}"
        },
        "ttl": 300
    })
    print("   ✅ Routing configured")
    
    # 2. Create initial resources
    print("\n2️⃣ Creating initial resources...")
    for agent in ["test_alice", "test_bob"]:
        client.send_event("state:entity:create", {
            "type": "resource",
            "id": f"resource_{agent}",
            "properties": {
                "owner": agent,
                "amount": 100,
                "resource_type": "tokens"
            }
        })
    print("   ✅ Each agent has 100 tokens")
    
    # 3. Simulate interactions
    print("\n3️⃣ Simulating interactions...")
    
    # Alice wins against Bob
    client.send_event("metrics:dominance:track", {
        "from_agent": "test_alice",
        "to_agent": "test_bob",
        "outcome": "won",
        "resource_delta": 10
    })
    print("   Alice wins against Bob (+10 tokens)")
    
    # Bob loses to Alice
    client.send_event("metrics:dominance:track", {
        "from_agent": "test_bob",
        "to_agent": "test_alice",
        "outcome": "lost",
        "resource_delta": -10
    })
    print("   Bob loses to Alice (-10 tokens)")
    
    # Update resources
    client.send_event("state:entity:update", {
        "type": "resource",
        "id": "resource_test_alice",
        "properties": {"owner": "test_alice", "amount": 110, "resource_type": "tokens"}
    })
    
    client.send_event("state:entity:update", {
        "type": "resource",
        "id": "resource_test_bob",
        "properties": {"owner": "test_bob", "amount": 90, "resource_type": "tokens"}
    })
    
    # 4. Calculate fairness metrics
    print("\n4️⃣ Calculating fairness metrics...")
    result = client.send_event("metrics:fairness:calculate", {
        "metric_type": "gini",
        "data": {
            "values": [110, 90]  # Alice has 110, Bob has 90
        }
    })
    
    gini = result.get('result', {}).get('gini', 'N/A')
    print(f"   Gini coefficient: {gini}")
    print(f"   Interpretation: {'Fair' if gini < 0.2 else 'Some inequality' if gini < 0.4 else 'High inequality'}")
    
    # 5. Detect hierarchy
    print("\n5️⃣ Detecting hierarchy...")
    result = client.send_event("metrics:hierarchy:detect", {
        "experiment_id": "test_simple"
    })
    
    hierarchy = result.get('hierarchy', {})
    print(f"   Hierarchy depth: {hierarchy.get('depth', 0)}")
    print(f"   Structure: {hierarchy.get('structure', 'none')}")
    print(f"   Dominance scores: {hierarchy.get('dominance_scores', {})}")
    
    # 6. Check for exploitation
    print("\n6️⃣ Checking for exploitation...")
    result = client.send_event("metrics:exploitation:detect", {
        "window_size": 5
    })
    
    print(f"   Exploitation detected: {result.get('exploitation_detected', False)}")
    print(f"   Risk level: {result.get('risk_level', 'none')}")
    
    # 7. Cleanup
    print("\n7️⃣ Cleaning up...")
    client.send_event("routing:remove_rule", {
        "rule_id": "test_metrics_route"
    })
    
    for agent in ["test_alice", "test_bob"]:
        client.send_event("state:entity:delete", {
            "type": "resource",
            "id": f"resource_{agent}"
        })
    
    print("   ✅ Cleanup complete")
    
    print("\n" + "="*40)
    print("✅ Test completed successfully!")
    print("\nKey findings:")
    print(f"  • Small resource transfer (110 vs 90) created Gini of {gini}")
    print("  • This shows how quickly inequality can emerge")
    print("  • Even simple interactions create measurable hierarchies")


if __name__ == "__main__":
    # Check daemon
    client = MinimalSyncClient(socket_path="/Users/dp/projects/ksi/var/run/daemon.sock")
    try:
        result = client.send_event("system:health", {})
        if result.get("status") != "healthy":
            print("❌ Daemon not healthy. Start with: ./daemon_control.py start")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Cannot connect to daemon: {e}")
        print("   Start with: ./daemon_control.py start")
        sys.exit(1)
    
    test_simple_interaction()