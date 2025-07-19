"""WebSocket writer adapter for monitor service integration."""

import asyncio
from typing import Dict, Any
import json
import logging

logger = logging.getLogger(__name__)


class WebSocketWriter:
    """Adapter that looks like a Unix socket writer but forwards to WebSocket."""
    
    def __init__(self, websocket, client_id: str):
        self.websocket = websocket
        self.client_id = client_id
        self._closed = False
        
    def write(self, data: bytes):
        """Queue data to be sent via WebSocket."""
        if self._closed:
            return
            
        # Decode and send as JSON via WebSocket
        try:
            if isinstance(data, bytes):
                data = data.decode('utf-8').strip()
            
            # Parse JSON if it's a string
            if isinstance(data, str) and data:
                # Handle newline-delimited JSON
                for line in data.split('\n'):
                    if line.strip():
                        event_data = json.loads(line)
                        # Use async task to send without blocking
                        asyncio.create_task(self._send_async(event_data))
        except Exception as e:
            logger.error(f"Error in WebSocketWriter.write: {e}")
    
    async def _send_async(self, data: Dict[str, Any]):
        """Send data asynchronously to WebSocket."""
        try:
            if not self._closed and self.websocket.open:
                await self.websocket.send(json.dumps(data))
        except Exception as e:
            logger.error(f"Error sending to WebSocket client {self.client_id}: {e}")
            self._closed = True
    
    async def drain(self):
        """Compatibility with asyncio writer interface."""
        # WebSocket handles its own flow control
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