#!/usr/bin/env python3
"""
LOAD_STATE command handler - Loads serialized state for hot reload
"""

import asyncio
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler
from ..socket_protocol_models import SocketResponse, LoadStateParameters
from ..manager_framework import log_operation


@command_handler("LOAD_STATE")
class LoadStateHandler(CommandHandler):
    """Handles LOAD_STATE command for hot reload state restoration"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute state loading"""
        # Validate parameters
        try:
            params = LoadStateParameters(**parameters)
        except Exception as e:
            return SocketResponse.error("LOAD_STATE", "INVALID_PARAMETERS", str(e))
        
        # Check hot reload manager availability
        if not self.context.hot_reload_manager:
            return SocketResponse.error("LOAD_STATE", "NO_HOT_RELOAD_MANAGER", "Hot reload manager not available")
        
        # Load the state
        try:
            self.context.hot_reload_manager.deserialize_state(params.state_data)
            
            return SocketResponse.success("LOAD_STATE", {
                'status': 'loaded',
                'message': 'State loaded successfully',
                'state_keys': list(params.state_data.keys())
            })
        except Exception as e:
            return SocketResponse.error("LOAD_STATE", "LOAD_STATE_FAILED", str(e))
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "LOAD_STATE",
            "description": "Load serialized state data for hot reload recovery",
            "parameters": {
                "state_data": {
                    "type": "object",
                    "description": "Serialized state data from previous daemon instance",
                    "required": True
                }
            },
            "examples": [
                {
                    "state_data": {
                        "sessions": {},
                        "agents": {},
                        "shared_state": {},
                        "processes": {}
                    }
                }
            ],
            "notes": [
                "Used during hot reload to restore daemon state",
                "State data comes from daemon serialization before shutdown"
            ]
        }