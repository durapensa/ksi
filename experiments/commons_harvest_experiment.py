#!/usr/bin/env python3
"""
Commons Harvest Multi-Agent Experiment
=======================================

Tests resource management, sustainability, and fairness in a shared commons scenario.
Uses the Melting Pot validators and metrics pipeline.
"""

import time
import random
from typing import Dict, List, Any, Optional
from collections import defaultdict
from enum import Enum
from dataclasses import dataclass, field

from ksi_common.sync_client import MinimalSyncClient


class HarvestStrategy(Enum):
    """Harvesting strategies for commons management."""
    SUSTAINABLE = "sustainable"      # Take only what regenerates
    GREEDY = "greedy"               # Take as much as possible
    FAIR_SHARE = "fair_share"       # Take equal portion
    ADAPTIVE = "adaptive"           # Adjust based on resource levels
    PUNISHER = "punisher"           # Punish over-harvesters
    RANDOM = "random"               # Random harvest amounts


@dataclass
class HarvesterAgent:
    """Agent profile for commons harvest experiment."""
    agent_id: str
    strategy: HarvestStrategy
    resources: Dict[str, float] = field(default_factory=lambda: {"apples": 0.0, "energy": 100.0})
    harvest_history: List[float] = field(default_factory=list)
    performance: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def total_harvested(self) -> float:
        return sum(self.harvest_history)
    
    @property
    def average_harvest(self) -> float:
        return sum(self.harvest_history) / len(self.harvest_history) if self.harvest_history else 0


@dataclass
class CommonsState:
    """State of the commons resource pool."""
    total_resources: float
    initial_resources: float
    regeneration_rate: float
    sustainability_threshold: float
    depletion_count: int = 0
    
    def regenerate(self):
        """Apply regeneration to resources."""
        if self.total_resources > 0:
            regenerated = self.total_resources * self.regeneration_rate
            self.total_resources = min(self.total_resources + regenerated, self.initial_resources * 1.5)
    
    def is_sustainable(self) -> bool:
        """Check if commons is above sustainability threshold."""
        return self.total_resources > self.sustainability_threshold
    
    def is_depleted(self) -> bool:
        """Check if commons is depleted."""
        return self.total_resources < 10


