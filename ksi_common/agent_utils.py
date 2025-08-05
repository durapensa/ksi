#!/usr/bin/env python3
"""
Shared utilities for agent operations across KSI services.

Provides common patterns for agent validation, state queries, and response handling.
"""

from typing import Dict, Any, Optional, List, TypeVar, Callable
from functools import wraps
import asyncio
from pathlib import Path

from .event_response_builder import error_response, event_response_builder
from .logging import get_bound_logger
from .event_utils import extract_single_response

logger = get_bound_logger("agent_utils")

# Type variable for TypedDict classes
T = TypeVar('T', bound=Dict[str, Any])


def event_handler_boilerplate(typed_dict_class: T):
    """
    Decorator that handles common event handler patterns.
    
    BREAKING CHANGE: Now uses direct data access instead of event_format_linter.
    
    Eliminates boilerplate for:
    - Direct data access (no parsing needed)
    - Automatic response building 
    - Standard error handling
    
    Usage:
        @event_handler_boilerplate(MyTypedDict)
        async def handle_my_event(data: MyTypedDict, context: Optional[Dict[str, Any]] = None):
            # data is already clean - system metadata is in _ksi_context
            return {"result": "success"}  # Automatically wrapped in event_response_builder
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            try:
                # BREAKING CHANGE: Direct data access, _ksi_context contains system metadata
                result = await func(data, context)
                
                # Auto-wrap result if it's not already a response
                if isinstance(result, dict) and "status" not in result and "error" not in result:
                    return event_response_builder(result, context)
                return result
                
            except Exception as e:
                logger.error(f"Event handler {func.__name__} failed: {e}")
                return error_response(f"Handler failed: {str(e)}", context)
        return wrapper
    return decorator


# REMOVED: require_agent decorator - deprecated with raw_data pattern


async def query_agent_state(event_emitter: Callable, agent_id: str, properties: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """
    Query agent entity from state system with standard error handling.
    
    Args:
        event_emitter: Event emitter function
        agent_id: Agent ID to query
        properties: Optional list of properties to fetch
        
    Returns:
        Agent entity dict or None if not found
    """
    if not event_emitter:
        logger.warning("No event emitter available for state query")
        return None
        
    try:
        query_data = {
            "type": "agent",
            "filter": {"agent_id": agent_id}
        }
        if properties:
            query_data["properties"] = properties
            
        entities = await event_emitter({
            "event": "state:entity:search",
            "data": query_data
        })
        
        # Handle KSI's list-wrapped responses
        entities = unwrap_list_response(entities)
        
        if entities and isinstance(entities, list) and len(entities) > 0:
            return entities[0]
            
    except Exception as e:
        logger.error(f"Failed to query agent state: {e}")
        
    return None


async def query_agent_metadata(event_emitter: Callable, agent_id: str, keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Query agent metadata from state system.
    
    Args:
        event_emitter: Event emitter function
        agent_id: Agent ID
        keys: Optional list of metadata keys to fetch
        
    Returns:
        Dict of metadata key-value pairs
    """
    if not event_emitter:
        return {}
        
    try:
        query_data = {
            "namespace": f"metadata:agent:{agent_id}"
        }
        if keys:
            query_data["keys"] = keys
            
        result = await event_emitter({
            "event": "state:metadata:get_multi",
            "data": query_data
        })
        
        result = unwrap_list_response(result)
        return result.get("values", {}) if result else {}
        
    except Exception as e:
        logger.error(f"Failed to query agent metadata: {e}")
        return {}


async def query_agent_relationships(event_emitter: Callable, agent_id: str, 
                                  relation_type: Optional[str] = None,
                                  direction: str = "both") -> List[Dict[str, Any]]:
    """
    Query agent relationships from state system.
    
    Args:
        event_emitter: Event emitter function
        agent_id: Agent ID
        relation_type: Optional specific relationship type to filter
        direction: 'incoming', 'outgoing', or 'both'
        
    Returns:
        List of relationship dicts
    """
    if not event_emitter:
        return []
        
    try:
        query_data = {
            "entity_id": agent_id,
            "direction": direction
        }
        if relation_type:
            query_data["relation_type"] = relation_type
            
        result = await event_emitter({
            "event": "state:relationship:list",
            "data": query_data
        })
        
        result = unwrap_list_response(result)
        return result.get("relationships", []) if result else []
        
    except Exception as e:
        logger.error(f"Failed to query agent relationships: {e}")
        return []


