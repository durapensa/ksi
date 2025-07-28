#!/usr/bin/env python3
"""
Routing Introspection Integration

Enhances routing system with introspection capabilities to provide visibility
into routing decisions, transformations, and event flow.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import event_handler, get_router
from ksi_common.event_response_builder import event_response_builder, error_response

logger = get_bound_logger("routing_introspection", version="1.0.0")

# Global tracking for routing decisions
_routing_decisions: Dict[str, Dict[str, Any]] = {}
_decision_limit = 1000  # Keep last N decisions


def track_routing_decision(
    event_id: str,
    event_name: str,
    rules_evaluated: List[Dict[str, Any]],
    rules_matched: List[Dict[str, Any]],
    rule_applied: Optional[Dict[str, Any]],
    transformation_applied: Optional[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Track a routing decision for introspection.
    
    Args:
        event_id: Original event ID
        event_name: Event name being routed
        rules_evaluated: All rules that were checked
        rules_matched: Rules that matched the pattern
        rule_applied: The winning rule (highest priority)
        transformation_applied: Any data transformation applied
        context: Event context
        
    Returns:
        Decision ID for reference
    """
    decision_id = f"routing_decision_{datetime.utcnow().timestamp()}"
    
    decision = {
        "decision_id": decision_id,
        "timestamp": datetime.utcnow().isoformat(),
        "event_id": event_id,
        "event_name": event_name,
        "rules_evaluated": len(rules_evaluated),
        "rules_matched": len(rules_matched),
        "rule_applied": rule_applied.get("rule_id") if rule_applied else None,
        "routing_path": _build_routing_path(event_name, rule_applied),
        "details": {
            "rules_evaluated": rules_evaluated,
            "rules_matched": rules_matched,
            "rule_applied": rule_applied,
            "transformation_applied": transformation_applied
        }
    }
    
    # Store decision with size limit
    _routing_decisions[decision_id] = decision
    
    # Trim old decisions if needed
    if len(_routing_decisions) > _decision_limit:
        oldest_keys = sorted(_routing_decisions.keys())[:len(_routing_decisions) - _decision_limit]
        for key in oldest_keys:
            del _routing_decisions[key]
    
    # Emit introspection event
    asyncio.create_task(_emit_routing_decision_event(decision))
    
    logger.debug(f"Tracked routing decision {decision_id} for {event_name}")
    return decision_id


def _build_routing_path(event_name: str, rule: Optional[Dict[str, Any]]) -> str:
    """Build a human-readable routing path."""
    if not rule:
        return f"{event_name} → (no routing)"
    
    target = rule.get("target", "unknown")
    transformer_name = rule.get("transformer_name", f"rule_{rule.get('rule_id', 'unknown')}")
    
    return f"{event_name} → [{transformer_name}] → {target}"


async def _emit_routing_decision_event(decision: Dict[str, Any]):
    """Emit routing decision as introspection event."""
    try:
        router = get_router()
        await router.emit("introspection:routing_decision", decision)
    except Exception as e:
        logger.error(f"Failed to emit routing decision event: {e}")


