#!/usr/bin/env python3
"""
COMPLETION command handler - Manages Claude completions via LiteLLM
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, Optional
from ..command_registry import command_handler, CommandHandler
from ..socket_protocol_models import SocketResponse, SpawnParameters
from ..manager_framework import log_operation
from pydantic import ValidationError

logger = logging.getLogger('daemon')

@command_handler("COMPLETION")
@command_handler("SPAWN")  # Backward compatibility alias
class CompletionHandler(CommandHandler):
    """Handles COMPLETION command for Claude interactions"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute completion request"""
        # Get the actual command name used
        command_name = full_command.get('command', 'COMPLETION')
        
        # Validate parameters
        try:
            params = SpawnParameters(**parameters)
        except ValidationError as e:
            return SocketResponse.error(command_name, "INVALID_PARAMETERS", str(e))
        
        # Check if we should route through an agent
        if params.agent_id:
            # Route through agent for session management
            if not self.context.completion_manager or not hasattr(self.context.completion_manager, 'agent_orchestrator'):
                return SocketResponse.error(command_name, "NO_ORCHESTRATOR", "Multi-agent orchestrator not available")
            
            orchestrator = self.context.completion_manager.agent_orchestrator
            if not orchestrator:
                return SocketResponse.error(command_name, "NO_ORCHESTRATOR", "Multi-agent orchestrator not initialized")
            
            # Check if agent exists
            if params.agent_id not in orchestrator.agents:
                return SocketResponse.error(command_name, "AGENT_NOT_FOUND", f"Agent '{params.agent_id}' not found")
            
            # Route based on mode
            if params.mode == "sync":
                return await self._completion_via_agent_sync(writer, params, orchestrator, command_name)
            else:
                return await self._completion_via_agent_async(writer, params, orchestrator, command_name)
        
        else:
            # Direct Claude call without agent
            if not self.context.completion_manager:
                return SocketResponse.error(command_name, "NO_PROCESS_MANAGER", "Process manager not available")
            
            # Route based on mode
            if params.mode == "sync":
                return await self._completion_direct_sync(writer, params, command_name)
            else:
                return await self._completion_direct_async(writer, params, command_name)
    
    async def _completion_via_agent_sync(self, writer: asyncio.StreamWriter, params: SpawnParameters, 
                                       orchestrator, command_name: str) -> Any:
        """Handle synchronous completion through an agent"""
        logger.info(f"Routing completion through agent {params.agent_id}: {params.prompt[:50]}...")
        
        agent = orchestrator.agents[params.agent_id]
        
        # Send prompt to agent and get response
        try:
            response = await agent.send_prompt(params.prompt, params.session_id)
            return SocketResponse.success(command_name, response)
        except Exception as e:
            logger.error(f"Agent completion failed: {e}")
            return SocketResponse.error(command_name, "AGENT_ERROR", str(e))
    
    async def _completion_via_agent_async(self, writer: asyncio.StreamWriter, params: SpawnParameters,
                                        orchestrator, command_name: str) -> Any:
        """Handle asynchronous completion through an agent"""
        logger.info(f"Async routing through agent {params.agent_id}: {params.prompt[:50]}...")
        
        # For async, we queue the message and return immediately
        agent = orchestrator.agents[params.agent_id]
        message_id = str(uuid.uuid4())[:8]
        
        # Queue message for async processing
        await agent.queue_prompt(params.prompt, params.session_id, message_id)
        
        return SocketResponse.success(command_name, {
            'message_id': message_id,
            'agent_id': params.agent_id,
            'status': 'queued',
            'mode': 'async'
        })
    
    async def _completion_direct_sync(self, writer: asyncio.StreamWriter, params: SpawnParameters,
                                    command_name: str) -> Any:
        """Handle synchronous completion without agent"""
        logger.info(f"Direct Claude completion: {params.prompt[:50]}...")
        
        result = await self.context.completion_manager.create_completion(
            params.prompt, 
            params.session_id, 
            params.model, 
            params.agent_id,  # Still pass for logging, but not used for routing
            params.enable_tools
        )
        
        return SocketResponse.success(command_name, result)
    
    async def _completion_direct_async(self, writer: asyncio.StreamWriter, params: SpawnParameters,
                                     command_name: str) -> Any:
        """Handle asynchronous completion without agent"""
        logger.info(f"Direct async Claude completion: {params.prompt[:50]}...")
        
        process_id = await self.context.completion_manager.create_completion_async(
            params.prompt,
            params.session_id,
            params.model,
            params.agent_id,  # Still pass for logging
            params.enable_tools
        )
        
        if process_id:
            return SocketResponse.success(command_name, {
                'process_id': process_id,
                'status': 'started',
                'type': 'claude',
                'mode': 'async'
            })
        else:
            return SocketResponse.error(command_name, "COMPLETION_FAILED", "Failed to start Claude completion")
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "COMPLETION",
            "aliases": ["SPAWN"],  # For backward compatibility
            "description": "Send a completion request to Claude, either directly or through an agent",
            "parameters": {
                "mode": {
                    "type": "string",
                    "enum": ["sync", "async"],
                    "description": "Execution mode - sync waits for response, async returns immediately"
                },
                "type": {
                    "type": "string", 
                    "enum": ["claude"],
                    "description": "Completion type (only 'claude' supported)",
                    "default": "claude"
                },
                "prompt": {
                    "type": "string",
                    "description": "The prompt/message to send"
                },
                "agent_id": {
                    "type": "string",
                    "description": "Route through specific agent for session continuity (optional)",
                    "optional": True
                },
                "session_id": {
                    "type": "string",
                    "description": "Session ID for conversation continuity (optional)",
                    "optional": True
                },
                "model": {
                    "type": "string",
                    "default": "sonnet",
                    "description": "Claude model to use",
                    "optional": True
                },
                "enable_tools": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to enable Claude tools",
                    "optional": True
                }
            },
            "routing": {
                "with_agent_id": "Routes through the specified agent, maintaining conversation state",
                "without_agent_id": "Direct Claude call, stateless unless session_id provided"
            },
            "examples": [
                {
                    "mode": "sync",
                    "type": "claude",
                    "prompt": "Hello, Claude!",
                    "description": "Simple direct completion"
                },
                {
                    "mode": "sync",
                    "type": "claude",
                    "prompt": "What number did I ask you to remember?",
                    "agent_id": "conversation_agent_1",
                    "description": "Route through agent for session continuity"
                },
                {
                    "mode": "async",
                    "type": "claude", 
                    "prompt": "Analyze this code",
                    "session_id": "session-123",
                    "model": "opus",
                    "description": "Async with explicit session"
                }
            ]
        }