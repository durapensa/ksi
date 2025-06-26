"""
Base administrative client - standalone implementation without ksi_client dependencies.

Provides core socket communication and event handling for admin operations.
"""

import asyncio
import json
import uuid
import logging
from typing import Dict, Any, Optional, List, Callable, Set
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ksi_common import config as ksi_config
from .protocols import AdminMessage, EventNamespace

logger = logging.getLogger(__name__)


@dataclass
class PendingRequest:
    """Track pending requests awaiting responses."""
    correlation_id: str
    future: asyncio.Future
    timeout_task: Optional[asyncio.Task] = None


class AdminBaseClient:
    """
    Base class for administrative clients.
    
    Provides standalone socket communication without dependencies on ksi_client.
    All admin clients inherit from this base.
    """
    
    def __init__(self, role: str, socket_path: str = None):
        """
        Initialize admin client.
        
        Args:
            role: Admin role (monitor, control, metrics, debug)
            socket_path: Path to daemon Unix socket (uses ksi_config if not provided)
        """
        self.role = role
        self.client_id = f"admin:{role}:{uuid.uuid4().hex[:8]}"
        self.socket_path = Path(socket_path) if socket_path else ksi_config.socket_path
        
        # Connection state
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self._listener_task: Optional[asyncio.Task] = None
        
        # Request tracking
        self.pending_requests: Dict[str, PendingRequest] = {}
        
        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {}
        
        logger.info(f"Created {self.__class__.__name__} with ID: {self.client_id}")
    
    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================
    
    async def connect(self):
        """Connect to daemon socket."""
        if self.connected:
            logger.warning("Already connected")
            return
        
        try:
            # Ensure socket exists
            if not self.socket_path.exists():
                raise FileNotFoundError(f"Socket not found: {self.socket_path}")
            
            # Connect to Unix socket
            self.reader, self.writer = await asyncio.open_unix_connection(
                str(self.socket_path)
            )
            
            self.connected = True
            
            # Start event listener
            self._listener_task = asyncio.create_task(self._event_listener())
            
            # Send initial identification
            await self._identify()
            
            logger.info(f"Connected to daemon at {self.socket_path}")
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self.connected = False
            raise
    
    async def disconnect(self):
        """Disconnect from daemon."""
        if not self.connected:
            return
        
        try:
            # Cancel listener
            if self._listener_task and not self._listener_task.done():
                self._listener_task.cancel()
                try:
                    await self._listener_task
                except asyncio.CancelledError:
                    pass
            
            # Close socket
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
            
            self.connected = False
            logger.info("Disconnected from daemon")
            
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
    async def _identify(self):
        """Send admin identification to daemon."""
        # Admin clients use a special identification protocol
        await self.emit_event("admin:identify", {
            "client_id": self.client_id,
            "role": self.role,
            "capabilities": self._get_capabilities()
        })
    
    def _get_capabilities(self) -> List[str]:
        """Get admin capabilities for this client type."""
        # Override in subclasses
        return ["basic"]
    
    # ========================================================================
    # EVENT HANDLING
    # ========================================================================
    
    async def emit_event(self, event: str, data: Dict[str, Any], 
                        correlation_id: Optional[str] = None) -> None:
        """
        Emit an event to the daemon.
        
        Args:
            event: Event name
            data: Event data
            correlation_id: Optional correlation ID
        """
        if not self.connected:
            raise ConnectionError("Not connected to daemon")
        
        msg = AdminMessage(
            event=event,
            data=data,
            client_id=self.client_id,
            timestamp=datetime.utcnow().isoformat(),
            correlation_id=correlation_id
        )
        
        message_str = msg.to_json() + '\n'
        self.writer.write(message_str.encode())
        await self.writer.drain()
        
        logger.debug(f"Emitted event: {event}")
    
    async def request_event(self, event: str, data: Dict[str, Any], 
                           timeout: float = 30.0) -> Dict[str, Any]:
        """
        Request-response pattern for events.
        
        Args:
            event: Event name
            data: Event data
            timeout: Response timeout
            
        Returns:
            Response data
        """
        correlation_id = str(uuid.uuid4())
        
        # Create future for response
        future = asyncio.Future()
        pending = PendingRequest(
            correlation_id=correlation_id,
            future=future
        )
        
        # Set timeout
        pending.timeout_task = asyncio.create_task(
            self._timeout_request(correlation_id, timeout)
        )
        
        self.pending_requests[correlation_id] = pending
        
        try:
            # Send request
            await self.emit_event(event, data, correlation_id)
            
            # Wait for response
            result = await future
            return result
            
        finally:
            # Cleanup
            if correlation_id in self.pending_requests:
                del self.pending_requests[correlation_id]
    
    async def _timeout_request(self, correlation_id: str, timeout: float):
        """Handle request timeout."""
        await asyncio.sleep(timeout)
        
        if correlation_id in self.pending_requests:
            pending = self.pending_requests[correlation_id]
            if not pending.future.done():
                pending.future.set_exception(
                    TimeoutError(f"Request timed out after {timeout}s")
                )
    
    def on_event(self, event_pattern: str, handler: Callable):
        """
        Register event handler.
        
        Args:
            event_pattern: Event name or pattern (supports wildcards)
            handler: Async function to handle event
        """
        if event_pattern not in self._event_handlers:
            self._event_handlers[event_pattern] = []
        
        self._event_handlers[event_pattern].append(handler)
        logger.debug(f"Registered handler for: {event_pattern}")
    
    async def _event_listener(self):
        """Background task to listen for events."""
        logger.info("Event listener started")
        
        try:
            while self.connected:
                data = await self.reader.readline()
                if not data:
                    logger.warning("Connection closed by daemon")
                    break
                
                try:
                    message = json.loads(data.decode().strip())
                    await self._handle_message(message)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON: {e}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
                    
        except asyncio.CancelledError:
            logger.info("Event listener cancelled")
            raise
        except Exception as e:
            logger.error(f"Fatal error in event listener: {e}")
        finally:
            self.connected = False
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming message."""
        # Check for correlation - is this a response?
        correlation_id = message.get("correlation_id")
        if correlation_id and correlation_id in self.pending_requests:
            pending = self.pending_requests[correlation_id]
            if pending.timeout_task and not pending.timeout_task.done():
                pending.timeout_task.cancel()
            if not pending.future.done():
                # Extract the actual data based on response format
                if "result" in message:
                    pending.future.set_result(message["result"])
                elif "error" in message:
                    pending.future.set_exception(Exception(message["error"]))
                else:
                    pending.future.set_result(message)
            return
        
        # Otherwise, it's an event - dispatch to handlers
        event_name = message.get("event", "")
        event_data = message.get("data", message)
        
        # Dispatch to matching handlers
        for pattern, handlers in self._event_handlers.items():
            if self._matches_pattern(event_name, pattern):
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event_name, event_data)
                        else:
                            handler(event_name, event_data)
                    except Exception as e:
                        logger.error(f"Error in event handler: {e}")
    
    def _matches_pattern(self, event: str, pattern: str) -> bool:
        """Check if event matches pattern (supports wildcards)."""
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return event.startswith(pattern[:-1])
        return event == pattern
    
    # ========================================================================
    # CONTEXT MANAGER
    # ========================================================================
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()