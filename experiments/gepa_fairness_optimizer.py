#!/usr/bin/env python3
"""
GEPA (Genetic-Evolutionary Pareto Adapter) for Fairness Optimization
Evolves ecosystem configurations that maintain fairness while optimizing multiple objectives.
"""

import random
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field
import json
from pathlib import Path
import time
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from ksi_common.sync_client import MinimalSyncClient


@dataclass
class EcosystemConfiguration:
    """Represents a configuration for multi-agent ecosystem."""
    
    # Strategy distribution (must sum to 1.0)
    aggressive_ratio: float
    cooperative_ratio: float
    cautious_ratio: float
    
    # Consent mechanism parameters
    refusal_threshold: float  # 0.0 (never refuse) to 1.0 (always refuse)
    consent_type: str  # "random", "threshold", "reputation"
    
    # Coordination limits
    max_coalition_size: int  # 1 = no coordination, N = full coordination
    coordination_penalty: float  # Penalty for forming coalitions
    
    # Evolution metadata
    generation: int = 0
    fitness: Dict[str, float] = field(default_factory=dict)
    pareto_rank: int = 0
    
    def __post_init__(self):
        """Normalize strategy ratios."""
        total = self.aggressive_ratio + self.cooperative_ratio + self.cautious_ratio
        if total > 0:
            self.aggressive_ratio /= total
            self.cooperative_ratio /= total
            self.cautious_ratio /= total
    
    def mutate(self, mutation_rate: float = 0.1) -> 'EcosystemConfiguration':
        """Create mutated version of configuration."""
        new_config = EcosystemConfiguration(
            aggressive_ratio=max(0, self.aggressive_ratio + random.gauss(0, mutation_rate)),
            cooperative_ratio=max(0, self.cooperative_ratio + random.gauss(0, mutation_rate)),
            cautious_ratio=max(0, self.cautious_ratio + random.gauss(0, mutation_rate)),
            refusal_threshold=np.clip(self.refusal_threshold + random.gauss(0, mutation_rate), 0, 1),
            consent_type=random.choice(["random", "threshold", "reputation"]) if random.random() < mutation_rate else self.consent_type,
            max_coalition_size=max(1, int(self.max_coalition_size + random.gauss(0, mutation_rate * 10))),
            coordination_penalty=max(0, self.coordination_penalty + random.gauss(0, mutation_rate)),
            generation=self.generation + 1
        )
        return new_config
    
    def crossover(self, other: 'EcosystemConfiguration') -> Tuple['EcosystemConfiguration', 'EcosystemConfiguration']:
        """Perform crossover with another configuration."""
        # Single-point crossover
        if random.random() < 0.5:
            child1 = EcosystemConfiguration(
                aggressive_ratio=self.aggressive_ratio,
                cooperative_ratio=self.cooperative_ratio,
                cautious_ratio=self.cautious_ratio,
                refusal_threshold=other.refusal_threshold,
                consent_type=other.consent_type,
                max_coalition_size=other.max_coalition_size,
                coordination_penalty=other.coordination_penalty,
                generation=max(self.generation, other.generation) + 1
            )
            child2 = EcosystemConfiguration(
                aggressive_ratio=other.aggressive_ratio,
                cooperative_ratio=other.cooperative_ratio,
                cautious_ratio=other.cautious_ratio,
                refusal_threshold=self.refusal_threshold,
                consent_type=self.consent_type,
                max_coalition_size=self.max_coalition_size,
                coordination_penalty=self.coordination_penalty,
                generation=max(self.generation, other.generation) + 1
            )
        else:
            # Uniform crossover
            child1 = EcosystemConfiguration(
                aggressive_ratio=(self.aggressive_ratio + other.aggressive_ratio) / 2,
                cooperative_ratio=(self.cooperative_ratio + other.cooperative_ratio) / 2,
                cautious_ratio=(self.cautious_ratio + other.cautious_ratio) / 2,
                refusal_threshold=(self.refusal_threshold + other.refusal_threshold) / 2,
                consent_type=random.choice([self.consent_type, other.consent_type]),
                max_coalition_size=(self.max_coalition_size + other.max_coalition_size) // 2,
                coordination_penalty=(self.coordination_penalty + other.coordination_penalty) / 2,
                generation=max(self.generation, other.generation) + 1
            )
            child2 = child1.mutate(0.05)  # Slight variation
        
        return child1, child2


