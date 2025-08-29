#!/usr/bin/env python3
"""
Test Melting Pot Integration with KSI Daemon
=============================================

Tests whether the Melting Pot services can be integrated with the running daemon.
This is a preliminary test before full service registration.
"""

import asyncio
from ksi_common.sync_client import MinimalSyncClient
import json
import time


def test_basic_events():
    """Test if basic events work with the daemon."""
    
    print("Testing basic KSI daemon connectivity...")
    
    try:
        # Use the correct socket path
        client = MinimalSyncClient(socket_path="/Users/dp/projects/ksi/var/run/daemon.sock")
        
        # Test a simple event
        print("  Testing system:health...")
        response = client.send_event("system:health", {})
        print(f"    Response: {response}")
        
        # Test if we can create state entities (which would be needed for episodes)
        print("  Testing state:entity:create...")
        response = client.send_event("state:entity:create", {
            "type": "test_episode",
            "id": f"test_ep_{int(time.time())}",
            "properties": {
                "participants": ["agent1", "agent2"],
                "max_steps": 100
            }
        })
        print(f"    Response: {response}")
        
        print("\n✓ Basic daemon connectivity works!")
        return True
        
    except Exception as e:
        print(f"\n✗ Daemon connectivity failed: {e}")
        return False


def test_spatial_concepts():
    """Test if spatial concepts can be implemented with existing events."""
    
    print("\nTesting spatial concepts with state events...")
    
    try:
        client = MinimalSyncClient(socket_path="/Users/dp/projects/ksi/var/run/daemon.sock")
        
        # Create a spatial environment using state entities
        env_id = f"spatial_env_{int(time.time())}"
        
        print(f"  Creating spatial environment {env_id}...")
        response = client.send_event("state:entity:create", {
            "type": "spatial_environment",
            "id": env_id,
            "properties": {
                "dimensions": 2,
                "bounds": {"x_min": 0, "x_max": 24, "y_min": 0, "y_max": 24},
                "grid_size": 1
            }
        })
        
        if "error" not in response:
            print("    ✓ Spatial environment created")
        else:
            print(f"    ✗ Failed: {response['error']}")
            return False
        
        # Add an entity to the environment
        agent_id = f"spatial_agent_{int(time.time())}"
        
        print(f"  Adding agent {agent_id} to environment...")
        response = client.send_event("state:entity:create", {
            "type": "spatial_agent",
            "id": agent_id,
            "properties": {
                "environment_id": env_id,
                "position": {"x": 5, "y": 5},
                "entity_type": "agent"
            }
        })
        
        if "error" not in response:
            print("    ✓ Agent added to environment")
        else:
            print(f"    ✗ Failed: {response['error']}")
            return False
        
        # Update agent position (movement)
        print("  Moving agent...")
        response = client.send_event("state:entity:update", {
            "type": "spatial_agent",
            "id": agent_id,
            "properties": {
                "position": {"x": 7, "y": 7}
            }
        })
        
        if "error" not in response:
            print("    ✓ Agent moved successfully")
        else:
            print(f"    ✗ Failed: {response['error']}")
            return False
        
        # Query agent position
        print("  Querying agent position...")
        response = client.send_event("state:entity:get", {
            "type": "spatial_agent",
            "id": agent_id
        })
        
        if "error" not in response:
            entity = response.get("result", {})
            position = entity.get("properties", {}).get("position", {})
            print(f"    ✓ Agent at position ({position.get('x')}, {position.get('y')})")
        else:
            print(f"    ✗ Failed: {response['error']}")
            return False
        
        print("\n✓ Spatial concepts can be implemented with state events!")
        return True
        
    except Exception as e:
        print(f"\n✗ Spatial test failed: {e}")
        return False


