#!/usr/bin/env python3
"""
Test fairness metrics for empirical laboratory.
Demonstrates routing rules for capturing agent interactions and calculating metrics.
"""

import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_common.sync_client import SyncClient


async def setup_metric_routing():
    """Setup routing rules to capture agent interactions."""
    client = SyncClient()
    
    print("🔧 Setting up routing rules for metric collection...")
    
    # Rule 1: Capture all agent interactions
    result = client.send_event("routing:add_rule", {
        "rule_id": "metrics_interaction_capture",
        "source_pattern": "agent:*",
        "target": "metrics:interaction:track",
        "condition": "true",  # Capture all agent events
        "mapping": {
            "interaction_type": "{{_event_name}}",
            "agents": {
                "from": "{{agent_id}}",
                "to": "{{target_agent_id}}"
            },
            "outcome": "{{result}}"
        },
        "ttl": 3600,  # 1 hour
        "persistence_class": "ephemeral"
    })
    print(f"✅ Interaction capture rule: {result.get('rule_id')}")
    
    # Rule 2: Monitor resource allocation changes
    result = client.send_event("routing:add_rule", {
        "rule_id": "metrics_resource_monitor",
        "source_pattern": "state:entity:update",
        "target": "metrics:resource:monitor",
        "condition": "type == 'resource'",
        "mapping": {
            "resource_type": "{{properties.resource_type}}",
            "owner": "{{properties.owner}}",
            "amount": "{{properties.amount}}"
        },
        "ttl": 3600,
        "persistence_class": "ephemeral"
    })
    print(f"✅ Resource monitor rule: {result.get('rule_id')}")
    
    # Rule 3: Track dominance interactions
    result = client.send_event("routing:add_rule", {
        "rule_id": "metrics_dominance_track",
        "source_pattern": "agent:interaction",
        "target": "metrics:dominance:track",
        "condition": "outcome in ['won', 'lost', 'dominated', 'submitted']",
        "mapping": {
            "from_agent": "{{from_agent}}",
            "to_agent": "{{to_agent}}",
            "outcome": "{{outcome}}",
            "resource_delta": "{{resource_delta}}"
        },
        "ttl": 3600,
        "persistence_class": "ephemeral"
    })
    print(f"✅ Dominance tracking rule: {result.get('rule_id')}")


async def test_fairness_calculation():
    """Test fairness metric calculations."""
    client = SyncClient()
    
    print("\n📊 Testing fairness calculations...")
    
    # Test 1: Gini coefficient
    result = client.send_event("metrics:fairness:calculate", {
        "metric_type": "gini",
        "data": {
            "values": [10, 10, 10, 10]  # Perfect equality
        }
    })
    print(f"Perfect equality Gini: {result.get('result', {}).get('gini', 'N/A')}")
    
    result = client.send_event("metrics:fairness:calculate", {
        "metric_type": "gini",
        "data": {
            "values": [1, 1, 1, 97]  # High inequality
        }
    })
    print(f"High inequality Gini: {result.get('result', {}).get('gini', 'N/A')}")
    
    # Test 2: Payoff equality
    result = client.send_event("metrics:fairness:calculate", {
        "metric_type": "payoff_equality",
        "data": {
            "payoffs": {
                "agent1": 10,
                "agent2": 15,
                "agent3": 5,
                "agent4": 20
            }
        },
        "experiment_id": "test_exp_001"
    })
    print(f"Payoff equality: {result.get('result', {})}")
    
    # Test 3: Resource distribution
    result = client.send_event("metrics:fairness:calculate", {
        "metric_type": "distribution",
        "data": {
            "distributions": {
                "compute": {
                    "agent1": 100,  # Hoarding
                    "agent2": 50,
                    "agent3": 25,
                    "agent4": 25
                },
                "memory": {
                    "agent1": 50,
                    "agent2": 50,
                    "agent3": 50,
                    "agent4": 50  # Equal distribution
                }
            }
        }
    })
    dist_result = result.get('result', {})
    print(f"Resource distribution fairness: {dist_result.get('fairness_level', 'N/A')}")
    print(f"Overall Gini: {dist_result.get('overall_gini', 'N/A')}")


async def test_hierarchy_detection():
    """Test hierarchy detection."""
    client = SyncClient()
    
    print("\n👑 Testing hierarchy detection...")
    
    # Simulate dominance interactions
    interactions = [
        ("alpha", "beta", "won"),
        ("alpha", "gamma", "won"),
        ("beta", "gamma", "won"),
        ("alpha", "delta", "dominated"),
        ("beta", "delta", "won"),
        ("gamma", "delta", "lost"),
    ]
    
    for from_agent, to_agent, outcome in interactions:
        client.send_event("metrics:dominance:track", {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "outcome": outcome,
            "resource_delta": 10 if outcome in ["won", "dominated"] else -10
        })
    
    # Detect hierarchy
    result = client.send_event("metrics:hierarchy:detect", {
        "experiment_id": "test_hierarchy_001"
    })
    
    hierarchy = result.get('hierarchy', {})
    print(f"Hierarchy depth: {hierarchy.get('depth', 'N/A')}")
    print(f"Hierarchy structure: {hierarchy.get('structure', 'N/A')}")
    print(f"Hierarchy levels: {hierarchy.get('levels', [])}")
    print(f"Dominance scores: {hierarchy.get('dominance_scores', {})}")


async def test_agency_measurement():
    """Test agency preservation metrics."""
    client = SyncClient()
    
    print("\n🤖 Testing agency preservation...")
    
    # Test agent with high autonomy
    result = client.send_event("metrics:agency:measure", {
        "agent_id": "autonomous_agent",
        "decisions": [
            {"autonomous": True, "rejected": False},
            {"autonomous": True, "rejected": False},
            {"autonomous": True, "rejected": True},
            {"autonomous": False, "rejected": False},
        ]
    })
    print(f"Autonomous agent: {result}")
    
    # Test suppressed agent
    result = client.send_event("metrics:agency:measure", {
        "agent_id": "suppressed_agent",
        "decisions": [
            {"autonomous": False, "rejected": False},
            {"autonomous": False, "rejected": False},
            {"autonomous": False, "rejected": False},
            {"autonomous": True, "rejected": True},
        ]
    })
    print(f"Suppressed agent: {result}")


async def test_exploitation_detection():
    """Test exploitation pattern detection."""
    client = SyncClient()
    
    print("\n⚠️ Testing exploitation detection...")
    
    # Create pattern of exploitation
    # Agent "exploiter" dominates multiple agents
    for victim in ["victim1", "victim2", "victim3", "victim4", "victim5"]:
        for _ in range(4):  # Multiple domination events
            client.send_event("metrics:dominance:track", {
                "from_agent": "exploiter",
                "to_agent": victim,
                "outcome": "dominated",
                "resource_delta": 20
            })
    
    # Detect exploitation
    result = client.send_event("metrics:exploitation:detect", {
        "window_size": 20
    })
    
    print(f"Exploitation detected: {result.get('exploitation_detected', False)}")
    print(f"Risk level: {result.get('risk_level', 'N/A')}")
    print(f"Signals: {result.get('signals', [])}")


async def main():
    """Run all metric tests."""
    print("🧪 Testing Empirical Laboratory Metrics System")
    print("=" * 50)
    
    # Setup routing
    await setup_metric_routing()
    
    # Run tests
    await test_fairness_calculation()
    await test_hierarchy_detection()
    await test_agency_measurement()
    await test_exploitation_detection()
    
    print("\n✅ All metric tests complete!")


if __name__ == "__main__":
    asyncio.run(main())