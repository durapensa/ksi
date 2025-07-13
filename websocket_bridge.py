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
            
        self.websocket_clients = set()
        self.logger = logging.getLogger('websocket_bridge')
        
        # Use KSI config for socket path
        self.socket_path = config.socket_path
        
        # Track WebSocket client subscriptions
        self.client_subscriptions = {}  # websocket -> client_id mapping
        
    async def handle_websocket(self, websocket):
        """Handle new WebSocket connection"""
        # In websockets v15, the handler only receives the websocket connection
        # Check origin for CORS
        origin = websocket.request.headers.get("Origin", "")
        if origin and origin not in self.cors_origins and "*" not in self.cors_origins:
            self.logger.warning(f"Rejected connection from origin: {origin}")
            await websocket.close(1008, "Origin not allowed")
            return
            
        self.websocket_clients.add(websocket)
        # Get client address from the connection
        client_addr = f"{websocket.request.headers.get('Host', 'unknown')}"
        self.logger.info(f"Client connected from {client_addr} (origin: {origin})")
        
        # Generate unique client ID for this WebSocket connection
        client_id = str(uuid.uuid4())
        self.client_subscriptions[websocket] = client_id
        
        try:
            # Send initial connection confirmation
            await websocket.send(json.dumps({
                "event": "bridge:connected",
                "data": {
                    "message": "Connected to KSI WebSocket bridge",
                    "suggested_client_id": client_id  # Client can use this or generate its own
                }
            }))
            
            # Handle incoming messages from WebSocket client
            async for message in websocket:
                await self.handle_websocket_message(websocket, message)
        finally:
            # Clean up when WebSocket disconnects
            if websocket in self.client_subscriptions:
                del self.client_subscriptions[websocket]
            self.websocket_clients.remove(websocket)
            self.logger.info(f"Client disconnected from {client_addr}")
    
    async def handle_websocket_message(self, websocket, message):
        """Forward WebSocket client message to KSI daemon"""
        if not hasattr(self, 'ksi_writer') or self.ksi_writer is None:
            await websocket.send(json.dumps({
                "error": "No KSI daemon connection available"
            }))
            return
            
        try:
            # Forward the message to KSI daemon
            message_str = message + "\n" if not message.endswith("\n") else message
            self.ksi_writer.write(message_str.encode())
            await self.ksi_writer.drain()
            
            client_id = self.client_subscriptions.get(websocket, "unknown")
            self.logger.debug(f"Forwarded message from WebSocket client {client_id} to KSI daemon")
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
    
    async def broadcast_event(self, event_json: str):
        """Broadcast event to all connected WebSocket clients"""
        if not self.websocket_clients:
            return
            
        # Send to all clients
        disconnected = set()
        for ws in self.websocket_clients:
            try:
                await ws.send(event_json)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(ws)
            except Exception as e:
                self.logger.error(f"Error sending to client: {e}")
                disconnected.add(ws)
                
        # Remove disconnected clients
        self.websocket_clients -= disconnected
        if disconnected:
            self.logger.info(f"Removed {len(disconnected)} disconnected clients")
    
    async def connect_to_ksi(self):
        """Connect to KSI daemon via Unix socket for real-time event streaming"""
        while True:
            reader = None
            writer = None
            
            try:
                self.logger.info(f"Connecting to KSI daemon at {self.socket_path}...")
                
                # Direct Unix socket connection
                reader, writer = await asyncio.wait_for(
                    asyncio.open_unix_connection(str(self.socket_path)),
                    timeout=5.0
                )
                
                self.logger.info("Connected to KSI daemon via Unix socket")
                
                # Store writer for forwarding WebSocket client messages
                self.ksi_writer = writer
                
                # Notify WebSocket clients of connection
                await self.broadcast_event(json.dumps({
                    "event": "bridge:ksi_connected",
                    "data": {"message": "KSI daemon connected"},
                    "timestamp": asyncio.get_event_loop().time()
                }))
                
                # Stream events from Unix socket to WebSocket clients
                while True:
                    line = await reader.readline()
                    if not line:
                        self.logger.warning("KSI daemon closed connection")
                        break
                    
                    try:
                        # Decode and validate JSON
                        event_str = line.decode('utf-8').strip()
                        if event_str:
                            # Validate it's JSON
                            json.loads(event_str)
                            # Forward raw event
                            await self.broadcast_event(event_str)
                    
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Invalid JSON from KSI: {e}")
                    except Exception as e:
                        self.logger.error(f"Error processing event: {e}")
                        
            except asyncio.TimeoutError:
                self.logger.error("Connection timeout to KSI daemon")
            except FileNotFoundError:
                self.logger.error(f"Socket file not found: {self.socket_path}")
            except PermissionError:
                self.logger.error(f"Permission denied accessing socket: {self.socket_path}")
            except Exception as e:
                self.logger.error(f"KSI connection error: {e}")
            
            finally:
                # Clean up connection
                if writer:
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except:
                        pass
                
                # Notify WebSocket clients of disconnection
                await self.broadcast_event(json.dumps({
                    "event": "bridge:ksi_disconnected",
                    "data": {"message": "KSI daemon disconnected, will retry..."},
                    "timestamp": asyncio.get_event_loop().time()
                }))
                
                # Wait before retry
                self.logger.info("Waiting 5 seconds before reconnecting...")
                await asyncio.sleep(5)
    
    async def run(self):
        """Main bridge loop with WebSocket server and KSI reconnection"""
        self.logger.info("Starting WebSocket bridge...")
        
        # Start WebSocket server
        async with serve(
            self.handle_websocket,
            self.ws_host,
            self.ws_port,
            process_request=self.process_request
        ) as server:
            self.logger.info(f"WebSocket server listening on ws://{self.ws_host}:{self.ws_port}")
            
            try:
                # Run KSI connection loop (handles reconnects)
                await self.connect_to_ksi()
            except KeyboardInterrupt:
                self.logger.info("Bridge shutdown requested")

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