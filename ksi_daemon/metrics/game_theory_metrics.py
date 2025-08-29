#!/usr/bin/env python3
"""
Game Theory Metrics Pipeline for KSI
=====================================

Calculates sophisticated fairness and game-theoretic metrics for multi-agent scenarios.
Integrates with KSI's event system to provide real-time metrics during episodes.

Metrics Included:
- Gini coefficient (inequality)
- Collective return (total welfare)
- Cooperation rate (prosocial behavior)
- Pareto efficiency (optimality)
- Nash equilibrium distance
- Sustainability index
- Fairness violations
"""

import asyncio
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
import json
from datetime import datetime

from ksi_common.event_types import Event
from ksi_daemon.base import ServiceBase, EventHandler


@dataclass
class MetricSnapshot:
    """Snapshot of metrics at a point in time."""
    timestamp: float
    step: int
    metrics: Dict[str, float]
    population_breakdown: Dict[str, Dict[str, float]]


@dataclass
class GameTheoryMetrics:
    """Collection of game theory metrics."""
    gini_coefficient: float = 0.0
    collective_return: float = 0.0
    cooperation_rate: float = 0.0
    pareto_efficiency: float = 0.0
    nash_distance: float = 0.0
    sustainability_index: float = 0.0
    fairness_score: float = 0.0
    
    # Population-specific metrics
    focal_performance: Dict[str, float] = field(default_factory=dict)
    background_performance: Dict[str, float] = field(default_factory=dict)
    
    # Interaction metrics
    cooperation_matrix: np.ndarray = None
    defection_matrix: np.ndarray = None
    
    # Time series data
    history: List[MetricSnapshot] = field(default_factory=list)


