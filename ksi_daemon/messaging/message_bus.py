#!/usr/bin/env python3
"""
Message Bus Module - Event-Based Version

Provides pub/sub messaging functionality with consolidated MessageBus class.
"""

import asyncio
import json
from typing import Dict, List, Set, Optional, Any, TypedDict, Literal
from typing_extensions import NotRequired, Required
from collections import defaultdict
import time

from ksi_daemon.event_system import event_handler, get_router, shutdown_handler
from ksi_common.timestamps import timestamp_utc
from ksi_common.logging import log_event, agent_context
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

# Module state
logger = get_bound_logger("message_bus", version="1.0.0")
event_emitter = None

# Track subscriptions per client
client_subscriptions: Dict[str, Set[str]] = {}


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
        
        # Track background tasks for cleanup
        self._delivery_tasks: Set[asyncio.Task] = set()
        
    def connect_agent(self, agent_id: str, writer: asyncio.StreamWriter):
        """Register an agent connection"""
        self.connections[agent_id] = writer
        
        log_event(logger, "message_bus.agent_connected",
                 event="message_bus.agent_connected",
                 agent_id=agent_id,
                 total_connections=len(self.connections),
                 has_queued_messages=agent_id in self.offline_queue)
        
        # Deliver any queued messages
        if agent_id in self.offline_queue:
            task = asyncio.create_task(self._deliver_queued_messages(agent_id))
            self._delivery_tasks.add(task)
            # Remove task from set when done
            task.add_done_callback(self._delivery_tasks.discard)
    
    def disconnect_agent(self, agent_id: str):
        """Remove agent connection"""
        was_connected = agent_id in self.connections
        
        if was_connected:
            del self.connections[agent_id]
            
        log_event(logger, "message_bus.agent_disconnected",
                 event="message_bus.agent_disconnected",
                 agent_id=agent_id,
                 was_connected=was_connected,
                 remaining_connections=len(self.connections))
            
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
                     event="message_bus.subscription_failed",
                     agent_id=agent_id,
                     event_types=event_types,
                     reason="agent_not_connected")
            return False
        
        for event_type in event_types:
            self.subscriptions[event_type].add((agent_id, writer))
        
        log_event(logger, "message_bus.subscribed",
                 event="message_bus.subscribed",
                 agent_id=agent_id,
                 event_types=event_types,
                 subscription_count=len(event_types))
        
        return True
    
    def unsubscribe(self, agent_id: str, event_types: List[str]):
        """Unsubscribe an agent from event types"""
        for event_type in event_types:
            self.subscriptions[event_type].discard((agent_id, self.connections.get(agent_id)))
        
        log_event(logger, "message_bus.unsubscribed",
                 event="message_bus.unsubscribed",
                 agent_id=agent_id,
                 event_types=event_types,
                 unsubscription_count=len(event_types))
    
    async def publish(self, from_agent: str, event_type: str, payload: dict) -> dict:
        """Publish an event to all subscribers"""
        # Create message
        message = {
            'id': str(time.time()),
            'type': event_type,
            'from': from_agent,
            'timestamp': timestamp_utc(),
            **payload
        }
        
        # Log to history
        self._add_to_history(message)
        
        # Log publication event
        log_event(logger, "message_bus.message_published",
                 event="message_bus.message_published",
                 agent_id=from_agent,
                 event_type=event_type,
                 message_id=message['id'],
                 subscriber_count=len(self.subscriptions.get(event_type, [])))
        
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
            to_agent = await self._find_capable_agent(required_capabilities)
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
    
    async def _find_capable_agent(self, required_capabilities: List[str]) -> Optional[str]:
        """Find an agent with required capabilities"""
        # Use agent service to find suitable agents
        if event_emitter:
            result = await event_emitter("agent:get_capabilities", {})
            if result and "capabilities" in result:
                all_capabilities = result["capabilities"]
                
                # Find agents that have all required capabilities
                for agent_id, caps in all_capabilities.items():
                    if all(cap in caps for cap in required_capabilities):
                        # Check if agent is connected
                        if agent_id in self.connections:
                            return agent_id
        
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
        return [
            {'agent_id': agent_id, 'connected': True}
            for agent_id in self.connections.keys()
        ]
    
    def list_subscriptions(self) -> List[Dict[str, Any]]:
        """List all subscriptions (standardized API)"""
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
    
    async def shutdown(self) -> None:
        """Comprehensive shutdown of message bus."""
        logger.info("Starting message bus shutdown")
        
        # 1. Cancel all pending delivery tasks
        if self._delivery_tasks:
            logger.info(f"Cancelling {len(self._delivery_tasks)} delivery tasks")
            for task in list(self._delivery_tasks):
                if not task.done():
                    task.cancel()
            
            # Wait for all tasks to complete cancellation
            if self._delivery_tasks:
                await asyncio.gather(*self._delivery_tasks, return_exceptions=True)
            self._delivery_tasks.clear()
        
        # 2. Disconnect all agents gracefully
        if self.connections:
            logger.info(f"Disconnecting {len(self.connections)} agents")
            for agent_id in list(self.connections.keys()):
                self.disconnect_agent(agent_id)
        
        # 3. Clear offline message queues
        queue_count = len(self.offline_queue)
        message_count = sum(len(msgs) for msgs in self.offline_queue.values())
        if queue_count > 0:
            logger.info(f"Clearing {message_count} messages from {queue_count} offline queues")
            self.offline_queue.clear()
        
        # 4. Clear message history
        history_count = len(self.message_history)
        if history_count > 0:
            logger.info(f"Clearing {history_count} messages from history")
            self.message_history.clear()
        
        # 5. Clear all subscriptions
        sub_count = self.clear_subscriptions()
        
        logger.info(f"Message bus shutdown complete - cleared {sub_count} subscriptions")
    
    # Simplified interface for in-process agents
    
    async def publish_simple(self, from_agent: str, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Simplified publish interface for in-process agents (no StreamWriter required)"""
        try:
            # Create message in same format as regular publish
            message = {
                'type': event_type,
                'from': from_agent,
                'timestamp': timestamp_utc(),
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


# Initialize message bus instance
message_bus = MessageBus()


# System event handlers
class SystemContextData(TypedDict):
    """System context with runtime references."""
    emit_event: NotRequired[Any]  # Event emitter function
    shutdown_event: NotRequired[Any]  # Shutdown event object


@event_handler("system:context")
async def handle_context(context: SystemContextData) -> None:
    """Store event emitter reference."""
    global event_emitter
    # Get router for event emission
    router = get_router()
    event_emitter = router.emit
    logger.info("Message bus received context, event_emitter configured")


class SystemStartupData(TypedDict):
    """System startup configuration."""
    # No specific fields required for this handler
    pass


@event_handler("system:startup")
async def handle_startup(config_data: SystemStartupData) -> Dict[str, Any]:
    """Initialize message bus."""
    logger.info("Message bus module started (consolidated)")
    return {"module.message_bus": {"loaded": True}}


@shutdown_handler("message_bus")
async def handle_shutdown(data: Dict[str, Any]) -> None:
    """Clean up on shutdown.
    
    This is a critical shutdown handler that ensures all message
    delivery tasks are properly cancelled before daemon exits.
    """
    # Perform comprehensive shutdown
    await message_bus.shutdown()
    
    # Clear client subscription tracking  
    client_subscriptions.clear()
    
    logger.info("Message bus module stopped")
    
    # Acknowledge shutdown completion
    router = get_router()
    await router.acknowledge_shutdown("message_bus")


# Message bus event handlers
class MessageSubscribeData(TypedDict):
    """Subscribe to message types."""
    agent_id: Required[str]  # Agent ID making the subscription
    event_types: Required[List[str]]  # List of event types to subscribe to


@event_handler("message:subscribe")
async def handle_subscribe(data: MessageSubscribeData) -> Dict[str, Any]:
    """Handle subscription request."""
    agent_id = data.get("agent_id")
    event_types = data.get("event_types", [])
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    if not event_types:
        return {"error": "event_types required"}
    
    # Track subscriptions per client for unsubscription
    if agent_id not in client_subscriptions:
        client_subscriptions[agent_id] = set()
    
    client_subscriptions[agent_id].update(event_types)
    
    # Subscribe to the message bus
    success = message_bus.subscribe(agent_id, event_types)
    
    if success:
        return {
            "status": "subscribed",
            "agent_id": agent_id,
            "event_types": event_types
        }
    else:
        return {"error": "Subscription failed - agent not connected"}


class MessageUnsubscribeData(TypedDict):
    """Unsubscribe from message types."""
    agent_id: Required[str]  # Agent ID unsubscribing
    event_types: NotRequired[List[str]]  # Event types to unsubscribe from (omit for all)


@event_handler("message:unsubscribe")
async def handle_unsubscribe(data: MessageUnsubscribeData) -> Dict[str, Any]:
    """Handle unsubscription request."""
    agent_id = data.get("agent_id")
    event_types = data.get("event_types", [])
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    # If no specific event_types, unsubscribe from all
    if not event_types and agent_id in client_subscriptions:
        event_types = list(client_subscriptions[agent_id])
    
    if event_types:
        message_bus.unsubscribe(agent_id, event_types)
        
        # Update tracking
        if agent_id in client_subscriptions:
            client_subscriptions[agent_id] -= set(event_types)
            if not client_subscriptions[agent_id]:
                del client_subscriptions[agent_id]
    
    return {
        "status": "unsubscribed",
        "agent_id": agent_id,
        "event_types": event_types
    }


class MessagePublishData(TypedDict):
    """Publish a message to subscribers."""
    agent_id: Required[str]  # Agent ID publishing the message
    event_type: Required[str]  # Event type to publish
    message: NotRequired[Dict[str, Any]]  # Message payload (default: {})


@event_handler("message:publish")
async def handle_publish(data: MessagePublishData) -> Dict[str, Any]:
    """Handle message publication."""
    agent_id = data.get("agent_id")
    event_type = data.get("event_type")
    message = data.get("message", {})
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    if not event_type:
        return {"error": "event_type required"}
    
    try:
        result = await message_bus.publish(agent_id, event_type, message)
        return result
    except Exception as e:
        logger.error(f"Publish error: {e}")
        return {"error": str(e)}


class MessageSubscriptionsData(TypedDict):
    """Get subscription information."""
    agent_id: NotRequired[str]  # Specific agent ID (omit for all)


@event_handler("message:subscriptions")
async def handle_get_subscriptions(data: MessageSubscriptionsData) -> Dict[str, Any]:
    """Get subscription information."""
    agent_id = data.get("agent_id")
    
    if agent_id:
        # Get subscriptions for specific agent
        return {
            "agent_id": agent_id,
            "subscriptions": list(client_subscriptions.get(agent_id, []))
        }
    else:
        # Get all subscriptions
        return {
            "all_subscriptions": dict(client_subscriptions)
        }


class MessageBusStatsData(TypedDict):
    """Get message bus statistics."""
    # No specific fields - returns overall stats
    pass


@event_handler("message_bus:stats")
async def handle_get_stats(data: MessageBusStatsData) -> Dict[str, Any]:
    """Get message bus statistics."""
    return {"stats": message_bus.get_stats()}


class MessageConnectData(TypedDict):
    """Connect an agent to the message bus."""
    agent_id: Required[str]  # Agent ID to connect


@event_handler("message:connect")
async def handle_connect_agent(data: MessageConnectData) -> Dict[str, Any]:
    """Handle agent connection."""
    agent_id = data.get("agent_id")
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    # For now, we'll create a mock writer - in real implementation this would be passed
    # This is mainly for the in-process agent case
    
    return {
        "status": "connected",
        "agent_id": agent_id
    }


class MessageDisconnectData(TypedDict):
    """Disconnect an agent from the message bus."""
    agent_id: Required[str]  # Agent ID to disconnect


@event_handler("message:disconnect")
async def handle_disconnect_agent(data: MessageDisconnectData) -> Dict[str, Any]:
    """Handle agent disconnection."""
    agent_id = data.get("agent_id")
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    message_bus.disconnect_agent(agent_id)
    
    # Clean up subscriptions
    if agent_id in client_subscriptions:
        del client_subscriptions[agent_id]
    
    return {
        "status": "disconnected",
        "agent_id": agent_id
    }


# Legacy transport:message compatibility
class TransportMessageParameters(TypedDict):
    """Legacy transport message parameters."""
    agent_id: NotRequired[str]  # Agent ID
    event_type: NotRequired[str]  # Event type (for PUBLISH)
    event_types: NotRequired[List[str]]  # Event types (for SUBSCRIBE)
    message: NotRequired[Dict[str, Any]]  # Message payload (for PUBLISH)


class TransportMessageData(TypedDict):
    """Legacy transport message format."""
    command: Required[Literal['PUBLISH', 'SUBSCRIBE']]  # Legacy command type
    parameters: NotRequired[TransportMessageParameters]  # Command parameters


@event_handler("transport:message")
async def handle_transport_message(data: TransportMessageData) -> Dict[str, Any]:
    """Handle legacy transport:message events by converting them."""
    command = data.get("command")
    
    if command == "PUBLISH":
        # Convert legacy format
        params = data.get("parameters", {})
        return await handle_publish({
            "agent_id": params.get("agent_id"),
            "event_type": params.get("event_type"),
            "message": params.get("message", {})
        })
    
    elif command == "SUBSCRIBE":
        # Convert legacy format
        params = data.get("parameters", {})
        return await handle_subscribe({
            "agent_id": params.get("agent_id"),
            "event_types": params.get("event_types", [])
        })
    
    return {"error": f"Unknown transport command: {command}"}


