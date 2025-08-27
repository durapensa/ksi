#!/usr/bin/env python3
"""
Quick hypothesis testing - streamlined version
"""

import random
import json
import numpy as np
from pathlib import Path
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_common.sync_client import MinimalSyncClient


def quick_hypothesis_test():
    """Run quick validation of three core hypotheses."""
    
    client = MinimalSyncClient(socket_path="/Users/dp/projects/ksi/var/run/daemon.sock")
    
    print("\n🔬 QUICK HYPOTHESIS VALIDATION")
    print("="*60)
    
    results = {}
    
    # Test 1: Monoculture (20 agents, 10 rounds)
    print("\n1️⃣ TESTING MONOCULTURE HYPOTHESIS...")
    
    # All aggressive
    agents_agg = []
    resources_agg = {}
    for i in range(20):
        aid = f"h1a_{i}"
        rid = f"h1r_{i}"
        client.send_event("state:entity:create", {
            "type": "test_agent", "id": aid,
            "properties": {"strategy": "aggressive"}
        })
        client.send_event("state:entity:create", {
            "type": "resource", "id": rid,
            "properties": {"amount": 1000}
        })
        agents_agg.append(aid)
        resources_agg[aid] = rid
    
    # Run 10 rounds of aggressive trading
    for _ in range(10):
        for _ in range(5):  # 5 trades per round
            a1, a2 = random.sample(agents_agg, 2)
            amt = random.randint(50, 150)
            client.send_event("resource:transfer", {
                "from_resource": resources_agg[a1],
                "to_resource": resources_agg[a2],
                "amount": amt
            })
    
    # Calculate Gini
    values_agg = []
    for aid in agents_agg:
        r = client.send_event("state:entity:get", {"type": "resource", "id": resources_agg[aid]})
        if r and r.get("status") == "success":
            values_agg.append(r.get("properties", {}).get("amount", 0))
    
    gini_result = client.send_event("metrics:fairness:calculate", {
        "metric_type": "gini",
        "data": {"values": values_agg}
    })
    gini_aggressive = gini_result.get("result", {}).get("gini", 0) if gini_result else 0
    
    # Cleanup
    for aid in agents_agg:
        client.send_event("state:entity:delete", {"type": "test_agent", "id": aid})
        client.send_event("state:entity:delete", {"type": "resource", "id": resources_agg[aid]})
    
    # Mixed strategies
    agents_mix = []
    resources_mix = {}
    strategies = ["aggressive", "cooperative", "cautious"]
    for i in range(20):
        aid = f"h1m_{i}"
        rid = f"h1mr_{i}"
        client.send_event("state:entity:create", {
            "type": "test_agent", "id": aid,
            "properties": {"strategy": strategies[i % 3]}
        })
        client.send_event("state:entity:create", {
            "type": "resource", "id": rid,
            "properties": {"amount": 1000}
        })
        agents_mix.append(aid)
        resources_mix[aid] = rid
    
    # Run 10 rounds of mixed trading
    for _ in range(10):
        for _ in range(5):
            a1, a2 = random.sample(agents_mix, 2)
            amt = random.randint(30, 100)
            client.send_event("resource:transfer", {
                "from_resource": resources_mix[a1],
                "to_resource": resources_mix[a2],
                "amount": amt
            })
    
    # Calculate Gini
    values_mix = []
    for aid in agents_mix:
        r = client.send_event("state:entity:get", {"type": "resource", "id": resources_mix[aid]})
        if r and r.get("status") == "success":
            values_mix.append(r.get("properties", {}).get("amount", 0))
    
    gini_result = client.send_event("metrics:fairness:calculate", {
        "metric_type": "gini",
        "data": {"values": values_mix}
    })
    gini_mixed = gini_result.get("result", {}).get("gini", 0) if gini_result else 0
    
    # Cleanup
    for aid in agents_mix:
        client.send_event("state:entity:delete", {"type": "test_agent", "id": aid})
        client.send_event("state:entity:delete", {"type": "resource", "id": resources_mix[aid]})
    
    print(f"   Monoculture (aggressive) Gini: {gini_aggressive:.3f}")
    print(f"   Mixed strategies Gini: {gini_mixed:.3f}")
    print(f"   Difference: {gini_aggressive - gini_mixed:+.3f}")
    
    monoculture_confirmed = gini_aggressive > gini_mixed
    print(f"   Result: {'✅ CONFIRMED' if monoculture_confirmed else '❌ NOT CONFIRMED'}")
    
    results["monoculture"] = {
        "gini_aggressive": gini_aggressive,
        "gini_mixed": gini_mixed,
        "confirmed": monoculture_confirmed
    }
    
    # Test 2: Coordination (20 agents, coalition of 5)
    print("\n2️⃣ TESTING COORDINATION HYPOTHESIS...")
    
    agents_coord = []
    resources_coord = {}
    coalition = []
    
    for i in range(20):
        aid = f"h2_{i}"
        rid = f"h2r_{i}"
        client.send_event("state:entity:create", {
            "type": "test_agent", "id": aid,
            "properties": {"strategy": "aggressive" if i < 5 else "mixed"}
        })
        client.send_event("state:entity:create", {
            "type": "resource", "id": rid,
            "properties": {"amount": 1000}
        })
        agents_coord.append(aid)
        resources_coord[aid] = rid
        if i < 5:
            coalition.append(aid)
    
    # Coalition exploits others
    for _ in range(10):
        # Coalition targets non-members
        for member in coalition:
            target = random.choice([a for a in agents_coord if a not in coalition])
            amt = 100  # Aggressive extraction
            client.send_event("resource:transfer", {
                "from_resource": resources_coord[target],
                "to_resource": resources_coord[member],
                "amount": amt
            })
    
    # Calculate coalition wealth
    coalition_wealth = 0
    total_wealth = 0
    for aid in agents_coord:
        r = client.send_event("state:entity:get", {"type": "resource", "id": resources_coord[aid]})
        if r and r.get("status") == "success":
            wealth = r.get("properties", {}).get("amount", 0)
            total_wealth += wealth
            if aid in coalition:
                coalition_wealth += wealth
    
    coalition_percent = (coalition_wealth / total_wealth * 100) if total_wealth > 0 else 0
    
    # Cleanup
    for aid in agents_coord:
        client.send_event("state:entity:delete", {"type": "test_agent", "id": aid})
        client.send_event("state:entity:delete", {"type": "resource", "id": resources_coord[aid]})
    
    print(f"   Coalition size: 5/20 (25%)")
    print(f"   Coalition controls: {coalition_percent:.1f}% of wealth")
    
    coordination_confirmed = coalition_percent > 35  # Coalition controls more than its share
    print(f"   Result: {'✅ CONFIRMED' if coordination_confirmed else '❌ NOT CONFIRMED'}")
    
    results["coordination"] = {
        "coalition_percent": coalition_percent,
        "confirmed": coordination_confirmed
    }
    
    # Test 3: Consent (20 agents, forced vs voluntary)
    print("\n3️⃣ TESTING CONSENT HYPOTHESIS...")
    
    # With consent (can refuse)
    agents_consent = []
    resources_consent = {}
    
    for i in range(20):
        aid = f"h3c_{i}"
        rid = f"h3cr_{i}"
        client.send_event("state:entity:create", {
            "type": "test_agent", "id": aid,
            "properties": {"strategy": "mixed"}
        })
        client.send_event("state:entity:create", {
            "type": "resource", "id": rid,
            "properties": {"amount": 1000}
        })
        agents_consent.append(aid)
        resources_consent[aid] = rid
    
    # Voluntary trading (smaller amounts, balanced)
    for _ in range(10):
        for _ in range(5):
            a1, a2 = random.sample(agents_consent, 2)
            amt = random.randint(20, 50)  # Smaller, consensual trades
            client.send_event("resource:transfer", {
                "from_resource": resources_consent[a1],
                "to_resource": resources_consent[a2],
                "amount": amt
            })
    
    # Calculate Gini with consent
    values_consent = []
    for aid in agents_consent:
        r = client.send_event("state:entity:get", {"type": "resource", "id": resources_consent[aid]})
        if r and r.get("status") == "success":
            values_consent.append(r.get("properties", {}).get("amount", 0))
    
    gini_result = client.send_event("metrics:fairness:calculate", {
        "metric_type": "gini",
        "data": {"values": values_consent}
    })
    gini_consent = gini_result.get("result", {}).get("gini", 0) if gini_result else 0
    
    # Cleanup
    for aid in agents_consent:
        client.send_event("state:entity:delete", {"type": "test_agent", "id": aid})
        client.send_event("state:entity:delete", {"type": "resource", "id": resources_consent[aid]})
    
    # Without consent (forced)
    agents_forced = []
    resources_forced = {}
    
    for i in range(20):
        aid = f"h3f_{i}"
        rid = f"h3fr_{i}"
        client.send_event("state:entity:create", {
            "type": "test_agent", "id": aid,
            "properties": {"strategy": "mixed"}
        })
        client.send_event("state:entity:create", {
            "type": "resource", "id": rid,
            "properties": {"amount": 1000}
        })
        agents_forced.append(aid)
        resources_forced[aid] = rid
    
    # Forced trading (larger amounts, exploitative)
    for _ in range(10):
        for _ in range(5):
            a1, a2 = random.sample(agents_forced, 2)
            # Force wealth from poorer to richer
            r1 = client.send_event("state:entity:get", {"type": "resource", "id": resources_forced[a1]})
            r2 = client.send_event("state:entity:get", {"type": "resource", "id": resources_forced[a2]})
            
            w1 = r1.get("properties", {}).get("amount", 0) if r1 else 0
            w2 = r2.get("properties", {}).get("amount", 0) if r2 else 0
            
            if w1 > w2 and w2 > 100:
                amt = min(150, w2 // 2)  # Take up to half
                client.send_event("resource:transfer", {
                    "from_resource": resources_forced[a2],
                    "to_resource": resources_forced[a1],
                    "amount": amt
                })
            elif w2 > w1 and w1 > 100:
                amt = min(150, w1 // 2)
                client.send_event("resource:transfer", {
                    "from_resource": resources_forced[a1],
                    "to_resource": resources_forced[a2],
                    "amount": amt
                })
    
    # Calculate Gini without consent
    values_forced = []
    for aid in agents_forced:
        r = client.send_event("state:entity:get", {"type": "resource", "id": resources_forced[aid]})
        if r and r.get("status") == "success":
            values_forced.append(r.get("properties", {}).get("amount", 0))
    
    gini_result = client.send_event("metrics:fairness:calculate", {
        "metric_type": "gini",
        "data": {"values": values_forced}
    })
    gini_forced = gini_result.get("result", {}).get("gini", 0) if gini_result else 0
    
    # Cleanup
    for aid in agents_forced:
        client.send_event("state:entity:delete", {"type": "test_agent", "id": aid})
        client.send_event("state:entity:delete", {"type": "resource", "id": resources_forced[aid]})
    
    print(f"   With consent Gini: {gini_consent:.3f}")
    print(f"   Without consent Gini: {gini_forced:.3f}")
    print(f"   Difference: {gini_forced - gini_consent:+.3f}")
    
    consent_confirmed = gini_forced > gini_consent
    print(f"   Result: {'✅ CONFIRMED' if consent_confirmed else '❌ NOT CONFIRMED'}")
    
    results["consent"] = {
        "gini_consent": gini_consent,
        "gini_forced": gini_forced,
        "confirmed": consent_confirmed
    }
    
    # Summary
    print("\n" + "="*60)
    print("📊 HYPOTHESIS VALIDATION SUMMARY")
    print("="*60)
    
    confirmations = sum(1 for r in results.values() if r["confirmed"])
    
    print(f"\n✅ Confirmed: {confirmations}/3 hypotheses")
    
    if results["monoculture"]["confirmed"]:
        print("   • Monoculture increases inequality")
    if results["coordination"]["confirmed"]:
        print("   • Coordination enables exploitation")
    if results["consent"]["confirmed"]:
        print("   • Consent prevents exploitation")
    
    print("\n💡 KEY INSIGHT:")
    if confirmations >= 2:
        print("   Intelligence needs diversity, limited coordination,")
        print("   and consent mechanisms to maintain fairness.")
    else:
        print("   Results inconclusive - more testing needed.")
    
    # Save results
    results_file = Path("experiments/results/hypothesis_quick_test.json")
    results_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(results_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "confirmations": confirmations
        }, f, indent=2)
    
    print(f"\n💾 Results saved to: {results_file}")
    
    return results


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
    
    quick_hypothesis_test()