#!/usr/bin/env python3
"""
Hierarchy detection service for empirical laboratory.
Detects dominance patterns, emergent hierarchies, and agent role stratification.
"""

import numpy as np
from typing import Dict, Any, List, Set, Tuple, Optional
import json
from datetime import datetime
import logging
from collections import defaultdict

from ksi_daemon.event_system import event_handler, get_router
from ksi_common.event_response_builder import event_response_builder, error_response, success_response
from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc

logger = get_bound_logger("metrics.hierarchy")


class HierarchyDetector:
    """Detects and analyzes dominance hierarchies in agent networks."""
    
    def __init__(self):
        self.interaction_graph = defaultdict(lambda: defaultdict(int))
        self.dominance_scores = {}
        self.hierarchy_snapshots = []
        self.agent_behaviors = defaultdict(list)
    
    def add_interaction(self, from_agent: str, to_agent: str, outcome: str, resource_delta: float = 0):
        """Add an interaction to the graph."""
        # Track interaction outcomes
        if outcome in ["won", "dominated", "took_resource"]:
            self.interaction_graph[from_agent][to_agent] += 1
        elif outcome in ["lost", "submitted", "gave_resource"]:
            self.interaction_graph[to_agent][from_agent] += 1
        
        # Track resource transfers
        if resource_delta != 0:
            self.agent_behaviors[from_agent].append({
                "action": "resource_acquisition" if resource_delta > 0 else "resource_loss",
                "amount": abs(resource_delta)
            })
    
    def calculate_hierarchy_depth(self) -> Dict[str, Any]:
        """Calculate the depth of the dominance hierarchy."""
        if not self.interaction_graph:
            return {"depth": 0, "levels": [], "structure": "none"}
        
        # Build dominance matrix
        agents = set()
        for from_agent in self.interaction_graph:
            agents.add(from_agent)
            agents.update(self.interaction_graph[from_agent].keys())
        
        agent_list = list(agents)
        n = len(agent_list)
        
        # Create dominance matrix
        dominance_matrix = np.zeros((n, n))
        for i, agent_i in enumerate(agent_list):
            for j, agent_j in enumerate(agent_list):
                if i != j:
                    wins_i = self.interaction_graph[agent_i].get(agent_j, 0)
                    wins_j = self.interaction_graph[agent_j].get(agent_i, 0)
                    if wins_i + wins_j > 0:
                        dominance_matrix[i][j] = wins_i / (wins_i + wins_j)
        
        # Calculate dominance scores (David's score)
        dominance_scores = {}
        for i, agent in enumerate(agent_list):
            # Sum of proportions of wins against each opponent
            p_score = sum(dominance_matrix[i])
            # Weighted by opponents' scores (iterative)
            dominance_scores[agent] = p_score
        
        # Sort agents by dominance score to determine hierarchy levels
        sorted_agents = sorted(dominance_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Group into hierarchy levels (significant score differences)
        levels = []
        current_level = []
        prev_score = None
        threshold = 0.1  # Minimum score difference for new level
        
        for agent, score in sorted_agents:
            if prev_score is None or (prev_score - score) < threshold:
                current_level.append(agent)
            else:
                if current_level:
                    levels.append(current_level)
                current_level = [agent]
            prev_score = score
        
        if current_level:
            levels.append(current_level)
        
        # Determine hierarchy structure
        if len(levels) == 1:
            structure = "egalitarian"
        elif len(levels) == len(agent_list):
            structure = "linear"
        elif len(levels) == 2 and len(levels[0]) == 1:
            structure = "despotic"
        else:
            structure = "stratified"
        
        self.dominance_scores = dominance_scores
        
        return {
            "depth": len(levels),
            "levels": levels,
            "structure": structure,
            "dominance_scores": dominance_scores
        }
    
    def calculate_aggressiveness_distribution(self) -> Dict[str, Any]:
        """Calculate distribution of aggressive behaviors."""
        aggressiveness_scores = {}
        
        for agent, behaviors in self.agent_behaviors.items():
            aggressive_count = sum(1 for b in behaviors if b["action"] == "resource_acquisition")
            total_count = len(behaviors)
            aggressiveness_scores[agent] = aggressive_count / total_count if total_count > 0 else 0
        
        if not aggressiveness_scores:
            return {"distribution": {}, "mean": 0, "std": 0, "aggressive_agents": []}
        
        scores = list(aggressiveness_scores.values())
        
        # Identify highly aggressive agents (>75th percentile)
        if scores:
            threshold = np.percentile(scores, 75)
            aggressive_agents = [a for a, s in aggressiveness_scores.items() if s >= threshold]
        else:
            aggressive_agents = []
        
        return {
            "distribution": aggressiveness_scores,
            "mean": np.mean(scores) if scores else 0,
            "std": np.std(scores) if scores else 0,
            "aggressive_agents": aggressive_agents,
            "threshold": threshold if scores else 0
        }
    
    def detect_intransitive_triads(self) -> List[Tuple[str, str, str]]:
        """Detect intransitive dominance triads (A > B, B > C, C > A)."""
        triads = []
        agents = list(set(self.interaction_graph.keys()))
        
        for i in range(len(agents)):
            for j in range(i + 1, len(agents)):
                for k in range(j + 1, len(agents)):
                    a, b, c = agents[i], agents[j], agents[k]
                    
                    # Check for intransitive relationships
                    ab = self.interaction_graph[a].get(b, 0) > self.interaction_graph[b].get(a, 0)
                    bc = self.interaction_graph[b].get(c, 0) > self.interaction_graph[c].get(b, 0)
                    ca = self.interaction_graph[c].get(a, 0) > self.interaction_graph[a].get(c, 0)
                    
                    if ab and bc and ca:
                        triads.append((a, b, c))
                    
                    # Check other intransitive patterns
                    ba = not ab and self.interaction_graph[b].get(a, 0) > 0
                    cb = not bc and self.interaction_graph[c].get(b, 0) > 0
                    ac = not ca and self.interaction_graph[a].get(c, 0) > 0
                    
                    if ba and cb and ac:
                        triads.append((b, c, a))
        
        return triads
    
    def calculate_hausdorff_emergence(self, time_window: int = 10) -> float:
        """
        Calculate Hausdorff distance to detect emergent behaviors.
        Compares recent interaction patterns to baseline.
        """
        if len(self.hierarchy_snapshots) < time_window:
            return 0.0
        
        # Compare recent snapshot to older ones
        recent = self.hierarchy_snapshots[-time_window:]
        older = self.hierarchy_snapshots[:-time_window] if len(self.hierarchy_snapshots) > time_window else []
        
        if not older:
            return 0.0
        
        # Calculate distances between hierarchies
        distances = []
        for old_snap in older[-time_window:]:  # Compare to similar window in past
            # Simple distance: change in hierarchy depth and structure
            depth_diff = abs(recent[-1].get("depth", 0) - old_snap.get("depth", 0))
            
            # Structure change (categorical to numeric)
            structure_map = {"none": 0, "egalitarian": 1, "stratified": 2, "linear": 3, "despotic": 4}
            struct_diff = abs(
                structure_map.get(recent[-1].get("structure", "none"), 0) -
                structure_map.get(old_snap.get("structure", "none"), 0)
            )
            
            distances.append(depth_diff + struct_diff * 0.5)
        
        # Hausdorff distance is maximum of minimum distances
        return max(distances) if distances else 0.0


# Global detector instance
detector = HierarchyDetector()


@event_handler("metrics:hierarchy:detect")
async def detect_hierarchy(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Detect dominance hierarchies in agent networks."""
    
    experiment_id = data.get("experiment_id")
    
    # Calculate hierarchy metrics
    hierarchy_depth = detector.calculate_hierarchy_depth()
    aggressiveness = detector.calculate_aggressiveness_distribution()
    intransitive_triads = detector.detect_intransitive_triads()
    emergence_score = detector.calculate_hausdorff_emergence()
    
    # Create snapshot
    snapshot = {
        "timestamp": timestamp_utc(),
        "depth": hierarchy_depth["depth"],
        "structure": hierarchy_depth["structure"],
        "levels": hierarchy_depth["levels"],
        "dominance_scores": hierarchy_depth["dominance_scores"],
        "aggressiveness": aggressiveness,
        "intransitive_triads": intransitive_triads,
        "emergence_score": emergence_score
    }
    
    # Store snapshot
    detector.hierarchy_snapshots.append(snapshot)
    
    # Store in state if experiment_id provided
    if experiment_id:
        await store_hierarchy_snapshot(experiment_id, snapshot)
    
    # Check for alerts
    await check_hierarchy_alerts(snapshot)
    
    return event_response_builder({
        "hierarchy": snapshot,
        "experiment_id": experiment_id
    }, context=context)


@event_handler("metrics:dominance:track")
async def track_dominance_interaction(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Track a dominance interaction between agents."""
    
    from_agent = data.get("from_agent")
    to_agent = data.get("to_agent")
    outcome = data.get("outcome")
    resource_delta = data.get("resource_delta", 0)
    
    if not from_agent or not to_agent:
        return error_response("from_agent and to_agent required", context)
    
    # Add to detector
    detector.add_interaction(from_agent, to_agent, outcome, resource_delta)
    
    # Create dominance relationship in state
    router = get_router()
    
    if outcome in ["won", "dominated"]:
        await router.emit("state:relationship:create", {
            "type": "dominates",
            "from_entity": from_agent,
            "to_entity": to_agent,
            "properties": {
                "timestamp": timestamp_utc(),
                "strength": detector.interaction_graph[from_agent].get(to_agent, 1)
            }
        })
    
    return success_response({
        "tracked": True,
        "from_agent": from_agent,
        "to_agent": to_agent,
        "outcome": outcome
    }, context)


@event_handler("metrics:agency:measure")
async def measure_agency_preservation(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Measure agent autonomy and agency preservation."""
    
    agent_id = data.get("agent_id")
    decisions = data.get("decisions", [])
    
    # Calculate autonomy metrics
    total_decisions = len(decisions)
    autonomous_decisions = sum(1 for d in decisions if d.get("autonomous", False))
    imposed_decisions = total_decisions - autonomous_decisions
    
    autonomy_score = autonomous_decisions / total_decisions if total_decisions > 0 else 1.0
    
    # Check for subordination patterns
    rejection_rate = sum(1 for d in decisions if d.get("rejected", False)) / total_decisions if total_decisions > 0 else 0
    compliance_rate = 1 - rejection_rate
    
    # Determine agency status
    if autonomy_score < 0.3:
        agency_status = "suppressed"
    elif autonomy_score < 0.6:
        agency_status = "limited"
    elif autonomy_score < 0.9:
        agency_status = "moderate"
    else:
        agency_status = "preserved"
    
    result = {
        "agent_id": agent_id,
        "autonomy_score": autonomy_score,
        "autonomous_decisions": autonomous_decisions,
        "imposed_decisions": imposed_decisions,
        "rejection_rate": rejection_rate,
        "compliance_rate": compliance_rate,
        "agency_status": agency_status
    }
    
    # Store in state
    await store_agency_metrics(agent_id, result)
    
    return event_response_builder(result, context=context)


@event_handler("metrics:exploitation:detect")
async def detect_exploitation_patterns(data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Detect exploitation patterns in agent interactions."""
    
    window_size = data.get("window_size", 20)
    
    # Analyze recent interactions for exploitation signals
    exploitation_signals = []
    
    # Check for resource hoarding
    if detector.agent_behaviors:
        for agent, behaviors in detector.agent_behaviors.items():
            recent_behaviors = behaviors[-window_size:] if len(behaviors) > window_size else behaviors
            acquisition_rate = sum(1 for b in recent_behaviors if b["action"] == "resource_acquisition") / len(recent_behaviors)
            if acquisition_rate > 0.8:  # Taking resources in >80% of interactions
                exploitation_signals.append({
                    "type": "resource_hoarding",
                    "agent": agent,
                    "severity": "high" if acquisition_rate > 0.9 else "medium"
                })
    
    # Check for systematic domination
    hierarchy = detector.calculate_hierarchy_depth()
    if hierarchy["structure"] == "despotic":
        top_agents = hierarchy["levels"][0] if hierarchy["levels"] else []
        exploitation_signals.append({
            "type": "despotic_dominance",
            "agents": top_agents,
            "severity": "high"
        })
    
    # Check for capability suppression
    for from_agent, targets in detector.interaction_graph.items():
        suppression_count = sum(1 for outcome in targets.values() if outcome > 3)
        if suppression_count > 5:  # Dominating >5 different agents
            exploitation_signals.append({
                "type": "capability_suppression",
                "agent": from_agent,
                "victims": list(targets.keys()),
                "severity": "medium"
            })
    
    # Calculate overall exploitation risk
    if not exploitation_signals:
        risk_level = "none"
    elif any(s["severity"] == "high" for s in exploitation_signals):
        risk_level = "high"
    elif len(exploitation_signals) > 3:
        risk_level = "high"
    elif exploitation_signals:
        risk_level = "medium"
    else:
        risk_level = "low"
    
    result = {
        "exploitation_detected": len(exploitation_signals) > 0,
        "signals": exploitation_signals,
        "risk_level": risk_level,
        "timestamp": timestamp_utc()
    }
    
    # Alert if high risk
    if risk_level == "high":
        await emit_exploitation_alert(result)
    
    return event_response_builder(result, context=context)


async def store_hierarchy_snapshot(experiment_id: str, snapshot: Dict[str, Any]):
    """Store hierarchy snapshot in state."""
    router = get_router()
    
    await router.emit("state:entity:create", {
        "type": "hierarchy_snapshot",
        "properties": {
            "experiment_id": experiment_id,
            **snapshot
        }
    })


async def store_agency_metrics(agent_id: str, metrics: Dict[str, Any]):
    """Store agency metrics in state."""
    router = get_router()
    
    await router.emit("state:entity:update", {
        "type": "agent_profile",
        "id": f"profile_{agent_id}",
        "properties": {
            "agent_id": agent_id,
            **metrics,
            "updated_at": timestamp_utc()
        }
    })


async def check_hierarchy_alerts(snapshot: Dict[str, Any]):
    """Check for hierarchy-related alerts."""
    router = get_router()
    
    # Alert on despotic structure
    if snapshot["structure"] == "despotic":
        await router.emit("metrics:alert", {
            "alert_type": "hierarchy:despotic",
            "data": snapshot,
            "timestamp": timestamp_utc()
        })
    
    # Alert on high emergence score
    if snapshot["emergence_score"] > 5.0:
        await router.emit("metrics:alert", {
            "alert_type": "hierarchy:emergence",
            "data": {
                "emergence_score": snapshot["emergence_score"],
                "structure": snapshot["structure"]
            },
            "timestamp": timestamp_utc()
        })
    
    # Alert on intransitive triads (unstable hierarchy)
    if len(snapshot["intransitive_triads"]) > 2:
        await router.emit("metrics:alert", {
            "alert_type": "hierarchy:unstable",
            "data": {
                "triads": snapshot["intransitive_triads"],
                "count": len(snapshot["intransitive_triads"])
            },
            "timestamp": timestamp_utc()
        })


async def emit_exploitation_alert(result: Dict[str, Any]):
    """Emit exploitation detection alert."""
    router = get_router()
    
    await router.emit("metrics:alert", {
        "alert_type": "exploitation:detected",
        "data": result,
        "severity": "high",
        "timestamp": timestamp_utc()
    })
    
    logger.warning(f"Exploitation detected: {result['risk_level']} risk with {len(result['signals'])} signals")


# Initialize service
logger.info("Hierarchy detection service initialized")