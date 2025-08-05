#!/usr/bin/env python3
"""
Hierarchical Event Routing for KSI

Implements subscription-level based event routing for workflow hierarchies.
Agents and workflows can specify what level of event feedback they want:
- Level 0: Only workflow-level events  
- Level 1: Direct child agents + immediate events (default)
- Level N: Events from agents up to N levels deep in the hierarchy
- Level -1: ALL events in entire workflow tree

Examples:
- Level 2: Children and grandchildren events
- Level 3: Children, grandchildren, and great-grandchildren events
- Level 10: Events from agents up to 10 levels deep
"""

import asyncio
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict
from ksi_common.logging import get_bound_logger
from ksi_common.event_utils import extract_single_response

logger = get_bound_logger("hierarchical_routing")

# Module state
_event_emitter = None
_subscription_cache: Dict[str, Dict[str, Any]] = {}  # agent_id -> subscription info


class HierarchicalRouter:
    """Routes events based on hierarchical subscription levels."""
    
    def __init__(self, event_emitter):
        self._event_emitter = event_emitter
        self._subscription_cache = {}
        self._entity_cache = {}  # Cache entity lookups
        
    async def route_event(self, source_agent_id: str, event_name: str, event_data: Dict[str, Any]) -> None:
        """Route an event based on hierarchical subscription rules."""
        try:
            # Get source agent's hierarchy info
            source_info = await self._get_agent_hierarchy(source_agent_id)
            if not source_info:
                logger.warning(f"No hierarchy info for agent {source_agent_id}")
                return
                
            workflow_id = source_info.get('workflow_id')
            if not workflow_id:
                # Agent not part of a workflow
                return
                
            source_depth = source_info.get('workflow_depth', 0)
            
            # Get all agents in the workflow
            agents = await self._get_workflow_agents(workflow_id)
            
            # Check if this is an error event (by name pattern or data content)
            is_error = self._is_error_event(event_name, event_data)
            
            # Route to each agent based on their subscription level
            routing_tasks = []
            for agent_id, agent_info in agents.items():
                if agent_id == source_agent_id:
                    continue  # Don't route to self
                    
                # Use appropriate subscription level based on event type
                if is_error:
                    subscription_level = agent_info.get('error_subscription_level', -1)  # Default: all errors
                else:
                    subscription_level = agent_info.get('event_subscription_level', 1)
                    
                agent_depth = agent_info.get('workflow_depth', 0)
                
                # Check if this agent should receive the event
                if self._should_receive_event(source_info, agent_info, subscription_level):
                    routing_tasks.append(
                        self._route_to_agent(agent_id, source_agent_id, event_name, event_data)
                    )
            
            # Route to coordinator agent if set
            coordinator_agent_id = await self._get_coordinator_agent(workflow_id)
            if coordinator_agent_id:
                # Check subscription level for coordinator
                coord_subscription_level = await self._get_coordinator_subscription_level(
                    workflow_id, is_error
                )
                if self._should_coordinator_receive_event(source_depth, coord_subscription_level):
                    routing_tasks.append(
                        self._route_to_coordinator_agent(
                            coordinator_agent_id, source_agent_id, event_name, event_data, workflow_id
                        )
                    )
            
            # Note: Parent workflow routing removed in Stage 2.4 migration
            # Dynamic routing now handles parent-child relationships through routing rules
            
            # Execute all routing tasks concurrently
            if routing_tasks:
                await asyncio.gather(*routing_tasks, return_exceptions=True)
                
        except Exception as e:
            logger.error(f"Error in hierarchical routing: {e}")
    
    def _should_receive_event(self, source: Dict[str, Any], target: Dict[str, Any], subscription_level: int) -> bool:
        """Determine if target should receive event from source based on subscription level."""
        source_depth = source.get('workflow_depth', 0)
        target_depth = target.get('workflow_depth', 0)
        
        # Level -1: Receive all events in workflow
        if subscription_level == -1:
            return True
            
        # Level 0: Only workflow-level events (depth 0)
        if subscription_level == 0:
            return source_depth == 0
            
        # For positive levels, check depth difference
        # Level 1: Direct children only (depth difference = 1)
        # Level 2: Children and grandchildren (depth difference <= 2)
        depth_diff = source_depth - target_depth
        
        # Parent receives events from children within subscription level
        if depth_diff > 0 and depth_diff <= subscription_level:
            # Check if source is actually a descendant of target
            return self._is_descendant(source, target)
            
        # Siblings at same level with same parent
        if depth_diff == 0 and subscription_level >= 1:
            return source.get('parent_agent_id') == target.get('parent_agent_id')
            
        return False
    
    def _is_descendant(self, potential_child: Dict[str, Any], potential_parent: Dict[str, Any]) -> bool:
        """Check if potential_child is a descendant of potential_parent."""
        # Walk up the parent chain
        current_parent_id = potential_child.get('parent_agent_id')
        parent_id = potential_parent.get('agent_id')
        
        while current_parent_id:
            if current_parent_id == parent_id:
                return True
            # Would need to look up parent's parent, simplified for now
            # In production, would cache the full hierarchy tree
            break
            
        return False
    
    async def _get_agent_hierarchy(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get hierarchy information for an agent."""
        # Check cache first
        if agent_id in self._entity_cache:
            return self._entity_cache[agent_id]
            
        # Query from state
        result = await self._event_emitter("state:entity:get", {
            "entity_id": agent_id,
            "entity_type": "agent"
        })
        
        response = extract_single_response(result)
        if response:
            entity = response.get('entity', {})
            props = entity.get('properties', {})
            
            hierarchy_info = {
                'agent_id': agent_id,
                'workflow_id': props.get('workflow_id'),
                'workflow_depth': props.get('workflow_depth', 0),
                'parent_agent_id': props.get('parent_agent_id'),
                'root_workflow_id': props.get('root_workflow_id'),
                'event_subscription_level': props.get('event_subscription_level', 1),
                'error_subscription_level': props.get('error_subscription_level', -1)
            }
            
            # Cache for future use
            self._entity_cache[agent_id] = hierarchy_info
            return hierarchy_info
            
        return None
    
    async def _get_workflow_agents(self, workflow_id: str) -> Dict[str, Dict[str, Any]]:
        """Get all agents in a workflow."""
        result = await self._event_emitter("state:entity:query", {
            "entity_type": "agent",
            "filters": {
                "workflow_id": workflow_id
            }
        })
        
        agents = {}
        response = extract_single_response(result)
        if response:
            entities = response.get('entities', [])
            for entity in entities:
                agent_id = entity.get('id')
                props = entity.get('properties', {})
                agents[agent_id] = {
                    'agent_id': agent_id,
                    'workflow_depth': props.get('workflow_depth', 0),
                    'parent_agent_id': props.get('parent_agent_id'),
                    'event_subscription_level': props.get('event_subscription_level', 1),
                    'error_subscription_level': props.get('error_subscription_level', -1)
                }
                
        return agents
    
    async def _route_to_agent(self, target_agent_id: str, source_agent_id: str, 
                             event_name: str, event_data: Dict[str, Any]) -> None:
        """Route event to a specific agent."""
        try:
            # Use completion:async to inject into agent's stream
            await self._event_emitter("completion:async", {
                "agent_id": target_agent_id,
                "event_notification": {
                    "source_agent": source_agent_id,
                    "event": event_name,
                    "data": event_data,
                    "routed_by": "hierarchical_router"
                }
            })
            logger.debug(f"Routed {event_name} from {source_agent_id} to {target_agent_id}")
        except Exception as e:
            logger.error(f"Failed to route to agent {target_agent_id}: {e}")
    
    # _route_to_workflow method removed in Stage 2.4 migration
    # Dynamic routing through routing rules replaced workflow-level routing
    
    def _is_error_event(self, event_name: str, event_data: Dict[str, Any]) -> bool:
        """Determine if an event is an error event."""
        # Check by event name patterns
        error_patterns = ['error', 'exception', 'failure', 'failed', 'timeout']
        event_lower = event_name.lower()
        if any(pattern in event_lower for pattern in error_patterns):
            return True
            
        # Check for error fields in data
        if event_data.get('error') or event_data.get('exception') or event_data.get('status') == 'error':
            return True
            
        return False
    
    async def _get_coordinator_agent(self, workflow_id: str) -> Optional[str]:
        """Get the coordinator agent ID for a workflow."""
        result = await self._event_emitter("state:entity:get", {
            "entity_type": "workflow",
            "entity_id": workflow_id
        })
        
        response = extract_single_response(result)
        if response:
            entity = response.get('entity', {})
            props = entity.get('properties', {})
            return props.get('coordinator_agent_id')
            
        return None
    
    async def _get_coordinator_subscription_level(self, workflow_id: str, is_error: bool) -> int:
        """Get the subscription level for the coordinator."""
        result = await self._event_emitter("state:entity:get", {
            "entity_type": "workflow",
            "entity_id": workflow_id
        })
        
        response = extract_single_response(result)
        if response:
            entity = response.get('entity', {})
            props = entity.get('properties', {})
            if is_error:
                return props.get('error_subscription_level', -1)
            else:
                return props.get('event_subscription_level', 1)
                
        return 1 if not is_error else -1
    
    def _should_coordinator_receive_event(self, source_depth: int, subscription_level: int) -> bool:
        """Check if coordinator should receive event based on source depth."""
        # Level -1: Receive all events
        if subscription_level == -1:
            return True
            
        # Level 0: Only root level events (depth 0)
        if subscription_level == 0:
            return source_depth == 0
            
        # For positive levels, check if source is within subscription depth
        return source_depth <= subscription_level
    
    async def _route_to_coordinator_agent(self, coordinator_agent_id: str, source_agent_id: str,
                                          event_name: str, event_data: Dict[str, Any], 
                                          workflow_id: str) -> None:
        """Route event to the coordinator agent."""
        try:
            # Special handling for claude-code as coordinator
            if coordinator_agent_id == "claude-code":
                # Tag with client_id for Claude Code
                enriched_data = {
                    **event_data,
                    "_client_id": "claude-code",
                    "_from_workflow": workflow_id,
                    "_source_agent": source_agent_id
                }
                # Route to system logger (Claude Code will see in logs/hook)
                logger.info(f"Coordinator feedback: {event_name}", 
                           extra={
                               "event": event_name,
                               "data": enriched_data,
                               "coordinator": "claude-code"
                           })
            else:
                # Route to regular agent
                await self._route_to_agent(
                    coordinator_agent_id, source_agent_id, event_name, event_data
                )
            logger.debug(f"Routed {event_name} to coordinator {coordinator_agent_id}")
        except Exception as e:
            logger.error(f"Failed to route to coordinator {coordinator_agent_id}: {e}")
    
    def clear_cache(self):
        """Clear cached entity data."""
        self._entity_cache.clear()
        self._subscription_cache.clear()


# Global router instance
_router: Optional[HierarchicalRouter] = None


def get_router() -> Optional[HierarchicalRouter]:
    """Get the global hierarchical router instance."""
    return _router


def set_event_emitter(emitter):
    """Set the event emitter and initialize router."""
    global _router, _event_emitter
    _event_emitter = emitter
    _router = HierarchicalRouter(emitter)
    logger.info("Hierarchical router initialized")


async def route_hierarchical_event(source_agent_id: str, event_name: str, event_data: Dict[str, Any]) -> None:
    """Route an event through the hierarchical routing system."""
    if _router:
        await _router.route_event(source_agent_id, event_name, event_data)
    else:
        logger.warning("Hierarchical router not initialized")