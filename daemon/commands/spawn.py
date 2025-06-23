#!/usr/bin/env python3
"""
SPAWN command handler - Manages Claude process spawning
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from ..command_registry import command_handler, CommandHandler
from ..models import ResponseFactory, SpawnParameters
from ..base_manager import log_operation
from pydantic import ValidationError

logger = logging.getLogger('daemon')

@command_handler("SPAWN")
class SpawnHandler(CommandHandler):
    """Handles SPAWN command for Claude process creation"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute spawn operation"""
        # Validate parameters
        try:
            params = SpawnParameters(**parameters)
        except ValidationError as e:
            return ResponseFactory.error("SPAWN", "INVALID_PARAMETERS", str(e))
        
        # Get process manager
        if not self.context.process_manager:
            return ResponseFactory.error("SPAWN", "NO_PROCESS_MANAGER", "Process manager not available")
        
        # Route based on mode
        if params.mode == "sync":
            return await self._spawn_sync(writer, params)
        elif params.mode == "async":
            return await self._spawn_async(writer, params)
        else:
            # This shouldn't happen due to validation, but just in case
            return ResponseFactory.error("SPAWN", "INVALID_MODE", f"Invalid mode: {params.mode}")
    
    async def _spawn_sync(self, writer: asyncio.StreamWriter, params: SpawnParameters) -> Any:
        """Handle synchronous Claude spawning"""
        logger.info(f"Synchronous Claude spawn: {params.prompt[:50]}...")
        
        result = await self.context.process_manager.spawn_claude(
            params.prompt, 
            params.session_id, 
            params.model, 
            params.agent_id, 
            params.enable_tools
        )
        
        return ResponseFactory.success("SPAWN", result)
    
    async def _spawn_async(self, writer: asyncio.StreamWriter, params: SpawnParameters) -> Any:
        """Handle asynchronous Claude spawning"""
        logger.info(f"Asynchronous Claude spawn: {params.prompt[:50]}...")
        
        process_id = await self.context.process_manager.spawn_claude_async(
            params.prompt,
            params.session_id,
            params.model,
            params.agent_id,
            params.enable_tools
        )
        
        if process_id:
            return ResponseFactory.success("SPAWN", {
                'process_id': process_id,
                'status': 'started',
                'type': 'claude',
                'mode': 'async'
            })
        else:
            return ResponseFactory.error("SPAWN", "SPAWN_FAILED", "Failed to start Claude process")
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "SPAWN",
            "description": "Spawn a Claude process in sync or async mode",
            "parameters": {
                "mode": {
                    "type": "string",
                    "enum": ["sync", "async"],
                    "description": "Execution mode"
                },
                "type": {
                    "type": "string", 
                    "enum": ["claude"],
                    "description": "Process type (only 'claude' supported)"
                },
                "prompt": {
                    "type": "string",
                    "description": "The prompt to send to Claude"
                },
                "session_id": {
                    "type": "string",
                    "description": "Session ID for conversation continuity",
                    "optional": True
                },
                "model": {
                    "type": "string",
                    "default": "sonnet",
                    "description": "Claude model to use",
                    "optional": True
                },
                "agent_id": {
                    "type": "string",
                    "description": "Agent ID for multi-agent coordination",
                    "optional": True
                },
                "enable_tools": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to enable Claude tools",
                    "optional": True
                }
            },
            "examples": [
                {
                    "mode": "sync",
                    "type": "claude",
                    "prompt": "Hello, Claude!"
                },
                {
                    "mode": "async",
                    "type": "claude", 
                    "prompt": "Analyze this code",
                    "session_id": "session-123",
                    "model": "opus"
                }
            ]
        }