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
from ksi_common.event_response_builder import event_response_builder, success_response, error_response

logger = get_bound_logger("routing_events", version="1.0.0")

# Helper function for capability checking
async def check_routing_capability(agent_id: str, context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Check if an agent has the routing_control capability.
    
    Returns:
        None if capability check passes, error response dict if it fails
    """
    # System agent always has permission
    if agent_id == "system":
        return None
        
    # Get agent capabilities from state
    from ksi_daemon.event_system import get_router
    router = get_router()
    
    # Query agent state to get capabilities
    result = await router.emit("state:entity:get", {"type": "agent", "id": agent_id})
    if result and len(result) > 0 and result[0].get("status") == "success":
        entity = result[0].get("data", {}).get("entity", {})
        capabilities = entity.get("properties", {}).get("capabilities", [])
        
        # Check if agent has routing_control capability
        if "routing_control" not in capabilities:
            return error_response(
                error="Permission denied",
                details={
                    "required_capability": "routing_control",
                    "agent_capabilities": capabilities
                }
            )
        return None  # Capability check passed
    else:
        # If we can't get agent info, deny by default
        return error_response(
            error="Unable to verify agent capabilities",
            details={"agent_id": agent_id}
        )

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

# Import routing service accessor
from .routing_service import get_routing_service

# In-memory routing store (will be moved to state system in Stage 1.4)
routing_rules: Dict[str, RoutingRule] = {}
routing_audit_log: List[Dict[str, Any]] = []

@event_handler("routing:add_rule")
async def handle_add_rule(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
    agent_id = context.get("_agent_id", "system") if context else "system"
    
    # Check routing_control capability
    capability_error = await check_routing_capability(agent_id, context)
    if capability_error:
        return capability_error
    
    # Extract parameters
    rule_id = data.get("rule_id")
    if not rule_id:
        rule_id = f"rule_{uuid.uuid4().hex[:8]}"
    
    source_pattern = data.get("source_pattern")
    target = data.get("target")
    
    if not source_pattern or not target:
        return error_response(
            error="Missing required fields",
            details={"required": ["source_pattern", "target"]}
        )
    
    # Check for conflicts
    if rule_id in routing_rules:
        return error_response(
            error="Rule ID already exists",
            details={"rule_id": rule_id}
        )
    
    # Convert string parameters to appropriate types
    priority = data.get("priority", 100)
    if isinstance(priority, str):
        try:
            priority = int(priority)
        except ValueError:
            priority = 100
    
    ttl = data.get("ttl")
    if ttl and isinstance(ttl, str):
        try:
            ttl = int(ttl)
        except ValueError:
            ttl = None
    
    # Handle mapping if it's a JSON string
    mapping = data.get("mapping")
    if mapping and isinstance(mapping, str):
        try:
            mapping = json.loads(mapping)
        except json.JSONDecodeError:
            # Leave as string if not valid JSON
            pass
    
    # Create rule
    rule = RoutingRule(
        rule_id=rule_id,
        source_pattern=source_pattern,
        target=target,
        condition=data.get("condition"),
        mapping=mapping,
        priority=priority,
        ttl=ttl,
        created_by=agent_id,
        created_at=datetime.utcnow().isoformat(),
        metadata=data.get("metadata")
    )
    
    # Get routing service
    service = get_routing_service()
    if not service:
        return error_response(
            error="Routing service not available",
            details={"service_status": "not_initialized"}
        )
    
    # Add rule via service (which will integrate with transformers)
    result = await service.add_routing_rule(rule)
    
    # Audit log (TODO: Move to service in Stage 1.6)
    audit_entry = {
        "operation": "add_rule",
        "rule_id": rule_id,
        "agent_id": agent_id,
        "timestamp": datetime.utcnow().isoformat(),
        "rule": rule
    }
    routing_audit_log.append(audit_entry)
    
    logger.info("Routing rule added", rule_id=rule_id, agent_id=agent_id)
    
    if result.get("status") == "success":
        return success_response(
            data={
                "rule_id": rule_id,
                "status": "created",
                "rule": rule
            }
        )
    else:
        return error_response(
            error=result.get("error", "Failed to add routing rule"),
            details=result
        )

@event_handler("routing:modify_rule")
async def handle_modify_rule(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Modify an existing routing rule.
    
    Parameters:
        rule_id: ID of rule to modify
        updates: Dictionary of fields to update
    
    Required capability: routing_control
    """
    # Get agent ID from context
    agent_id = context.get("_agent_id", "system") if context else "system"
    
    # Check routing_control capability
    capability_error = await check_routing_capability(agent_id, context)
    if capability_error:
        return capability_error
    
    rule_id = data.get("rule_id")
    updates = data.get("updates", {})
    
    # Handle case where updates might be a JSON string
    if isinstance(updates, str):
        try:
            updates = json.loads(updates)
        except json.JSONDecodeError:
            return error_response(
                error="Invalid updates format",
                details={"updates": updates, "expected": "JSON object"}
            )
    
    if not rule_id:
        return error_response(
            error="Missing rule_id"
        )
    
    # Get routing service
    service = get_routing_service()
    if not service:
        return error_response(
            error="Routing service not available",
            details={"service_status": "not_initialized"}
        )
    
    # Delegate to service for modification
    result = await service.modify_routing_rule(rule_id, updates)
    
    # Check result from service
    if result.get("status") == "success":
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
        
        return success_response(
            data={
                "rule_id": rule_id,
                "status": "modified",
                "updates": updates
            }
        )
    else:
        return error_response(
            error=result.get("error", "Failed to modify routing rule"),
            details=result
        )

@event_handler("routing:delete_rule")
async def handle_delete_rule(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Delete a routing rule.
    
    Parameters:
        rule_id: ID of rule to delete
    
    Required capability: routing_control
    """
    # Get agent ID from context
    agent_id = context.get("_agent_id", "system") if context else "system"
    
    # Check routing_control capability
    capability_error = await check_routing_capability(agent_id, context)
    if capability_error:
        return capability_error
    
    rule_id = data.get("rule_id")
    
    if not rule_id:
        return error_response(
            error="Missing rule_id"
        )
    
    # Get routing service
    service = get_routing_service()
    if not service:
        return error_response(
            error="Routing service not available",
            details={"service_status": "not_initialized"}
        )
    
    # Delegate to service for deletion (note: service method is _remove_rule, private)
    # We need to check if rule exists first
    if rule_id not in service.routing_rules:
        return error_response(
            error="Rule not found",
            details={"rule_id": rule_id}
        )
    
    # Get rule before deletion for audit log
    deleted_rule = service.routing_rules.get(rule_id)
    
    # Remove via service
    result = await service._remove_rule(rule_id)
    
    if result.get("status") == "success":
        # Audit log
        audit_entry = {
            "operation": "delete_rule",
            "rule_id": rule_id,
            "agent_id": agent_id,
            "timestamp": datetime.utcnow().isoformat(),
            "deleted_rule": deleted_rule
        }
        routing_audit_log.append(audit_entry)
        
        logger.info("Routing rule deleted", rule_id=rule_id, agent_id=agent_id)
        
        return success_response(
            data={
                "rule_id": rule_id,
                "status": "deleted"
            }
        )
    else:
        return error_response(
            error=result.get("error", "Failed to delete routing rule"),
            details=result
        )

@event_handler("routing:query_rules")
async def handle_query_rules(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
    filter_params = data.get("filter", {})
    limit = data.get("limit", 100)
    
    # Get routing service
    service = get_routing_service()
    if not service:
        return error_response(
            error="Routing service not available",
            details={"service_status": "not_initialized"}
        )
    
    # Filter rules from service
    filtered_rules = []
    for rule_id, rule in service.routing_rules.items():
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
    
    return success_response(
        data={
            "rules": filtered_rules,
            "count": len(filtered_rules),
            "total": len(service.routing_rules)
        }
    )

@event_handler("routing:update_subscription")
async def handle_update_subscription(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
    requesting_agent = context.get("_agent_id", "system") if context else "system"
    
    # TODO: In Stage 1.3, implement capability checking
    # For now, allow all agents to use routing control
    # if not await capability_check(requesting_agent, "routing_control"):
    #     return error_response(
    #         error="Permission denied",
    #         details={"required_capability": "routing_control"}
    #     )
    
    target_agent = data.get("agent_id")
    subscription_level = data.get("subscription_level")
    
    if not target_agent or subscription_level is None:
        return error_response(
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
        "error_subscription_level": data.get("error_subscription_level"),
        "reason": data.get("reason")
    }
    routing_audit_log.append(audit_entry)
    
    logger.info("Subscription updated", 
                target_agent=target_agent,
                subscription_level=subscription_level,
                requesting_agent=requesting_agent)
    
    return success_response(
        data={
            "agent_id": target_agent,
            "subscription_level": subscription_level,
            "status": "updated"
        }
    )

@event_handler("routing:spawn_with_routing")
async def handle_spawn_with_routing(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
    requesting_agent = context.get("_agent_id", "system") if context else "system"
    
    # TODO: In Stage 1.3, implement capability checking
    # For now, allow all agents to spawn with routing
    # if not await capability_check(requesting_agent, "agent"):
    #     return error_response(
    #         error="Permission denied",
    #         details={"required_capability": "agent"}
    #     )
    
    agent_id = data.get("agent_id")
    component = data.get("component")
    routing_config = data.get("routing", {})
    
    if not agent_id or not component:
        return error_response(
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
    
    return success_response(
        data={
            "agent_id": agent_id,
            "status": "spawned_with_routing",
            "routing_config": routing_config
        }
    )

@event_handler("routing:get_audit_log")
async def handle_get_audit_log(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Retrieve routing audit log for debugging.
    
    Parameters:
        limit: Maximum number of entries to return
        since: Optional timestamp to filter entries
        operation: Optional operation type to filter
    
    Required capability: routing_control (for security)
    """
    # Get agent ID from context
    agent_id = context.get("_agent_id", "system") if context else "system"
    
    # Check routing_control capability
    capability_error = await check_routing_capability(agent_id, context)
    if capability_error:
        return capability_error
    
    # Convert limit to int if it's a string
    limit = data.get("limit", 100)
    if isinstance(limit, str):
        try:
            limit = int(limit)
        except ValueError:
            limit = 100
    
    since = data.get("since")
    operation = data.get("operation")
    
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
    
    return success_response(
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