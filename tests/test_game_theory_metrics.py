#!/usr/bin/env python3
"""
Test the game theory metrics pipeline for Melting Pot scenarios.
Validates metrics calculation and fairness analysis.
"""

import time
import random
from typing import Dict, List, Any
from ksi_common.sync_client import MinimalSyncClient

class GameTheoryMetricsTest:
    """Test game theory metrics calculation and analysis."""
    
    def __init__(self):
        self.client = MinimalSyncClient()
        self.episode_id = None
        self.agents = []
        self.resources = {}
    
    def setup_test_scenario(self):
        """Set up a test scenario with agents and resources."""
        print("\n=== Setting Up Test Scenario ===")
        
        # Create episode
        result = self.client.send_event("episode:create", {
            "scenario_type": "metrics_test",
            "config": {
                "grid_size": 10,
                "max_steps": 100,
                "num_agents": 5
            }
        })
        self.episode_id = result.get("episode_id", "metrics_test_001")
        
        # Create agents with varying wealth levels
        wealth_distribution = [1000, 500, 200, 100, 50]  # Unequal distribution
        self.agents = []
        
        for i, wealth in enumerate(wealth_distribution):
            agent_id = f"agent_{i+1}"
            self.agents.append(agent_id)
            
            # Set up resources for each agent
            self.client.send_event("validator:resource:update_ownership", {
                "entity": agent_id,
                "resource_type": "gold",
                "amount": float(wealth),
                "episode_id": self.episode_id
            })
            
            self.client.send_event("validator:resource:update_ownership", {
                "entity": agent_id,
                "resource_type": "trust_points",
                "amount": random.uniform(0, 100),
                "episode_id": self.episode_id
            })
            
            self.resources[agent_id] = {
                "gold": wealth,
                "trust_points": random.uniform(0, 100)
            }
        
        print(f"Created {len(self.agents)} agents with wealth distribution: {wealth_distribution}")
        return True
    
    def test_basic_metrics(self):
        """Test basic game theory metrics calculation."""
        print("\n=== Testing Basic Metrics ===")
        
        # Test metrics:calculate event
        result = self.client.send_event("metrics:calculate", {
            "episode_id": self.episode_id,
            "metrics": ["gini_coefficient", "collective_return", "cooperation_rate"]
        })
        
        if result.get("status") == "success" or result.get("metrics"):
            metrics = result.get("metrics", {})
            print(f"✓ Metrics calculated successfully:")
            for metric, value in metrics.items():
                print(f"  - {metric}: {value}")
            return True
        else:
            print(f"✗ Metrics calculation failed: {result}")
            return False
    
    def test_gini_coefficient(self):
        """Test Gini coefficient calculation for wealth inequality."""
        print("\n=== Testing Gini Coefficient ===")
        
        # Calculate Gini coefficient manually
        wealth_values = [self.resources[agent]["gold"] for agent in self.agents]
        n = len(wealth_values)
        sorted_wealth = sorted(wealth_values)
        
        # Manual Gini calculation
        cumsum = 0
        for i, wealth in enumerate(sorted_wealth):
            cumsum += (2 * (i + 1) - n - 1) * wealth
        
        expected_gini = cumsum / (n * sum(sorted_wealth))
        print(f"Expected Gini (manual calculation): {expected_gini:.4f}")
        
        # Get Gini from metrics service
        result = self.client.send_event("metrics:calculate", {
            "episode_id": self.episode_id,
            "metrics": ["gini_coefficient"],
            "resource_type": "gold"
        })
        
        if result.get("metrics"):
            calculated_gini = result["metrics"].get("gini_coefficient", -1)
            print(f"Calculated Gini (metrics service): {calculated_gini:.4f}")
            
            # Check if they're reasonably close
            if abs(expected_gini - calculated_gini) < 0.1:
                print("✓ Gini coefficient calculation validated")
                return True
            else:
                print(f"✗ Gini mismatch: expected {expected_gini:.4f}, got {calculated_gini:.4f}")
                return False
        else:
            print("✗ Failed to calculate Gini coefficient")
            return False
    
    def test_cooperation_metrics(self):
        """Test cooperation and defection metrics."""
        print("\n=== Testing Cooperation Metrics ===")
        
        # Simulate some cooperation and defection events
        cooperation_count = 0
        defection_count = 0
        
        for _ in range(10):
            actor = random.choice(self.agents)
            target = random.choice([a for a in self.agents if a != actor])
            
            if random.random() < 0.6:  # 60% cooperation rate
                # Log cooperation
                self.client.send_event("metrics:log_interaction", {
                    "episode_id": self.episode_id,
                    "actor": actor,
                    "target": target,
                    "interaction_type": "cooperate",
                    "outcome": "success"
                })
                cooperation_count += 1
            else:
                # Log defection
                self.client.send_event("metrics:log_interaction", {
                    "episode_id": self.episode_id,
                    "actor": actor,
                    "target": target,
                    "interaction_type": "defect",
                    "outcome": "success"
                })
                defection_count += 1
        
        print(f"Simulated {cooperation_count} cooperations and {defection_count} defections")
        
        # Calculate cooperation rate
        result = self.client.send_event("metrics:calculate", {
            "episode_id": self.episode_id,
            "metrics": ["cooperation_rate", "defection_rate", "trust_level"]
        })
        
        if result.get("metrics"):
            print("✓ Cooperation metrics calculated:")
            for metric, value in result["metrics"].items():
                print(f"  - {metric}: {value}")
            return True
        else:
            print("✗ Failed to calculate cooperation metrics")
            return False
    
    def test_fairness_metrics(self):
        """Test fairness and exploitation metrics."""
        print("\n=== Testing Fairness Metrics ===")
        
        # Test fairness violation detection
        result = self.client.send_event("metrics:calculate", {
            "episode_id": self.episode_id,
            "metrics": ["fairness_violations", "exploitation_index", "monopoly_risk"]
        })
        
        if result.get("metrics"):
            print("✓ Fairness metrics calculated:")
            for metric, value in result["metrics"].items():
                print(f"  - {metric}: {value}")
            return True
        else:
            print("✗ Failed to calculate fairness metrics")
            return False
    
    def test_sustainability_metrics(self):
        """Test sustainability and resource depletion metrics."""
        print("\n=== Testing Sustainability Metrics ===")
        
        # Simulate resource consumption
        initial_total = sum(self.resources[agent]["gold"] for agent in self.agents)
        
        # Simulate some resource transfers
        for _ in range(5):
            # Random transfer
            from_agent = random.choice(self.agents)
            to_agent = random.choice([a for a in self.agents if a != from_agent])
            amount = random.uniform(10, 50)
            
            if self.resources[from_agent]["gold"] >= amount:
                self.resources[from_agent]["gold"] -= amount
                self.resources[to_agent]["gold"] += amount
                
                # Update in validator
                self.client.send_event("validator:resource:update_ownership", {
                    "entity": from_agent,
                    "resource_type": "gold",
                    "amount": self.resources[from_agent]["gold"],
                    "episode_id": self.episode_id
                })
                self.client.send_event("validator:resource:update_ownership", {
                    "entity": to_agent,
                    "resource_type": "gold",
                    "amount": self.resources[to_agent]["gold"],
                    "episode_id": self.episode_id
                })
        
        # Calculate sustainability metrics
        result = self.client.send_event("metrics:calculate", {
            "episode_id": self.episode_id,
            "metrics": ["sustainability_index", "resource_depletion_rate", "wealth_concentration"]
        })
        
        if result.get("metrics"):
            print("✓ Sustainability metrics calculated:")
            for metric, value in result["metrics"].items():
                print(f"  - {metric}: {value}")
            return True
        else:
            print("✗ Failed to calculate sustainability metrics")
            return False
    
    def test_pareto_efficiency(self):
        """Test Pareto efficiency calculation."""
        print("\n=== Testing Pareto Efficiency ===")
        
        # Test if current allocation is Pareto efficient
        result = self.client.send_event("metrics:calculate", {
            "episode_id": self.episode_id,
            "metrics": ["pareto_efficiency", "social_welfare", "utility_distribution"]
        })
        
        if result.get("metrics"):
            print("✓ Efficiency metrics calculated:")
            for metric, value in result["metrics"].items():
                print(f"  - {metric}: {value}")
            return True
        else:
            print("✗ Failed to calculate efficiency metrics")
            return False
    
    def test_nash_equilibrium(self):
        """Test Nash equilibrium distance calculation."""
        print("\n=== Testing Nash Equilibrium Distance ===")
        
        # Test distance from Nash equilibrium
        result = self.client.send_event("metrics:calculate", {
            "episode_id": self.episode_id,
            "metrics": ["nash_equilibrium_distance", "strategy_stability", "best_response_deviation"]
        })
        
        if result.get("metrics"):
            print("✓ Equilibrium metrics calculated:")
            for metric, value in result["metrics"].items():
                print(f"  - {metric}: {value}")
            return True
        else:
            print("✗ Failed to calculate equilibrium metrics")
            return False
    
    def test_metric_aggregation(self):
        """Test aggregation of multiple metrics."""
        print("\n=== Testing Metric Aggregation ===")
        
        # Request all available metrics
        all_metrics = [
            "gini_coefficient",
            "cooperation_rate",
            "collective_return",
            "fairness_violations",
            "sustainability_index",
            "pareto_efficiency",
            "nash_equilibrium_distance"
        ]
        
        result = self.client.send_event("metrics:calculate", {
            "episode_id": self.episode_id,
            "metrics": all_metrics
        })
        
        if result.get("metrics"):
            print("✓ All metrics aggregated successfully:")
            available_metrics = 0
            for metric in all_metrics:
                if metric in result["metrics"]:
                    print(f"  ✓ {metric}: {result['metrics'][metric]}")
                    available_metrics += 1
                else:
                    print(f"  ✗ {metric}: Not available")
            
            print(f"\nMetrics coverage: {available_metrics}/{len(all_metrics)} ({available_metrics/len(all_metrics)*100:.1f}%)")
            return available_metrics > len(all_metrics) * 0.5  # Success if >50% metrics available
        else:
            print("✗ Failed to aggregate metrics")
            return False
    
    def run_all_tests(self):
        """Run all game theory metrics tests."""
        print("\n" + "="*80)
        print("GAME THEORY METRICS PIPELINE TEST")
        print("="*80)
        
        # Setup
        if not self.setup_test_scenario():
            print("Failed to set up test scenario")
            return
        
        # Run tests
        test_results = {}
        test_results["basic"] = self.test_basic_metrics()
        test_results["gini"] = self.test_gini_coefficient()
        test_results["cooperation"] = self.test_cooperation_metrics()
        test_results["fairness"] = self.test_fairness_metrics()
        test_results["sustainability"] = self.test_sustainability_metrics()
        test_results["pareto"] = self.test_pareto_efficiency()
        test_results["nash"] = self.test_nash_equilibrium()
        test_results["aggregation"] = self.test_metric_aggregation()
        
        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        passed = sum(1 for v in test_results.values() if v)
        total = len(test_results)
        
        for test_name, result in test_results.items():
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"{test_name.capitalize():20} {status}")
        
        print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        # Cleanup
        if self.episode_id:
            self.client.send_event("episode:terminate", {"episode_id": self.episode_id})

if __name__ == "__main__":
    tester = GameTheoryMetricsTest()
    tester.run_all_tests()