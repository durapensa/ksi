#!/usr/bin/env python3
"""
SUBSCRIBE command handler - Subscribe agent to message bus events
"""

import asyncio
from typing import Dict, Any, List
from ..command_registry import command_handler, CommandHandler
from ..socket_protocol_models import SocketResponse, SubscribeParameters
from ..manager_framework import log_operation

@command_handler("SUBSCRIBE")
class SubscribeHandler(CommandHandler):
    """Handles SUBSCRIBE command for message bus event subscriptions"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute event subscription"""
        # Validate parameters
        try:
            params = SubscribeParameters(**parameters)
        except Exception as e:
            return SocketResponse.error("SUBSCRIBE", "INVALID_PARAMETERS", str(e))
        
        # Check if message bus is available
        if not self.context.message_bus:
            return SocketResponse.error("SUBSCRIBE", "NO_MESSAGE_BUS", "Message bus not available")
        
        # Check if agent is connected
        is_connected = params.agent_id in self.context.message_bus.connections
        if not is_connected:
            # Provide helpful information about why subscription failed
            connected_agents = list(self.context.message_bus.connections.keys())
            # Include details in the error message instead of as a separate parameter
            error_message = (
                f"Agent '{params.agent_id}' is not connected to the message bus. "
                f"Connected agents: {', '.join(connected_agents) if connected_agents else 'none'}. "
                f"Agent must connect via AGENT_CONNECTION:connect before subscribing."
            )
            return SocketResponse.error("SUBSCRIBE", "AGENT_NOT_CONNECTED", error_message)
        
        # Subscribe to events
        success = self.context.message_bus.subscribe(params.agent_id, params.event_types)
        
        if success:
            # Get current subscriptions for this agent
            agent_subscriptions = []
            for event_type, subscribers in self.context.message_bus.subscriptions.items():
                if any(sub[0] == params.agent_id for sub in subscribers):
                    agent_subscriptions.append(event_type)
            
            return SocketResponse.success("SUBSCRIBE", {
                'subscription': {
                    'agent_id': params.agent_id,
                    'subscribed_to': params.event_types,
                    'all_subscriptions': agent_subscriptions,
                    'status': 'active'
                },
                'message_bus': {
                    'total_event_types': len(self.context.message_bus.subscriptions),
                    'total_connections': len(self.context.message_bus.connections)
                }
            })
        else:
            # This shouldn't happen given our earlier check, but just in case
            return SocketResponse.error("SUBSCRIBE", "SUBSCRIPTION_FAILED", 
                f"Failed to subscribe agent '{params.agent_id}' to events")
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "SUBSCRIBE",
            "description": "Subscribe an agent to receive specific event types from the message bus",
            "parameters": {
                "agent_id": {
                    "type": "string",
                    "description": "Agent ID to subscribe",
                    "required": True
                },
                "event_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of event types to subscribe to",
                    "required": True
                }
            },
            "event_types": [
                "DIRECT_MESSAGE - Direct messages between agents",
                "BROADCAST - Broadcast messages to all agents",
                "TASK_ASSIGNMENT - Task routing notifications",
                "CONVERSATION_INVITE - Multi-agent conversation invitations",
                "AGENT_STATUS - Agent status changes",
                "SYSTEM_EVENT - System-wide events"
            ],
            "examples": [
                {
                    "agent_id": "monitor_agent",
                    "event_types": ["DIRECT_MESSAGE", "TASK_ASSIGNMENT", "AGENT_STATUS"]
                },
                {
                    "agent_id": "coordinator_001",
                    "event_types": ["BROADCAST", "SYSTEM_EVENT"]
                }
            ],
            "prerequisites": [
                "Agent must be connected via AGENT_CONNECTION:connect command",
                "Agent connection must have an active StreamWriter"
            ]
        }