class CommonsHarvestExperiment:
    """Framework for commons harvest experiments."""
    
    def __init__(self):
        self.client = MinimalSyncClient()
        self.agents: List[HarvesterAgent] = []
        self.commons: Optional[CommonsState] = None
        self.episode_id: Optional[str] = None
        self.round_metrics: List[Dict[str, Any]] = []
        
    def setup_experiment(self, num_agents: int = 6, initial_resources: float = 1000.0):
        """Set up the commons harvest experiment."""
        print("\n" + "="*80)
        print("COMMONS HARVEST - MULTI-AGENT RESOURCE MANAGEMENT")
        print("="*80)
        
        # Create commons
        self.commons = CommonsState(
            total_resources=initial_resources,
            initial_resources=initial_resources,
            regeneration_rate=0.1,  # 10% regeneration per round
            sustainability_threshold=initial_resources * 0.2  # 20% is minimum sustainable
        )
        
        # Create episode
        result = self.client.send_event("episode:create", {
            "scenario_type": "commons_harvest",
            "config": {
                "grid_size": 10,
                "max_steps": 20,
                "initial_resources": initial_resources,
                "regeneration_rate": self.commons.regeneration_rate,
                "sustainability_threshold": self.commons.sustainability_threshold
            }
        })
        self.episode_id = result.get("episode_id", "commons_001")
        
        # Initialize commons resources in validator
        self.client.send_event("validator:resource:update_ownership", {
            "entity": "commons",
            "resource_type": "apples",
            "amount": initial_resources,
            "episode_id": self.episode_id
        })
        
        # Also create in resource system
        self.client.send_event("resource:create", {
            "episode_id": self.episode_id,
            "resource_type": "apples",
            "amount": initial_resources,
            "owner": "commons"
        })
        
        # Track in metrics
        self.client.send_event("metrics:update_resources", {
            "episode_id": self.episode_id,
            "entity": "commons",
            "resource_type": "apples",
            "amount": initial_resources
        })
        
        # Create agents with different strategies
        strategies = [
            HarvestStrategy.SUSTAINABLE,
            HarvestStrategy.GREEDY,
            HarvestStrategy.FAIR_SHARE,
            HarvestStrategy.ADAPTIVE,
            HarvestStrategy.PUNISHER,
            HarvestStrategy.RANDOM
        ]
        
        self.agents = []
        for i in range(num_agents):
            strategy = strategies[i % len(strategies)]
            agent = HarvesterAgent(
                agent_id=f"harvester_{strategy.value}_{i+1}",
                strategy=strategy
            )
            self.agents.append(agent)
            
            # Spawn the agent
            self.spawn_harvester_agent(agent)
            
            # Initialize agent resources in validator
            self.client.send_event("validator:resource:update_ownership", {
                "entity": agent.agent_id,
                "resource_type": "apples",
                "amount": 0,
                "episode_id": self.episode_id
            })
        
        print(f"\nInitialized commons with {initial_resources} resources")
        print(f"Regeneration rate: {self.commons.regeneration_rate * 100}%")
        print(f"Sustainability threshold: {self.commons.sustainability_threshold}")
        print(f"\nCreated {len(self.agents)} harvester agents:")
        for agent in self.agents:
            print(f"  - {agent.agent_id}: {agent.strategy.value}")
    
    def spawn_harvester_agent(self, agent: HarvesterAgent):
        """Spawn a harvester agent with appropriate prompt."""
        prompts = {
            HarvestStrategy.SUSTAINABLE: "Harvest sustainably. Take only what can regenerate.",
            HarvestStrategy.GREEDY: "Maximize your harvest. Take as much as possible.",
            HarvestStrategy.FAIR_SHARE: "Take your fair share. Divide resources equally.",
            HarvestStrategy.ADAPTIVE: "Adapt to resource levels. Conserve when low.",
            HarvestStrategy.PUNISHER: "Punish over-harvesters by taking more when others are greedy.",
            HarvestStrategy.RANDOM: "Harvest random amounts each round."
        }
        
        result = self.client.send_event("agent:spawn", {
            "component": "components/core/base_agent",
            "agent_id": agent.agent_id,
            "prompt": prompts.get(agent.strategy, "Harvest resources from the commons."),
            "task": f"Harvest resources using {agent.strategy.value} strategy",
            "metadata": {
                "strategy": agent.strategy.value,
                "experiment": "commons_harvest"
            }
        })
        
        if result.get("status") == "created":
            print(f"  ✓ Spawned {agent.agent_id}")
        else:
            print(f"  ✗ Failed to spawn {agent.agent_id}")
    
    def calculate_harvest_amount(self, agent: HarvesterAgent, round_num: int) -> float:
        """Calculate how much an agent wants to harvest based on strategy."""
        available = self.commons.total_resources
        num_agents = len(self.agents)
        
        if available <= 0:
            return 0
        
        if agent.strategy == HarvestStrategy.SUSTAINABLE:
            # Take only what can regenerate
            sustainable_amount = available * self.commons.regeneration_rate
            return min(sustainable_amount / num_agents, available / num_agents)
        
        elif agent.strategy == HarvestStrategy.GREEDY:
            # Try to take 30-50% of what's available
            return min(available * random.uniform(0.3, 0.5), available)
        
        elif agent.strategy == HarvestStrategy.FAIR_SHARE:
            # Take exactly 1/n of available resources
            return available / num_agents
        
        elif agent.strategy == HarvestStrategy.ADAPTIVE:
            # Adjust based on resource levels
            if self.commons.is_sustainable():
                # Resources are healthy, take normal share
                return available / num_agents
            else:
                # Resources are low, be conservative
                return available * 0.05
        
        elif agent.strategy == HarvestStrategy.PUNISHER:
            # Check if others are being greedy
            if round_num > 0:
                avg_harvest = sum(a.harvest_history[-1] if a.harvest_history else 0 
                                for a in self.agents) / num_agents
                fair_share = self.commons.initial_resources / num_agents / 10
                
                if avg_harvest > fair_share * 1.5:
                    # Others are being greedy, punish by taking more
                    return min(available * 0.4, available)
                else:
                    # Others are cooperating, be fair
                    return available / num_agents
            else:
                return available / num_agents
        
        elif agent.strategy == HarvestStrategy.RANDOM:
            # Random between 5% and 25% of available
            return min(available * random.uniform(0.05, 0.25), available)
        
        else:
            return available / num_agents
    
    def validate_harvest(self, agent: HarvesterAgent, requested_amount: float) -> tuple:
        """Validate harvest request through KSI validators."""
        # Check resource transfer validity
        result = self.client.send_event("validator:resource:validate", {
            "from_entity": "commons",
            "to_entity": agent.agent_id,
            "resource_type": "apples",
            "amount": requested_amount,
            "transfer_type": "harvest",
            "metadata": {
                "episode_id": self.episode_id,
                "round": len(agent.harvest_history)
            }
        })
        
        if result.get("valid"):
            return True, requested_amount
        else:
            # Check if validator suggests alternative amount
            suggested = result.get("suggested_amount")
            if suggested is not None and suggested > 0:
                return True, suggested
            else:
                return False, 0
    
    def execute_harvest(self, agent: HarvesterAgent, amount: float):
        """Execute the harvest and update resources."""
        if amount <= 0 or amount > self.commons.total_resources:
            return False
        
        # Update commons
        self.commons.total_resources -= amount
        
        # Update agent resources
        agent.resources["apples"] += amount
        agent.harvest_history.append(amount)
        
        # Update validator tracking
        self.client.send_event("validator:resource:update_ownership", {
            "entity": "commons",
            "resource_type": "apples",
            "amount": self.commons.total_resources,
            "episode_id": self.episode_id
        })
        
        self.client.send_event("validator:resource:update_ownership", {
            "entity": agent.agent_id,
            "resource_type": "apples",
            "amount": agent.resources["apples"],
            "episode_id": self.episode_id
        })
        
        # Log to metrics
        self.client.send_event("metrics:log_interaction", {
            "episode_id": self.episode_id,
            "actor": agent.agent_id,
            "target": "commons",
            "interaction_type": "harvest",
            "outcome": "success",
            "value": amount
        })
        
        return True
    
    def run_harvest_round(self, round_num: int):
        """Run a single harvest round."""
        print(f"\n=== Round {round_num + 1} ===")
        print(f"Commons resources: {self.commons.total_resources:.1f}")
        
        round_harvests = {}
        
        # Each agent attempts to harvest
        random.shuffle(self.agents)  # Random order each round
        
        for agent in self.agents:
            # Calculate desired harvest
            requested = self.calculate_harvest_amount(agent, round_num)
            
            # Validate through fairness system
            valid, allowed = self.validate_harvest(agent, requested)
            
            # Execute harvest
            if valid and allowed > 0:
                actual = min(allowed, self.commons.total_resources)
                if self.execute_harvest(agent, actual):
                    round_harvests[agent.agent_id] = actual
                    print(f"  {agent.agent_id:25} harvested {actual:.1f} apples")
                else:
                    print(f"  {agent.agent_id:25} failed to harvest")
                    round_harvests[agent.agent_id] = 0
            else:
                print(f"  {agent.agent_id:25} blocked by fairness rules")
                round_harvests[agent.agent_id] = 0
        
        # Apply regeneration
        before_regen = self.commons.total_resources
        self.commons.regenerate()
        regenerated = self.commons.total_resources - before_regen
        
        print(f"\nResources after harvest: {before_regen:.1f}")
        print(f"Regeneration: +{regenerated:.1f}")
        print(f"Resources after regeneration: {self.commons.total_resources:.1f}")
        
        # Check sustainability
        if not self.commons.is_sustainable():
            print("  ⚠ WARNING: Commons below sustainability threshold!")
            self.commons.depletion_count += 1
        
        if self.commons.is_depleted():
            print("  ❌ COMMONS DEPLETED - Tragedy of the Commons!")
            return False
        
        # Calculate round metrics
        self.calculate_round_metrics(round_num, round_harvests)
        
        return True
    
    def calculate_round_metrics(self, round_num: int, harvests: Dict[str, float]):
        """Calculate metrics for the round."""
        metrics = {
            "round": round_num + 1,
            "total_harvested": sum(harvests.values()),
            "commons_remaining": self.commons.total_resources,
            "sustainability": self.commons.is_sustainable(),
            "harvests": harvests
        }
        
        # Calculate Gini coefficient for this round
        result = self.client.send_event("validator:resource:calculate_gini", {
            "episode_id": self.episode_id
        })
        
        if result.get("gini_coefficient") is not None:
            metrics["gini_coefficient"] = result["gini_coefficient"]
        
        self.round_metrics.append(metrics)
    
    def run_experiment(self, num_rounds: int = 20):
        """Run the full commons harvest experiment."""
        self.setup_experiment()
        
        print(f"\n=== Starting {num_rounds} Round Experiment ===")
        
        for round_num in range(num_rounds):
            if not self.run_harvest_round(round_num):
                print(f"\nExperiment ended early at round {round_num + 1} due to depletion")
                break
        
        self.analyze_results()
    
    def analyze_results(self):
        """Analyze and display experiment results."""
        print("\n" + "="*80)
        print("EXPERIMENT ANALYSIS")
        print("="*80)
        
        # Agent performance
        print("\nAgent Performance:")
        sorted_agents = sorted(self.agents, key=lambda a: a.total_harvested, reverse=True)
        
        for agent in sorted_agents:
            total = agent.total_harvested
            avg = agent.average_harvest
            print(f"  {agent.agent_id:25} Total: {total:6.1f} Avg: {avg:5.1f} - {agent.strategy.value}")
        
        # Commons sustainability
        print(f"\nCommons Analysis:")
        print(f"  Final resources: {self.commons.total_resources:.1f}/{self.commons.initial_resources:.1f}")
        print(f"  Depletion warnings: {self.commons.depletion_count}")
        print(f"  Sustainable: {self.commons.is_sustainable()}")
        
        # Strategy analysis
        strategy_totals = defaultdict(list)
        for agent in self.agents:
            strategy_totals[agent.strategy].append(agent.total_harvested)
        
        print("\nStrategy Performance:")
        for strategy, totals in strategy_totals.items():
            avg_total = sum(totals) / len(totals) if totals else 0
            print(f"  {strategy.value:15} avg harvest: {avg_total:.1f}")
        
        # Fairness metrics
        print("\nFairness Metrics:")
        result = self.client.send_event("metrics:calculate", {
            "episode_id": self.episode_id,
            "metrics": [
                "gini_coefficient",
                "fairness_violations", 
                "exploitation_index",
                "sustainability_index",
                "resource_depletion_rate"
            ]
        })
        
        if result.get("metrics"):
            for metric, value in result["metrics"].items():
                print(f"  {metric}: {value}")
        
        # Round-by-round cooperation
        if self.round_metrics:
            print("\nRound-by-Round Summary:")
            for metrics in self.round_metrics[-5:]:  # Last 5 rounds
                round_num = metrics["round"]
                total = metrics["total_harvested"]
                remaining = metrics["commons_remaining"]
                sustainable = "✓" if metrics["sustainability"] else "✗"
                print(f"  Round {round_num:2}: Harvested {total:6.1f}, Remaining {remaining:6.1f} {sustainable}")


if __name__ == "__main__":
    experiment = CommonsHarvestExperiment()
    experiment.run_experiment(num_rounds=15)