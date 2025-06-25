#!/usr/bin/env python3
"""
Minimal Test Plugin

Absolutely minimal plugin with no external dependencies.
"""

import pluggy

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Simple plugin info as dict
PLUGIN_INFO = {
    "name": "test_minimal",
    "version": "1.0.0",
    "description": "Minimal test plugin"
}


@hookimpl
def ksi_startup(config):
    """Called on startup."""
    print("Minimal test plugin: startup hook called!")
    return {"plugin.test_minimal": {"loaded": True}}


@hookimpl
def ksi_handle_event(event_name, data, context):
    """Handle test events."""
    if event_name == "test:ping":
        print(f"Minimal test plugin: got ping with data: {data}")
        return {"pong": True, "echo": data.get("message")}
    return None


@hookimpl
def ksi_shutdown():
    """Called on shutdown."""
    print("Minimal test plugin: shutdown hook called!")


# Module-level marker for plugin discovery
ksi_plugin = True