#!/usr/bin/env python3
"""
GET_PROCESSES command handler - List running processes
"""

import asyncio
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler
from ..models import ResponseFactory
from ..base_manager import log_operation

@command_handler("GET_PROCESSES")
class GetProcessesHandler(CommandHandler):
    """Returns list of running Claude processes"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Get list of running processes"""
        if not self.context.process_manager:
            return ResponseFactory.error("GET_PROCESSES", "NO_PROCESS_MANAGER", "Process manager not available")
        
        # Use standardized API
        processes = self.context.process_manager.list_processes()
        
        return ResponseFactory.success("GET_PROCESSES", {
            'processes': processes,
            'total': len(processes)
        })