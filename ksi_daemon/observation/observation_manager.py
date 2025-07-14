#!/usr/bin/env python3
"""
Observation Manager

Manages ephemeral observation subscriptions between agents, allowing observers to
receive events from target agents. Subscriptions are memory-only routing rules
that must be re-established on system startup, with checkpoint/restore capability
for system continuity scenarios.
"""

import asyncio
import json
import uuid
import fnmatch
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any, TypedDict, Literal
from typing_extensions import NotRequired, Required

from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc
from ksi_common.event_parser import event_format_linter
from ksi_common.event_response_builder import event_response_builder, error_response
from ksi_daemon.event_system import event_handler, get_router, RateLimiter


logger = get_bound_logger("observation_manager")

# Module state
_subscriptions: Dict[str, List[Dict[str, Any]]] = {}  # target_id -> subscriptions
_observers: Dict[str, Set[str]] = {}  # observer_id -> set of target_ids
_event_emitter = None
_rate_limiters: Dict[str, RateLimiter] = {}  # subscription_id -> rate limiter

# Async observation processing
_observation_queue: Optional[asyncio.Queue] = None
_observation_task: Optional[asyncio.Task] = None

# Circuit breaker state
_observer_failures = defaultdict(list)  # observer_id -> list of failure timestamps
_observer_circuit_open = {}  # observer_id -> circuit open until timestamp

# Track if subscriptions were restored from checkpoint
_subscriptions_restored_from_checkpoint = False


# TypedDict definitions for event handlers

class SystemContextData(TypedDict):
    """System context with runtime references."""
    emit_event: NotRequired[Any]  # Event emitter function
    shutdown_event: NotRequired[Any]  # Shutdown event object


class SystemReadyData(TypedDict):
    """System ready notification."""
    # No specific fields for observation manager
    pass


class AgentTerminatedData(TypedDict):
    """Agent termination notification."""
    agent_id: Required[str]  # Terminated agent ID


class ObservationSubscribeData(TypedDict):
    """Subscribe to observe events from a target agent."""
    observer: Required[str]  # Observer agent ID
    target: Required[str]  # Target agent ID to observe
    events: Required[List[str]]  # Event patterns to observe
    filter: NotRequired[Dict[str, Any]]  # Optional filters


class ObservationUnsubscribeData(TypedDict):
    """Unsubscribe from observing a target."""
    subscription_id: NotRequired[str]  # Subscription ID to cancel
    observer: NotRequired[str]  # Observer agent ID (required if no subscription_id)
    target: NotRequired[str]  # Target agent ID (required if no subscription_id)


class ObservationListData(TypedDict):
    """List active observation subscriptions."""
    observer: NotRequired[str]  # Filter by observer (optional)
    target: NotRequired[str]  # Filter by target (optional)


class CheckpointCollectData(TypedDict):
    """Collect checkpoint data."""
    # No specific fields - collects all observation state
    pass


class CheckpointRestoreData(TypedDict):
    """Restore from checkpoint data."""
    observation_subscriptions: NotRequired[Dict[str, Any]]  # Observation subscriptions to restore


