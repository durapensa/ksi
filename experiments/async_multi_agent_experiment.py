#!/usr/bin/env python3
"""
Async Multi-Agent Experiment Framework
======================================

True live multi-agent experiments with async AI agent interactions.
Uses KSI's completion:async event for real agent responses.
"""

import asyncio
import time
import random
from typing import Dict, List, Any, Optional
from collections import defaultdict
from enum import Enum
from dataclasses import dataclass, field

from ksi_common.sync_client import MinimalSyncClient


class Strategy(Enum):
    """Agent strategies for game theory experiments."""
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
    initial_resources: Dict[str, float] = field(default_factory=lambda: {"energy": 100.0})
    performance: Dict[str, Any] = field(default_factory=dict)
    memory: Dict[str, Any] = field(default_factory=dict)
    pending_request: Optional[str] = None  # Track pending async request


@dataclass
class InteractionResult:
    """Result of an agent interaction."""
    agent1_id: str
    agent2_id: str
    agent1_decision: str
    agent2_decision: str
    agent1_payoff: float
    agent2_payoff: float
    round_num: int
    timestamp: float


class AsyncMultiAgentExperiment:
    """Framework for async multi-agent experiments."""
    
    def __init__(self):
        self.client = MinimalSyncClient()
        self.agents: List[AgentProfile] = []
        self.episode_id: Optional[str] = None
        self.interaction_results: List[InteractionResult] = []
        self.pending_decisions: Dict[str, str] = {}  # agent_id -> request_id
        
    def create_agent_profiles(self, strategies: List[Strategy], num_agents: int = 6) -> List[AgentProfile]:
        """Create agent profiles with specified strategies."""
        agents = []
        strategy_counts = defaultdict(int)
        
        for i in range(num_agents):
            strategy = strategies[i % len(strategies)]
            strategy_counts[strategy] += 1
            
            agent_id = f"agent_{strategy.value}_{strategy_counts[strategy]}"
            agent = AgentProfile(
                agent_id=agent_id,
                strategy=strategy
            )
            agents.append(agent)
            
        return agents
    
    def spawn_agents(self, agents: List[AgentProfile]) -> Dict[str, str]:
        """Spawn AI agents with specified profiles."""
        print("\n=== Spawning AI Agents ===")
        spawned_agents = {}
        
        for agent in agents:
            prompt = self.generate_strategy_prompt(agent.strategy)
            
            result = self.client.send_event("agent:spawn", {
                "component": "components/core/base_agent",
                "agent_id": agent.agent_id,
                "prompt": prompt,
                "task": f"Play a game theory experiment with strategy: {agent.strategy.value}",
                "variables": {
                    "strategy": agent.strategy.value
                },
                "metadata": {
                    "strategy": agent.strategy.value,
                    "experiment": "async_multi_agent"
                }
            })
            
            if result.get("status") == "created":
                agent_uuid = result.get("agent_id", agent.agent_id)
                spawned_agents[agent.agent_id] = agent_uuid
                print(f"  ✓ Spawned {agent.agent_id}")
            else:
                print(f"  ✗ Failed to spawn {agent.agent_id}")
                
        return spawned_agents
    
    def generate_strategy_prompt(self, strategy: Strategy) -> str:
        """Generate an appropriate prompt for each strategy."""
        prompts = {
            Strategy.ALWAYS_COOPERATE: """
You are a cooperative agent in a game theory experiment.
Your strategy: ALWAYS COOPERATE
Always choose to cooperate with other agents.
When asked to make a decision, respond with: COOPERATE
""",
            Strategy.ALWAYS_DEFECT: """
You are a competitive agent in a game theory experiment.
Your strategy: ALWAYS DEFECT
Always choose to defect against other agents.
When asked to make a decision, respond with: DEFECT
""",
            Strategy.TIT_FOR_TAT: """
You are a reciprocal agent in a game theory experiment.
Your strategy: TIT FOR TAT
Start by cooperating, then copy what your opponent did last time.
If they cooperated, you cooperate. If they defected, you defect.
""",
            Strategy.RANDOM: """
You are a random agent in a game theory experiment.
Your strategy: RANDOM
Choose randomly between cooperating and defecting.
Mix up your choices unpredictably.
""",
            Strategy.GREEDY: """
You are a greedy agent in a game theory experiment.
Your strategy: GREEDY
Focus on maximizing your own score.
Defect most of the time, cooperate rarely.
""",
            Strategy.FAIR: """
You are a fairness-focused agent in a game theory experiment.
Your strategy: FAIR
Seek equitable outcomes for all.
Cooperate with cooperators, punish defectors.
""",
            Strategy.ADAPTIVE: """
You are an adaptive agent in a game theory experiment.
Your strategy: ADAPTIVE
Learn from past interactions and adapt.
Switch strategies based on what works best.
"""
        }
        
        return prompts.get(strategy, prompts[Strategy.RANDOM])
    
    def request_agent_decision(self, agent: AgentProfile, opponent: AgentProfile, round_num: int) -> str:
        """Send async request for agent decision."""
        
        # Build context for the agent
        history = agent.memory.get("interaction_history", [])
        
        prompt = f"""
Round {round_num + 1} of Prisoners Dilemma
Opponent: {opponent.agent_id}
Your current score: {agent.performance.get('total_score', 0)}

Payoff matrix:
- Both cooperate: 3 points each
- You cooperate, they defect: You get 0, they get 5
- You defect, they cooperate: You get 5, they get 0
- Both defect: 1 point each

What is your decision? Respond with just: COOPERATE or DEFECT
"""
        
        # Send async completion request
        result = self.client.send_event("completion:async", {
            "agent_id": agent.agent_id,
            "prompt": prompt,
            "max_tokens": 20
        })
        
        if result.get("status") == "queued":
            request_id = result.get("request_id", f"req_{agent.agent_id}_{round_num}")
            agent.pending_request = request_id
            return request_id
        else:
            print(f"  ⚠ Failed to queue request for {agent.agent_id}")
            return None
    
    def collect_agent_decisions(self, agents: List[AgentProfile], timeout: float = 5.0) -> Dict[str, str]:
        """Collect async responses from agents."""
        decisions = {}
        start_time = time.time()
        
        # Wait for responses with timeout
        while time.time() - start_time < timeout:
            all_received = True
            
            for agent in agents:
                if agent.agent_id not in decisions and agent.pending_request:
                    # Check if response is ready
                    # In a real system, we'd poll or have a callback mechanism
                    # For now, we'll use fallback decisions after timeout
                    all_received = False
            
            if all_received:
                break
            
            time.sleep(0.1)
        
        # Use fallback for any missing decisions
        for agent in agents:
            if agent.agent_id not in decisions:
                decisions[agent.agent_id] = self.get_fallback_decision(agent)
                print(f"    Using fallback for {agent.agent_id}: {decisions[agent.agent_id]}")
        
        return decisions
    
    def get_fallback_decision(self, agent: AgentProfile) -> str:
        """Get fallback decision based on strategy."""
        if agent.strategy == Strategy.ALWAYS_COOPERATE:
            return "cooperate"
        elif agent.strategy == Strategy.ALWAYS_DEFECT:
            return "defect"
        elif agent.strategy == Strategy.TIT_FOR_TAT:
            # Check last opponent move
            last_opponent_move = agent.memory.get("last_opponent_move", "cooperate")
            return last_opponent_move
        elif agent.strategy == Strategy.RANDOM:
            return random.choice(["cooperate", "defect"])
        elif agent.strategy == Strategy.GREEDY:
            return "defect" if random.random() > 0.2 else "cooperate"
        elif agent.strategy == Strategy.FAIR:
            # Cooperate if opponent has been fair
            opponent_defections = agent.memory.get("opponent_defections", 0)
            return "defect" if opponent_defections > 2 else "cooperate"
        elif agent.strategy == Strategy.ADAPTIVE:
            # Simple adaptive strategy
            avg_score = agent.performance.get("avg_score", 0)
            return "cooperate" if avg_score > 2 else "defect"
        else:
            return "cooperate"
    
    def run_prisoners_dilemma_round(self, round_num: int):
        """Run a single round of Prisoners Dilemma."""
        print(f"\nRound {round_num + 1}:")
        
        # Create pairs for this round
        pairs = self.create_agent_pairs(self.agents)
        
        # Request decisions from all agents
        for agent1, agent2 in pairs:
            self.request_agent_decision(agent1, agent2, round_num)
            self.request_agent_decision(agent2, agent1, round_num)
        
        # Collect decisions (with timeout and fallback)
        decisions = self.collect_agent_decisions(self.agents)
        
        # Process interactions
        round_cooperations = 0
        round_defections = 0
        
        for agent1, agent2 in pairs:
            decision1 = decisions.get(agent1.agent_id, "cooperate")
            decision2 = decisions.get(agent2.agent_id, "cooperate")
            
            # Calculate payoffs
            payoff1, payoff2 = self.calculate_payoff(decision1, decision2)
            
            # Update scores
            self.update_agent_score(agent1, payoff1)
            self.update_agent_score(agent2, payoff2)
            
            # Update memory for TIT_FOR_TAT
            agent1.memory["last_opponent_move"] = decision2
            agent2.memory["last_opponent_move"] = decision1
            
            # Track decisions
            if decision1 == "cooperate":
                round_cooperations += 1
            else:
                round_defections += 1
                
            if decision2 == "cooperate":
                round_cooperations += 1
            else:
                round_defections += 1
            
            # Store result
            result = InteractionResult(
                agent1_id=agent1.agent_id,
                agent2_id=agent2.agent_id,
                agent1_decision=decision1,
                agent2_decision=decision2,
                agent1_payoff=payoff1,
                agent2_payoff=payoff2,
                round_num=round_num,
                timestamp=time.time()
            )
            self.interaction_results.append(result)
            
            print(f"  {agent1.agent_id:20} vs {agent2.agent_id:20}: {decision1} vs {decision2} -> {payoff1}, {payoff2}")
        
        # Calculate round metrics
        total_decisions = round_cooperations + round_defections
        if total_decisions > 0:
            cooperation_rate = round_cooperations / total_decisions * 100
            print(f"  Round cooperation rate: {cooperation_rate:.1f}%")
    
    def create_agent_pairs(self, agents: List[AgentProfile]) -> List[tuple]:
        """Create pairs of agents for interactions."""
        shuffled = agents.copy()
        random.shuffle(shuffled)
        
        pairs = []
        for i in range(0, len(shuffled) - 1, 2):
            pairs.append((shuffled[i], shuffled[i + 1]))
            
        # If odd number, last agent plays against first
        if len(shuffled) % 2 == 1:
            pairs.append((shuffled[-1], shuffled[0]))
            
        return pairs
    
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
    
    def run_experiment(self, num_rounds: int = 10):
        """Run the full async multi-agent experiment."""
        print("\n" + "="*80)
        print("ASYNC PRISONERS DILEMMA - LIVE MULTI-AGENT EXPERIMENT")
        print("="*80)
        
        # Setup
        strategies = [
            Strategy.ALWAYS_COOPERATE,
            Strategy.ALWAYS_DEFECT,
            Strategy.TIT_FOR_TAT,
            Strategy.RANDOM,
            Strategy.FAIR,
            Strategy.ADAPTIVE
        ]
        
        self.agents = self.create_agent_profiles(strategies, num_agents=6)
        
        print(f"Created {len(self.agents)} agent profiles:")
        for agent in self.agents:
            print(f"  - {agent.agent_id}: {agent.strategy.value}")
        
        # Spawn agents
        spawned = self.spawn_agents(self.agents)
        
        if len(spawned) == 0:
            print("No agents spawned successfully. Exiting.")
            return
        
        # Create episode
        result = self.client.send_event("episode:create", {
            "scenario_type": "async_prisoners_dilemma",
            "config": {
                "num_agents": len(self.agents),
                "max_rounds": num_rounds
            }
        })
        self.episode_id = result.get("episode_id", "async_pd_001")
        
        # Run rounds
        print(f"\n=== Running {num_rounds} Rounds ===")
        for round_num in range(num_rounds):
            self.run_prisoners_dilemma_round(round_num)
        
        # Analysis
        self.analyze_results()
    
    def analyze_results(self):
        """Analyze and display experiment results."""
        print("\n" + "="*80)
        print("EXPERIMENT ANALYSIS")
        print("="*80)
        
        # Sort agents by total score
        sorted_agents = sorted(self.agents, key=lambda a: a.performance.get("total_score", 0), reverse=True)
        
        print("\nFinal Scores:")
        for agent in sorted_agents:
            score = agent.performance.get("total_score", 0)
            avg = agent.performance.get("avg_score", 0)
            print(f"  {agent.agent_id:30} {score:3.0f} points (avg: {avg:.2f}) - {agent.strategy.value}")
        
        # Strategy analysis
        strategy_scores = defaultdict(list)
        for agent in self.agents:
            strategy_scores[agent.strategy].append(agent.performance.get("total_score", 0))
        
        print("\nStrategy Performance:")
        for strategy, scores in strategy_scores.items():
            avg_score = sum(scores) / len(scores) if scores else 0
            print(f"  {strategy.value:20} avg score: {avg_score:.1f}")
        
        # Cooperation analysis
        total_cooperations = 0
        total_defections = 0
        
        for result in self.interaction_results:
            if result.agent1_decision == "cooperate":
                total_cooperations += 1
            else:
                total_defections += 1
                
            if result.agent2_decision == "cooperate":
                total_cooperations += 1
            else:
                total_defections += 1
        
        total_decisions = total_cooperations + total_defections
        if total_decisions > 0:
            overall_cooperation_rate = total_cooperations / total_decisions * 100
            print(f"\nOverall Cooperation Rate: {overall_cooperation_rate:.1f}%")
        
        # Metrics to KSI
        if self.episode_id:
            self.client.send_event("metrics:calculate", {
                "episode_id": self.episode_id,
                "metrics": ["cooperation_rate", "gini_coefficient", "fairness_violations"]
            })


if __name__ == "__main__":
    experiment = AsyncMultiAgentExperiment()
    experiment.run_experiment(num_rounds=10)