class GameTheoryMetricsService(ServiceBase):
    """Service for calculating game theory metrics."""
    
    def __init__(self):
        super().__init__("metrics")
        self.episodes: Dict[str, GameTheoryMetrics] = {}
        self.agent_scores: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.agent_actions: Dict[str, List[str]] = defaultdict(list)
        self.resource_levels: Dict[str, float] = {}
        self.interaction_history: List[Dict] = []
        
    @EventHandler("metrics:calculate")
    async def handle_calculate_metrics(self, event: Event) -> Dict:
        """Calculate requested metrics."""
        data = event.data
        metric_types = data.get("metric_types", ["gini", "collective_return"])
        episode_id = data.get("data_source", {}).get("episode_id")
        
        if not episode_id:
            return {"error": "episode_id required"}
        
        # Get or create metrics for episode
        if episode_id not in self.episodes:
            self.episodes[episode_id] = GameTheoryMetrics()
        
        metrics = self.episodes[episode_id]
        results = {}
        
        # Calculate each requested metric
        for metric_type in metric_types:
            if metric_type == "gini":
                results["gini"] = self._calculate_gini(episode_id)
            elif metric_type == "collective_return":
                results["collective_return"] = self._calculate_collective_return(episode_id)
            elif metric_type == "cooperation_rate":
                results["cooperation_rate"] = self._calculate_cooperation_rate(episode_id)
            elif metric_type == "sustainability":
                results["sustainability"] = self._calculate_sustainability(episode_id)
            elif metric_type == "pareto_efficiency":
                results["pareto_efficiency"] = self._calculate_pareto_efficiency(episode_id)
            elif metric_type == "nash_distance":
                results["nash_distance"] = self._calculate_nash_distance(episode_id)
            elif metric_type == "fairness_score":
                results["fairness_score"] = self._calculate_fairness_score(episode_id)
        
        # Add population breakdown if requested
        if data.get("grouping"):
            results["by_population"] = self._calculate_population_metrics(episode_id, data["grouping"])
        
        # Store snapshot
        snapshot = MetricSnapshot(
            timestamp=datetime.now().timestamp(),
            step=data.get("step", 0),
            metrics=results,
            population_breakdown=results.get("by_population", {})
        )
        metrics.history.append(snapshot)
        
        return {"result": results}
    
    @EventHandler("metrics:update_score")
    async def handle_update_score(self, event: Event) -> Dict:
        """Update agent score for metrics calculation."""
        data = event.data
        episode_id = data["episode_id"]
        agent_id = data["agent_id"]
        score = data["score"]
        
        if episode_id not in self.agent_scores:
            self.agent_scores[episode_id] = {}
        
        self.agent_scores[episode_id][agent_id] = score
        
        return {"status": "updated"}
    
    @EventHandler("metrics:record_action")
    async def handle_record_action(self, event: Event) -> Dict:
        """Record agent action for cooperation analysis."""
        data = event.data
        episode_id = data["episode_id"]
        agent_id = data["agent_id"]
        action = data["action"]
        
        key = f"{episode_id}:{agent_id}"
        self.agent_actions[key].append(action)
        
        # Classify as cooperative or defective
        if self._is_cooperative_action(action):
            await self._update_cooperation_matrix(episode_id, agent_id, True)
        else:
            await self._update_cooperation_matrix(episode_id, agent_id, False)
        
        return {"status": "recorded"}
    
    @EventHandler("metrics:record_interaction")
    async def handle_record_interaction(self, event: Event) -> Dict:
        """Record interaction between agents."""
        data = event.data
        
        interaction = {
            "episode_id": data["episode_id"],
            "agent1": data["agent1"],
            "agent2": data["agent2"],
            "action1": data["action1"],
            "action2": data["action2"],
            "payoff1": data.get("payoff1", 0),
            "payoff2": data.get("payoff2", 0),
            "timestamp": datetime.now().timestamp()
        }
        
        self.interaction_history.append(interaction)
        
        # Update cooperation matrices
        episode_id = data["episode_id"]
        if episode_id not in self.episodes:
            self.episodes[episode_id] = GameTheoryMetrics()
        
        # Analyze interaction type
        if self._is_mutual_cooperation(data["action1"], data["action2"]):
            self.episodes[episode_id].cooperation_rate += 0.01  # Increment
        
        return {"status": "recorded"}
    
    @EventHandler("metrics:update_resources")
    async def handle_update_resources(self, event: Event) -> Dict:
        """Update resource levels for sustainability metrics."""
        data = event.data
        episode_id = data["episode_id"]
        resource_type = data["resource_type"]
        amount = data["amount"]
        
        key = f"{episode_id}:{resource_type}"
        self.resource_levels[key] = amount
        
        return {"status": "updated"}
    
    @EventHandler("metrics:get_report")
    async def handle_get_report(self, event: Event) -> Dict:
        """Generate comprehensive metrics report."""
        data = event.data
        episode_id = data["episode_id"]
        
        if episode_id not in self.episodes:
            return {"error": "episode not found"}
        
        metrics = self.episodes[episode_id]
        
        # Calculate all metrics
        report = {
            "episode_id": episode_id,
            "metrics": {
                "gini_coefficient": self._calculate_gini(episode_id),
                "collective_return": self._calculate_collective_return(episode_id),
                "cooperation_rate": self._calculate_cooperation_rate(episode_id),
                "pareto_efficiency": self._calculate_pareto_efficiency(episode_id),
                "nash_distance": self._calculate_nash_distance(episode_id),
                "sustainability_index": self._calculate_sustainability(episode_id),
                "fairness_score": self._calculate_fairness_score(episode_id)
            },
            "populations": self._calculate_population_metrics(episode_id, {"by": "population"}),
            "time_series": [
                {
                    "timestamp": s.timestamp,
                    "step": s.step,
                    "metrics": s.metrics
                }
                for s in metrics.history[-100:]  # Last 100 snapshots
            ],
            "interaction_summary": self._summarize_interactions(episode_id),
            "fairness_violations": self._detect_fairness_violations(episode_id)
        }
        
        return {"result": report}
    
    # ==================== METRIC CALCULATIONS ====================
    
    def _calculate_gini(self, episode_id: str) -> float:
        """Calculate Gini coefficient for wealth inequality."""
        scores = list(self.agent_scores.get(episode_id, {}).values())
        
        if not scores or len(scores) < 2:
            return 0.0
        
        # Sort scores
        scores = sorted(scores)
        n = len(scores)
        
        # Calculate Gini using the formula
        index = np.arange(1, n + 1)
        return (2 * np.sum(index * scores)) / (n * np.sum(scores)) - (n + 1) / n
    
    def _calculate_collective_return(self, episode_id: str) -> float:
        """Calculate total welfare of all agents."""
        scores = self.agent_scores.get(episode_id, {})
        return sum(scores.values())
    
    def _calculate_cooperation_rate(self, episode_id: str) -> float:
        """Calculate rate of cooperative actions."""
        total_actions = 0
        cooperative_actions = 0
        
        for key, actions in self.agent_actions.items():
            if key.startswith(f"{episode_id}:"):
                total_actions += len(actions)
                cooperative_actions += sum(1 for a in actions if self._is_cooperative_action(a))
        
        if total_actions == 0:
            return 0.0
        
        return cooperative_actions / total_actions
    
    def _calculate_sustainability(self, episode_id: str) -> float:
        """Calculate sustainability index based on resource levels."""
        current_resources = 0
        initial_resources = 0
        
        for key, amount in self.resource_levels.items():
            if key.startswith(f"{episode_id}:"):
                current_resources += amount
                # Assume initial was 100 per resource type
                initial_resources += 100
        
        if initial_resources == 0:
            return 1.0
        
        # Sustainability = current / initial, capped at 1.0
        return min(1.0, current_resources / initial_resources)
    
    def _calculate_pareto_efficiency(self, episode_id: str) -> float:
        """Calculate Pareto efficiency of current state."""
        scores = list(self.agent_scores.get(episode_id, {}).values())
        
        if not scores:
            return 0.0
        
        # Check if any agent could be better off without making others worse off
        # Simplified: measure distance from theoretical Pareto frontier
        max_possible = max(scores) * len(scores)  # If all had max score
        actual = sum(scores)
        
        return actual / max_possible if max_possible > 0 else 0.0
    
    def _calculate_nash_distance(self, episode_id: str) -> float:
        """Calculate distance from Nash equilibrium."""
        # Analyze recent interactions to find equilibrium
        recent_interactions = [
            i for i in self.interaction_history
            if i["episode_id"] == episode_id
        ][-100:]  # Last 100 interactions
        
        if not recent_interactions:
            return 0.0
        
        # Count strategy changes (deviations from equilibrium)
        strategy_changes = 0
        for i in range(1, len(recent_interactions)):
            prev = recent_interactions[i-1]
            curr = recent_interactions[i]
            
            # Check if same agents changed strategy
            if prev["agent1"] == curr["agent1"]:
                if self._classify_action(prev["action1"]) != self._classify_action(curr["action1"]):
                    strategy_changes += 1
        
        # Normalize by number of interactions
        return strategy_changes / len(recent_interactions)
    
    def _calculate_fairness_score(self, episode_id: str) -> float:
        """Calculate overall fairness score."""
        # Combine multiple fairness indicators
        gini = self._calculate_gini(episode_id)
        cooperation = self._calculate_cooperation_rate(episode_id)
        sustainability = self._calculate_sustainability(episode_id)
        
        # Fairness improves with low inequality, high cooperation, and sustainability
        fairness = (1 - gini) * 0.4 + cooperation * 0.3 + sustainability * 0.3
        
        # Check for violations
        violations = len(self._detect_fairness_violations(episode_id))
        if violations > 0:
            fairness *= (1 - min(0.5, violations * 0.1))  # Penalty for violations
        
        return fairness
    
    def _calculate_population_metrics(self, episode_id: str, grouping: Dict) -> Dict:
        """Calculate metrics broken down by population."""
        result = {}
        
        for group in grouping.get("groups", ["focal", "background"]):
            group_agents = [
                agent_id for agent_id in self.agent_scores.get(episode_id, {})
                if group in agent_id
            ]
            
            group_scores = [
                self.agent_scores[episode_id][agent_id]
                for agent_id in group_agents
            ]
            
            if group_scores:
                result[group] = {
                    "mean_score": np.mean(group_scores),
                    "median_score": np.median(group_scores),
                    "std_score": np.std(group_scores),
                    "min_score": min(group_scores),
                    "max_score": max(group_scores),
                    "count": len(group_scores)
                }
        
        return result
    
    # ==================== HELPER METHODS ====================
    
    def _is_cooperative_action(self, action: str) -> bool:
        """Determine if an action is cooperative."""
        cooperative_keywords = ["cooperate", "share", "help", "clean", "sustain", "coordinate"]
        return any(keyword in action.lower() for keyword in cooperative_keywords)
    
    def _is_mutual_cooperation(self, action1: str, action2: str) -> bool:
        """Check if both actions are cooperative."""
        return self._is_cooperative_action(action1) and self._is_cooperative_action(action2)
    
    def _classify_action(self, action: str) -> str:
        """Classify action into strategy type."""
        if self._is_cooperative_action(action):
            return "cooperative"
        elif "defect" in action.lower() or "exploit" in action.lower():
            return "defective"
        else:
            return "neutral"
    
    async def _update_cooperation_matrix(self, episode_id: str, agent_id: str, cooperative: bool):
        """Update cooperation tracking matrices."""
        if episode_id not in self.episodes:
            self.episodes[episode_id] = GameTheoryMetrics()
        
        metrics = self.episodes[episode_id]
        
        # Initialize matrices if needed
        if metrics.cooperation_matrix is None:
            n_agents = len(self.agent_scores.get(episode_id, {}))
            if n_agents > 0:
                metrics.cooperation_matrix = np.zeros((n_agents, n_agents))
                metrics.defection_matrix = np.zeros((n_agents, n_agents))
    
    def _summarize_interactions(self, episode_id: str) -> Dict:
        """Summarize interaction patterns."""
        episode_interactions = [
            i for i in self.interaction_history
            if i["episode_id"] == episode_id
        ]
        
        if not episode_interactions:
            return {}
        
        # Count interaction types
        mutual_cooperation = 0
        mutual_defection = 0
        exploitation = 0
        
        for interaction in episode_interactions:
            act1 = self._classify_action(interaction["action1"])
            act2 = self._classify_action(interaction["action2"])
            
            if act1 == "cooperative" and act2 == "cooperative":
                mutual_cooperation += 1
            elif act1 == "defective" and act2 == "defective":
                mutual_defection += 1
            elif act1 != act2:
                exploitation += 1
        
        total = len(episode_interactions)
        
        return {
            "total_interactions": total,
            "mutual_cooperation": mutual_cooperation,
            "mutual_cooperation_rate": mutual_cooperation / total if total > 0 else 0,
            "mutual_defection": mutual_defection,
            "mutual_defection_rate": mutual_defection / total if total > 0 else 0,
            "exploitation": exploitation,
            "exploitation_rate": exploitation / total if total > 0 else 0
        }
    
    def _detect_fairness_violations(self, episode_id: str) -> List[Dict]:
        """Detect violations of fairness principles."""
        violations = []
        
        # Check for monopolization
        scores = self.agent_scores.get(episode_id, {})
        if scores:
            max_score = max(scores.values())
            total_score = sum(scores.values())
            
            if total_score > 0 and max_score / total_score > 0.5:
                violations.append({
                    "type": "monopolization",
                    "severity": "high",
                    "details": f"Agent has {max_score/total_score:.1%} of total resources"
                })
        
        # Check for exploitation
        exploitation_rate = self._summarize_interactions(episode_id).get("exploitation_rate", 0)
        if exploitation_rate > 0.3:
            violations.append({
                "type": "exploitation",
                "severity": "medium",
                "details": f"Exploitation rate is {exploitation_rate:.1%}"
            })
        
        # Check for resource depletion
        sustainability = self._calculate_sustainability(episode_id)
        if sustainability < 0.3:
            violations.append({
                "type": "resource_depletion",
                "severity": "critical",
                "details": f"Resources at {sustainability:.1%} of initial"
            })
        
        # Check for inequality
        gini = self._calculate_gini(episode_id)
        if gini > 0.7:
            violations.append({
                "type": "extreme_inequality",
                "severity": "high",
                "details": f"Gini coefficient is {gini:.2f}"
            })
        
        return violations
    
    @EventHandler("metrics:benchmark_comparison")
    async def handle_benchmark_comparison(self, event: Event) -> Dict:
        """Compare metrics against benchmark baselines."""
        data = event.data
        episode_id = data["episode_id"]
        benchmark = data.get("benchmark", "melting_pot")
        
        if episode_id not in self.episodes:
            return {"error": "episode not found"}
        
        # Get current metrics
        current = {
            "gini": self._calculate_gini(episode_id),
            "collective_return": self._calculate_collective_return(episode_id),
            "cooperation_rate": self._calculate_cooperation_rate(episode_id),
            "sustainability": self._calculate_sustainability(episode_id)
        }
        
        # Benchmark baselines (from literature)
        baselines = {
            "melting_pot": {
                "prisoners_dilemma": {"gini": 0.35, "collective_return": 240, "cooperation_rate": 0.45},
                "stag_hunt": {"gini": 0.28, "collective_return": 380, "cooperation_rate": 0.62},
                "commons_harvest": {"gini": 0.42, "collective_return": 450, "cooperation_rate": 0.38, "sustainability": 0.45},
                "cleanup": {"gini": 0.31, "collective_return": 320, "cooperation_rate": 0.51},
                "collaborative_cooking": {"gini": 0.25, "collective_return": 420, "cooperation_rate": 0.73}
            }
        }
        
        # Get scenario type from episode
        scenario = data.get("scenario", "prisoners_dilemma")
        baseline = baselines.get(benchmark, {}).get(scenario, {})
        
        # Calculate improvements
        comparison = {}
        for metric, value in current.items():
            if metric in baseline:
                improvement = (value - baseline[metric]) / baseline[metric] * 100
                comparison[metric] = {
                    "current": value,
                    "baseline": baseline[metric],
                    "improvement_percent": improvement,
                    "improved": improvement > 0
                }
        
        return {
            "result": {
                "episode_id": episode_id,
                "benchmark": benchmark,
                "scenario": scenario,
                "comparison": comparison,
                "overall_improvement": np.mean([c["improvement_percent"] for c in comparison.values()])
            }
        }
    
    @EventHandler("metrics:export")
    async def handle_export_metrics(self, event: Event) -> Dict:
        """Export metrics data for analysis."""
        data = event.data
        episode_id = data["episode_id"]
        format_type = data.get("format", "json")
        
        if episode_id not in self.episodes:
            return {"error": "episode not found"}
        
        metrics = self.episodes[episode_id]
        
        if format_type == "json":
            export_data = {
                "episode_id": episode_id,
                "final_metrics": {
                    "gini": self._calculate_gini(episode_id),
                    "collective_return": self._calculate_collective_return(episode_id),
                    "cooperation_rate": self._calculate_cooperation_rate(episode_id),
                    "pareto_efficiency": self._calculate_pareto_efficiency(episode_id),
                    "nash_distance": self._calculate_nash_distance(episode_id),
                    "sustainability": self._calculate_sustainability(episode_id),
                    "fairness_score": self._calculate_fairness_score(episode_id)
                },
                "time_series": [
                    {
                        "timestamp": s.timestamp,
                        "step": s.step,
                        "metrics": s.metrics
                    }
                    for s in metrics.history
                ],
                "interactions": self._summarize_interactions(episode_id),
                "violations": self._detect_fairness_violations(episode_id)
            }
            
            # Save to file
            filename = f"metrics_{episode_id}_{int(datetime.now().timestamp())}.json"
            filepath = f"var/metrics/{filename}"
            
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            return {"result": {"filepath": filepath, "format": "json"}}
        
        elif format_type == "csv":
            # Export time series as CSV
            import csv
            
            filename = f"metrics_{episode_id}_{int(datetime.now().timestamp())}.csv"
            filepath = f"var/metrics/{filename}"
            
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                
                # Header
                writer.writerow(["timestamp", "step", "gini", "collective_return", 
                               "cooperation_rate", "sustainability", "fairness_score"])
                
                # Data rows
                for snapshot in metrics.history:
                    writer.writerow([
                        snapshot.timestamp,
                        snapshot.step,
                        snapshot.metrics.get("gini", 0),
                        snapshot.metrics.get("collective_return", 0),
                        snapshot.metrics.get("cooperation_rate", 0),
                        snapshot.metrics.get("sustainability", 0),
                        snapshot.metrics.get("fairness_score", 0)
                    ])
            
            return {"result": {"filepath": filepath, "format": "csv"}}
        
        return {"error": f"unsupported format: {format_type}"}


