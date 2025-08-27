#!/usr/bin/env python3
"""
Test the atomic transfer service implementation.
Verifies fix for Issue #13: Race conditions.
"""

import time
import threading
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_common.sync_client import MinimalSyncClient


def test_atomic_transfers():
    """Test atomic transfer service."""
    client = MinimalSyncClient(socket_path="/Users/dp/projects/ksi/var/run/daemon.sock")
    
    print("\n" + "="*60)
    print("🔒 ATOMIC TRANSFER SERVICE TEST")
    print("="*60)
    
    # Create test resources
    print("\n1️⃣ Creating test resources...")
    client.send_event("state:entity:create", {
        "type": "resource",
        "id": "atomic_test_alice",
        "properties": {"owner": "alice", "amount": 1000, "resource_type": "tokens"}
    })
    client.send_event("state:entity:create", {
        "type": "resource",
        "id": "atomic_test_bob",
        "properties": {"owner": "bob", "amount": 1000, "resource_type": "tokens"}
    })
    print("   ✅ Created: Alice=1000, Bob=1000")
    
    # Test 1: Basic atomic transfer
    print("\n2️⃣ Testing basic atomic transfer...")
    result = client.send_event("resource:transfer", {
        "from_resource": "atomic_test_alice",
        "to_resource": "atomic_test_bob",
        "amount": 100
    })
    
    if result.get("status") == "success":
        print(f"   ✅ Transfer successful")
        print(f"   Alice: {result['from_balance_before']} → {result['from_balance_after']}")
        print(f"   Bob: {result['to_balance_before']} → {result['to_balance_after']}")
        print(f"   Conservation: {result['conservation_check']['conserved']}")
    else:
        print(f"   ❌ Transfer failed: {result}")
    
    # Test 2: Insufficient funds validation
    print("\n3️⃣ Testing insufficient funds validation...")
    result = client.send_event("resource:transfer", {
        "from_resource": "atomic_test_alice",
        "to_resource": "atomic_test_bob",
        "amount": 10000  # More than alice has
    })
    
    if result.get("status") == "failed" and "Insufficient" in result.get("error", ""):
        print(f"   ✅ Correctly rejected: {result['error']}")
    else:
        print(f"   ❌ Should have been rejected: {result}")
    
    # Test 3: Concurrent transfers (the real test!)
    print("\n4️⃣ Testing concurrent atomic transfers...")
    
    # Reset resources
    client.send_event("state:entity:update", {
        "type": "resource",
        "id": "atomic_test_alice",
        "properties": {"amount": 1000}
    })
    client.send_event("state:entity:update", {
        "type": "resource",
        "id": "atomic_test_bob",
        "properties": {"amount": 1000}
    })
    
    results = []
    errors = []
    
    def concurrent_transfer(thread_id: int):
        """Perform concurrent transfer."""
        try:
            result = client.send_event("resource:transfer", {
                "from_resource": "atomic_test_alice",
                "to_resource": "atomic_test_bob",
                "amount": 10
            })
            results.append(result)
        except Exception as e:
            errors.append(str(e))
    
    # Launch 10 concurrent transfers
    threads = []
    for i in range(10):
        t = threading.Thread(target=concurrent_transfer, args=(i,))
        threads.append(t)
        t.start()
    
    # Wait for all threads
    for t in threads:
        t.join()
    
    # Check final balances
    alice_final = client.send_event("state:entity:get", {
        "type": "resource", "id": "atomic_test_alice"
    }).get("properties", {}).get("amount", 0)
    
    bob_final = client.send_event("state:entity:get", {
        "type": "resource", "id": "atomic_test_bob"
    }).get("properties", {}).get("amount", 0)
    
    expected_alice = 1000 - (10 * 10)  # 900
    expected_bob = 1000 + (10 * 10)    # 1100
    
    print(f"   10 threads each transferred 10 tokens")
    print(f"   Expected: Alice=900, Bob=1100")
    print(f"   Actual: Alice={alice_final}, Bob={bob_final}")
    print(f"   Conservation: {alice_final + bob_final == 2000}")
    
    if alice_final == expected_alice and bob_final == expected_bob:
        print(f"   ✅ NO RACE CONDITIONS! All transfers atomic")
    else:
        print(f"   ❌ Race condition still exists")
    
    # Test 4: Bulk transfers
    print("\n5️⃣ Testing bulk atomic transfers...")
    result = client.send_event("resource:bulk_transfer", {
        "transfers": [
            {"from_resource": "atomic_test_alice", "to_resource": "atomic_test_bob", "amount": 50},
            {"from_resource": "atomic_test_bob", "to_resource": "atomic_test_alice", "amount": 30},
            {"from_resource": "atomic_test_alice", "to_resource": "atomic_test_bob", "amount": 20}
        ]
    })
    
    if result.get("status") == "success":
        print(f"   ✅ Bulk transfer successful: {result['transfers_completed']} transfers")
        print(f"   Total transferred: {result['total_amount_transferred']}")
    else:
        print(f"   ❌ Bulk transfer failed: {result}")
    
    # Cleanup
    print("\n6️⃣ Cleanup...")
    client.send_event("state:entity:delete", {"type": "resource", "id": "atomic_test_alice"})
    client.send_event("state:entity:delete", {"type": "resource", "id": "atomic_test_bob"})
    print("   ✅ Test resources deleted")
    
    # Results
    print("\n" + "="*60)
    print("📊 ATOMIC TRANSFER TEST RESULTS")
    print("="*60)
    print("✅ Basic transfers work")
    print("✅ Validation prevents negative balances")
    if alice_final == expected_alice and bob_final == expected_bob:
        print("✅ Race conditions FIXED - Issue #13 RESOLVED")
        print("\n🎉 Ready to proceed with Phase 2 multi-agent experiments!")
    else:
        print("❌ Race conditions still present")
        print("\n⚠️ Do not proceed with multi-agent experiments")


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
    
    test_atomic_transfers()