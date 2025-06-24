#!/usr/bin/env python3
"""
Plugin Manager for KSI Daemon

Central orchestrator for all plugins. Handles event routing, service discovery,
and plugin lifecycle management.
"""

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from collections import defaultdict

from .plugin_loader import PluginLoader
from .plugin_types import EventContext, EventMetadata, EventSubscription, TransportConnection
from .logging_config import get_logger, log_event

logger = get_logger(__name__)


class PluginManager:
    """
    Central manager for KSI plugin system.
    Coordinates plugin loading, event routing, and service discovery.
    """
    
    def __init__(self, config: Dict[str, Any], plugin_dirs: Optional[List[Path]] = None):
        """
        Initialize plugin manager.
        
        Args:
            config: Daemon configuration
            plugin_dirs: Additional plugin directories
        """
        self.config = config
        self.plugin_loader = PluginLoader(plugin_dirs)
        
        # Event routing
        self.event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.event_subscriptions: Dict[str, EventSubscription] = {}
        self.pattern_subscriptions: List[Tuple[str, EventSubscription]] = []
        
        # Service registry
        self.services: Dict[str, Any] = {}
        
        # Transport registry
        self.transports: Dict[str, TransportConnection] = {}
        
        # Event history for debugging
        self.event_history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        # Plugin configurations
        self.plugin_configs: Dict[str, Dict[str, Any]] = {}
        
        # Event correlation tracking
        self.pending_correlations: Dict[str, asyncio.Future] = {}
        
        # Stats
        self.stats = {
            "events_processed": 0,
            "events_failed": 0,
            "subscriptions_active": 0
        }
    
    async def initialize(self) -> None:
        """Initialize the plugin system."""
        logger.info("Initializing plugin manager")
        
        # Load all plugins
        loaded = self.plugin_loader.load_all_plugins()
        logger.info(f"Loaded {len(loaded)} plugins: {loaded}")
        
        # Call startup hooks
        startup_configs = self.plugin_loader.pm.hook.ksi_startup(config=self.config)
        for plugin_config in startup_configs:
            if plugin_config:
                # Merge plugin configs
                for key, value in plugin_config.items():
                    if key.startswith("plugin."):
                        plugin_name = key.split(".", 1)[1]
                        self.plugin_configs[plugin_name] = value
        
        # Initialize services
        await self._initialize_services()
        
        # Initialize transports
        await self._initialize_transports()
        
        # Call ready hooks
        self.plugin_loader.pm.hook.ksi_ready()
        
        logger.info("Plugin manager initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the plugin system."""
        logger.info("Shutting down plugin manager")
        
        # Call shutdown hooks
        self.plugin_loader.pm.hook.ksi_shutdown()
        
        # Stop transports
        for transport_name, transport in self.transports.items():
            try:
                await transport.stop()
                logger.info(f"Stopped transport: {transport_name}")
            except Exception as e:
                logger.error(f"Error stopping transport {transport_name}: {e}")
        
        # Clean up pending correlations
        for future in self.pending_correlations.values():
            if not future.done():
                future.cancel()
        
        logger.info("Plugin manager shutdown complete")
    
    async def _initialize_services(self) -> None:
        """Initialize plugin services."""
        # Get service providers from plugins
        for plugin_name, plugin_info in self.plugin_loader.loaded_plugins.items():
            try:
                # Get services from hooks
                services = self.plugin_loader.pm.hook.ksi_provide_service(
                    service_name=None  # Get all services
                )
                for service in services:
                    if service:
                        service_name = getattr(service, "service_name", None)
                        if service_name:
                            self.services[service_name] = service
                            logger.info(f"Registered service: {service_name} from {plugin_name}")
            except Exception as e:
                logger.error(f"Error initializing services from {plugin_name}: {e}")
    
    async def _initialize_transports(self) -> None:
        """Initialize transport plugins."""
        # Get transport configuration
        transport_config = self.config.get("transports", {
            "unix": {"enabled": True},
            "socketio": {"enabled": False}
        })
        
        logger.info(f"Initializing transports with config: {transport_config}")
        
        for transport_type, config in transport_config.items():
            if not config.get("enabled", False):
                logger.info(f"Transport {transport_type} is disabled")
                continue
            
            logger.info(f"Creating transport: {transport_type}")
            
            # Try to create transport via hooks
            transports = self.plugin_loader.pm.hook.ksi_create_transport(
                transport_type=transport_type,
                config=config
            )
            
            # Filter out None returns
            valid_transports = [t for t in transports if t is not None]
            logger.info(f"Got {len(valid_transports)} transport instances for {transport_type}")
            
            for transport in valid_transports:
                try:
                    # Set event emitter on transport if it supports it
                    if hasattr(transport, 'emit_event'):
                        # Create event emitter that routes through our event system
                        async def transport_emit_event(event_name: str, data: Dict[str, Any], **kwargs):
                            # Route through the plugin event system
                            event = {
                                "name": event_name,
                                "data": data,
                                "source": kwargs.get("source", "transport"),
                                "correlation_id": kwargs.get("correlation_id")
                            }
                            result = await self.emit_event(event)
                            return result if result else {"status": "success"}
                        
                        transport.emit_event = transport_emit_event
                        logger.info(f"Injected event emitter into transport: {transport_type}")
                    
                    await transport.start()
                    self.transports[transport_type] = transport
                    logger.info(f"Started transport: {transport_type}")
                    break
                except Exception as e:
                    logger.error(f"Error starting transport {transport_type}: {e}")
    
    async def emit_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Emit an event through the plugin system.
        
        Args:
            event: Event dictionary with name, data, source, etc.
            
        Returns:
            Response for request/response patterns
        """
        # Create event metadata
        event_meta = EventMetadata(
            id=event.get("id", str(uuid.uuid4())),
            name=event["name"],
            source=event.get("source", "unknown"),
            timestamp=time.time(),
            correlation_id=event.get("correlation_id"),
            parent_id=event.get("parent_id")
        )
        
        # Add to history
        self._add_to_history(event, event_meta)
        
        # Extract namespace
        namespace = event["name"].split(":", 1)[0] if ":" in event["name"] else None
        
        # Create event context
        context = EventContext(self, event.get("source", "unknown"))
        
        try:
            # Pre-event hooks
            pre_results = self.plugin_loader.pm.hook.ksi_pre_event(
                event_name=event["name"],
                data=event.get("data", {}),
                context=context
            )
            
            # Check if any pre-hook cancelled the event
            event_data = event.get("data", {})
            for result in pre_results:
                if result is None:
                    logger.info(f"Event {event['name']} cancelled by pre-hook")
                    return None
                elif isinstance(result, dict):
                    event_data = result
            
            # Main event handling
            result = None
            handled = False
            
            # Try hooks first
            hook_results = self.plugin_loader.pm.hook.ksi_handle_event(
                event_name=event["name"],
                data=event_data,
                context=context
            )
            
            if hook_results:
                result = hook_results
                handled = True
            
            # Try subscriptions
            if not handled:
                result = await self._route_to_subscriptions(event["name"], event_data, event_meta)
                if result:
                    handled = True
            
            # Post-event hooks
            post_results = self.plugin_loader.pm.hook.ksi_post_event(
                event_name=event["name"],
                result=result,
                context=context
            )
            
            for post_result in post_results:
                if post_result is not None:
                    result = post_result
            
            self.stats["events_processed"] += 1
            
            # Handle correlation if this is a response
            if event_meta.correlation_id and event["name"].endswith(":response"):
                await self._handle_correlation_response(event_meta.correlation_id, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing event {event['name']}: {e}", exc_info=True)
            self.stats["events_failed"] += 1
            
            # Error hooks
            error_results = self.plugin_loader.pm.hook.ksi_event_error(
                event_name=event["name"],
                error=e,
                context=context
            )
            
            for error_result in error_results:
                if error_result:
                    return error_result
            
            # Default error response
            return {
                "error": str(e),
                "event": event["name"]
            }
    
    async def _route_to_subscriptions(self, event_name: str, data: Dict[str, Any], 
                                     meta: EventMetadata) -> Optional[Dict[str, Any]]:
        """Route event to matching subscriptions."""
        results = []
        
        # Check exact matches
        for subscription in self.event_subscriptions.values():
            if event_name in subscription.patterns:
                try:
                    result = await subscription.handler(event_name, data)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Subscription handler error: {e}")
        
        # Check pattern matches
        for pattern, subscription in self.pattern_subscriptions:
            if self._matches_pattern(event_name, pattern):
                try:
                    result = await subscription.handler(event_name, data)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Pattern subscription handler error: {e}")
        
        # Return first result or None
        return results[0] if results else None
    
    def _matches_pattern(self, event_name: str, pattern: str) -> bool:
        """Check if event name matches pattern (supports wildcards)."""
        if "*" not in pattern:
            return event_name == pattern
        
        # Convert pattern to regex
        import re
        regex = pattern.replace("*", ".*")
        return bool(re.match(f"^{regex}$", event_name))
    
    async def subscribe(self, plugin_name: str, patterns: List[str], 
                       handler: Callable) -> str:
        """
        Subscribe to event patterns.
        
        Args:
            plugin_name: Name of subscribing plugin
            patterns: List of event patterns
            handler: Async handler function
            
        Returns:
            Subscription ID
        """
        sub_id = f"sub_{uuid.uuid4().hex[:8]}"
        
        subscription = EventSubscription(
            id=sub_id,
            plugin_name=plugin_name,
            patterns=patterns,
            handler=handler,
            created_at=time.time()
        )
        
        self.event_subscriptions[sub_id] = subscription
        
        # Add pattern subscriptions
        for pattern in patterns:
            if "*" in pattern:
                self.pattern_subscriptions.append((pattern, subscription))
        
        self.stats["subscriptions_active"] = len(self.event_subscriptions)
        
        logger.info(f"Plugin {plugin_name} subscribed to {patterns} (ID: {sub_id})")
        return sub_id
    
    async def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from events."""
        if subscription_id in self.event_subscriptions:
            subscription = self.event_subscriptions[subscription_id]
            del self.event_subscriptions[subscription_id]
            
            # Remove pattern subscriptions
            self.pattern_subscriptions = [
                (p, s) for p, s in self.pattern_subscriptions
                if s.id != subscription_id
            ]
            
            self.stats["subscriptions_active"] = len(self.event_subscriptions)
            
            logger.info(f"Unsubscribed {subscription_id}")
    
    async def emit_and_wait(self, event_name: str, data: Dict[str, Any], 
                           timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """
        Emit event and wait for correlated response.
        
        Args:
            event_name: Event name
            data: Event data
            timeout: Response timeout in seconds
            
        Returns:
            Response data or None if timeout
        """
        correlation_id = str(uuid.uuid4())
        future = asyncio.Future()
        self.pending_correlations[correlation_id] = future
        
        try:
            # Emit request
            await self.emit_event({
                "name": event_name,
                "data": data,
                "correlation_id": correlation_id
            })
            
            # Wait for response
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
            
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for response to {event_name}")
            return None
        finally:
            # Clean up
            self.pending_correlations.pop(correlation_id, None)
    
    async def _handle_correlation_response(self, correlation_id: str, 
                                         response: Dict[str, Any]) -> None:
        """Handle correlated response."""
        future = self.pending_correlations.get(correlation_id)
        if future and not future.done():
            future.set_result(response)
    
    def get_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """Get configuration for a plugin."""
        return self.plugin_configs.get(plugin_name, {})
    
    def get_service(self, service_name: str) -> Optional[Any]:
        """Get a registered service."""
        return self.services.get(service_name)
    
    def _add_to_history(self, event: Dict[str, Any], meta: EventMetadata) -> None:
        """Add event to history."""
        history_entry = {
            "event": event,
            "metadata": {
                "id": meta.id,
                "timestamp": meta.timestamp,
                "correlation_id": meta.correlation_id
            }
        }
        
        self.event_history.append(history_entry)
        
        # Trim history
        if len(self.event_history) > self.max_history:
            self.event_history = self.event_history[-self.max_history:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get plugin system statistics."""
        return {
            **self.stats,
            "plugins_loaded": len(self.plugin_loader.loaded_plugins),
            "services_registered": len(self.services),
            "transports_active": len(self.transports),
            "history_size": len(self.event_history),
            "hooks_registered": len(self.plugin_loader.get_hooks())
        }