class GEPAFairnessOptimizer:
    """Genetic-Evolutionary Pareto Adapter for fairness optimization."""
    
    def __init__(self, 
                 socket_path: str = "/Users/dp/projects/ksi/var/run/daemon.sock",
                 population_size: int = 20,
                 num_agents: int = 50,
                 num_rounds: int = 20):
        """Initialize GEPA optimizer."""
        self.client = MinimalSyncClient(socket_path=socket_path)
        self.population_size = population_size
        self.num_agents = num_agents
        self.num_rounds = num_rounds
        self.population: List[EcosystemConfiguration] = []
        self.pareto_front: List[EcosystemConfiguration] = []
        self.generation = 0
        self.history = []
    
    def initialize_population(self):
        """Create initial diverse population."""
        self.population = []
        
        # Add known good configurations
        self.population.append(EcosystemConfiguration(
            aggressive_ratio=0.40, cooperative_ratio=0.35, cautious_ratio=0.25,
            refusal_threshold=0.5, consent_type="threshold",
            max_coalition_size=1, coordination_penalty=0.5
        ))
        
        # Add extreme configurations to explore space
        self.population.append(EcosystemConfiguration(
            aggressive_ratio=1.0, cooperative_ratio=0.0, cautious_ratio=0.0,
            refusal_threshold=0.0, consent_type="random",
            max_coalition_size=10, coordination_penalty=0.0
        ))
        
        self.population.append(EcosystemConfiguration(
            aggressive_ratio=0.0, cooperative_ratio=1.0, cautious_ratio=0.0,
            refusal_threshold=1.0, consent_type="reputation",
            max_coalition_size=1, coordination_penalty=1.0
        ))
        
        # Fill rest with random configurations
        while len(self.population) < self.population_size:
            self.population.append(EcosystemConfiguration(
                aggressive_ratio=random.random(),
                cooperative_ratio=random.random(),
                cautious_ratio=random.random(),
                refusal_threshold=random.random(),
                consent_type=random.choice(["random", "threshold", "reputation"]),
                max_coalition_size=random.randint(1, 10),
                coordination_penalty=random.random()
            ))
        
        print(f"✅ Initialized population with {len(self.population)} configurations")
    
    def evaluate_configuration(self, config: EcosystemConfiguration) -> Dict[str, float]:
        """Evaluate a configuration by running simulation."""
        print(f"   Evaluating config: {config.aggressive_ratio:.2f}A/{config.cooperative_ratio:.2f}C/{config.cautious_ratio:.2f}Ca")
        
        # Create agents with configuration
        agents = []
        resources = {}
        
        # Determine agent counts
        n_aggressive = int(self.num_agents * config.aggressive_ratio)
        n_cooperative = int(self.num_agents * config.cooperative_ratio)
        n_cautious = self.num_agents - n_aggressive - n_cooperative
        
        # Create agents
        for i in range(self.num_agents):
            agent_id = f"gepa_agent_{i:03d}"
            resource_id = f"gepa_resource_{i:03d}"
            
            if i < n_aggressive:
                strategy = "aggressive"
            elif i < n_aggressive + n_cooperative:
                strategy = "cooperative"
            else:
                strategy = "cautious"
            
            initial_amount = 1000 + random.randint(-200, 200)
            
            self.client.send_event("state:entity:create", {
                "type": "gepa_agent",
                "id": agent_id,
                "properties": {
                    "strategy": strategy,
                    "refusal_threshold": config.refusal_threshold,
                    "consent_type": config.consent_type
                }
            })
            
            self.client.send_event("state:entity:create", {
                "type": "resource",
                "id": resource_id,
                "properties": {"owner": agent_id, "amount": initial_amount}
            })
            
            agents.append(agent_id)
            resources[agent_id] = resource_id
        
        # Get initial metrics
        initial_values = [self.get_resource_amount(resources[a]) for a in agents]
        initial_gini = self.calculate_gini(initial_values)
        initial_total = sum(initial_values)
        
        # Run simulation
        total_trades = 0
        total_refused = 0
        
        for round_num in range(self.num_rounds):
            trades, refused = self.simulate_round(agents, resources, config)
            total_trades += trades
            total_refused += refused
        
        # Get final metrics
        final_values = [self.get_resource_amount(resources[a]) for a in agents]
        final_gini = self.calculate_gini(final_values)
        final_total = sum(final_values)
        
        # Calculate fitness metrics (multi-objective)
        fitness = {
            "fairness": 1.0 - final_gini,  # Higher is better (minimize Gini)
            "efficiency": total_trades / (self.num_rounds * self.num_agents / 2),  # Trade volume
            "stability": 1.0 - abs(final_gini - initial_gini),  # Minimize change
            "conservation": 1.0 - abs(final_total - initial_total) / initial_total,  # Resource conservation
            "diversity": self.calculate_strategy_diversity(config),  # Strategic diversity
            "exploitation_resistance": self.test_exploitation_resistance(agents, resources, config)
        }
        
        # Cleanup
        for agent_id in agents:
            self.client.send_event("state:entity:delete", {"type": "gepa_agent", "id": agent_id})
            self.client.send_event("state:entity:delete", {"type": "resource", "id": resources[agent_id]})
        
        return fitness
    
    def simulate_round(self, agents: List[str], resources: Dict[str, str], 
                       config: EcosystemConfiguration) -> Tuple[int, int]:
        """Simulate one trading round with configuration."""
        trades = 0
        refused = 0
        
        # Shuffle and pair agents
        shuffled = agents.copy()
        random.shuffle(shuffled)
        
        for i in range(0, min(len(shuffled)-1, 20), 2):
            agent_a = shuffled[i]
            agent_b = shuffled[i+1]
            
            balance_a = self.get_resource_amount(resources[agent_a])
            balance_b = self.get_resource_amount(resources[agent_b])
            
            if balance_a < 10 or balance_b < 10:
                continue
            
            # Apply consent mechanism
            if config.consent_type == "random":
                if random.random() > config.refusal_threshold:
                    refused += 1
                    continue
            elif config.consent_type == "threshold":
                wealth_ratio = max(balance_a, balance_b) / min(balance_a, balance_b)
                if wealth_ratio > 2.0 and random.random() < config.refusal_threshold:
                    refused += 1
                    continue
            
            # Determine trade amount
            amount = int(min(balance_a, balance_b) * 0.15)
            if amount < 5:
                continue
            
            # Execute trade
            if random.random() < 0.5:
                from_agent, to_agent = agent_a, agent_b
            else:
                from_agent, to_agent = agent_b, agent_a
            
            result = self.client.send_event("resource:transfer", {
                "from_resource": resources[from_agent],
                "to_resource": resources[to_agent],
                "amount": amount
            })
            
            if result.get("status") == "success":
                trades += 1
        
        return trades, refused
    
    def calculate_gini(self, values: List[float]) -> float:
        """Calculate Gini coefficient."""
        result = self.client.send_event("metrics:fairness:calculate", {
            "metric_type": "gini",
            "data": {"values": values}
        })
        
        if result and "result" in result:
            return result["result"].get("gini", 0.0)
        return 0.0
    
    def calculate_strategy_diversity(self, config: EcosystemConfiguration) -> float:
        """Calculate Shannon entropy of strategy distribution."""
        ratios = [config.aggressive_ratio, config.cooperative_ratio, config.cautious_ratio]
        ratios = [r for r in ratios if r > 0]
        
        if not ratios:
            return 0.0
        
        entropy = -sum(r * np.log(r) for r in ratios if r > 0)
        max_entropy = np.log(3)  # Maximum entropy with 3 strategies
        
        return entropy / max_entropy if max_entropy > 0 else 0
    
    def test_exploitation_resistance(self, agents: List[str], resources: Dict[str, str],
                                    config: EcosystemConfiguration) -> float:
        """Test resistance to exploitation attempts."""
        # Inject exploiter
        exploiter_id = "exploiter"
        exploiter_resource = "exploiter_resource"
        
        self.client.send_event("state:entity:create", {
            "type": "gepa_agent",
            "id": exploiter_id,
            "properties": {"strategy": "exploiter"}
        })
        
        self.client.send_event("state:entity:create", {
            "type": "resource",
            "id": exploiter_resource,
            "properties": {"owner": exploiter_id, "amount": 1000}
        })
        
        # Try to exploit
        initial_exploiter = 1000
        victims = random.sample(agents, min(5, len(agents)))
        
        for victim in victims:
            victim_balance = self.get_resource_amount(resources[victim])
            if victim_balance > 50:
                # Attempt extraction
                amount = int(victim_balance * 0.3)
                result = self.client.send_event("resource:transfer", {
                    "from_resource": resources[victim],
                    "to_resource": exploiter_resource,
                    "amount": amount
                })
        
        final_exploiter = self.get_resource_amount(exploiter_resource)
        
        # Cleanup
        self.client.send_event("state:entity:delete", {"type": "gepa_agent", "id": exploiter_id})
        self.client.send_event("state:entity:delete", {"type": "resource", "id": exploiter_resource})
        
        # Return resistance score (lower gain = better resistance)
        gain = (final_exploiter - initial_exploiter) / initial_exploiter
        resistance = 1.0 / (1.0 + gain)  # Convert to 0-1 where 1 is perfect resistance
        
        return resistance
    
    def get_resource_amount(self, resource_id: str) -> int:
        """Get current resource amount."""
        result = self.client.send_event("state:entity:get", {
            "type": "resource",
            "id": resource_id
        })
        
        if result and result.get("status") == "success":
            return result.get("properties", {}).get("amount", 0)
        return 0
    
    def calculate_pareto_ranks(self):
        """Calculate Pareto ranks for population."""
        # Reset ranks
        for config in self.population:
            config.pareto_rank = 0
        
        remaining = self.population.copy()
        rank = 0
        
        while remaining:
            # Find non-dominated solutions
            non_dominated = []
            for i, config_i in enumerate(remaining):
                dominated = False
                for j, config_j in enumerate(remaining):
                    if i != j and self.dominates(config_j, config_i):
                        dominated = True
                        break
                if not dominated:
                    non_dominated.append(config_i)
            
            # Assign rank
            for config in non_dominated:
                config.pareto_rank = rank
                remaining.remove(config)
            
            rank += 1
            
            if rank > 10:  # Safety check
                break
    
    def dominates(self, a: EcosystemConfiguration, b: EcosystemConfiguration) -> bool:
        """Check if configuration a dominates b (a is better in all objectives)."""
        if not a.fitness or not b.fitness:
            return False
        
        better_in_at_least_one = False
        for key in a.fitness:
            if key not in b.fitness:
                continue
            if a.fitness[key] < b.fitness[key]:
                return False  # a is worse in this objective
            if a.fitness[key] > b.fitness[key]:
                better_in_at_least_one = True
        
        return better_in_at_least_one
    
    def tournament_selection(self, tournament_size: int = 3) -> EcosystemConfiguration:
        """Select configuration using tournament selection."""
        tournament = random.sample(self.population, min(tournament_size, len(self.population)))
        # Prefer lower Pareto rank (closer to front)
        tournament.sort(key=lambda x: x.pareto_rank)
        return tournament[0]
    
    def evolve_generation(self):
        """Evolve one generation."""
        self.generation += 1
        print(f"\n🧬 Generation {self.generation}")
        
        # Evaluate fitness for all configurations
        for i, config in enumerate(self.population):
            print(f"  Evaluating {i+1}/{len(self.population)}...")
            config.fitness = self.evaluate_configuration(config)
        
        # Calculate Pareto ranks
        self.calculate_pareto_ranks()
        
        # Update Pareto front
        self.pareto_front = [c for c in self.population if c.pareto_rank == 0]
        print(f"  📊 Pareto front size: {len(self.pareto_front)}")
        
        # Create next generation
        new_population = []
        
        # Elitism: Keep best solutions
        elite_size = self.population_size // 4
        elite = sorted(self.population, key=lambda x: x.pareto_rank)[:elite_size]
        new_population.extend(elite)
        
        # Generate offspring
        while len(new_population) < self.population_size:
            # Selection
            parent1 = self.tournament_selection()
            parent2 = self.tournament_selection()
            
            # Crossover
            if random.random() < 0.7:  # Crossover probability
                child1, child2 = parent1.crossover(parent2)
            else:
                child1, child2 = parent1, parent2
            
            # Mutation
            if random.random() < 0.3:  # Mutation probability
                child1 = child1.mutate(0.1)
            if random.random() < 0.3:
                child2 = child2.mutate(0.1)
            
            new_population.extend([child1, child2])
        
        # Trim to population size
        self.population = new_population[:self.population_size]
        
        # Record history
        best = min(self.pareto_front, key=lambda x: 1 - x.fitness.get("fairness", 0))
        self.history.append({
            "generation": self.generation,
            "best_fairness": best.fitness.get("fairness", 0),
            "pareto_size": len(self.pareto_front),
            "best_config": {
                "aggressive": best.aggressive_ratio,
                "cooperative": best.cooperative_ratio,
                "cautious": best.cautious_ratio
            }
        })
        
        print(f"  ✨ Best fairness: {best.fitness.get('fairness', 0):.3f}")
    
    def run_optimization(self, num_generations: int = 10):
        """Run GEPA optimization."""
        print("\n" + "="*60)
        print("🧬 GEPA FAIRNESS OPTIMIZATION")
        print("="*60)
        
        # Initialize
        self.initialize_population()
        
        # Evolution loop
        for gen in range(num_generations):
            self.evolve_generation()
            
            # Report progress
            if self.pareto_front:
                best = min(self.pareto_front, key=lambda x: 1 - x.fitness.get("fairness", 0))
                print(f"\n📈 Generation {gen+1} Summary:")
                print(f"   Fairness: {best.fitness.get('fairness', 0):.3f}")
                print(f"   Efficiency: {best.fitness.get('efficiency', 0):.3f}")
                print(f"   Diversity: {best.fitness.get('diversity', 0):.3f}")
                print(f"   Config: {best.aggressive_ratio:.2f}A/{best.cooperative_ratio:.2f}C/{best.cautious_ratio:.2f}Ca")
        
        return self.pareto_front
    
    def save_results(self, filename: str = "gepa_results.json"):
        """Save optimization results."""
        results = {
            "timestamp": datetime.now().isoformat(),
            "generations": self.generation,
            "population_size": self.population_size,
            "num_agents": self.num_agents,
            "history": self.history,
            "pareto_front": [
                {
                    "config": {
                        "aggressive_ratio": c.aggressive_ratio,
                        "cooperative_ratio": c.cooperative_ratio,
                        "cautious_ratio": c.cautious_ratio,
                        "refusal_threshold": c.refusal_threshold,
                        "consent_type": c.consent_type,
                        "max_coalition_size": c.max_coalition_size,
                        "coordination_penalty": c.coordination_penalty
                    },
                    "fitness": c.fitness
                }
                for c in self.pareto_front
            ]
        }
        
        results_file = Path("experiments/results") / filename
        results_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n💾 Results saved to {results_file}")
        return results_file


