#!/usr/bin/env python3
"""
Asynchronous Client - Full-featured async interface for JSON Protocol v2.0

Provides a comprehensive async API for complex agents and applications that need
persistent connections, event handling, and high-performance communication.
"""

import asyncio
import json
import logging
from ..config import config
from typing import Dict, Any, Optional, List, Callable
from .utils import CommandBuilder, ConnectionManager, ResponseHandler

logger = logging.getLogger('daemon.async_client')

class AsyncClient:
    """Asynchronous client for daemon communication"""
    
    def __init__(self, socket_path: str = None, timeout: float = None):
        self.socket_path = socket_path or str(config.socket_path)
        self.timeout = timeout or config.socket_timeout
    
    async def send_command(self, command: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Send a command asynchronously
        
        Args:
            command: Command name
            parameters: Command parameters
            
        Returns:
            Response dict
            
        Raises:
            ConnectionError: If connection fails
        """
        cmd_obj = CommandBuilder.build_command(command, parameters)
        return await ConnectionManager.send_command_once(self.socket_path, cmd_obj, self.timeout)
    
    async def health_check(self) -> bool:
        """Check if daemon is healthy"""
        try:
            response = await self.send_command("HEALTH_CHECK")
            return ResponseHandler.check_success(response) and \
                   ResponseHandler.get_result_data(response).get("status") == "healthy"
        except Exception:
            return False
    
    async def spawn_claude(self, prompt: str, mode: str = "sync", session_id: str = None,
                          model: str = "sonnet", agent_id: str = None, enable_tools: bool = True) -> Dict[str, Any]:
        """
        Spawn Claude process asynchronously
        
        Args:
            prompt: Text prompt for Claude
            mode: "sync" or "async"
            session_id: Optional session ID for continuity
            model: Claude model to use
            agent_id: Optional agent identifier
            enable_tools: Whether to enable tool usage
            
        Returns:
            Full response dict with result data
            
        Raises:
            ConnectionError: If connection fails
            ValueError: If command fails
        """
        cmd_obj = CommandBuilder.build_spawn_command(
            prompt=prompt, mode=mode, session_id=session_id,
            model=model, agent_id=agent_id, enable_tools=enable_tools
        )
        
        response = await ConnectionManager.send_command_once(self.socket_path, cmd_obj, self.timeout)
        
        if not ResponseHandler.check_success(response):
            error_msg = ResponseHandler.get_error_message(response)
            raise ValueError(f"SPAWN command failed: {error_msg}")
        
        return response
    
    async def get_agents(self) -> Dict[str, Any]:
        """Get all registered agents"""
        response = await self.send_command("GET_AGENTS")
        if ResponseHandler.check_success(response):
            return ResponseHandler.get_result_data(response).get("agents", {})
        return {}
    
    async def register_agent(self, agent_id: str, role: str, capabilities: List[str] = None) -> bool:
        """Register an agent with the system"""
        params = {
            "agent_id": agent_id,
            "role": role,
            "capabilities": capabilities or []
        }
        response = await self.send_command("REGISTER_AGENT", params)
        return ResponseHandler.check_success(response)
    
    async def set_shared_state(self, key: str, value: Any) -> bool:
        """Set shared state value"""
        response = await self.send_command("SET_SHARED", {"key": key, "value": value})
        return ResponseHandler.check_success(response) and \
               ResponseHandler.get_result_data(response).get("status") == "set"
    
    async def get_shared_state(self, key: str) -> Any:
        """Get shared state value"""
        response = await self.send_command("GET_SHARED", {"key": key})
        if ResponseHandler.check_success(response):
            return ResponseHandler.get_result_data(response).get("value")
        return None
    
    async def publish_event(self, from_agent: str, event_type: str, payload: Dict[str, Any]) -> bool:
        """Publish event to message bus"""
        cmd_obj = CommandBuilder.build_publish_command(from_agent, event_type, payload)
        response = await ConnectionManager.send_command_once(self.socket_path, cmd_obj, self.timeout)
        return ResponseHandler.check_success(response)
    
    async def cleanup(self, cleanup_type: str) -> str:
        """Run cleanup operation"""
        response = await self.send_command("CLEANUP", {"cleanup_type": cleanup_type})
        if ResponseHandler.check_success(response):
            return ResponseHandler.get_result_data(response).get("details", "")
        return ResponseHandler.get_error_message(response)
    
    async def shutdown_daemon(self) -> bool:
        """Shutdown the daemon"""
        try:
            response = await self.send_command("SHUTDOWN")
            return ResponseHandler.check_success(response)
        except ConnectionError:
            # Daemon may close connection before responding
            return True

class PersistentAsyncClient:
    """
    Persistent connection async client for long-lived agents
    
    Maintains an open connection to the daemon for receiving events
    and sending commands without connection overhead.
    """
    
    def __init__(self, agent_id: str, socket_path: str = None):
        self.agent_id = agent_id
        self.socket_path = socket_path or str(config.socket_path)
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self.event_handlers: Dict[str, Callable] = {}
        self._listen_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> bool:
        """Connect to daemon and establish persistent connection"""
        try:
            # Open connection
            self.reader, self.writer = await asyncio.open_unix_connection(self.socket_path)
            
            # Send connection command
            connect_cmd = CommandBuilder.build_agent_connection_command("connect", self.agent_id)
            
            command_str = json.dumps(connect_cmd) + '\n'
            self.writer.write(command_str.encode())
            await self.writer.drain()
            
            # Read response
            response_data = await self.reader.readline()
            response = ResponseHandler.parse_response(response_data)
            
            if ResponseHandler.check_success(response):
                self.connected = True
                logger.info(f"Agent {self.agent_id} connected to daemon")
                return True
            else:
                logger.error(f"Failed to connect agent {self.agent_id}: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Connection failed for agent {self.agent_id}: {e}")
            return False
    
    async def send_command(self, command: str, parameters: Dict[str, Any] = None) -> bool:
        """Send command on the persistent connection"""
        if not self.connected:
            raise ConnectionError("Not connected to daemon")
        
        cmd_obj = CommandBuilder.build_command(command, parameters)
        command_str = json.dumps(cmd_obj) + '\n'
        
        self.writer.write(command_str.encode())
        await self.writer.drain()
        
        return True
    
    async def subscribe_events(self, event_types: List[str]) -> bool:
        """Subscribe to message bus events"""
        cmd_obj = CommandBuilder.build_subscribe_command(self.agent_id, event_types)
        command_str = json.dumps(cmd_obj) + '\n'
        
        self.writer.write(command_str.encode())
        await self.writer.drain()
        
        return True
    
    def add_event_handler(self, event_type: str, handler: Callable[[Dict[str, Any]], None]):
        """Add handler for specific event type"""
        self.event_handlers[event_type] = handler
    
    async def start_listening(self):
        """Start listening for incoming messages"""
        if not self.connected:
            raise ConnectionError("Not connected to daemon")
        
        self._listen_task = asyncio.create_task(self._listen_loop())
        return self._listen_task
    
    async def _listen_loop(self):
        """Message listening loop"""
        try:
            while self.connected:
                data = await self.reader.readline()
                if not data:
                    break
                
                try:
                    message = ResponseHandler.parse_response(data)
                    await self._handle_message(message)
                except Exception as e:
                    logger.warning(f"Error handling message: {e}")
                    
        except Exception as e:
            logger.error(f"Error in message listener: {e}")
        finally:
            self.connected = False
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming message"""
        message_type = message.get("type", "unknown")
        handler = self.event_handlers.get(message_type)
        
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error(f"Error in event handler for {message_type}: {e}")
        else:
            logger.debug(f"No handler for message type: {message_type}")
    
    async def disconnect(self):
        """Disconnect from daemon"""
        if self.connected and self.writer:
            try:
                disconnect_cmd = CommandBuilder.build_agent_connection_command("disconnect", self.agent_id)
                command_str = json.dumps(disconnect_cmd) + '\n'
                
                self.writer.write(command_str.encode())
                await self.writer.drain()
                
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            
            self.connected = False
            
            # Cancel listening task
            if self._listen_task and not self._listen_task.done():
                self._listen_task.cancel()
                try:
                    await self._listen_task
                except asyncio.CancelledError:
                    pass
            
            logger.info(f"Agent {self.agent_id} disconnected from daemon")