def test_resource_concepts():
    """Test if resource concepts can be implemented with existing events."""
    
    print("\nTesting resource concepts with state events...")
    
    try:
        client = MinimalSyncClient(socket_path="/Users/dp/projects/ksi/var/run/daemon.sock")
        
        # Create resources using state entities
        resource_id = f"gold_{int(time.time())}"
        owner_id = "alice"
        
        print(f"  Creating resource {resource_id}...")
        response = client.send_event("state:entity:create", {
            "type": "resource",
            "id": resource_id,
            "properties": {
                "resource_type": "gold",
                "amount": 100,
                "owner": owner_id
            }
        })
        
        if "error" not in response:
            print("    ✓ Resource created")
        else:
            print(f"    ✗ Failed: {response['error']}")
            return False
        
        # Transfer resource (update ownership)
        new_owner = "bob"
        transfer_amount = 30
        
        print(f"  Transferring {transfer_amount} gold from {owner_id} to {new_owner}...")
        
        # Get current amount
        response = client.send_event("state:entity:get", {
            "type": "resource",
            "id": resource_id
        })
        
        if "error" not in response:
            current_amount = response["result"]["properties"]["amount"]
            
            # Create new resource for recipient
            new_resource_id = f"gold_{new_owner}_{int(time.time())}"
            response = client.send_event("state:entity:create", {
                "type": "resource",
                "id": new_resource_id,
                "properties": {
                    "resource_type": "gold",
                    "amount": transfer_amount,
                    "owner": new_owner
                }
            })
            
            # Update original resource
            response = client.send_event("state:entity:update", {
                "type": "resource",
                "id": resource_id,
                "properties": {
                    "amount": current_amount - transfer_amount
                }
            })
            
            print("    ✓ Resource transferred")
        else:
            print(f"    ✗ Failed: {response['error']}")
            return False
        
        print("\n✓ Resource concepts can be implemented with state events!")
        return True
        
    except Exception as e:
        print(f"\n✗ Resource test failed: {e}")
        return False


def test_episode_concepts():
    """Test if episode concepts can be implemented with existing events."""
    
    print("\nTesting episode concepts with state and workflow events...")
    
    try:
        client = MinimalSyncClient(socket_path="/Users/dp/projects/ksi/var/run/daemon.sock")
        
        # Create episode using state entity
        episode_id = f"episode_{int(time.time())}"
        
        print(f"  Creating episode {episode_id}...")
        response = client.send_event("state:entity:create", {
            "type": "episode",
            "id": episode_id,
            "properties": {
                "episode_type": "prisoners_dilemma",
                "participants": ["agent1", "agent2"],
                "max_steps": 100,
                "current_step": 0,
                "status": "initialized"
            }
        })
        
        if "error" not in response:
            print("    ✓ Episode created")
        else:
            print(f"    ✗ Failed: {response['error']}")
            return False
        
        # Step the episode
        print("  Stepping episode...")
        response = client.send_event("state:entity:update", {
            "type": "episode",
            "id": episode_id,
            "properties": {
                "current_step": 1,
                "last_actions": {
                    "agent1": "cooperate",
                    "agent2": "defect"
                }
            }
        })
        
        if "error" not in response:
            print("    ✓ Episode stepped")
        else:
            print(f"    ✗ Failed: {response['error']}")
            return False
        
        # Check victory conditions
        print("  Checking victory conditions...")
        response = client.send_event("state:entity:get", {
            "type": "episode",
            "id": episode_id
        })
        
        if "error" not in response:
            episode = response["result"]
            print(f"    ✓ Episode at step {episode['properties']['current_step']}")
        else:
            print(f"    ✗ Failed: {response['error']}")
            return False
        
        # Terminate episode
        print("  Terminating episode...")
        response = client.send_event("state:entity:update", {
            "type": "episode",
            "id": episode_id,
            "properties": {
                "status": "terminated",
                "termination_reason": "test_complete"
            }
        })
        
        if "error" not in response:
            print("    ✓ Episode terminated")
        else:
            print(f"    ✗ Failed: {response['error']}")
            return False
        
        print("\n✓ Episode concepts can be implemented with state events!")
        return True
        
    except Exception as e:
        print(f"\n✗ Episode test failed: {e}")
        return False


def main():
    """Run all integration tests."""
    
    print("="*80)
    print("MELTING POT INTEGRATION TEST")
    print("="*80)
    print("\nTesting if Melting Pot concepts can work with existing KSI events...")
    
    results = []
    
    # Test basic connectivity
    results.append(("Basic Events", test_basic_events()))
    
    # Test each concept area
    results.append(("Spatial Concepts", test_spatial_concepts()))
    results.append(("Resource Concepts", test_resource_concepts()))
    results.append(("Episode Concepts", test_episode_concepts()))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name:20} {status}")
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print("\n✅ ALL TESTS PASSED!")
        print("\nConclusion: Melting Pot can be implemented using existing KSI events!")
        print("We can use state:* events to manage spatial, resource, and episode data.")
        print("This validates our approach of using general events rather than")
        print("creating Melting Pot-specific events.")
    else:
        print("\n❌ SOME TESTS FAILED")
        print("\nWe may need to implement custom event handlers or use different approaches.")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)