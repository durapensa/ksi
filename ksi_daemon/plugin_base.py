#!/usr/bin/env python3
"""
Base classes and utilities for KSI plugin development.

Provides convenient base classes that handle common plugin patterns.
"""

import logging
from typing import Dict, Any, Optional, List, Set
import pluggy

from .plugin_types import KSIPlugin, PluginInfo, EventContext, ServiceProvider
from .hookspecs import hookspec

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")


class BasePlugin(KSIPlugin):
    """
    Base class for KSI plugins with common functionality.
    """
    
    def __init__(self, name: str, version: str = "1.0.0", 
                 description: str = "", **kwargs):
        """
        Initialize base plugin.
        
        Args:
            name: Plugin name
            version: Plugin version
            description: Plugin description
            **kwargs: Additional plugin info fields
        """
        self._info = PluginInfo(
            name=name,
            version=version,
            description=description,
            **kwargs
        )
        self.logger = logging.getLogger(f"ksi.plugin.{name}")
        self._context: Optional[EventContext] = None
        self._config: Dict[str, Any] = {}
    
    @property
    def info(self) -> PluginInfo:
        """Plugin metadata."""
        return self._info
    
    async def initialize(self, context: EventContext) -> None:
        """Initialize plugin with context."""
        self._context = context
        self._config = context.config
        await self.on_initialize()
    
    async def on_initialize(self) -> None:
        """Override this method to perform initialization."""
        pass
    
    async def cleanup(self) -> None:
        """Clean up plugin resources."""
        await self.on_cleanup()
    
    async def on_cleanup(self) -> None:
        """Override this method to perform cleanup."""
        pass
    
    async def emit(self, event_name: str, data: Dict[str, Any], 
                   correlation_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Emit an event.
        
        Args:
            event_name: Event name
            data: Event data
            correlation_id: Optional correlation ID
            
        Returns:
            Response if applicable
        """
        if not self._context:
            raise RuntimeError("Plugin not initialized")
        return await self._context.emit(event_name, data, correlation_id)
    
    async def subscribe(self, patterns: List[str], handler) -> str:
        """
        Subscribe to event patterns.
        
        Args:
            patterns: Event patterns to subscribe to
            handler: Event handler function
            
        Returns:
            Subscription ID
        """
        if not self._context:
            raise RuntimeError("Plugin not initialized")
        return await self._context.subscribe(patterns, handler)


class EventHandlerPlugin(BasePlugin):
    """
    Base class for plugins that handle specific events.
    """
    
    def __init__(self, name: str, handled_events: List[str], **kwargs):
        """
        Initialize event handler plugin.
        
        Args:
            name: Plugin name
            handled_events: List of event patterns this plugin handles
            **kwargs: Additional plugin info
        """
        super().__init__(name, **kwargs)
        self.handled_events = handled_events
        # Extract namespaces from events
        namespaces = set()
        for event in handled_events:
            if ":" in event:
                namespaces.add(event.split(":", 1)[0])
        self._info.namespaces = list(namespaces)
    
    @hookimpl
    def ksi_handle_event(self, event_name: str, data: Dict[str, Any], 
                        context: EventContext) -> Optional[Dict[str, Any]]:
        """Handle events matching our patterns."""
        # Check if we handle this event
        for pattern in self.handled_events:
            if self._matches_pattern(event_name, pattern):
                return self.handle_event(event_name, data, context)
        return None
    
    def handle_event(self, event_name: str, data: Dict[str, Any], 
                    context: EventContext) -> Optional[Dict[str, Any]]:
        """
        Override this method to handle events.
        
        Args:
            event_name: Name of the event
            data: Event data
            context: Event context
            
        Returns:
            Response data or None
        """
        raise NotImplementedError("Subclasses must implement handle_event")
    
    def _matches_pattern(self, event_name: str, pattern: str) -> bool:
        """Check if event name matches pattern."""
        if "*" not in pattern:
            return event_name == pattern
        
        import re
        regex = pattern.replace("*", ".*")
        return bool(re.match(f"^{regex}$", event_name))


class ServicePlugin(BasePlugin, ServiceProvider):
    """
    Base class for plugins that provide services.
    """
    
    def __init__(self, name: str, service_name: str, **kwargs):
        """
        Initialize service plugin.
        
        Args:
            name: Plugin name
            service_name: Name of the service provided
            **kwargs: Additional plugin info
        """
        super().__init__(name, **kwargs)
        self._service_name = service_name
        self._running = False
    
    @property
    def service_name(self) -> str:
        """Name of the service provided."""
        return self._service_name
    
    @hookimpl
    def ksi_provide_service(self, service_name: str) -> Optional[ServiceProvider]:
        """Provide service if requested."""
        if service_name == self._service_name or service_name is None:
            return self
        return None
    
    async def start(self) -> None:
        """Start the service."""
        if self._running:
            return
        await self.on_start()
        self._running = True
        self.logger.info(f"Service {self._service_name} started")
    
    async def stop(self) -> None:
        """Stop the service."""
        if not self._running:
            return
        await self.on_stop()
        self._running = False
        self.logger.info(f"Service {self._service_name} stopped")
    
    async def on_start(self) -> None:
        """Override this method to perform service startup."""
        pass
    
    async def on_stop(self) -> None:
        """Override this method to perform service shutdown."""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status."""
        return {
            "name": self._service_name,
            "running": self._running,
            **self.get_service_status()
        }
    
    def get_service_status(self) -> Dict[str, Any]:
        """Override this method to provide additional status info."""
        return {}


class TransportPlugin(BasePlugin):
    """
    Base class for transport plugins.
    """
    
    def __init__(self, name: str, transport_type: str, **kwargs):
        """
        Initialize transport plugin.
        
        Args:
            name: Plugin name
            transport_type: Type of transport (e.g., "unix", "socketio")
            **kwargs: Additional plugin info
        """
        super().__init__(name, **kwargs)
        self.transport_type = transport_type
    
    @hookimpl
    def ksi_create_transport(self, transport_type: str, 
                           config: Dict[str, Any]) -> Optional[Any]:
        """Create transport if type matches."""
        if transport_type == self.transport_type:
            return self.create_transport(config)
        return None
    
    def create_transport(self, config: Dict[str, Any]) -> Any:
        """
        Override this method to create transport instance.
        
        Args:
            config: Transport configuration
            
        Returns:
            Transport instance
        """
        raise NotImplementedError("Subclasses must implement create_transport")


