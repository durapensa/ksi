#!/usr/bin/env python3
"""
Client Utilities - Shared JSON command building and response handling

Provides common utilities for building JSON Protocol v2.0 commands and handling responses.
Used by daemon_client.py, agent_process.py, and other client code to eliminate duplication.
"""

import json
import asyncio
import logging
from typing import Dict, Any, Optional, Union, List, Tuple
from datetime import datetime

logger = logging.getLogger('daemon.client_utils')

class CommandBuilder:
    """Builder for JSON Protocol v2.0 commands"""
    
    VERSION = "2.0"
    
    @classmethod
    def build_command(cls, command: str, parameters: Dict[str, Any] = None, 
                     metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Build a standard JSON command object
        
        Args:
            command: Command name (e.g., "SPAWN", "PUBLISH")
            parameters: Command parameters
            metadata: Optional metadata
            
        Returns:
            Complete command dict ready for JSON serialization
        """
        cmd_obj = {
            "command": command,
            "version": cls.VERSION,
            "parameters": parameters or {}
        }
        
        if metadata:
            cmd_obj["metadata"] = metadata
            
        return cmd_obj
    
    @classmethod
    def build_spawn_command(cls, prompt: str, mode: str = "sync", 
                           session_id: str = None, model: str = "sonnet",
                           agent_id: str = None, enable_tools: bool = True,
                           spawn_type: str = "claude") -> Dict[str, Any]:
        """
        Build a SPAWN command with all parameters
        
        Args:
            prompt: Text prompt for Claude
            mode: "sync" or "async"
            session_id: Optional session ID for continuity
            model: Claude model to use
            agent_id: Optional agent identifier
            enable_tools: Whether to enable tool usage
            spawn_type: Type of process to spawn ("claude")
            
        Returns:
            SPAWN command dict
        """
        params = {
            "mode": mode,
            "type": spawn_type,
            "prompt": prompt,
            "model": model,
            "enable_tools": enable_tools
        }
        
        if session_id:
            params["session_id"] = session_id
        if agent_id:
            params["agent_id"] = agent_id
            
        return cls.build_command("SPAWN", params)
    
    @classmethod
    def build_publish_command(cls, from_agent: str, event_type: str, 
                             payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a PUBLISH command for message bus events
        
        Args:
            from_agent: Agent ID publishing the event
            event_type: Type of event (e.g., "DIRECT_MESSAGE", "CONVERSATION_INVITE")
            payload: Event payload data
            
        Returns:
            PUBLISH command dict
        """
        params = {
            "from_agent": from_agent,
            "event_type": event_type,
            "payload": payload
        }
        
        return cls.build_command("PUBLISH", params)
    
    @classmethod
    def build_subscribe_command(cls, agent_id: str, event_types: List[str]) -> Dict[str, Any]:
        """
        Build a SUBSCRIBE command for message bus events
        
        Args:
            agent_id: Agent ID to subscribe
            event_types: List of event types to subscribe to
            
        Returns:
            SUBSCRIBE command dict
        """
        params = {
            "agent_id": agent_id,
            "event_types": event_types
        }
        
        return cls.build_command("SUBSCRIBE", params)
    
    @classmethod
    def build_agent_connection_command(cls, action: str, agent_id: str) -> Dict[str, Any]:
        """
        Build an AGENT_CONNECTION command
        
        Args:
            action: "connect" or "disconnect"
            agent_id: Agent identifier
            
        Returns:
            AGENT_CONNECTION command dict
        """
        params = {
            "action": action,
            "agent_id": agent_id
        }
        
        return cls.build_command("AGENT_CONNECTION", params)
    
    @classmethod
    def build_identity_command(cls, command: str, agent_id: str, **kwargs) -> Dict[str, Any]:
        """
        Build identity management commands (CREATE_IDENTITY, GET_IDENTITY, etc.)
        
        Args:
            command: Identity command name
            agent_id: Agent identifier
            **kwargs: Additional parameters (display_name, role, personality_traits, etc.)
            
        Returns:
            Identity command dict
        """
        params = {"agent_id": agent_id}
        params.update(kwargs)
        
        return cls.build_command(command, params)

class ResponseHandler:
    """Handler for JSON Protocol v2.0 responses"""
    
    @staticmethod
    def parse_response(response_data: Union[str, bytes]) -> Dict[str, Any]:
        """
        Parse a JSON response from the daemon
        
        Args:
            response_data: Raw response data (string or bytes)
            
        Returns:
            Parsed response dict
            
        Raises:
            json.JSONDecodeError: If response is not valid JSON
        """
        if isinstance(response_data, bytes):
            response_data = response_data.decode().strip()
        elif isinstance(response_data, str):
            response_data = response_data.strip()
        
        return json.loads(response_data)
    
    @staticmethod
    def check_success(response: Dict[str, Any]) -> bool:
        """
        Check if response indicates success
        
        Args:
            response: Parsed response dict
            
        Returns:
            True if response indicates success
        """
        return response.get("status") == "success"
    
    @staticmethod
    def get_error_message(response: Dict[str, Any]) -> str:
        """
        Extract error message from error response
        
        Args:
            response: Parsed response dict
            
        Returns:
            Error message string
        """
        if response.get("status") == "error":
            error_info = response.get("error", {})
            return error_info.get("message", "Unknown error")
        return ""
    
    @staticmethod
    def get_result_data(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract result data from success response
        
        Args:
            response: Parsed response dict
            
        Returns:
            Result data dict, or None if no result
        """
        if response.get("status") == "success":
            return response.get("result")
        return None

class ConnectionManager:
    """Manager for JSON Protocol v2.0 connections"""
    
    @staticmethod
    async def send_command_once(socket_path: str, command_dict: Dict[str, Any], 
                               timeout: float = 5.0) -> Dict[str, Any]:
        """
        Send a single command and get response using one-shot connection
        
        Args:
            socket_path: Path to daemon socket
            command_dict: Command dict to send
            timeout: Connection timeout in seconds
            
        Returns:
            Parsed response dict
            
        Raises:
            ConnectionError: If connection fails
            asyncio.TimeoutError: If timeout exceeded
            json.JSONDecodeError: If response is invalid JSON
        """
        try:
            # Connect with timeout
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(socket_path),
                timeout=timeout
            )
            
            # Send command
            command_str = json.dumps(command_dict) + '\n'
            writer.write(command_str.encode())
            await writer.drain()
            
            # Read response
            response_data = await asyncio.wait_for(
                reader.readline(),
                timeout=timeout
            )
            
            # Close connection
            writer.close()
            await writer.wait_closed()
            
            # Parse and return response
            return ResponseHandler.parse_response(response_data)
            
        except asyncio.TimeoutError:
            raise ConnectionError(f"Connection timeout to {socket_path}")
        except ConnectionRefusedError:
            raise ConnectionError(f"Daemon not running at {socket_path}")
        except Exception as e:
            raise ConnectionError(f"Connection failed: {e}")

# Convenience functions for common patterns
def create_spawn_command(prompt: str, **kwargs) -> Dict[str, Any]:
    """Convenience function for creating SPAWN commands"""
    return CommandBuilder.build_spawn_command(prompt, **kwargs)

def create_publish_command(from_agent: str, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function for creating PUBLISH commands"""
    return CommandBuilder.build_publish_command(from_agent, event_type, payload)

def create_subscribe_command(agent_id: str, event_types: List[str]) -> Dict[str, Any]:
    """Convenience function for creating SUBSCRIBE commands"""
    return CommandBuilder.build_subscribe_command(agent_id, event_types)

def create_agent_connection_command(action: str, agent_id: str) -> Dict[str, Any]:
    """Convenience function for creating AGENT_CONNECTION commands"""
    return CommandBuilder.build_agent_connection_command(action, agent_id)

async def send_daemon_command(socket_path: str, command: str, parameters: Dict[str, Any] = None, 
                             timeout: float = 5.0) -> Dict[str, Any]:
    """
    High-level convenience function for sending commands to daemon
    
    Args:
        socket_path: Path to daemon socket
        command: Command name
        parameters: Command parameters
        timeout: Connection timeout
        
    Returns:
        Parsed response dict
    """
    command_dict = CommandBuilder.build_command(command, parameters)
    return await ConnectionManager.send_command_once(socket_path, command_dict, timeout)