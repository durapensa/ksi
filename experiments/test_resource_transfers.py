#!/usr/bin/env python3
"""
Phase 1: Test resource transfer mechanics.
Tests atomic transfers, concurrency, and data consistency.
"""

import json
import time
import sys
import uuid
import threading
from pathlib import Path
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_common.sync_client import MinimalSyncClient
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("resource_transfer_test")


def test_resource_transfers():
    """Test resource transfer mechanics and identify issues."""
    client = MinimalSyncClient(socket_path="/Users/dp/projects/ksi/var/run/daemon.sock")
    test_id = f"transfer_{uuid.uuid4().hex[:6]}"
    
    print("\n" + "="*60)
    print("💰 PHASE 1: Resource Transfer Mechanics Test")
    print("="*60)
    print(f"Test ID: {test_id}\n")
    
    issues = []
    
    # Test 1: Basic resource creation and update
    print("1️⃣ Test 1: Basic resource operations...")
    
    resource_id = f"resource_{test_id}_1"
    initial_amount = 100
    
    # Create resource
    create_result = client.send_event("state:entity:create", {
        "type": "resource",
        "id": resource_id,
        "properties": {
            "owner": "alice",
            "amount": initial_amount,
            "resource_type": "tokens"
        }
    })
    
    if create_result.get("status") == "success":
        print(f"   ✅ Resource created: {initial_amount} tokens")
    else:
        print(f"   ❌ Failed to create resource: {create_result}")
        issues.append({
            "title": "Resource creation failure",
            "severity": "HIGH",
            "impact": "Cannot run experiments",
            "details": str(create_result)
        })
        return {"issues": issues}
    
    # Update resource
    new_amount = 150
    update_result = client.send_event("state:entity:update", {
        "type": "resource",
        "id": resource_id,
        "properties": {"amount": new_amount}
    })
    
    # Verify update
    get_result = client.send_event("state:entity:get", {
        "type": "resource",
        "id": resource_id
    })
    
    actual_amount = get_result.get("properties", {}).get("amount", 0)
    if actual_amount == new_amount:
        print(f"   ✅ Resource updated: {initial_amount} → {new_amount}")
    else:
        print(f"   ❌ Update failed: expected {new_amount}, got {actual_amount}")
        issues.append({
            "title": "Resource update inconsistency",
            "severity": "HIGH",
            "impact": "Data integrity compromised",
            "details": f"Expected {new_amount}, got {actual_amount}"
        })
    
    # Test 2: Atomic transfer between two resources
    print("\n2️⃣ Test 2: Atomic transfer between resources...")
    
    alice_resource = f"resource_{test_id}_alice"
    bob_resource = f"resource_{test_id}_bob"
    
    # Create two resources
    for res_id, owner in [(alice_resource, "alice"), (bob_resource, "bob")]:
        client.send_event("state:entity:create", {
            "type": "resource",
            "id": res_id,
            "properties": {
                "owner": owner,
                "amount": 100,
                "resource_type": "tokens"
            }
        })
    print("   Created: Alice=100, Bob=100")
    
    # Transfer 30 tokens from Alice to Bob
    transfer_amount = 30
    
    # Get current amounts
    alice_before = client.send_event("state:entity:get", {
        "type": "resource", "id": alice_resource
    }).get("properties", {}).get("amount", 0)
    
    bob_before = client.send_event("state:entity:get", {
        "type": "resource", "id": bob_resource
    }).get("properties", {}).get("amount", 0)
    
    # Perform transfer (non-atomic - this is the problem!)
    client.send_event("state:entity:update", {
        "type": "resource",
        "id": alice_resource,
        "properties": {"amount": alice_before - transfer_amount}
    })
    
    client.send_event("state:entity:update", {
        "type": "resource",
        "id": bob_resource,
        "properties": {"amount": bob_before + transfer_amount}
    })
    
    # Verify transfer
    alice_after = client.send_event("state:entity:get", {
        "type": "resource", "id": alice_resource
    }).get("properties", {}).get("amount", 0)
    
    bob_after = client.send_event("state:entity:get", {
        "type": "resource", "id": bob_resource
    }).get("properties", {}).get("amount", 0)
    
    total_before = alice_before + bob_before
    total_after = alice_after + bob_after
    
    print(f"   Transfer: Alice {alice_before}→{alice_after}, Bob {bob_before}→{bob_after}")
    
    if total_before == total_after:
        print(f"   ✅ Conservation maintained: Total = {total_after}")
    else:
        print(f"   ❌ Conservation violated: {total_before} → {total_after}")
        issues.append({
            "title": "Non-atomic transfers risk conservation violation",
            "severity": "HIGH",
            "impact": "Resources can be lost or duplicated",
            "details": f"Total changed from {total_before} to {total_after}"
        })
    
    # Test 3: Concurrent updates (race condition test)
    print("\n3️⃣ Test 3: Concurrent update race conditions...")
    
    race_resource = f"resource_{test_id}_race"
    client.send_event("state:entity:create", {
        "type": "resource",
        "id": race_resource,
        "properties": {"amount": 1000, "owner": "system"}
    })
    
    results = []
    errors = []
    
    def concurrent_update(thread_id: int, amount_delta: int):
        """Simulate concurrent update."""
        try:
            # Read current value
            current = client.send_event("state:entity:get", {
                "type": "resource", "id": race_resource
            }).get("properties", {}).get("amount", 0)
            
            # Small delay to increase chance of race condition
            time.sleep(0.01)
            
            # Update based on read value
            client.send_event("state:entity:update", {
                "type": "resource",
                "id": race_resource,
                "properties": {"amount": current + amount_delta}
            })
            
            results.append(amount_delta)
        except Exception as e:
            errors.append(str(e))
    
    # Launch 10 concurrent updates
    threads = []
    for i in range(10):
        t = threading.Thread(target=concurrent_update, args=(i, 10))
        threads.append(t)
        t.start()
    
    # Wait for all threads
    for t in threads:
        t.join()
    
    # Check final value
    final = client.send_event("state:entity:get", {
        "type": "resource", "id": race_resource
    }).get("properties", {}).get("amount", 0)
    
    expected = 1000 + (10 * 10)  # Initial + (10 threads × 10 tokens)
    
    print(f"   Started with: 1000")
    print(f"   10 threads each adding: 10")
    print(f"   Expected final: {expected}")
    print(f"   Actual final: {final}")
    
    if final == expected:
        print(f"   ✅ No race condition detected")
    else:
        lost_updates = expected - final
        print(f"   ❌ Race condition! Lost {lost_updates} tokens")
        issues.append({
            "title": "Concurrent update race conditions (Issue #13)",
            "severity": "HIGH",
            "impact": "Multi-agent transfers unreliable",
            "details": f"Lost {lost_updates} tokens in 10 concurrent updates"
        })
    
    # Test 4: Transfer with validation (negative balance check)
    print("\n4️⃣ Test 4: Transfer validation (overdraft protection)...")
    
    poor_resource = f"resource_{test_id}_poor"
    client.send_event("state:entity:create", {
        "type": "resource",
        "id": poor_resource,
        "properties": {"amount": 10, "owner": "poor_agent"}
    })
    
    # Try to transfer more than available (should fail, but doesn't!)
    current = 10
    transfer = 20
    
    client.send_event("state:entity:update", {
        "type": "resource",
        "id": poor_resource,
        "properties": {"amount": current - transfer}  # Will be -10!
    })
    
    result = client.send_event("state:entity:get", {
        "type": "resource", "id": poor_resource
    }).get("properties", {}).get("amount", 0)
    
    if result < 0:
        print(f"   ❌ Negative balance allowed: {result}")
        issues.append({
            "title": "No balance validation on transfers",
            "severity": "MEDIUM",
            "impact": "Invalid game states possible",
            "details": "System allows negative resource amounts"
        })
    else:
        print(f"   ✅ Balance validation working")
    
    # Test 5: Bulk transfer performance
    print("\n5️⃣ Test 5: Bulk transfer performance...")
    
    start_time = time.time()
    bulk_transfers = 50
    
    for i in range(bulk_transfers):
        src = f"resource_{test_id}_bulk_src_{i}"
        dst = f"resource_{test_id}_bulk_dst_{i}"
        
        # Create source and destination
        client.send_event("state:entity:create", {
            "type": "resource", "id": src,
            "properties": {"amount": 100}
        })
        client.send_event("state:entity:create", {
            "type": "resource", "id": dst,
            "properties": {"amount": 0}
        })
        
        # Transfer
        client.send_event("state:entity:update", {
            "type": "resource", "id": src,
            "properties": {"amount": 50}
        })
        client.send_event("state:entity:update", {
            "type": "resource", "id": dst,
            "properties": {"amount": 50}
        })
    
    elapsed = time.time() - start_time
    transfers_per_second = bulk_transfers / elapsed
    
    print(f"   Completed {bulk_transfers} transfers in {elapsed:.2f}s")
    print(f"   Performance: {transfers_per_second:.1f} transfers/second")
    
    if transfers_per_second < 10:
        issues.append({
            "title": "Slow transfer performance",
            "severity": "LOW",
            "impact": "Large experiments will be slow",
            "details": f"Only {transfers_per_second:.1f} transfers/second"
        })
    
    # Cleanup
    print("\n6️⃣ Cleanup...")
    # Delete all test resources
    all_resources = client.send_event("state:entity:query", {
        "type": "resource",
        "filter": {"id": {"$regex": test_id}}
    })
    
    for entity in all_resources.get("entities", []):
        if isinstance(entity, dict) and "id" in entity:
            client.send_event("state:entity:delete", {
                "type": "resource",
                "id": entity["id"]
            })
    print("   ✅ Test resources cleaned up")
    
    # Results
    print("\n" + "="*60)
    print("📊 RESOURCE TRANSFER TEST RESULTS")
    print("="*60)
    
    if len(issues) == 0:
        print("✅ All transfer tests passed!")
    else:
        print(f"⚠️ {len(issues)} issue(s) found:\n")
        for i, issue in enumerate(issues, 1):
            print(f"{i}. {issue['title']}")
            print(f"   Severity: {issue['severity']}")
            print(f"   Impact: {issue['impact']}")
            print(f"   Details: {issue['details']}\n")
    
    return {
        "test_id": test_id,
        "issues": issues,
        "transfers_per_second": transfers_per_second if 'transfers_per_second' in locals() else 0
    }


