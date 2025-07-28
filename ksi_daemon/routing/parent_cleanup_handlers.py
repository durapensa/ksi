#!/usr/bin/env python3
"""
Parent Cleanup Event Handlers

Automatically clean up routing rules when parent entities are terminated.
"""

from typing import Dict, Any, Optional
from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import event_handler
from .routing_service import get_routing_service

logger = get_bound_logger("parent_cleanup", version="1.0.0")

@event_handler("agent:terminated")
async def handle_agent_terminated(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Clean up routing rules when an agent is terminated.
    
    Parameters:
        agent_id: ID of the terminated agent
    """
    agent_id = data.get("agent_id")
    if not agent_id:
        logger.warning("Agent termination event missing agent_id")
        return {"status": "ignored", "reason": "No agent_id provided"}
    
    # Get routing service
    service = get_routing_service()
    if not service:
        logger.error("Routing service not available")
        return {"status": "error", "error": "Routing service not available"}
    
    # Clean up rules associated with this agent
    try:
        rules_cleaned = await service.cleanup_parent_rules("agent", agent_id)
        logger.info(f"Cleaned up {rules_cleaned} routing rules for terminated agent {agent_id}")
        return {"status": "success", "rules_cleaned": rules_cleaned}
    except Exception as e:
        logger.error(f"Failed to clean up rules for agent {agent_id}: {e}")
        return {"status": "error", "error": str(e)}

@event_handler("orchestration:terminated")
async def handle_orchestration_terminated(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Clean up routing rules when an orchestration is terminated.
    
    Parameters:
        orchestration_id: ID of the terminated orchestration
    """
    orchestration_id = data.get("orchestration_id")
    if not orchestration_id:
        logger.warning("Orchestration termination event missing orchestration_id")
        return {"status": "ignored", "reason": "No orchestration_id provided"}
    
    # Get routing service
    service = get_routing_service()
    if not service:
        logger.error("Routing service not available")
        return {"status": "error", "error": "Routing service not available"}
    
    # Clean up rules associated with this orchestration
    try:
        rules_cleaned = await service.cleanup_parent_rules("orchestration", orchestration_id)
        logger.info(f"Cleaned up {rules_cleaned} routing rules for terminated orchestration {orchestration_id}")
        return {"status": "success", "rules_cleaned": rules_cleaned}
    except Exception as e:
        logger.error(f"Failed to clean up rules for orchestration {orchestration_id}: {e}")
        return {"status": "error", "error": str(e)}

@event_handler("workflow:terminated")
async def handle_workflow_terminated(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Clean up routing rules when a workflow is terminated.
    
    Parameters:
        workflow_id: ID of the terminated workflow
    """
    workflow_id = data.get("workflow_id")
    if not workflow_id:
        logger.warning("Workflow termination event missing workflow_id")
        return {"status": "ignored", "reason": "No workflow_id provided"}
    
    # Get routing service
    service = get_routing_service()
    if not service:
        logger.error("Routing service not available")
        return {"status": "error", "error": "Routing service not available"}
    
    # Clean up rules associated with this workflow
    try:
        rules_cleaned = await service.cleanup_parent_rules("workflow", workflow_id)
        logger.info(f"Cleaned up {rules_cleaned} routing rules for terminated workflow {workflow_id}")
        return {"status": "success", "rules_cleaned": rules_cleaned}
    except Exception as e:
        logger.error(f"Failed to clean up rules for workflow {workflow_id}: {e}")
        return {"status": "error", "error": str(e)}

# Alternative handler for agent:removed event (some systems use this instead of terminated)
@event_handler("agent:removed")
async def handle_agent_removed(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Clean up routing rules when an agent is removed.
    Delegates to the terminated handler for consistency.
    """
    return await handle_agent_terminated(data, context)

# Handler for state entity deletion (catches any missed termination events)
@event_handler("state:entity:deleted")
async def handle_entity_deleted(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Clean up routing rules when a state entity is deleted.
    This is a catch-all for any missed termination events.
    
    Parameters:
        type: Entity type ("agent", "orchestration", etc.)
        id: Entity ID
    """
    entity_type = data.get("type")
    entity_id = data.get("id")
    
    if not entity_type or not entity_id:
        return {"status": "ignored", "reason": "Missing entity type or id"}
    
    # Only handle types we care about
    if entity_type not in ["agent", "orchestration", "workflow"]:
        return {"status": "ignored", "reason": f"Entity type {entity_type} not tracked for routing"}
    
    # Get routing service
    service = get_routing_service()
    if not service:
        logger.error("Routing service not available")
        return {"status": "error", "error": "Routing service not available"}
    
    # Clean up rules associated with this entity
    try:
        rules_cleaned = await service.cleanup_parent_rules(entity_type, entity_id)
        if rules_cleaned > 0:
            logger.info(f"Cleaned up {rules_cleaned} routing rules for deleted {entity_type} {entity_id}")
        return {"status": "success", "rules_cleaned": rules_cleaned}
    except Exception as e:
        logger.error(f"Failed to clean up rules for {entity_type} {entity_id}: {e}")
        return {"status": "error", "error": str(e)}