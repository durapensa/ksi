#!/usr/bin/env python3
"""
Universal error handler for KSI system.

This module provides the system:error handler that:
1. Routes all errors to their originators based on context
2. Stores errors for debugging and monitoring
3. Handles critical error escalation
4. Manages error recovery for recoverable errors
5. Provides informative error messages to agents
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from ksi_common.event_response_builder import success_response, error_response
from ksi_common.timestamps import timestamp_utc
from ksi_daemon.event_system import event_handler, get_router

logger = logging.getLogger(__name__)

# Define critical error types that require escalation
CRITICAL_ERROR_TYPES = {
    "system_failure",
    "data_corruption", 
    "security_breach",
    "database_corruption",
    "handler_crash",
    "service_crash"
}

# Define recoverable error types that can be retried
RECOVERABLE_ERROR_TYPES = {
    "timeout",
    "rate_limit",
    "temporary_failure",
    "network_error",
    "provider_error",
    "transformation_failure"
}


async def find_parent_agents(agent_id: str, level: int) -> List[str]:
    """
    Find parent agents using dynamic routing rules.
    
    Parents are agents that have routing rules targeting this agent.
    
    Args:
        agent_id: The agent whose parents to find
        level: How many levels up to traverse (0=none, 1=direct, 2=grandparents, -1=all)
        
    Returns:
        List of parent agent IDs
    """
    if level == 0:
        return []
    
    router = get_router()
    
    # Query routing rules where this agent is a target
    # For now, we'll use state queries to find parent relationships
    # In the future this would query the routing system directly
    routing_result = await router.emit_first("state:entity:query", {
        "type": "routing_rule",
        "where": {
            "properties.target_agent": agent_id,
            "properties.relationship": "parent_child"
        }
    })
    
    parents = set()
    if routing_result and routing_result.get("entities"):
        for rule in routing_result["entities"]:
            source_agent = rule.get("properties", {}).get("source_agent")
            if source_agent:
                parents.add(source_agent)
                
                # Recursively find ancestors if level > 1 or level == -1
                if level > 1 or level == -1:
                    ancestors = await find_parent_agents(
                        source_agent,
                        level - 1 if level > 1 else -1
                    )
                    parents.update(ancestors)
    
    return list(parents)


async def propagate_error_hierarchically(
    agent_id: str, 
    error_data: Dict[str, Any], 
    error_message: str, 
    level: int
) -> List[Dict[str, Any]]:
    """
    Propagate error to parent agents based on propagation level.
    
    Args:
        agent_id: The originating agent
        error_data: The full error data
        error_message: Formatted error message
        level: Propagation level (1=parents, 2=grandparents, -1=all ancestors)
        
    Returns:
        List of propagation results
    """
    router = get_router()
    parent_agents = await find_parent_agents(agent_id, level)
    
    propagation_results = []
    for parent_id in parent_agents:
        # Format error for parent context
        parent_message = f"[Error from child agent '{agent_id}']\n{error_message}"
        
        # Deliver to parent agent
        inject_result = await router.emit("completion:inject", {
            "agent_id": parent_id,
            "messages": [{
                "role": "system",
                "content": parent_message,
                "metadata": {
                    "error_source": agent_id,
                    "error_id": error_data.get("error_id"),
                    "propagation_type": "hierarchical",
                    "propagation_level": level
                }
            }]
        })
        
        propagation_results.append({
            "parent_agent": parent_id,
            "delivered": inject_result is not None
        })
        
        logger.info(f"Propagated error to parent agent {parent_id} (level {level})")
    
    return propagation_results


def format_agent_error(error_data: Dict[str, Any]) -> str:
    """
    Format error data into informative message for agent consumption.
    
    Provides context about what failed, why, and what the agent might do.
    
    Args:
        error_data: The system:error event data
        
    Returns:
        Formatted error message for agent
    """
    error_type = error_data.get("error_type", "unknown")
    error_class = error_data.get("error_class", "Exception")
    error_message = error_data.get("error_message", "An error occurred")
    
    source = error_data.get("source", {})
    operation = source.get("operation", "unknown operation")
    module = source.get("module", "unknown module")
    
    # Build informative error message
    message_parts = [
        f"ERROR: Operation '{operation}' failed",
        f"Type: {error_class}",
        f"Message: {error_message}",
    ]
    
    # Add context-specific information
    if error_type == "transformer_failure":
        transformer = source.get("transformer", "unknown")
        source_event = source.get("source_event", "unknown")
        target_event = source.get("target_event", "unknown")
        message_parts.extend([
            f"Transformer: {transformer}",
            f"Failed transforming: {source_event} → {target_event}"
        ])
        
        # If it's a template error, provide more details
        if "TemplateResolutionError" in error_class:
            mapping = source.get("mapping", {})
            message_parts.append(f"Check your mapping configuration: {mapping}")
    
    elif error_type == "handler_failure":
        message_parts.append(f"Handler in module: {module}")
        
    elif error_type == "service_failure":
        message_parts.append(f"Service component: {module}")
    
    # Add recovery suggestions based on error type
    if error_type in RECOVERABLE_ERROR_TYPES:
        message_parts.append("\nThis error may be temporary. The system will attempt recovery.")
    elif "TemplateResolutionError" in error_class:
        message_parts.append("\nThis appears to be a configuration error. Check your event data includes all required fields.")
    elif "ValidationError" in error_class:
        message_parts.append("\nYour request data did not pass validation. Check the format and required fields.")
    
    return "\n".join(message_parts)


def generate_error_id() -> str:
    """Generate unique error ID for tracking."""
    import uuid
    return f"err_{uuid.uuid4().hex[:12]}"


@event_handler("system:error")
async def universal_error_handler(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Universal error handler - routes ALL errors based on context.
    
    This is the single source of truth for error propagation in KSI.
    Every error in the system flows through this handler.
    
    Returns an informative response about how the error was handled.
    """
    # Debug logging to understand what we're receiving
    logger.info(f"system:error handler called with data type: {type(data)}")
    if isinstance(data, str):
        logger.error(f"ERROR: system:error handler received STRING instead of dict: '{data}'")
        logger.error(f"Context type: {type(context)}, Context keys: {list(context.keys()) if context else 'None'}")
    else:
        logger.info(f"system:error handler received dict with keys: {list(data.keys()) if data else 'None'}")
    
    # Handle cases where data might be a string (context reference)
    if isinstance(data, str):
        logger.error(f"system:error handler received string data: {data}")
        # If it's a context reference, try to resolve it
        if data.startswith("ctx_"):
            from ksi_daemon.core.context_manager import get_context_manager
            cm = get_context_manager()
            resolved_context = await cm.get_context(data)
            if resolved_context:
                data = resolved_context
            else:
                logger.error(f"Could not resolve context reference: {data}")
                return error_response("Invalid context reference", context)
        else:
            logger.error(f"system:error handler received invalid string data: {data}")
            return error_response("Invalid data format - expected dict", context)
    
    # Extract routing context
    # PYTHONIC CONTEXT REFACTOR: _ksi_context is now a reference string, not a dict
    ksi_context_ref = data.get("_ksi_context", "")
    
    # Resolve the context reference to get actual context data
    if isinstance(ksi_context_ref, str) and ksi_context_ref.startswith("ctx_"):
        from ksi_daemon.core.context_manager import get_context_manager
        cm = get_context_manager()
        ksi_context = await cm.get_context(ksi_context_ref) or {}
    elif isinstance(ksi_context_ref, dict):
        # Support legacy format where context might still be a dict
        ksi_context = ksi_context_ref
    else:
        ksi_context = {}
    
    client_id = ksi_context.get("_client_id", "") if isinstance(ksi_context, dict) else ""
    correlation_id = ksi_context.get("_correlation_id", "") if isinstance(ksi_context, dict) else ""
    
    error_id = generate_error_id()
    error_type = data.get("error_type", "unknown")
    
    # Store error for debugging/monitoring with full context
    router = get_router()
    storage_result = await router.emit("state:entity:create", {
        "type": "error",
        "id": error_id,
        "properties": {
            **data,
            "error_id": error_id,
            "processed_at": timestamp_utc(),
            "routed_to": client_id,
            "correlation_id": correlation_id
        }
    })
    
    routing_results = []
    
    # Route to originator based on client type
    if client_id.startswith("agent_"):
        # Deliver error to agent via completion:inject
        agent_id = client_id[6:]
        
        # Format informative error message
        error_message = format_agent_error(data)
        
        inject_result = await router.emit("completion:inject", {
            "agent_id": agent_id,
            "messages": [{
                "role": "system",
                "content": error_message
            }]
        })
        
        routing_results.append({
            "destination": "agent",
            "agent_id": agent_id,
            "delivered": inject_result is not None
        })
        
        logger.info(f"Routed error {error_id} to agent {agent_id}")
        
        # HIERARCHICAL ERROR PROPAGATION
        # Check agent's error propagation preference
        agent_state = await router.emit_first("state:entity:get", {
            "type": "agent",
            "id": agent_id
        })
        
        hierarchical_results = []
        if agent_state and isinstance(agent_state, dict) and agent_state.get("properties"):
            propagation_level = agent_state["properties"].get("error_propagation_level", 0)
            
            if propagation_level != 0:
                hierarchical_results = await propagate_error_hierarchically(
                    agent_id,
                    data,
                    error_message,
                    propagation_level
                )
                routing_results.extend(hierarchical_results)
                logger.info(f"Propagated error hierarchically to {len(hierarchical_results)} parents")
        
    elif client_id.startswith("workflow_"):
        # Route to workflow error handler
        workflow_id = client_id[9:]
        
        workflow_result = await router.emit("workflow:error", {
            "workflow_id": workflow_id,
            "error_id": error_id,
            "error": data
        })
        
        routing_results.append({
            "destination": "workflow",
            "workflow_id": workflow_id,
            "delivered": workflow_result is not None
        })
        
        logger.info(f"Routed error {error_id} to workflow {workflow_id}")
        
    elif client_id == "cli":
        # CLI already gets error via return path
        routing_results.append({
            "destination": "cli",
            "delivered": True,
            "note": "CLI receives error via direct response"
        })
        
    else:
        # No specific routing - just stored for monitoring
        routing_results.append({
            "destination": "monitor_only",
            "reason": "No client_id in context for routing"
        })
        logger.warning(f"Error {error_id} has no routing destination (client_id: {client_id})")
    
    # Check for critical errors requiring escalation
    if error_type in CRITICAL_ERROR_TYPES or data.get("error_class") in CRITICAL_ERROR_TYPES:
        escalation_result = await router.emit("monitor:critical_error", {
            "error_id": error_id,
            "error_data": data,
            "escalation_reason": "Critical error type detected"
        })
        
        routing_results.append({
            "destination": "critical_escalation",
            "escalated": escalation_result is not None
        })
        
        logger.critical(f"Critical error {error_id} escalated: {error_type}")
    
    # Check for recoverable errors
    if error_type in RECOVERABLE_ERROR_TYPES:
        recovery_result = await router.emit("error:recovery:attempt", {
            "error_id": error_id,
            "error_type": error_type,
            "original_error": data,
            "recovery_strategy": "retry",
            "_ksi_context": ksi_context_ref  # Preserve context reference for retry
        })
        
        routing_results.append({
            "destination": "recovery_system",
            "recovery_initiated": recovery_result is not None
        })
        
        logger.info(f"Recovery initiated for error {error_id}: {error_type}")
    
    # Return informative response about error handling
    return success_response({
        "error_id": error_id,
        "error_type": error_type,
        "handled": True,
        "stored": storage_result is not None,
        "routing": routing_results,
        "client_id": client_id,
        "correlation_id": correlation_id,
        "is_critical": error_type in CRITICAL_ERROR_TYPES,
        "is_recoverable": error_type in RECOVERABLE_ERROR_TYPES,
        "message": f"Error {error_id} processed and routed to {len(routing_results)} destination(s)"
    })


