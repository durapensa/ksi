#!/usr/bin/env python3
"""
GET_COMMANDS handler - List all available commands
"""

import asyncio
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler, CommandRegistry
from ..socket_protocol_models import SocketResponse, GetCommandsParameters
from ..manager_framework import log_operation
@command_handler("GET_COMMANDS", aliases=["HELP"])
class GetCommandsHandler(CommandHandler):
    """Returns list of available commands with their schemas"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Get list of all commands"""
        try:
            commands = []
            
            # Get commands from registry (new pattern)
            registry_commands = CommandRegistry.list_commands()
            for cmd_name in registry_commands:
                handler_class = CommandRegistry.get_handler(cmd_name)
                if hasattr(handler_class, 'get_help'):
                    help_info = handler_class.get_help()
                    commands.append({
                        'command': cmd_name,
                        'source': 'registry',
                        'description': help_info.get('description', 'No description'),
                        'parameters': help_info.get('parameters', {})
                    })
                else:
                    commands.append({
                        'command': cmd_name,
                        'source': 'registry',
                        'description': 'Command registered',
                        'parameters': {}
                    })
            
            # No legacy commands - all commands are now in the registry
            
            # Sort by command name
            commands.sort(key=lambda x: x['command'])
            
            # Add alias information
            aliases = CommandRegistry.list_aliases()
            
            return SocketResponse.help(commands, aliases)
        except Exception as e:
            return SocketResponse.error("GET_COMMANDS", str(type(e).__name__), str(e))