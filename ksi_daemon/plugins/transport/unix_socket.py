#!/usr/bin/env python3
"""
Simplified Unix Socket Transport Plugin

Handles Unix domain socket communication without complex inheritance.
"""

import asyncio
import json
import os
from pathlib import Path
import logging
from typing import Dict, Any, Optional, Callable
import pluggy

from ...plugin_utils import get_logger, plugin_metadata
from ...config import config

# Plugin metadata
plugin_metadata("unix_socket_transport", version="2.0.0",
                description="Simplified Unix domain socket transport")

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("ksi")

# Module state
logger = get_logger("unix_socket_transport")
server = None
event_emitter: Optional[Callable] = None
client_connections = {}


class UnixSocketTransport:
    """Simple Unix socket transport implementation."""
    
    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self.server = None
        self.running = False
    
    def set_event_emitter(self, emitter: Callable):
        """Set the event emitter function."""
        global event_emitter
        event_emitter = emitter
        logger.info("Event emitter configured")
    
    async def start(self):
        """Start the Unix socket server."""
        if self.running:
            return
        
        # Ensure socket directory exists
        socket_dir = os.path.dirname(self.socket_path)
        os.makedirs(socket_dir, exist_ok=True)
        
        # Remove existing socket file
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        # Start server
        self.server = await asyncio.start_unix_server(
            handle_client,
            path=self.socket_path
        )
        
        self.running = True
        logger.info(f"Unix socket transport started on {self.socket_path}")
    
    async def stop(self):
        """Stop the Unix socket server."""
        if not self.running:
            return
        
        self.running = False
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # Clean up socket file
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        logger.info("Unix socket transport stopped")


async def handle_client(reader, writer):
    """Handle a client connection."""
    client_addr = writer.get_extra_info('peername', 'unknown')
    client_id = id(writer)
    client_connections[client_id] = writer
    
    logger.debug(f"Client connected: {client_addr}")
    
    try:
        while True:
            # Read line-delimited JSON messages
            line = await reader.readline()
            if not line:
                break
            
            try:
                message = json.loads(line.decode('utf-8').strip())
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
                await send_response(writer, {"error": f"Invalid JSON: {e}"})
                continue
            
            # Handle the message
            response = await handle_message(message)
            
            # Send response
            logger.debug(f"Got response to send: {response}")
            if response:
                await send_response(writer, response)
            else:
                logger.debug("No response to send")
    
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"Error handling client: {e}", exc_info=True)
    finally:
        # Clean up
        del client_connections[client_id]
        writer.close()
        await writer.wait_closed()
        logger.debug(f"Client disconnected: {client_addr}")


async def handle_message(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle an incoming message."""
    if not event_emitter:
        logger.error("No event emitter configured")
        return {"error": "Transport not initialized"}
    
    # Extract event info
    event_name = message.get("event")
    data = message.get("data", {})
    correlation_id = message.get("correlation_id")
    
    if not event_name:
        return {"error": "Missing event name"}
    
    try:
        # Emit the event and get response
        response = await event_emitter(event_name, data, correlation_id)
        
        # Handle async responses
        if asyncio.iscoroutine(response) or asyncio.isfuture(response):
            response = await response
        
        # Include correlation_id if present
        if response and correlation_id:
            response["correlation_id"] = correlation_id
        
        return response
    
    except Exception as e:
        logger.error(f"Error handling event {event_name}: {e}", exc_info=True)
        return {
            "error": str(e),
            "correlation_id": correlation_id
        }


async def send_response(writer, response: Dict[str, Any]):
    """Send a response to the client."""
    try:
        # Send newline-delimited JSON response
        response_str = json.dumps(response) + '\n'
        logger.debug(f"Sending response: {response_str.strip()}")
        writer.write(response_str.encode('utf-8'))
        await writer.drain()
        logger.debug("Response sent successfully")
    except Exception as e:
        logger.error(f"Error sending response: {e}")


# Hook implementations
@hookimpl
def ksi_startup(config):
    """Initialize transport on startup."""
    logger.info("Unix socket transport plugin starting")
    return {"plugin.unix_socket_transport": {"loaded": True}}


@hookimpl
def ksi_create_transport(transport_type: str, config: Dict[str, Any]):
    """Create Unix socket transport if requested."""
    if transport_type != "unix":
        return None
    
    logger.info(f"Creating unix socket transport with config: {config}")
    
    # Import daemon config to get default paths
    from ...config import config as daemon_config
    
    # Get socket path from config or use default
    socket_dir = config.get("socket_dir", str(daemon_config.socket_path.parent))
    socket_path = os.path.join(socket_dir, "daemon.sock")
    
    return UnixSocketTransport(socket_path)


@hookimpl
def ksi_shutdown():
    """Clean up on shutdown."""
    global server
    if server:
        asyncio.create_task(server.stop())
    
    logger.info("Unix socket transport plugin stopped")
    return {"status": "unix_socket_transport_stopped"}


# Module-level marker for plugin discovery
ksi_plugin = True