# Additional handler for error recovery attempts
@event_handler("error:recovery:attempt")
async def handle_error_recovery(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Handle error recovery attempts for recoverable errors.
    
    This handler implements retry logic and recovery strategies.
    """
    error_id = data.get("error_id")
    error_type = data.get("error_type")
    strategy = data.get("recovery_strategy", "retry")
    original_error = data.get("original_error", {})
    
    logger.info(f"Attempting recovery for error {error_id} using strategy: {strategy}")
    
    if strategy == "retry":
        # Extract original operation details
        source = original_error.get("source", {})
        operation = source.get("operation")
        original_data = original_error.get("original_data", {})
        
        # TODO: Implement actual retry logic based on operation type
        # For now, just log the recovery attempt
        logger.info(f"Would retry operation {operation} with data: {original_data}")
        
        return success_response({
            "error_id": error_id,
            "recovery_status": "attempted",
            "strategy": strategy,
            "message": f"Recovery attempted for {error_type} error"
        })
    
    return error_response(f"Unknown recovery strategy: {strategy}", context)


# Register handlers when module is imported
def register_system_error_handlers():
    """Register system error handlers with the event system."""
    logger.info("System error handlers registered")


# Auto-register when imported
try:
    register_system_error_handlers()
except Exception as e:
    logger.warning(f"Could not auto-register system error handlers: {e}")