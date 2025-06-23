#!/usr/bin/env python3
"""
HEALTH_CHECK command handler - System health status
"""

import asyncio
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler
from ..models import ResponseFactory
from ..base_manager import log_operation

@command_handler("HEALTH_CHECK")
class HealthCheckHandler(CommandHandler):
    """Returns system health status and statistics"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Get system health status"""
        health_data = {
            'status': 'healthy',
            'uptime': 0,  # TODO: Track actual uptime
            'managers': {}
        }
        
        # Check each manager
        if self.context.state_manager:
            sessions = len(self.context.state_manager.sessions)
            health_data['managers']['state'] = {
                'status': 'active',
                'sessions': sessions
            }
        
        if self.context.process_manager:
            processes = len(self.context.process_manager.running_processes)
            health_data['managers']['process'] = {
                'status': 'active',
                'processes': processes
            }
        
        if self.context.agent_manager:
            agents = len(self.context.agent_manager.agents)
            health_data['managers']['agent'] = {
                'status': 'active',
                'agents': agents
            }
        
        if self.context.message_bus:
            # Count total subscribers across all event types
            total_subscribers = sum(len(subs) for subs in self.context.message_bus.subscriptions.values())
            health_data['managers']['message_bus'] = {
                'status': 'active',
                'subscribers': total_subscribers,
                'event_types': len(self.context.message_bus.subscriptions),
                'connections': len(self.context.message_bus.connections)
            }
        
        return ResponseFactory.success("HEALTH_CHECK", health_data)