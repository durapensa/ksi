#!/usr/bin/env python3
"""
RELOAD_DAEMON command handler - Hot reload daemon with zero downtime
"""

import asyncio
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler
from ..protocols import SocketResponse
from ..manager_framework import log_operation


@command_handler("RELOAD_DAEMON")
class ReloadDaemonHandler(CommandHandler):
    """Handles RELOAD_DAEMON command for zero-downtime daemon reload"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute hot reload of daemon"""
        # Check hot reload manager availability
        if not self.context.hot_reload_manager:
            return SocketResponse.error("RELOAD_DAEMON", "NO_HOT_RELOAD_MANAGER", "Hot reload manager not available")
        
        # Execute hot reload
        result = await self.context.hot_reload_manager.hot_reload_daemon()
        
        return SocketResponse.success("RELOAD_DAEMON", result)
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "RELOAD_DAEMON",
            "description": "Hot reload the daemon process with zero downtime",
            "parameters": {},
            "examples": [
                {}
            ],
            "notes": [
                "Preserves all active connections and state",
                "Spawns new daemon process before shutting down old one",
                "State is serialized and restored in the new process",
                "Use when daemon code has been updated"
            ]
        }