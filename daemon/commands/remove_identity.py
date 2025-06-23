#!/usr/bin/env python3
"""
REMOVE_IDENTITY command handler - Remove an identity from the system
"""

import asyncio
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler
from ..models import ResponseFactory, RemoveIdentityParameters
from ..base_manager import log_operation

@command_handler("REMOVE_IDENTITY")
class RemoveIdentityHandler(CommandHandler):
    """Handles REMOVE_IDENTITY command"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute remove identity operation"""
        # Validate parameters
        try:
            params = RemoveIdentityParameters(**parameters)
        except Exception as e:
            return ResponseFactory.error(
                "REMOVE_IDENTITY", 
                "INVALID_PARAMETERS", 
                f"Invalid parameters: {str(e)}"
            )
        
        # Check if identity manager is available
        if not self.context.identity_manager:
            return ResponseFactory.error(
                "REMOVE_IDENTITY", 
                "NO_IDENTITY_MANAGER", 
                "Identity manager not available"
            )
        
        # Remove the identity and get the removed data
        removed_identity = self.context.identity_manager.remove_identity(params.agent_id)
        
        if not removed_identity:
            # Get list of available agent_ids for helpful error message
            all_identities = self.context.identity_manager.list_identities()
            available_agents = [i['agent_id'] for i in all_identities][:5]
            
            error_msg = f"Identity not found for agent_id: {params.agent_id}. "
            if available_agents:
                error_msg += f"Available identities: {', '.join(available_agents)}"
                if len(all_identities) > 5:
                    error_msg += f" (and {len(all_identities) - 5} more)"
                error_msg += ". "
            else:
                error_msg += "No identities exist. "
            error_msg += "Use LIST_IDENTITIES to see all identities."
            
            return ResponseFactory.error(
                "REMOVE_IDENTITY",
                "IDENTITY_NOT_FOUND",
                error_msg
            )
        
        # Return standardized deletion response with removed data for potential undo
        return ResponseFactory.success("REMOVE_IDENTITY", {
            'deleted': True,
            'identity': removed_identity
        })
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "REMOVE_IDENTITY",
            "description": "Remove an identity from the system",
            "parameters": {
                "agent_id": {
                    "type": "string",
                    "description": "The agent ID whose identity to remove",
                    "required": True
                }
            },
            "examples": [
                {
                    "description": "Remove an identity",
                    "parameters": {
                        "agent_id": "research_001"
                    },
                    "response": {
                        "deleted": true,
                        "identity": {
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
                            "last_active": "2025-06-23T16:45:00Z",
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
                            "message": "Identity not found for agent_id: unknown_agent. Available identities: research_001, code_assistant, data_analyst (and 2 more). Use LIST_IDENTITIES to see all identities."
                        }
                    }
                }
            ],
            "notes": [
                "The removed identity data is returned in the response for potential undo operations",
                "This operation is permanent unless you recreate the identity with CREATE_IDENTITY",
                "Active sessions and connections are not affected by removing an identity"
            ]
        }