#!/usr/bin/env python3
"""
Test KSI graph database scalability and performance.
Creates a large network of entities and measures query performance.
"""

import asyncio
import json
import time
import random
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_client import EventClient

class GraphScaleTester:
    def __init__(self, client: EventClient):
        self.client = client
        self.timings = {}
        
    async def measure_time(self, name: str, coro):
        """Measure execution time of an async operation."""
        start = time.time()
        result = await coro
        duration = time.time() - start
        self.timings[name] = duration
        print(f"  ⏱️  {name}: {duration:.3f}s")
        return result
    
    async def create_social_network(self, size: int = 100):
        """Create a social network graph."""
        print(f"\n1. Creating social network with {size} users...")
        
        # Batch create users
        users = []
        for i in range(size):
            users.append({
                "type": "user",
                "id": f"user_{i}",
                "properties": {
                    "name": f"User {i}",
                    "active": str(random.choice([True, False])).lower(),
                    "score": str(random.randint(1, 100))
                }
            })
        
        # Create entities in batches
        batch_size = 50
        for i in range(0, len(users), batch_size):
            batch = users[i:i + batch_size]
            await self.measure_time(
                f"create_batch_{i//batch_size}",
                self.client.send_single("state:entity:bulk_create", {"entities": batch})
            )
        
        print(f"✓ Created {size} users")
        
        # Create relationships (friendships)
        print(f"\n2. Creating friendships...")
        relationships_created = 0
        
        for i in range(size):
            # Each user has 1-10 friends
            num_friends = random.randint(1, min(10, size - 1))
            for _ in range(num_friends):
                friend_id = random.randint(0, size - 1)
                if friend_id != i:  # Don't friend yourself
                    await self.client.send_single("state:relationship:create", {
                        "from": f"user_{i}",
                        "to": f"user_{friend_id}",
                        "type": "friends_with",
                        "metadata": {"since": "2024"}
                    })
                    relationships_created += 1
        
        print(f"✓ Created ~{relationships_created} friendships")
        return users
    
    async def test_queries(self, size: int):
        """Test various query patterns."""
        print(f"\n3. Testing query performance...")
        
        # Test 1: Simple entity query
        await self.measure_time(
            "query_all_users",
            self.client.send_single("state:entity:query", {
                "type": "user",
                "limit": 1000
            })
        )
        
        # Test 2: Filtered query
        result = await self.measure_time(
            "query_active_users",
            self.client.send_single("state:entity:query", {
                "type": "user",
                "where": {"active": "true"},
                "limit": 100
            })
        )
        active_count = len(result.get("entities", []))
        
        # Test 3: Query with relationships
        await self.measure_time(
            "query_with_relationships",
            self.client.send_single("state:entity:query", {
                "type": "user",
                "include": ["properties", "relationships"],
                "limit": 10
            })
        )
        
        # Test 4: Relationship queries
        test_user = f"user_{random.randint(0, size-1)}"
        rel_result = await self.measure_time(
            "query_user_friends",
            self.client.send_single("state:relationship:query", {
                "from": test_user,
                "type": "friends_with"
            })
        )
        friend_count = len(rel_result.get("relationships", []))
        
        # Test 5: Graph traversal - 1 hop
        await self.measure_time(
            "traverse_1_hop",
            self.client.send_single("state:graph:traverse", {
                "from": test_user,
                "direction": "outgoing",
                "types": ["friends_with"],
                "depth": 1,
                "include_entities": False
            })
        )
        
        # Test 6: Graph traversal - 2 hops
        result_2hop = await self.measure_time(
            "traverse_2_hop",
            self.client.send_single("state:graph:traverse", {
                "from": test_user,
                "direction": "both",
                "types": ["friends_with"],
                "depth": 2,
                "include_entities": False
            })
        )
        nodes_2hop = len(result_2hop.get("nodes", {}))
        
        # Test 7: Graph traversal - 3 hops (might be slow)
        if size <= 500:
            result_3hop = await self.measure_time(
                "traverse_3_hop",
                self.client.send_single("state:graph:traverse", {
                    "from": test_user,
                    "direction": "outgoing",
                    "types": ["friends_with"],
                    "depth": 3,
                    "include_entities": False
                })
            )
            nodes_3hop = len(result_3hop.get("nodes", {}))
        else:
            nodes_3hop = "skipped (too large)"
        
        # Test 8: Aggregation
        count_result = await self.measure_time(
            "count_by_type",
            self.client.send_single("state:aggregate:count", {
                "target": "entities",
                "group_by": "type"
            })
        )
        
        return {
            "active_users": active_count,
            "test_user": test_user,
            "friend_count": friend_count,
            "nodes_2hop": nodes_2hop,
            "nodes_3hop": nodes_3hop
        }
    
    async def create_knowledge_graph(self):
        """Create a more complex knowledge graph."""
        print(f"\n4. Creating knowledge graph...")
        
        # Create different entity types
        entities = [
            # Topics
            {"type": "topic", "id": "ai", "properties": {"name": "Artificial Intelligence"}},
            {"type": "topic", "id": "ml", "properties": {"name": "Machine Learning"}},
            {"type": "topic", "id": "dl", "properties": {"name": "Deep Learning"}},
            {"type": "topic", "id": "nlp", "properties": {"name": "Natural Language Processing"}},
            {"type": "topic", "id": "cv", "properties": {"name": "Computer Vision"}},
            
            # Papers
            {"type": "paper", "id": "attention", "properties": {"title": "Attention Is All You Need", "year": "2017"}},
            {"type": "paper", "id": "bert", "properties": {"title": "BERT: Pre-training of Deep Bidirectional Transformers", "year": "2018"}},
            {"type": "paper", "id": "gpt", "properties": {"title": "Language Models are Few-Shot Learners", "year": "2020"}},
            
            # Authors
            {"type": "author", "id": "vaswani", "properties": {"name": "Vaswani et al."}},
            {"type": "author", "id": "devlin", "properties": {"name": "Devlin et al."}},
            {"type": "author", "id": "brown", "properties": {"name": "Brown et al."}},
            
            # Institutions
            {"type": "institution", "id": "google", "properties": {"name": "Google"}},
            {"type": "institution", "id": "openai", "properties": {"name": "OpenAI"}},
        ]
        
        await self.client.send_single("state:entity:bulk_create", {"entities": entities})
        
        # Create relationships
        relationships = [
            # Topic hierarchy
            ("ml", "ai", "subset_of"),
            ("dl", "ml", "subset_of"),
            ("nlp", "ai", "application_of"),
            ("cv", "ai", "application_of"),
            
            # Papers to topics
            ("attention", "dl", "contributes_to"),
            ("attention", "nlp", "contributes_to"),
            ("bert", "nlp", "advances"),
            ("gpt", "nlp", "advances"),
            
            # Authors to papers
            ("vaswani", "attention", "authored"),
            ("devlin", "bert", "authored"),
            ("brown", "gpt", "authored"),
            
            # Authors to institutions
            ("vaswani", "google", "affiliated_with"),
            ("devlin", "google", "affiliated_with"),
            ("brown", "openai", "affiliated_with"),
            
            # Papers cite each other
            ("bert", "attention", "cites"),
            ("gpt", "attention", "cites"),
            ("gpt", "bert", "cites"),
        ]
        
        for from_id, to_id, rel_type in relationships:
            await self.client.send_single("state:relationship:create", {
                "from": from_id,
                "to": to_id,
                "type": rel_type
            })
        
        print(f"✓ Created knowledge graph with {len(entities)} entities and {len(relationships)} relationships")
        
        # Test complex queries
        print(f"\n5. Testing complex graph queries...")
        
        # Find all papers that contribute to AI (through topic hierarchy)
        ai_traverse = await self.measure_time(
            "papers_contributing_to_ai",
            self.client.send_single("state:graph:traverse", {
                "from": "ai",
                "direction": "incoming",
                "types": ["subset_of", "application_of", "contributes_to", "advances"],
                "depth": 3,
                "include_entities": True
            })
        )
        
        # Find citation network
        citation_traverse = await self.measure_time(
            "citation_network",
            self.client.send_single("state:graph:traverse", {
                "from": "attention",
                "direction": "incoming",
                "types": ["cites"],
                "depth": 2,
                "include_entities": True
            })
        )
        
        return {
            "ai_network_size": len(ai_traverse.get("nodes", {})),
            "citation_network_size": len(citation_traverse.get("nodes", {}))
        }

