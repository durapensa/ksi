#!/usr/bin/env python3
"""
SET_SHARED command handler - Write to shared state
"""

import asyncio
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler
from ..models import ResponseFactory
from ..base_manager import log_operation
from pydantic import BaseModel, Field

class SetSharedParameters(BaseModel):
    """Parameters for SET_SHARED command"""
    key: str = Field(..., description="State key to set")
    value: str = Field(..., description="State value to store")

@command_handler("SET_SHARED")
class SetSharedHandler(CommandHandler):
    """Handles setting values in shared state"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Set a value in shared state"""
        # Validate parameters
        try:
            params = SetSharedParameters(**parameters)
        except Exception as e:
            return ResponseFactory.error("SET_SHARED", "INVALID_PARAMETERS", str(e))
        
        # Get state manager
        if not self.context.state_manager:
            return ResponseFactory.error("SET_SHARED", "NO_STATE_MANAGER", "State manager not available")
        
        # Set the value
        self.context.state_manager.set_shared_state(params.key, params.value)
        
        return ResponseFactory.success("SET_SHARED", {
            'key': params.key,
            'status': 'set'
        })
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "SET_SHARED",
            "description": "Set a value in shared state",
            "parameters": {
                "key": {
                    "type": "string",
                    "description": "The key to set"
                },
                "value": {
                    "type": "string", 
                    "description": "The value to store"
                }
            },
            "examples": [
                {"key": "api_key", "value": "secret123"},
                {"key": "config.timeout", "value": "30"}
            ]
        }