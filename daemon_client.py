#!/usr/bin/env python3
"""
Daemon Client - JSON Protocol v2.0 Client Library

Provides a clean Python API for sending JSON commands to the Claude daemon.
Handles connection management, command building, and response parsing.
"""

import asyncio
import json
import socket
import logging
from typing import Dict, Any, Optional, Union, List
from datetime import datetime
from pathlib import Path

# Import shared utilities from organized client package
from daemon.client import (
    CommandBuilder, 
    ResponseHandler, 
    ConnectionManager
)

logger = logging.getLogger('daemon_client')

class DaemonClientError(Exception):
    """Base exception for daemon client errors"""
    pass

class ConnectionError(DaemonClientError):
    """Raised when connection to daemon fails"""
    pass

class CommandError(DaemonClientError):
    """Raised when command execution fails"""
    def __init__(self, message: str, error_code: str = None, details: str = ""):
        super().__init__(message)
        self.error_code = error_code
        self.details = details

class DaemonClient:
    """Client for interacting with Claude daemon using JSON protocol v2.0"""
    
    def __init__(self, socket_path: str = "sockets/claude_daemon.sock"):
        self.socket_path = socket_path
        self.connection_timeout = 5.0
        self.command_timeout = 30.0
    
    async def send_command(self, command: str, parameters: Dict[str, Any] = None, 
                          timeout: float = None) -> Dict[str, Any]:
        """
        Send a JSON command to the daemon and return the response
        
        Args:
            command: Command name (e.g., "SPAWN", "HEALTH_CHECK")
            parameters: Command parameters dict
            timeout: Optional timeout override
            
        Returns:
            Response dict from daemon
            
        Raises:
            ConnectionError: If connection fails
            CommandError: If command fails
        """
        # Build JSON command using shared utilities
        cmd_obj = CommandBuilder.build_command(command, parameters)
        
        # Send command and get response
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(self.socket_path),
                timeout=self.connection_timeout
            )
            
            # Send JSON command
            command_str = json.dumps(cmd_obj) + '\n'
            writer.write(command_str.encode())
            await writer.drain()
            
            # Read response
            response_timeout = timeout or self.command_timeout
            response_data = await asyncio.wait_for(
                reader.readline(),
                timeout=response_timeout
            )
            
            # Close connection
            writer.close()
            await writer.wait_closed()
            
            # Parse response
            if not response_data:
                raise CommandError("Empty response from daemon")
                
            try:
                response = json.loads(response_data.decode().strip())
            except json.JSONDecodeError as e:
                raise CommandError(f"Invalid JSON response: {e}")
            
            # Check for errors
            if response.get("status") == "error":
                error_info = response.get("error", {})
                raise CommandError(
                    error_info.get("message", "Unknown error"),
                    error_info.get("code"),
                    error_info.get("details", "")
                )
            
            return response
            
        except asyncio.TimeoutError:
            raise ConnectionError(f"Connection timeout to {self.socket_path}")
        except ConnectionRefusedError:
            raise ConnectionError(f"Daemon not running at {self.socket_path}")
        except Exception as e:
            if isinstance(e, (CommandError, ConnectionError)):
                raise
            raise ConnectionError(f"Connection failed: {e}")
    
    # Convenience methods for common commands
    
    async def health_check(self) -> bool:
        """Check if daemon is healthy"""
        try:
            response = await self.send_command("HEALTH_CHECK")
            return response.get("result", {}).get("status") == "healthy"
        except Exception:
            return False
    
    async def spawn_claude(self, prompt: str, mode: str = "sync", 
                          session_id: str = None, model: str = "sonnet",
                          agent_id: str = None, enable_tools: bool = True) -> Dict[str, Any]:
        """
        Spawn a Claude process
        
        Args:
            prompt: Text prompt for Claude
            mode: "sync" or "async"
            session_id: Optional session ID for continuity
            model: Claude model to use
            agent_id: Optional agent identifier
            enable_tools: Whether to enable tool usage
            
        Returns:
            Response with Claude output (sync) or process_id (async)
        """
        # Build parameters for SPAWN command
        params = {
            "mode": mode,
            "type": "claude",
            "prompt": prompt,
            "model": model,
            "enable_tools": enable_tools
        }
        
        if session_id:
            params["session_id"] = session_id
        if agent_id:
            params["agent_id"] = agent_id
            
        return await self.send_command("SPAWN", params)
    
    async def get_agents(self) -> Dict[str, Any]:
        """Get all registered agents"""
        response = await self.send_command("GET_AGENTS")
        return response.get("result", {}).get("agents", {})
    
    async def register_agent(self, agent_id: str, role: str, 
                           capabilities: List[str] = None) -> Dict[str, Any]:
        """Register an agent with the system"""
        params = {
            "agent_id": agent_id,
            "role": role,
            "capabilities": capabilities or []
        }
        return await self.send_command("REGISTER_AGENT", params)
    
    async def spawn_agent(self, profile_name: str, task: str,
                         context: str = "", agent_id: str = None) -> Dict[str, Any]:
        """Spawn an agent using a predefined profile"""
        params = {
            "profile_name": profile_name,
            "task": task,
            "context": context
        }
        if agent_id:
            params["agent_id"] = agent_id
            
        return await self.send_command("SPAWN_AGENT", params)
    
    async def set_shared_state(self, key: str, value: Any) -> bool:
        """Set shared state value"""
        params = {"key": key, "value": value}
        response = await self.send_command("SET_SHARED", params)
        return response.get("result", {}).get("status") == "set"
    
    async def get_shared_state(self, key: str) -> Any:
        """Get shared state value"""
        params = {"key": key}
        response = await self.send_command("GET_SHARED", params)
        return response.get("result", {}).get("value")
    
    async def subscribe_events(self, agent_id: str, event_types: List[str]) -> bool:
        """Subscribe agent to message bus events"""
        params = {
            "agent_id": agent_id,
            "event_types": event_types
        }
        response = await self.send_command("SUBSCRIBE", params)
        return response.get("result", {}).get("status") == "subscribed"
    
    async def publish_event(self, from_agent: str, event_type: str, 
                          payload: Dict[str, Any]) -> Dict[str, Any]:
        """Publish event to message bus"""
        params = {
            "from_agent": from_agent,
            "event_type": event_type,
            "payload": payload
        }
        return await self.send_command("PUBLISH", params)
    
    async def connect_agent(self, agent_id: str) -> bool:
        """Connect agent to message bus"""
        params = {"action": "connect", "agent_id": agent_id}
        response = await self.send_command("AGENT_CONNECTION", params)
        return response.get("result", {}).get("status") == "connected"
    
    async def disconnect_agent(self, agent_id: str) -> bool:
        """Disconnect agent from message bus"""
        params = {"action": "disconnect", "agent_id": agent_id}
        response = await self.send_command("AGENT_CONNECTION", params)
        return response.get("result", {}).get("status") == "disconnected"
    
    async def get_processes(self) -> Dict[str, Any]:
        """Get running processes"""
        response = await self.send_command("GET_PROCESSES")
        return response.get("result", {}).get("processes", {})
    
    async def cleanup(self, cleanup_type: str) -> str:
        """Run cleanup operation"""
        params = {"cleanup_type": cleanup_type}
        response = await self.send_command("CLEANUP", params)
        return response.get("result", {}).get("details", "")
    
    async def reload_module(self, module_name: str) -> bool:
        """Hot-reload a Python module"""
        params = {"module_name": module_name}
        response = await self.send_command("RELOAD", params)
        return response.get("result", {}).get("status") == "reloaded"
    
    async def get_commands(self) -> Dict[str, Any]:
        """Get available daemon commands"""
        response = await self.send_command("GET_COMMANDS")
        return response.get("result", {})
    
    async def shutdown(self) -> bool:
        """Shutdown the daemon"""
        try:
            response = await self.send_command("SHUTDOWN")
            return response.get("result", {}).get("status") == "shutting_down"
        except CommandError:
            # Daemon may close connection before responding
            return True
    
    # Identity management methods
    
    async def create_identity(self, agent_id: str, display_name: str = None,
                            role: str = None, personality_traits: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create agent identity"""
        params = {"agent_id": agent_id}
        if display_name:
            params["display_name"] = display_name
        if role:
            params["role"] = role
        if personality_traits:
            params["personality_traits"] = personality_traits
            
        return await self.send_command("CREATE_IDENTITY", params)
    
    async def get_identity(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent identity"""
        try:
            params = {"agent_id": agent_id}
            response = await self.send_command("GET_IDENTITY", params)
            return response.get("result", {}).get("identity")
        except CommandError:
            return None
    
    async def list_identities(self) -> List[Dict[str, Any]]:
        """List all identities"""
        response = await self.send_command("LIST_IDENTITIES")
        return response.get("result", {}).get("identities", [])
    
    async def update_identity(self, agent_id: str, updates: Dict[str, Any]) -> bool:
        """Update agent identity"""
        params = {"agent_id": agent_id, "updates": updates}
        response = await self.send_command("UPDATE_IDENTITY", params)
        return response.get("result", {}).get("status") == "identity_updated"
    
    async def remove_identity(self, agent_id: str) -> bool:
        """Remove agent identity"""
        params = {"agent_id": agent_id}
        response = await self.send_command("REMOVE_IDENTITY", params)
        return response.get("result", {}).get("status") == "identity_removed"

class PersistentDaemonClient:
    """
    Persistent connection client for agents that need to maintain long-lived connections
    to the daemon (e.g., for receiving events via message bus)
    """
    
    def __init__(self, agent_id: str, socket_path: str = "sockets/claude_daemon.sock"):
        self.agent_id = agent_id
        self.socket_path = socket_path
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self.message_handlers = {}
    
    async def connect(self) -> bool:
        """Connect to daemon and establish persistent connection"""
        try:
            # Open connection
            self.reader, self.writer = await asyncio.open_unix_connection(self.socket_path)
            
            # Send AGENT_CONNECTION:connect command using shared utilities
            connect_cmd = CommandBuilder.build_agent_connection_command("connect", self.agent_id)
            
            command_str = json.dumps(connect_cmd) + '\n'
            self.writer.write(command_str.encode())
            await self.writer.drain()
            
            # Read response
            response_data = await self.reader.readline()
            response = json.loads(response_data.decode().strip())
            
            if response.get("status") == "success":
                self.connected = True
                logger.info(f"Agent {self.agent_id} connected to daemon")
                return True
            else:
                logger.error(f"Failed to connect agent {self.agent_id}: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Connection failed for agent {self.agent_id}: {e}")
            return False
    
    async def send_command(self, command: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send command on the persistent connection"""
        if not self.connected:
            raise ConnectionError("Not connected to daemon")
        
        cmd_obj = CommandBuilder.build_command(command, parameters)
        
        command_str = json.dumps(cmd_obj) + '\n'
        self.writer.write(command_str.encode())
        await self.writer.drain()
        
        # For persistent connections, responses may come asynchronously
        # This method sends the command but doesn't wait for a specific response
        return {"status": "sent"}
    
    async def listen_for_messages(self):
        """Listen for incoming messages on the persistent connection"""
        if not self.connected:
            raise ConnectionError("Not connected to daemon")
        
        try:
            while self.connected:
                data = await self.reader.readline()
                if not data:
                    break
                
                try:
                    message = json.loads(data.decode().strip())
                    await self._handle_message(message)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON message: {e}")
                    
        except Exception as e:
            logger.error(f"Error listening for messages: {e}")
        finally:
            self.connected = False
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming message"""
        message_type = message.get("type", "unknown")
        handler = self.message_handlers.get(message_type)
        
        if handler:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"Error in message handler for {message_type}: {e}")
        else:
            logger.debug(f"No handler for message type: {message_type}")
    
    def add_message_handler(self, message_type: str, handler):
        """Add a handler for a specific message type"""
        self.message_handlers[message_type] = handler
    
    async def disconnect(self):
        """Disconnect from daemon"""
        if self.connected and self.writer:
            disconnect_cmd = CommandBuilder.build_agent_connection_command("disconnect", self.agent_id)
            
            try:
                command_str = json.dumps(disconnect_cmd) + '\n'
                self.writer.write(command_str.encode())
                await self.writer.drain()
                
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            
            self.connected = False
            logger.info(f"Agent {self.agent_id} disconnected from daemon")

# Convenience functions for simple use cases

async def daemon_health_check(socket_path: str = "sockets/claude_daemon.sock") -> bool:
    """Quick health check"""
    client = DaemonClient(socket_path)
    return await client.health_check()

async def spawn_claude_sync(prompt: str, session_id: str = None, 
                           socket_path: str = "sockets/claude_daemon.sock") -> str:
    """Quick synchronous Claude spawn - returns just the result text"""
    client = DaemonClient(socket_path)
    response = await client.spawn_claude(prompt, mode="sync", session_id=session_id)
    return response.get("result", {}).get("result", "")

async def get_daemon_commands(socket_path: str = "sockets/claude_daemon.sock") -> Dict[str, Any]:
    """Get available daemon commands"""
    client = DaemonClient(socket_path)
    return await client.get_commands()