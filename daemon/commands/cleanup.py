#!/usr/bin/env python3
"""
CLEANUP command handler - Manages system cleanup operations
"""

import asyncio
from typing import Dict, Any, Optional
from ..command_registry import command_handler, CommandHandler
from ..models import ResponseFactory
from ..base_manager import log_operation
from pydantic import BaseModel, Field, field_validator

class CleanupParameters(BaseModel):
    """Parameters for CLEANUP command"""
    cleanup_type: str = Field(..., description="Type of cleanup: logs, sessions, sockets, or all")
    
    @field_validator('cleanup_type')
    def validate_cleanup_type(cls, v):
        valid_types = ['logs', 'sessions', 'sockets', 'all']
        if v not in valid_types:
            raise ValueError(f"Invalid cleanup_type: {v}. Must be one of: {', '.join(valid_types)}")
        return v

@command_handler("CLEANUP")
class CleanupHandler(CommandHandler):
    """Handles CLEANUP command for various system resources"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute cleanup operation"""
        # Validate parameters
        try:
            params = CleanupParameters(**parameters)
        except Exception as e:
            return ResponseFactory.error("CLEANUP", "INVALID_PARAMETERS", str(e))
        
        # Get utils manager
        if not self.context.utils_manager:
            return ResponseFactory.error("CLEANUP", "NO_UTILS_MANAGER", "Utils manager not available")
        
        # Perform cleanup
        result = self.context.utils_manager.cleanup(params.cleanup_type)
        
        # Return success response
        return ResponseFactory.success("CLEANUP", {
            'status': 'cleaned',
            'cleanup_type': params.cleanup_type,
            'details': result
        })
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "CLEANUP",
            "description": "Clean up system resources (logs, sessions, sockets)",
            "parameters": {
                "cleanup_type": {
                    "type": "string",
                    "enum": ["logs", "sessions", "sockets", "all"],
                    "description": "Type of cleanup to perform"
                }
            },
            "examples": [
                {"cleanup_type": "logs"},
                {"cleanup_type": "all"}
            ]
        }