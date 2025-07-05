#!/usr/bin/env python3
"""
Test script for graph-oriented state operations
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


async def test_graph_operations():
    """Test the new graph-oriented state operations."""
    print("Testing Graph-Oriented State Operations")
    print("=" * 50)
    
    # 1. Bulk create entities
    print("\n1. Testing bulk entity creation...")
    
    bulk_entities = {
        "event": "state:entity:bulk_create",
        "data": {
            "entities": [
                {
                    "type": "agent",
                    "id": "graph_originator",
                    "properties": {
                        "status": "active",
                        "agent_type": "originator",
                        "profile": "orchestrator"
                    }
                },
                {
                    "type": "agent", 
                    "id": "graph_construct_1",
                    "properties": {
                        "status": "active",
                        "agent_type": "construct",
                        "purpose": "data_collector"
                    }
                },
                {
                    "type": "agent",
                    "id": "graph_construct_2",
                    "properties": {
                        "status": "active",
                        "agent_type": "construct",
                        "purpose": "analyzer"
                    }
                },
                {
                    "type": "agent",
                    "id": "graph_construct_3",
                    "properties": {
                        "status": "active",
                        "agent_type": "construct",
                        "purpose": "reporter"
                    }
                }
            ]
        }
    }
    
    response = await send_socket_message(bulk_entities)
    if response and response.get("data"):
        data = response["data"]
        print(f"✓ Created {data.get('success', 0)}/{data.get('total', 0)} entities")
    else:
        print("✗ Failed to bulk create entities")
        return
    
    # 2. Create relationships to form a hierarchy
    print("\n2. Creating relationship hierarchy...")
    
    relationships = [
        ("graph_originator", "graph_construct_1", "spawned"),
        ("graph_originator", "graph_construct_2", "spawned"),
        ("graph_construct_1", "graph_construct_3", "spawned"),  # Nested construct
        ("graph_construct_2", "graph_construct_3", "observes")  # Cross-relationship
    ]
    
    for from_id, to_id, rel_type in relationships:
        rel_msg = {
            "event": "state:relationship:create",
            "data": {
                "from": from_id,
                "to": to_id,
                "type": rel_type,
                "metadata": {
                    "created_for_test": True,
                    "timestamp": time.time()
                }
            }
        }
        
        response = await send_socket_message(rel_msg)
        if response and response.get("data", {}).get("status") == "created":
            print(f"✓ Created {rel_type} relationship: {from_id} → {to_id}")
        else:
            print(f"✗ Failed to create relationship: {from_id} → {to_id}")
    
    # 3. Test graph traversal
    print("\n3. Testing graph traversal...")
    
    # Traverse from originator with depth 2
    traverse_msg = {
        "event": "state:graph:traverse",
        "data": {
            "from": "graph_originator",
            "direction": "outgoing",
            "types": ["spawned"],
            "depth": 2,
            "include_entities": True
        }
    }
    
    response = await send_socket_message(traverse_msg)
    if response and response.get("data"):
        graph = response["data"]
        print(f"✓ Traversal found {graph.get('node_count', 0)} nodes and {graph.get('edge_count', 0)} edges")
        print(f"  Root: {graph.get('root')}")
        print(f"  Nodes: {list(graph.get('nodes', {}).keys())}")
    else:
        print("✗ Failed to traverse graph")
    
    # Test incoming traversal
    traverse_incoming = {
        "event": "state:graph:traverse",
        "data": {
            "from": "graph_construct_3",
            "direction": "incoming",
            "depth": 2,
            "include_entities": False
        }
    }
    
    response = await send_socket_message(traverse_incoming)
    if response and response.get("data"):
        graph = response["data"]
        print(f"\n✓ Incoming traversal found {graph.get('node_count', 0)} nodes")
        print(f"  Paths to construct_3: {list(graph.get('nodes', {}).keys())}")
    
    # 4. Test aggregate counting
    print("\n4. Testing aggregate counts...")
    
    # Count entities by type
    count_entities = {
        "event": "state:aggregate:count",
        "data": {
            "target": "entities",
            "group_by": "type"
        }
    }
    
    response = await send_socket_message(count_entities)
    if response and response.get("data"):
        counts = response["data"].get("counts", {})
        print("✓ Entity counts by type:")
        for entity_type, count in counts.items():
            print(f"  - {entity_type}: {count}")
    
    # Count relationships by type
    count_relationships = {
        "event": "state:aggregate:count",
        "data": {
            "target": "relationships",
            "group_by": "type"
        }
    }
    
    response = await send_socket_message(count_relationships)
    if response and response.get("data"):
        counts = response["data"].get("counts", {})
        print("\n✓ Relationship counts by type:")
        for rel_type, count in counts.items():
            print(f"  - {rel_type}: {count}")
    
    # 5. Clean up test entities
    print("\n5. Cleaning up test entities...")
    
    test_entities = ["graph_originator", "graph_construct_1", "graph_construct_2", "graph_construct_3"]
    
    for entity_id in test_entities:
        delete_msg = {
            "event": "state:entity:delete",
            "data": {"id": entity_id}
        }
        response = await send_socket_message(delete_msg)
        if response and response.get("data", {}).get("status") == "deleted":
            print(f"✓ Deleted entity: {entity_id}")
    
    print("\n✓ Graph operations testing complete!")


if __name__ == "__main__":
    asyncio.run(test_graph_operations())