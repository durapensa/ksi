#!/usr/bin/env python3
"""
WebSocket Bridge for KSI
Connects to KSI daemon via Unix socket and bridges events to WebSocket clients
"""
import asyncio
import websockets
from websockets.asyncio.server import serve
import json
import argparse
import logging
import sys
import uuid
from pathlib import Path

# Import KSI config
from ksi_common.config import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class WebSocketBridge:
    def __init__(self, ws_host=None, ws_port=None, cors_origins=None):
        # Use config values as defaults
        self.ws_host = ws_host or config.websocket_bridge_host
        self.ws_port = ws_port or config.websocket_bridge_port
        
        # Handle CORS origins - validator ensures it's always a list
        if cors_origins:
            self.cors_origins = cors_origins
        else:
            # Get from config - validator ensures it's a list
            origins = config.websocket_bridge_cors_origins
            self.cors_origins = origins if isinstance(origins, list) else [origins]
            
        self.logger = logging.getLogger('websocket_bridge')
        
        # Use KSI config for socket path
        self.socket_path = config.socket_path
        
        # Each WebSocket client gets its own KSI connection for true transparency
        self.client_connections = {}  # websocket -> (ksi_reader, ksi_writer) mapping
        
    async def handle_websocket(self, websocket):
        """Handle new WebSocket connection - each client gets its own KSI connection."""
        # Check origin for CORS
        origin = websocket.request.headers.get("Origin", "")
        if origin and origin not in self.cors_origins and "*" not in self.cors_origins:
            self.logger.warning(f"Rejected connection from origin: {origin}")
            await websocket.close(1008, "Origin not allowed")
            return
            
        # Get client address from the connection
        client_addr = f"{websocket.request.headers.get('Host', 'unknown')}"
        self.logger.info(f"Client connected from {client_addr} (origin: {origin})")
        
        # Generate unique client ID for this WebSocket connection
        client_id = str(uuid.uuid4())
        
        # Create dedicated KSI connection for this WebSocket client
        ksi_reader = None
        ksi_writer = None
        ksi_task = None
        
        try:
            # Connect to KSI daemon for this specific client
            try:
                ksi_reader, ksi_writer = await asyncio.wait_for(
                    asyncio.open_unix_connection(str(self.socket_path)),
                    timeout=5.0
                )
                self.client_connections[websocket] = (ksi_reader, ksi_writer)
                self.logger.info(f"Created dedicated KSI connection for client {client_addr}")
            except Exception as e:
                self.logger.error(f"Failed to connect to KSI for client: {e}")
                await websocket.send(json.dumps({
                    "event": "bridge:error",
                    "data": {"error": "Failed to connect to KSI daemon"}
                }))
                return
            
            # Send initial connection confirmation
            await websocket.send(json.dumps({
                "event": "bridge:connected",
                "data": {
                    "message": "Connected to KSI WebSocket bridge",
                    "suggested_client_id": client_id
                }
            }))
            
            # Start task to forward KSI events to this WebSocket client
            ksi_task = asyncio.create_task(
                self.forward_ksi_to_websocket(ksi_reader, websocket, client_addr)
            )
            
            # Handle incoming messages from WebSocket client
            async for message in websocket:
                await self.handle_websocket_message(websocket, ksi_writer, message)
                
        finally:
            # Clean up when WebSocket disconnects
            if ksi_task:
                ksi_task.cancel()
                try:
                    await ksi_task
                except asyncio.CancelledError:
                    pass
                    
            if websocket in self.client_connections:
                _, writer = self.client_connections[websocket]
                if writer:
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except:
                        pass
                del self.client_connections[websocket]
                
            self.logger.info(f"Client disconnected from {client_addr}")
    
    async def handle_websocket_message(self, websocket, ksi_writer, message):
        """Forward WebSocket client message to its dedicated KSI connection."""
        if not ksi_writer:
            await websocket.send(json.dumps({
                "error": "No KSI daemon connection available"
            }))
            return
            
        try:
            # Forward the message to KSI daemon
            message_str = message + "\n" if not message.endswith("\n") else message
            ksi_writer.write(message_str.encode())
            await ksi_writer.drain()
            
            self.logger.debug(f"Forwarded message from WebSocket client to KSI daemon")
        except Exception as e:
            self.logger.error(f"Failed to forward message to KSI daemon: {e}")
            await websocket.send(json.dumps({
                "error": f"Failed to forward message: {e}"
            }))
    

    async def process_request(self, connection, request):
        """Handle CORS preflight requests"""
        # In websockets 15.x, this receives connection and request objects
        # For WebSocket connections, return None to proceed
        # For other requests (like CORS preflight), return a response
        
        # Get headers from request object
        headers = request.headers
        
        # If it's a WebSocket upgrade request, let it through
        if headers.get("Upgrade", "").lower() == "websocket":
            return None
            
        # Handle CORS preflight
        origin = headers.get("Origin", "")
        if origin in self.cors_origins or "*" in self.cors_origins:
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
    
    async def forward_ksi_to_websocket(self, ksi_reader, websocket, client_addr):
        """Forward events from KSI to specific WebSocket client."""
        try:
            while True:
                line = await ksi_reader.readline()
                if not line:
                    self.logger.warning(f"KSI daemon closed connection for client {client_addr}")
                    break
                
                try:
                    # Forward raw event to this specific WebSocket client only
                    event_str = line.decode('utf-8').strip()
                    if event_str:
                        await websocket.send(event_str)
                        self.logger.debug(f"Forwarded KSI event to client {client_addr}")
                        
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Invalid JSON from KSI: {e}")
                except websockets.exceptions.ConnectionClosed:
                    self.logger.info(f"WebSocket closed for client {client_addr}")
                    break
                except Exception as e:
                    self.logger.error(f"Error forwarding to client {client_addr}: {e}")
                    
        except asyncio.CancelledError:
            self.logger.debug(f"KSI forwarding task cancelled for client {client_addr}")
            raise
    
    async def monitor_ksi_health(self):
        """Periodically check KSI daemon health."""
        while True:
            try:
                # Simple health check - try connecting
                reader, writer = await asyncio.wait_for(
                    asyncio.open_unix_connection(str(self.socket_path)),
                    timeout=2.0
                )
                # Send health check
                writer.write(b'{"event": "system:health", "data": {}}\n')
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                self.logger.debug("KSI daemon health check passed")
                
            except Exception as e:
                self.logger.warning(f"KSI daemon health check failed: {e}")
                
            await asyncio.sleep(30)  # Check every 30 seconds
    
    async def run(self):
        """Main bridge loop with WebSocket server."""
        self.logger.info("Starting WebSocket bridge...")
        
        # Start WebSocket server
        async with serve(
            self.handle_websocket,
            self.ws_host,
            self.ws_port,
            process_request=self.process_request
        ) as server:
            self.logger.info(f"WebSocket server listening on ws://{self.ws_host}:{self.ws_port}")
            self.logger.info("Bridge operating in transparent mode - each client gets dedicated KSI connection")
            
            try:
                # Run health monitoring in background
                health_task = asyncio.create_task(self.monitor_ksi_health())
                
                # Keep server running
                await asyncio.Future()  # Run forever
                
            except KeyboardInterrupt:
                self.logger.info("Bridge shutdown requested")
                health_task.cancel()

