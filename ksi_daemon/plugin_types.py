#!/usr/bin/env python3
"""
Plugin System Type Definitions

Common types and interfaces used by the plugin system.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable, TYPE_CHECKING
import asyncio
from dataclasses import dataclass
from enum import Enum

if TYPE_CHECKING:
    from .plugin_manager import PluginManager


class EventContext:
    """
    Context object passed to event handlers.
    Provides methods to emit events, access config, and interact with the system.
    """
    
    def __init__(self, plugin_manager: "PluginManager", source_plugin: str):
        self._plugin_manager = plugin_manager
        self._source_plugin = source_plugin
        self._emitted_events: List[Dict[str, Any]] = []
    
    async def emit(self, event_name: str, data: Dict[str, Any], 
                   correlation_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Emit a new event.
        
        Args:
            event_name: Namespaced event name
            data: Event data
            correlation_id: Optional ID to correlate request/response
            
        Returns:
            Response if this is a request/response pattern
        """
        event = {
            "name": event_name,
            "data": data,
            "source": self._source_plugin,
            "correlation_id": correlation_id
        }
        self._emitted_events.append(event)
        return await self._plugin_manager.emit_event(event)
    
    async def subscribe(self, event_patterns: List[str], 
                       handler: Callable[[str, Dict[str, Any]], None]) -> str:
        """
        Subscribe to event patterns.
        
        Args:
            event_patterns: List of event name patterns (supports wildcards)
            handler: Async callback function
            
        Returns:
            Subscription ID
        """
        return await self._plugin_manager.subscribe(
            self._source_plugin, event_patterns, handler
        )
    
    async def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from events."""
        await self._plugin_manager.unsubscribe(subscription_id)
    
    @property
    def config(self) -> Dict[str, Any]:
        """Get plugin configuration."""
        return self._plugin_manager.get_plugin_config(self._source_plugin)
    
    @property
    def emitted_events(self) -> List[Dict[str, Any]]:
        """Get list of events emitted in this context."""
        return self._emitted_events.copy()


class TransportStatus(Enum):
    """Transport connection status."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class TransportConnection(ABC):
    """
    Abstract base class for transport connections.
    All transport plugins must implement this interface.
    """
    
    @abstractmethod
    async def start(self) -> None:
        """Start accepting connections."""
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop accepting connections and clean up."""
    
    @abstractmethod
    async def send_event(self, connection_id: str, event: Dict[str, Any]) -> None:
        """
        Send event to specific connection.
        
        Args:
            connection_id: Unique connection identifier
            event: Event data to send
        """
    
    @abstractmethod
    async def broadcast_event(self, event: Dict[str, Any], room: Optional[str] = None) -> None:
        """
        Broadcast event to multiple connections.
        
        Args:
            event: Event data to broadcast
            room: Optional room/channel to broadcast to
        """
    
    @abstractmethod
    def get_connections(self) -> List[str]:
        """Get list of active connection IDs."""
    
    @abstractmethod
    def get_status(self) -> TransportStatus:
        """Get current transport status."""


@dataclass
class PluginInfo:
    """Information about a loaded plugin."""
    name: str
    version: str
    description: str
    author: Optional[str] = None
    namespaces: List[str] = None
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.namespaces is None:
            self.namespaces = []
        if self.dependencies is None:
            self.dependencies = []


class KSIPlugin(ABC):
    """
    Base class for KSI plugins.
    Plugins can inherit from this for better type hints and structure.
    """
    
    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """Plugin metadata."""
    
    async def initialize(self, context: EventContext) -> None:
        """
        Initialize plugin.
        Called after all plugins are loaded.
        
        Args:
            context: Plugin event context
        """
        pass
    
    async def cleanup(self) -> None:
        """
        Clean up plugin resources.
        Called during shutdown.
        """
        pass


@dataclass
class EventSubscription:
    """Represents an event subscription."""
    id: str
    plugin_name: str
    patterns: List[str]
    handler: Callable[[str, Dict[str, Any]], None]
    created_at: float


@dataclass
class EventMetadata:
    """Metadata for events."""
    id: str
    name: str
    source: str
    timestamp: float
    correlation_id: Optional[str] = None
    parent_id: Optional[str] = None


class ServiceProvider(ABC):
    """Base class for service provider plugins."""
    
    @property
    @abstractmethod
    def service_name(self) -> str:
        """Name of the service provided."""
    
    @abstractmethod
    async def start(self) -> None:
        """Start the service."""
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the service."""
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get service status."""