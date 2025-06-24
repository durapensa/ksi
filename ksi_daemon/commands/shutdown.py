#!/usr/bin/env python3
"""
SHUTDOWN command handler - Gracefully shuts down the daemon
"""

import asyncio
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler
from ..protocols import SocketResponse
from ..manager_framework import log_operation


@command_handler("SHUTDOWN")
class ShutdownHandler(CommandHandler):
    """Handles SHUTDOWN command for graceful daemon shutdown"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Execute graceful shutdown"""
        self.logger.info("Received SHUTDOWN command")
        
        response = SocketResponse.success("SHUTDOWN", {
            'status': 'shutting_down',
            'message': 'SHUTTING DOWN',
            'details': 'Daemon shutdown initiated'
        })
        
        # Send response before closing
        await self.context.send_response(writer, response.model_dump())
        
        # Close connection
        writer.close()
        await writer.wait_closed()
        
        # Signal shutdown
        if hasattr(self.context, 'core_daemon') and self.context.core_daemon:
            self.context.core_daemon.shutdown_event.set()
        
        # Return the already-sent response as dict
        return response.model_dump()
    
    @classmethod
    def get_help(cls) -> Dict[str, Any]:
        """Get command help information"""
        return {
            "command": "SHUTDOWN",
            "description": "Gracefully shut down the daemon",
            "parameters": {},
            "examples": [
                {}
            ],
            "notes": [
                "Cleanly shuts down all components",
                "Closes all active connections",
                "Saves state if needed",
                "Use daemon_control.sh for safe shutdown"
            ]
        }