#!/usr/bin/env python3
"""
KSI Plugin-Based Core Daemon

Minimal event router that orchestrates plugins. All functionality is provided
by plugins - the core only handles plugin loading and event routing.

This replaces the monolithic core.py with a <500 line implementation.
"""

import asyncio
import json
import logging
import signal
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from .plugin_manager import PluginManager
from .event_bus import EventBus
from .config import config
from .logging_config import get_logger, log_event

logger = get_logger(__name__)


class PluginDaemon:
    """
    Minimal plugin-based daemon core.
    
    All functionality is provided by plugins:
    - Transport plugins handle connections (Unix sockets, SocketIO, etc)
    - Service plugins provide state management, completion, agents, etc
    - Event plugins handle specific event types
    """
    
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        """
        Initialize plugin daemon.
        
        Args:
            config_dict: Configuration dictionary
        """
        self.config = config_dict or self._load_config()
        self.shutdown_event = asyncio.Event()
        self.plugin_manager: Optional[PluginManager] = None
        self.event_bus: Optional[EventBus] = None
        self._shutdown_handlers = []
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from various sources."""
        # Start with defaults
        daemon_config = {
            "daemon": {
                "plugin_dirs": [],
                "max_event_history": 1000,
                "event_timeout": 30.0
            },
            "transports": {
                "unix": {
                    "enabled": True,
                    "socket_dir": str(config.socket_dir)
                },
                "socketio": {
                    "enabled": False,
                    "port": 8080
                }
            },
            "plugins": {}
        }
        
        # Load from config file if exists
        config_file = Path.home() / ".ksi" / "daemon.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    file_config = json.load(f)
                    daemon_config = self._merge_config(daemon_config, file_config)
            except Exception as e:
                logger.warning(f"Error loading config file: {e}")
        
        # Override with environment variables
        # KSI_PLUGIN_DIRS, KSI_TRANSPORT_UNIX_ENABLED, etc.
        
        return daemon_config
    
    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge configuration dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        
        return result
    
    async def initialize(self) -> None:
        """Initialize the daemon and all plugins."""
        logger.info("Initializing plugin daemon")
        
        # Create event bus
        self.event_bus = EventBus(
            max_history=self.config["daemon"].get("max_event_history", 1000)
        )
        
        # Create plugin manager
        plugin_dirs = [Path(d) for d in self.config["daemon"].get("plugin_dirs", [])]
        self.plugin_manager = PluginManager(self.config, plugin_dirs)
        
        # Wire up event bus to plugin manager
        await self._setup_event_routing()
        
        # Initialize plugins
        await self.plugin_manager.initialize()
        
        # Set up signal handlers
        self._setup_signals()
        
        logger.info("Plugin daemon initialized")
    
    async def _setup_event_routing(self) -> None:
        """Set up event routing between bus and plugin manager."""
        # Plugin manager emits events through the bus
        async def emit_via_bus(event_name: str, data: Dict[str, Any], **kwargs) -> Any:
            return await self.event_bus.emit(
                event_name=event_name,
                data=data,
                source=kwargs.get("source", "plugin_manager"),
                correlation_id=kwargs.get("correlation_id"),
                expect_response=kwargs.get("expect_response", False)
            )
        
        # Subscribe plugin manager to all events
        def route_to_plugins(event_name: str, data: Dict[str, Any], metadata: Any) -> Any:
            # Create event dict for plugin system
            event = {
                "name": event_name,
                "data": data,
                "source": metadata.source if hasattr(metadata, 'source') else "unknown",
                "correlation_id": metadata.correlation_id if hasattr(metadata, 'correlation_id') else None
            }
            
            # Route through plugin system synchronously (plugin manager handles async)
            future = asyncio.ensure_future(self.plugin_manager.emit_event(event))
            return future
        
        # Subscribe to all events
        self.event_bus.subscribe(
            subscriber="plugin_manager",
            patterns=["*"],  # All events
            handler=route_to_plugins
        )
    
    def _setup_signals(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}")
            self.shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def run(self) -> None:
        """Run the daemon until shutdown."""
        logger.info("Plugin daemon starting")
        
        try:
            # Emit startup event
            await self.event_bus.emit("system:startup", {
                "config": self.config,
                "plugins": list(self.plugin_manager.plugin_loader.loaded_plugins.keys())
            })
            
            # Wait for shutdown
            await self.shutdown_event.wait()
            
            logger.info("Shutdown initiated")
            
        except Exception as e:
            logger.error(f"Daemon error: {e}", exc_info=True)
            raise
        
        finally:
            await self.shutdown()
    
    async def shutdown(self) -> None:
        """Shutdown the daemon and all plugins."""
        logger.info("Shutting down plugin daemon")
        
        try:
            # Emit shutdown event
            await self.event_bus.emit("system:shutdown", {
                "reason": "manual",
                "save_state": True
            })
            
            # Give plugins time to clean up
            await asyncio.sleep(1.0)
            
            # Shutdown plugin manager
            if self.plugin_manager:
                await self.plugin_manager.shutdown()
            
            # Run custom shutdown handlers
            for handler in self._shutdown_handlers:
                try:
                    await handler()
                except Exception as e:
                    logger.error(f"Shutdown handler error: {e}")
            
            logger.info("Plugin daemon shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
    
    def add_shutdown_handler(self, handler) -> None:
        """Add a custom shutdown handler."""
        self._shutdown_handlers.append(handler)
    
    async def emit_event(self, event_name: str, data: Dict[str, Any], **kwargs) -> Any:
        """
        Emit an event through the daemon.
        
        Args:
            event_name: Event name
            data: Event data
            **kwargs: Additional options (correlation_id, expect_response, etc)
            
        Returns:
            Response if expect_response=True
        """
        if not self.event_bus:
            raise RuntimeError("Daemon not initialized")
        
        return await self.event_bus.emit(
            event_name=event_name,
            data=data,
            source=kwargs.get("source", "daemon"),
            correlation_id=kwargs.get("correlation_id"),
            expect_response=kwargs.get("expect_response", False)
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get daemon statistics."""
        stats = {
            "daemon": "plugin-based",
            "version": "2.0.0",
            "status": "running" if not self.shutdown_event.is_set() else "shutting_down"
        }
        
        if self.event_bus:
            stats["event_bus"] = self.event_bus.get_stats()
        
        if self.plugin_manager:
            stats["plugin_manager"] = self.plugin_manager.get_stats()
        
        return stats


