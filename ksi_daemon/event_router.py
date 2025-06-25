#!/usr/bin/env python3
"""
Simplified event router that combines event bus and plugin manager functionality.

Removes unnecessary layers of abstraction and provides direct event routing.
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Any, Optional, Callable, List, Set
from collections import defaultdict
import fnmatch

logger = logging.getLogger(__name__)


class SimpleEventRouter:
    """
    Simplified event router that directly routes events to plugin hooks.
    
    Combines the functionality of EventBus and PluginManager into a single,
    simpler component.
    """
    
    def __init__(self, plugin_loader):
        """
        Initialize the event router.
        
        Args:
            plugin_loader: The plugin loader instance
        """
        self.plugin_loader = plugin_loader
        self.plugin_manager = plugin_loader.pm
        
        # Direct event routing without intermediate subscriptions
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.request_timeout = 30.0
        
        # Statistics
        self.stats = {
            "events_routed": 0,
            "events_handled": 0,
            "events_failed": 0
        }
        
        # Transport instances
        self.transports = {}
    
    async def route_event(self, event_name: str, data: Dict[str, Any],
                         correlation_id: Optional[str] = None,
                         context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Route an event directly to plugin hooks.
        
        Args:
            event_name: Name of the event
            data: Event data
            correlation_id: Optional correlation ID for request/response
            context: Optional context data
            
        Returns:
            Combined responses from all handlers, or None
        """
        self.stats["events_routed"] += 1
        
        # Create context if not provided
        if context is None:
            context = {
                "event_id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "correlation_id": correlation_id
            }
        
        responses = []
        handlers_called = 0
        
        try:
            # Call the hook directly - pluggy will handle calling all implementations
            hook_results = self.plugin_manager.hook.ksi_handle_event(
                event_name=event_name,
                data=data,
                context=context
            )
            
            # Collect non-None responses
            if hook_results:
                for result in hook_results:
                    if result is not None:
                        handlers_called += 1
                        
                        # Handle async results
                        if asyncio.iscoroutine(result):
                            result = await result
                        
                        logger.debug(f"Got response from plugin: {result}")
                        responses.append(result)
            
            if handlers_called > 0:
                self.stats["events_handled"] += 1
            
            # For single response, return it directly
            if len(responses) == 1:
                response = responses[0]
                
                # Handle correlation responses
                if correlation_id and correlation_id in self.pending_requests:
                    future = self.pending_requests[correlation_id]
                    if not future.done():
                        future.set_result(response)
                
                return response
            
            # For multiple responses, combine them
            elif len(responses) > 1:
                logger.debug(f"Multiple responses for {event_name}: {responses}")
                combined = {"responses": responses}
                
                # Handle correlation
                if correlation_id and correlation_id in self.pending_requests:
                    future = self.pending_requests[correlation_id]
                    if not future.done():
                        future.set_result(combined)
                
                return combined
            
            return None
            
        except Exception as e:
            logger.error(f"Error routing event {event_name}: {e}", exc_info=True)
            self.stats["events_failed"] += 1
            return None
    
    async def request_event(self, event_name: str, data: Dict[str, Any],
                           timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Send an event and wait for a response.
        
        Args:
            event_name: Name of the event
            data: Event data
            timeout: Optional timeout (defaults to self.request_timeout)
            
        Returns:
            Response data or None if timeout
        """
        correlation_id = str(uuid.uuid4())
        future = asyncio.Future()
        self.pending_requests[correlation_id] = future
        
        timeout = timeout or self.request_timeout
        
        try:
            # Route the event
            await self.route_event(event_name, data, correlation_id)
            
            # Wait for response
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
            
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for response to {event_name}")
            return None
        finally:
            # Clean up
            self.pending_requests.pop(correlation_id, None)
    
    def inject_event_emitter(self, transport):
        """
        Inject a simple event emitter into a transport.
        
        The emitter will route events through this router.
        """
        async def emit_event(event_name: str, data: Dict[str, Any],
                            correlation_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
            return await self.route_event(event_name, data, correlation_id)
        
        # Set the emitter on the transport
        if hasattr(transport, 'set_event_emitter'):
            transport.set_event_emitter(emit_event)
        elif hasattr(transport, 'event_emitter'):
            transport.event_emitter = emit_event
        else:
            # Try setting it as an attribute
            transport.emit_event = emit_event
    
    async def initialize_transports(self, config: Dict[str, Any]) -> None:
        """Initialize transport plugins."""
        transports_config = config.get("transports", {"unix": {"enabled": True}})
        
        for transport_type, transport_config in transports_config.items():
            if not transport_config.get("enabled", True):
                continue
            
            logger.info(f"Creating transport: {transport_type}")
            
            # Get transport instances from plugins
            transport_results = self.plugin_manager.hook.ksi_create_transport(
                transport_type=transport_type,
                config=transport_config
            )
            
            # Use the first valid transport
            for transport in transport_results:
                if transport:
                    self.transports[transport_type] = transport
                    
                    # Inject event emitter
                    self.inject_event_emitter(transport)
                    
                    # Start transport
                    if hasattr(transport, 'start'):
                        await transport.start()
                    
                    logger.info(f"Started transport: {transport_type}")
                    break
    
    async def shutdown(self) -> None:
        """Shutdown all transports and clean up."""
        # Stop transports
        for transport_type, transport in self.transports.items():
            if hasattr(transport, 'stop'):
                await transport.stop()
            logger.info(f"Stopped transport: {transport_type}")
        
        # Cancel pending requests
        for future in self.pending_requests.values():
            if not future.done():
                future.cancel()
        
        self.pending_requests.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics."""
        return {
            **self.stats,
            "pending_requests": len(self.pending_requests),
            "active_transports": len(self.transports),
            "loaded_plugins": len(self.plugin_loader.loaded_plugins)
        }