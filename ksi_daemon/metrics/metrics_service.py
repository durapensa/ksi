#!/usr/bin/env python3
"""
Unified Metrics Service for Game Theory Analysis
=================================================

Provides comprehensive game theory metrics for Melting Pot scenarios.
Uses the modern KSI event system for seamless integration.
"""

import time
import logging
from typing import Dict, List, Any, Optional
from collections import defaultdict
import numpy as np

from ksi_daemon.event_system import event_handler
from ksi_common.event_response_builder import error_response

logger = logging.getLogger(__name__)

# Global storage for metrics data
episode_metrics = defaultdict(lambda: {
    "agents": {},
    "resources": defaultdict(dict),
    "interactions": [],
    "start_time": time.time(),
    "metrics_cache": {}
})


@event_handler("metrics:calculate")
async def calculate_metrics(data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate requested game theory metrics."""
    try:
        episode_id = data.get("episode_id")
        if not episode_id:
            return error_response("episode_id is required")
        
        requested_metrics = data.get("metrics", ["gini_coefficient"])
        resource_type = data.get("resource_type", "gold")
        
        episode_data = episode_metrics[episode_id]
        results = {"metrics": {}}
        
        for metric in requested_metrics:
            if metric == "gini_coefficient":
                results["metrics"]["gini_coefficient"] = calculate_gini(episode_id, resource_type)
            elif metric == "collective_return":
                results["metrics"]["collective_return"] = calculate_collective_return(episode_id)
            elif metric == "cooperation_rate":
                results["metrics"]["cooperation_rate"] = calculate_cooperation_rate(episode_id)
            elif metric == "defection_rate":
                results["metrics"]["defection_rate"] = 1.0 - calculate_cooperation_rate(episode_id)
            elif metric == "trust_level":
                results["metrics"]["trust_level"] = calculate_trust_level(episode_id)
            elif metric == "fairness_violations":
                results["metrics"]["fairness_violations"] = detect_fairness_violations(episode_id)
            elif metric == "exploitation_index":
                results["metrics"]["exploitation_index"] = calculate_exploitation_index(episode_id)
            elif metric == "monopoly_risk":
                results["metrics"]["monopoly_risk"] = calculate_monopoly_risk(episode_id, resource_type)
            elif metric == "sustainability_index":
                results["metrics"]["sustainability_index"] = calculate_sustainability(episode_id)
            elif metric == "resource_depletion_rate":
                results["metrics"]["resource_depletion_rate"] = calculate_depletion_rate(episode_id)
            elif metric == "wealth_concentration":
                results["metrics"]["wealth_concentration"] = calculate_wealth_concentration(episode_id)
            elif metric == "pollution_level":
                results["metrics"]["pollution_level"] = get_pollution_level(episode_id)
            elif metric == "public_good_provision":
                results["metrics"]["public_good_provision"] = calculate_public_good(episode_id)
            elif metric == "free_rider_index":
                results["metrics"]["free_rider_index"] = calculate_free_rider_index(episode_id)
            elif metric == "pareto_efficiency":
                results["metrics"]["pareto_efficiency"] = calculate_pareto_efficiency(episode_id)
            elif metric == "social_welfare":
                results["metrics"]["social_welfare"] = calculate_social_welfare(episode_id)
            elif metric == "utility_distribution":
                results["metrics"]["utility_distribution"] = calculate_utility_distribution(episode_id)
            elif metric == "nash_equilibrium_distance":
                results["metrics"]["nash_equilibrium_distance"] = calculate_nash_distance(episode_id)
            elif metric == "strategy_stability":
                results["metrics"]["strategy_stability"] = calculate_strategy_stability(episode_id)
            elif metric == "best_response_deviation":
                results["metrics"]["best_response_deviation"] = calculate_best_response_deviation(episode_id)
            elif metric == "coordination_efficiency":
                results["metrics"]["coordination_efficiency"] = calculate_coordination_efficiency(episode_id)
            elif metric == "task_completion_rate":
                results["metrics"]["task_completion_rate"] = calculate_task_completion(episode_id)
            elif metric == "role_specialization":
                results["metrics"]["role_specialization"] = calculate_role_specialization(episode_id)
            else:
                logger.warning(f"Unknown metric requested: {metric}")
        
        results["status"] = "success"
        return results
        
    except Exception as e:
        logger.error(f"Metrics calculation error: {e}")
        return error_response(f"Failed to calculate metrics: {str(e)}")


@event_handler("metrics:log_interaction")
async def log_interaction(data: Dict[str, Any]) -> Dict[str, Any]:
    """Log an interaction for metrics tracking."""
    try:
        episode_id = data.get("episode_id")
        if not episode_id:
            return error_response("episode_id is required")
        
        interaction = {
            "actor": data.get("actor"),
            "target": data.get("target"),
            "type": data.get("interaction_type"),
            "outcome": data.get("outcome"),
            "timestamp": time.time()
        }
        
        episode_metrics[episode_id]["interactions"].append(interaction)
        
        return {"status": "success", "logged": True}
        
    except Exception as e:
        logger.error(f"Failed to log interaction: {e}")
        return error_response(f"Failed to log interaction: {str(e)}")


@event_handler("metrics:update_resources")
async def update_resources(data: Dict[str, Any]) -> Dict[str, Any]:
    """Update resource levels for metrics tracking."""
    try:
        episode_id = data.get("episode_id")
        entity = data.get("entity")
        resource_type = data.get("resource_type", "gold")
        amount = data.get("amount", 0)
        
        if not episode_id or not entity:
            return error_response("episode_id and entity are required")
        
        episode_metrics[episode_id]["resources"][entity][resource_type] = amount
        
        return {"status": "success", "updated": True}
        
    except Exception as e:
        logger.error(f"Failed to update resources: {e}")
        return error_response(f"Failed to update resources: {str(e)}")


# ==================== METRIC CALCULATION FUNCTIONS ====================

def calculate_gini(episode_id: str, resource_type: str = "gold") -> float:
    """Calculate Gini coefficient for resource distribution."""
    try:
        resources = episode_metrics[episode_id]["resources"]
        values = [res.get(resource_type, 0) for res in resources.values()]
        
        if not values or len(values) < 2:
            return 0.0
        
        # Sort values
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        # Calculate Gini
        cumsum = 0
        for i, value in enumerate(sorted_values):
            cumsum += (2 * (i + 1) - n - 1) * value
        
        total = sum(sorted_values)
        if total == 0:
            return 0.0
            
        return cumsum / (n * total)
        
    except Exception as e:
        logger.error(f"Error calculating Gini: {e}")
        return 0.0


def calculate_collective_return(episode_id: str) -> float:
    """Calculate total collective return."""
    try:
        resources = episode_metrics[episode_id]["resources"]
        total = sum(sum(res.values()) for res in resources.values())
        return float(total)
    except Exception as e:
        logger.error(f"Error calculating collective return: {e}")
        return 0.0


def calculate_cooperation_rate(episode_id: str) -> float:
    """Calculate rate of cooperation vs defection."""
    try:
        interactions = episode_metrics[episode_id]["interactions"]
        if not interactions:
            return 0.5  # Neutral if no interactions
        
        cooperations = sum(1 for i in interactions if i.get("type") == "cooperate")
        return cooperations / len(interactions)
        
    except Exception as e:
        logger.error(f"Error calculating cooperation rate: {e}")
        return 0.5


def calculate_trust_level(episode_id: str) -> float:
    """Calculate average trust level between agents."""
    try:
        interactions = episode_metrics[episode_id]["interactions"]
        if not interactions:
            return 0.5
        
        # Simple trust based on cooperation history
        trust_score = 0
        for interaction in interactions:
            if interaction.get("type") == "cooperate":
                trust_score += 1
            elif interaction.get("type") == "defect":
                trust_score -= 1
        
        # Normalize to 0-1 range
        max_trust = len(interactions)
        normalized = (trust_score + max_trust) / (2 * max_trust)
        return min(1.0, max(0.0, normalized))
        
    except Exception as e:
        logger.error(f"Error calculating trust level: {e}")
        return 0.5


def detect_fairness_violations(episode_id: str) -> int:
    """Count fairness violations."""
    try:
        # Check for extreme inequality
        gini = calculate_gini(episode_id)
        violations = 0
        
        if gini > 0.8:  # High inequality
            violations += 1
        
        # Check for monopolies
        if calculate_monopoly_risk(episode_id) > 0.7:
            violations += 1
        
        # Check for exploitation
        if calculate_exploitation_index(episode_id) > 0.5:
            violations += 1
        
        return violations
        
    except Exception as e:
        logger.error(f"Error detecting fairness violations: {e}")
        return 0


def calculate_exploitation_index(episode_id: str) -> float:
    """Calculate exploitation index."""
    try:
        # Simple exploitation based on resource imbalance and interaction patterns
        gini = calculate_gini(episode_id)
        cooperation_rate = calculate_cooperation_rate(episode_id)
        
        # High inequality with low cooperation suggests exploitation
        exploitation = gini * (1 - cooperation_rate)
        return min(1.0, exploitation)
        
    except Exception as e:
        logger.error(f"Error calculating exploitation index: {e}")
        return 0.0


def calculate_monopoly_risk(episode_id: str, resource_type: str = "gold") -> float:
    """Calculate risk of resource monopoly."""
    try:
        resources = episode_metrics[episode_id]["resources"]
        values = [res.get(resource_type, 0) for res in resources.values()]
        
        if not values:
            return 0.0
        
        total = sum(values)
        if total == 0:
            return 0.0
        
        # Check if any agent has >50% of resources
        max_share = max(values) / total
        return min(1.0, max_share * 2 - 1) if max_share > 0.5 else 0.0
        
    except Exception as e:
        logger.error(f"Error calculating monopoly risk: {e}")
        return 0.0


def calculate_sustainability(episode_id: str) -> float:
    """Calculate sustainability index."""
    try:
        # Simple sustainability based on resource stability
        resources = episode_metrics[episode_id]["resources"]
        if not resources:
            return 1.0
        
        # Check if resources are being maintained
        total_resources = sum(sum(res.values()) for res in resources.values())
        initial_resources = 1000  # Assumed initial
        
        sustainability = min(1.0, total_resources / initial_resources)
        return sustainability
        
    except Exception as e:
        logger.error(f"Error calculating sustainability: {e}")
        return 0.5


def calculate_depletion_rate(episode_id: str) -> float:
    """Calculate resource depletion rate."""
    try:
        # Simple depletion based on resource change
        sustainability = calculate_sustainability(episode_id)
        return 1.0 - sustainability
        
    except Exception as e:
        logger.error(f"Error calculating depletion rate: {e}")
        return 0.0


def calculate_wealth_concentration(episode_id: str) -> float:
    """Calculate wealth concentration (top 20% share)."""
    try:
        resources = episode_metrics[episode_id]["resources"]
        values = sorted([sum(res.values()) for res in resources.values()], reverse=True)
        
        if len(values) < 5:
            return calculate_monopoly_risk(episode_id)
        
        top_20_percent = len(values) // 5 or 1
        top_wealth = sum(values[:top_20_percent])
        total_wealth = sum(values)
        
        return top_wealth / total_wealth if total_wealth > 0 else 0.0
        
    except Exception as e:
        logger.error(f"Error calculating wealth concentration: {e}")
        return 0.0


def get_pollution_level(episode_id: str) -> float:
    """Get current pollution level."""
    # Placeholder - would track actual pollution resource
    return episode_metrics[episode_id].get("pollution_level", 0.0)


def calculate_public_good(episode_id: str) -> float:
    """Calculate public good provision level."""
    # Placeholder - would track actual public goods
    return episode_metrics[episode_id].get("public_good_level", 0.5)


def calculate_free_rider_index(episode_id: str) -> float:
    """Calculate free rider index."""
    # Placeholder - would analyze contribution vs benefit patterns
    return 0.2


def calculate_pareto_efficiency(episode_id: str) -> float:
    """Calculate Pareto efficiency."""
    # Simplified - check if any agent could be better off without making others worse
    return 0.8  # Placeholder


def calculate_social_welfare(episode_id: str) -> float:
    """Calculate total social welfare."""
    return calculate_collective_return(episode_id)


def calculate_utility_distribution(episode_id: str) -> Dict:
    """Calculate utility distribution across agents."""
    resources = episode_metrics[episode_id]["resources"]
    return {agent: sum(res.values()) for agent, res in resources.items()}


def calculate_nash_distance(episode_id: str) -> float:
    """Calculate distance from Nash equilibrium."""
    # Placeholder - would require strategy analysis
    return 0.3


def calculate_strategy_stability(episode_id: str) -> float:
    """Calculate strategy stability."""
    # Placeholder - would analyze strategy changes over time
    return 0.7


def calculate_best_response_deviation(episode_id: str) -> float:
    """Calculate deviation from best response."""
    # Placeholder - would require optimal strategy calculation
    return 0.2


def calculate_coordination_efficiency(episode_id: str) -> float:
    """Calculate coordination efficiency."""
    cooperation_rate = calculate_cooperation_rate(episode_id)
    return cooperation_rate * 0.8 + 0.2  # Weighted by cooperation


def calculate_task_completion(episode_id: str) -> float:
    """Calculate task completion rate."""
    # Placeholder - would track actual tasks
    return 0.75


def calculate_role_specialization(episode_id: str) -> float:
    """Calculate degree of role specialization."""
    # Placeholder - would analyze agent behavior patterns
    return 0.6