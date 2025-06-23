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
    
    def __init__(self, core_daemon, state_manager=None, completion_manager=None, agent_manager=None, hot_reload_manager=None, message_bus=None, identity_manager=None):
        # Store references to all managers for cross-module communication
        self.core_daemon = core_daemon
        self.state_manager = state_manager
        self.completion_manager = completion_manager
        self.agent_manager = agent_manager
        self.hot_reload_manager = hot_reload_manager
        self.message_bus = message_bus
        self.identity_manager = identity_manager
        
        # All commands now use CommandRegistry pattern
    
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
        
        # All commands use registry pattern
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