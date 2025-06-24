#!/usr/bin/env python3
"""
GET_IDENTITY command handler - Get a specific identity by agent_id
"""

import asyncio
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler
from ..protocols import SocketResponse, GetIdentityParameters
from ..manager_framework import log_operation

@command_handler("GET_IDENTITY")
class GetIdentityHandler(CommandHandler):
    """Handles GET_IDENTITY command"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute get identity operation"""
        # Validate parameters
        try:
            params = GetIdentityParameters(**parameters)
        except Exception as e:
            return SocketResponse.error(
                "GET_IDENTITY", 
                "INVALID_PARAMETERS", 
                f"Invalid parameters: {str(e)}"
            )
        
        # Check if identity manager is available
        if not self.context.identity_manager:
            return SocketResponse.error(
                "GET_IDENTITY", 
                "NO_IDENTITY_MANAGER", 
                "Identity manager not available"
            )
        
        # Get identity using agent_id
        identity = self.context.identity_manager.get_identity(params.agent_id)
        
        if not identity:
            # Get list of available agent_ids for helpful error message
            all_identities = self.context.identity_manager.list_identities()
            available_agents = [i['agent_id'] for i in all_identities][:5]  # Show first 5
            
            # Build comprehensive error message with suggestions
            error_msg = f"Identity not found for agent_id: {params.agent_id}. "
            
            if available_agents:
                error_msg += f"Available identities: {', '.join(available_agents)}"
                if len(all_identities) > 5:
                    error_msg += f" (and {len(all_identities) - 5} more)"
                error_msg += ". "
            else:
                error_msg += "No identities exist yet. "
            
            error_msg += "Use LIST_IDENTITIES to see all identities or CREATE_IDENTITY to create a new one."
            
            return SocketResponse.error(
                "GET_IDENTITY",
                "IDENTITY_NOT_FOUND",
                error_msg
            )
        
        # Return the full identity object directly as the result
        return SocketResponse.success("GET_IDENTITY", identity)
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "GET_IDENTITY",
            "description": "Get complete identity information for a specific agent",
            "parameters": {
                "agent_id": {
                    "type": "string",
                    "description": "The agent ID to retrieve identity for",
                    "required": True
                }
            },
            "examples": [
                {
                    "description": "Get identity for a specific agent",
                    "parameters": {
                        "agent_id": "research_001"
                    },
                    "response": {
                        "identity_uuid": "b4f3c8d1-2e4a-4b7c-9d3f-1a2b3c4d5e6f",
                        "agent_id": "research_001",
                        "display_name": "Research Assistant",
                        "role": "researcher",
                        "personality_traits": ["analytical", "thorough", "curious", "methodical"],
                        "appearance": {
                            "avatar_style": "academic",
                            "color_theme": "blue",
                            "icon": "🧑‍🔬"
                        },
                        "created_at": "2025-06-23T12:00:00Z",
                        "last_active": "2025-06-23T15:30:00Z",
                        "conversation_count": 5,
                        "sessions": [
                            {
                                "session_id": "session_123",
                                "started_at": "2025-06-23T14:00:00Z"
                            }
                        ],
                        "preferences": {
                            "communication_style": "professional",
                            "verbosity": "moderate",
                            "formality": "balanced"
                        },
                        "stats": {
                            "messages_sent": 42,
                            "conversations_participated": 5,
                            "tasks_completed": 12,
                            "tools_used": ["web_search", "data_analysis"]
                        }
                    }
                },
                {
                    "description": "Error case - identity not found",
                    "parameters": {
                        "agent_id": "unknown_agent"
                    },
                    "response": {
                        "error": {
                            "code": "IDENTITY_NOT_FOUND",
                            "message": "Identity not found for agent_id: unknown_agent. Available identities: research_001, code_assistant, data_analyst (and 2 more). Use LIST_IDENTITIES to see all identities or CREATE_IDENTITY to create a new one."
                        }
                    }
                }
            ]
        }