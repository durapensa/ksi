#!/usr/bin/env python3
"""
Message Bus Plugin

Provides pub/sub messaging functionality using the existing MessageBus class.
"""

import asyncio
import json
from typing import Dict, Any, Optional, Set
import pluggy

from ksi_daemon.message_bus import MessageBus
from ksi_daemon.plugin_utils import get_logger, plugin_metadata
from ksi_common import TimestampManager

# Plugin metadata
plugin_metadata("message_bus", version="1.0.0",
                description="Event-based pub/sub messaging for agents")

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Module state
logger = get_logger("message_bus")
message_bus = MessageBus()
event_emitter = None

# Track subscriptions per client
client_subscriptions: Dict[str, Set[str]] = {}


@hookimpl
def ksi_startup(config):
    """Initialize message bus plugin."""
    logger.info("Message bus plugin started")
    return {"plugin.message_bus": {"loaded": True}}


@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
    """Handle message bus events."""
    
    # Subscribe to events
    if event_name == "message:subscribe":
        return handle_subscribe(data)
    
    # Unsubscribe from events
    elif event_name == "message:unsubscribe":
        return handle_unsubscribe(data)
    
    # Publish message
    elif event_name == "message:publish":
        return handle_publish(data)
    
    # Get subscriptions
    elif event_name == "message:subscriptions":
        return handle_get_subscriptions(data)
    
    # Legacy PUBLISH/SUBSCRIBE command support
    elif event_name == "transport:message" and data.get("command") == "PUBLISH":
        # Convert legacy format
        params = data.get("parameters", {})
        return handle_publish({
            "agent_id": params.get("agent_id"),
            "event_type": params.get("event_type"),
            "message": params.get("message", {})
        })
    
    elif event_name == "transport:message" and data.get("command") == "SUBSCRIBE":
        # Convert legacy format
        params = data.get("parameters", {})
        return handle_subscribe({
            "agent_id": params.get("agent_id"),
            "event_types": params.get("event_types", [])
        })
    
    return None


def handle_subscribe(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle subscription request."""
    agent_id = data.get("agent_id")
    event_types = data.get("event_types", [])
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    if not event_types:
        return {"error": "event_types required"}
    
    # Track subscriptions
    if agent_id not in client_subscriptions:
        client_subscriptions[agent_id] = set()
    
    subscribed = []
    for event_type in event_types:
        # Add to message bus subscriptions
        # Note: In the plugin architecture, we don't have direct writer access
        # Instead, we track subscriptions and route via events
        client_subscriptions[agent_id].add(event_type)
        subscribed.append(event_type)
        logger.info(f"Agent {agent_id} subscribed to {event_type}")
    
    return {
        "status": "subscribed",
        "agent_id": agent_id,
        "event_types": subscribed
    }


def handle_unsubscribe(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle unsubscribe request."""
    agent_id = data.get("agent_id")
    event_types = data.get("event_types", [])
    
    if not agent_id:
        return {"error": "agent_id required"}
    
    if agent_id not in client_subscriptions:
        return {"error": f"Agent {agent_id} has no subscriptions"}
    
    unsubscribed = []
    for event_type in event_types:
        if event_type in client_subscriptions[agent_id]:
            client_subscriptions[agent_id].remove(event_type)
            unsubscribed.append(event_type)
            logger.info(f"Agent {agent_id} unsubscribed from {event_type}")
    
    # Clean up if no subscriptions left
    if not client_subscriptions[agent_id]:
        del client_subscriptions[agent_id]
    
    return {
        "status": "unsubscribed",
        "agent_id": agent_id,
        "event_types": unsubscribed
    }


async def handle_publish(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle message publish."""
    sender_id = data.get("agent_id") or data.get("sender")
    event_type = data.get("event_type")
    message = data.get("message", {})
    
    if not event_type:
        return {"error": "event_type required"}
    
    # Find all subscribers
    recipients = []
    for agent_id, subscriptions in client_subscriptions.items():
        if event_type in subscriptions:
            recipients.append(agent_id)
    
    # Special handling for DIRECT_MESSAGE
    if event_type == "DIRECT_MESSAGE":
        target = message.get("to")
        if target:
            recipients = [target] if target in recipients else []
    
    # Emit event to each recipient
    delivered = []
    failed = []
    
    for recipient_id in recipients:
        try:
            # Emit targeted event to recipient
            if event_emitter:
                await event_emitter(f"message:received:{recipient_id}", {
                    "event_type": event_type,
                    "sender": sender_id,
                    "message": message,
                    "timestamp": TimestampManager.format_for_logging()
                })
                delivered.append(recipient_id)
            else:
                failed.append(recipient_id)
        except Exception as e:
            logger.error(f"Failed to deliver to {recipient_id}: {e}")
            failed.append(recipient_id)
    
    logger.info(f"Published {event_type} from {sender_id} to {len(delivered)} recipients")
    
    return {
        "status": "published",
        "event_type": event_type,
        "delivered": delivered,
        "failed": failed,
        "total_recipients": len(recipients)
    }


def handle_get_subscriptions(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get subscriptions for an agent or all agents."""
    agent_id = data.get("agent_id")
    
    if agent_id:
        return {
            "agent_id": agent_id,
            "subscriptions": list(client_subscriptions.get(agent_id, []))
        }
    
    # Return all subscriptions
    all_subs = {}
    for aid, subs in client_subscriptions.items():
        all_subs[aid] = list(subs)
    
    return {
        "subscriptions": all_subs,
        "total_agents": len(all_subs)
    }


@hookimpl
def ksi_plugin_context(context):
    """Receive plugin context with event emitter."""
    global event_emitter
    event_emitter = context.get("emit_event")


@hookimpl
def ksi_shutdown():
    """Clean up on shutdown."""
    logger.info(f"Message bus plugin stopped - {len(client_subscriptions)} agents had subscriptions")
    return {
        "plugin.message_bus": {
            "stopped": True,
            "total_subscriptions": len(client_subscriptions)
        }
    }


# Module-level marker for plugin discovery
ksi_plugin = True