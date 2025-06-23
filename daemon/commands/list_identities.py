#!/usr/bin/env python3
"""
LIST_IDENTITIES command handler - List all system identities
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from ..command_registry import command_handler, CommandHandler
from ..models import ResponseFactory, ListIdentitiesParameters
from ..base_manager import log_operation
from ..timestamp_utils import TimestampManager

@command_handler("LIST_IDENTITIES")
class ListIdentitiesHandler(CommandHandler):
    """Handles LIST_IDENTITIES command"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute list identities operation"""
        # Validate parameters
        try:
            params = ListIdentitiesParameters(**parameters)
        except Exception as e:
            return ResponseFactory.error(
                "LIST_IDENTITIES", 
                "INVALID_PARAMETERS", 
                f"Invalid parameters: {str(e)}"
            )
        
        # Check if identity manager is available
        if not self.context.identity_manager:
            return ResponseFactory.error(
                "LIST_IDENTITIES", 
                "NO_IDENTITY_MANAGER", 
                "Identity manager not available"
            )
        
        # Get all identities using standardized API
        identities_list = self.context.identity_manager.list_identities()
        
        # Apply filters if specified
        if params.filter_role:
            identities_list = [i for i in identities_list if i.get('role') == params.filter_role]
        
        if params.filter_active is not None:
            # Consider an identity active if it has activity within the last 24 hours
            now = TimestampManager.utc_now()
            active_threshold = timedelta(hours=24)
            
            filtered_list = []
            for identity in identities_list:
                last_active_str = identity.get('last_active')
                if last_active_str:
                    try:
                        last_active = TimestampManager.parse_iso_timestamp(last_active_str)
                        is_active = (now - last_active) < active_threshold
                        
                        # Include if matches the filter criteria
                        if params.filter_active == is_active:
                            filtered_list.append(identity)
                    except Exception as e:
                        self.logger.warning(f"Failed to parse last_active for {identity.get('agent_id')}: {e}")
                        # Include identities with unparseable timestamps when filtering for inactive
                        if not params.filter_active:
                            filtered_list.append(identity)
                else:
                    # No last_active means inactive
                    if not params.filter_active:
                        filtered_list.append(identity)
            
            identities_list = filtered_list
        
        # Apply sorting
        if params.sort_by and params.sort_by in ['created_at', 'last_active', 'display_name']:
            reverse = params.order == 'desc'
            identities_list.sort(
                key=lambda x: x.get(params.sort_by, ''), 
                reverse=reverse
            )
        
        # Return standardized list response with full objects
        return ResponseFactory.success("LIST_IDENTITIES", {
            'items': identities_list,
            'total': len(identities_list),
            'metadata': {
                'filtered': bool(params.filter_role or params.filter_active is not None),
                'sort': params.sort_by,
                'order': params.order,
                'filters_applied': {
                    k: v for k, v in {
                        'role': params.filter_role,
                        'active': params.filter_active
                    }.items() if v is not None
                }
            }
        })
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "LIST_IDENTITIES",
            "description": "List all system identities with their full information",
            "parameters": {
                "sort_by": {
                    "type": "string",
                    "description": "Field to sort by (created_at, last_active, display_name)",
                    "optional": True,
                    "default": "created_at"
                },
                "order": {
                    "type": "string",
                    "description": "Sort order: asc or desc",
                    "optional": True,
                    "default": "desc"
                },
                "filter_role": {
                    "type": "string",
                    "description": "Filter identities by role",
                    "optional": True
                },
                "filter_active": {
                    "type": "boolean",
                    "description": "Filter by active status",
                    "optional": True
                }
            },
            "examples": [
                {
                    "description": "List all identities",
                    "command": "LIST_IDENTITIES",
                    "response": {
                        "items": [
                            {
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
                        ],
                        "total": 1,
                        "metadata": {
                            "filtered": false,
                            "sort": "created_at",
                            "order": "desc",
                            "filters_applied": {}
                        }
                    }
                },
                {
                    "description": "List researcher identities only",
                    "parameters": {
                        "filter_role": "researcher",
                        "sort_by": "last_active"
                    }
                }
            ]
        }