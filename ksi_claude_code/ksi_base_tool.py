"""
Base class for KSI-Claude Code integration tools
"""
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, TypedDict, AsyncIterator
import logging
from ksi_common.config import config

logger = logging.getLogger(__name__)


class KSIResponse(TypedDict):
    """Standard response format from KSI daemon"""
    success: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    request_id: Optional[str]


class KSIBaseTool:
    """Base class for all KSI-related Claude Code tools"""
    
    # Tool metadata - override in subclasses
    name: str = "ksi_base_tool"
    description: str = "Base KSI tool"
    
    def __init__(self, socket_path: Optional[Path] = None):
        """
        Initialize KSI tool
        
        Args:
            socket_path: Optional override for daemon socket path
        """
        self.socket_path = socket_path or config.socket_path
        self._timeout = 30.0  # Default timeout for operations
        self._max_response_size = 1024 * 1024  # 1MB max response
    
    async def send_event(
        self, 
        event: str, 
        data: Dict[str, Any],
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Send event to KSI daemon and await response
        
        Args:
            event: Event name to send
            data: Event data payload
            timeout: Optional timeout override
            
        Returns:
            Response dictionary from KSI
        """
        timeout = timeout or self._timeout
        
        try:
            # Validate daemon is running
            if not self._validate_daemon_running():
                return {
                    "success": False,
                    "error": "KSI daemon is not running"
                }
            
            # Open connection
            reader, writer = await asyncio.open_unix_connection(str(self.socket_path))
            
            # Send request
            request = json.dumps({"event": event, "data": data})
            logger.debug(f"Sending KSI event: {event}")
            writer.write(request.encode() + b'\n')
            await writer.drain()
            
            # Read response with timeout
            response_data = await asyncio.wait_for(
                reader.readline(), 
                timeout=timeout
            )
            
            # Close connection
            writer.close()
            await writer.wait_closed()
            
            # Parse response
            if not response_data:
                return {
                    "success": False,
                    "error": "Empty response from daemon"
                }
            
            response = json.loads(response_data.decode())
            logger.debug(f"Received KSI response: {response.get('success', False)}")
            
            return response
            
        except asyncio.TimeoutError:
            logger.error(f"KSI operation timed out after {timeout}s")
            return {
                "success": False,
                "error": f"Operation timed out after {timeout}s"
            }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode KSI response: {e}")
            return {
                "success": False,
                "error": f"Invalid JSON response: {str(e)}"
            }
        except ConnectionError as e:
            logger.error(f"Connection to KSI daemon failed: {e}")
            return {
                "success": False,
                "error": f"Connection failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in KSI communication: {e}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }
    
    def _validate_daemon_running(self) -> bool:
        """Check if KSI daemon is running"""
        return self.socket_path.exists()
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the KSI daemon
        
        Returns:
            Health status information
        """
        response = await self.send_event("system:health", {})
        
        if response.get("success", False):
            return {
                "status": "healthy",
                "daemon_running": True,
                "details": response
            }
        else:
            return {
                "status": "unhealthy",
                "daemon_running": self._validate_daemon_running(),
                "error": response.get("error", "Unknown error")
            }
    
    async def stream_events(
        self,
        subscription_id: str,
        timeout: Optional[float] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream events from a subscription
        
        Args:
            subscription_id: Subscription to stream from
            timeout: Optional timeout for each poll
            
        Yields:
            Event dictionaries
        """
        poll_timeout = timeout or 1.0
        
        while True:
            # Poll for new events
            result = await self.send_event(
                "observation:poll",
                {
                    "subscription_id": subscription_id,
                    "timeout": int(poll_timeout * 1000)  # Convert to ms
                }
            )
            
            if not result.get("success", False):
                logger.error(f"Failed to poll subscription: {result.get('error')}")
                break
                
            events = result.get("observations", [])
            for event in events:
                yield event
            
            # Brief pause if no events
            if not events:
                await asyncio.sleep(0.1)
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get OpenAI-compatible tool schema
        
        This should be overridden by subclasses to provide proper schema
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    
    async def run(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the tool operation
        
        This must be overridden by subclasses
        """
        raise NotImplementedError("Subclasses must implement run()")
    
    def __repr__(self) -> str:
        """String representation"""
        return f"{self.__class__.__name__}(socket={self.socket_path})"