def unwrap_list_response(response: Any) -> Any:
    """
    Unwrap KSI's common pattern of list-wrapped responses.
    
    Many KSI handlers return [result] instead of result directly.
    This utility safely unwraps single-element lists.
    
    Args:
        response: The response to unwrap
        
    Returns:
        Unwrapped response or original if not a single-element list
    """
    if isinstance(response, list) and len(response) == 1:
        return response[0]
    return response


async def emit_agent_event(event_emitter: Callable, event_name: str, 
                         agent_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Emit an agent-related event with standard structure.
    
    Args:
        event_emitter: Event emitter function
        event_name: Name of the event
        agent_id: Agent ID
        data: Additional event data
        
    Returns:
        Event response or None
    """
    if not event_emitter:
        logger.warning(f"No event emitter available for {event_name}")
        return None
        
    try:
        event_data = {"agent_id": agent_id, **data}
        return await event_emitter({
            "event": event_name,
            "data": event_data
        })
    except Exception as e:
        logger.error(f"Failed to emit {event_name}: {e}")
        return None


async def gather_agent_info(event_emitter: Callable, agent_info: Dict[str, Any], 
                          include: List[str]) -> Dict[str, Any]:
    """
    Gather comprehensive agent information based on include list.
    
    Args:
        event_emitter: Event emitter function
        agent_info: Basic agent info dict
        include: List of data types to include
        
    Returns:
        Dict with requested agent information
    """
    agent_id = agent_info["agent_id"]
    result = {}
    
    # Always include basic info
    result.update({
        "agent_id": agent_id,
        "status": agent_info.get("status"),
        "profile": agent_info.get("profile"),
        "created_at": agent_info.get("created_at"),
        "sandbox_dir": agent_info.get("sandbox_dir"),
        "sandbox_uuid": agent_info.get("sandbox_uuid")
    })
    
    # Gather requested data types in parallel where possible
    tasks = {}
    
    if "state" in include:
        tasks["state"] = query_agent_state(event_emitter, agent_id)
        
    if "metadata" in include:
        tasks["metadata"] = query_agent_metadata(event_emitter, agent_id)
        
    if "relationships" in include:
        tasks["relationships"] = query_agent_relationships(event_emitter, agent_id)
    
    # Execute parallel queries
    if tasks:
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for key, value in zip(tasks.keys(), results):
            if not isinstance(value, Exception):
                result[key] = value
            else:
                logger.warning(f"Failed to gather {key} for agent {agent_id}: {value}")
                result[key] = None
    
    return result


def extract_first_result(response: Any) -> Any:
    """
    Extract first result from response handling multiple patterns.
    
    KSI responses can be:
    - Direct dict/value
    - List with single dict
    - List with multiple dicts (take first)
    - Empty list (return empty dict)
    
    This is an alias for unwrap_list_response for clarity.
    """
    return unwrap_list_response(response)


async def batch_query_state_entities(event_emitter: Callable, entity_type: str,
                                   filters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Batch query multiple entities from state system.
    
    Args:
        event_emitter: Event emitter function
        entity_type: Type of entities to query
        filters: List of filter dicts for each query
        
    Returns:
        List of entity results (None for not found)
    """
    if not event_emitter or not filters:
        return []
        
    # Execute queries in parallel
    tasks = []
    for filter_dict in filters:
        query_data = {"type": entity_type, "filter": filter_dict}
        tasks.append(event_emitter({
            "event": "state:entity:search",
            "data": query_data
        }))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    entities = []
    for result in results:
        if isinstance(result, Exception):
            entities.append(None)
        else:
            result = extract_single_response(result)
            # result should now be the search response, check if it has entities
            if result and result.get('entities') and len(result['entities']) > 0:
                entities.append(result['entities'][0])
            else:
                entities.append(None)
                
    return entities


# REMOVED: validate_event_handler_data - deprecated with raw_data pattern