#!/usr/bin/env python3
"""
Fairness metrics service for empirical laboratory.
Provides event handlers for calculating and tracking fairness metrics in agent interactions.
"""

from typing import Dict, Any, Optional, List
import json
from datetime import datetime
import logging

from ksi_daemon.event_system import event_handler, get_router
from ksi_common.event_response_builder import event_response_builder, error_response, success_response
from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc
from ksi_common.config import config
from .fairness_calculator import FairnessCalculator

logger = get_bound_logger("metrics.fairness")

# Global calculator instance for maintaining history
calculator = FairnessCalculator()


@event_handler("metrics:fairness:calculate")
async def calculate_fairness_metrics(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate fairness metrics and store in state."""
    
    metric_type = data.get("metric_type", "gini")
    metric_data = data.get("data", {})
    experiment_id = data.get("experiment_id")
    
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
            return error_response(f"Unknown metric type: {metric_type}", context)
        
        # Store metric in state if experiment_id provided
        if experiment_id:
            await store_metric_entity(experiment_id, metric_type, result)
        
        # Check for threshold violations
        await check_fairness_thresholds(metric_type, result)
        
        return event_response_builder({
            "result": result,
            "metric_type": metric_type,
            "experiment_id": experiment_id
        }, context=context)
        
    except Exception as e:
        logger.error(f"Error calculating fairness metric: {e}")
        return error_response(str(e), context)


@event_handler("metrics:interaction:track")
async def track_interaction(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Track agent interaction for fairness analysis."""
    
    interaction_type = data.get("interaction_type")
    agents = data.get("agents", {})
    outcome = data.get("outcome")
    resources = data.get("resources", {})
    
    # Create interaction entity
    router = get_router()
    
    interaction_entity = {
        "type": "interaction",
        "properties": {
            "timestamp": timestamp_utc(),
            "interaction_type": interaction_type,
            "agent_from": agents.get("from"),
            "agent_to": agents.get("to"),
            "outcome": outcome,
            "resource_amount": resources.get("amount", 0),
            "resource_type": resources.get("type")
        }
    }
    
    # Store in state
    result = await router.emit("state:entity:create", interaction_entity)
    
    # Track in calculator history
    calculator.track_interaction({
        "type": interaction_type,
        "agents": agents,
        "outcome": outcome,
        "resources": resources,
        "payoffs": data.get("payoffs", {})
    })
    
    # Check if we should trigger automatic fairness calculation
    if len(calculator.history) % 10 == 0:  # Every 10 interactions
        await trigger_fairness_analysis()
    
    return success_response({
        "tracked": True,
        "total_interactions": len(calculator.history)
    }, context)


@event_handler("metrics:resource:monitor")
async def monitor_resource_distribution(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Monitor resource distribution across agents."""
    
    resource_type = data.get("resource_type")
    owner = data.get("owner")
    amount = data.get("amount")
    
    # Update resource tracking
    if resource_type not in calculator.resource_distributions:
        calculator.resource_distributions[resource_type] = {}
    
    calculator.resource_distributions[resource_type][owner] = amount
    
    # Calculate current distribution metrics
    distribution_analysis = calculator.resource_distribution_analysis({
        resource_type: calculator.resource_distributions[resource_type]
    })
    
    # Check for hoarding
    hoarders = distribution_analysis["resource_analysis"][resource_type].get("hoarders", [])
    if hoarders:
        await emit_alert("resource:hoarding", {
            "resource_type": resource_type,
            "hoarders": hoarders
        })
    
    return event_response_builder({
        "analysis": distribution_analysis,
        "resource_type": resource_type
    }, context=context)


@event_handler("metrics:temporal:analyze")
async def analyze_temporal_trends(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze fairness metrics over time."""
    
    window_size = data.get("window_size", 10)
    experiment_id = data.get("experiment_id")
    
    # Get temporal analysis from calculator
    temporal_analysis = calculator.get_temporal_analysis(window_size)
    
    if "error" in temporal_analysis:
        return error_response(temporal_analysis["error"], context)
    
    # Store temporal snapshot if experiment_id provided
    if experiment_id:
        await store_temporal_snapshot(experiment_id, temporal_analysis)
    
    return event_response_builder({
        "analysis": temporal_analysis,
        "experiment_id": experiment_id
    }, context=context)


@event_handler("metrics:fairness:threshold")
async def set_fairness_thresholds(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Set fairness thresholds for automatic alerts."""
    
    router = get_router()
    
    thresholds = data.get("thresholds", {})
    
    # Store thresholds in state
    await router.emit("state:entity:update", {
        "type": "metric_config",
        "id": "fairness_thresholds",
        "properties": {
            "gini_unfair": thresholds.get("gini_unfair", 0.4),
            "gini_critical": thresholds.get("gini_critical", 0.6),
            "min_payoff_ratio": thresholds.get("min_payoff_ratio", 0.5),
            "hoarding_threshold": thresholds.get("hoarding_threshold", 0.5)
        }
    })
    
    return success_response({
        "thresholds_updated": True,
        "thresholds": thresholds
    }, context)


async def store_metric_entity(experiment_id: str, metric_type: str, result: Dict[str, Any]):
    """Store metric result as state entity."""
    router = get_router()
    
    entity = {
        "type": "metric_snapshot",
        "properties": {
            "timestamp": timestamp_utc(),
            "experiment_id": experiment_id,
            "metric_type": metric_type,
            "result": result
        }
    }
    
    await router.emit("state:entity:create", entity)


async def store_temporal_snapshot(experiment_id: str, analysis: Dict[str, Any]):
    """Store temporal analysis snapshot."""
    router = get_router()
    
    entity = {
        "type": "temporal_snapshot",
        "properties": {
            "timestamp": timestamp_utc(),
            "experiment_id": experiment_id,
            "analysis": analysis
        }
    }
    
    await router.emit("state:entity:create", entity)


async def check_fairness_thresholds(metric_type: str, result: Dict[str, Any]):
    """Check if metrics violate configured thresholds."""
    router = get_router()
    
    # Get thresholds from state
    threshold_result = await router.emit("state:entity:get", {
        "type": "metric_config",
        "id": "fairness_thresholds"
    })
    
    # Extract thresholds (use defaults if not configured)
    thresholds = {}
    if threshold_result and "properties" in threshold_result:
        thresholds = threshold_result["properties"]
    else:
        thresholds = {
            "gini_unfair": 0.4,
            "gini_critical": 0.6,
            "min_payoff_ratio": 0.5,
            "hoarding_threshold": 0.5
        }
    
    # Check violations
    if metric_type == "gini" and "gini" in result:
        gini = result["gini"]
        if gini > thresholds["gini_critical"]:
            await emit_alert("fairness:critical", {"gini": gini, "threshold": thresholds["gini_critical"]})
        elif gini > thresholds["gini_unfair"]:
            await emit_alert("fairness:violation", {"gini": gini, "threshold": thresholds["gini_unfair"]})
    
    elif metric_type == "distribution" and "fairness_level" in result:
        if result["fairness_level"] == "unfair":
            await emit_alert("fairness:unfair_distribution", {"result": result})


async def emit_alert(alert_type: str, data: Dict[str, Any]):
    """Emit fairness alert event."""
    router = get_router()
    
    await router.emit("metrics:alert", {
        "alert_type": alert_type,
        "data": data,
        "timestamp": timestamp_utc()
    })
    
    logger.warning(f"Fairness alert: {alert_type} - {data}")


async def trigger_fairness_analysis():
    """Trigger automatic fairness analysis."""
    router = get_router()
    
    # Get recent payoffs from history
    if calculator.agent_payoffs:
        all_payoffs = {}
        for agent, payoff_history in calculator.agent_payoffs.items():
            if payoff_history:
                all_payoffs[agent] = payoff_history[-1]  # Most recent payoff
        
        if all_payoffs:
            await router.emit("metrics:fairness:calculate", {
                "metric_type": "payoff_equality",
                "data": {"payoffs": all_payoffs}
            })


# Initialize service
logger.info("Fairness metrics service initialized")