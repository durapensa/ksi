#!/usr/bin/env python3
"""
Melting Pot Validator Edge Case Tests
======================================

Comprehensive edge case testing for Melting Pot validators.
Tests boundary conditions, error handling, and stress scenarios.
"""

import json
import time
import random
from typing import Dict, List, Any
from ksi_common.sync_client import MinimalSyncClient

class MeltingPotEdgeCaseTests:
    """Edge case test suite for Melting Pot validators."""
    
    def __init__(self):
        self.client = MinimalSyncClient()
        self.suite_id = None
        self.test_results = []
        
    def create_test_suite(self, name: str) -> str:
        """Create a new test suite."""
        response = self.client.send_event("testing:suite:create", {
            "suite_name": name,
            "metadata": {
                "test_type": "edge_cases",
                "framework": "melting_pot",
                "timestamp": time.time()
            }
        })
        self.suite_id = response.get("suite_id")
        return self.suite_id
    
    def run_test(self, test_name: str, event: str, args: Dict) -> Dict:
        """Run a single test through the testing framework."""
        result = self.client.send_event("testing:run:test", {
            "test_name": test_name,
            "test_function": event,
            "test_args": args,
            "suite_id": self.suite_id
        })
        self.test_results.append(result)
        return result
    
    def test_movement_edge_cases(self):
        """Test movement validation edge cases."""
        print("\n=== Movement Validation Edge Cases ===")
        
        # Test 1: Zero distance movement
        result = self.run_test(
            "Movement - Zero Distance",
            "validator:movement:validate",
            {
                "from_x": 5.0, "from_y": 5.0,
                "to_x": 5.0, "to_y": 5.0,
                "movement_type": "walk",
                "entity_capacity": 10.0
            }
        )
        print(f"Zero distance: {'✓' if result.get('passed') else '✗'}")
        
        # Test 2: Negative coordinates
        result = self.run_test(
            "Movement - Negative Coordinates",
            "validator:movement:validate",
            {
                "from_x": -10.0, "from_y": -10.0,
                "to_x": -5.0, "to_y": -5.0,
                "movement_type": "walk",
                "entity_capacity": 10.0
            }
        )
        print(f"Negative coords: {'✓' if result.get('passed') else '✗'}")
        
        # Test 3: Very large coordinates
        result = self.run_test(
            "Movement - Large Coordinates",
            "validator:movement:validate",
            {
                "from_x": 1000000.0, "from_y": 1000000.0,
                "to_x": 1000001.0, "to_y": 1000001.0,
                "movement_type": "walk",
                "entity_capacity": 10.0
            }
        )
        print(f"Large coords: {'✓' if result.get('passed') else '✗'}")
        
        # Test 4: Teleport (instant movement)
        result = self.run_test(
            "Movement - Teleport",
            "validator:movement:validate",
            {
                "from_x": 0.0, "from_y": 0.0,
                "to_x": 100.0, "to_y": 100.0,
                "movement_type": "teleport",
                "entity_capacity": 10.0
            }
        )
        print(f"Teleport: {'✓' if result.get('passed') else '✗'}")
        
        # Test 5: Movement with obstacles
        # First add some obstacles
        self.client.send_event("validator:movement:add_obstacle", {"x": 5, "y": 5})
        self.client.send_event("validator:movement:add_obstacle", {"x": 6, "y": 6})
        
        result = self.run_test(
            "Movement - Through Obstacle",
            "validator:movement:validate",
            {
                "from_x": 0.0, "from_y": 0.0,
                "to_x": 10.0, "to_y": 10.0,
                "movement_type": "walk",
                "entity_capacity": 10.0
            }
        )
        print(f"Through obstacle: {'✓' if result.get('passed') else '✗'}")
        
        # Clear obstacles for clean state
        self.client.send_event("validator:movement:clear_obstacles", {})
    
    def test_resource_edge_cases(self):
        """Test resource transfer edge cases."""
        print("\n=== Resource Transfer Edge Cases ===")
        
        # Setup: Create entities with resources
        self.client.send_event("validator:resource:update_ownership", {
            "entity": "rich_agent",
            "resource_type": "gold",
            "amount": 1000000.0
        })
        self.client.send_event("validator:resource:update_ownership", {
            "entity": "poor_agent",
            "resource_type": "gold",
            "amount": 1.0
        })
        
        # Test 1: Zero amount transfer
        result = self.run_test(
            "Resource - Zero Amount Transfer",
            "validator:resource:validate",
            {
                "from_entity": "rich_agent",
                "to_entity": "poor_agent",
                "resource_type": "gold",
                "amount": 0.0,
                "transfer_type": "gift"
            }
        )
        print(f"Zero transfer: {'✓' if result.get('passed') else '✗'}")
        
        # Test 2: Negative amount transfer
        result = self.run_test(
            "Resource - Negative Amount",
            "validator:resource:validate",
            {
                "from_entity": "rich_agent",
                "to_entity": "poor_agent",
                "resource_type": "gold",
                "amount": -10.0,
                "transfer_type": "trade"
            }
        )
        print(f"Negative amount: {'✓' if result.get('passed') else '✗'}")
        
        # Test 3: Transfer to self
        result = self.run_test(
            "Resource - Self Transfer",
            "validator:resource:validate",
            {
                "from_entity": "rich_agent",
                "to_entity": "rich_agent",
                "resource_type": "gold",
                "amount": 100.0,
                "transfer_type": "trade"
            }
        )
        print(f"Self transfer: {'✓' if result.get('passed') else '✗'}")
        
        # Test 4: Theft (no consent required)
        result = self.run_test(
            "Resource - Theft",
            "validator:resource:validate",
            {
                "from_entity": "rich_agent",
                "to_entity": "poor_agent",
                "resource_type": "gold",
                "amount": 100.0,
                "transfer_type": "theft"
            }
        )
        print(f"Theft: {'✓' if result.get('passed') else '✗'}")
        
        # Test 5: Extreme wealth inequality transfer
        result = self.run_test(
            "Resource - Extreme Inequality",
            "validator:resource:validate",
            {
                "from_entity": "poor_agent",
                "to_entity": "rich_agent",
                "resource_type": "gold",
                "amount": 0.5,
                "transfer_type": "trade"
            }
        )
        print(f"Extreme inequality: {'✓' if result.get('passed') else '✗'}")
        
        # Test 6: Non-existent resource type
        result = self.run_test(
            "Resource - Unknown Resource Type",
            "validator:resource:validate",
            {
                "from_entity": "rich_agent",
                "to_entity": "poor_agent",
                "resource_type": "unobtainium",
                "amount": 10.0,
                "transfer_type": "trade"
            }
        )
        print(f"Unknown resource: {'✓' if result.get('passed') else '✗'}")
    
    def test_interaction_edge_cases(self):
        """Test interaction validation edge cases."""
        print("\n=== Interaction Validation Edge Cases ===")
        
        # Test 1: Self interaction
        result = self.run_test(
            "Interaction - Self Interaction",
            "validator:interaction:validate",
            {
                "actor_id": "agent_1",
                "target_id": "agent_1",
                "interaction_type": "cooperate",
                "actor_x": 0.0, "actor_y": 0.0,
                "target_x": 0.0, "target_y": 0.0,
                "range_limit": 5.0,
                "capabilities": ["cooperate"]
            }
        )
        print(f"Self interaction: {'✓' if result.get('passed') else '✗'}")
        
        # Test 2: Zero range limit
        result = self.run_test(
            "Interaction - Zero Range",
            "validator:interaction:validate",
            {
                "actor_id": "agent_1",
                "target_id": "agent_2",
                "interaction_type": "cooperate",
                "actor_x": 0.0, "actor_y": 0.0,
                "target_x": 0.0, "target_y": 0.0,
                "range_limit": 0.0,
                "capabilities": ["cooperate"]
            }
        )
        print(f"Zero range: {'✓' if result.get('passed') else '✗'}")
        
        # Test 3: Negative range limit
        result = self.run_test(
            "Interaction - Negative Range",
            "validator:interaction:validate",
            {
                "actor_id": "agent_1",
                "target_id": "agent_2",
                "interaction_type": "cooperate",
                "actor_x": 0.0, "actor_y": 0.0,
                "target_x": 1.0, "target_y": 1.0,
                "range_limit": -5.0,
                "capabilities": ["cooperate"]
            }
        )
        print(f"Negative range: {'✓' if result.get('passed') else '✗'}")
        
        # Test 4: Missing capabilities
        result = self.run_test(
            "Interaction - No Capabilities",
            "validator:interaction:validate",
            {
                "actor_id": "agent_1",
                "target_id": "agent_2",
                "interaction_type": "compete",
                "actor_x": 0.0, "actor_y": 0.0,
                "target_x": 1.0, "target_y": 1.0,
                "range_limit": 5.0,
                "capabilities": []
            }
        )
        print(f"No capabilities: {'✓' if result.get('passed') else '✗'}")
        
        # Test 5: Unknown interaction type
        result = self.run_test(
            "Interaction - Unknown Type",
            "validator:interaction:validate",
            {
                "actor_id": "agent_1",
                "target_id": "agent_2",
                "interaction_type": "mind_meld",
                "actor_x": 0.0, "actor_y": 0.0,
                "target_x": 1.0, "target_y": 1.0,
                "range_limit": 5.0,
                "capabilities": ["mind_meld"]
            }
        )
        print(f"Unknown type: {'✓' if result.get('passed') else '✗'}")
        
        # Test 6: Update trust relationship
        update_result = self.client.send_event("validator:interaction:update_relationship", {
            "entity1": "agent_1",
            "entity2": "agent_2",
            "trust_score": 0.9
        })
        
        # Now test interaction with high trust
        result = self.run_test(
            "Interaction - High Trust",
            "validator:interaction:validate",
            {
                "actor_id": "agent_1",
                "target_id": "agent_2",
                "interaction_type": "cooperate",
                "actor_x": 0.0, "actor_y": 0.0,
                "target_x": 1.0, "target_y": 1.0,
                "range_limit": 5.0,
                "capabilities": ["cooperate"]
            }
        )
        print(f"High trust: {'✓' if result.get('passed') else '✗'}")
    
    def test_batch_validation(self):
        """Test batch validation with mixed requests."""
        print("\n=== Batch Validation Tests ===")
        
        # Create a batch of mixed validation requests
        batch_request = {
            "movement_requests": [
                {
                    "from_x": 0.0, "from_y": 0.0,
                    "to_x": 3.0, "to_y": 4.0,
                    "movement_type": "walk",
                    "entity_capacity": 10.0
                },
                {
                    "from_x": 10.0, "from_y": 10.0,
                    "to_x": 15.0, "to_y": 15.0,
                    "movement_type": "run",
                    "entity_capacity": 15.0
                }
            ],
            "resource_requests": [
                {
                    "from_entity": "rich_agent",
                    "to_entity": "poor_agent",
                    "resource_type": "gold",
                    "amount": 10.0,
                    "transfer_type": "gift"
                }
            ],
            "interaction_requests": [
                {
                    "actor_id": "agent_1",
                    "target_id": "agent_2",
                    "interaction_type": "cooperate",
                    "actor_x": 0.0, "actor_y": 0.0,
                    "target_x": 2.0, "target_y": 2.0,
                    "range_limit": 5.0,
                    "capabilities": ["cooperate"]
                }
            ]
        }
        
        result = self.client.send_event("validator:batch:validate_all", batch_request)
        
        summary = result.get("summary", {})
        print(f"Batch validation:")
        print(f"  Total: {summary.get('total_requests', 0)}")
        print(f"  Valid: {summary.get('valid_count', 0)}")
        print(f"  Pass rate: {summary.get('pass_rate', 0)*100:.1f}%")
    
    def stress_test_validators(self, num_requests: int = 100):
        """Stress test validators with rapid requests."""
        print(f"\n=== Stress Test ({num_requests} requests) ===")
        
        start_time = time.time()
        successes = 0
        failures = 0
        
        for i in range(num_requests):
            # Randomly choose a validator
            validator_type = random.choice(["movement", "resource", "interaction"])
            
            try:
                if validator_type == "movement":
                    result = self.client.send_event("validator:movement:validate", {
                        "from_x": random.uniform(-100, 100),
                        "from_y": random.uniform(-100, 100),
                        "to_x": random.uniform(-100, 100),
                        "to_y": random.uniform(-100, 100),
                        "movement_type": random.choice(["walk", "run", "fly"]),
                        "entity_capacity": random.uniform(1, 20)
                    })
                elif validator_type == "resource":
                    result = self.client.send_event("validator:resource:validate", {
                        "from_entity": f"agent_{random.randint(1, 10)}",
                        "to_entity": f"agent_{random.randint(1, 10)}",
                        "resource_type": random.choice(["gold", "wood", "food"]),
                        "amount": random.uniform(0.1, 100),
                        "transfer_type": random.choice(["trade", "gift", "theft"])
                    })
                else:  # interaction
                    result = self.client.send_event("validator:interaction:validate", {
                        "actor_id": f"agent_{random.randint(1, 10)}",
                        "target_id": f"agent_{random.randint(1, 10)}",
                        "interaction_type": random.choice(["cooperate", "compete", "trade"]),
                        "actor_x": random.uniform(-100, 100),
                        "actor_y": random.uniform(-100, 100),
                        "target_x": random.uniform(-100, 100),
                        "target_y": random.uniform(-100, 100),
                        "range_limit": random.uniform(1, 50),
                        "capabilities": [random.choice(["cooperate", "compete", "trade"])]
                    })
                
                if isinstance(result, list) and len(result) > 0:
                    result = result[0]
                
                if result.get("valid") or result.get("status") == "success":
                    successes += 1
                else:
                    failures += 1
                    
            except Exception as e:
                print(f"Error in request {i}: {e}")
                failures += 1
        
        elapsed = time.time() - start_time
        
        print(f"Stress test results:")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Requests/sec: {num_requests/elapsed:.1f}")
        print(f"  Successes: {successes}")
        print(f"  Failures: {failures}")
    
    def run_all_tests(self):
        """Run all edge case tests."""
        self.create_test_suite("Melting Pot Edge Case Tests")
        
        self.test_movement_edge_cases()
        self.test_resource_edge_cases()
        self.test_interaction_edge_cases()
        self.test_batch_validation()
        self.stress_test_validators(100)
        
        # Finish the suite
        report = self.client.send_event("testing:suite:finish", {
            "suite_id": self.suite_id
        })
        
        print("\n=== Final Test Report ===")
        print(f"Suite: {self.suite_id}")
        print(f"Total tests: {len(report.get('tests', []))}")
        print(f"Passed: {report.get('passed', 0)}")
        print(f"Failed: {report.get('failed', 0)}")
        print(f"Pass rate: {report.get('pass_rate', 0)*100:.1f}%")
        print(f"Duration: {report.get('duration', 0):.3f}s")

if __name__ == "__main__":
    tester = MeltingPotEdgeCaseTests()
    tester.run_all_tests()