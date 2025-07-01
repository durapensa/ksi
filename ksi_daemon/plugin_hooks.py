"""
KSI Plugin Hook Specifications

Defines the contract between plugins and the daemon.
"""

import pluggy
from typing import Dict, Any, List, Optional

# Define the hook specification namespace
hookspec = pluggy.HookspecMarker("ksi")


@hookspec
def ksi_startup(config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Called when daemon starts up."""
    pass


@hookspec
def ksi_shutdown() -> None:
    """Called when daemon shuts down."""
    pass


@hookspec
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle an event."""
    pass


@hookspec
def ksi_plugin_loaded(plugin_name: str, plugin_instance: Any) -> None:
    """Called when a plugin is loaded."""
    pass


@hookspec
def ksi_create_transport(transport_type: str, config: Dict[str, Any]) -> Optional[Any]:
    """Create a transport instance."""
    pass


@hookspec
def ksi_ready() -> Optional[Dict[str, Any]]:
    """Called when daemon is ready to accept connections."""
    pass


@hookspec
def ksi_describe_events() -> Optional[Dict[str, List[Dict[str, Any]]]]:
    """
    Describe events handled by this plugin.
    
    Returns:
        Dictionary mapping namespace to list of event descriptions.
        Each event description should include:
        - event: Full event name (e.g., "permission:list_profiles")
        - summary: Brief description
        - parameters: Dictionary of parameter definitions
        - examples: Optional list of example usage
    
    Example:
        {
            "permission": [
                {
                    "event": "permission:list_profiles",
                    "summary": "List available permission profiles",
                    "parameters": {}
                },
                {
                    "event": "permission:get_profile",
                    "summary": "Get details of a specific permission profile",
                    "parameters": {
                        "level": {
                            "type": "str",
                            "required": True,
                            "description": "The permission level name"
                        }
                    }
                }
            ]
        }
    """
    pass