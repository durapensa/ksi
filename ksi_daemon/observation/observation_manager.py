#!/usr/bin/env python3
"""
Observation Manager

Manages observation subscriptions between agents, allowing originators to observe
events from their constructs or other agents. Built on the relational state system.
"""

import asyncio
import json
import uuid
import fnmatch
from typing import Dict, List, Set, Optional, Any

from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc
from ksi_daemon.event_system import event_handler, get_router


logger = get_bound_logger("observation_manager")

# Module state
_subscriptions: Dict[str, List[Dict[str, Any]]] = {}  # target_id -> subscriptions
_observers: Dict[str, Set[str]] = {}  # observer_id -> set of target_ids
_event_emitter = None


@event_handler("system:context")
async def handle_context(context: Dict[str, Any]) -> None:
    """Receive system context with event emitter."""
    global _event_emitter
    router = get_router()
    _event_emitter = router.emit
    logger.info("Observation manager initialized")


@event_handler("observation:subscribe")
async def handle_subscribe(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Subscribe to observe events from a target agent.
    
    Args:
        observer (str): Observer agent ID (required)
        target (str): Target agent ID to observe (required)
        events (list): Event patterns to observe (required)
        filter (dict): Optional filters:
            - exclude (list): Patterns to exclude
            - include_responses (bool): Include completion responses
            - sampling_rate (float): 0.0-1.0, fraction of events to observe
    
    Returns:
        Subscription details with ID
    
    Example:
        {
            "observer": "originator_1",
            "target": "construct_1",
            "events": ["message:*", "error:*"],
            "filter": {
                "exclude": ["system:health"],
                "include_responses": true,
                "sampling_rate": 1.0
            }
        }
    """
    observer_id = data.get("observer")
    target_id = data.get("target")
    event_patterns = data.get("events", [])
    
    if not all([observer_id, target_id, event_patterns]):
        return {"error": "observer, target, and events are required"}
    
    # Create subscription
    subscription_id = f"sub_{uuid.uuid4().hex[:8]}"
    subscription = {
        "id": subscription_id,
        "observer": observer_id,
        "target": target_id,
        "events": event_patterns,
        "filter": data.get("filter", {}),
        "created_at": timestamp_utc(),
        "active": True
    }
    
    # Store in memory
    if target_id not in _subscriptions:
        _subscriptions[target_id] = []
    _subscriptions[target_id].append(subscription)
    
    if observer_id not in _observers:
        _observers[observer_id] = set()
    _observers[observer_id].add(target_id)
    
    # Store in relational state if available
    if _event_emitter:
        # Create subscription entity
        entity_result = await _event_emitter("state:entity:create", {
            "type": "observation_subscription",
            "id": subscription_id,
            "properties": {
                "observer_id": observer_id,
                "target_id": target_id,
                "event_patterns": event_patterns,
                "filters": json.dumps(subscription["filter"]),
                "active": True
            }
        })
        
        if entity_result and isinstance(entity_result, list):
            entity_result = entity_result[0] if entity_result else {}
        
        if entity_result and "error" not in entity_result:
            logger.debug(f"Created subscription entity {subscription_id}")
        
        # Create observes relationship
        rel_result = await _event_emitter("state:relationship:create", {
            "from": observer_id,
            "to": target_id,
            "type": "observes",
            "metadata": {
                "subscription_id": subscription_id,
                "patterns": event_patterns
            }
        })
        
        if rel_result and isinstance(rel_result, list):
            rel_result = rel_result[0] if rel_result else {}
        
        if rel_result and rel_result.get("status") == "created":
            logger.info(f"Created observes relationship: {observer_id} -> {target_id}")
    
    logger.info(f"Created observation subscription {subscription_id}: {observer_id} observing {target_id}")
    
    return {
        "subscription_id": subscription_id,
        "observer": observer_id,
        "target": target_id,
        "events": event_patterns,
        "status": "active"
    }


@event_handler("observation:unsubscribe")
async def handle_unsubscribe(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Unsubscribe from observing a target.
    
    Args:
        subscription_id (str): Subscription ID to cancel (if provided)
        observer (str): Observer agent ID (required if no subscription_id)
        target (str): Target agent ID (required if no subscription_id)
    
    Returns:
        Unsubscribe status
    """
    subscription_id = data.get("subscription_id")
    observer_id = data.get("observer")
    target_id = data.get("target")
    
    if not subscription_id and not (observer_id and target_id):
        return {"error": "Either subscription_id or both observer and target required"}
    
    unsubscribed = []
    
    # Find subscriptions to remove
    if subscription_id:
        # Remove specific subscription
        for target, subs in _subscriptions.items():
            for sub in subs[:]:  # Copy to allow removal during iteration
                if sub["id"] == subscription_id:
                    subs.remove(sub)
                    unsubscribed.append(sub)
                    
                    # Update observer tracking
                    obs_id = sub["observer"]
                    if obs_id in _observers:
                        _observers[obs_id].discard(target)
                        if not _observers[obs_id]:
                            del _observers[obs_id]
    else:
        # Remove all subscriptions between observer and target
        if target_id in _subscriptions:
            for sub in _subscriptions[target_id][:]:
                if sub["observer"] == observer_id:
                    _subscriptions[target_id].remove(sub)
                    unsubscribed.append(sub)
            
            # Clean up empty lists
            if not _subscriptions[target_id]:
                del _subscriptions[target_id]
        
        # Update observer tracking
        if observer_id in _observers:
            _observers[observer_id].discard(target_id)
            if not _observers[observer_id]:
                del _observers[observer_id]
    
    # Update state for each unsubscribed
    if _event_emitter:
        for sub in unsubscribed:
            # Update subscription entity
            await _event_emitter("state:entity:update", {
                "id": sub["id"],
                "properties": {"active": False}
            })
            
            # Could also delete the observes relationship here if desired
    
    logger.info(f"Unsubscribed {len(unsubscribed)} subscriptions")
    
    return {
        "unsubscribed": len(unsubscribed),
        "subscription_ids": [sub["id"] for sub in unsubscribed]
    }


@event_handler("observation:list")
async def handle_list_observations(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    List active observation subscriptions.
    
    Args:
        observer (str): Filter by observer (optional)
        target (str): Filter by target (optional)
    
    Returns:
        List of active subscriptions
    """
    observer_filter = data.get("observer")
    target_filter = data.get("target")
    
    subscriptions = []
    
    for target_id, subs in _subscriptions.items():
        if target_filter and target_id != target_filter:
            continue
            
        for sub in subs:
            if observer_filter and sub["observer"] != observer_filter:
                continue
            
            if sub.get("active", True):
                subscriptions.append({
                    "subscription_id": sub["id"],
                    "observer": sub["observer"],
                    "target": sub["target"],
                    "events": sub["events"],
                    "created_at": sub.get("created_at")
                })
    
    return {
        "subscriptions": subscriptions,
        "count": len(subscriptions)
    }


def should_observe_event(event_name: str, source_agent: str) -> List[Dict[str, Any]]:
    """
    Check if an event should be observed and return matching subscriptions.
    
    Args:
        event_name: The event being emitted
        source_agent: The agent emitting the event
    
    Returns:
        List of subscriptions that match this event
    """
    if source_agent not in _subscriptions:
        return []
    
    matching_subscriptions = []
    
    for subscription in _subscriptions[source_agent]:
        if not subscription.get("active", True):
            continue
        
        # Check if event matches any patterns
        event_matched = False
        for pattern in subscription["events"]:
            if fnmatch.fnmatch(event_name, pattern):
                event_matched = True
                break
        
        if not event_matched:
            continue
        
        # Check exclusions
        filters = subscription.get("filter", {})
        exclude_patterns = filters.get("exclude", [])
        
        excluded = False
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(event_name, pattern):
                excluded = True
                break
        
        if excluded:
            continue
        
        # Check sampling rate
        sampling_rate = filters.get("sampling_rate", 1.0)
        if sampling_rate < 1.0:
            # Simple sampling - could be improved with deterministic sampling
            import random
            if random.random() > sampling_rate:
                continue
        
        matching_subscriptions.append(subscription)
    
    return matching_subscriptions


async def notify_observers(subscriptions: List[Dict[str, Any]], event_type: str, 
                         event_name: str, data: Dict[str, Any], 
                         source_agent: str) -> None:
    """
    Notify observers about an event.
    
    Args:
        subscriptions: List of subscriptions to notify
        event_type: "begin" or "end"
        event_name: The original event name
        data: Event data or result
        source_agent: The agent that emitted the event
    """
    if not _event_emitter:
        return
    
    observation_id = f"obs_{uuid.uuid4().hex[:8]}"
    
    for subscription in subscriptions:
        observer_id = subscription["observer"]
        
        observation_event = {
            "observation_id": observation_id,
            "subscription_id": subscription["id"],
            "source": source_agent,
            "observer": observer_id,
            "original_event": event_name,
            "timestamp": timestamp_utc()
        }
        
        if event_type == "begin":
            observation_event["original_data"] = data
        else:  # end
            observation_event["result"] = data
        
        # Emit observation event
        await _event_emitter(f"observe:{event_type}", observation_event)
        
        logger.debug(f"Notified {observer_id} about {event_type} of {event_name} from {source_agent}")


# Export key functions for event router integration
__all__ = ["should_observe_event", "notify_observers"]