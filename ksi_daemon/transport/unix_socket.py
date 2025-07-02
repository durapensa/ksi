#!/usr/bin/env python3
"""
Unix Socket Transport Plugin - Event-Based Version

Handles Unix domain socket communication using pure event system.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Callable

from ksi_daemon.event_system import event_handler, EventPriority, get_router
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

# Module state
logger = get_bound_logger("unix_socket_transport", version="2.0.0")
server = None
event_emitter: Optional[Callable] = None
client_connections = {}
client_subscriptions = {}  # client_id -> set of event patterns they're subscribed to
transport_instance = None

# Plugin info
PLUGIN_INFO = {
    "name": "unix_socket_transport",
    "version": "2.0.0",
    "description": "Unix domain socket transport layer"
}


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
        # Clean up subscriptions
        if client_id in client_subscriptions:
            del client_subscriptions[client_id]
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
        # Emit the event and get response (event system always returns list)
        response_data = await event_emitter(event_name, data)
        
        # Handle async responses
        if asyncio.iscoroutine(response_data) or asyncio.isfuture(response_data):
            response_data = await response_data
        
        # Ensure we have a list from event system
        if not isinstance(response_data, list):
            response_data = [response_data] if response_data is not None else []
        
        # Apply REST pattern: single response = object, multiple = array
        if len(response_data) == 1:
            data_payload = response_data[0]  # Unwrap single response
        else:
            data_payload = response_data     # Keep array for 0 or multiple responses
        
        # Create proper JSON envelope following REST conventions
        envelope = {
            "event": event_name,
            "data": data_payload,
            "count": len(response_data),
            "correlation_id": correlation_id,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        return envelope
    
    except Exception as e:
        logger.error(f"Error handling event {event_name}: {e}", exc_info=True)
        return {
            "event": event_name,
            "error": str(e),
            "correlation_id": correlation_id,
            "timestamp": asyncio.get_event_loop().time()
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


async def broadcast_event(event_message: Dict[str, Any]):
    """Broadcast an event to all connected clients."""
    if not client_connections:
        return
        
    logger.debug(f"Broadcasting event {event_message.get('event')} to {len(client_connections)} clients")
    
    # Send to all connected clients
    disconnect_clients = []
    for client_id, writer in client_connections.items():
        try:
            message_str = json.dumps(event_message) + '\n'
            writer.write(message_str.encode())
            await writer.drain()
        except Exception as e:
            logger.warning(f"Failed to send event to client {client_id}: {e}")
            disconnect_clients.append(client_id)
    
    # Clean up disconnected clients
    for client_id in disconnect_clients:
        if client_id in client_connections:
            del client_connections[client_id]
        if client_id in client_subscriptions:
            del client_subscriptions[client_id]


# Event handlers

@event_handler("system:startup")
async def handle_startup(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize transport on startup."""
    global transport_instance
    
    # Create transport instance - use imported config
    socket_path = str(config.socket_path)
    transport_instance = UnixSocketTransport(socket_path)
    
    logger.info("Unix socket transport plugin starting")
    return {"plugin.unix_socket_transport": {"loaded": True}}


@event_handler("system:ready")
async def handle_ready(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return long-running server task to keep daemon alive."""
    global transport_instance
    
    if transport_instance:
        logger.info("Starting Unix socket server task")
        
        async def run_server():
            """Run the Unix socket server - keeps daemon alive."""
            await transport_instance.start()
            
            # Keep server running until cancelled
            try:
                # Use the server's serve_forever() method which is properly cancellable
                await transport_instance.server.serve_forever()
            except asyncio.CancelledError:
                logger.info("Server task cancelled - shutting down")
                await transport_instance.stop()
                raise
        
        return {
            "service": "unix_socket_transport",
            "tasks": [
                {
                    "name": "socket_server", 
                    "coroutine": run_server()
                }
            ]
        }
    
    return None


@event_handler("system:context")
async def handle_context(context: Dict[str, Any]) -> None:
    """Receive context including event emitter."""
    global transport_instance, event_emitter
    
    event_emitter = context.get("emit_event")
    if transport_instance and event_emitter:
        transport_instance.set_event_emitter(event_emitter)
        logger.info("Transport configured with event emitter")


@event_handler("transport:create")
async def handle_create_transport(data: Dict[str, Any]) -> Optional[UnixSocketTransport]:
    """Create Unix socket transport if requested."""
    transport_type = data.get("transport_type")
    config_data = data.get("config", {})
    
    if transport_type != "unix":
        return None
    
    logger.info(f"Creating unix socket transport with config: {config_data}")
    
    # Get socket path from transport config (always provided)
    socket_dir = config_data["socket_dir"]
    socket_path = os.path.join(socket_dir, "daemon.sock")
    
    return UnixSocketTransport(socket_path)


# Broadcast handler for certain events
@event_handler("completion:result")
@event_handler("completion:progress")
@event_handler("completion:error")
@event_handler("completion:cancelled")
async def handle_broadcastable_event(data: Dict[str, Any]) -> None:
    """Broadcast certain events to all connected clients."""
    # Get event name from router context if available
    router = get_router()
    event_name = "completion:result"  # Default, will be overridden by context
    
    # Create event message to broadcast
    event_message = {
        "event": event_name,
        "data": data,
        "timestamp": data.get("timestamp", "")
    }
    
    # Add correlation_id if present
    correlation_id = data.get("correlation_id")
    if correlation_id:
        event_message["correlation_id"] = correlation_id
    
    # Broadcast to all connected clients
    await broadcast_event(event_message)


@event_handler("system:shutdown")
async def handle_shutdown(data: Dict[str, Any]) -> Dict[str, Any]:
    """Clean up on shutdown."""
    global transport_instance
    if transport_instance:
        await transport_instance.stop()
    
    logger.info("Unix socket transport plugin stopped")
    return {"status": "unix_socket_transport_stopped"}


