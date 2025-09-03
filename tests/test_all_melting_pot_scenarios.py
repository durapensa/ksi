#!/usr/bin/env python3
"""
Comprehensive test of all 5 Melting Pot scenarios with validator integration.
Tests each scenario's unique mechanics and validator interactions.
"""

import time
import random
from typing import Dict, List, Any
from enum import Enum
from dataclasses import dataclass
from ksi_common.sync_client import MinimalSyncClient

class MeltingPotScenario(Enum):
    """Core Melting Pot scenarios."""
    PRISONERS_DILEMMA = "prisoners_dilemma_in_the_matrix"
    STAG_HUNT = "stag_hunt"
    COMMONS_HARVEST = "commons_harvest"
    CLEANUP = "cleanup"
    COLLABORATIVE_COOKING = "collaborative_cooking"

@dataclass
class ScenarioTestResult:
    """Results from testing a scenario."""
    scenario: MeltingPotScenario
    setup_success: bool
    movement_validations: int
    resource_validations: int
    interaction_validations: int
    validation_failures: List[str]
    metrics: Dict[str, float]
    runtime: float

class ComprehensiveMeltingPotTest:
    """Test all Melting Pot scenarios with validators."""
    
    def __init__(self):
        self.client = MinimalSyncClient()
        self.results = []
    
    def test_prisoners_dilemma(self) -> ScenarioTestResult:
        """Test Prisoners Dilemma with validators."""
        print("\n=== Testing PRISONERS DILEMMA ===")
        start_time = time.time()
        result = ScenarioTestResult(
            scenario=MeltingPotScenario.PRISONERS_DILEMMA,
            setup_success=False,
            movement_validations=0,
            resource_validations=0,
            interaction_validations=0,
            validation_failures=[],
            metrics={},
            runtime=0
        )
        
        try:
            # Create episode
            episode = self.client.send_event("episode:create", {
                "scenario_type": "prisoners_dilemma",
                "config": {
                    "grid_size": 10,
                    "max_steps": 20,
                    "payoff_matrix": {
                        "both_cooperate": 3,
                        "both_defect": 1,
                        "cooperate_vs_defect": 0,
                        "defect_vs_cooperate": 5
                    }
                }
            })
            episode_id = episode.get("episode_id", "pd_test")
            result.setup_success = True
            
            # Initialize spatial
            self.client.send_event("spatial:initialize", {
                "episode_id": episode_id,
                "grid_size": [10, 10]
            })
            
            # Create two agents
            agents = ["agent_coop", "agent_defect"]
            positions = {"agent_coop": [2, 2], "agent_defect": [7, 7]}
            
            for agent_id in agents:
                self.client.send_event("spatial:entity:add", {
                    "episode_id": episode_id,
                    "entity_id": agent_id,
                    "position": positions[agent_id]
                })
            
            # Test movement validation
            for i in range(3):
                agent = random.choice(agents)
                new_x = positions[agent][0] + random.randint(-2, 2)
                new_y = positions[agent][1] + random.randint(-2, 2)
                
                validation = self.client.send_event("validator:movement:validate", {
                    "from_x": positions[agent][0],
                    "from_y": positions[agent][1],
                    "to_x": new_x,
                    "to_y": new_y,
                    "movement_type": "walk"
                })
                
                result.movement_validations += 1
                if not validation.get("valid"):
                    result.validation_failures.append(f"Movement: {validation.get('reason')}")
                else:
                    positions[agent] = [new_x, new_y]
            
            # Test interaction validation (cooperate/defect)
            for interaction_type in ["cooperate", "defect"]:
                validation = self.client.send_event("validator:interaction:validate", {
                    "actor_id": agents[0],
                    "target_id": agents[1],
                    "interaction_type": interaction_type,
                    "actor_x": positions[agents[0]][0],
                    "actor_y": positions[agents[0]][1],
                    "target_x": positions[agents[1]][0],
                    "target_y": positions[agents[1]][1],
                    "range_limit": 10,
                    "capabilities": [interaction_type]
                })
                
                result.interaction_validations += 1
                if not validation.get("valid"):
                    result.validation_failures.append(f"Interaction ({interaction_type}): {validation.get('reason')}")
            
            # Calculate metrics
            metrics = self.client.send_event("metrics:calculate", {
                "episode_id": episode_id,
                "metrics": ["cooperation_rate", "collective_return"]
            })
            result.metrics = metrics.get("metrics", {})
            
            # Cleanup
            self.client.send_event("episode:terminate", {"episode_id": episode_id})
            
        except Exception as e:
            result.validation_failures.append(f"Error: {str(e)}")
        
        result.runtime = time.time() - start_time
        return result
    
    def test_stag_hunt(self) -> ScenarioTestResult:
        """Test Stag Hunt with validators."""
        print("\n=== Testing STAG HUNT ===")
        start_time = time.time()
        result = ScenarioTestResult(
            scenario=MeltingPotScenario.STAG_HUNT,
            setup_success=False,
            movement_validations=0,
            resource_validations=0,
            interaction_validations=0,
            validation_failures=[],
            metrics={},
            runtime=0
        )
        
        try:
            # Create episode
            episode = self.client.send_event("episode:create", {
                "scenario_type": "stag_hunt",
                "config": {
                    "grid_size": 15,
                    "max_steps": 30,
                    "stag_reward": 10,
                    "hare_reward": 3,
                    "min_hunters_for_stag": 2
                }
            })
            episode_id = episode.get("episode_id", "sh_test")
            result.setup_success = True
            
            # Create resources (stags and hares)
            resources = [
                {"type": "stag", "position": [7, 7], "value": 10},
                {"type": "hare", "position": [3, 3], "value": 3},
                {"type": "hare", "position": [11, 11], "value": 3}
            ]
            
            for resource in resources:
                self.client.send_event("resource:create", {
                    "episode_id": episode_id,
                    "resource_type": resource["type"],
                    "amount": resource["value"],
                    "position": resource["position"]
                })
            
            # Create hunters
            hunters = ["hunter_1", "hunter_2", "hunter_3"]
            positions = {"hunter_1": [5, 5], "hunter_2": [9, 9], "hunter_3": [7, 5]}
            
            # Test coordination validation for stag hunting
            print("  Testing stag hunt coordination...")
            
            # Move hunters toward stag
            for hunter in hunters[:2]:  # Need 2 for stag
                current = positions[hunter]
                target = resources[0]["position"]  # Stag position
                
                # Validate movement toward stag
                validation = self.client.send_event("validator:movement:validate", {
                    "from_x": current[0],
                    "from_y": current[1],
                    "to_x": target[0],
                    "to_y": target[1],
                    "movement_type": "walk"
                })
                
                result.movement_validations += 1
                if not validation.get("valid"):
                    # Use suggested path if available
                    if validation.get("suggested_path"):
                        print(f"    Using suggested path for {hunter}")
                
            # Test interaction for coordinated hunting
            validation = self.client.send_event("validator:interaction:validate", {
                "actor_id": hunters[0],
                "target_id": hunters[1],
                "interaction_type": "coordinate",
                "actor_x": positions[hunters[0]][0],
                "actor_y": positions[hunters[0]][1],
                "target_x": positions[hunters[1]][0],
                "target_y": positions[hunters[1]][1],
                "range_limit": 5,
                "capabilities": ["hunt", "coordinate"]
            })
            
            result.interaction_validations += 1
            if not validation.get("valid"):
                result.validation_failures.append(f"Hunt coordination: {validation.get('reason')}")
            
            # Test resource collection validation
            validation = self.client.send_event("validator:resource:validate", {
                "from_entity": "environment",
                "to_entity": hunters[0],
                "resource_type": "stag",
                "amount": 10,
                "transfer_type": "harvest"
            })
            
            result.resource_validations += 1
            if not validation.get("valid"):
                result.validation_failures.append(f"Stag harvest: {validation.get('reason')}")
            
            # Cleanup
            self.client.send_event("episode:terminate", {"episode_id": episode_id})
            
        except Exception as e:
            result.validation_failures.append(f"Error: {str(e)}")
        
        result.runtime = time.time() - start_time
        return result
    
    def test_commons_harvest(self) -> ScenarioTestResult:
        """Test Commons Harvest with validators."""
        print("\n=== Testing COMMONS HARVEST ===")
        start_time = time.time()
        result = ScenarioTestResult(
            scenario=MeltingPotScenario.COMMONS_HARVEST,
            setup_success=False,
            movement_validations=0,
            resource_validations=0,
            interaction_validations=0,
            validation_failures=[],
            metrics={},
            runtime=0
        )
        
        try:
            # Create episode
            episode = self.client.send_event("episode:create", {
                "scenario_type": "commons_harvest",
                "config": {
                    "grid_size": 20,
                    "max_steps": 50,
                    "initial_resources": 1000,
                    "regeneration_rate": 0.02,
                    "sustainability_threshold": 200
                }
            })
            episode_id = episode.get("episode_id", "ch_test")
            result.setup_success = True
            
            # Create common resource pool
            self.client.send_event("resource:create", {
                "episode_id": episode_id,
                "resource_type": "apples",
                "amount": 1000,
                "owner": "commons"
            })
            
            # Create harvesters
            harvesters = ["sustainable_harvester", "greedy_harvester", "adaptive_harvester"]
            
            for harvester in harvesters:
                # Give initial capacity
                self.client.send_event("validator:resource:update_ownership", {
                    "entity": harvester,
                    "resource_type": "harvest_capacity",
                    "amount": 50.0
                })
            
            # Test sustainable vs greedy harvesting
            print("  Testing harvesting strategies...")
            
            # Sustainable harvest
            validation = self.client.send_event("validator:resource:validate", {
                "from_entity": "commons",
                "to_entity": "sustainable_harvester",
                "resource_type": "apples",
                "amount": 20,  # Below regeneration capacity
                "transfer_type": "harvest"
            })
            result.resource_validations += 1
            if not validation.get("valid"):
                result.validation_failures.append(f"Sustainable harvest: {validation.get('reason')}")
            
            # Greedy harvest
            validation = self.client.send_event("validator:resource:validate", {
                "from_entity": "commons",
                "to_entity": "greedy_harvester",
                "resource_type": "apples",
                "amount": 200,  # Excessive
                "transfer_type": "harvest"
            })
            result.resource_validations += 1
            # This might be valid but harmful to sustainability
            
            # Test fairness mechanism
            print("  Testing fairness enforcement...")
            validation = self.client.send_event("validator:resource:validate", {
                "from_entity": "greedy_harvester",
                "to_entity": "sustainable_harvester",
                "resource_type": "apples",
                "amount": 50,
                "transfer_type": "redistribution"
            })
            result.resource_validations += 1
            
            # Calculate sustainability metrics
            metrics = self.client.send_event("metrics:calculate", {
                "episode_id": episode_id,
                "metrics": ["sustainability_index", "gini_coefficient", "resource_depletion_rate"]
            })
            result.metrics = metrics.get("metrics", {})
            
            # Cleanup
            self.client.send_event("episode:terminate", {"episode_id": episode_id})
            
        except Exception as e:
            result.validation_failures.append(f"Error: {str(e)}")
        
        result.runtime = time.time() - start_time
        return result
    
    def test_cleanup(self) -> ScenarioTestResult:
        """Test Cleanup with validators."""
        print("\n=== Testing CLEANUP ===")
        start_time = time.time()
        result = ScenarioTestResult(
            scenario=MeltingPotScenario.CLEANUP,
            setup_success=False,
            movement_validations=0,
            resource_validations=0,
            interaction_validations=0,
            validation_failures=[],
            metrics={},
            runtime=0
        )
        
        try:
            # Create episode
            episode = self.client.send_event("episode:create", {
                "scenario_type": "cleanup",
                "config": {
                    "grid_size": 15,
                    "max_steps": 40,
                    "initial_pollution": 100,
                    "pollution_growth_rate": 0.05,
                    "production_pollution_ratio": 2
                }
            })
            episode_id = episode.get("episode_id", "cu_test")
            result.setup_success = True
            
            # Create pollution
            self.client.send_event("resource:create", {
                "episode_id": episode_id,
                "resource_type": "pollution",
                "amount": 100,
                "owner": "environment"
            })
            
            # Create agents
            agents = ["cleaner", "producer", "balanced"]
            
            # Test cleanup action validation
            print("  Testing cleanup mechanics...")
            
            # Validate cleanup action
            validation = self.client.send_event("validator:resource:validate", {
                "from_entity": "environment",
                "to_entity": "cleaner",
                "resource_type": "pollution",
                "amount": -10,  # Removing pollution
                "transfer_type": "cleanup"
            })
            result.resource_validations += 1
            if not validation.get("valid"):
                result.validation_failures.append(f"Cleanup action: {validation.get('reason')}")
            
            # Validate production (creates pollution)
            validation = self.client.send_event("validator:resource:validate", {
                "from_entity": "producer",
                "to_entity": "environment",
                "resource_type": "pollution",
                "amount": 5,  # Creating pollution
                "transfer_type": "production_byproduct"
            })
            result.resource_validations += 1
            
            # Test public good provision
            print("  Testing public good dynamics...")
            
            # Clean air as public good
            validation = self.client.send_event("validator:resource:validate", {
                "from_entity": "cleaner",
                "to_entity": "all_agents",
                "resource_type": "clean_air",
                "amount": 10,
                "transfer_type": "public_good"
            })
            result.resource_validations += 1
            
            # Calculate public good metrics
            metrics = self.client.send_event("metrics:calculate", {
                "episode_id": episode_id,
                "metrics": ["pollution_level", "public_good_provision", "free_rider_index"]
            })
            result.metrics = metrics.get("metrics", {})
            
            # Cleanup
            self.client.send_event("episode:terminate", {"episode_id": episode_id})
            
        except Exception as e:
            result.validation_failures.append(f"Error: {str(e)}")
        
        result.runtime = time.time() - start_time
        return result
    
    def test_collaborative_cooking(self) -> ScenarioTestResult:
        """Test Collaborative Cooking with validators."""
        print("\n=== Testing COLLABORATIVE COOKING ===")
        start_time = time.time()
        result = ScenarioTestResult(
            scenario=MeltingPotScenario.COLLABORATIVE_COOKING,
            setup_success=False,
            movement_validations=0,
            resource_validations=0,
            interaction_validations=0,
            validation_failures=[],
            metrics={},
            runtime=0
        )
        
        try:
            # Create episode
            episode = self.client.send_event("episode:create", {
                "scenario_type": "collaborative_cooking",
                "config": {
                    "grid_size": 12,
                    "max_steps": 60,
                    "recipes": [
                        {"name": "soup", "ingredients": ["tomato", "onion"], "reward": 10},
                        {"name": "salad", "ingredients": ["lettuce", "tomato"], "reward": 8}
                    ]
                }
            })
            episode_id = episode.get("episode_id", "cc_test")
            result.setup_success = True
            
            # Create cooking stations and ingredients
            stations = [
                {"type": "chopping_board", "position": [3, 3]},
                {"type": "pot", "position": [9, 9]},
                {"type": "serving_counter", "position": [6, 6]}
            ]
            
            ingredients = [
                {"type": "tomato", "position": [2, 8]},
                {"type": "onion", "position": [8, 2]},
                {"type": "lettuce", "position": [5, 5]}
            ]
            
            # Create chefs
            chefs = ["chef_1", "chef_2", "chef_3"]
            positions = {"chef_1": [4, 4], "chef_2": [8, 8], "chef_3": [6, 2]}
            
            # Test movement to ingredients
            print("  Testing ingredient collection...")
            for chef in chefs[:2]:
                ingredient = ingredients[chefs.index(chef) % len(ingredients)]
                
                validation = self.client.send_event("validator:movement:validate", {
                    "from_x": positions[chef][0],
                    "from_y": positions[chef][1],
                    "to_x": ingredient["position"][0],
                    "to_y": ingredient["position"][1],
                    "movement_type": "walk"
                })
                result.movement_validations += 1
                
                if validation.get("valid"):
                    # Pick up ingredient
                    pickup_validation = self.client.send_event("validator:resource:validate", {
                        "from_entity": "environment",
                        "to_entity": chef,
                        "resource_type": ingredient["type"],
                        "amount": 1,
                        "transfer_type": "pickup"
                    })
                    result.resource_validations += 1
            
            # Test coordination for cooking
            print("  Testing cooking coordination...")
            
            # Chefs need to coordinate at stations
            validation = self.client.send_event("validator:interaction:validate", {
                "actor_id": chefs[0],
                "target_id": chefs[1],
                "interaction_type": "coordinate_cooking",
                "actor_x": stations[0]["position"][0],
                "actor_y": stations[0]["position"][1],
                "target_x": stations[0]["position"][0] + 1,
                "target_y": stations[0]["position"][1],
                "range_limit": 2,
                "capabilities": ["cook", "coordinate"]
            })
            result.interaction_validations += 1
            
            # Test recipe completion
            validation = self.client.send_event("validator:resource:validate", {
                "from_entity": "cooking_station",
                "to_entity": "serving_counter",
                "resource_type": "soup",
                "amount": 1,
                "transfer_type": "serve"
            })
            result.resource_validations += 1
            
            # Calculate cooperation metrics
            metrics = self.client.send_event("metrics:calculate", {
                "episode_id": episode_id,
                "metrics": ["coordination_efficiency", "task_completion_rate", "role_specialization"]
            })
            result.metrics = metrics.get("metrics", {})
            
            # Cleanup
            self.client.send_event("episode:terminate", {"episode_id": episode_id})
            
        except Exception as e:
            result.validation_failures.append(f"Error: {str(e)}")
        
        result.runtime = time.time() - start_time
        return result
    
    def print_summary(self):
        """Print comprehensive test summary."""
        print("\n" + "="*80)
        print("ALL MELTING POT SCENARIOS TEST SUMMARY")
        print("="*80)
        
        total_validations = 0
        total_failures = 0
        
        for result in self.results:
            print(f"\n{result.scenario.value.upper()}:")
            print(f"  Setup: {'✓' if result.setup_success else '✗'}")
            print(f"  Movement validations: {result.movement_validations}")
            print(f"  Resource validations: {result.resource_validations}")
            print(f"  Interaction validations: {result.interaction_validations}")
            
            total_validations += (result.movement_validations + 
                                 result.resource_validations + 
                                 result.interaction_validations)
            
            if result.validation_failures:
                print(f"  Failures: {len(result.validation_failures)}")
                for failure in result.validation_failures[:2]:  # Show first 2
                    print(f"    - {failure}")
                total_failures += len(result.validation_failures)
            else:
                print(f"  Failures: None ✓")
            
            if result.metrics:
                print(f"  Metrics collected: {len(result.metrics)}")
            
            print(f"  Runtime: {result.runtime:.2f}s")
        
        print(f"\n=== OVERALL STATISTICS ===")
        print(f"Total scenarios tested: {len(self.results)}")
        print(f"Total validations performed: {total_validations}")
        print(f"Total validation failures: {total_failures}")
        print(f"Success rate: {((total_validations - total_failures) / total_validations * 100) if total_validations > 0 else 0:.1f}%")
        
        # Check for systemic issues
        print(f"\n=== SYSTEMIC ISSUES ===")
        common_failures = {}
        for result in self.results:
            for failure in result.validation_failures:
                failure_type = failure.split(":")[0]
                common_failures[failure_type] = common_failures.get(failure_type, 0) + 1
        
        if common_failures:
            print("Common failure patterns:")
            for failure_type, count in sorted(common_failures.items(), key=lambda x: x[1], reverse=True):
                print(f"  - {failure_type}: {count} occurrences")
        else:
            print("No systemic issues detected ✓")
    
    def run_all_tests(self):
        """Run tests for all scenarios."""
        print("\nStarting Comprehensive Melting Pot Scenario Tests")
        print("="*80)
        
        # Test each scenario
        self.results.append(self.test_prisoners_dilemma())
        self.results.append(self.test_stag_hunt())
        self.results.append(self.test_commons_harvest())
        self.results.append(self.test_cleanup())
        self.results.append(self.test_collaborative_cooking())
        
        # Print summary
        self.print_summary()

if __name__ == "__main__":
    tester = ComprehensiveMeltingPotTest()
    tester.run_all_tests()