@event_handler("system:context")
async def handle_context(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
    """Receive system context with event emitter."""
    data = event_format_linter(raw_data, SystemContextData)
    global _event_emitter
    router = get_router()
    _event_emitter = router.emit
    logger.info("Observation manager initialized")


@event_handler("system:ready")
async def observation_system_ready(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Signal that observation system is ready for subscriptions.
    
    The daemon always checks for checkpoints on startup. We only emit
    observation:ready if subscriptions were NOT restored from checkpoint,
    indicating agents need to re-establish them.
    """
    data = event_format_linter(raw_data, SystemReadyData)
    global _observation_queue, _observation_task
    
    # Start async observation processor
    _observation_queue = asyncio.Queue(maxsize=1000)
    _observation_task = asyncio.create_task(_process_observations())
    
    # Check if subscriptions were restored from checkpoint
    if _subscriptions_restored_from_checkpoint:
        logger.info(f"Observation system ready - {len(_observers)} observers with "
                   f"subscriptions restored from checkpoint")
        # Don't emit observation:ready - subscriptions were already restored
    else:
        logger.info("Observation system ready - no subscriptions restored, "
                   "agents must re-establish subscriptions")
        # Emit observation:ready for agents to re-subscribe
        await _event_emitter("observation:ready", {
            "status": "ready",
            "ephemeral": True,
            "message": "Subscriptions must be re-established by agents"
        })
    
    return event_response_builder({
        "status": "ready",
        "subscriptions_restored": _subscriptions_restored_from_checkpoint,
        "subscriptions_active": len(_observers)
    }, context)


@event_handler("agent:terminated")
async def cleanup_agent_subscriptions(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Remove all subscriptions for terminated agent."""
    data = event_format_linter(raw_data, AgentTerminatedData)
    agent_id = data.get("agent_id")
    if not agent_id:
        return error_response("No agent_id provided", context)
    
    removed_count = 0
    
    # Remove as observer
    if agent_id in _observers:
        targets = list(_observers[agent_id])
        for target in targets:
            if target in _subscriptions:
                before = len(_subscriptions[target])
                _subscriptions[target] = [
                    sub for sub in _subscriptions[target]
                    if sub["observer"] != agent_id
                ]
                removed_count += before - len(_subscriptions[target])
                
                # Clean up empty lists
                if not _subscriptions[target]:
                    del _subscriptions[target]
        
        del _observers[agent_id]
        logger.info(f"Removed {agent_id} as observer of {len(targets)} targets")
    
    # Remove as target
    if agent_id in _subscriptions:
        observer_count = len(_subscriptions[agent_id])
        
        # Notify observers that target is gone
        for subscription in _subscriptions[agent_id]:
            observer_id = subscription["observer"]
            await _event_emitter("observation:target_terminated", {
                "observer": observer_id,
                "target": agent_id,
                "subscription_id": subscription["id"]
            })
        
        del _subscriptions[agent_id]
        removed_count += observer_count
        logger.info(f"Removed {observer_count} observers of {agent_id}")
    
    # Clean up rate limiters
    keys_to_remove = [
        key for key in _rate_limiters.keys()
        if key.startswith(f"{agent_id}_") or key.endswith(f"_{agent_id}")
    ]
    for key in keys_to_remove:
        del _rate_limiters[key]
    
    return event_response_builder({
        "agent_id": agent_id,
        "subscriptions_removed": removed_count,
        "status": "cleaned"
    }, context)


@event_handler("observation:subscribe")
async def handle_subscribe(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Subscribe to observe events from a target agent."""
    data = event_format_linter(raw_data, ObservationSubscribeData)
    observer_id = data.get("observer")
    target_id = data.get("target")
    event_patterns = data.get("events", [])
    
    if not all([observer_id, target_id, event_patterns]):
        return error_response("observer, target, and events are required", context)
    
    # Validate agents exist
    if _event_emitter:
        # Check observer exists
        observer_result = await _event_emitter("state:entity:get", {
            "id": observer_id,
            "type": "agent"
        })
        
        # Handle list response format
        if isinstance(observer_result, list):
            observer_result = observer_result[0] if observer_result else {}
        
        if observer_result.get("error") or not observer_result.get("entity"):
            return error_response(f"Observer agent {observer_id} not found", context)
        
        # Check target exists
        target_result = await _event_emitter("state:entity:get", {
            "id": target_id,
            "type": "agent"
        })
        
        # Handle list response format
        if isinstance(target_result, list):
            target_result = target_result[0] if target_result else {}
        
        if target_result.get("error") or not target_result.get("entity"):
            return error_response(f"Target agent {target_id} not found", context)
    
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
    
    # Create rate limiter if specified
    rate_limit_config = data.get("filter", {}).get("rate_limit", {})
    if rate_limit_config:
        max_events = rate_limit_config.get("max_events", 10)
        window_seconds = rate_limit_config.get("window_seconds", 1.0)
        _rate_limiters[subscription_id] = RateLimiter(max_events, window_seconds)
    
    # Subscriptions are ephemeral - they will not survive restart unless checkpoint/restore is used
    logger.info(f"Created ephemeral subscription {subscription_id}: {observer_id} observing {target_id} (will not survive restart)")
    
    return event_response_builder({
        "subscription_id": subscription_id,
        "observer": observer_id,
        "target": target_id,
        "events": event_patterns,
        "status": "active"
    }, context)


@event_handler("observation:unsubscribe")
async def handle_unsubscribe(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Unsubscribe from observing a target."""
    data = event_format_linter(raw_data, ObservationUnsubscribeData)
    subscription_id = data.get("subscription_id")
    observer_id = data.get("observer")
    target_id = data.get("target")
    
    if not subscription_id and not (observer_id and target_id):
        return error_response("Either subscription_id or both observer and target required", context)
    
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
                    
                    # Clean up rate limiter if exists
                    if sub["id"] in _rate_limiters:
                        del _rate_limiters[sub["id"]]
    else:
        # Remove all subscriptions between observer and target
        if target_id in _subscriptions:
            for sub in _subscriptions[target_id][:]:
                if sub["observer"] == observer_id:
                    _subscriptions[target_id].remove(sub)
                    unsubscribed.append(sub)
                    
                    # Clean up rate limiter if exists
                    if sub["id"] in _rate_limiters:
                        del _rate_limiters[sub["id"]]
            
            # Clean up empty lists
            if not _subscriptions[target_id]:
                del _subscriptions[target_id]
        
        # Update observer tracking
        if observer_id in _observers:
            _observers[observer_id].discard(target_id)
            if not _observers[observer_id]:
                del _observers[observer_id]
    
    logger.info(f"Unsubscribed {len(unsubscribed)} ephemeral subscriptions")
    
    return event_response_builder({
        "unsubscribed": len(unsubscribed),
        "subscription_ids": [sub["id"] for sub in unsubscribed]
    }, context)


@event_handler("observation:list")
async def handle_list_observations(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """List active observation subscriptions."""
    data = event_format_linter(raw_data, ObservationListData)
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
    
    return event_response_builder({
        "subscriptions": subscriptions,
        "count": len(subscriptions)
    }, context)


def should_observe_event(event_name: str, source_agent: str, 
                        data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Check if an event should be observed and return matching subscriptions.
    
    Args:
        event_name: The event being emitted
        source_agent: The agent emitting the event
        data: Event data for content filtering
    
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
        
        # Check content matching if specified
        content_match = filters.get("content_match", {})
        if content_match and data:
            field = content_match.get("field")
            expected_value = content_match.get("value")
            pattern = content_match.get("pattern")
            operator = content_match.get("operator", "equals")
            
            if field:
                # Navigate to field value
                current = data
                for part in field.split("."):
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        continue  # Skip this subscription if field not found
                
                # Check value/pattern
                if expected_value is not None:
                    if operator == "equals" and current != expected_value:
                        continue
                    elif operator == "contains" and expected_value not in str(current):
                        continue
                    elif operator == "gt" and not (current > expected_value):
                        continue
                    elif operator == "lt" and not (current < expected_value):
                        continue
                elif pattern:
                    if not fnmatch.fnmatch(str(current), pattern):
                        continue
        
        # Check sampling rate
        sampling_rate = filters.get("sampling_rate", 1.0)
        if sampling_rate < 1.0:
            # Simple sampling - could be improved with deterministic sampling
            import random
            if random.random() > sampling_rate:
                continue
        
        # Check rate limit if configured
        subscription_id = subscription.get("id")
        if subscription_id and subscription_id in _rate_limiters:
            rate_limiter = _rate_limiters[subscription_id]
            # Create a context-like dict for the rate limiter
            context = {"agent_id": source_agent}
            if not rate_limiter(event_name, data or {}, context):
                logger.debug(f"Rate limit exceeded for subscription {subscription_id}")
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


async def _process_observations():
    """Process observations asynchronously to avoid blocking event emission."""
    while True:
        try:
            batch = []
            # Collect up to 10 observations or wait 100ms
            deadline = asyncio.get_event_loop().time() + 0.1
            
            while len(batch) < 10:
                try:
                    timeout = max(0, deadline - asyncio.get_event_loop().time())
                    item = await asyncio.wait_for(
                        _observation_queue.get(), 
                        timeout=timeout
                    )
                    batch.append(item)
                except asyncio.TimeoutError:
                    break
            
            if batch:
                await _process_observation_batch(batch)
                
        except asyncio.CancelledError:
            logger.info("Observation processor task cancelled")
            break
        except Exception as e:
            logger.error(f"Observation processor error: {e}")
            await asyncio.sleep(1)  # Back off on errors


async def _process_observation_batch(batch: List[Dict[str, Any]]):
    """Process a batch of observations."""
    for item in batch:
        subscriptions = item["subscriptions"]
        event_type = item["event_type"]
        event_name = item["event_name"]
        data = item["data"]
        source_agent = item["source_agent"]
        
        # Process each subscription with circuit breaker
        for subscription in subscriptions:
            observer_id = subscription["observer"]
            
            # Check circuit breaker
            if await _notify_observer_with_circuit_breaker(
                observer_id, event_type, event_name, data, source_agent, subscription
            ):
                logger.debug(f"Successfully notified {observer_id}")
            else:
                logger.warning(f"Failed to notify {observer_id} (circuit breaker)")


async def _notify_observer_with_circuit_breaker(
    observer_id: str, 
    event_type: str,
    event_name: str,
    data: Dict[str, Any],
    source_agent: str,
    subscription: Dict[str, Any]
) -> bool:
    """Notify observer with circuit breaker pattern."""
    # Check if circuit is open
    if observer_id in _observer_circuit_open:
        if datetime.now() < _observer_circuit_open[observer_id]:
            logger.warning(f"Circuit open for observer {observer_id}")
            return False
        else:
            # Try to close circuit
            del _observer_circuit_open[observer_id]
            logger.info(f"Closing circuit for observer {observer_id}")
    
    try:
        observation_id = f"obs_{uuid.uuid4().hex[:8]}"
        
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
        
        # Send observation
        result = await _event_emitter(f"observe:{event_type}", observation_event)
        
        if result and isinstance(result, list):
            result = result[0] if result else {}
            
        if result.get("error"):
            raise Exception(result["error"])
        
        # Success - clear failures
        if observer_id in _observer_failures:
            del _observer_failures[observer_id]
        
        return True
        
    except Exception as e:
        # Record failure
        _observer_failures[observer_id].append(datetime.now())
        
        # Keep only recent failures (last 5 minutes)
        cutoff = datetime.now() - timedelta(minutes=5)
        _observer_failures[observer_id] = [
            f for f in _observer_failures[observer_id] 
            if f > cutoff
        ]
        
        # Open circuit if too many failures
        if len(_observer_failures[observer_id]) >= 5:
            _observer_circuit_open[observer_id] = datetime.now() + timedelta(minutes=1)
            logger.error(f"Opening circuit for observer {observer_id} due to repeated failures")
        
        return False


# Modified notify_observers to use async queue
async def notify_observers_async(subscriptions: List[Dict[str, Any]], event_type: str, 
                               event_name: str, data: Dict[str, Any], 
                               source_agent: str) -> None:
    """Queue observations for async processing."""
    if not _event_emitter or not _observation_queue:
        return
    
    # Queue the observation for async processing
    try:
        await _observation_queue.put({
            "subscriptions": subscriptions,
            "event_type": event_type,
            "event_name": event_name,
            "data": data,
            "source_agent": source_agent
        })
    except asyncio.QueueFull:
        logger.warning("Observation queue full, dropping observation")


@event_handler("checkpoint:collect")
async def collect_observation_state(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Collect observation subscriptions for checkpoint.
    
    Only called during system checkpoint operations.
    Normal restarts do NOT trigger this.
    """
    data = event_format_linter(raw_data, CheckpointCollectData)
    # Flatten subscription data for storage
    subscriptions = []
    for target_id, target_subs in _subscriptions.items():
        for sub in target_subs:
            subscriptions.append({
                "id": sub["id"],
                "observer": sub["observer"],
                "target": target_id,
                "events": sub["events"],
                "filter": sub.get("filter", {}),
                "metadata": sub.get("metadata", {})
            })
    
    logger.info(f"Checkpointing {len(subscriptions)} active subscriptions")
    
    return event_response_builder({
        "observation_subscriptions": {
            "version": "1.0",
            "subscriptions": subscriptions,
            "checkpointed_at": timestamp_utc()
        }
    }, context)


@event_handler("checkpoint:restore")
async def restore_observation_state(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Restore observation subscriptions from checkpoint.
    
    Only called during checkpoint restore operations.
    Sets the module flag to indicate if subscriptions were restored.
    """
    data = event_format_linter(raw_data, CheckpointRestoreData)
    global _subscriptions_restored_from_checkpoint
    
    checkpoint_data = data.get("observation_subscriptions", {})
    if not checkpoint_data:
        logger.info("No observation subscriptions in checkpoint")
        _subscriptions_restored_from_checkpoint = False
        return event_response_builder({"restored": 0}, context)
    
    subscriptions = checkpoint_data.get("subscriptions", [])
    restored = 0
    
    # Clear current state
    _subscriptions.clear()
    _observers.clear()
    _rate_limiters.clear()
    _observer_failures.clear()
    _observer_circuit_open.clear()
    
    # Restore each subscription
    for sub in subscriptions:
        try:
            # Reconstruct internal state
            target_id = sub["target"]
            observer_id = sub["observer"]
            
            if target_id not in _subscriptions:
                _subscriptions[target_id] = []
            
            _subscriptions[target_id].append({
                "id": sub["id"],
                "observer": observer_id,
                "events": sub["events"],
                "filter": sub.get("filter", {}),
                "metadata": sub.get("metadata", {})
            })
            
            if observer_id not in _observers:
                _observers[observer_id] = set()
            _observers[observer_id].add(target_id)
            
            # Recreate rate limiter if needed
            rate_limit_config = sub.get("filter", {}).get("rate_limit")
            if rate_limit_config:
                _rate_limiters[sub["id"]] = RateLimiter(
                    max_events=rate_limit_config["max_events"],
                    window_seconds=rate_limit_config["window_seconds"]
                )
            
            restored += 1
            
        except Exception as e:
            logger.error(f"Failed to restore subscription {sub.get('id')}: {e}")
    
    # Set flag indicating if we actually restored any subscriptions
    _subscriptions_restored_from_checkpoint = (restored > 0)
    
    logger.info(f"Restored {restored}/{len(subscriptions)} observation subscriptions")
    
    # Notify that observations were restored (different from observation:ready)
    if restored > 0:
        await _event_emitter("observation:restored", {
            "subscriptions_restored": restored,
            "from_checkpoint": checkpoint_data.get("checkpointed_at")
        })
    
    return event_response_builder({"restored": restored}, context)


# Export key functions for event router integration
__all__ = ["should_observe_event", "notify_observers", "notify_observers_async"]