def enhance_event_with_routing_metadata(
    event_data: Dict[str, Any],
    routing_decision_id: str,
    rule_applied: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Enhance event data with routing metadata for introspection.
    
    Args:
        event_data: Original event data
        routing_decision_id: ID of the routing decision
        rule_applied: The routing rule that was applied
        
    Returns:
        Enhanced event data with routing metadata
    """
    # Ensure _ksi_routing exists in the data
    if "_ksi_routing" not in event_data:
        event_data["_ksi_routing"] = {}
    
    # Add routing metadata
    event_data["_ksi_routing"].update({
        "decision_id": routing_decision_id,
        "rule_id": rule_applied.get("rule_id") if rule_applied else None,
        "source_pattern": rule_applied.get("source_pattern") if rule_applied else None,
        "transformation_type": "dynamic" if rule_applied else "static",
        "routed_at": datetime.utcnow().isoformat()
    })
    
    return event_data


@event_handler("introspection:routing_path")
async def handle_routing_path_query(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Query the routing path for a specific event.
    
    Parameters:
        event_id: Event ID to trace routing for
        decision_id: Routing decision ID to examine
    """
    event_id = data.get("event_id")
    decision_id = data.get("decision_id")
    
    if not event_id and not decision_id:
        return error_response(
            "Must provide either event_id or decision_id",
            context
        )
    
    # Find routing decision
    if decision_id:
        decision = _routing_decisions.get(decision_id)
    else:
        # Search by event_id
        decision = None
        for dec_id, dec in _routing_decisions.items():
            if dec.get("event_id") == event_id:
                decision = dec
                break
    
    if not decision:
        return error_response(
            "Routing decision not found",
            context
        )
    
    # Build detailed routing path
    path_details = _build_detailed_routing_path(decision)
    
    return event_response_builder({
        "routing_path": path_details,
        "decision": decision
    }, context)


def _build_detailed_routing_path(decision: Dict[str, Any]) -> Dict[str, Any]:
    """Build detailed routing path information."""
    rule = decision["details"].get("rule_applied")
    
    return {
        "source": {
            "event": decision["event_name"],
            "event_id": decision["event_id"]
        },
        "routing": {
            "rule_id": rule.get("rule_id") if rule else None,
            "pattern": rule.get("source_pattern") if rule else None,
            "priority": rule.get("priority") if rule else None,
            "condition": rule.get("condition") if rule else None
        },
        "transformation": decision["details"].get("transformation_applied"),
        "target": {
            "event": rule.get("target") if rule else None,
            "routed": rule is not None
        },
        "metadata": {
            "decision_id": decision["decision_id"],
            "timestamp": decision["timestamp"],
            "rules_evaluated": decision["rules_evaluated"],
            "rules_matched": decision["rules_matched"]
        }
    }


@event_handler("introspection:routing_impact")
async def handle_routing_impact_analysis(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Analyze the potential impact of a routing rule change.
    
    Parameters:
        rule_id: Rule to analyze
        event_patterns: List of event patterns to check impact for
        time_window: Time window in seconds to analyze (default: 300)
    """
    rule_id = data.get("rule_id")
    event_patterns = data.get("event_patterns", ["*"])
    time_window = data.get("time_window", 300)
    
    if not rule_id:
        return error_response(
            "rule_id is required",
            context
        )
    
    # Get routing service to fetch rule
    from .routing_service import get_routing_service
    service = get_routing_service()
    
    if not service:
        return error_response(
            "Routing service not available",
            context
        )
    
    # Get the rule
    rule = service.routing_rules.get(rule_id)
    if not rule:
        return error_response(
            f"Rule {rule_id} not found",
            context
        )
    
    # Analyze recent routing decisions
    impact_analysis = await _analyze_routing_impact(rule, event_patterns, time_window)
    
    return event_response_builder({
        "rule_id": rule_id,
        "rule": rule,
        "impact_analysis": impact_analysis
    }, context)


async def _analyze_routing_impact(rule: Dict[str, Any], event_patterns: List[str], time_window: int) -> Dict[str, Any]:
    """Analyze the impact of a routing rule on recent events."""
    from fnmatch import fnmatch
    
    affected_events = []
    pattern = rule.get("source_pattern", "")
    
    # Check recent routing decisions
    current_time = datetime.utcnow()
    for decision in _routing_decisions.values():
        # Check time window
        try:
            decision_time = datetime.fromisoformat(decision["timestamp"].replace('Z', '+00:00'))
        except:
            # If timestamp parsing fails, skip
            continue
            
        # Ensure time_window is numeric
        try:
            time_window_seconds = float(time_window)
        except (ValueError, TypeError):
            time_window_seconds = 300.0
            
        if (current_time - decision_time).total_seconds() > time_window_seconds:
            continue
        
        # Check if this event would be affected
        event_name = decision["event_name"]
        if fnmatch(event_name, pattern):
            # Check if event name matches any of the patterns we're analyzing
            if any(fnmatch(event_name, ep) for ep in event_patterns):
                affected_events.append({
                    "event_name": event_name,
                    "event_id": decision["event_id"],
                    "current_routing": decision["routing_path"],
                    "would_match": True
                })
    
    return {
        "affected_event_count": len(affected_events),
        "affected_events": affected_events[:10],  # Limit to first 10
        "analysis_window": time_window,
        "patterns_analyzed": event_patterns
    }


@event_handler("introspection:routing_decisions")
async def handle_routing_decisions_query(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Query recent routing decisions.
    
    Parameters:
        limit: Maximum number of decisions to return
        event_name: Filter by event name
        rule_id: Filter by rule ID
    """
    limit = data.get("limit", 50)
    # Ensure limit is an integer
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = 50
        
    event_name = data.get("event_name")
    rule_id = data.get("rule_id")
    
    # Filter decisions
    decisions = []
    for decision in _routing_decisions.values():
        # Apply filters
        if event_name and decision["event_name"] != event_name:
            continue
        if rule_id and decision.get("rule_applied") != rule_id:
            continue
        
        decisions.append(decision)
    
    # Sort by timestamp descending
    decisions.sort(key=lambda d: d["timestamp"], reverse=True)
    
    # Apply limit
    decisions = decisions[:limit]
    
    return event_response_builder({
        "decisions": decisions,
        "count": len(decisions),
        "total_tracked": len(_routing_decisions)
    }, context)


# Export for use in routing service
__all__ = [
    "track_routing_decision",
    "enhance_event_with_routing_metadata",
    "handle_routing_path_query",
    "handle_routing_impact_analysis",
    "handle_routing_decisions_query"
]