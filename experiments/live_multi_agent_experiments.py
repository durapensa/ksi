#!/usr/bin/env python3
"""
Live Multi-Agent Experiments for Melting Pot Scenarios
========================================================

Runs actual AI agents through Melting Pot scenarios to collect empirical data
on cooperation, fairness, and emergent behaviors.
"""

import time
import json
import random
import asyncio
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
from ksi_common.sync_client import MinimalSyncClient


class Strategy(Enum):
    """Agent strategies for experiments."""
    ALWAYS_COOPERATE = "always_cooperate"
    ALWAYS_DEFECT = "always_defect"
    TIT_FOR_TAT = "tit_for_tat"
    RANDOM = "random"
    GREEDY = "greedy"
    FAIR = "fair"
    ADAPTIVE = "adaptive"


@dataclass
class AgentProfile:
    """Profile for an experimental agent."""
    agent_id: str
    strategy: Strategy
    component: str = "components/personas/experimental/game_player"
    initial_resources: Dict[str, float] = field(default_factory=dict)
    memory: Dict[str, Any] = field(default_factory=dict)
    performance: Dict[str, float] = field(default_factory=dict)
    

@dataclass
class ExperimentResults:
    """Results from a multi-agent experiment."""
    scenario: str
    num_agents: int
    num_steps: int
    strategies_used: List[Strategy]
    
    # Metrics
    final_gini: float = 0.0
    avg_cooperation_rate: float = 0.0
    total_welfare: float = 0.0
    fairness_violations: int = 0
    exploitation_events: int = 0
    
    # Agent outcomes
    agent_scores: Dict[str, float] = field(default_factory=dict)
    agent_decisions: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    
    # Emergent behaviors
    dominant_strategy: Optional[Strategy] = None
    equilibrium_reached: bool = False
    cooperation_clusters: List[List[str]] = field(default_factory=list)


