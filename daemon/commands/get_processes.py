#!/usr/bin/env python3
"""
GET_PROCESSES command handler - List running processes
"""

import asyncio
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler
from ..socket_protocol_models import SocketResponse, GetProcessesParameters
from ..manager_framework import log_operation

@command_handler("GET_PROCESSES")
class GetProcessesHandler(CommandHandler):
    """Returns list of running Claude processes"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Get list of running processes"""
        if not self.context.completion_manager:
            return SocketResponse.error("GET_PROCESSES", "NO_PROCESS_MANAGER", "Process manager not available")
        
        # Use standardized API
        processes = self.context.completion_manager.list_processes()
        
        return SocketResponse.get_processes(processes)