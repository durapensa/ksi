"""
WebSocket transport for KSI daemon.

Provides native WebSocket connectivity for real-time event streaming and
bidirectional communication with web clients.
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, Any, Optional, Set
from typing_extensions import TypedDict
from pathlib import Path

import websockets
from websockets.server import WebSocketServerProtocol, serve

from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_common.event_response_builder import event_response_builder

# Transport state
logger = get_bound_logger("websocket_transport", version="1.0.0")
server = None
client_connections: Dict[uuid.UUID, WebSocketServerProtocol] = {}
client_metadata: Dict[uuid.UUID, Dict[str, Any]] = {}
shutdown_event = None
event_emitter: Optional[Any] = None  # Will be set via system:context event


async def handle_client(websocket: WebSocketServerProtocol) -> None:
    """Handle a WebSocket client connection."""
    client_id = uuid.uuid4()
    client_addr = websocket.remote_address
    
    logger.info(f"WebSocket client connected: {client_addr} (ID: {client_id})")
    
    # Store connection
    client_connections[client_id] = websocket
    client_metadata[client_id] = {
        "address": client_addr,
        "connected_at": asyncio.get_event_loop().time()
    }
    
    try:
        # Send connection confirmation
        await send_response(websocket, {
            "event": "transport:connected",
            "data": {
                "message": "Connected to KSI daemon via WebSocket",
                "client_id": str(client_id),
                "transport": "websocket"
            }
        })
        
        # Handle messages
        async for message in websocket:
            try:
                data = json.loads(message)
                
                # Check for monitor:subscribe to register with monitor module
                if data.get("event") == "monitor:subscribe":
                    subscribe_data = data.get("data", {})
                    str_client_id = subscribe_data.get("client_id")
                    if str_client_id:
                        # Create writer adapter for monitor integration
                        writer_adapter = WebSocketWriterAdapter(websocket, str_client_id)
                        
                        # Register with monitor module
                        from ksi_daemon.core import monitor
                        monitor.register_client_writer(str_client_id, writer_adapter)
                        logger.debug(f"Registered WebSocket client {str_client_id} with monitor module")
                
                # Handle the message
                response = await handle_message(data)
                
                # Send response if any
                if response:
                    await send_response(websocket, response)
                    
            except json.JSONDecodeError as e:
                await send_response(websocket, {"error": f"Invalid JSON: {e}"})
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                await send_response(websocket, {"error": str(e)})
                
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"WebSocket client disconnected: {client_addr}")
    except Exception as e:
        logger.error(f"Error handling WebSocket client: {e}", exc_info=True)
    finally:
        # Clean up
        del client_connections[client_id]
        del client_metadata[client_id]
        
        # Unregister from monitor module
        from ksi_daemon.core import monitor
        # Find any client IDs that map to this websocket and unregister
        for str_client_id in list(monitor.client_writers.keys()):
            writer = monitor.client_writers.get(str_client_id)
            if hasattr(writer, 'websocket') and writer.websocket == websocket:
                monitor.unregister_client_writer(str_client_id)
                logger.debug(f"Unregistered WebSocket client {str_client_id} from monitor module")


async def handle_message(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle an incoming message."""
    if not event_emitter:
        logger.error("No event emitter configured")
        return {"error": "Transport not initialized"}
    
    # Extract event info
    event_name = message.get("event")
    data = message.get("data", {})
    
    if not event_name:
        return {"error": "Missing event name"}
    
    # Build context from message metadata
    from ksi_common.event_parser import SYSTEM_METADATA_FIELDS
    
    context = {}
    
    # Extract all system metadata fields if present
    for field in SYSTEM_METADATA_FIELDS:
        if field in message:
            context[field] = message[field]
    
    # Extract correlation_id for response envelope
    correlation_id = message.get("correlation_id") or context.get("_correlation_id")
    
    try:
        # Emit the event and get response (event system always returns list)
        # Pass context if we have any metadata
        if context:
            response_data = await event_emitter(event_name, data, context)
        else:
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


async def send_response(websocket: WebSocketServerProtocol, response: Dict[str, Any]) -> None:
    """Send a response to the client."""
    try:
        await websocket.send(json.dumps(response))
    except Exception as e:
        logger.error(f"Failed to send response: {e}")