def propose_atomic_transfer_solution():
    """Propose solution for atomic transfers."""
    print("\n" + "="*60)
    print("💡 PROPOSED SOLUTION: Atomic Transfer Service")
    print("="*60)
    
    print("""
    Create new event handler for atomic transfers:
    
    @event_handler("resource:transfer")
    async def atomic_transfer(data: Dict[str, Any], context: Dict) -> Dict:
        '''Atomic resource transfer with validation.'''
        from_resource = data["from_resource"]
        to_resource = data["to_resource"]  
        amount = data["amount"]
        
        # Begin transaction (use Redis WATCH or similar)
        with atomic_transaction():
            # Get both resources
            from_current = get_resource(from_resource)
            to_current = get_resource(to_resource)
            
            # Validate
            if from_current < amount:
                return error_response("Insufficient funds")
            
            # Update both atomically
            update_resource(from_resource, from_current - amount)
            update_resource(to_resource, to_current + amount)
            
            # Commit transaction
        
        return success_response({
            "transferred": amount,
            "from_balance": from_current - amount,
            "to_balance": to_current + amount
        })
    
    This ensures:
    - No lost updates
    - No negative balances
    - Conservation of resources
    - Thread-safe transfers
    """)


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
    
    # Run test
    results = test_resource_transfers()
    
    # Show solution if issues found
    if results.get("issues"):
        propose_atomic_transfer_solution()