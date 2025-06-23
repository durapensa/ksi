#!/usr/bin/env python3
"""
GET_SHARED command handler - Read from shared state
"""

import asyncio
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler
from ..models import ResponseFactory
from ..base_manager import log_operation
from pydantic import BaseModel, Field

class GetSharedParameters(BaseModel):
    """Parameters for GET_SHARED command"""
    key: str = Field(..., description="State key to retrieve")

@command_handler("GET_SHARED")
class GetSharedHandler(CommandHandler):
    """Handles reading values from shared state"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Get a value from shared state"""
        # Validate parameters
        try:
            params = GetSharedParameters(**parameters)
        except Exception as e:
            return ResponseFactory.error("GET_SHARED", "INVALID_PARAMETERS", str(e))
        
        # Get state manager
        if not self.context.state_manager:
            return ResponseFactory.error("GET_SHARED", "NO_STATE_MANAGER", "State manager not available")
        
        # Get the value
        value = self.context.state_manager.get_shared_state(params.key)
        
        if value is not None:
            return ResponseFactory.success("GET_SHARED", {
                'key': params.key,
                'value': value,
                'found': True
            })
        else:
            return ResponseFactory.success("GET_SHARED", {
                'key': params.key,
                'value': None,
                'found': False
            })
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "GET_SHARED",
            "description": "Get a value from shared state",
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