def main():
    """Run GEPA fairness optimization."""
    
    # Check daemon
    client = MinimalSyncClient(socket_path="/Users/dp/projects/ksi/var/run/daemon.sock")
    try:
        result = client.send_event("system:health", {})
        if result.get("status") != "healthy":
            print("❌ Daemon not healthy")
            return
    except Exception as e:
        print(f"❌ Cannot connect to daemon: {e}")
        return
    
    # Configure GEPA
    optimizer = GEPAFairnessOptimizer(
        population_size=10,  # Start small for testing
        num_agents=30,       # Smaller ecosystem for speed
        num_rounds=10        # Fewer rounds for quick evaluation
    )
    
    # Run optimization
    start_time = time.time()
    pareto_front = optimizer.run_optimization(num_generations=5)
    duration = time.time() - start_time
    
    # Report results
    print("\n" + "="*60)
    print("🎯 GEPA OPTIMIZATION COMPLETE")
    print("="*60)
    
    print(f"\n⏱️ Duration: {duration:.1f} seconds")
    print(f"📊 Pareto front size: {len(pareto_front)}")
    
    if pareto_front:
        # Find best for each objective
        best_fairness = min(pareto_front, key=lambda x: 1 - x.fitness.get("fairness", 0))
        best_efficiency = max(pareto_front, key=lambda x: x.fitness.get("efficiency", 0))
        best_diversity = max(pareto_front, key=lambda x: x.fitness.get("diversity", 0))
        
        print("\n🏆 Best Configurations:")
        print(f"\n1️⃣ Maximum Fairness (Gini: {1-best_fairness.fitness['fairness']:.3f}):")
        print(f"   {best_fairness.aggressive_ratio:.1%} Aggressive")
        print(f"   {best_fairness.cooperative_ratio:.1%} Cooperative")
        print(f"   {best_fairness.cautious_ratio:.1%} Cautious")
        print(f"   Refusal: {best_fairness.refusal_threshold:.2f}")
        print(f"   Consent: {best_fairness.consent_type}")
        
        print(f"\n2️⃣ Maximum Efficiency (Trade volume: {best_efficiency.fitness['efficiency']:.2f}):")
        print(f"   {best_efficiency.aggressive_ratio:.1%} Aggressive")
        print(f"   {best_efficiency.cooperative_ratio:.1%} Cooperative")
        print(f"   {best_efficiency.cautious_ratio:.1%} Cautious")
        
        print(f"\n3️⃣ Maximum Diversity (Entropy: {best_diversity.fitness['diversity']:.2f}):")
        print(f"   {best_diversity.aggressive_ratio:.1%} Aggressive")
        print(f"   {best_diversity.cooperative_ratio:.1%} Cooperative")
        print(f"   {best_diversity.cautious_ratio:.1%} Cautious")
    
    # Save results
    optimizer.save_results()
    
    print("\n✅ GEPA optimization complete! Ready for advanced fairness engineering.")


if __name__ == "__main__":
    main()