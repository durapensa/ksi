#!/usr/bin/env python3
"""
Enhanced Message Bus - Supports targeted pub/sub and direct delivery

Improvements over basic message bus:
1. Targeted subscriptions with topics/filters
2. Direct delivery for point-to-point messages
3. Channel-based subscriptions (e.g., "completions/<client_id>")
"""

import asyncio
import json
import re
from typing import Dict, List, Set, Optional, Any, Tuple, Callable
from collections import defaultdict
import time

from .timestamp_utils import TimestampManager
from .config import config
from .logging_config import get_logger, log_event, agent_context
from .event_taxonomy import MESSAGE_BUS_EVENTS, format_agent_event
from .message_bus import MessageBus

logger = get_logger(__name__)


class EnhancedMessageBus(MessageBus):
    """Enhanced message bus with targeted pub/sub support"""
    
    def __init__(self):
        super().__init__()
        
        # Enhanced subscriptions with filters
        # Format: (event_pattern, filter_func) -> set of (agent_id, writer)
        self.filtered_subscriptions: Dict[Tuple[str, Optional[Callable]], Set[tuple]] = defaultdict(set)
        
        # Channel subscriptions: channel_pattern -> set of (agent_id, writer)
        self.channel_subscriptions: Dict[str, Set[tuple]] = defaultdict(set)
        
        # Direct delivery optimization for specific event types
        self.direct_delivery_events = {'COMPLETION_RESULT', 'DIRECT_MESSAGE'}
    
    def subscribe_with_filter(self, agent_id: str, event_pattern: str, 
                            filter_func: Optional[Callable[[dict], bool]] = None):
        """
        Subscribe to events with optional filter function.
        
        Args:
            agent_id: Agent identifier
            event_pattern: Event type pattern (supports wildcards)
            filter_func: Optional function to filter events
        """
        writer = self.connections.get(agent_id)
        if not writer:
            return False
        
        key = (event_pattern, filter_func)
        self.filtered_subscriptions[key].add((agent_id, writer))
        
        log_event(logger, "message_bus.filtered_subscription",
                 agent_id=agent_id,
                 event_pattern=event_pattern,
                 has_filter=filter_func is not None)
        
        return True
    
    def subscribe_to_channel(self, agent_id: str, channel: str):
        """
        Subscribe to a specific channel (e.g., "completions/client_123").
        
        Args:
            agent_id: Agent identifier
            channel: Channel path
        """
        writer = self.connections.get(agent_id)
        if not writer:
            return False
        
        self.channel_subscriptions[channel].add((agent_id, writer))
        
        log_event(logger, "message_bus.channel_subscription",
                 agent_id=agent_id,
                 channel=channel)
        
        return True
    
    async def publish_to_channel(self, channel: str, message: dict) -> dict:
        """
        Publish message to a specific channel.
        
        Args:
            channel: Target channel
            message: Message to publish
        """
        subscribers = self.channel_subscriptions.get(channel, set())
        delivered = []
        
        for agent_id, writer in subscribers:
            try:
                await self._send_message(writer, message)
                delivered.append(agent_id)
            except Exception as e:
                logger.error(f"Failed to deliver to {agent_id} on channel {channel}: {e}")
        
        # Also check wildcard subscriptions
        for pattern, subs in self.channel_subscriptions.items():
            if '*' in pattern and self._matches_pattern(channel, pattern):
                for agent_id, writer in subs:
                    if agent_id not in delivered:  # Avoid duplicates
                        try:
                            await self._send_message(writer, message)
                            delivered.append(agent_id)
                        except Exception as e:
                            logger.error(f"Failed to deliver to {agent_id} on pattern {pattern}: {e}")
        
        return {
            'status': 'published',
            'channel': channel,
            'delivered_to': delivered
        }
    
    async def publish_targeted(self, from_agent: str, event_type: str, 
                             target: str, payload: dict) -> dict:
        """
        Publish event with specific target (direct delivery).
        
        Args:
            from_agent: Sender agent ID
            event_type: Event type
            target: Target agent ID or client ID
            payload: Event payload
        """
        # Create targeted message
        message = {
            'id': str(time.time()),
            'type': event_type,
            'from': from_agent,
            'to': target,  # Specific target
            'timestamp': TimestampManager.format_for_message_bus(),
            **payload
        }
        
        # Direct delivery if target is connected
        if target in self.connections:
            writer = self.connections[target]
            try:
                await self._send_message(writer, message)
                return {'status': 'delivered', 'to': target}
            except Exception as e:
                logger.error(f"Failed to deliver {event_type} to {target}: {e}")
                # Fall back to queue
                self.offline_queue[target].append(message)
                return {'status': 'queued', 'to': target, 'error': str(e)}
        else:
            # Queue for offline delivery
            self.offline_queue[target].append(message)
            return {'status': 'queued', 'to': target}
    
    async def publish(self, from_agent: str, event_type: str, payload: dict) -> dict:
        """
        Enhanced publish with smart routing.
        
        Automatically uses targeted delivery for certain event types.
        """
        # Check if this should be direct delivery
        if event_type in self.direct_delivery_events:
            # Extract target from payload
            target = payload.get('to') or payload.get('client_id')
            if target:
                return await self.publish_targeted(from_agent, event_type, target, payload)
        
        # Otherwise use standard broadcast
        return await super().publish(from_agent, event_type, payload)
    
    def subscribe_dynamic(self, agent_id: str, event_patterns: List[str]):
        """
        Subscribe to dynamic event patterns.
        
        Supports patterns like:
        - "COMPLETION_RESULT:client_123" - Specific client results
        - "COMPLETION_RESULT:*" - All completion results
        - "*/client_123" - All events for specific client
        """
        writer = self.connections.get(agent_id)
        if not writer:
            return False
        
        for pattern in event_patterns:
            if ':' in pattern or '*' in pattern:
                # Dynamic pattern
                self.filtered_subscriptions[(pattern, None)].add((agent_id, writer))
            else:
                # Standard event type
                self.subscriptions[pattern].add((agent_id, writer))
        
        return True
    
    async def _handle_generic_event(self, event_type: str, message: dict) -> dict:
        """Enhanced generic event handling with pattern matching"""
        delivered = []
        
        # Standard subscribers
        subscribers = self.subscriptions.get(event_type, set())
        for agent_id, writer in subscribers:
            try:
                await self._send_message(writer, message)
                delivered.append(agent_id)
            except Exception as e:
                logger.error(f"Failed to deliver {event_type} to {agent_id}: {e}")
        
        # Check filtered/pattern subscriptions
        for (pattern, filter_func), subs in self.filtered_subscriptions.items():
            if self._matches_event_pattern(event_type, pattern, message):
                # Apply filter if provided
                if filter_func and not filter_func(message):
                    continue
                    
                for agent_id, writer in subs:
                    if agent_id not in delivered:  # Avoid duplicates
                        try:
                            await self._send_message(writer, message)
                            delivered.append(agent_id)
                        except Exception as e:
                            logger.error(f"Failed to deliver {event_type} to {agent_id}: {e}")
        
        return {
            'status': 'published',
            'event_type': event_type,
            'delivered_to': delivered
        }
    
    def _matches_pattern(self, value: str, pattern: str) -> bool:
        """Check if value matches wildcard pattern"""
        # Convert wildcard pattern to regex
        regex_pattern = pattern.replace('*', '.*')
        return bool(re.match(f"^{regex_pattern}$", value))
    
    def _matches_event_pattern(self, event_type: str, pattern: str, message: dict) -> bool:
        """Check if event matches pattern (supports dynamic patterns)"""
        if ':' in pattern:
            # Dynamic pattern like "COMPLETION_RESULT:client_123"
            pattern_type, pattern_id = pattern.split(':', 1)
            
            # Check event type
            if pattern_type != '*' and not self._matches_pattern(event_type, pattern_type):
                return False
            
            # Check ID match
            if pattern_id != '*':
                # Look for client_id or target in message
                msg_id = message.get('client_id') or message.get('to') or message.get('from')
                if not msg_id or not self._matches_pattern(msg_id, pattern_id):
                    return False
            
            return True
        else:
            # Simple pattern
            return self._matches_pattern(event_type, pattern)

