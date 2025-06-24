#!/usr/bin/env python3
"""
CREATE_IDENTITY command handler - Create a new system identity
"""

import asyncio
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler
from ..protocols import SocketResponse, CreateIdentityParameters
from ..manager_framework import log_operation

@command_handler("CREATE_IDENTITY")
class CreateIdentityHandler(CommandHandler):
    """Handles CREATE_IDENTITY command"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute create identity operation"""
        # Validate parameters
        try:
            params = CreateIdentityParameters(**parameters)
        except Exception as e:
            return SocketResponse.error(
                "CREATE_IDENTITY", 
                "INVALID_PARAMETERS", 
                f"Invalid parameters: {str(e)}"
            )
        
        # Check if identity manager is available
        if not self.context.identity_manager:
            return SocketResponse.error(
                "CREATE_IDENTITY", 
                "NO_IDENTITY_MANAGER", 
                "Identity manager not available"
            )
        
        # Check if identity already exists
        existing_identity = self.context.identity_manager.get_identity(params.agent_id)
        if existing_identity:
            return SocketResponse.error(
                "CREATE_IDENTITY",
                "IDENTITY_EXISTS",
                f"Identity already exists for agent_id: {params.agent_id}. Use UPDATE_IDENTITY to modify existing identity."
            )
        
        # Create the identity with all provided and generated fields
        identity = self.context.identity_manager.create_identity(
            agent_id=params.agent_id,
            display_name=params.display_name,
            personality_traits=params.personality_traits,
            role=params.role,
            appearance=params.appearance
        )
        
        # Return standardized creation response
        return SocketResponse.success("CREATE_IDENTITY", {
            'identity': identity,
            'created': True
        })
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "CREATE_IDENTITY",
            "description": "Create a new system identity for an agent",
            "parameters": {
                "agent_id": {
                    "type": "string",
                    "description": "Unique identifier for the agent",
                    "required": True
                },
                "display_name": {
                    "type": "string",
                    "description": "Human-friendly display name",
                    "optional": True,
                    "default": "Auto-generated based on role"
                },
                "role": {
                    "type": "string",
                    "description": "Agent's primary role (researcher, coder, debater, teacher, creative, analyst, collaborator, orchestrator)",
                    "optional": True,
                    "default": "general"
                },
                "personality_traits": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of personality traits",
                    "optional": True,
                    "default": "Auto-generated based on role"
                },
                "appearance": {
                    "type": "object",
                    "description": "Appearance configuration (avatar_style, color_theme, icon)",
                    "optional": True,
                    "default": "Auto-generated based on role"
                }
            },
            "examples": [
                {
                    "description": "Create a researcher identity with auto-generated traits",
                    "parameters": {
                        "agent_id": "research_001",
                        "display_name": "Research Assistant",
                        "role": "researcher"
                    },
                    "response": {
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
                            "last_active": "2025-06-23T12:00:00Z",
                            "conversation_count": 0,
                            "sessions": [],
                            "preferences": {
                                "communication_style": "professional",
                                "verbosity": "moderate",
                                "formality": "balanced"
                            },
                            "stats": {
                                "messages_sent": 0,
                                "conversations_participated": 0,
                                "tasks_completed": 0,
                                "tools_used": []
                            }
                        },
                        "created": True
                    }
                },
                {
                    "description": "Create a custom identity with specific traits",
                    "parameters": {
                        "agent_id": "creative_writer",
                        "display_name": "Creative Writing Assistant",
                        "role": "creative",
                        "personality_traits": ["imaginative", "eloquent", "empathetic", "playful"],
                        "appearance": {
                            "avatar_style": "artistic",
                            "color_theme": "purple",
                            "icon": "✍️"
                        }
                    }
                },
                {
                    "description": "Error case - identity already exists",
                    "parameters": {
                        "agent_id": "research_001"
                    },
                    "response": {
                        "error": {
                            "code": "IDENTITY_EXISTS",
                            "message": "Identity already exists for agent_id: research_001. Use UPDATE_IDENTITY to modify existing identity."
                        }
                    }
                }
            ]
        }