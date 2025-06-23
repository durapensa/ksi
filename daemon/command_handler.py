#!/usr/bin/env python3

"""
Command Handler - JSON Protocol v2.0 Command routing and processing
Handles all daemon commands using validated JSON format only
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger('daemon')

class CommandHandler:
    """Handler for daemon commands using JSON Protocol v2.0"""
    
    def __init__(self, core_daemon, state_manager=None, process_manager=None, agent_manager=None, utils_manager=None, hot_reload_manager=None, message_bus=None, identity_manager=None):
        # Store references to all managers for cross-module communication
        self.core_daemon = core_daemon
        self.state_manager = state_manager
        self.process_manager = process_manager
        self.agent_manager = agent_manager
        self.utils_manager = utils_manager
        self.hot_reload_manager = hot_reload_manager
        self.message_bus = message_bus
        self.identity_manager = identity_manager
        
        # JSON Protocol v2.0 - Initialize JSON handlers
        from .json_handlers import CommandHandlers
        self.handlers = CommandHandlers(self)
    
    async def handle_command(self, command_text: str, writer: asyncio.StreamWriter, reader: asyncio.StreamReader = None) -> bool:
        """Handle JSON protocol v2.0 commands only"""
        try:
            # Store reader for potential future use
            self._current_reader = reader
            
            # Import validator
            from .command_validator import validate_command
            
            # Parse and validate JSON command
            is_valid, error_msg, command_data = validate_command(command_text.strip())
            
            if not is_valid:
                return await self.send_error_response(writer, "INVALID_COMMAND", error_msg)
            
            command_name = command_data.get("command")
            parameters = command_data.get("parameters", {})
            
            # Route to appropriate handler
            return await self._route_command(command_name, parameters, writer, command_data)
                
        except Exception as e:
            logger.error(f"Error processing command: {e}")
            return await self.send_error_response(writer, "COMMAND_PROCESSING_FAILED", str(e))
    
    async def _route_command(self, command_name: str, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Route JSON command to appropriate handler method"""
        
        # Check command registry first (new pattern)
        from .command_registry import CommandRegistry
        handler_class = CommandRegistry.get_handler(command_name)
        if handler_class:
            # Use new command handler pattern
            handler = handler_class(self)  # Pass self as context
            logger.info(f"Using registry handler for command: {command_name}")
            response = await handler.handle(parameters, writer, full_command)
            
            # If response is a Pydantic model, convert to dict
            if hasattr(response, 'model_dump'):
                return await self.send_response(writer, response.model_dump())
            else:
                return await self.send_response(writer, response)
        
        # Fall back to old handlers dictionary
        handlers = {
            'SPAWN': self.handlers._handle_spawn,
            'CLEANUP': self.handlers._handle_cleanup,
            'RELOAD': self.handlers._handle_reload,
            'REGISTER_AGENT': self.handlers._handle_register_agent,
            'GET_AGENTS': self.handlers._handle_get_agents,
            'SPAWN_AGENT': self.handlers._handle_spawn_agent,
            'ROUTE_TASK': self.handlers._handle_route_task,
            'SET_SHARED': self.handlers._handle_set_shared,
            'GET_SHARED': self.handlers._handle_get_shared,
            'SUBSCRIBE': self.handlers._handle_subscribe,
            'PUBLISH': self.handlers._handle_publish,
            'AGENT_CONNECTION': self.handlers._handle_agent_connection,
            'HEALTH_CHECK': self.handlers._handle_health_check,
            'GET_PROCESSES': self.handlers._handle_get_processes,
            'LOAD_STATE': self.handlers._handle_load_state,
            'RELOAD_DAEMON': self.handlers._handle_reload_daemon,
            'SHUTDOWN': self.handlers._handle_shutdown,
            'MESSAGE_BUS_STATS': self.handlers._handle_message_bus_stats,
            'GET_COMMANDS': self.handlers._handle_get_commands,
            'GET_COMPOSITIONS': self.handlers._handle_get_compositions,
            'GET_COMPOSITION': self.handlers._handle_get_composition,
            'VALIDATE_COMPOSITION': self.handlers._handle_validate_composition,
            'LIST_COMPONENTS': self.handlers._handle_list_components,
            'COMPOSE_PROMPT': self.handlers._handle_compose_prompt,
            'CREATE_IDENTITY': self.handlers._handle_create_identity,
            'UPDATE_IDENTITY': self.handlers._handle_update_identity,
            'GET_IDENTITY': self.handlers._handle_get_identity,
            'LIST_IDENTITIES': self.handlers._handle_list_identities,
            'REMOVE_IDENTITY': self.handlers._handle_remove_identity
        }
        
        handler = handlers.get(command_name)
        if handler:
            logger.info(f"Using legacy handler for command: {command_name}")
            return await handler(parameters, writer, full_command)
        else:
            return await self.send_error_response(writer, "UNKNOWN_COMMAND", f"Command '{command_name}' not recognized")
    
    async def send_response(self, writer: asyncio.StreamWriter, response: dict) -> bool:
        """Send JSON response to client"""
        try:
            response_str = json.dumps(response) + '\n'
            writer.write(response_str.encode())
            await writer.drain()
            return True
        except Exception as e:
            logger.error(f"Failed to send response: {e}")
            return True
    
    async def send_error_response(self, writer: asyncio.StreamWriter, error_code: str, details: str = "") -> bool:
        """Send standardized error response to client"""
        return await self.send_response(writer, {
            'status': 'error',
            'error': {
                'code': error_code,
                'message': details,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
        })
    
    async def send_text_response(self, writer: asyncio.StreamWriter, text: str) -> bool:
        """Send plain text response - deprecated, kept for compatibility"""
        logger.warning("send_text_response is deprecated - use send_response with JSON")
        try:
            writer.write(text.encode() + b'\n')
            await writer.drain()
            return True
        except Exception as e:
            logger.error(f"Failed to send text response: {e}")
            return True