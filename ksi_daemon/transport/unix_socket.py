#!/usr/bin/env python3
"""
Unix Socket Transport Module - Event-Based Version

Handles Unix domain socket communication using pure event system.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Callable, TypedDict, Literal
from typing_extensions import NotRequired, Required

from ksi_daemon.event_system import event_handler, EventPriority, get_router
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

# Module state
logger = get_bound_logger("unix_socket_transport", version="2.0.0")
server = None
event_emitter: Optional[Callable] = None
client_connections = {}  # Keep for transport layer connection tracking
transport_instance = None

# Module info
MODULE_INFO = {
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
        logger.info("Event emitter configured for transport")
    
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
            
            # Check for monitor:subscribe to register with monitor module
            if message.get("event") == "monitor:subscribe":
                data = message.get("data", {})
                str_client_id = data.get("client_id")
                if str_client_id:
                    # Register client writer with monitor module
                    from ksi_daemon.core import monitor
                    monitor.register_client_writer(str_client_id, writer)
                    logger.debug(f"Registered client {str_client_id} with monitor module")
            
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
        # Clean up transport connection
        del client_connections[client_id]
        
        # Unregister from monitor module
        from ksi_daemon.core import monitor
        # Find any client IDs that map to this writer and unregister them
        for str_client_id in list(monitor.client_writers.keys()):
            if monitor.client_writers[str_client_id] == writer:
                monitor.unregister_client_writer(str_client_id)
                logger.debug(f"Unregistered client {str_client_id} from monitor module")
        
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

class SystemStartupData(TypedDict):
    """System startup configuration."""
    # No specific fields required for this handler
    pass


@event_handler("system:startup")
async def handle_startup(config_data: SystemStartupData) -> Dict[str, Any]:
    """Initialize transport on startup."""
    global transport_instance
    
    # Create transport instance - use imported config
    socket_path = str(config.socket_path)
    transport_instance = UnixSocketTransport(socket_path)
    
    logger.info("Unix socket transport module starting")
    return {"module.unix_socket_transport": {"loaded": True}}


class SystemReadyData(TypedDict):
    """System ready notification."""
    # No specific fields for this handler
    pass


@event_handler("system:ready")
async def handle_ready(data: SystemReadyData) -> Optional[Dict[str, Any]]:
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


class SystemContextData(TypedDict):
    """System context with runtime references."""
    emit_event: NotRequired[Callable]  # Event emitter function
    shutdown_event: NotRequired[Any]  # Shutdown event object


@event_handler("system:context")
async def handle_context(context: SystemContextData) -> None:
    """Receive context including event emitter."""
    global transport_instance, event_emitter
    
    event_emitter = context.get("emit_event")
    if transport_instance and event_emitter:
        transport_instance.set_event_emitter(event_emitter)
        logger.info("Transport configured with event emitter")


class TransportCreateConfig(TypedDict):
    """Transport configuration."""
    socket_dir: Required[str]  # Socket directory path


class TransportCreateData(TypedDict):
    """Create transport request."""
    transport_type: Required[Literal['unix']]  # Transport type (must be 'unix')
    config: Required[TransportCreateConfig]  # Transport configuration


@event_handler("transport:create")
async def handle_create_transport(data: TransportCreateData) -> Optional[UnixSocketTransport]:
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




class SystemShutdownData(TypedDict):
    """System shutdown notification."""
    # No specific fields for shutdown
    pass


@event_handler("system:shutdown")
async def handle_shutdown(data: SystemShutdownData) -> Dict[str, Any]:
    """Begin shutdown sequence - send notification but keep socket open for completion event."""
    global client_connections
    
    # First, broadcast shutdown notification to all connected clients
    if client_connections:
        logger.info(f"Broadcasting shutdown to {len(client_connections)} connected clients")
        shutdown_msg = {
            "event": "system:shutdown_notification",
            "data": {
                "reason": "daemon_shutdown",
                "timestamp": asyncio.get_event_loop().time()
            }
        }
        
        # Send to all clients
        for client_id, writer in list(client_connections.items()):
            try:
                await send_response(writer, shutdown_msg)
            except Exception as e:
                logger.debug(f"Failed to send shutdown notification to client {client_id}: {e}")
    
    # Don't stop the transport yet - wait for shutdown_complete event
    logger.info("Unix socket transport shutdown notification sent, awaiting completion")
    return {"status": "unix_socket_transport_shutdown_initiated"}


@event_handler("system:shutdown_complete")
async def handle_shutdown_complete(data: Dict[str, Any]) -> Dict[str, Any]:
    """Send final shutdown_complete event to clients and close socket.
    
    NOTE: This manual broadcast is intentional - the event system has completed 
    its shutdown sequence and this transport layer delivers the final notification
    to clients (like daemon_control.py) before closing the socket.
    """
    global transport_instance, client_connections
    
    # Send shutdown_complete notification to all remaining connected clients
    if client_connections:
        logger.info(f"Broadcasting shutdown_complete to {len(client_connections)} connected clients")
        shutdown_complete_msg = {
            "event": "system:shutdown_complete",
            "data": {
                "reason": "daemon_shutdown_complete",
                "timestamp": asyncio.get_event_loop().time(),
                "services": data.get("services", [])
            }
        }
        
        # Send to all clients - this is the final message before socket closure
        for client_id, writer in list(client_connections.items()):
            try:
                await send_response(writer, shutdown_complete_msg)
                # Ensure the message is sent
                await writer.drain()
            except Exception as e:
                logger.debug(f"Failed to send shutdown_complete notification to client {client_id}: {e}")
    
    # Now stop the transport after sending the final message
    if transport_instance:
        await transport_instance.stop()
    
    logger.info("Unix socket transport shutdown complete - socket closed")
    return {"status": "unix_socket_transport_stopped"}


