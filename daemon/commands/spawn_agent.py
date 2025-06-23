#!/usr/bin/env python3
"""
SPAWN_AGENT command handler - Spawn an agent process with intelligent composition selection
"""

import asyncio
from typing import Dict, Any, List, Optional
from ..command_registry import command_handler, CommandHandler
from ..protocols import SocketResponse, SpawnAgentParameters
from ..manager_framework import log_operation
import sys
import os

# Add path for composition selector
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from prompts.composition_selector import CompositionSelector, SelectionContext

@command_handler("SPAWN_AGENT")
class SpawnAgentHandler(CommandHandler):
    """Handles SPAWN_AGENT command with intelligent composition selection"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute agent spawning with composition selection"""
        # Validate parameters
        try:
            params = SpawnAgentParameters(**parameters)
        except Exception as e:
            return SocketResponse.error("SPAWN_AGENT", "INVALID_PARAMETERS", str(e))
        
        # Check if agent manager is available
        if not self.context.agent_manager:
            return SocketResponse.error("SPAWN_AGENT", "NO_AGENT_MANAGER", "Agent manager not available")
        
        # Use CompositionSelector for intelligent composition selection
        try:
            socket_path = 'sockets/claude_daemon.sock'
            selector = CompositionSelector(socket_path)
            
            # Create selection context from provided parameters
            selection_context = SelectionContext(
                agent_id=params.agent_id or f"agent_{params.profile_name or 'auto'}",
                role=params.role or params.profile_name or "assistant",
                capabilities=params.capabilities,
                task_description=params.task,
                context_variables={"context": params.context}
            )
            
            # Select best composition
            selection_result = await selector.select_composition(selection_context)
            composition_name = selection_result.composition_name
            
            self.logger.info(f"Selected composition '{composition_name}' for agent {params.agent_id} (score: {selection_result.score:.3f})")
            self.logger.debug(f"Selection reasons: {selection_result.reasons}")
            
        except Exception as e:
            self.logger.warning(f"Composition selection failed, falling back to profile: {e}")
            # Fallback to profile-based behavior
            composition_name = params.profile_name or "claude_agent_default"
        
        # Spawn the agent process
        process_id = await self.context.agent_manager.spawn_agent_with_composition(
            composition_name=composition_name,
            task=params.task,
            context=params.context,
            agent_id=params.agent_id,
            profile_fallback=params.profile_name
        )
        
        if not process_id:
            return SocketResponse.error("SPAWN_AGENT", "SPAWN_FAILED", 
                                       f"Failed to spawn agent with composition {composition_name}")
        
        # Generate agent_id if it wasn't provided
        final_agent_id = params.agent_id or f"{composition_name}_{process_id[:8]}"
        
        # Get the newly created agent details
        agent_info = self.context.agent_manager.get_agent(final_agent_id)
        
        # Return standardized response with full agent information
        return SocketResponse.success("SPAWN_AGENT", {
            'agent': {
                'id': final_agent_id,
                'process_id': process_id,
                'composition': composition_name,
                'role': agent_info.get('role') if agent_info else params.role,
                'capabilities': agent_info.get('capabilities', []) if agent_info else params.capabilities,
                'status': 'active',
                'task': params.task,
                'model': agent_info.get('model', params.model) if agent_info else params.model
            },
            'selection': {
                'composition_used': composition_name,
                'fallback_used': 'selection_result' not in locals(),
                'score': getattr(selection_result, 'score', 0.0) if 'selection_result' in locals() else 0.0
            }
        })
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "SPAWN_AGENT",
            "description": "Spawn an agent process with intelligent composition selection based on task and capabilities",
            "parameters": {
                "task": {
                    "type": "string",
                    "description": "Initial task for the agent",
                    "required": True
                },
                "profile_name": {
                    "type": "string",
                    "description": "Agent profile name (fallback if composition selection fails)",
                    "optional": True
                },
                "agent_id": {
                    "type": "string",
                    "description": "Unique agent identifier (auto-generated if not provided)",
                    "optional": True
                },
                "context": {
                    "type": "string",
                    "description": "Additional context for the agent",
                    "optional": True,
                    "default": ""
                },
                "role": {
                    "type": "string",
                    "description": "Role hint for composition selection",
                    "optional": True
                },
                "capabilities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required capabilities for composition selection",
                    "optional": True,
                    "default": []
                },
                "model": {
                    "type": "string",
                    "description": "Claude model to use",
                    "optional": True,
                    "default": "sonnet"
                }
            },
            "examples": [
                {
                    "task": "Research the latest AI developments",
                    "role": "researcher",
                    "capabilities": ["web_search", "analysis"],
                    "context": "Focus on LLM advancements in 2024"
                },
                {
                    "task": "Review and refactor the authentication module",
                    "profile_name": "software_developer",
                    "agent_id": "dev_agent_001",
                    "capabilities": ["code_review", "refactoring"]
                }
            ]
        }