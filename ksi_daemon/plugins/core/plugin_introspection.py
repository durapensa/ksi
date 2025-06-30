#!/usr/bin/env python3
"""
Plugin Introspection Service

Provides read-only introspection of the plugin system.
Follows pluggy best practices - no lifecycle management, just inspection.
"""

import pluggy
from typing import Dict, Any, List

from ksi_daemon.plugin_utils import plugin_metadata
from ksi_common.logging import get_bound_logger

# Plugin metadata
plugin_metadata("plugin_introspection", version="1.0.0",
                description="Read-only plugin system introspection")

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Module state
logger = get_bound_logger("plugin_introspection", version="1.0.0")
plugin_manager = None  # The pluggy PluginManager instance

# Plugin marker
ksi_plugin = True


@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Handle introspection events."""
    
    if event_name == "plugin:list":
        return list_plugins()
    
    elif event_name == "plugin:hooks":
        return list_hooks()
    
    elif event_name == "plugin:inspect":
        return inspect_plugin(data)
    
    return None


def list_plugins() -> Dict[str, Any]:
    """List all registered plugins."""
    if not plugin_manager:
        return {"error": "Plugin manager not available"}
    
    plugins = []
    for name, plugin_obj in plugin_manager.list_name_plugin():
        plugins.append({
            "name": name,
            "type": type(plugin_obj).__name__,
            "module": getattr(plugin_obj, "__module__", "unknown")
        })
    
    return {
        "plugins": plugins,
        "count": len(plugins)
    }


def list_hooks() -> Dict[str, Any]:
    """List all available hooks and their implementations."""
    if not plugin_manager:
        return {"error": "Plugin manager not available"}
    
    hooks = {}
    
    # Iterate through all hooks
    for attr_name in dir(plugin_manager.hook):
        if attr_name.startswith("ksi_"):
            hook = getattr(plugin_manager.hook, attr_name)
            
            # Get implementations
            impls = []
            for impl in hook.get_hookimpls():
                impls.append({
                    "plugin": impl.plugin_name,
                    "function": impl.function.__name__,
                    "tryfirst": impl.tryfirst,
                    "trylast": impl.trylast,
                    "wrapper": impl.hookwrapper
                })
            
            if impls:  # Only include hooks that have implementations
                hooks[attr_name] = {
                    "implementations": impls,
                    "count": len(impls)
                }
    
    return {
        "hooks": hooks,
        "total_hooks": len(hooks)
    }


def inspect_plugin(data: Dict[str, Any]) -> Dict[str, Any]:
    """Inspect a specific plugin."""
    if not plugin_manager:
        return {"error": "Plugin manager not available"}
    
    plugin_name = data.get("plugin_name")
    if not plugin_name:
        return {"error": "plugin_name required"}
    
    # Find the plugin
    plugin_obj = None
    for name, obj in plugin_manager.list_name_plugin():
        if name == plugin_name:
            plugin_obj = obj
            break
    
    if not plugin_obj:
        return {"error": f"Plugin '{plugin_name}' not found"}
    
    # Get implemented hooks
    implemented_hooks = []
    for attr_name in dir(plugin_manager.hook):
        if attr_name.startswith("ksi_"):
            hook = getattr(plugin_manager.hook, attr_name)
            for impl in hook.get_hookimpls():
                if impl.plugin_name == plugin_name:
                    implemented_hooks.append({
                        "name": attr_name,
                        "function": impl.function.__name__,
                        "tryfirst": impl.tryfirst,
                        "trylast": impl.trylast
                    })
    
    # Basic plugin info
    info = {
        "name": plugin_name,
        "type": type(plugin_obj).__name__,
        "module": getattr(plugin_obj, "__module__", "unknown"),
        "hooks": implemented_hooks,
        "hook_count": len(implemented_hooks)
    }
    
    # Add docstring if available
    if hasattr(plugin_obj, "__doc__") and plugin_obj.__doc__:
        info["description"] = plugin_obj.__doc__.strip()
    
    # Check for common attributes (but don't require them)
    if hasattr(plugin_obj, "PLUGIN_INFO"):
        info["plugin_info"] = plugin_obj.PLUGIN_INFO
    
    return info


@hookimpl
def ksi_plugin_context(context: Dict[str, Any]):
    """Receive plugin context to get access to plugin manager."""
    global plugin_manager
    
    # Get the plugin manager from the loader
    plugin_loader = context.get("plugin_loader")
    if plugin_loader:
        plugin_manager = plugin_loader.pm
        logger.info(f"Plugin introspection ready, found {len(list(plugin_manager.list_name_plugin()))} plugins")