async def start_server() -> None:
    """Start the WebSocket server."""
    global server
    
    host = config.websocket_host
    port = config.websocket_port
    
    logger.info(f"Starting WebSocket server on {host}:{port}")
    
    # Configure CORS if needed
    cors_origins = config.websocket_cors_origins if hasattr(config, 'websocket_cors_origins') else []
    
    async def process_request(path: str, request_headers: Any) -> Optional[tuple]:
        """Handle CORS preflight requests."""
        origin = request_headers.get("Origin", "")
        
        # Allow WebSocket upgrade
        if request_headers.get("Upgrade", "").lower() == "websocket":
            # Check origin for WebSocket connections
            if cors_origins and origin and origin not in cors_origins and "*" not in cors_origins:
                logger.warning(f"Rejected WebSocket connection from origin: {origin}")
                return (403, [], b"Forbidden")
            return None
            
        # Handle CORS preflight
        if origin in cors_origins or "*" in cors_origins:
            return (
                200,
                [
                    ("Access-Control-Allow-Origin", origin),
                    ("Access-Control-Allow-Methods", "GET"),
                    ("Access-Control-Allow-Headers", "Content-Type"),
                ],
                b"OK",
            )
        return (403, [], b"Forbidden")
    
    # Start server
    server = await serve(
        handle_client,
        host,
        port,
        process_request=process_request if cors_origins else None
    )
    
    logger.info(f"WebSocket server listening on ws://{host}:{port}")
    
    # Wait for shutdown
    if shutdown_event:
        await shutdown_event.wait()
    else:
        await asyncio.Future()  # Run forever


async def stop_server() -> None:
    """Stop the WebSocket server."""
    global server
    
    if server:
        logger.info("Stopping WebSocket server...")
        
        # Notify connected clients
        disconnect_msg = json.dumps({
            "event": "transport:shutdown",
            "data": {
                "message": "KSI daemon is shutting down",
                "reason": "shutdown"
            }
        })
        
        # Send to all connected clients
        tasks = []
        for websocket in list(client_connections.values()):
            try:
                tasks.append(websocket.send(disconnect_msg))
            except Exception:
                pass
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # Close all connections
        close_tasks = []
        for websocket in list(client_connections.values()):
            try:
                close_tasks.append(websocket.close(1001, "Server shutting down"))
            except Exception:
                pass
                
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)
        
        # Stop server
        server.close()
        await server.wait_closed()
        server = None
        
        logger.info("WebSocket server stopped")


class WebSocketWriterAdapter:
    """Adapter that makes WebSocket look like asyncio writer for monitor integration."""
    
    def __init__(self, websocket: WebSocketServerProtocol, client_id: str):
        self.websocket = websocket
        self.client_id = client_id
        self._closed = False
    
    def write(self, data: bytes):
        """Queue data to be sent via WebSocket."""
        if self._closed:
            return
            
        try:
            # Decode and send as JSON
            if isinstance(data, bytes):
                data = data.decode('utf-8').strip()
            
            # Handle newline-delimited JSON
            for line in data.split('\n'):
                if line.strip():
                    try:
                        event_data = json.loads(line)
                        # Send asynchronously without blocking
                        asyncio.create_task(self._send_async(event_data))
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON from monitor: {line}")
        except Exception as e:
            logger.error(f"Error in WebSocketWriterAdapter.write: {e}")
    
    async def _send_async(self, data: Dict[str, Any]):
        """Send data asynchronously."""
        try:
            if not self._closed and self.websocket.open:
                await self.websocket.send(json.dumps(data))
        except Exception as e:
            logger.error(f"Error sending to WebSocket client {self.client_id}: {e}")
            self._closed = True
    
    async def drain(self):
        """Compatibility with asyncio writer interface."""
        pass
    
    def close(self):
        """Mark as closed."""
        self._closed = True
    
    async def wait_closed(self):
        """Compatibility with asyncio writer interface."""
        pass
    
    @property
    def is_closing(self):
        """Check if writer is closing."""
        return self._closed or not self.websocket.open


# Transport info for module discovery
MODULE_INFO = {
    "name": "websocket",
    "version": "1.0.0",
    "description": "Native WebSocket transport for KSI daemon",
    "capabilities": ["real-time", "bidirectional", "web-compatible"],
    "config": {
        "host": config.websocket_host if hasattr(config, 'websocket_host') else "localhost",
        "port": config.websocket_port if hasattr(config, 'websocket_port') else 8765,
        "cors_origins": config.websocket_cors_origins if hasattr(config, 'websocket_cors_origins') else []
    }
}


# Event handlers for transport integration
from ksi_daemon.event_system import event_handler, EventPriority

class SystemContextData(TypedDict):
    """System context with runtime references."""
    emit_event: Optional[Any]  # Event emitter function
    shutdown_event: Optional[Any]  # Shutdown event object


@event_handler("system:context")
async def handle_context(data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Receive context including event emitter."""
    # PYTHONIC CONTEXT REFACTOR: Use system registry for components
    
    global event_emitter, shutdown_event
    
    if data.get("registry_available"):
        from ksi_daemon.core.system_registry import SystemRegistry
        event_emitter = SystemRegistry.get("event_emitter")
        shutdown_event = SystemRegistry.get("shutdown_event")
    else:
        event_emitter = data.get("emit_event")
        shutdown_event = data.get("shutdown_event")
    
    if event_emitter:
        logger.info("WebSocket transport configured with event emitter")
        
    return event_response_builder(
        {
            "event_processed": True,
            "module": "websocket_transport"
        },
        context=context
    )