#!/usr/bin/env python3
"""
Test script for universal graph database system (Phase 2 Redesign)
"""

import asyncio
import json
import subprocess
import time


async def send_socket_message(message):
    """Send message to daemon via Unix socket."""
    cmd = ['echo', json.dumps(message), '|', 'nc', '-U', 'var/run/daemon.sock']
    result = subprocess.run(' '.join(cmd), shell=True, capture_output=True, text=True)
    if result.stdout:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            print(f"Failed to parse response: {result.stdout}")
    return None


async def test_graph_state():
    """Test the universal graph database system."""
    print("Testing Universal Graph Database System")
    print("=" * 50)
    
    # 1. Test basic entity operations
    print("\n1. Testing entity creation...")
    
    # Create a test entity
    test_entity = {
        "event": "state:entity:create",
        "data": {
            "type": "test_object",
            "id": "test_001",
            "properties": {
                "name": "Test Entity",
                "value": 42,
                "active": True,
                "tags": ["test", "demo"]
            }
        }
    }
    
    response = await send_socket_message(test_entity)
    if response and response.get("data"):
        entity = response["data"]
        print(f"✓ Created entity: {entity['id']} at {entity.get('created_at_iso')}")
    else:
        print("✗ Failed to create entity")
        return
    
    # 2. Test entity retrieval
    print("\n2. Testing entity retrieval...")
    get_entity = {
        "event": "state:entity:get",
        "data": {
            "id": "test_001",
            "include": ["properties", "relationships"]
        }
    }
    
    response = await send_socket_message(get_entity)
    if response and response.get("data"):
        entity = response["data"]
        print(f"✓ Retrieved entity: {entity['id']}")
        print(f"  Properties: {entity.get('properties')}")
    else:
        print("✗ Failed to retrieve entity")
    
    # 3. Test entity update
    print("\n3. Testing entity update...")
    update_entity = {
        "event": "state:entity:update",
        "data": {
            "id": "test_001",
            "properties": {
                "value": 100,
                "updated": True,
                "active": None  # This should delete the property
            }
        }
    }
    
    response = await send_socket_message(update_entity)
    if response and response.get("data", {}).get("status") == "updated":
        print("✓ Updated entity properties")
    else:
        print("✗ Failed to update entity")
    
    # 4. Test agent entities with relationships
    print("\n4. Testing agent entities and relationships...")
    
    # Create originator agent entity
    originator = {
        "event": "state:entity:create",
        "data": {
            "type": "agent",
            "id": "test_originator_002",
            "properties": {
                "status": "active",
                "agent_type": "originator",
                "profile": "base_single_agent",
                "purpose": "Test originator for graph database"
            }
        }
    }
    
    response = await send_socket_message(originator)
    if response and response.get("data"):
        print(f"✓ Created originator entity: {response['data']['id']}")
    else:
        print("✗ Failed to create originator")
        return
    
    # Create construct entities
    construct_ids = []
    for i in range(3):
        construct = {
            "event": "state:entity:create",
            "data": {
                "type": "agent",
                "id": f"test_construct_{i:03d}_v2",
                "properties": {
                    "status": "active",
                    "agent_type": "construct",
                    "profile": "base_single_agent",
                    "purpose": f"Observer for aspect {i}"
                }
            }
        }
        
        response = await send_socket_message(construct)
        if response and response.get("data"):
            construct_id = response['data']['id']
            construct_ids.append(construct_id)
            print(f"✓ Created construct entity: {construct_id}")
            
            # Create relationship
            relationship = {
                "event": "state:relationship:create",
                "data": {
                    "from": "test_originator_002",
                    "to": construct_id,
                    "type": "spawned",
                    "metadata": {
                        "purpose": f"Observer for aspect {i}",
                        "spawned_at": time.time()
                    }
                }
            }
            
            rel_response = await send_socket_message(relationship)
            if rel_response and rel_response.get("data", {}).get("status") == "created":
                print(f"  ✓ Created spawned relationship")
            else:
                print(f"  ✗ Failed to create relationship")
    
    # 5. Test relationship queries
    print("\n5. Testing relationship queries...")
    query_rel = {
        "event": "state:relationship:query",
        "data": {
            "from": "test_originator_002",
            "type": "spawned"
        }
    }
    
    response = await send_socket_message(query_rel)
    if response and response.get("data"):
        relationships = response['data'].get('relationships', [])
        print(f"✓ Found {len(relationships)} relationships:")
        for rel in relationships:
            print(f"  - {rel['from']} spawned {rel['to']} at {rel.get('created_at_iso')}")
    else:
        print("✗ Failed to query relationships")
    
    # 6. Test entity queries
    print("\n6. Testing entity queries...")
    query_entities = {
        "event": "state:entity:query",
        "data": {
            "type": "agent",
            "where": {"agent_type": "construct"},
            "include": ["properties"],
            "limit": 5
        }
    }
    
    response = await send_socket_message(query_entities)
    if response and response.get("data"):
        entities = response['data'].get('entities', [])
        print(f"✓ Found {len(entities)} construct agents:")
        for entity in entities:
            props = entity.get('properties', {})
            print(f"  - {entity['id']}: {props.get('purpose', 'No purpose')}")
    else:
        print("✗ Failed to query entities")
    
    # 7. Test observation use case
    print("\n7. Testing observation subscription pattern...")
    
    # Create observation subscription entity
    subscription = {
        "event": "state:entity:create",
        "data": {
            "type": "observation_subscription",
            "id": "sub_001",
            "properties": {
                "observer_id": "test_originator_002",
                "target_id": construct_ids[0] if construct_ids else "unknown",
                "event_patterns": ["message:*", "error:*"],
                "filters": {"include_responses": True},
                "active": True
            }
        }
    }
    
    response = await send_socket_message(subscription)
    if response and response.get("data"):
        print(f"✓ Created observation subscription: {response['data']['id']}")
        
        # Create relationship for the subscription
        obs_rel = {
            "event": "state:relationship:create",
            "data": {
                "from": "test_originator_002",
                "to": construct_ids[0] if construct_ids else "unknown",
                "type": "observes",
                "metadata": {
                    "subscription_id": "sub_001",
                    "patterns": ["message:*", "error:*"]
                }
            }
        }
        
        rel_response = await send_socket_message(obs_rel)
        if rel_response and rel_response.get("data", {}).get("status") == "created":
            print("  ✓ Created observes relationship")
    
    # 8. Clean up - delete test entities
    print("\n8. Cleaning up test entities...")
    entities_to_delete = ["test_001", "test_originator_002", "sub_001"] + construct_ids
    
    for entity_id in entities_to_delete:
        delete_msg = {
            "event": "state:entity:delete",
            "data": {"id": entity_id}
        }
        response = await send_socket_message(delete_msg)
        if response and response.get("data", {}).get("status") == "deleted":
            print(f"✓ Deleted entity: {entity_id}")
        else:
            print(f"✗ Failed to delete entity: {entity_id}")
    
    print("\n✓ Universal graph database testing complete!")
    print("\nNext steps:")
    print("- Phase 3: Implement observation subscription system")
    print("- Phase 4: Add filtered event routing")
    print("- Phase 5: Historical analysis capabilities")


if __name__ == "__main__":
    asyncio.run(test_graph_state())