def main():
    parser = argparse.ArgumentParser(
        description="WebSocket bridge for KSI",
        epilog="""
Configuration via environment variables:
  KSI_SOCKET_PATH - Unix socket path
  KSI_WEBSOCKET_BRIDGE_HOST - WebSocket host  
  KSI_WEBSOCKET_BRIDGE_PORT - WebSocket port
  KSI_WEBSOCKET_BRIDGE_CORS_ORIGINS - Comma-separated CORS origins
  
Example:
  export KSI_WEBSOCKET_BRIDGE_CORS_ORIGINS="http://localhost:8080,https://myapp.com"
  python websocket_bridge.py
        """
    )
    parser.add_argument('--ws-host', help=f'WebSocket host (default: {config.websocket_bridge_host})')
    parser.add_argument('--ws-port', type=int, help=f'WebSocket port (default: {config.websocket_bridge_port})')
    parser.add_argument('--cors-origin', action='append', dest='cors_origins',
                        help='Additional CORS origin (can be specified multiple times)')
    args = parser.parse_args()
    
    # Command line args override config
    bridge = WebSocketBridge(
        ws_host=args.ws_host,
        ws_port=args.ws_port,
        cors_origins=args.cors_origins
    )
    
    try:
        asyncio.run(bridge.run())
    except KeyboardInterrupt:
        print("\nBridge shutdown complete")

if __name__ == "__main__":
    main()