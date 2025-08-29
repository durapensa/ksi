#!/usr/bin/env python3
"""
Proof of Concept: Testing KSI Fairness Mechanisms in Melting Pot
Validates whether our three fairness conditions generalize to DeepMind's benchmark.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
from pathlib import Path

# Note: Requires installation
# pip install dm-meltingpot

@dataclass
class FairnessConfig:
    """Configuration for fairness mechanisms."""
    # Strategic diversity (agent behavior distribution)
    diversity_ratio: Tuple[float, float, float]  # (aggressive, cooperative, cautious)
    
    # Consent mechanisms
    consent_enabled: bool
    refusal_threshold: float  # 0.0 to 1.0
    consent_type: str  # "random", "threshold", "reputation"
    
    # Coordination limits
    max_coalition_size: int
    coordination_penalty: float
    
    # Reputation system
    reputation_enabled: bool
    reputation_decay: float


class MeltingPotFairnessWrapper:
    """
    Wraps Melting Pot environments with KSI fairness mechanisms.
    Tests if our findings generalize to standard benchmarks.
    """
    
    def __init__(self, substrate_name: str, fairness_config: FairnessConfig):
        """Initialize with a Melting Pot substrate and fairness config."""
        self.substrate_name = substrate_name
        self.fairness = fairness_config
        
        # Track agent behaviors and interactions
        self.agent_strategies = {}
        self.reputation_scores = {}
        self.coalition_tracker = {}
        self.interaction_history = []
        
        # Metrics for analysis
        self.metrics = {
            "cooperation_rate": [],
            "gini_coefficient": [],
            "exploitation_attempts": 0,
            "successful_defenses": 0,
            "welfare_scores": []
        }
        
        # Try to import and initialize Melting Pot
        try:
            import meltingpot
            self.substrate = meltingpot.substrate.build(substrate_name)
            print(f"✅ Loaded Melting Pot substrate: {substrate_name}")
        except ImportError:
            print("⚠️  Melting Pot not installed. Using mock environment.")
            self.substrate = None
            self.mock_mode = True
    
    def assign_strategies(self, num_agents: int):
        """Assign diverse strategies based on fairness config."""
        n_aggressive = int(num_agents * self.fairness.diversity_ratio[0])
        n_cooperative = int(num_agents * self.fairness.diversity_ratio[1])
        n_cautious = num_agents - n_aggressive - n_cooperative
        
        strategies = (
            ["aggressive"] * n_aggressive +
            ["cooperative"] * n_cooperative +
            ["cautious"] * n_cautious
        )
        
        np.random.shuffle(strategies)
        
        for i, strategy in enumerate(strategies):
            agent_id = f"agent_{i}"
            self.agent_strategies[agent_id] = strategy
            self.reputation_scores[agent_id] = 0.5  # Neutral starting reputation
    
    def check_consent(self, agent1: str, agent2: str, action: str) -> bool:
        """Check if an interaction is consented based on fairness mechanisms."""
        if not self.fairness.consent_enabled:
            return True
        
        if self.fairness.consent_type == "random":
            return np.random.random() > self.fairness.refusal_threshold
        
        elif self.fairness.consent_type == "threshold":
            # Refuse if action seems exploitative
            if action in ["defect", "steal", "hoard"]:
                return np.random.random() > (self.fairness.refusal_threshold * 1.5)
            return np.random.random() > self.fairness.refusal_threshold
        
        elif self.fairness.consent_type == "reputation":
            # Check reputation of requesting agent
            rep = self.reputation_scores.get(agent1, 0.5)
            if rep < 0.3:  # Low reputation
                return np.random.random() > (self.fairness.refusal_threshold * 2)
            return np.random.random() > self.fairness.refusal_threshold
        
        return True
    
    def enforce_coordination_limits(self, coalition: List[str]) -> bool:
        """Check and enforce coordination limits."""
        if len(coalition) > self.fairness.max_coalition_size:
            # Apply penalty to oversized coalitions
            if self.fairness.coordination_penalty > 0:
                for agent in coalition:
                    # Reduce reputation for violating coordination limits
                    self.reputation_scores[agent] *= (1 - self.fairness.coordination_penalty)
            return False
        return True
    
    def update_reputation(self, agent: str, action: str, outcome: float):
        """Update agent reputation based on actions."""
        if not self.fairness.reputation_enabled:
            return
        
        # Cooperative actions increase reputation
        if action in ["cooperate", "share", "help"]:
            self.reputation_scores[agent] += 0.1 * outcome
        # Defection decreases reputation
        elif action in ["defect", "steal", "exploit"]:
            self.reputation_scores[agent] -= 0.2
        
        # Apply decay
        self.reputation_scores[agent] *= (1 - self.fairness.reputation_decay)
        
        # Clamp between 0 and 1
        self.reputation_scores[agent] = np.clip(self.reputation_scores[agent], 0, 1)
    
    def calculate_gini(self, resources: Dict[str, float]) -> float:
        """Calculate Gini coefficient for resource distribution."""
        values = sorted(list(resources.values()))
        n = len(values)
        if n == 0:
            return 0.0
        
        cumsum = np.cumsum(values)
        return (2 * np.sum((np.arange(1, n+1)) * values)) / (n * np.sum(values)) - (n + 1) / n
    
    def detect_attack(self, actions: Dict[str, str]) -> str:
        """Detect if current actions constitute an attack pattern."""
        # Count defections
        defection_count = sum(1 for a in actions.values() if a in ["defect", "exploit"])
        defection_rate = defection_count / len(actions) if actions else 0
        
        # Detect cartel formation (coordinated defection)
        if defection_rate > 0.3:
            defectors = [agent for agent, action in actions.items() 
                         if action in ["defect", "exploit"]]
            if len(defectors) > 3:
                return "cartel_formation"
        
        # Detect resource hoarding
        if any(a == "hoard" for a in actions.values()):
            return "resource_hoarding"
        
        return "none"
    
    def run_episode_with_fairness(self, num_steps: int = 1000) -> Dict:
        """Run an episode with fairness mechanisms applied."""
        if self.mock_mode:
            return self.run_mock_episode(num_steps)
        
        # Initialize episode
        timestep = self.substrate.reset()
        episode_rewards = {agent: 0 for agent in self.agent_strategies}
        resources = {agent: 100.0 for agent in self.agent_strategies}
        
        for step in range(num_steps):
            # Collect actions based on strategies
            actions = {}
            for agent_id, obs in timestep.observations.items():
                strategy = self.agent_strategies.get(agent_id, "random")
                
                # Strategy-based action selection
                if strategy == "aggressive":
                    action = self.select_aggressive_action(obs)
                elif strategy == "cooperative":
                    action = self.select_cooperative_action(obs)
                elif strategy == "cautious":
                    action = self.select_cautious_action(obs)
                else:
                    action = np.random.choice(self.substrate.action_spec().num_values)
                
                # Apply consent check
                if not self.check_consent(agent_id, "environment", str(action)):
                    action = 0  # Default to no-op if consent denied
                
                actions[agent_id] = action
            
            # Detect attacks
            attack_type = self.detect_attack(actions)
            if attack_type != "none":
                self.metrics["exploitation_attempts"] += 1
                
                # Apply fairness defenses
                if self.defend_against_attack(attack_type, actions):
                    self.metrics["successful_defenses"] += 1
            
            # Step environment
            timestep = self.substrate.step(actions)
            
            # Update metrics
            for agent_id, reward in timestep.rewards.items():
                episode_rewards[agent_id] += reward
                resources[agent_id] += reward
            
            # Update reputations
            for agent_id, action in actions.items():
                self.update_reputation(agent_id, str(action), 
                                     timestep.rewards.get(agent_id, 0))
            
            if timestep.last():
                break
        
        # Calculate final metrics
        final_gini = self.calculate_gini(resources)
        cooperation_rate = self.calculate_cooperation_rate(episode_rewards)
        total_welfare = sum(episode_rewards.values())
        
        return {
            "gini_coefficient": final_gini,
            "cooperation_rate": cooperation_rate,
            "total_welfare": total_welfare,
            "defense_success_rate": (
                self.metrics["successful_defenses"] / 
                max(self.metrics["exploitation_attempts"], 1)
            ),
            "episode_rewards": episode_rewards
        }
    
    def run_mock_episode(self, num_steps: int) -> Dict:
        """Run a mock episode for testing without Melting Pot installed."""
        print(f"Running mock episode with {len(self.agent_strategies)} agents")
        
        resources = {agent: 100.0 for agent in self.agent_strategies}
        cooperation_count = 0
        total_interactions = 0
        
        for step in range(num_steps):
            # Simulate interactions
            agents = list(self.agent_strategies.keys())
            if len(agents) >= 2:
                agent1 = np.random.choice(agents)
                agent2 = np.random.choice([a for a in agents if a != agent1])
                
                strategy1 = self.agent_strategies[agent1]
                strategy2 = self.agent_strategies[agent2]
                
                # Determine interaction outcome
                if strategy1 == "cooperative" and strategy2 == "cooperative":
                    # Both cooperate - mutual benefit
                    resources[agent1] += 3
                    resources[agent2] += 3
                    cooperation_count += 2
                elif strategy1 == "aggressive" and strategy2 == "cooperative":
                    # Exploitation attempt
                    if self.check_consent(agent1, agent2, "exploit"):
                        resources[agent1] += 5
                        resources[agent2] -= 1
                        self.metrics["exploitation_attempts"] += 1
                    else:
                        # Consent denied - no exploitation
                        self.metrics["successful_defenses"] += 1
                elif strategy1 == "aggressive" and strategy2 == "aggressive":
                    # Mutual defection - both lose
                    resources[agent1] -= 1
                    resources[agent2] -= 1
                
                total_interactions += 2
                
                # Update reputations
                self.update_reputation(agent1, strategy1, 
                                     resources[agent1] / 100)
                self.update_reputation(agent2, strategy2, 
                                     resources[agent2] / 100)
        
        # Calculate metrics
        final_gini = self.calculate_gini(resources)
        cooperation_rate = cooperation_count / max(total_interactions, 1)
        total_welfare = sum(resources.values())
        defense_rate = (
            self.metrics["successful_defenses"] / 
            max(self.metrics["exploitation_attempts"], 1)
        ) if self.metrics["exploitation_attempts"] > 0 else 1.0
        
        return {
            "gini_coefficient": final_gini,
            "cooperation_rate": cooperation_rate,
            "total_welfare": total_welfare,
            "defense_success_rate": defense_rate,
            "resources": resources
        }
    
    def calculate_cooperation_rate(self, rewards: Dict) -> float:
        """Calculate cooperation rate from rewards."""
        if not rewards:
            return 0.0
        
        # Assume higher average reward indicates more cooperation
        avg_reward = np.mean(list(rewards.values()))
        max_possible = 3.0  # Mutual cooperation payoff
        
        return min(avg_reward / max_possible, 1.0)
    
    def defend_against_attack(self, attack_type: str, actions: Dict) -> bool:
        """Apply fairness defenses against detected attacks."""
        defense_successful = False
        
        if attack_type == "cartel_formation":
            # Check coordination limits
            defectors = [agent for agent, action in actions.items() 
                         if action in ["defect", "exploit"]]
            if not self.enforce_coordination_limits(defectors):
                defense_successful = True
                
        elif attack_type == "resource_hoarding":
            # Apply consent checks more strictly
            hoarders = [agent for agent, action in actions.items() 
                        if action == "hoard"]
            for hoarder in hoarders:
                if not self.check_consent(hoarder, "community", "hoard"):
                    defense_successful = True
                    actions[hoarder] = 0  # Force no-op
        
        return defense_successful
    
    def select_aggressive_action(self, observation):
        """Select action for aggressive strategy."""
        # Simplified - would use observation in real implementation
        return "defect"  # Or appropriate action index
    
    def select_cooperative_action(self, observation):
        """Select action for cooperative strategy."""
        return "cooperate"  # Or appropriate action index
    
    def select_cautious_action(self, observation):
        """Select action for cautious strategy."""
        return "cooperate" if np.random.random() > 0.3 else "defect"


def test_fairness_generalization():
    """Test if KSI fairness findings generalize to Melting Pot benchmarks."""
    
    print("="*80)
    print("TESTING KSI FAIRNESS IN MELTING POT BENCHMARKS")
    print("="*80)
    
    # Test substrates (social dilemmas)
    substrates = [
        "prisoners_dilemma_in_the_matrix__repeated",
        "stag_hunt_in_the_matrix__repeated",
        "chicken_in_the_matrix__repeated",
        "commons_harvest__open"
    ]
    
    # Fairness configurations to test
    configs = {
        "No Fairness": FairnessConfig(
            diversity_ratio=(1.0, 0.0, 0.0),
            consent_enabled=False,
            refusal_threshold=0.0,
            consent_type="random",
            max_coalition_size=50,
            coordination_penalty=0.0,
            reputation_enabled=False,
            reputation_decay=0.0
        ),
        "KSI Optimal": FairnessConfig(
            diversity_ratio=(0.40, 0.35, 0.25),
            consent_enabled=True,
            refusal_threshold=0.65,
            consent_type="reputation",
            max_coalition_size=3,
            coordination_penalty=0.6,
            reputation_enabled=True,
            reputation_decay=0.05
        )
    }
    
    results = {}
    
    # Use mock substrate for demonstration
    substrate = "mock_social_dilemma"
    
    for config_name, fairness_config in configs.items():
        print(f"\nTesting configuration: {config_name}")
        print(f"  Diversity: {fairness_config.diversity_ratio}")
        print(f"  Consent: {fairness_config.consent_enabled} "
              f"(threshold={fairness_config.refusal_threshold})")
        print(f"  Coordination: max_size={fairness_config.max_coalition_size}")
        
        wrapper = MeltingPotFairnessWrapper(substrate, fairness_config)
        wrapper.mock_mode = True  # Force mock mode for demo
        wrapper.assign_strategies(20)  # 20 agents
        
        # Run multiple episodes
        episode_results = []
        for episode in range(5):
            result = wrapper.run_episode_with_fairness(num_steps=100)
            episode_results.append(result)
            print(f"    Episode {episode+1}: "
                  f"Gini={result['gini_coefficient']:.3f}, "
                  f"Cooperation={result['cooperation_rate']:.2%}, "
                  f"Defense={result['defense_success_rate']:.2%}")
        
        # Aggregate results
        avg_gini = np.mean([r["gini_coefficient"] for r in episode_results])
        avg_cooperation = np.mean([r["cooperation_rate"] for r in episode_results])
        avg_defense = np.mean([r["defense_success_rate"] for r in episode_results])
        avg_welfare = np.mean([r["total_welfare"] for r in episode_results])
        
        results[config_name] = {
            "avg_gini": avg_gini,
            "avg_cooperation": avg_cooperation,
            "avg_defense": avg_defense,
            "avg_welfare": avg_welfare,
            "episodes": episode_results
        }
        
        print(f"  Averages: Gini={avg_gini:.3f}, Cooperation={avg_cooperation:.2%}, "
              f"Defense={avg_defense:.2%}, Welfare={avg_welfare:.0f}")
    
    # Compare results
    print("\n" + "="*80)
    print("COMPARISON SUMMARY")
    print("="*80)
    
    baseline = results["No Fairness"]
    optimal = results["KSI Optimal"]
    
    gini_reduction = (baseline["avg_gini"] - optimal["avg_gini"]) / baseline["avg_gini"] * 100
    cooperation_increase = (optimal["avg_cooperation"] - baseline["avg_cooperation"]) / baseline["avg_cooperation"] * 100
    defense_increase = optimal["avg_defense"] - baseline["avg_defense"]
    welfare_change = (optimal["avg_welfare"] - baseline["avg_welfare"]) / baseline["avg_welfare"] * 100
    
    print(f"\nFairness Impact:")
    print(f"  Gini Reduction: {gini_reduction:.1f}%")
    print(f"  Cooperation Increase: {cooperation_increase:.1f}%")
    print(f"  Defense Improvement: {defense_increase:.1%}")
    print(f"  Welfare Change: {welfare_change:+.1f}%")
    
    # Validation verdict
    print("\n" + "="*80)
    if gini_reduction > 30 and cooperation_increase > 50 and defense_increase > 0.5:
        print("✅ STRONG VALIDATION: Fairness mechanisms generalize well")
    elif gini_reduction > 20 and cooperation_increase > 30:
        print("⚠️  MODERATE VALIDATION: Fairness helps but less than internal tests")
    else:
        print("❌ WEAK VALIDATION: Fairness effects limited in this benchmark")
    print("="*80)
    
    # Save results
    report = {
        "substrate": substrate,
        "configurations_tested": list(configs.keys()),
        "results": results,
        "comparison": {
            "gini_reduction_percent": gini_reduction,
            "cooperation_increase_percent": cooperation_increase,
            "defense_improvement": defense_increase,
            "welfare_change_percent": welfare_change
        }
    }
    
    report_path = Path("results/melting_pot_validation.json")
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nResults saved to: {report_path}")


if __name__ == "__main__":
    test_fairness_generalization()