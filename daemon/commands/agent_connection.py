#!/usr/bin/env python3
"""
AGENT_CONNECTION command handler - Manages agent connections to message bus
"""

import asyncio
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler
from ..socket_protocol_models import SocketResponse, AgentConnectionParameters
from ..manager_framework import log_operation


@command_handler("AGENT_CONNECTION")
class AgentConnectionHandler(CommandHandler):
    """Handles AGENT_CONNECTION command for message bus connections"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute agent connection/disconnection"""
        # Validate parameters
        try:
            params = AgentConnectionParameters(**parameters)
        except Exception as e:
            return SocketResponse.error("AGENT_CONNECTION", "INVALID_PARAMETERS", str(e))
        
        # Check message bus availability
        if not self.context.message_bus:
            return SocketResponse.error("AGENT_CONNECTION", "NO_MESSAGE_BUS", "Message bus not available")
        
        # Validate action
        if params.action not in ["connect", "disconnect"]:
            return SocketResponse.error("AGENT_CONNECTION", "INVALID_ACTION", f"Invalid action: {params.action}")
        
        # Execute action
        if params.action == "connect":
            self.context.message_bus.connect_agent(params.agent_id, writer)
            return SocketResponse.success("AGENT_CONNECTION", {
                'status': 'connected',
                'agent_id': params.agent_id,
                'action': 'connect'
            })
        else:  # disconnect
            self.context.message_bus.disconnect_agent(params.agent_id)
            return SocketResponse.success("AGENT_CONNECTION", {
                'status': 'disconnected',
                'agent_id': params.agent_id,
                'action': 'disconnect'
            })
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "AGENT_CONNECTION",
            "description": "Connect or disconnect agents from the message bus",
            "parameters": {
                "action": {
                    "type": "string",
                    "enum": ["connect", "disconnect"],
                    "description": "Action to perform",
                    "required": True
                },
                "agent_id": {
                    "type": "string",
                    "description": "ID of agent to connect/disconnect",
                    "required": True
                }
            },
            "examples": [
                {
                    "action": "connect",
                    "agent_id": "agent_001"
                },
                {
                    "action": "disconnect",
                    "agent_id": "agent_001"
                }
            ]
        }