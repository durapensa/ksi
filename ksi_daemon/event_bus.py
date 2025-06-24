#!/usr/bin/env python3
"""
Event Bus - Namespace-aware event routing with correlation support.

This is the new event bus for the plugin architecture, replacing the message bus
for internal event routing. Supports:
- Hierarchical namespaces (e.g., /completion, /agent, /message)
- Event correlation for request/response patterns
- Event replay for debugging
- Wildcard subscriptions
"""

import asyncio
import json
import time
import uuid
from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from collections import defaultdict
from dataclasses import dataclass, field
import fnmatch
import logging

from .plugin_types import EventMetadata
from .timestamp_utils import TimestampManager

logger = logging.getLogger(__name__)


@dataclass
class EventRecord:
    """Record of an event for history/replay."""
    metadata: EventMetadata
    event_name: str
    data: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    handlers_called: List[str] = field(default_factory=list)


@dataclass
class Subscription:
    """Event subscription details."""
    id: str
    subscriber: str
    patterns: List[str]
    handler: Callable
    namespace: Optional[str] = None
    created_at: float = field(default_factory=time.time)


class EventBus:
    """
    Central event bus for the plugin architecture.
    Routes events between plugins using namespaces and patterns.
    """
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize event bus.
        
        Args:
            max_history: Maximum events to keep in history
        """
        # Subscription tracking
        self.subscriptions: Dict[str, Subscription] = {}
        
        # Namespace registry: namespace -> set of subscriber IDs
        self.namespace_subscribers: Dict[str, Set[str]] = defaultdict(set)
        
        # Pattern subscriptions for wildcard matching
        self.pattern_subscriptions: List[Tuple[str, Subscription]] = []
        
        # Event correlation
        self.pending_correlations: Dict[str, asyncio.Future] = {}
        self.correlation_timeout = 30.0  # seconds
        
        # Event history for replay
        self.event_history: List[EventRecord] = []
        self.max_history = max_history
        
        # Statistics
        self.stats = {
            "events_emitted": 0,
            "events_handled": 0,
            "events_failed": 0,
            "active_subscriptions": 0,
            "active_correlations": 0
        }
        
        # Event validation schemas (event_name -> validator)
        self.event_schemas: Dict[str, Any] = {}
    
    def extract_namespace(self, event_name: str) -> Optional[str]:
        """
        Extract namespace from event name.
        
        Examples:
            "completion:request" -> "completion"
            "/agent/spawn" -> "/agent"
            "simple_event" -> None
        """
        if ":" in event_name:
            return event_name.split(":", 1)[0]
        elif "/" in event_name:
            parts = event_name.split("/")
            if event_name.startswith("/"):
                return "/" + parts[1] if len(parts) > 1 else "/"
            else:
                return parts[0]
        return None
    
    async def emit(self, event_name: str, data: Dict[str, Any], 
                   source: str = "unknown",
                   correlation_id: Optional[str] = None,
                   expect_response: bool = False) -> Optional[Dict[str, Any]]:
        """
        Emit an event to all matching subscribers.
        
        Args:
            event_name: Namespaced event name
            data: Event data
            source: Source plugin/component
            correlation_id: For request/response correlation
            expect_response: Wait for correlated response
            
        Returns:
            Response if expect_response=True, None otherwise
        """
        # Generate event ID
        event_id = str(uuid.uuid4())
        
        # Create metadata
        metadata = EventMetadata(
            id=event_id,
            name=event_name,
            source=source,
            timestamp=time.time(),
            correlation_id=correlation_id
        )
        
        # Create event record
        record = EventRecord(
            metadata=metadata,
            event_name=event_name,
            data=data
        )
        
        # Validate event if schema exists
        if event_name in self.event_schemas:
            try:
                validator = self.event_schemas[event_name]
                validated_data = validator(**data)
                data = validated_data.model_dump() if hasattr(validated_data, 'model_dump') else data
            except Exception as e:
                logger.error(f"Event validation failed for {event_name}: {e}")
                record.error = f"Validation error: {e}"
                self._add_to_history(record)
                self.stats["events_failed"] += 1
                return None
        
        # Set up correlation future if expecting response
        future = None
        if expect_response:
            future = asyncio.Future()
            self.pending_correlations[correlation_id or event_id] = future
            self.stats["active_correlations"] = len(self.pending_correlations)
        
        try:
            # Emit the event
            self.stats["events_emitted"] += 1
            logger.debug(f"Emitting event: {event_name} from {source}")
            
            # Route to subscribers
            handlers_called = await self._route_event(event_name, data, metadata)
            record.handlers_called = handlers_called
            
            if handlers_called:
                self.stats["events_handled"] += 1
            
            # Wait for response if requested
            if future:
                try:
                    result = await asyncio.wait_for(future, timeout=self.correlation_timeout)
                    record.result = result
                    return result
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout waiting for response to {event_name}")
                    record.error = "Response timeout"
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"Error emitting event {event_name}: {e}", exc_info=True)
            record.error = str(e)
            self.stats["events_failed"] += 1
            return None
            
        finally:
            # Clean up correlation
            if correlation_id or event_id in self.pending_correlations:
                self.pending_correlations.pop(correlation_id or event_id, None)
                self.stats["active_correlations"] = len(self.pending_correlations)
            
            # Add to history
            self._add_to_history(record)
    
    async def _route_event(self, event_name: str, data: Dict[str, Any], 
                          metadata: EventMetadata) -> List[str]:
        """Route event to all matching subscribers."""
        handlers_called = []
        namespace = self.extract_namespace(event_name)
        
        # Collect matching subscriptions
        matching_subs = []
        
        # Check namespace subscribers
        if namespace:
            for sub_id in self.namespace_subscribers.get(namespace, set()):
                if sub_id in self.subscriptions:
                    matching_subs.append(self.subscriptions[sub_id])
        
        # Check exact pattern matches
        for subscription in self.subscriptions.values():
            if event_name in subscription.patterns and subscription not in matching_subs:
                matching_subs.append(subscription)
        
        # Check wildcard patterns
        for pattern, subscription in self.pattern_subscriptions:
            if self._matches_pattern(event_name, pattern) and subscription not in matching_subs:
                matching_subs.append(subscription)
        
        # Call handlers
        for subscription in matching_subs:
            try:
                # Call handler
                result = await self._call_handler(subscription.handler, event_name, data, metadata)
                handlers_called.append(subscription.subscriber)
                
                # Handle correlation response
                if result and metadata.correlation_id:
                    await self._handle_correlation_response(metadata.correlation_id, result)
                
            except Exception as e:
                logger.error(f"Handler error in {subscription.subscriber}: {e}", exc_info=True)
        
        return handlers_called
    
    async def _call_handler(self, handler: Callable, event_name: str, 
                           data: Dict[str, Any], metadata: EventMetadata) -> Any:
        """Call event handler with proper signature."""
        # Check if handler expects metadata
        import inspect
        sig = inspect.signature(handler)
        params = list(sig.parameters.keys())
        
        if len(params) >= 3:
            # Handler expects metadata
            return await handler(event_name, data, metadata)
        else:
            # Legacy handler - just event name and data
            return await handler(event_name, data)
    
    def _matches_pattern(self, event_name: str, pattern: str) -> bool:
        """
        Check if event name matches pattern.
        
        Supports:
        - Exact match: "completion:request"
        - Wildcard: "completion:*", "*:request", "*"
        - Glob patterns: "agent:*:status"
        """
        return fnmatch.fnmatch(event_name, pattern)
    
    async def _handle_correlation_response(self, correlation_id: str, response: Any) -> None:
        """Handle correlated response."""
        future = self.pending_correlations.get(correlation_id)
        if future and not future.done():
            future.set_result(response)
    
    def subscribe(self, subscriber: str, patterns: List[str], 
                  handler: Callable,
                  namespace: Optional[str] = None) -> str:
        """
        Subscribe to event patterns.
        
        Args:
            subscriber: Name of subscribing component
            patterns: List of event patterns to match
            handler: Async function to call for matching events
            namespace: Optional namespace to subscribe to
            
        Returns:
            Subscription ID
        """
        sub_id = f"sub_{uuid.uuid4().hex[:8]}"
        
        subscription = Subscription(
            id=sub_id,
            subscriber=subscriber,
            patterns=patterns,
            handler=handler,
            namespace=namespace
        )
        
        self.subscriptions[sub_id] = subscription
        
        # Track namespace subscription
        if namespace:
            self.namespace_subscribers[namespace].add(sub_id)
        
        # Track pattern subscriptions
        for pattern in patterns:
            if "*" in pattern:
                self.pattern_subscriptions.append((pattern, subscription))
        
        self.stats["active_subscriptions"] = len(self.subscriptions)
        
        logger.info(f"{subscriber} subscribed to {patterns} (ID: {sub_id})")
        return sub_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from events.
        
        Args:
            subscription_id: ID returned from subscribe()
            
        Returns:
            True if unsubscribed successfully
        """
        if subscription_id not in self.subscriptions:
            return False
        
        subscription = self.subscriptions[subscription_id]
        
        # Remove from namespace tracking
        if subscription.namespace:
            self.namespace_subscribers[subscription.namespace].discard(subscription_id)
        
        # Remove from pattern tracking
        self.pattern_subscriptions = [
            (p, s) for p, s in self.pattern_subscriptions
            if s.id != subscription_id
        ]
        
        # Remove subscription
        del self.subscriptions[subscription_id]
        
        self.stats["active_subscriptions"] = len(self.subscriptions)
        
        logger.info(f"Unsubscribed {subscription_id}")
        return True
    
    def register_schema(self, event_name: str, schema: Any) -> None:
        """
        Register validation schema for an event.
        
        Args:
            event_name: Event name to validate
            schema: Pydantic model or validator
        """
        self.event_schemas[event_name] = schema
        logger.debug(f"Registered schema for {event_name}")
    
    def _add_to_history(self, record: EventRecord) -> None:
        """Add event to history."""
        self.event_history.append(record)
        
        # Trim history if needed
        if len(self.event_history) > self.max_history:
            self.event_history = self.event_history[-self.max_history:]
    
    async def replay_events(self, filter_fn: Optional[Callable[[EventRecord], bool]] = None,
                           handler: Optional[Callable] = None) -> List[EventRecord]:
        """
        Replay events from history.
        
        Args:
            filter_fn: Optional function to filter events
            handler: Optional handler to call for each event
            
        Returns:
            List of replayed events
        """
        replayed = []
        
        for record in self.event_history:
            if filter_fn and not filter_fn(record):
                continue
            
            replayed.append(record)
            
            if handler:
                try:
                    await handler(record.event_name, record.data, record.metadata)
                except Exception as e:
                    logger.error(f"Error replaying event: {e}")
        
        return replayed
    
    def get_namespace_info(self) -> Dict[str, Any]:
        """Get information about registered namespaces."""
        namespace_info = {}
        
        for namespace, sub_ids in self.namespace_subscribers.items():
            subscribers = []
            for sub_id in sub_ids:
                if sub_id in self.subscriptions:
                    sub = self.subscriptions[sub_id]
                    subscribers.append({
                        "subscriber": sub.subscriber,
                        "patterns": sub.patterns
                    })
            
            namespace_info[namespace] = {
                "subscriber_count": len(sub_ids),
                "subscribers": subscribers
            }
        
        return namespace_info
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        return {
            **self.stats,
            "history_size": len(self.event_history),
            "registered_schemas": len(self.event_schemas),
            "namespace_count": len(self.namespace_subscribers),
            "pattern_subscriptions": len(self.pattern_subscriptions)
        }
    
    def clear_history(self) -> None:
        """Clear event history."""
        self.event_history.clear()
        logger.info("Event history cleared")