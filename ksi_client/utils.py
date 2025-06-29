#!/usr/bin/env python3
"""
Client Utilities - Shared JSON command building and response handling

Provides common utilities for building JSON Protocol v2.0 commands and handling responses.
Used by daemon_client.py, agent_process.py, and other client code to eliminate duplication.

Now supports both legacy command-based and new event-based protocols.
"""

import json
import asyncio
import logging
import uuid
from typing import Dict, Any, Optional, Union, List, Tuple
from datetime import datetime

from ksi_common import get_logger

logger = get_logger(__name__)

# CommandBuilder removed - use EventBuilder instead

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

# Command convenience functions removed - use event functions instead


class EventBuilder:
    """Builder for event-based protocol messages"""
    
    @classmethod
    def build_event(cls, event_name: str, data: Dict[str, Any] = None,
                   correlation_id: str = None, client_id: str = None) -> Dict[str, Any]:
        """
        Build an event message for the new plugin architecture
        
        Args:
            event_name: Event name (e.g., "system:health", "completion:request")
            data: Event data/parameters
            correlation_id: Optional correlation ID for request/response patterns
            client_id: Optional client identifier
            
        Returns:
            Complete event dict ready for JSON serialization
        """
        event = {
            "event": event_name,
            "data": data or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if correlation_id:
            event["correlation_id"] = correlation_id
        if client_id:
            event["client_id"] = client_id
            
        return event
    
    @classmethod
    def build_health_event(cls) -> Dict[str, Any]:
        """Build a system:health event"""
        return cls.build_event("system:health")
    
    @classmethod
    def build_completion_event(cls, prompt: str, model: str = "sonnet",
                             session_id: str = None, client_id: str = None,
                             correlation_id: str = None, priority: str = "normal") -> Dict[str, Any]:
        """
        Build a completion:async event
        
        Args:
            prompt: Text prompt for Claude
            model: Claude model to use
            session_id: Optional session ID for continuity
            client_id: Client identifier for response routing
            correlation_id: Correlation ID for response matching
            priority: Request priority (critical, high, normal, low, background)
            
        Returns:
            Completion request event dict
        """
        import uuid
        
        data = {
            "prompt": prompt,
            "model": model,
            "priority": priority,
            "request_id": f"{client_id or 'client'}_{uuid.uuid4().hex[:8]}"
        }
        
        if session_id:
            data["session_id"] = session_id
        if client_id:
            data["client_id"] = client_id
            
        return cls.build_event("completion:async", data, correlation_id, client_id)
    
    @classmethod
    def build_agent_event(cls, action: str, agent_id: str = None, 
                         role: str = None, capabilities: List[str] = None,
                         correlation_id: str = None) -> Dict[str, Any]:
        """
        Build agent-related events
        
        Args:
            action: Action type ("register", "list", "spawn", etc.)
            agent_id: Agent identifier (for actions on specific agents)
            role: Agent role (for registration)
            capabilities: Agent capabilities (for registration)
            correlation_id: Correlation ID for response
            
        Returns:
            Agent event dict
        """
        event_name = f"agent:{action}"
        data = {}
        
        if agent_id:
            data["agent_id"] = agent_id
        if role:
            data["role"] = role
        if capabilities:
            data["capabilities"] = capabilities
            
        return cls.build_event(event_name, data, correlation_id)
    
    @classmethod
    def build_state_event(cls, action: str, namespace: str = None,
                         key: str = None, value: Any = None,
                         correlation_id: str = None) -> Dict[str, Any]:
        """
        Build state management events
        
        Args:
            action: Action type ("get", "set", "delete")
            namespace: State namespace
            key: State key
            value: State value (for set operations)
            correlation_id: Correlation ID
            
        Returns:
            State event dict
        """
        event_name = f"state:{action}"
        data = {}
        
        if namespace:
            data["namespace"] = namespace
        if key:
            data["key"] = key
        if value is not None:
            data["value"] = value
            
        return cls.build_event(event_name, data, correlation_id)
    
    @classmethod
    def build_shutdown_event(cls) -> Dict[str, Any]:
        """Build a system:shutdown event"""
        return cls.build_event("system:shutdown")


# Event-based convenience functions
def create_event(event_name: str, data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
    """Convenience function for creating events"""
    return EventBuilder.build_event(event_name, data, **kwargs)

def create_health_event() -> Dict[str, Any]:
    """Convenience function for health check event"""
    return EventBuilder.build_health_event()

def create_completion_event(prompt: str, **kwargs) -> Dict[str, Any]:
    """Convenience function for completion request event"""
    return EventBuilder.build_completion_event(prompt, **kwargs)

def create_agent_event(action: str, **kwargs) -> Dict[str, Any]:
    """Convenience function for agent events"""
    return EventBuilder.build_agent_event(action, **kwargs)

def create_state_event(action: str, **kwargs) -> Dict[str, Any]:
    """Convenience function for state events"""
    return EventBuilder.build_state_event(action, **kwargs)

async def send_daemon_event(socket_path: str, event_name: str, data: Dict[str, Any] = None,
                          correlation_id: str = None, timeout: float = 5.0) -> Dict[str, Any]:
    """
    High-level convenience function for sending events to daemon
    
    Args:
        socket_path: Path to daemon socket
        event_name: Event name
        data: Event data
        correlation_id: Optional correlation ID
        timeout: Connection timeout
        
    Returns:
        Parsed response dict
    """
    event_dict = EventBuilder.build_event(event_name, data, correlation_id)
    return await ConnectionManager.send_command_once(socket_path, event_dict, timeout)