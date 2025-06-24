#!/usr/bin/env python3
"""
Command Registry - Self-registering command pattern
Eliminates large if/elif chains and manual command mapping
"""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Type, Optional, Callable
from datetime import datetime
import structlog
from .protocols import BaseCommand, BaseResponse, SocketResponse
from .manager_framework import with_error_handling

# Import all command handlers to trigger registration
from . import commands

logger = structlog.get_logger('daemon.command_registry')


class CommandHandler(ABC):
    """Base class for command handlers"""
    
    command_name: str = None  # Must be set by subclasses
    
    def __init__(self, command_handler_context):
        """
        Initialize with access to daemon context
        
        Args:
            command_handler_context: The CommandHandler instance with manager references
        """
        self.context = command_handler_context
        self.logger = structlog.get_logger(f'handler.{self.command_name}')
    
    @abstractmethod
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, 
                    full_command: Dict[str, Any]) -> BaseResponse:
        """
        Handle the command and return a response
        
        Args:
            parameters: Command parameters
            writer: Stream writer for responses
            full_command: Full command data including metadata
            
        Returns:
            Response object
        """
        pass
    
    @property
    def state_manager(self):
        return self.context.state_manager
    
    @property
    def completion_manager(self):
        return self.context.completion_manager
    
    @property
    def agent_manager(self):
        return self.context.agent_manager
    
    @property
    def message_bus(self):
        return self.context.message_bus
    
    @property
    def identity_manager(self):
        return self.context.identity_manager
    
    @property
    def hot_reload_manager(self):
        return self.context.hot_reload_manager


class CommandRegistry:
    """Registry for self-registering commands with alias support"""
    
    _instance = None
    _handlers: Dict[str, Type[CommandHandler]] = {}
    _aliases: Dict[str, str] = {}  # alias -> primary command name
    _handler_instances: Dict[str, CommandHandler] = {}  # Cache handler instances
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def register(cls, handler_class: Type[CommandHandler], aliases: list = None):
        """Register a command handler with optional aliases"""
        if not handler_class.command_name:
            raise ValueError(f"Handler {handler_class.__name__} must define command_name")
        
        cls._handlers[handler_class.command_name] = handler_class
        logger.info(f"Registered command handler: {handler_class.command_name}")
        
        # Register aliases
        if aliases:
            for alias in aliases:
                cls._aliases[alias] = handler_class.command_name
                logger.info(f"Registered alias: {alias} -> {handler_class.command_name}")
    
    @classmethod
    def get_handler(cls, command_name: str) -> Optional[Type[CommandHandler]]:
        """Get handler class for a command (supports aliases)"""
        # Check if it's an alias first
        if command_name in cls._aliases:
            command_name = cls._aliases[command_name]
        return cls._handlers.get(command_name)
    
    @classmethod
    def list_commands(cls) -> list:
        """List all registered commands (primary names only)"""
        return list(cls._handlers.keys())
    
    @classmethod
    def list_aliases(cls) -> Dict[str, str]:
        """List all command aliases"""
        return cls._aliases.copy()


def command_handler(command_name: str, aliases: list = None):
    """Decorator to register command handlers with optional aliases"""
    def decorator(cls: Type[CommandHandler]):
        cls.command_name = command_name
        CommandRegistry.register(cls, aliases=aliases)
        return cls
    return decorator


# Simplified command handler that uses the registry
class SimplifiedCommandHandler:
    """Simplified command handler using registry pattern"""
    
    def __init__(self, core_daemon, **managers):
        self.core_daemon = core_daemon
        self.state_manager = managers.get('state_manager')
        self.completion_manager = managers.get('completion_manager')
        self.agent_manager = managers.get('agent_manager')
        self.hot_reload_manager = managers.get('hot_reload_manager')
        self.message_bus = managers.get('message_bus')
        self.identity_manager = managers.get('identity_manager')
        self.logger = structlog.get_logger('daemon.command_handler')
    
    @with_error_handling("handle_command")
    async def handle_command(self, command_text: str, writer: asyncio.StreamWriter, 
                           reader: asyncio.StreamReader = None) -> bool:
        """Handle commands using the registry pattern"""
        try:
            # Parse and validate command
            from .command_validator_refactored import validate_command
            is_valid, error_msg, command_data = validate_command(command_text.strip())
            
            if not is_valid:
                await self.send_error_response(writer, "INVALID_COMMAND", error_msg)
                return True
            
            command_name = command_data.get("command")
            parameters = command_data.get("parameters", {})
            
            # Get handler from registry
            handler_class = CommandRegistry.get_handler(command_name)
            if not handler_class:
                await self.send_error_response(writer, "UNKNOWN_COMMAND", 
                                             f"Command '{command_name}' not recognized")
                return True
            
            # Get or create handler instance (singleton pattern for stateful handlers)
            if command_name not in CommandRegistry._handler_instances:
                handler = handler_class(self)
                
                # Initialize handler if it has an initialize method
                if hasattr(handler, 'initialize'):
                    await handler.initialize(self)
                
                # Cache the handler instance
                CommandRegistry._handler_instances[command_name] = handler
            else:
                handler = CommandRegistry._handler_instances[command_name]
            
            response = await handler.handle(parameters, writer, command_data)
            
            # Send response
            if response:
                await self.send_response(writer, response.model_dump())
            
            return True
            
        except Exception as e:
            self.logger.error(f"Command handling error: {e}", exc_info=True)
            await self.send_error_response(writer, "INTERNAL_ERROR", str(e))
            return True
    
    async def send_response(self, writer: asyncio.StreamWriter, response_data: dict) -> bool:
        """Send response to client"""
        try:
            response_json = json.dumps(response_data) + '\n'
            writer.write(response_json.encode())
            await writer.drain()
            return True
        except Exception as e:
            self.logger.error(f"Failed to send response: {e}")
            return True
    
    async def send_error_response(self, writer: asyncio.StreamWriter, error_code: str, 
                                details: str = "") -> bool:
        """Send standardized error response to client"""
        from .protocols import SocketResponse
        response = SocketResponse.error("", error_code, details)
        return await self.send_response(writer, response.model_dump())