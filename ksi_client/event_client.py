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

from ksi_common import config, get_logger, parse_completion_response

logger = get_logger(__name__)


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
    
    def __init__(self, client_id: str = None, socket_path: str = None):
        """
        Initialize event-based client.
        
        Args:
            client_id: Unique client identifier (auto-generated if None)
            socket_path: Path to daemon socket
        """
        self.client_id = client_id or f"event_client_{uuid.uuid4().hex[:8]}"
        self.socket_path = Path(socket_path) if socket_path else config.socket_path
        
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
            
            # Mark as connected before announcing (emit_event checks this)
            self.connected = True
            
            # Start event listener
            self._listen_task = asyncio.create_task(self._event_listener())
            
            # Give the listener a moment to start
            await asyncio.sleep(0.01)
            
            # Announce ourselves
            try:
                await self.emit_event("transport:connection", {
                    "client_id": self.client_id,
                    "action": "connect"
                })
            except Exception as e:
                logger.warning(f"Failed to announce connection: {e}")
                # Continue anyway - connection might still work
            
            logger.info(f"Event client {self.client_id} connected")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            # Clean up on failure
            self.connected = False
            if self._listen_task and not self._listen_task.done():
                self._listen_task.cancel()
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
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
        
        # Send event directly (new protocol)
        event_str = json.dumps(event) + '\n'
        self.writer.write(event_str.encode())
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
    
    async def send_async_wait_result(self, request_event: str, request_data: Dict[str, Any],
                                    result_event: str, timeout: float = 30.0,
                                    result_id_field: str = "request_id") -> Dict[str, Any]:
        """
        Send an async event and wait synchronously for matching result.
        
        This is a generic pattern for async operations that need a sync interface.
        It handles request ID generation, event subscription, timeout, and cleanup.
        
        Args:
            request_event: Event to send (e.g., "completion:async")
            request_data: Data for request (request_id will be added if not present)
            result_event: Event to wait for (e.g., "completion:result")
            timeout: How long to wait for result
            result_id_field: Field name to match results (default: "request_id")
            
        Returns:
            Result data from the matching result event
            
        Raises:
            TimeoutError: If no matching result within timeout
        """
        # Generate request ID if not provided
        request_id = request_data.get(result_id_field)
        if not request_id:
            request_id = f"{self.client_id}_{uuid.uuid4().hex[:8]}"
            request_data[result_id_field] = request_id
        
        # Create future for result
        result_future = asyncio.Future()
        
        # Handler for results
        async def handle_result(event_name: str, event_data: Dict[str, Any]):
            if event_data.get(result_id_field) == request_id:
                if not result_future.done():
                    result_future.set_result(event_data)
        
        # Subscribe to result events
        self.subscribe(result_event, handle_result)
        
        try:
            # Send async request
            await self.emit_event(request_event, request_data)
            
            # Wait for result with timeout
            return await asyncio.wait_for(result_future, timeout=timeout)
            
        except asyncio.TimeoutError:
            raise TimeoutError(f"Request {request_id} timed out after {timeout}s waiting for {result_event}")
            
        finally:
            # Always unsubscribe handler
            self.unsubscribe(result_event, handle_result)
    
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
            correlation_id = message.get("id") or message.get("correlation_id")
            
            # Handle different response formats
            if message.get("status") == "success":
                # Response might have result or be the data itself
                data = message.get("result", message)
            elif message.get("status") == "healthy":
                # Health check response
                data = message
            elif "error" in message:
                # Error response
                data = message
            else:
                # Unknown format - use as-is
                data = message
            
            # Convert to event
            event = {
                "event": "response",
                "data": data,
                "correlation_id": correlation_id
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
    
    async def create_completion_async(self, prompt: str, model: str = "sonnet",
                                     session_id: Optional[str] = None,
                                     priority: str = "normal",
                                     injection_config: Optional[Dict[str, Any]] = None) -> str:
        """
        Create an async completion request and return immediately.
        
        Args:
            prompt: The prompt text
            model: Model to use
            session_id: Optional session ID for continuity
            priority: Request priority (critical, high, normal, low, background)
            injection_config: Optional injection configuration
            
        Returns:
            Request ID for tracking the completion
        """
        request_id = f"{self.client_id}_{uuid.uuid4().hex[:8]}"
        
        data = {
            "request_id": request_id,
            "prompt": prompt,
            "model": model,
            "client_id": self.client_id,
            "priority": priority
        }
        
        if session_id:
            data["session_id"] = session_id
            
        if injection_config:
            data["injection_config"] = injection_config
        
        # Send async completion event
        await self.emit_event("completion:async", data)
        
        return request_id
    
    async def create_completion_sync(self, prompt: str, model: str = "sonnet",
                                    session_id: Optional[str] = None,
                                    timeout: float = 900.0) -> Dict[str, Any]:
        """
        Create a completion and wait for the result (synchronous interface).
        
        This method provides a synchronous-looking interface while using
        the async completion system internally.
        
        Args:
            prompt: The prompt text
            model: Model to use
            session_id: Optional session ID for continuity
            timeout: Completion timeout
            
        Returns:
            Completion result with response text and metadata
            
        Raises:
            ValueError: If completion returns an error
            TimeoutError: If completion times out
        """
        # Prepare request data
        request_data = {
            "prompt": prompt,
            "model": model,
            "client_id": self.client_id,
            "priority": "normal"
        }
        
        if session_id:
            request_data["session_id"] = session_id
        
        # Use generic helper to send and wait
        result = await self.send_async_wait_result(
            request_event="completion:async",
            request_data=request_data,
            result_event="completion:result",
            timeout=timeout
        )
        
        # Check for errors
        if result.get("status") == "error":
            raise ValueError(result.get("error", "Completion failed"))
            
        return result
    
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
    
    Provides a high-level API for simple chat operations.
    For multi-agent coordination, use MultiAgentClient instead.
    """
    
    def __init__(self, client_id: str = None, socket_path: str = None):
        super().__init__(client_id, socket_path)
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
        # Use provided session_id or current - None is valid for NEW conversations
        session_id = session_id or self.current_session_id
        # Note: session_id=None is valid for starting new conversations
        # Claude CLI will provide session_id in response
        
        # Get completion
        result = await self.create_completion_sync(
            prompt=prompt,
            model=model,
            session_id=session_id
        )
        
        # Parse standardized completion response and extract text
        completion_response = parse_completion_response(result)
        response_text = completion_response.get_text()
        
        # Extract session ID from response (might be updated by provider)
        response_session_id = completion_response.get_session_id() or session_id
        self.current_session_id = response_session_id
        
        return response_text, response_session_id


class MultiAgentClient(EventBasedClient):
    """
    Multi-agent coordination client.
    
    Provides agent management, message bus, and state management capabilities
    for multi-agent systems. State management is included here because persistent
    state is primarily used for agent coordination.
    """
    
    def __init__(self, client_id: str = None, socket_path: str = None):
        super().__init__(client_id, socket_path)
        self.agent_id: Optional[str] = None
        self.conversation_id: Optional[str] = None
        self._message_handlers: List[Callable] = []
        self._agent_connected = False
    
    # ========================================================================
    # AGENT MANAGEMENT API
    # ========================================================================
    
    async def register_as_agent(self, agent_id: str = None, profile: str = None) -> bool:
        """
        Register this client as an agent.
        
        Args:
            agent_id: Agent ID (uses client_id if None)
            profile: Optional agent profile to use
            
        Returns:
            True if registration successful
        """
        self.agent_id = agent_id or self.client_id
        
        try:
            # Connect as agent
            result = await self.request_event("agent:connect", {
                "agent_id": self.agent_id,
                "profile": profile
            })
            
            if result.get("status") == "connected":
                self._agent_connected = True
                
                # Subscribe to agent messages
                await self._setup_agent_subscriptions()
                
                logger.info(f"Registered as agent: {self.agent_id}")
                return True
            else:
                logger.error(f"Agent registration failed: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to register as agent: {e}")
            return False
    
    async def unregister_agent(self) -> bool:
        """Unregister current agent."""
        if not self.agent_id or not self._agent_connected:
            return True
            
        try:
            # Unsubscribe from messages
            await self.request_event("message:unsubscribe", {
                "agent_id": self.agent_id
            })
            
            # Disconnect agent
            await self.request_event("agent:disconnect", {
                "agent_id": self.agent_id
            })
            
            self._agent_connected = False
            self.agent_id = None
            logger.info(f"Unregistered agent")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister agent: {e}")
            return False
    
    async def list_agents(self) -> List[Dict[str, Any]]:
        """Get list of active agents."""
        try:
            result = await self.request_event("agent:list", {})
            return result.get("agents", [])
        except Exception as e:
            logger.error(f"Failed to list agents: {e}")
            return []
    
    async def get_agent_info(self, agent_id: str = None) -> Optional[Dict[str, Any]]:
        """Get information about an agent."""
        agent_id = agent_id or self.agent_id
        if not agent_id:
            return None
            
        try:
            result = await self.request_event("agent:info", {
                "agent_id": agent_id
            })
            return result
        except Exception as e:
            logger.error(f"Failed to get agent info: {e}")
            return None
    
    # ========================================================================
    # MESSAGE BUS API
    # ========================================================================
    
    async def join_conversation(self, conversation_id: str) -> bool:
        """
        Join a conversation.
        
        Args:
            conversation_id: Conversation to join
            
        Returns:
            True if joined successfully
        """
        if not self._agent_connected:
            # Auto-register as agent if not already
            if not await self.register_as_agent():
                return False
        
        self.conversation_id = conversation_id
        
        # Subscribe to conversation messages
        try:
            await self.request_event("message:subscribe", {
                "agent_id": self.agent_id,
                "conversation_id": conversation_id,
                "events": ["DIRECT_MESSAGE", "BROADCAST", "CONVERSATION_MESSAGE"]
            })
            
            logger.info(f"Joined conversation: {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to join conversation: {e}")
            return False
    
    async def leave_conversation(self) -> bool:
        """Leave current conversation."""
        if not self.conversation_id:
            return True
            
        try:
            await self.request_event("message:unsubscribe", {
                "agent_id": self.agent_id,
                "conversation_id": self.conversation_id
            })
            
            self.conversation_id = None
            logger.info("Left conversation")
            return True
            
        except Exception as e:
            logger.error(f"Failed to leave conversation: {e}")
            return False
    
    async def send_message(self, content: str, to: str = None, 
                          conversation_id: str = None) -> bool:
        """
        Send a message.
        
        Args:
            content: Message content
            to: Target agent ID (for direct messages)
            conversation_id: Conversation ID (uses current if None)
            
        Returns:
            True if sent successfully
        """
        if not self._agent_connected:
            logger.error("Not registered as agent")
            return False
        
        conversation_id = conversation_id or self.conversation_id
        
        try:
            # Determine message type
            if to:
                # Direct message
                await self.request_event("message:publish", {
                    "agent_id": self.agent_id,
                    "event_type": "DIRECT_MESSAGE",
                    "data": {
                        "to": to,
                        "content": content,
                        "conversation_id": conversation_id
                    }
                })
            elif conversation_id:
                # Conversation broadcast
                await self.request_event("message:publish", {
                    "agent_id": self.agent_id,
                    "event_type": "CONVERSATION_MESSAGE",
                    "data": {
                        "content": content,
                        "conversation_id": conversation_id
                    }
                })
            else:
                logger.error("No target specified for message")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    def on_message(self, callback: Callable[[str, str, str, Optional[str]], None]):
        """
        Register callback for incoming messages.
        
        Args:
            callback: Function to call with (sender, content, timestamp, conversation_id)
        """
        self._message_handlers.append(callback)
    
    async def list_conversations(self) -> List[Dict[str, Any]]:
        """Get list of active conversations."""
        try:
            result = await self.request_event("message:conversations", {})
            return result.get("conversations", [])
        except Exception as e:
            logger.error(f"Failed to list conversations: {e}")
            return []
    
    # ========================================================================
    # STATE MANAGEMENT API
    # ========================================================================
    
    async def get_state(self, key: str, namespace: str = "global") -> Any:
        """
        Get state value.
        
        Args:
            key: State key
            namespace: State namespace
            
        Returns:
            State value or None
        """
        try:
            result = await self.request_event("state:get", {
                "key": key,
                "namespace": namespace
            })
            
            if result.get("found"):
                return result.get("value")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get state: {e}")
            return None
    
    async def set_state(self, key: str, value: Any, 
                       namespace: str = "global") -> bool:
        """
        Set state value.
        
        Args:
            key: State key
            value: State value
            namespace: State namespace
            
        Returns:
            True if set successfully
        """
        try:
            result = await self.request_event("state:set", {
                "key": key,
                "value": value,
                "namespace": namespace
            })
            
            return result.get("status") == "set"
            
        except Exception as e:
            logger.error(f"Failed to set state: {e}")
            return False
    
    async def delete_state(self, key: str, namespace: str = "global") -> bool:
        """Delete state value."""
        try:
            result = await self.request_event("state:delete", {
                "key": key,
                "namespace": namespace
            })
            
            return result.get("status") in ["deleted", "not_found"]
            
        except Exception as e:
            logger.error(f"Failed to delete state: {e}")
            return False
    
    async def list_state_keys(self, namespace: str = None, 
                             pattern: str = None) -> List[str]:
        """List state keys."""
        try:
            data = {}
            if namespace:
                data["namespace"] = namespace
            if pattern:
                data["pattern"] = pattern
                
            result = await self.request_event("state:list", data)
            return result.get("keys", [])
            
        except Exception as e:
            logger.error(f"Failed to list state keys: {e}")
            return []
    
    # ========================================================================
    # INTERNAL METHODS
    # ========================================================================
    
    async def _setup_agent_subscriptions(self):
        """Set up message subscriptions for agent."""
        if not self.agent_id:
            return
            
        # Subscribe to message events
        await self.subscribe("message:received:*", self._handle_incoming_message)
        await self.subscribe(f"message:direct:{self.agent_id}", self._handle_incoming_message)
        await self.subscribe(f"message:broadcast", self._handle_incoming_message)
        
        # Also request explicit subscription for the message bus
        await self.request_event("message:subscribe", {
            "agent_id": self.agent_id,
            "events": ["DIRECT_MESSAGE", "BROADCAST", "CONVERSATION_INVITE"]
        })
    
    async def _handle_incoming_message(self, event_name: str, data: Dict[str, Any]):
        """Handle incoming message events."""
        # Extract message details
        sender = data.get("from", "Unknown")
        content = data.get("content", "")
        timestamp = data.get("timestamp", "")
        conversation_id = data.get("conversation_id")
        
        # Call all registered handlers
        for handler in self._message_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(sender, content, timestamp, conversation_id)
                else:
                    handler(sender, content, timestamp, conversation_id)
            except Exception as e:
                logger.error(f"Error in message handler: {e}", exc_info=True)
    
    async def disconnect(self):
        """Enhanced disconnect that cleans up agent state."""
        # Unregister agent if needed
        if self._agent_connected:
            await self.unregister_agent()
            
        # Call parent disconnect
        await super().disconnect()
    
