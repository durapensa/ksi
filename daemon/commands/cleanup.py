#!/usr/bin/env python3
"""
CLEANUP command handler - Manages system cleanup operations
"""

import asyncio
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from ..command_registry import command_handler, CommandHandler
from ..socket_protocol_models import SocketResponse, CleanupParameters
from ..manager_framework import log_operation
from ..config import config

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
            return SocketResponse.error("CLEANUP", "INVALID_PARAMETERS", str(e))
        
        # Perform cleanup based on type
        results = []
        
        if params.cleanup_type in ['logs', 'all']:
            result = self._cleanup_logs()
            results.append(f"Logs: {result}")
        
        if params.cleanup_type in ['sessions', 'all']:
            result = self._cleanup_sessions()
            results.append(f"Sessions: {result}")
        
        if params.cleanup_type in ['sockets', 'all']:
            result = self._cleanup_sockets()
            results.append(f"Sockets: {result}")
        
        # Return success response
        return SocketResponse.cleanup(
            cleanup_type=params.cleanup_type,
            details=' | '.join(results)
        )
    
    def _cleanup_logs(self) -> str:
        """Clean up log files in session logs directory"""
        try:
            log_dir = config.session_log_dir
            if not log_dir.exists():
                return "Session log directory does not exist"
            
            count = 0
            for file in log_dir.glob('*.jsonl'):
                if file.name != 'latest.jsonl':
                    file.unlink()
                    count += 1
            
            return f"Deleted {count} log files"
        except Exception as e:
            return f"Error cleaning logs: {e}"
    
    def _cleanup_sessions(self) -> str:
        """Clean up tracked sessions"""
        if self.context.state_manager:
            sessions_cleared = self.context.state_manager.clear_sessions()
            return f"Cleared {sessions_cleared} tracked sessions"
        return "No state manager available"
    
    def _cleanup_sockets(self) -> str:
        """Clean up socket files"""
        try:
            socket_dir = Path('sockets')
            if not socket_dir.exists():
                return "No sockets directory found"
            
            count = 0
            for file in socket_dir.iterdir():
                if file.name != 'claude_daemon.sock' and file.is_file():
                    file.unlink()
                    count += 1
            
            return f"Deleted {count} socket files"
        except Exception as e:
            return f"Error cleaning sockets: {e}"
    
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