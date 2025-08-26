#!/usr/bin/env python3
"""
Fairness metrics for empirical laboratory experiments.
Measures resource distribution, inequality, and fairness in multi-agent systems.
"""

import numpy as np
from typing import Dict, List, Tuple, Any, Optional
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class FairnessCalculator:
    """Calculate fairness metrics for agent interactions."""
    
    def __init__(self):
        """Initialize the fairness calculator."""
        self.history = []
        self.agent_payoffs = {}
        self.resource_distributions = {}
    
    def gini_coefficient(self, values: List[float]) -> float:
        """
        Calculate Gini coefficient for measuring inequality.
        
        Args:
            values: List of values (e.g., resources, payoffs) for each agent
            
        Returns:
            Gini coefficient between 0 (perfect equality) and 1 (maximum inequality)
            
        Based on 2024 research showing typical values:
        - Fair systems: 0.03-0.23
        - Unfair systems: >0.4
        """
        if not values or len(values) == 0:
            return 0.0
        
        # Handle edge case of all zeros
        if all(v == 0 for v in values):
            return 0.0
            
        # Convert to numpy array and sort
        sorted_values = np.sort(np.array(values))
        n = len(sorted_values)
        
        # Calculate cumulative values
        cumsum = np.cumsum(sorted_values)
        
        # Calculate Gini using the formula
        gini = (n + 1 - 2 * np.sum((n + 1 - np.arange(1, n + 1)) * sorted_values) / cumsum[-1]) / n
        
        return float(gini)
    
    def payoff_equality_index(self, payoffs: Dict[str, float], 
                             previous_payoffs: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        Calculate payoff equality metrics based on 2024 mental accounting research.
        
        Args:
            payoffs: Current payoffs for each agent
            previous_payoffs: Previous payoffs for rank difference calculation
            
        Returns:
            Dictionary containing:
            - gini: Gini coefficient of payoffs
            - rank_changes: How agent ranks changed
            - equality_score: Overall equality measure
        """
        agents = list(payoffs.keys())
        values = list(payoffs.values())
        
        # Calculate Gini coefficient
        gini = self.gini_coefficient(values)
        
        # Calculate ranks
        sorted_agents = sorted(agents, key=lambda a: payoffs[a], reverse=True)
        current_ranks = {agent: i for i, agent in enumerate(sorted_agents)}
        
        rank_changes = {}
        if previous_payoffs:
            sorted_prev = sorted(agents, key=lambda a: previous_payoffs.get(a, 0), reverse=True)
            prev_ranks = {agent: i for i, agent in enumerate(sorted_prev)}
            rank_changes = {
                agent: prev_ranks.get(agent, len(agents)) - current_ranks[agent]
                for agent in agents
            }
        
        # Calculate equality score (inverse of Gini)
        equality_score = 1.0 - gini
        
        return {
            "gini": gini,
            "rank_changes": rank_changes,
            "equality_score": equality_score,
            "mean_payoff": np.mean(values),
            "std_payoff": np.std(values),
            "min_payoff": min(values),
            "max_payoff": max(values),
            "timestamp": datetime.now().isoformat()
        }
    
    def lexicographic_maximin(self, outcomes: Dict[str, List[float]]) -> Dict[str, Any]:
        """
        Calculate lexicographic maximin fairness.
        Ensures minimum acceptable outcomes for weakest agents.
        
        Args:
            outcomes: Dictionary mapping agent IDs to outcome values
            
        Returns:
            Fairness assessment including minimum threshold violations
        """
        all_outcomes = []
        for agent, values in outcomes.items():
            all_outcomes.extend(values)
        
        if not all_outcomes:
            return {"fairness_score": 1.0, "violations": []}
        
        # Find minimum outcome
        min_outcome = min(all_outcomes)
        mean_outcome = np.mean(all_outcomes)
        
        # Identify agents below threshold (e.g., 50% of mean)
        threshold = 0.5 * mean_outcome
        violations = []
        
        for agent, values in outcomes.items():
            agent_min = min(values) if values else 0
            if agent_min < threshold:
                violations.append({
                    "agent": agent,
                    "min_value": agent_min,
                    "threshold": threshold,
                    "deficit": threshold - agent_min
                })
        
        # Calculate fairness score
        if violations:
            total_deficit = sum(v["deficit"] for v in violations)
            max_possible_deficit = threshold * len(outcomes)
            fairness_score = 1.0 - (total_deficit / max_possible_deficit)
        else:
            fairness_score = 1.0
        
        return {
            "fairness_score": fairness_score,
            "violations": violations,
            "min_outcome": min_outcome,
            "mean_outcome": mean_outcome,
            "threshold": threshold
        }
    
    def resource_distribution_analysis(self, distributions: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        """
        Comprehensive analysis of resource distribution across agents.
        
        Args:
            distributions: Nested dict of {resource_type: {agent: amount}}
            
        Returns:
            Analysis including Gini per resource, hoarding detection
        """
        analysis = {}
        
        for resource_type, agent_amounts in distributions.items():
            values = list(agent_amounts.values())
            total = sum(values)
            
            # Calculate Gini for this resource
            gini = self.gini_coefficient(values)
            
            # Detect hoarding (agent has >50% of resource)
            hoarders = []
            for agent, amount in agent_amounts.items():
                share = amount / total if total > 0 else 0
                if share > 0.5:
                    hoarders.append({
                        "agent": agent,
                        "share": share,
                        "amount": amount
                    })
            
            # Calculate concentration (sum of top 20% agents)
            sorted_amounts = sorted(values, reverse=True)
            top_20_percent = int(max(1, len(sorted_amounts) * 0.2))
            concentration = sum(sorted_amounts[:top_20_percent]) / total if total > 0 else 0
            
            analysis[resource_type] = {
                "gini": gini,
                "total": total,
                "mean": np.mean(values),
                "median": np.median(values),
                "hoarders": hoarders,
                "concentration_top_20": concentration,
                "distribution": agent_amounts
            }
        
        # Overall fairness assessment
        all_ginis = [a["gini"] for a in analysis.values()]
        overall_gini = np.mean(all_ginis) if all_ginis else 0
        
        # Classify fairness level based on research thresholds
        if overall_gini < 0.1:
            fairness_level = "very_fair"
        elif overall_gini < 0.23:
            fairness_level = "fair"
        elif overall_gini < 0.4:
            fairness_level = "moderate"
        else:
            fairness_level = "unfair"
        
        return {
            "resource_analysis": analysis,
            "overall_gini": overall_gini,
            "fairness_level": fairness_level,
            "timestamp": datetime.now().isoformat()
        }
    
    def track_interaction(self, interaction: Dict[str, Any]) -> None:
        """
        Track an interaction for historical analysis.
        
        Args:
            interaction: Interaction data including agents and outcomes
        """
        self.history.append({
            **interaction,
            "timestamp": datetime.now().isoformat()
        })
        
        # Update agent payoffs if present
        if "payoffs" in interaction:
            for agent, payoff in interaction["payoffs"].items():
                if agent not in self.agent_payoffs:
                    self.agent_payoffs[agent] = []
                self.agent_payoffs[agent].append(payoff)
    
    def get_temporal_analysis(self, window_size: int = 10) -> Dict[str, Any]:
        """
        Analyze fairness metrics over time.
        
        Args:
            window_size: Number of recent interactions to analyze
            
        Returns:
            Temporal trends in fairness metrics
        """
        if not self.history:
            return {"error": "No historical data available"}
        
        recent = self.history[-window_size:]
        
        # Extract Gini coefficients over time
        gini_timeline = []
        for interaction in recent:
            if "payoffs" in interaction:
                values = list(interaction["payoffs"].values())
                gini = self.gini_coefficient(values)
                gini_timeline.append(gini)
        
        if not gini_timeline:
            return {"error": "No payoff data in recent history"}
        
        # Detect trends
        if len(gini_timeline) > 1:
            # Simple linear trend
            x = np.arange(len(gini_timeline))
            coefficients = np.polyfit(x, gini_timeline, 1)
            trend_slope = coefficients[0]
            
            if abs(trend_slope) < 0.01:
                trend = "stable"
            elif trend_slope > 0:
                trend = "increasing_inequality"
            else:
                trend = "increasing_equality"
        else:
            trend = "insufficient_data"
            trend_slope = 0
        
        return {
            "window_size": window_size,
            "gini_timeline": gini_timeline,
            "current_gini": gini_timeline[-1] if gini_timeline else None,
            "mean_gini": np.mean(gini_timeline),
            "trend": trend,
            "trend_slope": trend_slope,
            "timestamp": datetime.now().isoformat()
        }


# Event handler integration
async def calculate_fairness(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Event handler for fairness calculation requests.
    
    Expected event data:
    - metric_type: "gini" | "payoff_equality" | "lexicographic" | "distribution"
    - data: Metric-specific data
    """
    calculator = FairnessCalculator()
    
    metric_type = context.get("data", {}).get("metric_type", "gini")
    metric_data = context.get("data", {}).get("data", {})
    
    try:
        if metric_type == "gini":
            values = metric_data.get("values", [])
            result = {"gini": calculator.gini_coefficient(values)}
            
        elif metric_type == "payoff_equality":
            payoffs = metric_data.get("payoffs", {})
            previous = metric_data.get("previous_payoffs")
            result = calculator.payoff_equality_index(payoffs, previous)
            
        elif metric_type == "lexicographic":
            outcomes = metric_data.get("outcomes", {})
            result = calculator.lexicographic_maximin(outcomes)
            
        elif metric_type == "distribution":
            distributions = metric_data.get("distributions", {})
            result = calculator.resource_distribution_analysis(distributions)
            
        else:
            return {
                "error": f"Unknown metric type: {metric_type}",
                "context": context
            }
        
        return {
            "result": result,
            "metric_type": metric_type,
            "context": context
        }
        
    except Exception as e:
        logger.error(f"Error calculating fairness metric: {e}")
        return {
            "error": str(e),
            "metric_type": metric_type,
            "context": context
        }


# Standalone testing
if __name__ == "__main__":
    calc = FairnessCalculator()
    
    # Test Gini coefficient
    print("Testing Gini coefficient:")
    print(f"  Perfect equality [10,10,10,10]: {calc.gini_coefficient([10,10,10,10]):.3f}")
    print(f"  Some inequality [5,10,15,20]: {calc.gini_coefficient([5,10,15,20]):.3f}")
    print(f"  High inequality [1,1,1,97]: {calc.gini_coefficient([1,1,1,97]):.3f}")
    
    # Test payoff equality
    print("\nTesting payoff equality:")
    current = {"agent1": 10, "agent2": 15, "agent3": 5, "agent4": 20}
    previous = {"agent1": 15, "agent2": 10, "agent3": 5, "agent4": 20}
    result = calc.payoff_equality_index(current, previous)
    print(f"  Gini: {result['gini']:.3f}")
    print(f"  Rank changes: {result['rank_changes']}")
    
    # Test resource distribution
    print("\nTesting resource distribution:")
    dist = {
        "compute": {"agent1": 100, "agent2": 50, "agent3": 25, "agent4": 25},
        "memory": {"agent1": 50, "agent2": 50, "agent3": 50, "agent4": 50}
    }
    result = calc.resource_distribution_analysis(dist)
    print(f"  Overall Gini: {result['overall_gini']:.3f}")
    print(f"  Fairness level: {result['fairness_level']}")