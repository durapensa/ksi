#!/usr/bin/env python3
"""
MESSAGE_BUS_STATS command handler - Returns message bus statistics
"""

import asyncio
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler
from ..socket_protocol_models import SocketResponse
from ..manager_framework import log_operation


@command_handler("MESSAGE_BUS_STATS")
class MessageBusStatsHandler(CommandHandler):
    """Handles MESSAGE_BUS_STATS command for message bus statistics"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Get message bus statistics"""
        # No parameters needed for this command
        
        if self.context.message_bus:
            stats = self.context.message_bus.get_stats()
            return SocketResponse.success("MESSAGE_BUS_STATS", stats)
        else:
            return SocketResponse.success("MESSAGE_BUS_STATS", {
                'error': 'Message bus not available'
            })
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "MESSAGE_BUS_STATS",
            "description": "Get current message bus statistics and status",
            "parameters": {},
            "examples": [
                {}
            ],
            "response_format": {
                "connected_agents": "Number of connected agents",
                "total_messages": "Total messages sent through the bus",
                "subscriptions": "Active event subscriptions",
                "active_connections": "Current active connections"
            }
        }