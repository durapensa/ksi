#!/usr/bin/env python3
"""
GET_COMMANDS handler - List all available commands
"""

import asyncio
from typing import Dict, Any
from ..command_registry import command_handler, CommandHandler, CommandRegistry
from ..models import ResponseFactory
from ..base_manager import log_operation
from ..command_validator import CommandValidator

@command_handler("GET_COMMANDS")
class GetCommandsHandler(CommandHandler):
    """Returns list of available commands with their schemas"""
    
    @log_operation()
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, full_command: Dict[str, Any]) -> Any:
        """Get list of all commands"""
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
        
        # Get legacy commands from validator
        validator = CommandValidator()
        from ..command_schemas import COMMAND_MAPPINGS
        
        for cmd_name in COMMAND_MAPPINGS.keys():
            if cmd_name not in registry_commands:  # Don't duplicate
                try:
                    help_info = validator.get_command_help(cmd_name)
                    commands.append({
                        'command': cmd_name,
                        'source': 'legacy',
                        'description': help_info.get('description', 'No description'),
                        'parameters': help_info.get('parameters', {})
                    })
                except:
                    # If help not available, just add basic info
                    commands.append({
                        'command': cmd_name,
                        'source': 'legacy',
                        'description': 'Legacy command',
                        'parameters': {}
                    })
        
        # Sort by command name
        commands.sort(key=lambda x: x['command'])
        
        return ResponseFactory.success("GET_COMMANDS", {
            'commands': commands,
            'total': len(commands),
            'registry_count': len(registry_commands),
            'legacy_count': len(commands) - len(registry_commands)
        })