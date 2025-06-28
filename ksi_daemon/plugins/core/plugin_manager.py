#!/usr/bin/env python3
"""
Plugin Manager Service

Provides runtime plugin management including reloading.
"""

import logging
from typing import Dict, Any, Optional
import pluggy

from ...plugin_utils import get_logger, plugin_metadata

# Plugin metadata
plugin_metadata("plugin_manager", version="1.0.0",
                description="Runtime plugin management and reloading")

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Module state
logger = get_logger("plugin_manager")
plugin_loader = None  # Will be set during context

# Mark as reloadable - extra fields stored separately
PLUGIN_INFO = {
    "name": "plugin_manager",
    "version": "1.0.0", 
    "description": "Manages plugin lifecycle including hot reloading"
}

# Reload configuration (checked by get_plugin_metadata)
_reloadable = True
_reload_strategy = "stateless"


@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Handle plugin management events."""
    
    if event_name == "plugin:reload":
        return handle_reload(data)
    
    elif event_name == "plugin:list":
        return handle_list(data)
    
    elif event_name == "plugin:info":
        return handle_info(data)
    
    return None


def handle_reload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle plugin reload request."""
    if not plugin_loader:
        return {"error": "Plugin loader not available"}
    
    plugin_name = data.get("plugin_name")
    force = data.get("force", False)
    
    if not plugin_name:
        return {"error": "plugin_name required"}
    
    logger.info(f"Reloading plugin {plugin_name} (force={force})")
    
    result = plugin_loader.reload_plugin(plugin_name, force=force)
    
    if "error" in result:
        logger.error(f"Failed to reload {plugin_name}: {result['error']}")
    else:
        logger.info(f"Successfully reloaded {plugin_name}")
    
    return result


def handle_list(data: Dict[str, Any]) -> Dict[str, Any]:
    """List plugins with reload info."""
    if not plugin_loader:
        return {"error": "Plugin loader not available"}
    
    include_reload_info = data.get("reload_info", True)
    
    plugins = []
    for plugin_info in plugin_loader.list_plugins():
        plugin_data = {
            "name": plugin_info.name,
            "version": plugin_info.version,
            "description": plugin_info.description
        }
        
        if include_reload_info:
            metadata = plugin_loader.get_plugin_metadata(plugin_info.name)
            plugin_data["reloadable"] = metadata.get("reloadable", False)
            plugin_data["reload_strategy"] = metadata.get("reload_strategy", "unknown")
            if not plugin_data["reloadable"]:
                plugin_data["reload_reason"] = metadata.get("reason", "Not marked as reloadable")
        
        plugins.append(plugin_data)
    
    return {
        "plugins": plugins,
        "count": len(plugins)
    }


def handle_info(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get detailed plugin information."""
    if not plugin_loader:
        return {"error": "Plugin loader not available"}
    
    plugin_name = data.get("plugin_name")
    if not plugin_name:
        return {"error": "plugin_name required"}
    
    plugin_info = plugin_loader.get_plugin_info(plugin_name)
    if not plugin_info:
        return {"error": f"Plugin {plugin_name} not found"}
    
    # Get metadata including reload info
    metadata = plugin_loader.get_plugin_metadata(plugin_name)
    
    # Get implemented hooks
    all_hooks = plugin_loader.get_hooks()
    implemented_hooks = []
    for hook_name, implementers in all_hooks.items():
        if plugin_name in implementers:
            implemented_hooks.append(hook_name)
    
    return {
        "name": plugin_info.name,
        "version": plugin_info.version,
        "description": plugin_info.description,
        "author": plugin_info.author,
        "dependencies": plugin_info.dependencies,
        "namespaces": plugin_info.namespaces,
        "reloadable": metadata.get("reloadable", False),
        "reload_strategy": metadata.get("reload_strategy"),
        "reload_reason": metadata.get("reason"),
        "hooks": implemented_hooks
    }


@hookimpl
def ksi_plugin_context(context):
    """Receive plugin context."""
    global plugin_loader
    plugin_loader = context.get("plugin_loader")
    logger.info(f"Plugin manager received context, loader available: {plugin_loader is not None}")


# Module-level marker for plugin discovery
ksi_plugin = True