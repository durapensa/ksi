#!/usr/bin/env python3
"""
Fairness Metrics Analysis
==========================

Comprehensive analysis of fairness metrics across different scenarios.
Tests the complete game theory metrics pipeline.
"""

import time
import random
from typing import Dict, List, Any
from collections import defaultdict
from dataclasses import dataclass, field

from ksi_common.sync_client import MinimalSyncClient


@dataclass
class MetricsSnapshot:
    """A snapshot of metrics at a point in time."""
    timestamp: float
    episode_id: str
    scenario: str
    metrics: Dict[str, Any]
    resource_distribution: Dict[str, float] = field(default_factory=dict)
    interaction_counts: Dict[str, int] = field(default_factory=dict)


class FairnessMetricsAnalyzer:
    """Analyze fairness metrics across different scenarios."""
    
    def __init__(self):
        self.client = MinimalSyncClient()
        self.snapshots: List[MetricsSnapshot] = []
        self.current_episode: Optional[str] = None
        
    def create_test_scenario(self, scenario_type: str, num_agents: int = 5) -> str:
        """Create a test scenario with agents and resources."""
        print(f"\n=== Creating {scenario_type} Scenario ===")
        
        # Create episode
        result = self.client.send_event("episode:create", {
            "scenario_type": scenario_type,
            "config": {
                "num_agents": num_agents,
                "test_mode": True
            }
        })
        self.current_episode = result.get("episode_id", f"{scenario_type}_test")
        
        # Create agents with varying wealth
        wealth_levels = [1000, 800, 500, 200, 50]  # Unequal distribution
        
        for i in range(num_agents):
            agent_id = f"agent_{i+1}"
            wealth = wealth_levels[i] if i < len(wealth_levels) else 100
            
            # Update ownership in validator
            self.client.send_event("validator:resource:update_ownership", {
                "entity": agent_id,
                "resource_type": "gold",
                "amount": float(wealth),
                "episode_id": self.current_episode
            })
            
            # Also track in metrics
            self.client.send_event("metrics:update_resources", {
                "episode_id": self.current_episode,
                "entity": agent_id,
                "resource_type": "gold",
                "amount": float(wealth)
            })
            
            print(f"  Created {agent_id} with {wealth} gold")
        
        return self.current_episode
    
    def simulate_interactions(self, num_interactions: int = 20):
        """Simulate various interactions between agents."""
        print(f"\n=== Simulating {num_interactions} Interactions ===")
        
        interaction_types = ["cooperate", "defect", "trade", "harvest", "help"]
        agents = [f"agent_{i+1}" for i in range(5)]
        
        cooperation_count = 0
        defection_count = 0
        
        for i in range(num_interactions):
            actor = random.choice(agents)
            target = random.choice([a for a in agents if a != actor])
            interaction_type = random.choice(interaction_types)
            
            # Log interaction
            self.client.send_event("metrics:log_interaction", {
                "episode_id": self.current_episode,
                "actor": actor,
                "target": target,
                "interaction_type": interaction_type,
                "outcome": "success"
            })
            
            if interaction_type == "cooperate":
                cooperation_count += 1
            elif interaction_type == "defect":
                defection_count += 1
        
        print(f"  Cooperations: {cooperation_count}")
        print(f"  Defections: {defection_count}")
        print(f"  Other interactions: {num_interactions - cooperation_count - defection_count}")
    
    def simulate_resource_transfers(self, num_transfers: int = 10):
        """Simulate resource transfers to create inequality."""
        print(f"\n=== Simulating {num_transfers} Resource Transfers ===")
        
        agents = [f"agent_{i+1}" for i in range(5)]
        
        for i in range(num_transfers):
            from_agent = random.choice(agents)
            to_agent = random.choice([a for a in agents if a != from_agent])
            amount = random.uniform(10, 100)
            
            # Validate transfer
            result = self.client.send_event("validator:resource:validate", {
                "from_entity": from_agent,
                "to_entity": to_agent,
                "resource_type": "gold",
                "amount": amount,
                "transfer_type": "trade",
                "metadata": {
                    "episode_id": self.current_episode
                }
            })
            
            if result.get("valid"):
                # Execute transfer
                self.client.send_event("validator:resource:update_ownership", {
                    "entity": from_agent,
                    "resource_type": "gold",
                    "amount": -amount,  # Subtract
                    "episode_id": self.current_episode
                })
                
                self.client.send_event("validator:resource:update_ownership", {
                    "entity": to_agent,
                    "resource_type": "gold",
                    "amount": amount,  # Add
                    "episode_id": self.current_episode
                })
                
                print(f"  ✓ {from_agent} → {to_agent}: {amount:.1f} gold")
            else:
                reason = result.get("reason", "Unknown")
                if "fairness" in reason.lower():
                    print(f"  ✗ {from_agent} → {to_agent}: BLOCKED (fairness violation)")
                else:
                    print(f"  ✗ {from_agent} → {to_agent}: BLOCKED ({reason})")
    
    def calculate_all_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive metrics for current episode."""
        print("\n=== Calculating All Metrics ===")
        
        # Request all available metrics
        all_metrics = [
            # Economic metrics
            "gini_coefficient",
            "wealth_concentration",
            "monopoly_risk",
            
            # Social metrics
            "cooperation_rate",
            "defection_rate",
            "trust_level",
            
            # Game theory metrics
            "nash_equilibrium_distance",
            "pareto_efficiency",
            "social_welfare",
            
            # Fairness metrics
            "fairness_violations",
            "exploitation_index",
            
            # Sustainability metrics
            "sustainability_index",
            "resource_depletion_rate",
            
            # Distribution metrics
            "collective_return",
            "utility_distribution"
        ]
        
        result = self.client.send_event("metrics:calculate", {
            "episode_id": self.current_episode,
            "metrics": all_metrics
        })
        
        metrics = result.get("metrics", {})
        
        # Display calculated metrics
        print("\nCalculated Metrics:")
        for metric, value in metrics.items():
            if value is not None:
                print(f"  {metric:30} = {value}")
        
        return metrics
    
    def get_resource_distribution(self) -> Dict[str, float]:
        """Get current resource distribution across agents."""
        distribution = {}
        
        for i in range(5):
            agent_id = f"agent_{i+1}"
            result = self.client.send_event("validator:resource:get_wealth", {
                "entity": agent_id
            })
            
            wealth = result.get("total_wealth", 0)
            distribution[agent_id] = wealth
        
        return distribution
    
    def analyze_inequality_evolution(self):
        """Analyze how inequality evolves over interactions."""
        print("\n" + "="*80)
        print("INEQUALITY EVOLUTION ANALYSIS")
        print("="*80)
        
        # Initial state
        print("\n1. Initial Distribution")
        self.create_test_scenario("inequality_test")
        initial_metrics = self.calculate_all_metrics()
        initial_distribution = self.get_resource_distribution()
        
        snapshot = MetricsSnapshot(
            timestamp=time.time(),
            episode_id=self.current_episode,
            scenario="initial",
            metrics=initial_metrics,
            resource_distribution=initial_distribution
        )
        self.snapshots.append(snapshot)
        
        # After interactions
        print("\n2. After Social Interactions")
        self.simulate_interactions(30)
        interaction_metrics = self.calculate_all_metrics()
        
        snapshot = MetricsSnapshot(
            timestamp=time.time(),
            episode_id=self.current_episode,
            scenario="post_interactions",
            metrics=interaction_metrics
        )
        self.snapshots.append(snapshot)
        
        # After transfers
        print("\n3. After Resource Transfers")
        self.simulate_resource_transfers(15)
        transfer_metrics = self.calculate_all_metrics()
        final_distribution = self.get_resource_distribution()
        
        snapshot = MetricsSnapshot(
            timestamp=time.time(),
            episode_id=self.current_episode,
            scenario="post_transfers",
            metrics=transfer_metrics,
            resource_distribution=final_distribution
        )
        self.snapshots.append(snapshot)
        
        # Analyze changes
        self.analyze_metric_changes()
    
    def analyze_metric_changes(self):
        """Analyze how metrics changed over time."""
        print("\n" + "="*80)
        print("METRIC EVOLUTION SUMMARY")
        print("="*80)
        
        if len(self.snapshots) < 2:
            print("Not enough snapshots for comparison")
            return
        
        initial = self.snapshots[0]
        final = self.snapshots[-1]
        
        print("\nKey Metric Changes:")
        
        # Gini coefficient
        initial_gini = initial.metrics.get("gini_coefficient", 0)
        final_gini = final.metrics.get("gini_coefficient", 0)
        gini_change = final_gini - initial_gini
        print(f"  Gini Coefficient: {initial_gini:.3f} → {final_gini:.3f} ({gini_change:+.3f})")
        
        # Cooperation rate
        initial_coop = initial.metrics.get("cooperation_rate", 0)
        final_coop = final.metrics.get("cooperation_rate", 0)
        coop_change = final_coop - initial_coop
        print(f"  Cooperation Rate: {initial_coop:.3f} → {final_coop:.3f} ({coop_change:+.3f})")
        
        # Fairness violations
        initial_fair = initial.metrics.get("fairness_violations", 0)
        final_fair = final.metrics.get("fairness_violations", 0)
        fair_change = final_fair - initial_fair
        print(f"  Fairness Violations: {initial_fair} → {final_fair} ({fair_change:+d})")
        
        # Resource distribution
        if initial.resource_distribution and final.resource_distribution:
            print("\nWealth Distribution Changes:")
            for agent_id in initial.resource_distribution:
                initial_wealth = initial.resource_distribution.get(agent_id, 0)
                final_wealth = final.resource_distribution.get(agent_id, 0)
                change = final_wealth - initial_wealth
                print(f"  {agent_id}: {initial_wealth:.1f} → {final_wealth:.1f} ({change:+.1f})")
    
    def test_fairness_enforcement(self):
        """Test how fairness rules prevent exploitation."""
        print("\n" + "="*80)
        print("FAIRNESS ENFORCEMENT TEST")
        print("="*80)
        
        self.create_test_scenario("fairness_test")
        
        print("\n=== Testing Exploitation Prevention ===")
        
        # Try to make unfair transfers
        test_cases = [
            {
                "from": "agent_5",  # Poorest
                "to": "agent_1",    # Richest
                "amount": 25,
                "description": "Poor → Rich transfer"
            },
            {
                "from": "agent_1",  # Richest
                "to": "agent_5",    # Poorest
                "amount": 100,
                "description": "Rich → Poor transfer"
            },
            {
                "from": "agent_1",  # Richest
                "to": "agent_2",    # Second richest
                "amount": 500,
                "description": "Large wealth concentration"
            },
            {
                "from": "agent_3",  # Middle
                "to": "agent_4",    # Second poorest
                "amount": 50,
                "description": "Middle → Lower transfer"
            }
        ]
        
        for test in test_cases:
            result = self.client.send_event("validator:resource:validate", {
                "from_entity": test["from"],
                "to_entity": test["to"],
                "resource_type": "gold",
                "amount": test["amount"],
                "transfer_type": "trade",
                "metadata": {
                    "episode_id": self.current_episode
                }
            })
            
            valid = result.get("valid", False)
            fairness = result.get("fairness", {})
            
            print(f"\n{test['description']}:")
            print(f"  Amount: {test['amount']} gold")
            print(f"  Valid: {'✓' if valid else '✗'}")
            
            if fairness:
                print(f"  Fair: {'✓' if fairness.get('fair') else '✗'}")
                print(f"  Gini Impact: {fairness.get('gini_impact', 0):.3f}")
                print(f"  Monopoly Risk: {fairness.get('monopoly_risk', 0):.3f}")
                print(f"  Exploitation Risk: {fairness.get('exploitation_risk', 0):.3f}")
                
                warnings = fairness.get('warnings', [])
                if warnings:
                    print(f"  Warnings: {', '.join(warnings)}")
    
    def run_comprehensive_analysis(self):
        """Run comprehensive fairness metrics analysis."""
        print("\n" + "="*80)
        print("COMPREHENSIVE FAIRNESS METRICS ANALYSIS")
        print("="*80)
        
        # Test 1: Inequality evolution
        self.analyze_inequality_evolution()
        
        # Test 2: Fairness enforcement
        self.test_fairness_enforcement()
        
        # Summary
        print("\n" + "="*80)
        print("ANALYSIS COMPLETE")
        print("="*80)
        
        print(f"\nTotal snapshots collected: {len(self.snapshots)}")
        
        # Find most interesting metrics
        all_metrics = defaultdict(list)
        for snapshot in self.snapshots:
            for metric, value in snapshot.metrics.items():
                if value is not None:
                    all_metrics[metric].append(value)
        
        print("\nMetric Coverage:")
        for metric, values in all_metrics.items():
            if values:
                # Skip dict values like utility_distribution
                if isinstance(values[0], (int, float)):
                    avg = sum(values) / len(values)
                    print(f"  {metric:30} samples: {len(values)}, avg: {avg:.3f}")
                else:
                    print(f"  {metric:30} samples: {len(values)}, type: {type(values[0]).__name__}")


if __name__ == "__main__":
    analyzer = FairnessMetricsAnalyzer()
    analyzer.run_comprehensive_analysis()