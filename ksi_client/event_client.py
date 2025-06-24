#!/usr/bin/env python3
"""
Event-Based KSI Client - For the new plugin architecture

This client uses the event-driven API of the new plugin-based daemon.
All commands are converted to events and responses are received via events.

Key differences from the legacy client:
- Uses event names instead of command names
- All operations are async and event-driven
- No polling or direct socket management
- Supports plugin discovery and capability queries
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, Any, Optional, List, Callable, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger('ksi_client.event_client')


@dataclass
class EventSubscription:
    """Tracks an event subscription"""
    event_pattern: str
    handler: Callable
    filter_fn: Optional[Callable] = None


@dataclass
class PendingRequest:
    """Tracks a pending request with correlation ID"""
    correlation_id: str
    event_name: str
    future: asyncio.Future
    timeout_task: Optional[asyncio.Task] = None


class EventBasedClient:
    """
    Event-based client for the new plugin architecture.
    
    This client communicates entirely through events, matching
    the new daemon's event-driven design.
    """
    
    def __init__(self, client_id: str = None, socket_path: str = "/tmp/ksi/admin.sock"):
        """
        Initialize event-based client.
        
        Args:
            client_id: Unique client identifier (auto-generated if None)
            socket_path: Path to daemon socket (uses legacy socket for now)
        """
        self.client_id = client_id or f"event_client_{uuid.uuid4().hex[:8]}"
        self.socket_path = Path(socket_path)
        
        # Connection state
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        
        # Event handling
        self.subscriptions: List[EventSubscription] = []
        self.pending_requests: Dict[str, PendingRequest] = {}
        self._listen_task: Optional[asyncio.Task] = None
        
        # Plugin capabilities cache
        self._plugin_capabilities: Dict[str, Any] = {}
        
    async def connect(self) -> bool:
        """
        Connect to the daemon.
        
        Returns:
            True if connection successful
        """
        if self.connected:
            return True
            
        try:
            self.reader, self.writer = await asyncio.open_unix_connection(
                str(self.socket_path)
            )
            
            # Start event listener
            self._listen_task = asyncio.create_task(self._event_listener())
            
            # Announce ourselves
            await self.emit_event("transport:connection", {
                "client_id": self.client_id,
                "action": "connect"
            })
            
            self.connected = True
            logger.info(f"Event client {self.client_id} connected")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the daemon."""
        if not self.connected:
            return
            
        # Announce disconnection
        await self.emit_event("transport:connection", {
            "client_id": self.client_id,
            "action": "disconnect"
        })
        
        # Cancel listener
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        
        # Close connection
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        
        # Cancel pending requests
        for pending in self.pending_requests.values():
            if not pending.future.done():
                pending.future.set_exception(ConnectionError("Client disconnected"))
            if pending.timeout_task and not pending.timeout_task.done():
                pending.timeout_task.cancel()
        
        self.connected = False
        self.pending_requests.clear()
        logger.info(f"Event client {self.client_id} disconnected")
    
    # ========================================================================
    # CORE EVENT METHODS
    # ========================================================================
    
    async def emit_event(self, event_name: str, data: Dict[str, Any] = None,
                        correlation_id: str = None) -> None:
        """
        Emit an event to the daemon.
        
        Args:
            event_name: Event name (e.g., "system:health", "completion:request")
            data: Event data/parameters
            correlation_id: Optional correlation ID for request/response patterns
        """
        if not self.connected:
            raise ConnectionError("Not connected to daemon")
        
        event = {
            "event": event_name,
            "data": data or {},
            "client_id": self.client_id,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        if correlation_id:
            event["correlation_id"] = correlation_id
        
        # For now, wrap in legacy command format
        # This will be removed when daemon fully supports raw events
        command = {
            "command": "EVENT",
            "parameters": event
        }
        
        command_str = json.dumps(command) + '\n'
        self.writer.write(command_str.encode())
        await self.writer.drain()
    
    async def request_event(self, event_name: str, data: Dict[str, Any] = None,
                           timeout: float = 30.0) -> Dict[str, Any]:
        """
        Emit an event and wait for correlated response.
        
        Args:
            event_name: Event name
            data: Event data
            timeout: Response timeout in seconds
            
        Returns:
            Response data
            
        Raises:
            TimeoutError: If no response within timeout
        """
        correlation_id = str(uuid.uuid4())
        
        # Create pending request
        future = asyncio.Future()
        pending = PendingRequest(
            correlation_id=correlation_id,
            event_name=event_name,
            future=future
        )
        self.pending_requests[correlation_id] = pending
        
        # Set timeout
        pending.timeout_task = asyncio.create_task(
            self._request_timeout(correlation_id, timeout)
        )
        
        try:
            # Emit event with correlation ID
            await self.emit_event(event_name, data, correlation_id)
            
            # Wait for response
            return await future
            
        finally:
            # Clean up
            if correlation_id in self.pending_requests:
                pending = self.pending_requests.pop(correlation_id)
                if pending.timeout_task and not pending.timeout_task.done():
                    pending.timeout_task.cancel()
    
    async def _request_timeout(self, correlation_id: str, timeout: float):
        """Handle request timeout"""
        await asyncio.sleep(timeout)
        
        if correlation_id in self.pending_requests:
            pending = self.pending_requests.pop(correlation_id)
            if not pending.future.done():
                pending.future.set_exception(
                    TimeoutError(f"Request {correlation_id} timed out after {timeout}s")
                )
    
    def subscribe(self, event_pattern: str, handler: Callable,
                  filter_fn: Optional[Callable] = None):
        """
        Subscribe to events matching a pattern.
        
        Args:
            event_pattern: Event name pattern (supports wildcards)
            handler: Async function to handle matching events
            filter_fn: Optional filter function for additional filtering
        """
        sub = EventSubscription(
            event_pattern=event_pattern,
            handler=handler,
            filter_fn=filter_fn
        )
        self.subscriptions.append(sub)
        logger.debug(f"Subscribed to {event_pattern}")
    
    def unsubscribe(self, event_pattern: str, handler: Callable):
        """Unsubscribe from events."""
        self.subscriptions = [
            sub for sub in self.subscriptions
            if not (sub.event_pattern == event_pattern and sub.handler == handler)
        ]
    
    # ========================================================================
    # EVENT HANDLING
    # ========================================================================
    
    async def _event_listener(self):
        """Background task that listens for events from daemon."""
        logger.info(f"Event listener started for client {self.client_id}")
        
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
                    logger.error(f"Error handling message: {e}", exc_info=True)
                    
        except asyncio.CancelledError:
            logger.info("Event listener cancelled")
            raise
        except Exception as e:
            logger.error(f"Fatal error in event listener: {e}", exc_info=True)
        finally:
            self.connected = False
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming message from daemon."""
        # Check if it's an event or legacy response
        if "event" in message:
            # New event format
            await self._handle_event(message)
        else:
            # Legacy response format - convert to event
            if message.get("status") == "success" and "result" in message:
                # Convert to event
                event = {
                    "event": "response",
                    "data": message["result"],
                    "correlation_id": message.get("id")
                }
                await self._handle_event(event)
    
    async def _handle_event(self, event: Dict[str, Any]):
        """Handle incoming event."""
        event_name = event.get("event", "")
        event_data = event.get("data", {})
        correlation_id = event.get("correlation_id")
        
        # Check for correlated response
        if correlation_id and correlation_id in self.pending_requests:
            pending = self.pending_requests.pop(correlation_id)
            if pending.timeout_task and not pending.timeout_task.done():
                pending.timeout_task.cancel()
            if not pending.future.done():
                pending.future.set_result(event_data)
            return
        
        # Process subscriptions
        for sub in self.subscriptions:
            if self._matches_pattern(event_name, sub.event_pattern):
                if sub.filter_fn and not sub.filter_fn(event):
                    continue
                
                try:
                    if asyncio.iscoroutinefunction(sub.handler):
                        await sub.handler(event_name, event_data)
                    else:
                        sub.handler(event_name, event_data)
                except Exception as e:
                    logger.error(f"Error in handler for {event_name}: {e}", exc_info=True)
    
    def _matches_pattern(self, event_name: str, pattern: str) -> bool:
        """Check if event name matches pattern (supports wildcards)."""
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return event_name.startswith(prefix)
        return event_name == pattern
    
    # ========================================================================
    # HIGH-LEVEL API METHODS
    # ========================================================================
    
    async def health_check(self) -> Dict[str, Any]:
        """Check daemon health using event API."""
        return await self.request_event("system:health")
    
    async def get_plugins(self) -> Dict[str, Any]:
        """Get information about loaded plugins."""
        return await self.request_event("system:plugins")
    
    async def get_capabilities(self) -> Dict[str, List[str]]:
        """Get all available capabilities from plugins."""
        plugins = await self.get_plugins()
        
        capabilities = defaultdict(list)
        for plugin_name, plugin_info in plugins.items():
            caps = plugin_info.get("capabilities", {})
            
            # Aggregate capabilities by type
            for namespace in caps.get("event_namespaces", []):
                capabilities["namespaces"].append(namespace)
            
            for command in caps.get("commands", []):
                capabilities["commands"].append(command)
            
            for service in caps.get("provides_services", []):
                capabilities["services"].append(service)
        
        return dict(capabilities)
    
    async def create_completion(self, prompt: str, model: str = "sonnet",
                               session_id: Optional[str] = None,
                               timeout: float = 300.0) -> Dict[str, Any]:
        """
        Create a completion using event API.
        
        Args:
            prompt: The prompt text
            model: Model to use
            session_id: Optional session ID for continuity
            timeout: Completion timeout
            
        Returns:
            Completion result with response text and metadata
        """
        data = {
            "prompt": prompt,
            "model": model,
            "client_id": self.client_id
        }
        
        if session_id:
            data["session_id"] = session_id
        
        # Subscribe to completion events for this client
        completion_future = asyncio.Future()
        request_id = None
        
        async def completion_handler(event_name: str, event_data: Dict[str, Any]):
            nonlocal request_id
            
            if event_name == "completion:started":
                # Capture request ID
                if event_data.get("client_id") == self.client_id:
                    request_id = event_data.get("request_id")
            
            elif event_name == "completion:result":
                # Check if this is our result
                if (event_data.get("request_id") == request_id or
                    event_data.get("client_id") == self.client_id):
                    if not completion_future.done():
                        completion_future.set_result(event_data)
            
            elif event_name == "completion:error":
                # Check if this is our error
                if (event_data.get("request_id") == request_id or
                    event_data.get("client_id") == self.client_id):
                    if not completion_future.done():
                        completion_future.set_exception(
                            ValueError(event_data.get("error", "Completion failed"))
                        )
        
        # Subscribe to completion events
        self.subscribe("completion:*", completion_handler)
        
        try:
            # Send completion request
            await self.emit_event("completion:request", data)
            
            # Wait for result
            result = await asyncio.wait_for(completion_future, timeout=timeout)
            return result
            
        except asyncio.TimeoutError:
            raise TimeoutError(f"Completion timed out after {timeout}s")
        
        finally:
            # Unsubscribe
            self.unsubscribe("completion:*", completion_handler)
    
    async def shutdown_daemon(self) -> bool:
        """Request daemon shutdown."""
        try:
            await self.emit_event("system:shutdown")
            return True
        except Exception:
            # Connection may close before response
            return True
    
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


class EventChatClient(EventBasedClient):
    """
    Simplified event-based client for chat interfaces.
    
    Provides a high-level API similar to SimpleChatClient but using events.
    """
    
    def __init__(self, client_id: str = None):
        super().__init__(client_id)
        self.current_session_id: Optional[str] = None
    
    async def send_prompt(self, prompt: str, session_id: Optional[str] = None,
                         model: str = "sonnet") -> Tuple[str, str]:
        """
        Send a prompt and get response.
        
        Args:
            prompt: The prompt text
            session_id: Session ID (uses current if None)
            model: Model to use
            
        Returns:
            Tuple of (response_text, session_id)
        """
        # Use provided session_id or current
        session_id = session_id or self.current_session_id or str(uuid.uuid4())
        
        # Get completion
        result = await self.create_completion(
            prompt=prompt,
            model=model,
            session_id=session_id
        )
        
        # Extract response text
        response_text = result.get("response", "")
        
        # Update session ID
        self.current_session_id = session_id
        
        return response_text, session_id