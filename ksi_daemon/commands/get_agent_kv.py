#!/usr/bin/env python3
"""
GET_AGENT_KV command handler - Read from agent key-value store
"""

import asyncio
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler
from ..protocols import SocketResponse, GetAgentKVParameters
from ..manager_framework import log_operation

@command_handler("GET_AGENT_KV")
class GetAgentKVHandler(CommandHandler):
    """Handles reading values from agent key-value store"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Get a value from shared state"""
        # Validate parameters
        try:
            params = GetAgentKVParameters(**parameters)
        except Exception as e:
            return SocketResponse.error("GET_AGENT_KV", "INVALID_PARAMETERS", str(e))
        
        # Get state manager
        if not self.context.state_manager:
            return SocketResponse.error("GET_AGENT_KV", "NO_STATE_MANAGER", "State manager not available")
        
        # Get the value
        value = self.context.state_manager.get_shared_state(params.key)
        
        return SocketResponse.get_agent_kv(
            key=params.key,
            value=value,
            found=value is not None
        )
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "GET_AGENT_KV",
            "description": "Get a value from agent key-value store",
            "parameters": {
                "key": {
                    "type": "string",
                    "description": "The key to retrieve"
                }
            },
            "examples": [
                {"key": "api_key"},
                {"key": "config.timeout"}
            ]
        }