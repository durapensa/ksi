#!/usr/bin/env python3
"""
Command Registry - Self-registering command pattern
Eliminates large if/elif chains and manual command mapping
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Type, Optional, Callable
from datetime import datetime
import structlog
from .models import BaseCommand, BaseResponse, ResponseFactory
from .base_manager import with_error_handling

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
    def process_manager(self):
        return self.context.process_manager
    
    @property
    def agent_manager(self):
        return self.context.agent_manager
    
    @property
    def utils_manager(self):
        return self.context.utils_manager
    
    @property
    def message_bus(self):
        return self.context.message_bus
    
    @property
    def identity_manager(self):
        return self.context.identity_manager


class CommandRegistry:
    """Registry for self-registering commands"""
    
    _instance = None
    _handlers: Dict[str, Type[CommandHandler]] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def register(cls, handler_class: Type[CommandHandler]):
        """Register a command handler"""
        if not handler_class.command_name:
            raise ValueError(f"Handler {handler_class.__name__} must define command_name")
        
        cls._handlers[handler_class.command_name] = handler_class
        logger.info(f"Registered command handler: {handler_class.command_name}")
    
    @classmethod
    def get_handler(cls, command_name: str) -> Optional[Type[CommandHandler]]:
        """Get handler class for a command"""
        return cls._handlers.get(command_name)
    
    @classmethod
    def list_commands(cls) -> list:
        """List all registered commands"""
        return list(cls._handlers.keys())


def command_handler(command_name: str):
    """Decorator to register command handlers"""
    def decorator(cls: Type[CommandHandler]):
        cls.command_name = command_name
        CommandRegistry.register(cls)
        return cls
    return decorator


# Example command handlers using the new pattern

@command_handler("SPAWN")
class SpawnHandler(CommandHandler):
    """Handler for SPAWN command"""
    
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, 
                    full_command: Dict[str, Any]) -> BaseResponse:
        mode = parameters.get("mode")
        
        if mode == "sync":
            return await self._spawn_sync(parameters)
        elif mode == "async":
            return await self._spawn_async(parameters)
        else:
            return ResponseFactory.error("SPAWN", "INVALID_MODE", f"Invalid mode: {mode}")
    
    async def _spawn_sync(self, parameters: Dict[str, Any]) -> BaseResponse:
        """Handle synchronous Claude spawning"""
        if not self.process_manager:
            return ResponseFactory.error("SPAWN", "NO_PROCESS_MANAGER", "Process manager not available")
        
        result = await self.process_manager.spawn_claude(
            prompt=parameters.get("prompt"),
            session_id=parameters.get("session_id"),
            model=parameters.get("model", "sonnet"),
            agent_id=parameters.get("agent_id"),
            enable_tools=parameters.get("enable_tools", True)
        )
        
        if 'error' in result:
            return ResponseFactory.error("SPAWN", "SPAWN_FAILED", result['error'])
        
        return ResponseFactory.success("SPAWN", result)
    
    async def _spawn_async(self, parameters: Dict[str, Any]) -> BaseResponse:
        """Handle asynchronous Claude spawning"""
        if not self.process_manager:
            return ResponseFactory.error("SPAWN", "NO_PROCESS_MANAGER", "Process manager not available")
        
        process_id = await self.process_manager.spawn_claude_async(
            prompt=parameters.get("prompt"),
            session_id=parameters.get("session_id"),
            model=parameters.get("model", "sonnet"),
            agent_id=parameters.get("agent_id"),
            enable_tools=parameters.get("enable_tools", True)
        )
        
        if not process_id:
            return ResponseFactory.error("SPAWN", "SPAWN_FAILED", "Failed to start Claude process")
        
        return ResponseFactory.success("SPAWN", {
            'process_id': process_id,
            'status': 'started',
            'type': 'claude',
            'mode': 'async'
        })


@command_handler("CLEANUP")
class CleanupHandler(CommandHandler):
    """Handler for CLEANUP command"""
    
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, 
                    full_command: Dict[str, Any]) -> BaseResponse:
        if not self.utils_manager:
            return ResponseFactory.error("CLEANUP", "NO_UTILS_MANAGER", "Utils manager not available")
        
        cleanup_type = parameters.get("cleanup_type")
        result = self.utils_manager.cleanup(cleanup_type)
        
        return ResponseFactory.success("CLEANUP", {
            'status': 'cleaned',
            'cleanup_type': cleanup_type,
            'details': result
        })


@command_handler("HEALTH_CHECK")
class HealthCheckHandler(CommandHandler):
    """Handler for HEALTH_CHECK command"""
    
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, 
                    full_command: Dict[str, Any]) -> BaseResponse:
        # Gather health information from all managers
        health_info = {
            'status': 'healthy',
            'message': 'HEALTHY',
            'uptime_info': 'Daemon is running normally',
            'managers': {}
        }
        
        # Check each manager
        if self.state_manager:
            health_info['managers']['state'] = {
                'sessions': len(self.state_manager.sessions),
                'shared_state_keys': len(self.state_manager.shared_state)
            }
        
        if self.agent_manager:
            health_info['managers']['agents'] = {
                'registered': len(self.agent_manager.agents),
                'active': sum(1 for a in self.agent_manager.agents.values() 
                            if a.get('status') == 'active')
            }
        
        if self.process_manager:
            health_info['managers']['processes'] = {
                'running': len(self.process_manager.running_processes)
            }
        
        if self.message_bus:
            stats = self.message_bus.get_stats()
            health_info['managers']['message_bus'] = stats
        
        return ResponseFactory.success("HEALTH_CHECK", health_info)


@command_handler("SHUTDOWN")
class ShutdownHandler(CommandHandler):
    """Handler for SHUTDOWN command"""
    
    async def handle(self, parameters: Dict[str, Any], writer: asyncio.StreamWriter, 
                    full_command: Dict[str, Any]) -> BaseResponse:
        self.logger.info("Received SHUTDOWN command")
        
        response = ResponseFactory.success("SHUTDOWN", {
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
        
        return response  # Won't actually be sent since we closed the writer


# Simplified command handler that uses the registry

class SimplifiedCommandHandler:
    """Simplified command handler using registry pattern"""
    
    def __init__(self, core_daemon, **managers):
        self.core_daemon = core_daemon
        self.state_manager = managers.get('state_manager')
        self.process_manager = managers.get('process_manager')
        self.agent_manager = managers.get('agent_manager')
        self.utils_manager = managers.get('utils_manager')
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
            
            # Create handler instance and execute
            handler = handler_class(self)
            response = await handler.handle(parameters, writer, command_data)
            
            # Send response
            if response:
                await self.send_response(writer, response.model_dump())
            
            # Check if we should continue (shutdown returns False)
            return command_name != "SHUTDOWN"
            
        except Exception as e:
            self.logger.error(f"Error processing command: {e}", exc_info=True)
            await self.send_error_response(writer, "COMMAND_PROCESSING_FAILED", str(e))
            return True
    
    async def send_response(self, writer: asyncio.StreamWriter, response: dict) -> bool:
        """Send JSON response to client"""
        try:
            import json
            response_str = json.dumps(response) + '\n'
            writer.write(response_str.encode())
            await writer.drain()
            return True
        except Exception as e:
            self.logger.error(f"Failed to send response: {e}")
            return True
    
    async def send_error_response(self, writer: asyncio.StreamWriter, error_code: str, 
                                details: str = "") -> bool:
        """Send standardized error response to client"""
        from .models import ResponseFactory
        response = ResponseFactory.error("", error_code, details)
        return await self.send_response(writer, response.model_dump())