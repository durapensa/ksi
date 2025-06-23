#!/usr/bin/env python3
"""
REGISTER_AGENT command handler - Register a new agent with role and capabilities
"""

import asyncio
from typing import Dict, Any, List, Optional
from ..command_registry import command_handler, CommandHandler
from ..protocols import SocketResponse, RegisterAgentParameters
from ..manager_framework import log_operation

@command_handler("REGISTER_AGENT")
class RegisterAgentHandler(CommandHandler):
    """Handles REGISTER_AGENT command"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute agent registration"""
        # Validate parameters
        try:
            params = RegisterAgentParameters(**parameters)
        except Exception as e:
            return SocketResponse.error("REGISTER_AGENT", "INVALID_PARAMETERS", str(e))
        
        # Check if agent manager is available
        if not self.context.agent_manager:
            return SocketResponse.error("REGISTER_AGENT", "NO_AGENT_MANAGER", "Agent manager not available")
        
        # Create agent using standardized API
        agent_data = {
            'agent_id': params.agent_id,
            'role': params.role,
            'capabilities': params.capabilities
        }
        
        agent_id = self.context.agent_manager.create_agent(agent_data)
        
        return SocketResponse.success("REGISTER_AGENT", {
            'status': 'registered',
            'agent_id': agent_id,
            'role': params.role,
            'capabilities': params.capabilities
        })
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "REGISTER_AGENT",
            "description": "Register a new agent with specified role and capabilities",
            "parameters": {
                "agent_id": {
                    "type": "string",
                    "description": "Unique identifier for the agent",
                    "required": True
                },
                "role": {
                    "type": "string",
                    "description": "Agent's primary role (e.g., assistant, researcher, analyst)",
                    "required": True
                },
                "capabilities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of agent capabilities",
                    "optional": True,
                    "default": []
                }
            },
            "examples": [
                {
                    "agent_id": "research_agent_001",
                    "role": "researcher",
                    "capabilities": ["web_search", "data_analysis", "report_generation"]
                },
                {
                    "agent_id": "code_assistant",
                    "role": "developer",
                    "capabilities": ["code_review", "debugging", "refactoring"]
                }
            ]
        }