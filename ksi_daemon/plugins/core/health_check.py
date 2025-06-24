#!/usr/bin/env python3
"""
Health Check Plugin

Provides system health check functionality for the KSI daemon.
Handles system:health events and returns daemon status.
"""

import time
from typing import Dict, Any, Optional

# Try absolute import first, fall back to relative
try:
    from ksi_daemon.plugin_base import EventHandlerPlugin, hookimpl
    from ksi_daemon.plugin_types import EventContext
except ImportError:
    # For when plugin is loaded as a module
    import sys
    from pathlib import Path
    # Add ksi_daemon to path
    daemon_path = Path(__file__).parent.parent.parent.parent
    if str(daemon_path) not in sys.path:
        sys.path.insert(0, str(daemon_path))
    
    from ksi_daemon.plugin_base import EventHandlerPlugin, hookimpl
    from ksi_daemon.plugin_types import EventContext


class HealthCheckPlugin(EventHandlerPlugin):
    """Plugin that provides health check functionality."""
    
    def __init__(self):
        super().__init__(
            name="health_check",
            handled_events=["system:health"],
            version="1.0.0",
            description="System health check provider"
        )
        self.start_time = time.time()
    
    def handle_event(self, event_name: str, data: Dict[str, Any], 
                    context: EventContext) -> Optional[Dict[str, Any]]:
        """Handle health check requests."""
        if event_name != "system:health":
            return None
        
        # Get plugin manager stats
        stats = {}
        if hasattr(context, '_plugin_manager'):
            stats = context._plugin_manager.get_stats()
        
        # Build health response
        uptime = time.time() - self.start_time
        
        response = {
            "status": "healthy",
            "uptime": uptime,
            "uptime_human": self._format_uptime(uptime),
            "daemon": {
                "type": "plugin-based",
                "version": "2.0.0"
            }
        }
        
        # Add plugin info if requested
        if data.get("include_plugins", True):
            response["plugins"] = self._get_plugin_health(context)
        
        # Add service info if requested
        if data.get("include_services", True):
            response["services"] = self._get_service_health(context)
        
        # Add stats
        response["stats"] = stats
        
        return response
    
    def _format_uptime(self, seconds: float) -> str:
        """Format uptime in human-readable format."""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")
        
        return " ".join(parts)
    
    def _get_plugin_health(self, context: EventContext) -> Dict[str, Any]:
        """Get health information for all plugins."""
        plugin_info = {}
        
        # Get plugin manager if available
        if hasattr(context, '_plugin_manager') and context._plugin_manager:
            pm = context._plugin_manager
            
            for plugin_name, info in pm.plugin_loader.loaded_plugins.items():
                plugin_info[plugin_name] = {
                    "version": info.version,
                    "status": "active",
                    "namespaces": info.namespaces
                }
        
        return plugin_info
    
    def _get_service_health(self, context: EventContext) -> Dict[str, Any]:
        """Get health information for all services."""
        service_info = {}
        
        # Get services from plugin manager
        if hasattr(context, '_plugin_manager') and context._plugin_manager:
            pm = context._plugin_manager
            
            for service_name, service in pm.services.items():
                if hasattr(service, 'get_status'):
                    service_info[service_name] = service.get_status()
                else:
                    service_info[service_name] = {"status": "active"}
        
        return service_info
    
    @hookimpl
    def ksi_register_commands(self) -> Dict[str, str]:
        """Register legacy command mapping."""
        return {
            "HEALTH_CHECK": "system:health"
        }


# Plugin instance
plugin = HealthCheckPlugin()