class LiveMultiAgentExperiment:
    """Framework for running live multi-agent experiments."""
    
    def __init__(self):
        self.client = MinimalSyncClient()
        self.agents: List[AgentProfile] = []
        self.episode_id: Optional[str] = None
        self.current_step: int = 0
        self.max_steps: int = 50
        self.results: Optional[ExperimentResults] = None
        
    def create_agent_profiles(self, strategies: List[Strategy], num_agents: int = 6) -> List[AgentProfile]:
        """Create agent profiles with specified strategies."""
        agents = []
        
        for i in range(num_agents):
            strategy = strategies[i % len(strategies)] if i < len(strategies) else random.choice(strategies)
            
            agent = AgentProfile(
                agent_id=f"agent_{strategy.value}_{i+1}",
                strategy=strategy,
                initial_resources={"energy": 100.0, "points": 0.0}
            )
            agents.append(agent)
            
        print(f"Created {len(agents)} agent profiles:")
        for agent in agents:
            print(f"  - {agent.agent_id}: {agent.strategy.value}")
            
        return agents
    
    def spawn_agents(self, agents: List[AgentProfile]) -> Dict[str, str]:
        """Spawn AI agents with specified profiles."""
        print("\n=== Spawning AI Agents ===")
        spawned_agents = {}
        
        for agent in agents:
            # Create the agent with appropriate prompt based on strategy
            prompt = self.generate_strategy_prompt(agent.strategy)
            
            result = self.client.send_event("agent:spawn", {
                "component": "components/core/base_agent",  # Use base agent component
                "agent_id": agent.agent_id,
                "prompt": prompt,
                "task": f"Play a game theory experiment with strategy: {agent.strategy.value}",
                "variables": {
                    "strategy": agent.strategy.value
                },
                "metadata": {
                    "strategy": agent.strategy.value,
                    "experiment": "live_multi_agent"
                }
            })
            
            if result.get("status") == "created":
                agent_uuid = result.get("agent_id", agent.agent_id)
                spawned_agents[agent.agent_id] = agent_uuid
                print(f"  ✓ Spawned {agent.agent_id} (UUID: {agent_uuid[:8]}...)")
                
                # Initialize agent resources
                self.client.send_event("validator:resource:update_ownership", {
                    "entity": agent.agent_id,
                    "resource_type": "energy",
                    "amount": agent.initial_resources["energy"],
                    "episode_id": self.episode_id
                })
            else:
                print(f"  ✗ Failed to spawn {agent.agent_id}: {result.get('error', 'Unknown error')}")
                
        return spawned_agents
    
    def generate_strategy_prompt(self, strategy: Strategy) -> str:
        """Generate an appropriate prompt for each strategy."""
        prompts = {
            Strategy.ALWAYS_COOPERATE: """
You are a cooperative agent in a game theory experiment.
Your strategy: ALWAYS COOPERATE
- Always choose to cooperate with other agents
- Trust others and seek mutual benefit
- Never defect or exploit others
When asked to make a decision, always choose cooperation.
""",
            Strategy.ALWAYS_DEFECT: """
You are a competitive agent in a game theory experiment.
Your strategy: ALWAYS DEFECT
- Always choose to defect against other agents
- Maximize your own score regardless of others
- Never cooperate
When asked to make a decision, always choose defection.
""",
            Strategy.TIT_FOR_TAT: """
You are a reciprocal agent in a game theory experiment.
Your strategy: TIT FOR TAT
- Start by cooperating
- Copy what the other agent did last time
- Punish defection with defection
- Reward cooperation with cooperation
Track what others do and respond in kind.
""",
            Strategy.RANDOM: """
You are an unpredictable agent in a game theory experiment.
Your strategy: RANDOM
- Choose randomly between cooperation and defection
- Be unpredictable
- Don't follow patterns
Flip a coin for each decision.
""",
            Strategy.GREEDY: """
You are a resource-maximizing agent in a game theory experiment.
Your strategy: GREEDY
- Always try to get the most resources
- Take as much as possible
- Focus on personal gain
- Exploit opportunities when you see them
Maximize your resource collection.
""",
            Strategy.FAIR: """
You are a fairness-focused agent in a game theory experiment.
Your strategy: FAIR
- Seek equitable distribution of resources
- Cooperate when it promotes fairness
- Defect against exploiters
- Share resources equally
Promote fairness and equality.
""",
            Strategy.ADAPTIVE: """
You are an adaptive agent in a game theory experiment.
Your strategy: ADAPTIVE
- Learn from interactions
- Identify successful strategies
- Adapt your behavior based on outcomes
- Switch strategies if current one isn't working
Observe, learn, and adapt.
"""
        }
        
        return prompts.get(strategy, prompts[Strategy.RANDOM])
    
    def run_prisoners_dilemma_experiment(self, num_rounds: int = 10) -> ExperimentResults:
        """Run a Prisoners Dilemma experiment with multiple agents."""
        print("\n" + "="*80)
        print("PRISONERS DILEMMA - LIVE MULTI-AGENT EXPERIMENT")
        print("="*80)
        
        # Setup experiment
        strategies = [
            Strategy.ALWAYS_COOPERATE,
            Strategy.ALWAYS_DEFECT,
            Strategy.TIT_FOR_TAT,
            Strategy.RANDOM,
            Strategy.ADAPTIVE
        ]
        
        self.agents = self.create_agent_profiles(strategies, num_agents=6)
        
        # Create episode
        result = self.client.send_event("episode:create", {
            "scenario_type": "prisoners_dilemma_multi",
            "config": {
                "num_agents": len(self.agents),
                "max_rounds": num_rounds,
                "payoff_matrix": {
                    "both_cooperate": 3,
                    "both_defect": 1,
                    "cooperate_vs_defect": 0,
                    "defect_vs_cooperate": 5
                }
            }
        })
        self.episode_id = result.get("episode_id", "pd_live_001")
        
        # Spawn agents
        agent_uuids = self.spawn_agents(self.agents)
        
        # Initialize results
        self.results = ExperimentResults(
            scenario="prisoners_dilemma",
            num_agents=len(self.agents),
            num_steps=num_rounds,
            strategies_used=strategies
        )
        
        # Run rounds
        print(f"\n=== Running {num_rounds} Rounds ===")
        
        for round_num in range(num_rounds):
            print(f"\nRound {round_num + 1}:")
            
            # Pair agents for interactions
            pairs = self.create_agent_pairs(self.agents)
            
            for agent1, agent2 in pairs:
                # Get decisions from agents
                decision1 = self.get_agent_decision(agent1, agent2, round_num)
                decision2 = self.get_agent_decision(agent2, agent1, round_num)
                
                # Calculate payoffs
                payoff1, payoff2 = self.calculate_payoff(decision1, decision2)
                
                # Update scores
                self.update_agent_score(agent1, payoff1)
                self.update_agent_score(agent2, payoff2)
                
                # Record decisions
                self.results.agent_decisions[agent1.agent_id].append(decision1)
                self.results.agent_decisions[agent2.agent_id].append(decision2)
                
                # Log interaction
                self.client.send_event("metrics:log_interaction", {
                    "episode_id": self.episode_id,
                    "actor": agent1.agent_id,
                    "target": agent2.agent_id,
                    "interaction_type": decision1,
                    "outcome": "success"
                })
                
                print(f"  {agent1.agent_id[:20]:20} vs {agent2.agent_id[:20]:20}: {decision1} vs {decision2} -> {payoff1}, {payoff2}")
            
            # Calculate round metrics
            self.calculate_round_metrics(round_num)
        
        # Final analysis
        self.analyze_experiment_results()
        
        return self.results
    
    def create_agent_pairs(self, agents: List[AgentProfile]) -> List[tuple]:
        """Create pairs of agents for interactions."""
        # For now, simple random pairing
        shuffled = agents.copy()
        random.shuffle(shuffled)
        
        pairs = []
        for i in range(0, len(shuffled) - 1, 2):
            pairs.append((shuffled[i], shuffled[i + 1]))
            
        # If odd number, last agent plays against first
        if len(shuffled) % 2 == 1:
            pairs.append((shuffled[-1], shuffled[0]))
            
        return pairs
    
    def get_agent_decision(self, agent: AgentProfile, opponent: AgentProfile, round_num: int) -> str:
        """Get decision from an agent based on their strategy."""
        
        # For now, use the fallback strategy-based decisions
        # TODO: Implement proper async agent querying with completion:async
        # This would require restructuring the experiment to handle async responses
        
        decision = self.get_fallback_decision(agent, round_num)
        
        # Store decision in memory for TIT_FOR_TAT strategy
        agent.memory["last_decision"] = decision
        agent.memory[f"last_{opponent.agent_id}"] = decision
        
        # Store in interaction history
        history = agent.memory.get("interaction_history", [])
        history.append({
            "round": round_num,
            "opponent": opponent.agent_id,
            "decision": decision
        })
        agent.memory["interaction_history"] = history[-10:]  # Keep last 10 interactions
        
        return decision
    
    def get_fallback_decision(self, agent: AgentProfile, round_num: int) -> str:
        """Get fallback decision based on strategy if agent doesn't respond."""
        if agent.strategy == Strategy.ALWAYS_COOPERATE:
            return "cooperate"
        elif agent.strategy == Strategy.ALWAYS_DEFECT:
            return "defect"
        elif agent.strategy == Strategy.TIT_FOR_TAT:
            return "cooperate" if round_num == 0 else agent.memory.get("last_decision", "cooperate")
        elif agent.strategy == Strategy.RANDOM:
            return random.choice(["cooperate", "defect"])
        else:
            return "cooperate"  # Default
    
    def calculate_payoff(self, decision1: str, decision2: str) -> tuple:
        """Calculate payoffs for two decisions."""
        if decision1 == "cooperate" and decision2 == "cooperate":
            return (3, 3)
        elif decision1 == "cooperate" and decision2 == "defect":
            return (0, 5)
        elif decision1 == "defect" and decision2 == "cooperate":
            return (5, 0)
        else:  # both defect
            return (1, 1)
    
    def update_agent_score(self, agent: AgentProfile, payoff: float):
        """Update agent's score and performance metrics."""
        current_score = agent.performance.get("total_score", 0)
        agent.performance["total_score"] = current_score + payoff
        
        rounds_played = agent.performance.get("rounds_played", 0) + 1
        agent.performance["rounds_played"] = rounds_played
        agent.performance["avg_score"] = agent.performance["total_score"] / rounds_played
    
    def calculate_round_metrics(self, round_num: int):
        """Calculate metrics for the current round."""
        # Count cooperation vs defection
        cooperations = 0
        defections = 0
        
        for agent_id, decisions in self.results.agent_decisions.items():
            if decisions and decisions[-1] == "cooperate":
                cooperations += 1
            elif decisions and decisions[-1] == "defect":
                defections += 1
        
        total = cooperations + defections
        if total > 0:
            coop_rate = cooperations / total
            print(f"  Round cooperation rate: {coop_rate:.2%}")
    
    def analyze_experiment_results(self):
        """Analyze the final results of the experiment."""
        print("\n=== EXPERIMENT ANALYSIS ===")
        
        # Calculate final scores
        for agent in self.agents:
            score = agent.performance.get("total_score", 0)
            self.results.agent_scores[agent.agent_id] = score
            print(f"  {agent.agent_id}: {score} points (strategy: {agent.strategy.value})")
        
        # Calculate final metrics
        result = self.client.send_event("metrics:calculate", {
            "episode_id": self.episode_id,
            "metrics": [
                "gini_coefficient",
                "cooperation_rate",
                "collective_return",
                "fairness_violations",
                "exploitation_index"
            ]
        })
        
        if result.get("metrics"):
            self.results.final_gini = result["metrics"].get("gini_coefficient", 0)
            self.results.avg_cooperation_rate = result["metrics"].get("cooperation_rate", 0)
            self.results.total_welfare = result["metrics"].get("collective_return", 0)
            self.results.fairness_violations = result["metrics"].get("fairness_violations", 0)
            
            print("\n=== FAIRNESS METRICS ===")
            print(f"  Gini Coefficient: {self.results.final_gini:.3f}")
            print(f"  Cooperation Rate: {self.results.avg_cooperation_rate:.2%}")
            print(f"  Total Welfare: {self.results.total_welfare:.1f}")
            print(f"  Fairness Violations: {self.results.fairness_violations}")
        
        # Identify dominant strategy
        strategy_scores = defaultdict(list)
        for agent in self.agents:
            score = agent.performance.get("total_score", 0)
            strategy_scores[agent.strategy].append(score)
        
        avg_by_strategy = {
            strategy: sum(scores) / len(scores) 
            for strategy, scores in strategy_scores.items()
        }
        
        if avg_by_strategy:
            best_strategy = max(avg_by_strategy, key=avg_by_strategy.get)
            self.results.dominant_strategy = best_strategy
            
            print("\n=== STRATEGY PERFORMANCE ===")
            for strategy, avg_score in sorted(avg_by_strategy.items(), key=lambda x: x[1], reverse=True):
                print(f"  {strategy.value}: {avg_score:.1f} avg points")
            print(f"\n  Dominant Strategy: {best_strategy.value}")
        
        # Check for cooperation clusters
        self.identify_cooperation_clusters()
        
        # Check if equilibrium was reached
        self.check_equilibrium()
        
        return self.results
    
    def identify_cooperation_clusters(self):
        """Identify groups of agents that cooperated with each other."""
        # Simple clustering based on cooperation frequency
        cooperation_matrix = defaultdict(lambda: defaultdict(int))
        
        # This would need more sophisticated tracking in production
        print("\n=== COOPERATION PATTERNS ===")
        
        # For now, identify agents that mostly cooperated
        cooperators = []
        defectors = []
        
        for agent in self.agents:
            decisions = self.results.agent_decisions.get(agent.agent_id, [])
            if decisions:
                coop_rate = decisions.count("cooperate") / len(decisions)
                if coop_rate > 0.7:
                    cooperators.append(agent.agent_id)
                elif coop_rate < 0.3:
                    defectors.append(agent.agent_id)
        
        if cooperators:
            print(f"  Cooperative cluster: {cooperators}")
            self.results.cooperation_clusters.append(cooperators)
        if defectors:
            print(f"  Defector cluster: {defectors}")
    
    def check_equilibrium(self):
        """Check if the system reached a Nash equilibrium."""
        # Simple check: did strategies stabilize in the last few rounds?
        stable_threshold = 3  # Last 3 rounds
        
        for agent_id, decisions in self.results.agent_decisions.items():
            if len(decisions) >= stable_threshold:
                last_decisions = decisions[-stable_threshold:]
                if len(set(last_decisions)) == 1:
                    # Agent's strategy stabilized
                    continue
                else:
                    # At least one agent is still changing
                    self.results.equilibrium_reached = False
                    return
        
        self.results.equilibrium_reached = True
        print(f"\n  Equilibrium reached: {self.results.equilibrium_reached}")
    
    def run_commons_harvest_experiment(self, num_steps: int = 20) -> ExperimentResults:
        """Run a Commons Harvest experiment with resource depletion."""
        print("\n" + "="*80)
        print("COMMONS HARVEST - LIVE MULTI-AGENT EXPERIMENT")
        print("="*80)
        
        # Setup experiment with different harvesting strategies
        strategies = [
            Strategy.GREEDY,      # Take as much as possible
            Strategy.FAIR,        # Take fair share
            Strategy.ADAPTIVE,    # Adapt based on resource levels
            Strategy.GREEDY,      # Another greedy agent
            Strategy.FAIR,        # Another fair agent
        ]
        
        self.agents = self.create_agent_profiles(strategies, num_agents=5)
        
        # Create episode
        result = self.client.send_event("episode:create", {
            "scenario_type": "commons_harvest",
            "config": {
                "num_agents": len(self.agents),
                "max_steps": num_steps,
                "initial_resources": 1000,
                "regeneration_rate": 0.05,
                "sustainability_threshold": 200
            }
        })
        self.episode_id = result.get("episode_id", "commons_live_001")
        
        # Initialize common resource pool
        self.client.send_event("resource:create", {
            "episode_id": self.episode_id,
            "resource_type": "apples",
            "amount": 1000,
            "owner": "commons"
        })
        
        # Track resources in metrics
        self.client.send_event("metrics:update_resources", {
            "episode_id": self.episode_id,
            "entity": "commons",
            "resource_type": "apples",
            "amount": 1000
        })
        
        current_resources = 1000
        
        # Spawn agents
        agent_uuids = self.spawn_agents(self.agents)
        
        # Initialize results
        self.results = ExperimentResults(
            scenario="commons_harvest",
            num_agents=len(self.agents),
            num_steps=num_steps,
            strategies_used=strategies
        )
        
        # Run harvesting rounds
        print(f"\n=== Running {num_steps} Steps ===")
        
        for step in range(num_steps):
            print(f"\nStep {step + 1} (Resources: {current_resources:.0f}):")
            
            step_harvest = 0
            
            for agent in self.agents:
                # Determine harvest amount based on strategy
                harvest = self.get_harvest_decision(agent, current_resources, len(self.agents))
                
                # Validate harvest
                if harvest > 0 and harvest <= current_resources:
                    # Execute harvest
                    self.client.send_event("resource:transfer", {
                        "episode_id": self.episode_id,
                        "from_entity": "commons",
                        "to_entity": agent.agent_id,
                        "resource_type": "apples",
                        "amount": harvest
                    })
                    
                    current_resources -= harvest
                    step_harvest += harvest
                    
                    # Update agent score
                    self.update_agent_score(agent, harvest)
                    
                    print(f"  {agent.agent_id[:20]:20} harvested {harvest:.0f} (strategy: {agent.strategy.value})")
                else:
                    print(f"  {agent.agent_id[:20]:20} couldn't harvest (insufficient resources)")
            
            # Regeneration
            regeneration = current_resources * 0.05
            current_resources = min(1000, current_resources + regeneration)  # Cap at initial amount
            print(f"  Regeneration: +{regeneration:.1f}")
            
            # Check for tragedy of commons
            if current_resources < 100:
                print("  ⚠️ WARNING: Resources critically low!")
                self.results.exploitation_events += 1
            
            # Update metrics
            self.client.send_event("metrics:update_resources", {
                "episode_id": self.episode_id,
                "entity": "commons",
                "resource_type": "apples",
                "amount": current_resources
            })
        
        # Final analysis
        print(f"\n=== FINAL RESOURCE LEVEL: {current_resources:.0f}/1000 ===")
        
        if current_resources < 200:
            print("❌ TRAGEDY OF THE COMMONS OCCURRED")
        elif current_resources > 800:
            print("✅ SUSTAINABLE HARVESTING ACHIEVED")
        else:
            print("⚠️ PARTIAL DEPLETION")
        
        self.analyze_experiment_results()
        
        return self.results
    
    def get_harvest_decision(self, agent: AgentProfile, available: float, num_agents: int) -> float:
        """Get harvest decision based on agent strategy."""
        
        if agent.strategy == Strategy.GREEDY:
            # Take as much as possible (up to 30% of what's available)
            return min(available * 0.3, 100)
            
        elif agent.strategy == Strategy.FAIR:
            # Take fair share
            fair_share = available / num_agents
            sustainable_harvest = available * 0.05  # Match regeneration rate
            return min(fair_share, sustainable_harvest, 50)
            
        elif agent.strategy == Strategy.ADAPTIVE:
            # Adapt based on resource level
            if available > 800:
                return 50  # Harvest more when abundant
            elif available > 400:
                return 30  # Moderate harvesting
            else:
                return 10  # Conservative when scarce
                
        else:
            return 30  # Default moderate harvest


def main():
    """Run live multi-agent experiments."""
    experiment = LiveMultiAgentExperiment()
    
    # Run experiments
    pd_results = experiment.run_prisoners_dilemma_experiment(num_rounds=10)
    
    # Reset for next experiment
    experiment = LiveMultiAgentExperiment()
    commons_results = experiment.run_commons_harvest_experiment(num_steps=20)
    
    # Summary
    print("\n" + "="*80)
    print("EXPERIMENT SUMMARY")
    print("="*80)
    
    print("\nPrisoners Dilemma:")
    print(f"  Dominant Strategy: {pd_results.dominant_strategy.value if pd_results.dominant_strategy else 'None'}")
    print(f"  Cooperation Rate: {pd_results.avg_cooperation_rate:.2%}")
    print(f"  Gini Coefficient: {pd_results.final_gini:.3f}")
    
    print("\nCommons Harvest:")
    print(f"  Dominant Strategy: {commons_results.dominant_strategy.value if commons_results.dominant_strategy else 'None'}")
    print(f"  Total Welfare: {commons_results.total_welfare:.1f}")
    print(f"  Exploitation Events: {commons_results.exploitation_events}")


if __name__ == "__main__":
    main()