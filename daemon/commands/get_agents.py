#!/usr/bin/env python3
"""
GET_AGENTS command handler - List all registered agents
"""

import asyncio
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler
from ..models import ResponseFactory
from ..base_manager import log_operation
from pydantic import BaseModel

class GetAgentsParameters(BaseModel):
    """Parameters for GET_AGENTS command"""
    # No parameters needed for this command
    pass

@command_handler("GET_AGENTS")
class GetAgentsHandler(CommandHandler):
    """Handles GET_AGENTS command"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute get agents operation"""
        # No parameters to validate for this command
        
        # Get agent manager
        if not self.context.agent_manager:
            # Return empty agents list if no manager available
            return ResponseFactory.success("GET_AGENTS", {'agents': {}})
        
        # Use standardized list_agents() API
        agents_list = self.context.agent_manager.list_agents()
        
        # Convert list to dict format for backward compatibility
        agents_dict = {}
        for agent in agents_list:
            agent_id = agent['agent_id']
            agents_dict[agent_id] = {
                'role': agent.get('role'),
                'status': agent.get('status'),
                'capabilities': agent.get('capabilities', [])
            }
        
        return ResponseFactory.success("GET_AGENTS", {'agents': agents_dict})
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "GET_AGENTS",
            "description": "List all registered agents with their roles and capabilities",
            "parameters": {},
            "examples": [
                {
                    "description": "Get all agents",
                    "command": "GET_AGENTS",
                    "response": {
                        "agents": {
                            "research_agent_001": {
                                "role": "researcher",
                                "status": "active",
                                "capabilities": ["web_search", "data_analysis"]
                            },
                            "code_assistant": {
                                "role": "developer",
                                "status": "active",
                                "capabilities": ["code_review", "debugging"]
                            }
                        }
                    }
                }
            ]
        }