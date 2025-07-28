#!/usr/bin/env python3
"""
Dynamic Routing Event Handlers

Provides runtime control over event routing rules, enabling agents to modify
routing patterns dynamically instead of relying on static orchestrations.
"""

from typing import Dict, Any, List, Optional, TypedDict
from datetime import datetime
import json
import uuid

from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import event_handler
from ksi_common.event_response_builder import event_response_builder

logger = get_bound_logger("routing_events", version="1.0.0")

# Type definitions for routing structures
class RoutingRule(TypedDict):
    """Structure of a routing rule."""
    rule_id: str
    source_pattern: str
    target: str
    condition: Optional[str]
    mapping: Optional[Dict[str, Any]]
    priority: int
    ttl: Optional[int]  # Time-to-live in seconds
    created_by: str
    created_at: str
    metadata: Optional[Dict[str, Any]]

class RoutingPermission:
    """Permission levels for routing control."""
    NONE = 0  # No routing control
    SELF = 1  # Can modify own routes only
    CHILDREN = 2  # Can modify children's routes
    ORCHESTRATION = 3  # Can modify orchestration routes
    GLOBAL = 4  # Can modify any routes (admin)

# In-memory routing store (will be moved to state system in Stage 1.4)
routing_rules: Dict[str, RoutingRule] = {}
routing_audit_log: List[Dict[str, Any]] = []

