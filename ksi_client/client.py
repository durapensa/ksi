#!/usr/bin/env python3
"""
KSI Event Client

Adaptive, self-discovering event client for KSI daemon.
Automatically manages daemon lifecycle and discovers available events.
"""

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Set, Union, TypeVar, Literal
import structlog

from .daemon_manager import DaemonManager
from .exceptions import (
    KSIConnectionError, KSITimeoutError, KSIEventError,
    KSIDiscoveryError, KSIPermissionError
)
from .validation import validate_event_params
from .discovery import generate_type_stubs_for_client

logger = structlog.get_logger("ksi.client")

# Only these bootstrap events are hardcoded
BOOTSTRAP_EVENTS = {
    "system:health",      # Check connection
    "system:discover",    # Discover all other events
    "system:help",        # Get detailed event help
}

BOOTSTRAP_TIMEOUT = 5.0  # seconds


class EventNamespace:
    """Dynamic namespace for events like client.completion.async()"""
    
    def __init__(self, client: 'EventClient', namespace: str):
        self._client = client
        self._namespace = namespace
    
    def __getattr__(self, event_name: str) -> Callable:
        """Create event method dynamically."""
        # Handle Python reserved keywords by appending underscore
        if event_name == "async_":
            event_name = "async"
        
        full_event = f"{self._namespace}:{event_name}"
        
        # Check if event exists in cache (if discovered)
        if self._client._discovered and not self._client.has_event(full_event):
            raise AttributeError(f"Unknown event: {full_event}")
        
        async def event_method(**kwargs) -> Dict[str, Any]:
            """Dynamically created event method."""
            # Validate parameters if schema available
            if self._client._discovered:
                self._client._validate_params(full_event, kwargs)
            
            return await self._client.send_event(full_event, kwargs)
        
        # Add metadata
        event_method.__name__ = event_name
        event_method.__qualname__ = f"{self._namespace}.{event_name}"
        
        # Add docstring from discovery if available
        if self._client._discovered:
            event_info = self._client.get_event_info(full_event)
            if event_info:
                event_method.__doc__ = self._format_event_doc(event_info)
        
        return event_method
    
    def _format_event_doc(self, event_info: Dict[str, Any]) -> str:
        """Format event info as docstring."""
        doc = event_info.get("summary", "")
        
        if event_info.get("parameters"):
            doc += "\n\nParameters:\n"
            for name, info in event_info["parameters"].items():
                required = " (required)" if info.get("required") else " (optional)"
                doc += f"    {name}: {info.get('type', 'Any')}{required}\n"
                if info.get("description"):
                    doc += f"        {info['description']}\n"
        
        return doc