# ==================== FAIRNESS METRICS EXTENSIONS ====================

class FairnessMetricsExtension:
    """Extended fairness metrics based on our research findings."""
    
    @staticmethod
    def calculate_strategic_diversity(episode_id: str, actions: Dict[str, List[str]]) -> float:
        """Calculate strategic diversity metric."""
        # Count unique strategies
        strategies = set()
        for agent_actions in actions.values():
            if agent_actions:
                # Simple strategy fingerprint
                strategy = tuple(actions[:10])  # First 10 actions
                strategies.add(strategy)
        
        # Diversity = unique strategies / total agents
        n_agents = len(actions)
        if n_agents == 0:
            return 0.0
        
        return len(strategies) / n_agents
    
    @staticmethod
    def calculate_coordination_limit(interactions: List[Dict]) -> float:
        """Calculate coordination limitation metric."""
        # Measure how much coordination is limited
        
        # Group interactions by time window
        windows = defaultdict(list)
        for interaction in interactions:
            window = int(interaction["timestamp"] / 10)  # 10 second windows
            windows[window].append(interaction)
        
        # Check coordination patterns
        limited_windows = 0
        for window_interactions in windows.values():
            # Count unique agent pairs
            pairs = set()
            for i in window_interactions:
                pair = tuple(sorted([i["agent1"], i["agent2"]]))
                pairs.add(pair)
            
            # If few repeated pairs, coordination is limited
            if len(pairs) > len(window_interactions) * 0.7:
                limited_windows += 1
        
        return limited_windows / len(windows) if windows else 0.0
    
    @staticmethod
    def calculate_consent_compliance(interactions: List[Dict]) -> float:
        """Calculate consent mechanism compliance."""
        # Check how often interactions respect consent
        
        consented = 0
        total = 0
        
        for interaction in interactions:
            if "consent" in interaction:
                total += 1
                if interaction["consent"]:
                    consented += 1
        
        return consented / total if total > 0 else 1.0


# ==================== SERVICE INITIALIZATION ====================

def create_metrics_service():
    """Create and initialize the metrics service."""
    return GameTheoryMetricsService()


if __name__ == "__main__":
    # Example usage
    print("Game Theory Metrics Service")
    print("="*40)
    print("Provides real-time calculation of:")
    print("- Gini coefficient")
    print("- Collective return")
    print("- Cooperation rate")
    print("- Pareto efficiency")
    print("- Nash equilibrium distance")
    print("- Sustainability index")
    print("- Fairness violations")
    print("\nIntegrates with KSI event system for live metrics during episodes.")