@event_handler("routing:add_rule")
async def handle_add_rule(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add a new routing rule to the system.
    
    Parameters:
        rule_id: Unique identifier for the rule
        source_pattern: Event pattern to match (e.g., "analysis:*", "agent:status")
        target: Target event or agent to route to
        condition: Optional condition expression (evaluated by transformer)
        mapping: Optional data transformation mapping
        priority: Rule priority (higher number = higher priority)
        ttl: Optional time-to-live in seconds
        metadata: Optional metadata about the rule
    
    Required capability: routing_control
    """
    # Get agent ID from context
    ksi_context = event_data.get("_ksi_context", {})
    agent_id = ksi_context.get("_agent_id", "system")
    
    # TODO: In Stage 1.3, implement capability checking
    # For now, allow all agents to use routing control
    # if not await capability_check(agent_id, "routing_control"):
    #     return event_response_builder.error_response(
    #         error="Permission denied",
    #         details={"required_capability": "routing_control"}
    #     )
    
    # Extract parameters
    rule_id = event_data.get("rule_id")
    if not rule_id:
        rule_id = f"rule_{uuid.uuid4().hex[:8]}"
    
    source_pattern = event_data.get("source_pattern")
    target = event_data.get("target")
    
    if not source_pattern or not target:
        return event_response_builder.error_response(
            error="Missing required fields",
            details={"required": ["source_pattern", "target"]}
        )
    
    # Check for conflicts
    if rule_id in routing_rules:
        return event_response_builder.error_response(
            error="Rule ID already exists",
            details={"rule_id": rule_id}
        )
    
    # Create rule
    rule = RoutingRule(
        rule_id=rule_id,
        source_pattern=source_pattern,
        target=target,
        condition=event_data.get("condition"),
        mapping=event_data.get("mapping"),
        priority=event_data.get("priority", 100),
        ttl=event_data.get("ttl"),
        created_by=agent_id,
        created_at=datetime.utcnow().isoformat(),
        metadata=event_data.get("metadata")
    )
    
    # Store rule
    routing_rules[rule_id] = rule
    
    # Audit log
    audit_entry = {
        "operation": "add_rule",
        "rule_id": rule_id,
        "agent_id": agent_id,
        "timestamp": datetime.utcnow().isoformat(),
        "rule": rule
    }
    routing_audit_log.append(audit_entry)
    
    logger.info("Routing rule added", rule_id=rule_id, agent_id=agent_id)
    
    # TODO: In Stage 1.2, actually register with transformer system
    
    return event_response_builder.success_response(
        data={
            "rule_id": rule_id,
            "status": "created",
            "rule": rule
        }
    )

@event_handler("routing:modify_rule")
async def handle_modify_rule(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Modify an existing routing rule.
    
    Parameters:
        rule_id: ID of rule to modify
        updates: Dictionary of fields to update
    
    Required capability: routing_control
    """
    # Get agent ID from context
    ksi_context = event_data.get("_ksi_context", {})
    agent_id = ksi_context.get("_agent_id", "system")
    
    # TODO: In Stage 1.3, implement capability checking
    # For now, allow all agents to use routing control
    # if not await capability_check(agent_id, "routing_control"):
    #     return event_response_builder.error_response(
    #         error="Permission denied",
    #         details={"required_capability": "routing_control"}
    #     )
    
    rule_id = event_data.get("rule_id")
    updates = event_data.get("updates", {})
    
    if not rule_id:
        return event_response_builder.error_response(
            error="Missing rule_id"
        )
    
    if rule_id not in routing_rules:
        return event_response_builder.error_response(
            error="Rule not found",
            details={"rule_id": rule_id}
        )
    
    # Get existing rule
    rule = routing_rules[rule_id]
    
    # Check permission to modify this specific rule
    # TODO: Implement ownership/scope checking in Stage 1.5
    
    # Apply updates
    for field, value in updates.items():
        if field in ["rule_id", "created_by", "created_at"]:
            continue  # Can't modify these
        if field in rule:
            rule[field] = value
    
    # Audit log
    audit_entry = {
        "operation": "modify_rule",
        "rule_id": rule_id,
        "agent_id": agent_id,
        "timestamp": datetime.utcnow().isoformat(),
        "updates": updates
    }
    routing_audit_log.append(audit_entry)
    
    logger.info("Routing rule modified", rule_id=rule_id, agent_id=agent_id)
    
    # TODO: In Stage 1.2, update transformer system
    
    return event_response_builder.success_response(
        data={
            "rule_id": rule_id,
            "status": "modified",
            "rule": rule
        }
    )

@event_handler("routing:delete_rule")
async def handle_delete_rule(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Delete a routing rule.
    
    Parameters:
        rule_id: ID of rule to delete
    
    Required capability: routing_control
    """
    # Get agent ID from context
    ksi_context = event_data.get("_ksi_context", {})
    agent_id = ksi_context.get("_agent_id", "system")
    
    # TODO: In Stage 1.3, implement capability checking
    # For now, allow all agents to use routing control
    # if not await capability_check(agent_id, "routing_control"):
    #     return event_response_builder.error_response(
    #         error="Permission denied",
    #         details={"required_capability": "routing_control"}
    #     )
    
    rule_id = event_data.get("rule_id")
    
    if not rule_id:
        return event_response_builder.error_response(
            error="Missing rule_id"
        )
    
    if rule_id not in routing_rules:
        return event_response_builder.error_response(
            error="Rule not found",
            details={"rule_id": rule_id}
        )
    
    # Remove rule
    rule = routing_rules.pop(rule_id)
    
    # Audit log
    audit_entry = {
        "operation": "delete_rule",
        "rule_id": rule_id,
        "agent_id": agent_id,
        "timestamp": datetime.utcnow().isoformat(),
        "deleted_rule": rule
    }
    routing_audit_log.append(audit_entry)
    
    logger.info("Routing rule deleted", rule_id=rule_id, agent_id=agent_id)
    
    # TODO: In Stage 1.2, remove from transformer system
    
    return event_response_builder.success_response(
        data={
            "rule_id": rule_id,
            "status": "deleted"
        }
    )

@event_handler("routing:query_rules")
async def handle_query_rules(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query active routing rules.
    
    Parameters:
        filter: Optional filter criteria
            - agent_scope: Limit to rules created by specific agent
            - source_pattern: Filter by source pattern
            - target: Filter by target
        limit: Maximum number of rules to return
    
    No special capability required for querying.
    """
    # Extract filter parameters
    filter_params = event_data.get("filter", {})
    limit = event_data.get("limit", 100)
    
    # Filter rules
    filtered_rules = []
    for rule_id, rule in routing_rules.items():
        # Apply filters
        if filter_params.get("agent_scope"):
            if rule["created_by"] != filter_params["agent_scope"]:
                continue
        
        if filter_params.get("source_pattern"):
            if not rule["source_pattern"].startswith(filter_params["source_pattern"]):
                continue
        
        if filter_params.get("target"):
            if rule["target"] != filter_params["target"]:
                continue
        
        filtered_rules.append(rule)
    
    # Sort by priority (descending)
    filtered_rules.sort(key=lambda r: r["priority"], reverse=True)
    
    # Apply limit
    filtered_rules = filtered_rules[:limit]
    
    return event_response_builder.success_response(
        data={
            "rules": filtered_rules,
            "count": len(filtered_rules),
            "total": len(routing_rules)
        }
    )

@event_handler("routing:update_subscription")
async def handle_update_subscription(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update an agent's event subscription level.
    
    Parameters:
        agent_id: Agent whose subscription to update
        subscription_level: New subscription level (0, 1, 2, ..., -1)
        error_subscription_level: Optional separate level for errors
        reason: Optional reason for the change
    
    Required capability: routing_control
    """
    # Get requesting agent ID from context
    ksi_context = event_data.get("_ksi_context", {})
    requesting_agent = ksi_context.get("_agent_id", "system")
    
    # TODO: In Stage 1.3, implement capability checking
    # For now, allow all agents to use routing control
    # if not await capability_check(requesting_agent, "routing_control"):
    #     return event_response_builder.error_response(
    #         error="Permission denied",
    #         details={"required_capability": "routing_control"}
    #     )
    
    target_agent = event_data.get("agent_id")
    subscription_level = event_data.get("subscription_level")
    
    if not target_agent or subscription_level is None:
        return event_response_builder.error_response(
            error="Missing required fields",
            details={"required": ["agent_id", "subscription_level"]}
        )
    
    # TODO: In Stage 1.4, store in state system
    # TODO: In Stage 1.5, validate permission to modify this agent
    
    # Audit log
    audit_entry = {
        "operation": "update_subscription",
        "target_agent": target_agent,
        "requesting_agent": requesting_agent,
        "timestamp": datetime.utcnow().isoformat(),
        "subscription_level": subscription_level,
        "error_subscription_level": event_data.get("error_subscription_level"),
        "reason": event_data.get("reason")
    }
    routing_audit_log.append(audit_entry)
    
    logger.info("Subscription updated", 
                target_agent=target_agent,
                subscription_level=subscription_level,
                requesting_agent=requesting_agent)
    
    return event_response_builder.success_response(
        data={
            "agent_id": target_agent,
            "subscription_level": subscription_level,
            "status": "updated"
        }
    )

@event_handler("routing:spawn_with_routing")
async def handle_spawn_with_routing(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Spawn an agent with predefined routing relationships.
    
    Parameters:
        agent_id: ID for the new agent
        component: Component to use for the agent
        routing: Routing configuration
            - parent: Parent agent ID (optional)
            - subscription_level: Event subscription level
            - initial_routes: List of initial routing rules
            - capabilities: Capabilities including routing_control
    
    Required capability: agent (standard agent spawning)
    """
    # Get requesting agent ID from context
    ksi_context = event_data.get("_ksi_context", {})
    requesting_agent = ksi_context.get("_agent_id", "system")
    
    # TODO: In Stage 1.3, implement capability checking
    # For now, allow all agents to spawn with routing
    # if not await capability_check(requesting_agent, "agent"):
    #     return event_response_builder.error_response(
    #         error="Permission denied",
    #         details={"required_capability": "agent"}
    #     )
    
    agent_id = event_data.get("agent_id")
    component = event_data.get("component")
    routing_config = event_data.get("routing", {})
    
    if not agent_id or not component:
        return event_response_builder.error_response(
            error="Missing required fields",
            details={"required": ["agent_id", "component"]}
        )
    
    # First spawn the agent
    # TODO: Actually call agent:spawn with proper context
    
    # Then set up routing
    parent = routing_config.get("parent")
    if parent:
        # Create parent-child routing rules
        parent_to_child = {
            "rule_id": f"{parent}_to_{agent_id}",
            "source_pattern": f"orchestration:broadcast",
            "source_agent": parent,
            "target_agent": agent_id,
            "priority": 200,
            "created_by": requesting_agent
        }
        
        child_to_parent = {
            "rule_id": f"{agent_id}_to_{parent}",
            "source_pattern": f"agent:report",
            "source_agent": agent_id,
            "target_agent": parent,
            "priority": 200,
            "created_by": requesting_agent
        }
        
        # Store rules (simplified for now)
        # TODO: Properly integrate with routing system
    
    # Set up initial routes
    for route in routing_config.get("initial_routes", []):
        # Add each route
        pass  # TODO: Implement
    
    return event_response_builder.success_response(
        data={
            "agent_id": agent_id,
            "status": "spawned_with_routing",
            "routing_config": routing_config
        }
    )

@event_handler("routing:get_audit_log")
async def handle_get_audit_log(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieve routing audit log for debugging.
    
    Parameters:
        limit: Maximum number of entries to return
        since: Optional timestamp to filter entries
        operation: Optional operation type to filter
    
    Required capability: routing_control (for security)
    """
    # Get agent ID from context
    ksi_context = event_data.get("_ksi_context", {})
    agent_id = ksi_context.get("_agent_id", "system")
    
    # TODO: In Stage 1.3, implement capability checking
    # For now, allow all agents to use routing control
    # if not await capability_check(agent_id, "routing_control"):
    #     return event_response_builder.error_response(
    #         error="Permission denied",
    #         details={"required_capability": "routing_control"}
    #     )
    
    limit = event_data.get("limit", 100)
    since = event_data.get("since")
    operation = event_data.get("operation")
    
    # Filter audit log
    filtered_log = routing_audit_log
    
    if since:
        filtered_log = [e for e in filtered_log if e["timestamp"] > since]
    
    if operation:
        filtered_log = [e for e in filtered_log if e["operation"] == operation]
    
    # Sort by timestamp descending
    filtered_log.sort(key=lambda e: e["timestamp"], reverse=True)
    
    # Apply limit
    filtered_log = filtered_log[:limit]
    
    return event_response_builder.success_response(
        data={
            "entries": filtered_log,
            "count": len(filtered_log),
            "total": len(routing_audit_log)
        }
    )

# Helper function for route validation (Stage 1.5)
def validate_routing_rule(rule: Dict[str, Any]) -> Optional[str]:
    """
    Validate a routing rule for correctness.
    Returns error message if invalid, None if valid.
    """
    # Check for required fields
    if not rule.get("source_pattern"):
        return "source_pattern is required"
    
    if not rule.get("target"):
        return "target is required"
    
    # Check for circular routing (simplified)
    if rule.get("source_pattern") == rule.get("target"):
        return "Circular routing detected"
    
    # TODO: More sophisticated validation in Stage 1.5
    
    return None