class EventClient:
    """
    Self-discovering event client with automatic daemon management.
    
    Usage:
        async with EventClient() as client:
            # Daemon automatically started if needed
            # Events automatically discovered
            
            # Use discovered events with namespace syntax
            # Note: Use async_ because async is a Python keyword
            response = await client.completion.async_(
                prompt="Hello!",
                agent_config={"permission_profile": "restricted"}
            )
    """
    
    def __init__(self, 
                 client_id: Optional[str] = None,
                 socket_path: Optional[Path] = None,
                 auto_start_daemon: bool = True,
                 discovery_cache_ttl: int = 3600):
        """
        Initialize event client.
        
        Args:
            client_id: Unique client identifier (auto-generated if None)
            socket_path: Path to daemon socket (auto-detected if None)
            auto_start_daemon: Automatically start daemon if not running
            discovery_cache_ttl: Cache discovered events for this many seconds
        """
        self.client_id = client_id or f"ksi_client_{uuid.uuid4().hex[:8]}"
        self.socket_path = socket_path or Path.cwd() / "var/run/daemon.sock"
        self.auto_start_daemon = auto_start_daemon
        self.discovery_cache_ttl = discovery_cache_ttl
        
        # Daemon manager (if auto-start enabled)
        self.daemon_manager = DaemonManager() if auto_start_daemon else None
        
        # Connection state
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self._listen_task: Optional[asyncio.Task] = None
        
        # Discovery state
        self._event_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._permission_cache: Dict[str, Dict[str, Any]] = {}
        self._discovered = False
        self._cache_time: Optional[float] = None
        
        # Event handling
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
    
    async def __aenter__(self):
        """Async context manager entry."""
        # Ensure daemon is running (if auto-start enabled)
        if self.daemon_manager:
            logger.info("Ensuring daemon is running...")
            if not await self.daemon_manager.ensure_daemon_running():
                raise KSIConnectionError("Failed to start daemon")
        
        # Connect to socket
        await self.connect()
        
        # Discover available events
        try:
            await self.discover()
        except Exception as e:
            logger.warning(f"Discovery failed: {e}")
            # Client still works with bootstrap events only
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
    
    async def connect(self):
        """Connect to daemon socket."""
        if self.connected:
            return
        
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_unix_connection(str(self.socket_path)),
                timeout=BOOTSTRAP_TIMEOUT
            )
            self.connected = True
            
            # Start listening for events
            self._listen_task = asyncio.create_task(self._listen_for_events())
            
            logger.info(f"Connected to daemon at {self.socket_path}")
            
        except asyncio.TimeoutError:
            raise KSITimeoutError(f"Connection timeout to {self.socket_path}")
        except Exception as e:
            raise KSIConnectionError(f"Failed to connect: {e}")
    
    async def disconnect(self):
        """Disconnect from daemon."""
        if not self.connected:
            return
        
        # Cancel listen task
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        
        # Close connection
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        
        self.connected = False
        logger.info("Disconnected from daemon")
    
    async def _listen_for_events(self):
        """Listen for broadcast events from daemon."""
        try:
            while self.connected:
                line = await self.reader.readline()
                if not line:
                    break
                
                try:
                    message = json.loads(line.decode().strip())
                    
                    # Check if this is a response to a request
                    correlation_id = message.get("correlation_id")
                    if correlation_id and correlation_id in self._pending_requests:
                        # This is a response to our request
                        future = self._pending_requests.pop(correlation_id)
                        if not future.cancelled():
                            future.set_result(message)
                    else:
                        # This is a broadcast event
                        event_name = message.get("event")
                        if event_name:
                            await self._handle_broadcast_event(event_name, message)
                
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON received: {e}")
                    
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Listen task error: {e}")
            self.connected = False
    
    async def _handle_broadcast_event(self, event_name: str, message: Dict[str, Any]):
        """Handle broadcast events."""
        handlers = self._event_handlers.get(event_name, [])
        for handler in handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"Handler error for {event_name}: {e}")
    
    async def send_event(self, event_name: str, data: Dict[str, Any] = None,
                        timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Send event and wait for response.
        
        Args:
            event_name: Name of the event (e.g., "completion:async")
            data: Event data/parameters
            timeout: Response timeout in seconds
            
        Returns:
            Response from daemon
        """
        if not self.connected:
            raise KSIConnectionError("Not connected to daemon")
        
        if data is None:
            data = {}
        
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())
        
        # Create request message
        request = {
            "event": event_name,
            "data": data,
            "correlation_id": correlation_id
        }
        
        # Create future for response
        response_future = asyncio.Future()
        self._pending_requests[correlation_id] = response_future
        
        try:
            # Send request
            message = json.dumps(request) + '\n'
            self.writer.write(message.encode())
            await self.writer.drain()
            
            # Wait for response
            timeout = timeout or (BOOTSTRAP_TIMEOUT if event_name in BOOTSTRAP_EVENTS else 30.0)
            envelope = await asyncio.wait_for(response_future, timeout=timeout)
            
            # Handle JSON envelope format
            if "error" in envelope:
                raise KSIEventError(event_name, envelope["error"], envelope)
            
            # Return raw REST response - let clients decide how to handle
            # REST pattern: single object for single response, array for multiple
            return envelope.get("data")
            
        except asyncio.TimeoutError:
            self._pending_requests.pop(correlation_id, None)
            raise KSITimeoutError(f"Event {event_name} timed out")
        except Exception:
            self._pending_requests.pop(correlation_id, None)
            raise
    
    # Convenience methods for common JSON API patterns
    
    async def send_single(self, event_name: str, data: Dict[str, Any] = None,
                         timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Send event expecting exactly one response.
        
        Raises:
            KSIEventError: If 0 or >1 responses received
        """
        response = await self.send_event(event_name, data, timeout)
        
        # Handle REST pattern
        if isinstance(response, dict):
            return response  # Single response
        elif isinstance(response, list):
            if len(response) == 0:
                raise KSIEventError(event_name, "No response received", response)
            elif len(response) == 1:
                return response[0]
            else:
                raise KSIEventError(event_name, f"Expected single response, got {len(response)}", response)
        else:
            raise KSIEventError(event_name, f"Unexpected response type: {type(response)}", response)
    
    async def send_all(self, event_name: str, data: Dict[str, Any] = None,
                      timeout: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Send event and always return a list of responses.
        
        Normalizes single responses to [response].
        """
        response = await self.send_event(event_name, data, timeout)
        
        # Normalize to list
        if isinstance(response, dict):
            return [response]
        elif isinstance(response, list):
            return response
        else:
            return [response] if response is not None else []
    
    async def send_first(self, event_name: str, data: Dict[str, Any] = None,
                        timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Send event and return first response, or None if no responses.
        
        Useful for events where any response is acceptable.
        """
        response = await self.send_event(event_name, data, timeout)
        
        if isinstance(response, dict):
            return response
        elif isinstance(response, list) and len(response) > 0:
            return response[0]
        else:
            return None
    
    async def get_value(self, event_name: str, data: Dict[str, Any] = None,
                       key: str = "value", default: Any = None,
                       timeout: Optional[float] = None) -> Any:
        """
        Send event and extract a specific field from the response.
        
        Args:
            event_name: Event to send
            data: Event data
            key: Field to extract from response
            default: Default value if field not found
            timeout: Response timeout
            
        Returns:
            Extracted value or default
        """
        try:
            response = await self.send_single(event_name, data, timeout)
            return response.get(key, default)
        except KSIEventError:
            return default
    
    async def send_success_only(self, event_name: str, data: Dict[str, Any] = None,
                               timeout: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Send event and return only successful responses (no 'error' field).
        
        Filters out any responses containing error fields.
        """
        responses = await self.send_all(event_name, data, timeout)
        return [r for r in responses if isinstance(r, dict) and "error" not in r]
    
    async def send_and_merge(self, event_name: str, data: Dict[str, Any] = None,
                            merge_key: Optional[str] = None, 
                            timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Send event and merge responses from multiple handlers.
        
        Args:
            event_name: Event to send
            data: Event data
            merge_key: If specified, merge this field across responses (must be dict)
            timeout: Response timeout
            
        Returns:
            Merged response dict
        """
        responses = await self.send_all(event_name, data, timeout)
        
        if not responses:
            return {}
        
        # Start with first response
        merged = responses[0].copy() if isinstance(responses[0], dict) else {}
        
        # Merge additional responses
        for resp in responses[1:]:
            if not isinstance(resp, dict):
                continue
                
            if merge_key and merge_key in resp and merge_key in merged:
                # Deep merge specific field
                if isinstance(merged[merge_key], dict) and isinstance(resp[merge_key], dict):
                    merged[merge_key].update(resp[merge_key])
                elif isinstance(merged[merge_key], list) and isinstance(resp[merge_key], list):
                    merged[merge_key].extend(resp[merge_key])
            else:
                # Shallow merge entire response
                merged.update(resp)
        
        return merged
    
    async def send_with_errors(self, event_name: str, data: Dict[str, Any] = None,
                              error_mode: Literal["fail_fast", "collect", "warn"] = "fail_fast",
                              timeout: Optional[float] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Send event with configurable error handling.
        
        Args:
            event_name: Event to send
            data: Event data
            error_mode: How to handle errors
                - "fail_fast": Raise on first error (default)
                - "collect": Return {"results": [...], "errors": [...]}
                - "warn": Log warnings but return successful responses
            timeout: Response timeout
            
        Returns:
            Response(s) based on error_mode
        """
        responses = await self.send_all(event_name, data, timeout)
        
        errors = []
        results = []
        
        for resp in responses:
            if isinstance(resp, dict) and "error" in resp:
                errors.append(resp)
            else:
                results.append(resp)
        
        if error_mode == "fail_fast" and errors:
            # Re-raise first error
            raise KSIEventError(event_name, errors[0].get("error", "Unknown error"), errors[0])
        elif error_mode == "collect":
            return {"results": results, "errors": errors, "has_errors": len(errors) > 0}
        else:  # warn mode
            for error in errors:
                logger.warning(f"Event {event_name} error: {error.get('error', 'Unknown')}")
            return results
    
    def subscribe(self, event_pattern: str, handler: Callable):
        """
        Subscribe to broadcast events.
        
        Args:
            event_pattern: Event name or pattern to subscribe to
            handler: Async function to handle events
        """
        if event_pattern not in self._event_handlers:
            self._event_handlers[event_pattern] = []
        self._event_handlers[event_pattern].append(handler)
    
    def unsubscribe(self, event_pattern: str, handler: Callable):
        """Unsubscribe from broadcast events."""
        if event_pattern in self._event_handlers:
            self._event_handlers[event_pattern].remove(handler)
    
    async def discover(self):
        """Discover all available events and permissions."""
        logger.info("Discovering available events...")
        
        try:
            # Discover all events using send_all for consistency
            responses = await self.send_all("system:discover", {})
            
            # Merge discovery data from all responses
            all_events = {}
            for resp in responses:
                if isinstance(resp, dict) and "events" in resp:
                    events = resp["events"]
                    for namespace, events_list in events.items():
                        if namespace not in all_events:
                            all_events[namespace] = []
                        all_events[namespace].extend(events_list)
            
            self._event_cache = all_events
            
            # Try to discover permission profiles
            if self._has_event_in_cache("permission:list_profiles"):
                try:
                    perm_responses = await self.send_all("permission:list_profiles", {})
                    
                    # Merge permission data from all responses
                    all_profiles = {}
                    for resp in perm_responses:
                        if isinstance(resp, dict) and "profiles" in resp:
                            all_profiles.update(resp["profiles"])
                    
                    self._permission_cache = all_profiles
                except Exception as e:
                    logger.warning(f"Permission discovery failed: {e}")
            
            self._discovered = True
            self._cache_time = time.time()
            
            logger.info(f"Discovered {sum(len(events) for events in self._event_cache.values())} events "
                       f"in {len(self._event_cache)} namespaces")
            
        except Exception as e:
            raise KSIDiscoveryError(f"Discovery failed: {e}")
    
    def _has_event_in_cache(self, event_name: str) -> bool:
        """Check if event exists in discovered cache."""
        if ":" not in event_name:
            return False
        
        namespace, _ = event_name.split(":", 1)
        events = self._event_cache.get(namespace, [])
        
        return any(event["event"] == event_name for event in events)
    
    def _cache_expired(self) -> bool:
        """Check if discovery cache has expired."""
        if not self._cache_time:
            return True
        return (time.time() - self._cache_time) > self.discovery_cache_ttl
    
    def has_event(self, event_name: str) -> bool:
        """Check if event is available."""
        if event_name in BOOTSTRAP_EVENTS:
            return True
        
        if not self._discovered or self._cache_expired():
            return False
        
        return self._has_event_in_cache(event_name)
    
    def get_event_info(self, event_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific event."""
        if not self._discovered:
            return None
        
        if ":" not in event_name:
            return None
        
        namespace, _ = event_name.split(":", 1)
        events = self._event_cache.get(namespace, [])
        
        for event in events:
            if event["event"] == event_name:
                return event
        
        return None
    
    def get_namespaces(self) -> List[str]:
        """Get list of discovered namespaces."""
        return list(self._event_cache.keys())
    
    def get_events_in_namespace(self, namespace: str) -> List[Dict[str, Any]]:
        """Get all events in a namespace."""
        return self._event_cache.get(namespace, [])
    
    def get_permission_profiles(self) -> List[str]:
        """Get available permission profiles."""
        return list(self._permission_cache.keys())
    
    def get_profile_info(self, profile: str) -> Optional[Dict[str, Any]]:
        """Get information about a permission profile."""
        return self._permission_cache.get(profile)
    
    def get_profile_tools(self, profile: str) -> Dict[str, List[str]]:
        """Get tools allowed/disallowed for a profile."""
        info = self.get_profile_info(profile)
        if not info:
            raise KSIPermissionError(profile, "Unknown permission profile")
        return info.get("tools", {"allowed": [], "disallowed": []})
    
    def _validate_params(self, event_name: str, params: Dict[str, Any]):
        """Validate parameters against discovered schema."""
        event_info = self.get_event_info(event_name)
        if event_info:
            validate_event_params(event_name, params, event_info)
    
    def __getattr__(self, namespace: str) -> EventNamespace:
        """Access event namespaces dynamically."""
        if namespace.startswith("_"):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{namespace}'")
        return EventNamespace(self, namespace)
    
    async def create_chat_completion(self, 
                                   prompt: str,
                                   permission_profile: str = "restricted",
                                   session_id: Optional[str] = None,
                                   **kwargs) -> Dict[str, Any]:
        """
        High-level helper for secure chat completions.
        
        Args:
            prompt: The prompt text
            permission_profile: Permission profile to use (default: "restricted" for safety)
            session_id: Optional session ID for conversation continuity
            **kwargs: Additional parameters for the completion
            
        Returns:
            Completion response
        """
        # Validate permission profile if discovered
        if self._discovered and permission_profile not in self._permission_cache:
            raise KSIPermissionError(permission_profile, "Unknown permission profile")
        
        # Build agent config
        agent_config = kwargs.pop("agent_config", {})
        agent_config.update({
            "permission_profile": permission_profile,
            "profile": agent_config.get("profile", "conversationalist")
        })
        
        # Send completion request expecting single response
        # Note: Use async_ because async is a Python keyword
        return await self.send_single("completion:async", {
            "prompt": prompt,
            "session_id": session_id,
            "agent_config": agent_config,
            **kwargs
        })
    
    def generate_type_stubs(self, output_path: Optional[Path] = None) -> str:
        """
        Generate type stubs from discovered events.
        
        Args:
            output_path: Path to write .pyi file (default: ksi_client/types/discovered.pyi)
            
        Returns:
            Generated stub content
            
        Raises:
            RuntimeError: If discovery hasn't been performed yet
        """
        return generate_type_stubs_for_client(self, output_path)