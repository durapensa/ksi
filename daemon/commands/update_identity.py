#!/usr/bin/env python3
"""
UPDATE_IDENTITY command handler - Update an existing identity
"""

import asyncio
from typing import Dict, Any, List
from ..command_registry import command_handler, CommandHandler
from ..socket_protocol_models import SocketResponse, UpdateIdentityParameters
from ..manager_framework import log_operation

@command_handler("UPDATE_IDENTITY")
class UpdateIdentityHandler(CommandHandler):
    """Handles UPDATE_IDENTITY command"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute update identity operation"""
        # Validate parameters
        try:
            params = UpdateIdentityParameters(**parameters)
        except Exception as e:
            return SocketResponse.error(
                "UPDATE_IDENTITY", 
                "INVALID_PARAMETERS", 
                f"Invalid parameters: {str(e)}"
            )
        
        # Check if identity manager is available
        if not self.context.identity_manager:
            return SocketResponse.error(
                "UPDATE_IDENTITY", 
                "NO_IDENTITY_MANAGER", 
                "Identity manager not available"
            )
        
        # Get the current identity to track changes
        current_identity = self.context.identity_manager.get_identity(params.agent_id)
        if not current_identity:
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
                error_msg += "No identities exist yet. "
            error_msg += "Use LIST_IDENTITIES to see all identities or CREATE_IDENTITY to create a new one."
            
            return SocketResponse.error(
                "UPDATE_IDENTITY",
                "IDENTITY_NOT_FOUND",
                error_msg
            )
        
        # Track what fields are being changed
        changes: List[str] = []
        for key, new_value in params.updates.items():
            if key in current_identity:
                old_value = current_identity[key]
                if old_value != new_value:
                    changes.append(key)
            else:
                # New field being added
                changes.append(key)
        
        # Perform the update
        updated_identity = self.context.identity_manager.update_identity(params.agent_id, params.updates)
        
        if not updated_identity:
            return SocketResponse.error(
                "UPDATE_IDENTITY",
                "UPDATE_FAILED",
                f"Failed to update identity for agent_id: {params.agent_id}"
            )
        
        # Return standardized update response
        return SocketResponse.success("UPDATE_IDENTITY", {
            'identity': updated_identity,
            'updated': True,
            'changes': changes
        })
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "UPDATE_IDENTITY",
            "description": "Update an existing identity's information",
            "parameters": {
                "agent_id": {
                    "type": "string",
                    "description": "The agent ID whose identity to update",
                    "required": True
                },
                "updates": {
                    "type": "object",
                    "description": "Fields to update (display_name, role, personality_traits, appearance, preferences, etc.)",
                    "required": True,
                    "notes": "Protected fields (identity_uuid, agent_id, created_at) cannot be updated"
                }
            },
            "examples": [
                {
                    "description": "Update display name and role",
                    "parameters": {
                        "agent_id": "research_001",
                        "updates": {
                            "display_name": "Senior Research Analyst",
                            "role": "analyst"
                        }
                    },
                    "response": {
                        "identity": {
                            "identity_uuid": "b4f3c8d1-2e4a-4b7c-9d3f-1a2b3c4d5e6f",
                            "agent_id": "research_001",
                            "display_name": "Senior Research Analyst",
                            "role": "analyst",
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
                        },
                        "updated": True,
                        "changes": ["display_name", "role"]
                    }
                },
                {
                    "description": "Update personality traits and preferences",
                    "parameters": {
                        "agent_id": "creative_writer",
                        "updates": {
                            "personality_traits": ["imaginative", "eloquent", "empathetic", "witty", "insightful"],
                            "preferences": {
                                "communication_style": "creative",
                                "verbosity": "expressive",
                                "formality": "casual"
                            }
                        }
                    }
                },
                {
                    "description": "Error case - attempt to update protected field",
                    "parameters": {
                        "agent_id": "research_001",
                        "updates": {
                            "agent_id": "new_id",
                            "display_name": "Renamed Agent"
                        }
                    },
                    "response": {
                        "identity": {
                            "identity_uuid": "b4f3c8d1-2e4a-4b7c-9d3f-1a2b3c4d5e6f",
                            "agent_id": "research_001",
                            "display_name": "Renamed Agent",
                            "role": "researcher",
                            "note": "agent_id was not changed (protected field)"
                        },
                        "updated": True,
                        "changes": ["display_name"]
                    }
                }
            ]
        }