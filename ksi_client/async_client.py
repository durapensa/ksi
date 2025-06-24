#!/usr/bin/env python3
"""
Multi-Socket Async Client - Full multi-socket architecture support

Provides comprehensive async API for the new multi-socket daemon architecture:
- admin.sock: System administration 
- agents.sock: Agent lifecycle
- messaging.sock: Events and messages
- state.sock: Agent state
- completion.sock: LLM completions

Handles async completion flow properly with event subscriptions.
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, Any, Optional, List, Callable, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from ksi_daemon.config import config
from .utils import CommandBuilder, ConnectionManager, ResponseHandler

logger = logging.getLogger('ksi_client.async_client')


@dataclass
class SocketConnection:
    """Represents a connection to a specific socket"""
    socket_name: str
    socket_path: Path
    reader: Optional[asyncio.StreamReader] = None
    writer: Optional[asyncio.StreamWriter] = None
    connected: bool = False


@dataclass
class PendingCompletion:
    """Tracks a pending completion request"""
    request_id: str
    future: asyncio.Future
    timeout_task: Optional[asyncio.Task] = None


class MultiSocketAsyncClient:
    """
    Full-featured async client supporting all daemon sockets.
    
    Features:
    - Proper async completion flow with event subscriptions
    - Support for all socket domains
    - Clean separation of concerns
    - Event-driven architecture (no polling)
    """
    
    def __init__(self, client_id: str = None, timeout: float = None):
        """
        Initialize multi-socket client.
        
        Args:
            client_id: Unique client identifier (auto-generated if None)
            timeout: Default timeout for operations
        """
        self.client_id = client_id or f"client_{uuid.uuid4().hex[:8]}"
        self.timeout = timeout or config.socket_timeout
        
        # Socket connections - multi-socket architecture
        self.sockets: Dict[str, SocketConnection] = {
            'admin': SocketConnection('admin', config.admin_socket),
            'agents': SocketConnection('agents', config.agents_socket),
            'messaging': SocketConnection('messaging', config.messaging_socket),
            'state': SocketConnection('state', config.state_socket),
            'completion': SocketConnection('completion', config.completion_socket),
        }
        
        # Persistent messaging connection for events
        self.messaging_connected = False
        self.messaging_reader: Optional[asyncio.StreamReader] = None
        self.messaging_writer: Optional[asyncio.StreamWriter] = None
        
        # Event handling
        self.event_handlers: Dict[str, List[Callable]] = {}
        self._listen_task: Optional[asyncio.Task] = None
        
        # Pending completions
        self.pending_completions: Dict[str, PendingCompletion] = {}
        
        # Connection state
        self._initialized = False
        
    async def initialize(self) -> bool:
        """
        Initialize the client by setting up messaging connection and subscriptions.
        
        Returns:
            True if initialization successful
        """
        if self._initialized:
            return True
            
        try:
            # Connect to messaging socket for events
            await self._connect_messaging()
            
            # Subscribe to completion results
            await self._subscribe_completion_results()
            
            # Start event listener
            self._listen_task = asyncio.create_task(self._event_listener())
            
            self._initialized = True
            logger.info(f"Multi-socket client {self.client_id} initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize client: {e}")
            return False
    
    async def _connect_messaging(self) -> None:
        """Establish persistent messaging connection"""
        self.messaging_reader, self.messaging_writer = await asyncio.open_unix_connection(
            str(self.sockets['messaging'].socket_path)
        )
        
        # Send connection command
        connect_cmd = CommandBuilder.build_agent_connection_command("connect", self.client_id)
        await self._send_messaging_command(connect_cmd)
        
        self.messaging_connected = True
        logger.info(f"Client {self.client_id} connected to messaging socket")
    
    async def _subscribe_completion_results(self) -> None:
        """Subscribe to COMPLETION_RESULT events targeted to this client"""
        # Try dynamic subscription first (if daemon supports it)
        subscribe_cmd = CommandBuilder.build_subscribe_command(
            self.client_id, 
            [f"COMPLETION_RESULT:{self.client_id}"]  # Targeted subscription
        )
        
        try:
            await self._send_messaging_command(subscribe_cmd)
            logger.info(f"Client {self.client_id} subscribed to targeted COMPLETION_RESULT events")
        except:
            # Fallback to general subscription if dynamic patterns not supported
            subscribe_cmd = CommandBuilder.build_subscribe_command(
                self.client_id, 
                ["COMPLETION_RESULT"]
            )
            await self._send_messaging_command(subscribe_cmd)
            logger.info(f"Client {self.client_id} subscribed to all COMPLETION_RESULT events (will filter)")
    
    async def _send_messaging_command(self, command: Dict[str, Any]) -> None:
        """Send command on messaging connection"""
        if not self.messaging_writer:
            raise ConnectionError("Not connected to messaging socket")
            
        command_str = json.dumps(command) + '\n'
        self.messaging_writer.write(command_str.encode())
        await self.messaging_writer.drain()
    
    # ========================================================================
    # ONE-SHOT COMMANDS (for non-messaging sockets)
    # ========================================================================
    
    async def send_command(self, socket_name: str, command: str, 
                          parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Send a command to a specific socket using one-shot connection.
        
        Args:
            socket_name: Which socket to use (admin, agents, state, completion)
            command: Command name
            parameters: Command parameters
            
        Returns:
            Response dict
            
        Raises:
            ValueError: If socket name invalid
            ConnectionError: If connection fails
        """
        if socket_name not in self.sockets:
            raise ValueError(f"Invalid socket name: {socket_name}")
            
        if socket_name == 'messaging':
            raise ValueError("Use persistent messaging methods for messaging socket")
            
        socket = self.sockets[socket_name]
        cmd_obj = CommandBuilder.build_command(command, parameters)
        
        return await ConnectionManager.send_command_once(
            str(socket.socket_path), 
            cmd_obj, 
            self.timeout
        )
    
    # ========================================================================
    # ADMIN SOCKET COMMANDS
    # ========================================================================
    
    async def health_check(self) -> Dict[str, Any]:
        """Check daemon health"""
        response = await self.send_command("admin", "HEALTH_CHECK")
        return ResponseHandler.get_result_data(response) if ResponseHandler.check_success(response) else {}
    
    async def get_processes(self) -> List[Dict[str, Any]]:
        """Get all daemon processes"""
        response = await self.send_command("admin", "GET_PROCESSES")
        if ResponseHandler.check_success(response):
            return ResponseHandler.get_result_data(response).get("processes", [])
        return []
    
    async def shutdown_daemon(self) -> bool:
        """Shutdown the daemon"""
        try:
            response = await self.send_command("admin", "SHUTDOWN")
            return ResponseHandler.check_success(response)
        except ConnectionError:
            # Daemon may close connection before responding
            return True
    
    async def get_message_bus_stats(self) -> Dict[str, Any]:
        """Get message bus statistics"""
        response = await self.send_command("admin", "MESSAGE_BUS_STATS")
        return ResponseHandler.get_result_data(response) if ResponseHandler.check_success(response) else {}
    
    # ========================================================================
    # AGENTS SOCKET COMMANDS
    # ========================================================================
    
    async def register_agent(self, agent_id: str, role: str, 
                           capabilities: List[str] = None) -> bool:
        """Register an agent"""
        params = {
            "agent_id": agent_id,
            "role": role,
            "capabilities": capabilities or []
        }
        response = await self.send_command("agents", "REGISTER_AGENT", params)
        return ResponseHandler.check_success(response)
    
    async def get_agents(self) -> Dict[str, Any]:
        """Get all registered agents"""
        response = await self.send_command("agents", "GET_AGENTS")
        if ResponseHandler.check_success(response):
            return ResponseHandler.get_result_data(response).get("agents", {})
        return {}
    
    async def spawn_agent(self, agent_type: str, config: Dict[str, Any]) -> str:
        """Spawn a new agent process"""
        params = {
            "agent_type": agent_type,
            "config": config
        }
        response = await self.send_command("agents", "SPAWN_AGENT", params)
        if ResponseHandler.check_success(response):
            return ResponseHandler.get_result_data(response).get("process_id", "")
        raise ValueError(f"Failed to spawn agent: {ResponseHandler.get_error_message(response)}")
    
    # ========================================================================
    # STATE SOCKET COMMANDS
    # ========================================================================
    
    async def set_agent_kv(self, agent_id: str, key: str, value: Any) -> bool:
        """Set agent key-value state"""
        params = {
            "agent_id": agent_id,
            "key": key,
            "value": value
        }
        response = await self.send_command("state", "SET_AGENT_KV", params)
        return ResponseHandler.check_success(response)
    
    async def get_agent_kv(self, agent_id: str, key: str) -> Any:
        """Get agent key-value state"""
        params = {
            "agent_id": agent_id,
            "key": key
        }
        response = await self.send_command("state", "GET_AGENT_KV", params)
        if ResponseHandler.check_success(response):
            return ResponseHandler.get_result_data(response).get("value")
        return None
    
    # ========================================================================
    # COMPLETION SOCKET COMMANDS (ASYNC)
    # ========================================================================
    
    async def create_completion(self, prompt: str, model: str = "sonnet",
                               session_id: Optional[str] = None,
                               agent_id: Optional[str] = None,
                               timeout: int = 300) -> str:
        """
        Create an async completion request.
        
        This is the replacement for the old SPAWN command. It sends a completion
        request and returns the full response text when ready.
        
        Args:
            prompt: The prompt text
            model: Claude model to use
            session_id: Session ID for conversation continuity
            agent_id: Optional agent to route through
            timeout: Timeout in seconds
            
        Returns:
            The completion response text
            
        Raises:
            TimeoutError: If completion times out
            ValueError: If completion fails
        """
        if not self._initialized:
            await self.initialize()
        
        # Build completion parameters
        params = {
            "prompt": prompt,
            "model": model,
            "client_id": self.client_id,
            "timeout": timeout
        }
        
        if session_id:
            params["session_id"] = session_id
        if agent_id:
            params["agent_id"] = agent_id
        
        # Send completion request
        response = await self.send_command("completion", "COMPLETION", params)
        
        if not ResponseHandler.check_success(response):
            raise ValueError(f"Completion request failed: {ResponseHandler.get_error_message(response)}")
        
        # Get request ID from acknowledgment
        result = ResponseHandler.get_result_data(response)
        request_id = result.get("request_id")
        
        if not request_id:
            raise ValueError("No request_id in completion acknowledgment")
        
        # Create future for this completion
        future = asyncio.Future()
        pending = PendingCompletion(request_id, future)
        self.pending_completions[request_id] = pending
        
        # Set timeout
        pending.timeout_task = asyncio.create_task(self._completion_timeout(request_id, timeout))
        
        try:
            # Wait for completion result
            result = await future
            
            # Extract response text
            if "error" in result:
                raise ValueError(f"Completion failed: {result['error']}")
                
            return result.get("response", "")
            
        finally:
            # Clean up
            if request_id in self.pending_completions:
                pending = self.pending_completions.pop(request_id)
                if pending.timeout_task and not pending.timeout_task.done():
                    pending.timeout_task.cancel()
    
    async def _completion_timeout(self, request_id: str, timeout: int):
        """Handle completion timeout"""
        await asyncio.sleep(timeout)
        
        if request_id in self.pending_completions:
            pending = self.pending_completions.pop(request_id)
            if not pending.future.done():
                pending.future.set_exception(
                    TimeoutError(f"Completion {request_id} timed out after {timeout}s")
                )
    
    # ========================================================================
    # MESSAGING SOCKET COMMANDS (PERSISTENT)
    # ========================================================================
    
    async def publish_event(self, event_type: str, payload: Dict[str, Any]) -> bool:
        """Publish an event to the message bus"""
        if not self._initialized:
            await self.initialize()
            
        publish_cmd = CommandBuilder.build_publish_command(
            self.client_id, event_type, payload
        )
        
        await self._send_messaging_command(publish_cmd)
        return True
    
    async def send_message(self, to_agent: str, content: str, 
                          metadata: Dict[str, Any] = None) -> bool:
        """Send a direct message to another agent"""
        if not self._initialized:
            await self.initialize()
            
        params = {
            "from_agent": self.client_id,
            "to_agent": to_agent,
            "content": content,
            "metadata": metadata or {}
        }
        
        send_cmd = CommandBuilder.build_command("SEND_MESSAGE", params)
        await self._send_messaging_command(send_cmd)
        return True
    
    def add_event_handler(self, event_type: str, handler: Callable[[Dict[str, Any]], None]):
        """Add handler for specific event type"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    def remove_event_handler(self, event_type: str, handler: Callable[[Dict[str, Any]], None]):
        """Remove event handler"""
        if event_type in self.event_handlers:
            self.event_handlers[event_type].remove(handler)
    
    # ========================================================================
    # EVENT HANDLING
    # ========================================================================
    
    async def _event_listener(self):
        """Background task that listens for events"""
        logger.info(f"Event listener started for client {self.client_id}")
        
        try:
            while self.messaging_connected:
                data = await self.messaging_reader.readline()
                if not data:
                    logger.warning("Messaging connection closed")
                    break
                
                try:
                    message = json.loads(data.decode().strip())
                    await self._handle_event(message)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON in event: {e}")
                except Exception as e:
                    logger.error(f"Error handling event: {e}", exc_info=True)
                    
        except asyncio.CancelledError:
            logger.info("Event listener cancelled")
            raise
        except Exception as e:
            logger.error(f"Fatal error in event listener: {e}", exc_info=True)
        finally:
            self.messaging_connected = False
    
    async def _handle_event(self, event: Dict[str, Any]):
        """Handle incoming event"""
        event_type = event.get("type")
        
        # Handle completion results specially
        if event_type == "COMPLETION_RESULT":
            await self._handle_completion_result(event)
            return
        
        # Call registered handlers
        handlers = self.event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}", exc_info=True)
    
    async def _handle_completion_result(self, event: Dict[str, Any]):
        """Handle completion result event"""
        # With targeted delivery, we should only receive our own results
        # But still check as a safety measure
        target_client = event.get("client_id") or event.get("to")
        if target_client and target_client != self.client_id:
            logger.debug(f"Ignoring completion result for different client: {target_client}")
            return
            
        request_id = event.get("request_id")
        if not request_id or request_id not in self.pending_completions:
            logger.warning(f"Received completion result for unknown request: {request_id}")
            return
        
        # Resolve the pending completion
        pending = self.pending_completions.pop(request_id)
        
        # Cancel timeout if still running
        if pending.timeout_task and not pending.timeout_task.done():
            pending.timeout_task.cancel()
        
        # Set the result
        result = event.get("result", {})
        if not pending.future.done():
            pending.future.set_result(result)
        
        logger.info(f"Completed request {request_id}")
    
    # ========================================================================
    # LIFECYCLE MANAGEMENT
    # ========================================================================
    
    async def close(self):
        """Clean up all connections"""
        # Cancel event listener
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        
        # Disconnect from messaging
        if self.messaging_connected and self.messaging_writer:
            try:
                disconnect_cmd = CommandBuilder.build_agent_connection_command(
                    "disconnect", self.client_id
                )
                await self._send_messaging_command(disconnect_cmd)
                
                self.messaging_writer.close()
                await self.messaging_writer.wait_closed()
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
        
        # Cancel all pending completions
        for pending in self.pending_completions.values():
            if not pending.future.done():
                pending.future.set_exception(
                    ConnectionError("Client closing")
                )
            if pending.timeout_task and not pending.timeout_task.done():
                pending.timeout_task.cancel()
        
        self.pending_completions.clear()
        self.messaging_connected = False
        self._initialized = False
        
        logger.info(f"Client {self.client_id} closed")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()


# ============================================================================
# HIGH-LEVEL CONVENIENCE CLASS
# ============================================================================

class SimpleChatClient(MultiSocketAsyncClient):
    """
    Simplified client for chat interfaces that just need completion functionality.
    
    This provides a simpler API that's closer to the old SPAWN interface.
    """
    
    def __init__(self, client_id: str = None):
        super().__init__(client_id)
        self.current_session_id: Optional[str] = None
    
    async def send_prompt(self, prompt: str, session_id: Optional[str] = None,
                         model: str = "sonnet") -> Tuple[str, str]:
        """
        Send a prompt and get response - simplified interface.
        
        Args:
            prompt: The prompt text
            session_id: Session ID (uses current if None)
            model: Claude model to use
            
        Returns:
            Tuple of (response_text, session_id)
        """
        # Use provided session_id or current
        session_id = session_id or self.current_session_id
        
        # Get completion
        response = await self.create_completion(
            prompt=prompt,
            model=model,
            session_id=session_id
        )
        
        # Extract session_id from response if available
        # (This would need to be added to the completion result)
        # For now, keep the same session_id
        self.current_session_id = session_id
        
        return response, session_id