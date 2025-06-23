#!/usr/bin/env python3
"""
SEND_MESSAGE command handler - Send messages between agents
"""

import asyncio
from typing import Dict, Any, Optional
from ..command_registry import command_handler, CommandHandler
from ..socket_protocol_models import SocketResponse, SendMessageParameters
from ..manager_framework import log_operation
from ..timestamp_utils import TimestampManager

@command_handler("SEND_MESSAGE")
class SendMessageHandler(CommandHandler):
    """Handles SEND_MESSAGE command for agent-to-agent communication"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute message sending between agents"""
        # Validate parameters
        try:
            params = SendMessageParameters(**parameters)
        except Exception as e:
            return SocketResponse.error("SEND_MESSAGE", "INVALID_PARAMETERS", str(e))
        
        # Check if orchestrator is available
        if not self.context.completion_manager or not hasattr(self.context.completion_manager, 'agent_orchestrator'):
            return SocketResponse.error("SEND_MESSAGE", "NO_ORCHESTRATOR", "Multi-agent orchestrator not available")
        
        orchestrator = self.context.completion_manager.agent_orchestrator
        if not orchestrator:
            return SocketResponse.error("SEND_MESSAGE", "NO_ORCHESTRATOR", "Multi-agent orchestrator not initialized")
        
        # Verify sender exists
        if params.from_agent not in orchestrator.agents:
            return SocketResponse.error("SEND_MESSAGE", "SENDER_NOT_FOUND", f"Sender agent '{params.from_agent}' not found")
        
        # Build message payload
        message = {
            'type': params.message_type,
            'from': params.from_agent,
            'content': params.content,
            'timestamp': TimestampManager.format_for_message_bus(),
            **params.metadata
        }
        
        # Route based on destination type
        if params.to_agent:
            # Direct message to specific agent
            return await self._send_direct_message(orchestrator, params.to_agent, message)
        elif params.event_types:
            # Publish to event bus for subscribed agents
            return await self._publish_to_event_bus(orchestrator, params.from_agent, params.event_types, message)
        else:
            # Broadcast to all agents
            return await self._broadcast_message(orchestrator, params.from_agent, message)
    
    async def _send_direct_message(self, orchestrator, to_agent: str, message: Dict[str, Any]) -> Any:
        """Send message directly to specific agent"""
        # Verify recipient exists
        if to_agent not in orchestrator.agents:
            return SocketResponse.error("SEND_MESSAGE", "RECIPIENT_NOT_FOUND", f"Recipient agent '{to_agent}' not found")
        
        # Send the message
        success = await orchestrator.send_message_to_agent(to_agent, message)
        
        if success:
            return SocketResponse.success("SEND_MESSAGE", {
                'delivery': 'direct',
                'from': message['from'],
                'to': to_agent,
                'type': message['type'],
                'timestamp': message['timestamp'],
                'status': 'delivered'
            })
        else:
            return SocketResponse.error("SEND_MESSAGE", "DELIVERY_FAILED", f"Failed to deliver message to agent '{to_agent}'")
    
    async def _publish_to_event_bus(self, orchestrator, from_agent: str, event_types: list[str], message: Dict[str, Any]) -> Any:
        """Publish message via event bus for subscribers"""
        delivered_count = 0
        delivery_details = []
        
        # For each event type, route through orchestrator's pub/sub system
        for event_type in event_types:
            message['type'] = event_type
            await orchestrator.handle_agent_message(from_agent, event_type, message)
            
            # Count subscribers
            subscribers = orchestrator.message_subscriptions.get(event_type, [])
            active_subscribers = [s for s in subscribers if s != from_agent]
            delivered_count += len(active_subscribers)
            
            delivery_details.append({
                'event_type': event_type,
                'subscribers': active_subscribers,
                'count': len(active_subscribers)
            })
        
        return SocketResponse.success("SEND_MESSAGE", {
            'delivery': 'event_bus',
            'from': from_agent,
            'event_types': event_types,
            'total_delivered': delivered_count,
            'details': delivery_details,
            'timestamp': message['timestamp'],
            'status': 'published'
        })
    
    async def _broadcast_message(self, orchestrator, from_agent: str, message: Dict[str, Any]) -> Any:
        """Broadcast message to all agents except sender"""
        delivered_count = await orchestrator.broadcast_message(message, exclude_agent=from_agent)
        
        all_agents = list(orchestrator.agents.keys())
        recipients = [a for a in all_agents if a != from_agent]
        
        return SocketResponse.success("SEND_MESSAGE", {
            'delivery': 'broadcast',
            'from': from_agent,
            'recipients': recipients,
            'count': delivered_count,
            'type': message['type'],
            'timestamp': message['timestamp'],
            'status': 'broadcast'
        })
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "SEND_MESSAGE",
            "description": "Send messages between agents for orchestration and communication",
            "parameters": {
                "from_agent": {
                    "type": "string",
                    "description": "ID of the agent sending the message",
                    "required": True
                },
                "to_agent": {
                    "type": "string",
                    "description": "ID of specific target agent (omit for broadcast)",
                    "optional": True
                },
                "message_type": {
                    "type": "string",
                    "description": "Type of message (MESSAGE, TASK_ASSIGNMENT, DEBATE_OPENING, etc.)",
                    "optional": True,
                    "default": "MESSAGE"
                },
                "content": {
                    "type": "string",
                    "description": "Message content",
                    "required": True
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata for the message",
                    "optional": True,
                    "default": {}
                },
                "event_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Event types for pub/sub routing (alternative to to_agent)",
                    "optional": True
                }
            },
            "routing_modes": {
                "direct": "Specify 'to_agent' to send directly to one agent",
                "broadcast": "Omit both 'to_agent' and 'event_types' to broadcast to all",
                "pub_sub": "Specify 'event_types' to route via event subscriptions"
            },
            "examples": [
                {
                    "from_agent": "coordinator",
                    "to_agent": "analyst_001",
                    "message_type": "TASK_ASSIGNMENT",
                    "content": "Please analyze the Q4 sales data",
                    "metadata": {"priority": "high", "deadline": "2024-12-31"},
                    "description": "Direct task assignment"
                },
                {
                    "from_agent": "debate_agent_1",
                    "message_type": "DEBATE_OPENING",
                    "content": "I believe AI will fundamentally transform education...",
                    "event_types": ["DEBATE_OPENING"],
                    "description": "Publish debate opening for subscribers"
                },
                {
                    "from_agent": "announcer",
                    "content": "System maintenance scheduled for midnight",
                    "description": "Broadcast announcement to all agents"
                }
            ]
        }