# =============================================================================
# Entry Point Functions
# =============================================================================

async def run_daemon(config_dict: Optional[Dict[str, Any]] = None) -> None:
    """
    Run the plugin daemon.
    
    Args:
        config_dict: Optional configuration
    """
    daemon = PluginDaemon(config_dict)
    
    try:
        await daemon.initialize()
        await daemon.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Daemon failed: {e}", exc_info=True)
        sys.exit(1)


def main():
    """Main entry point for the daemon."""
    import argparse
    
    parser = argparse.ArgumentParser(description="KSI Plugin Daemon")
    parser.add_argument("--config", "-c", help="Configuration file path")
    parser.add_argument("--plugin-dir", "-p", action="append", 
                       help="Additional plugin directory (can be specified multiple times)")
    parser.add_argument("--debug", "-d", action="store_true", 
                       help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Set up logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load config
    config_dict = None
    if args.config:
        try:
            with open(args.config) as f:
                config_dict = json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            sys.exit(1)
    
    # Add plugin directories
    if args.plugin_dir:
        if not config_dict:
            config_dict = {"daemon": {}}
        if "plugin_dirs" not in config_dict["daemon"]:
            config_dict["daemon"]["plugin_dirs"] = []
        config_dict["daemon"]["plugin_dirs"].extend(args.plugin_dir)
    
    # Run daemon
    asyncio.run(run_daemon(config_dict))


if __name__ == "__main__":
    main()