async def main():
    """Run the scale tests."""
    
    async with EventClient() as client:
        tester = GraphScaleTester(client)
        
        print("=== KSI Graph Database Scale Test ===")
        
        # Test different scales
        test_sizes = [100, 500, 1000]  # Adjust based on your system
        
        results = {}
        
        for size in test_sizes:
            print(f"\n{'='*50}")
            print(f"Testing with {size} entities")
            print(f"{'='*50}")
            
            # Create and test social network
            await tester.create_social_network(size)
            query_results = await tester.test_queries(size)
            
            results[size] = {
                "timings": tester.timings.copy(),
                "query_results": query_results
            }
            
            # Clear timings for next run
            tester.timings.clear()
            
            # Optional: Clean up before next test
            print(f"\nCleaning up...")
            # Note: No bulk delete, would need to implement cleanup
        
        # Create and test knowledge graph
        print(f"\n{'='*50}")
        print(f"Testing Knowledge Graph")
        print(f"{'='*50}")
        
        kg_results = await tester.create_knowledge_graph()
        
        # Summary
        print(f"\n{'='*50}")
        print("PERFORMANCE SUMMARY")
        print(f"{'='*50}")
        
        for size, data in results.items():
            print(f"\n{size} entities:")
            print(f"  • Entity creation: {data['timings'].get('create_batch_0', 0):.3f}s per batch")
            print(f"  • Simple query: {data['timings'].get('query_all_users', 0):.3f}s")
            print(f"  • Filtered query: {data['timings'].get('query_active_users', 0):.3f}s")
            print(f"  • With relationships: {data['timings'].get('query_with_relationships', 0):.3f}s")
            print(f"  • 1-hop traversal: {data['timings'].get('traverse_1_hop', 0):.3f}s")
            print(f"  • 2-hop traversal: {data['timings'].get('traverse_2_hop', 0):.3f}s")
            print(f"    - Found {data['query_results']['nodes_2hop']} nodes")
            if 'traverse_3_hop' in data['timings']:
                print(f"  • 3-hop traversal: {data['timings']['traverse_3_hop']:.3f}s")
                print(f"    - Found {data['query_results']['nodes_3hop']} nodes")
        
        print(f"\nKnowledge Graph:")
        print(f"  • AI network nodes: {kg_results['ai_network_size']}")
        print(f"  • Citation network nodes: {kg_results['citation_network_size']}")
        
        # Performance insights
        print(f"\n{'='*50}")
        print("INSIGHTS")
        print(f"{'='*50}")
        
        # Calculate scaling factor
        if len(results) >= 2:
            sizes = sorted(results.keys())
            time_100 = results[sizes[0]]['timings'].get('traverse_2_hop', 1)
            time_large = results[sizes[-1]]['timings'].get('traverse_2_hop', 1)
            scale_factor = time_large / time_100
            size_factor = sizes[-1] / sizes[0]
            
            print(f"\n• Scaling: {sizes[0]} → {sizes[-1]} entities ({size_factor}x)")
            print(f"• 2-hop traversal time increased {scale_factor:.1f}x")
            
            if scale_factor > size_factor * 2:
                print("• ⚠️  Performance degradation detected - graph queries don't scale linearly")
            else:
                print("• ✓ Performance scales reasonably well")
        
        # Recommendations
        print(f"\nRecommendations:")
        if any(results[s]['timings'].get('traverse_3_hop', 0) > 1.0 for s in results if 'traverse_3_hop' in results[s]['timings']):
            print("• Consider limiting traversal depth for large graphs")
        
        if any(results[s]['timings'].get('query_with_relationships', 0) > 0.5 for s in results):
            print("• Relationship queries could benefit from better indexing")
        
        print("• SQLite handles moderate graphs well but may struggle with deep traversals")
        print("• Consider Kùzu for graphs with >10k entities or complex traversal needs")

if __name__ == "__main__":
    print("Starting graph scale test...")
    print("This will create many entities and relationships - ensure daemon has enough resources")
    
    try:
        asyncio.run(main())
    except ConnectionError:
        print("\n❌ Error: KSI daemon is not running")
        print("Start it with: ./daemon_control.py start")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)