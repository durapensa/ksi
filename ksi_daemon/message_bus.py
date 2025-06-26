#!/usr/bin/env python3
"""
Message Bus - Event-based message routing for agent communication
"""

import asyncio
import json
from typing import Dict, List, Set, Optional, Any
from collections import defaultdict
import time

from ksi_common import TimestampManager
from .config import config
from ksi_common import get_logger, log_event, agent_context
from .event_taxonomy import MESSAGE_BUS_EVENTS, format_agent_event

logger = get_logger(__name__)

class MessageBus:
    """Event-based message bus for inter-agent communication"""
    
    def __init__(self):
        # Subscriptions: event_type -> set of (agent_id, writer)
        self.subscriptions: Dict[str, Set[tuple]] = defaultdict(set)
        
        # Active connections: agent_id -> writer
        self.connections: Dict[str, asyncio.StreamWriter] = {}
        
        # Message queue for offline agents: agent_id -> list of messages
        self.offline_queue: Dict[str, List[dict]] = defaultdict(list)
        
        # Message history for debugging
        self.message_history = []
        self.max_history_size = 1000
        
    def connect_agent(self, agent_id: str, writer: asyncio.StreamWriter):
        """Register an agent connection"""
        self.connections[agent_id] = writer
        
        log_event(logger, "message_bus.agent_connected",
                 **format_agent_event("message_bus.agent_connected", agent_id,
                                     total_connections=len(self.connections),
                                     has_queued_messages=agent_id in self.offline_queue))
        
        # Deliver any queued messages
        if agent_id in self.offline_queue:
            asyncio.create_task(self._deliver_queued_messages(agent_id))
    
    def disconnect_agent(self, agent_id: str):
        """Remove agent connection"""
        was_connected = agent_id in self.connections
        
        if was_connected:
            del self.connections[agent_id]
            
        log_event(logger, "message_bus.agent_disconnected",
                 **format_agent_event("message_bus.agent_disconnected", agent_id,
                                     was_connected=was_connected,
                                     remaining_connections=len(self.connections)))
            
        # Remove from all subscriptions
        for event_type, subscribers in self.subscriptions.items():
            self.subscriptions[event_type] = {
                (aid, w) for aid, w in subscribers if aid != agent_id
            }
        
    
    def subscribe(self, agent_id: str, event_types: List[str]):
        """Subscribe an agent to event types"""
        writer = self.connections.get(agent_id)
        if not writer:
            log_event(logger, "message_bus.subscription_failed",
                     **format_agent_event("message_bus.subscription_failed", agent_id,
                                         event_types=event_types,
                                         reason="agent_not_connected"))
            return False
        
        for event_type in event_types:
            self.subscriptions[event_type].add((agent_id, writer))
        
        log_event(logger, "message_bus.subscribed",
                 **format_agent_event("message_bus.subscribed", agent_id,
                                     event_types=event_types,
                                     subscription_count=len(event_types)))
        
        return True
    
    def unsubscribe(self, agent_id: str, event_types: List[str]):
        """Unsubscribe an agent from event types"""
        for event_type in event_types:
            self.subscriptions[event_type].discard((agent_id, self.connections.get(agent_id)))
        
        log_event(logger, "message_bus.unsubscribed",
                 **format_agent_event("message_bus.unsubscribed", agent_id,
                                     event_types=event_types,
                                     unsubscription_count=len(event_types)))
    
    async def publish(self, from_agent: str, event_type: str, payload: dict) -> dict:
        """Publish an event to all subscribers"""
        # Create message
        message = {
            'id': str(time.time()),
            'type': event_type,
            'from': from_agent,
            'timestamp': TimestampManager.format_for_message_bus(),
            **payload
        }
        
        # Log to history
        self._add_to_history(message)
        
        # Log publication event
        log_event(logger, "message_bus.message_published",
                 **format_agent_event("message_bus.message_published", from_agent,
                                     event_type=event_type,
                                     message_id=message['id'],
                                     subscriber_count=len(self.subscriptions.get(event_type, []))))
        
        # Handle different event types
        if event_type == 'DIRECT_MESSAGE':
            return await self._handle_direct_message(message)
        elif event_type == 'BROADCAST':
            return await self._handle_broadcast(message)
        elif event_type == 'TASK_ASSIGNMENT':
            return await self._handle_task_assignment(message)
        else:
            # Generic event handling
            return await self._handle_generic_event(event_type, message)
    
    async def _handle_direct_message(self, message: dict) -> dict:
        """Handle direct message between agents"""
        to_agent = message.get('to')
        if not to_agent:
            return {'status': 'error', 'error': 'No recipient specified'}
        
        # First, notify all subscribers to DIRECT_MESSAGE events (like monitors)
        subscribers = self.subscriptions.get('DIRECT_MESSAGE', set())
        notified = []
        for agent_id, writer in subscribers:
            if agent_id != message.get('from'):  # Don't send back to sender
                try:
                    await self._send_message(writer, message)
                    notified.append(agent_id)
                except Exception as e:
                    logger.error(f"Failed to notify {agent_id} of DIRECT_MESSAGE: {e}")
        
        # Then deliver to the specific recipient
        if to_agent in self.connections:
            writer = self.connections[to_agent]
            try:
                await self._send_message(writer, message)
                return {'status': 'delivered', 'to': to_agent, 'notified': notified}
            except Exception as e:
                logger.error(f"Failed to deliver message to {to_agent}: {e}")
                self.offline_queue[to_agent].append(message)
                return {'status': 'queued', 'to': to_agent, 'error': str(e), 'notified': notified}
        else:
            # Queue for offline delivery
            self.offline_queue[to_agent].append(message)
            return {'status': 'queued', 'to': to_agent, 'notified': notified}
    
    async def _handle_broadcast(self, message: dict) -> dict:
        """Handle broadcast message to all subscribers"""
        subscribers = self.subscriptions.get('BROADCAST', set())
        delivered = []
        failed = []
        
        for agent_id, writer in subscribers:
            if agent_id != message.get('from'):  # Don't send back to sender
                try:
                    await self._send_message(writer, message)
                    delivered.append(agent_id)
                except Exception as e:
                    logger.error(f"Failed to broadcast to {agent_id}: {e}")
                    failed.append(agent_id)
        
        return {
            'status': 'broadcast',
            'delivered': delivered,
            'failed': failed,
            'total': len(delivered) + len(failed)
        }
    
    async def _handle_task_assignment(self, message: dict) -> dict:
        """Handle task assignment to specific agent"""
        to_agent = message.get('to')
        if not to_agent:
            # Find suitable agent based on capabilities
            required_capabilities = message.get('required_capabilities', [])
            to_agent = self._find_capable_agent(required_capabilities)
            if not to_agent:
                return {'status': 'error', 'error': 'No capable agent found'}
            message['to'] = to_agent
        
        # Deliver as direct message
        return await self._handle_direct_message(message)
    
    async def _handle_generic_event(self, event_type: str, message: dict) -> dict:
        """Handle generic event type"""
        subscribers = self.subscriptions.get(event_type, set())
        delivered = []
        
        for agent_id, writer in subscribers:
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
    
    async def _send_message(self, writer: asyncio.StreamWriter, message: dict):
        """Send message to agent via writer"""
        try:
            data = json.dumps(message) + '\n'
            writer.write(data.encode())
            await writer.drain()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise
    
    async def _deliver_queued_messages(self, agent_id: str):
        """Deliver queued messages to newly connected agent"""
        if agent_id not in self.offline_queue:
            return
        
        writer = self.connections.get(agent_id)
        if not writer:
            return
        
        queued = self.offline_queue[agent_id]
        delivered = 0
        
        logger.info(f"Delivering {len(queued)} queued messages to {agent_id}")
        
        for message in queued[:]:  # Copy list to avoid modification during iteration
            try:
                await self._send_message(writer, message)
                queued.remove(message)
                delivered += 1
            except Exception as e:
                logger.error(f"Failed to deliver queued message: {e}")
                break
        
        logger.info(f"Delivered {delivered} queued messages to {agent_id}")
        
        # Clean up if all delivered
        if not queued:
            del self.offline_queue[agent_id]
    
    def _find_capable_agent(self, required_capabilities: List[str]) -> Optional[str]:
        """Find an agent with required capabilities"""
        # This would integrate with agent_manager to find suitable agents
        # For now, return None (should be implemented with agent_manager integration)
        return None
    
    def _add_to_history(self, message: dict):
        """Add message to history for debugging"""
        self.message_history.append(message)
        
        # Trim history if too large
        if len(self.message_history) > self.max_history_size:
            self.message_history = self.message_history[-self.max_history_size:]
        
        # Also log to file
        try:
            log_file = str(config.response_log_dir / 'message_bus.jsonl')
            with open(log_file, 'a') as f:
                f.write(json.dumps(message) + '\n')
        except Exception as e:
            logger.error(f"Failed to log message: {e}")
    
    def get_stats(self) -> dict:
        """Get message bus statistics"""
        return {
            'connected_agents': list(self.connections.keys()),
            'subscriptions': {
                event_type: [aid for aid, _ in subscribers]
                for event_type, subscribers in self.subscriptions.items()
            },
            'offline_queues': {
                agent_id: len(messages)
                for agent_id, messages in self.offline_queue.items()
            },
            'history_size': len(self.message_history)
        }
    
    def list_connections(self) -> List[Dict[str, Any]]:
        """List all active connections (standardized API)"""
        from typing import List
        return [
            {'agent_id': agent_id, 'connected': True}
            for agent_id in self.connections.keys()
        ]
    
    def list_subscriptions(self) -> List[Dict[str, Any]]:
        """List all subscriptions (standardized API)"""
        from typing import List
        result = []
        for event_type, subscribers in self.subscriptions.items():
            for agent_id, writer in subscribers:
                result.append({
                    'agent_id': agent_id,
                    'event_type': event_type
                })
        return result
    
    def clear_subscriptions(self) -> int:
        """Clear all subscriptions (standardized API)"""
        count = sum(len(subs) for subs in self.subscriptions.values())
        self.subscriptions.clear()
        return count
    
    # Simplified interface for in-process agents
    
    async def publish_simple(self, from_agent: str, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Simplified publish interface for in-process agents (no StreamWriter required)"""
        try:
            # Create message in same format as regular publish
            message = {
                'type': event_type,
                'from': from_agent,
                'timestamp': TimestampManager.format_for_message_bus(),
                **payload
            }
            
            # Log to history
            self._add_to_history(message)
            
            # For in-process agents, we just need to route the message
            # The orchestrator will handle delivery to subscribed agents
            
            return {
                'status': 'success',
                'message_id': f"simple_{int(time.time() * 1000)}",
                'event_type': event_type,
                'timestamp': message['timestamp']
            }
            
        except Exception as e:
            logger.error(f"Error in publish_simple: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }