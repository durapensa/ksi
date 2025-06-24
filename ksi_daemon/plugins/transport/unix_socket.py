#!/usr/bin/env python3
"""
Unix Socket Transport Plugin

Provides Unix domain socket transport for the KSI daemon.
Handles all socket communication and converts between socket protocol and events.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Set
import logging

from ...plugin_base import BasePlugin, hookimpl
from ...plugin_types import (
    PluginMetadata, PluginCapabilities, 
    TransportConnection, TransportStatus
)

logger = logging.getLogger(__name__)


class UnixSocketConnection(TransportConnection):
    """Unix socket transport implementation."""
    
    def __init__(self, config: Dict[str, Any], event_emitter):
        """
        Initialize Unix socket transport.
        
        Args:
            config: Transport configuration
            event_emitter: Function to emit events
        """
        self.config = config
        self.emit_event = event_emitter
        
        # Single socket path from config
        socket_dir = Path(config.get("socket_dir", "/tmp/ksi"))
        socket_dir.mkdir(parents=True, exist_ok=True)
        self.socket_path = socket_dir / "daemon.sock"
        
        # Connection tracking
        self.connections: Dict[str, asyncio.StreamWriter] = {}
        self.connection_info: Dict[str, Dict[str, Any]] = {}
        self.servers = {}
        self.status = TransportStatus.DISCONNECTED
    
    async def start(self) -> None:
        """Start Unix socket server."""
        logger.info("Starting Unix socket transport")
        
        # Clean up existing socket
        if self.socket_path.exists():
            self.socket_path.unlink()
            logger.debug("Cleaned up existing socket")
        
        # Start single server
        try:
            self.server = await asyncio.start_unix_server(
                self._handle_connection,
                path=str(self.socket_path)
            )
            logger.info(f"Started server on {self.socket_path}")
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            raise
        
        self.status = TransportStatus.CONNECTED
        logger.info("Unix socket transport started successfully")
    
    async def stop(self) -> None:
        """Stop Unix socket server."""
        logger.info("Stopping Unix socket transport")
        self.status = TransportStatus.DISCONNECTED
        
        # Close all connections
        for conn_id, writer in list(self.connections.items()):
            try:
                writer.close()
                await writer.wait_closed()
            except Exception as e:
                logger.error(f"Error closing connection {conn_id}: {e}")
        
        # Stop server
        if hasattr(self, 'server'):
            self.server.close()
            await self.server.wait_closed()
            logger.debug("Stopped server")
        
        # Clean up socket file
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except Exception as e:
                logger.error(f"Error removing socket: {e}")
        
        self.connections.clear()
        logger.info("Unix socket transport stopped")
    
    async def _handle_connection(self, reader: asyncio.StreamReader, 
                                writer: asyncio.StreamWriter) -> None:
        """Handle a client connection."""
        conn_id = f"unix_{len(self.connections)}"
        
        try:
            # Store connection
            self.connections[conn_id] = writer
            self.connection_info[conn_id] = {
                "connected_at": asyncio.get_event_loop().time()
            }
            
            # Emit connection event
            await self.emit_event("transport:connection", {
                "transport_type": "unix",
                "connection_id": conn_id,
                "action": "connect"
            })
            
            # Handle messages
            while True:
                # Read line (JSON protocol)
                data = await reader.readline()
                if not data:
                    break
                
                try:
                    # Parse JSON event
                    event_str = data.decode().strip()
                    if not event_str:
                        continue
                    
                    event_data = json.loads(event_str)
                    
                    # Extract event details
                    event_name = event_data.get("event", "")
                    event_payload = event_data.get("data", {})
                    correlation_id = event_data.get("correlation_id")
                    
                    if not event_name:
                        raise ValueError("Missing event name")
                    
                    # Emit event and wait for response
                    response = await self.emit_event(
                        event_name,
                        event_payload,
                        source="unix",
                        correlation_id=correlation_id,
                        expect_response=True
                    )
                    
                    # Send response
                    if response:
                        await self._send_response(writer, response)
                    
                except json.JSONDecodeError as e:
                    # Send error response
                    error_response = {
                        "error": {
                            "code": "INVALID_JSON",
                            "message": str(e)
                        },
                        "correlation_id": event_data.get("correlation_id") if isinstance(event_data, dict) else None
                    }
                    await self._send_response(writer, error_response)
                
                except ValueError as e:
                    # Missing event name or other validation error
                    error_response = {
                        "error": {
                            "code": "INVALID_EVENT",
                            "message": str(e)
                        },
                        "correlation_id": event_data.get("correlation_id") if isinstance(event_data, dict) else None
                    }
                    await self._send_response(writer, error_response)
                
                except Exception as e:
                    logger.error(f"Error handling event: {e}")
                    error_response = {
                        "error": {
                            "code": "INTERNAL_ERROR",
                            "message": str(e)
                        },
                        "correlation_id": event_data.get("correlation_id") if isinstance(event_data, dict) else None
                    }
                    await self._send_response(writer, error_response)
        
        except asyncio.CancelledError:
            logger.debug(f"Connection {conn_id} cancelled")
        
        except Exception as e:
            logger.error(f"Connection error: {e}")
        
        finally:
            # Clean up connection
            if conn_id in self.connections:
                del self.connections[conn_id]
                del self.connection_info[conn_id]
            
            # Emit disconnection event
            await self.emit_event("transport:connection", {
                "transport_type": "unix",
                "connection_id": conn_id,
                "action": "disconnect"
            })
            
            # Close writer
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
    
    
    async def _send_response(self, writer: asyncio.StreamWriter, 
                           response: Dict[str, Any]) -> None:
        """Send response to client."""
        try:
            response_json = json.dumps(response) + '\n'
            writer.write(response_json.encode())
            await writer.drain()
        except Exception as e:
            logger.error(f"Error sending response: {e}")
    
    async def send_event(self, connection_id: str, event: Dict[str, Any]) -> None:
        """Send event to specific connection."""
        writer = self.connections.get(connection_id)
        if not writer:
            logger.warning(f"Connection {connection_id} not found")
            return
        
        await self._send_response(writer, event)
    
    async def broadcast_event(self, event: Dict[str, Any], room: Optional[str] = None) -> None:
        """Broadcast event to all connections."""
        # With single socket, room filtering is not applicable
        # Broadcast to all connections
        for conn_id, writer in self.connections.items():
            try:
                await self._send_response(writer, event)
            except Exception as e:
                logger.error(f"Error broadcasting to {conn_id}: {e}")
    
    def get_connections(self) -> list[str]:
        """Get list of active connection IDs."""
        return list(self.connections.keys())
    
    def get_status(self) -> TransportStatus:
        """Get transport status."""
        return self.status


class UnixSocketPlugin(BasePlugin):
    """Unix socket transport plugin."""
    
    def __init__(self):
        super().__init__(
            metadata=PluginMetadata(
                name="unix_socket_transport",
                version="1.0.0",
                description="Unix domain socket transport for KSI daemon",
                author="KSI Team"
            ),
            capabilities=PluginCapabilities(
                event_namespaces=["/transport"],
                commands=[],
                provides_services=["transport:unix"]
            )
        )
        self._transport: Optional[UnixSocketConnection] = None
        self._context = None
        self._event_bus = None
    
    @hookimpl
    def ksi_startup(self):
        """Initialize transport on startup."""
        logger.info("Unix socket transport plugin starting")
        return {"status": "unix_socket_transport_ready"}
    
    @hookimpl
    def ksi_plugin_context(self, context):
        """Receive plugin context with event bus access."""
        self._context = context
        self._event_bus = context.get("event_bus") if context else None
        
        # Create event emitter function
        async def emit_event(event_name: str, data: Dict[str, Any], **kwargs):
            if self._event_bus:
                correlation_id = kwargs.get("correlation_id")
                source = kwargs.get("source", "unix_socket")
                expect_response = kwargs.get("expect_response", False)
                
                # Publish event
                await self._event_bus.publish(
                    event_name,
                    data,
                    correlation_id=correlation_id,
                    source=source
                )
                
                # If expecting response, wait for it
                if expect_response and correlation_id:
                    # This is simplified - in real implementation we'd subscribe to response events
                    # For now, return success
                    return {
                        "status": "success",
                        "id": correlation_id,
                        "data": data
                    }
                
                return {"status": "published"}
            else:
                logger.error("No event bus available for event emission")
                return None
        
        # Initialize transport with event emitter
        config = self._context.get("config", {}).get("transport", {}).get("unix", {})
        self._transport = UnixSocketConnection(config, emit_event)
        
        # Start transport
        if self._context and hasattr(self._context, "create_task"):
            self._context.create_task(self._transport.start())
        else:
            asyncio.create_task(self._transport.start())
    
    @hookimpl
    def ksi_handle_event(self, event_name: str, data: Dict[str, Any], context: Dict[str, Any]):
        """Handle transport-related events."""
        if not self._transport:
            return None
        
        # Handle transport control events
        if event_name == "transport:send":
            # Send to specific connection
            connection_id = data.get("connection_id")
            event_data = data.get("event")
            if connection_id and event_data:
                asyncio.create_task(
                    self._transport.send_event(connection_id, event_data)
                )
                return {"status": "sent"}
        
        elif event_name == "transport:broadcast":
            # Broadcast to room or all
            event_data = data.get("event")
            room = data.get("room")
            if event_data:
                asyncio.create_task(
                    self._transport.broadcast_event(event_data, room)
                )
                return {"status": "broadcast"}
        
        elif event_name == "transport:status":
            # Get transport status
            return {
                "status": self._transport.get_status().value,
                "connections": len(self._transport.get_connections()),
                "socket": str(self._transport.socket_path)
            }
        
        return None
    
    @hookimpl
    def ksi_shutdown(self):
        """Clean up on shutdown."""
        if self._transport:
            # Create cleanup task
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._transport.stop())
            else:
                # If loop not running, run sync
                loop.run_until_complete(self._transport.stop())
        
        return {"status": "unix_socket_transport_stopped"}


# Plugin instance
plugin = UnixSocketPlugin()