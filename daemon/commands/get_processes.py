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
        
        processes = []
        for proc_id, proc_info in self.context.process_manager.running_processes.items():
            # Extract process details
            process_data = {
                'process_id': proc_id,
                'status': 'running' if proc_info.get('process') and proc_info['process'].returncode is None else 'completed',
                'type': proc_info.get('type', 'claude'),
                'session_id': proc_info.get('session_id'),
                'agent_id': proc_info.get('agent_id'),
                'model': proc_info.get('model', 'unknown'),
                'started_at': proc_info.get('started_at', 'unknown')
            }
            
            # Add return code if process completed
            if proc_info.get('process') and proc_info['process'].returncode is not None:
                process_data['return_code'] = proc_info['process'].returncode
            
            processes.append(process_data)
        
        return ResponseFactory.success("GET_PROCESSES", {
            'processes': processes,
            'total': len(processes)
        })