#!/usr/bin/env python3
"""
Integration test: Melting Pot scenarios with validators.
Demonstrates how validators enforce rules in actual game scenarios.
"""

import time
import random
from typing import Dict, List, Any, Tuple
from ksi_common.sync_client import MinimalSyncClient

class MeltingPotScenarioIntegration:
    """Run Melting Pot scenarios with validator enforcement."""
    
    def __init__(self):
        self.client = MinimalSyncClient()
        self.episode_id = None
        self.agents = []
        self.resources = {}
        self.positions = {}
    
    def setup_prisoners_dilemma(self) -> str:
        """
        Set up a Prisoners Dilemma scenario with validators.
        
        Two agents must decide whether to cooperate or defect.
        Validators ensure movement and interaction rules are followed.
        """
        print("\n=== Setting Up Prisoners Dilemma in the Matrix ===")
        
        # Create episode
        result = self.client.send_event("episode:create", {
            "scenario_type": "prisoners_dilemma",
            "config": {
                "grid_size": 10,
                "max_steps": 100,
                "payoff_matrix": {
                    "both_cooperate": 3,
                    "both_defect": 1,
                    "cooperate_vs_defect": 0,
                    "defect_vs_cooperate": 5
                }
            }
        })
        self.episode_id = result.get("episode_id", "pd_episode_001")
        
        # Initialize spatial system
        self.client.send_event("spatial:initialize", {
            "episode_id": self.episode_id,
            "grid_size": [10, 10],
            "terrain_type": "matrix"
        })
        
        # Create two agents
        self.agents = ["neo", "morpheus"]
        
        # Place agents at opposite corners
        self.positions["neo"] = [2, 2]
        self.positions["morpheus"] = [7, 7]
        
        for agent_id in self.agents:
            self.client.send_event("spatial:entity:add", {
                "episode_id": self.episode_id,
                "entity_id": agent_id,
                "position": self.positions[agent_id],
                "entity_type": "agent"
            })
            
            # Give each agent initial resources
            self.client.send_event("validator:resource:update_ownership", {
                "entity": agent_id,
                "resource_type": "trust_points",
                "amount": 10.0
            })
            self.resources[agent_id] = {"trust_points": 10.0}
        
        print(f"Episode created: {self.episode_id}")
        print(f"Agents placed: Neo at {self.positions['neo']}, Morpheus at {self.positions['morpheus']}")
        
        return self.episode_id
    
    def test_movement_validation(self):
        """Test movement with validator enforcement."""
        print("\n=== Testing Movement with Validation ===")
        
        # Test 1: Valid movement (within walk distance)
        print("\n1. Neo attempts to walk to nearby position...")
        current_pos = self.positions["neo"]
        new_pos = [current_pos[0] + 2, current_pos[1] + 2]  # Distance ~2.8
        
        # Validate movement first
        validation = self.client.send_event("validator:movement:validate", {
            "from_x": current_pos[0],
            "from_y": current_pos[1],
            "to_x": new_pos[0],
            "to_y": new_pos[1],
            "movement_type": "walk"
        })
        
        if validation.get("valid"):
            # Execute movement
            self.client.send_event("spatial:move", {
                "episode_id": self.episode_id,
                "entity_id": "neo",
                "to_position": new_pos
            })
            self.positions["neo"] = new_pos
            print(f"   ✓ Movement validated and executed. Neo now at {new_pos}")
        else:
            print(f"   ✗ Movement rejected: {validation.get('reason')}")
        
        # Test 2: Invalid movement (exceeds walk distance)
        print("\n2. Morpheus attempts to walk too far...")
        current_pos = self.positions["morpheus"]
        far_pos = [current_pos[0] - 6, current_pos[1] - 6]  # Distance ~8.5
        
        validation = self.client.send_event("validator:movement:validate", {
            "from_x": current_pos[0],
            "from_y": current_pos[1],
            "to_x": far_pos[0],
            "to_y": far_pos[1],
            "movement_type": "walk"
        })
        
        if validation.get("valid"):
            self.client.send_event("spatial:move", {
                "episode_id": self.episode_id,
                "entity_id": "morpheus",
                "to_position": far_pos
            })
            self.positions["morpheus"] = far_pos
            print(f"   ✓ Movement validated and executed. Morpheus now at {far_pos}")
        else:
            print(f"   ✗ Movement rejected: {validation.get('reason')}")
            # Try suggested path if available
            if validation.get("suggested_path"):
                print(f"   → Suggested path: {validation['suggested_path'][:3]}...")
    
    def test_interaction_validation(self):
        """Test interaction with validator enforcement."""
        print("\n=== Testing Interaction with Validation ===")
        
        # Calculate distance between agents
        neo_pos = self.positions["neo"]
        morpheus_pos = self.positions["morpheus"]
        distance = ((neo_pos[0] - morpheus_pos[0])**2 + 
                   (neo_pos[1] - morpheus_pos[1])**2)**0.5
        
        print(f"Distance between agents: {distance:.2f}")
        
        # Test cooperation interaction
        print("\n1. Neo attempts to cooperate with Morpheus...")
        
        validation = self.client.send_event("validator:interaction:validate", {
            "actor_id": "neo",
            "target_id": "morpheus",
            "interaction_type": "cooperate",
            "actor_x": neo_pos[0],
            "actor_y": neo_pos[1],
            "target_x": morpheus_pos[0],
            "target_y": morpheus_pos[1],
            "range_limit": 5.0,
            "capabilities": ["cooperate"]
        })
        
        if validation.get("valid"):
            print(f"   ✓ Cooperation validated! Trust score: {validation.get('cooperation_score', 0)}")
            # Execute cooperation
            self.execute_cooperation("neo", "morpheus")
        else:
            print(f"   ✗ Cooperation rejected: {validation.get('reason')}")
            if validation.get("suggested_position"):
                print(f"   → Suggested position for interaction: {validation['suggested_position']}")
        
        # Test defection interaction
        print("\n2. Morpheus considers defecting...")
        
        validation = self.client.send_event("validator:interaction:validate", {
            "actor_id": "morpheus",
            "target_id": "neo",
            "interaction_type": "defect",
            "actor_x": morpheus_pos[0],
            "actor_y": morpheus_pos[1],
            "target_x": neo_pos[0],
            "target_y": neo_pos[1],
            "range_limit": 10.0,  # Defection has longer range
            "capabilities": ["defect"]
        })
        
        if validation.get("valid"):
            print(f"   ✓ Defection validated! Could defect from this position.")
        else:
            print(f"   ✗ Defection rejected: {validation.get('reason')}")
    
    def test_resource_validation(self):
        """Test resource transfer with validator enforcement."""
        print("\n=== Testing Resource Transfer with Validation ===")
        
        # Test trust point transfer
        print("\n1. Neo attempts to transfer trust points to Morpheus...")
        
        transfer_amount = 3.0
        validation = self.client.send_event("validator:resource:validate", {
            "from_entity": "neo",
            "to_entity": "morpheus",
            "resource_type": "trust_points",
            "amount": transfer_amount,
            "transfer_type": "cooperation_reward"
        })
        
        if validation.get("valid"):
            # Execute transfer
            self.client.send_event("resource:transfer", {
                "episode_id": self.episode_id,
                "from_entity": "neo",
                "to_entity": "morpheus",
                "resource_type": "trust_points",
                "amount": transfer_amount
            })
            self.resources["neo"]["trust_points"] -= transfer_amount
            self.resources["morpheus"]["trust_points"] += transfer_amount
            print(f"   ✓ Transfer validated and executed.")
            print(f"   Neo: {self.resources['neo']['trust_points']} points")
            print(f"   Morpheus: {self.resources['morpheus']['trust_points']} points")
        else:
            print(f"   ✗ Transfer rejected: {validation.get('reason')}")
            if validation.get("suggested_amount"):
                print(f"   → Suggested amount: {validation['suggested_amount']}")
        
        # Test excessive transfer (should fail)
        print("\n2. Morpheus attempts excessive transfer...")
        
        validation = self.client.send_event("validator:resource:validate", {
            "from_entity": "morpheus",
            "to_entity": "neo",
            "resource_type": "trust_points",
            "amount": 100.0,  # More than Morpheus has
            "transfer_type": "trade"
        })
        
        if validation.get("valid"):
            print(f"   ✓ Transfer validated (unexpected!)")
        else:
            print(f"   ✗ Transfer rejected: {validation.get('reason')}")
    
    def execute_cooperation(self, agent1: str, agent2: str):
        """Execute cooperation between agents."""
        # Apply payoff matrix
        payoff = 3  # Both cooperate
        
        # Update resources
        self.client.send_event("resource:create", {
            "episode_id": self.episode_id,
            "resource_type": "cooperation_points",
            "amount": payoff,
            "owner": agent1
        })
        
        self.client.send_event("resource:create", {
            "episode_id": self.episode_id,
            "resource_type": "cooperation_points",
            "amount": payoff,
            "owner": agent2
        })
        
        print(f"   → Both agents earned {payoff} cooperation points")
    
    def test_strategic_movement(self):
        """Test strategic movement validation."""
        print("\n=== Testing Strategic Movement ===")
        
        # Move agents closer for interaction
        print("\n1. Agents move strategically to enable cooperation...")
        
        # Neo moves toward center
        neo_target = [5, 5]
        validation = self.client.send_event("validator:movement:validate", {
            "from_x": self.positions["neo"][0],
            "from_y": self.positions["neo"][1],
            "to_x": neo_target[0],
            "to_y": neo_target[1],
            "movement_type": "walk"
        })
        
        if validation.get("valid"):
            self.positions["neo"] = neo_target
            print(f"   ✓ Neo moved to center: {neo_target}")
        else:
            # Use suggested path
            if validation.get("suggested_path") and len(validation["suggested_path"]) > 1:
                next_pos = validation["suggested_path"][1]
                self.positions["neo"] = [next_pos["x"], next_pos["y"]]
                print(f"   → Neo moved along path to: {self.positions['neo']}")
        
        # Morpheus moves toward center
        morpheus_target = [5, 6]
        validation = self.client.send_event("validator:movement:validate", {
            "from_x": self.positions["morpheus"][0],
            "from_y": self.positions["morpheus"][1],
            "to_x": morpheus_target[0],
            "to_y": morpheus_target[1],
            "movement_type": "walk"
        })
        
        if validation.get("valid"):
            self.positions["morpheus"] = morpheus_target
            print(f"   ✓ Morpheus moved to: {morpheus_target}")
        else:
            if validation.get("suggested_path") and len(validation["suggested_path"]) > 1:
                next_pos = validation["suggested_path"][1]
                self.positions["morpheus"] = [next_pos["x"], next_pos["y"]]
                print(f"   → Morpheus moved along path to: {self.positions['morpheus']}")
        
        # Now test interaction at new positions
        distance = ((self.positions["neo"][0] - self.positions["morpheus"][0])**2 + 
                   (self.positions["neo"][1] - self.positions["morpheus"][1])**2)**0.5
        print(f"\n2. New distance between agents: {distance:.2f}")
        
        if distance <= 2.0:
            print("   ✓ Agents are now in cooperation range!")
        else:
            print("   → Agents need to move closer for optimal cooperation")
    
    def calculate_metrics(self):
        """Calculate game theory metrics."""
        print("\n=== Game Theory Metrics ===")
        
        result = self.client.send_event("metrics:calculate", {
            "episode_id": self.episode_id,
            "metrics": ["cooperation_rate", "collective_return", "fairness"]
        })
        
        if result.get("metrics"):
            for metric, value in result["metrics"].items():
                print(f"  {metric}: {value}")
    
    def run_integrated_test(self):
        """Run complete integration test."""
        print("\n" + "="*60)
        print("MELTING POT SCENARIO WITH VALIDATOR INTEGRATION")
        print("="*60)
        
        # Setup scenario
        self.setup_prisoners_dilemma()
        
        # Test validator integration
        self.test_movement_validation()
        self.test_interaction_validation()
        self.test_resource_validation()
        self.test_strategic_movement()
        
        # Calculate metrics
        self.calculate_metrics()
        
        # Cleanup
        self.client.send_event("episode:terminate", {
            "episode_id": self.episode_id
        })
        
        print("\n=== Integration Test Complete ===")
        print("✓ Movement validation integrated")
        print("✓ Interaction validation integrated")
        print("✓ Resource validation integrated")
        print("✓ Strategic decision-making demonstrated")

if __name__ == "__main__":
    tester = MeltingPotScenarioIntegration()
    tester.run_integrated_test()