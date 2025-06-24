#!/usr/bin/env python3
"""
SET_AGENT_KV command handler - Write to agent key-value store
"""

import asyncio
from typing import Dict, Any, Optional
from ..command_registry import command_handler, CommandHandler
from ..protocols import SocketResponse, SetAgentKVParameters
from ..manager_framework import log_operation

@command_handler("SET_AGENT_KV")
class SetAgentKVHandler(CommandHandler):
    """Handles setting values in agent key-value store"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Set a value in shared state"""
        # Validate parameters
        try:
            self.logger.info(f"SET_AGENT_KV received parameters: {parameters}")
            params = SetAgentKVParameters(**parameters)
            self.logger.info(f"SET_AGENT_KV parsed params: owner_agent_id={params.owner_agent_id}, scope={params.scope}, metadata={params.metadata}")
        except Exception as e:
            return SocketResponse.error("SET_AGENT_KV", "INVALID_PARAMETERS", str(e))
        
        # Get state manager
        if not self.context.state_manager:
            return SocketResponse.error("SET_AGENT_KV", "NO_STATE_MANAGER", "State manager not available")
        
        # Set the value with all metadata
        self.context.state_manager.set_shared_state(
            key=params.key,
            value=params.value,
            owner_agent_id=params.owner_agent_id,
            scope=params.scope,
            expires_at=params.expires_at,
            metadata=params.metadata
        )
        
        return SocketResponse.set_agent_kv(key=params.key)
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "SET_AGENT_KV",
            "description": "Set a value in agent key-value store (SQLite-backed with metadata)",
            "parameters": {
                "key": {
                    "type": "string",
                    "description": "The key to set (suggest agent_id.purpose.detail format)",
                    "required": True
                },
                "value": {
                    "type": "any", 
                    "description": "The value to store (string, number, object, array, boolean, or null)",
                    "required": True
                },
                "owner_agent_id": {
                    "type": "string",
                    "description": "Agent ID that owns this data",
                    "default": "system",
                    "optional": True
                },
                "scope": {
                    "type": "string",
                    "description": "Data scope: private, shared, or coordination",
                    "default": "shared",
                    "optional": True
                },
                "expires_at": {
                    "type": "string",
                    "description": "ISO timestamp when this expires (optional)",
                    "optional": True
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata (optional)",
                    "optional": True
                }
            },
            "examples": [
                {"key": "agent_001.status.current", "value": "active", "owner_agent_id": "agent_001"},
                {"key": "task_coord.assignments.pending", "value": ["task_1", "task_2"], "scope": "coordination"},
                {"key": "project.config.settings", "value": {"timeout": 30, "retries": 3}, "metadata": {"description": "Global project settings"}}
            ],
            "note": "For discovery and advanced queries, use: sqlite3 agent_shared_state.db"
        }