#!/usr/bin/env python3
"""
Minimal synchronous client for KSI daemon communication.

This provides a lightweight, synchronous interface for communicating with the KSI daemon
via Unix sockets. It's designed for use cases where async is not needed or desired,
such as hooks, simple scripts, or synchronous utilities.

No discovery, no daemon management, just simple request/response.
"""

import json
import socket
from typing import Dict, Any, Optional
from pathlib import Path


class KSIConnectionError(Exception):
    """Raised when connection to daemon fails"""
    pass


class KSIResponseError(Exception):
    """Raised when daemon returns an error response"""
    pass


class MinimalSyncClient:
    """Minimal synchronous client for KSI daemon - no discovery, no daemon management."""
    
    def __init__(self, socket_path: Optional[str] = None, timeout: float = 2.0):
        """Initialize client.
        
        Args:
            socket_path: Path to Unix socket. If None, uses default locations.
            timeout: Socket timeout in seconds
        """
        self.socket_path = socket_path or self._find_socket_path()
        self.timeout = timeout
        
    def _find_socket_path(self) -> str:
        """Find the daemon socket path."""
        # Check common locations
        paths_to_try = [
            Path.cwd() / "var/run/daemon.sock",
            Path.home() / ".ksi/var/run/daemon.sock",
            Path("/tmp/ksi/daemon.sock"),
        ]
        
        for path in paths_to_try:
            if path.exists():
                return str(path)
                
        # Default to project-relative path
        return str(Path.cwd() / "var/run/daemon.sock")
        
    def send_event(self, event: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send event and return response data.
        
        Args:
            event: Event name (e.g., "system:health")
            data: Event data dictionary
            
        Returns:
            Response data from daemon
            
        Raises:
            KSIConnectionError: If connection fails
            KSIResponseError: If daemon returns error
        """
        if data is None:
            data = {}
            
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        
        try:
            # Connect
            try:
                sock.connect(self.socket_path)
            except (ConnectionRefusedError, FileNotFoundError) as e:
                raise KSIConnectionError(f"Cannot connect to daemon at {self.socket_path}: {e}")
            
            # Send request
            request = {"event": event, "data": data}
            sock.sendall(json.dumps(request).encode() + b'\n')
            
            # Read response
            response_bytes = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response_bytes += chunk
                
                # Check if we have complete JSON
                try:
                    # Quick check for balanced braces
                    if response_bytes.count(b'{') == response_bytes.count(b'}') and response_bytes.count(b'{') > 0:
                        # Try to parse to confirm it's complete
                        json.loads(response_bytes.decode())
                        break
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Not complete yet, keep reading
                    continue
            
            # Parse response
            try:
                envelope = json.loads(response_bytes.decode())
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                raise KSIResponseError(f"Invalid response from daemon: {e}")
            
            # Check for error
            if "error" in envelope:
                raise KSIResponseError(f"Daemon error: {envelope['error']}")
                
            # Return data
            return envelope.get("data", {})
            
        except socket.timeout:
            raise KSIConnectionError(f"Timeout waiting for daemon response ({self.timeout}s)")
        finally:
            sock.close()
    
    def send_event_raw(self, event: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send event and return full response envelope.
        
        This returns the complete response including metadata like correlation_id,
        timestamp, etc. Use send_event() for just the data portion.
        
        Args:
            event: Event name
            data: Event data
            
        Returns:
            Full response envelope
        """
        if data is None:
            data = {}
            
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        
        try:
            # Connect
            try:
                sock.connect(self.socket_path)
            except (ConnectionRefusedError, FileNotFoundError) as e:
                raise KSIConnectionError(f"Cannot connect to daemon at {self.socket_path}: {e}")
            
            # Send request
            request = {"event": event, "data": data}
            sock.sendall(json.dumps(request).encode() + b'\n')
            
            # Read response
            response_bytes = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response_bytes += chunk
                
                # Check if we have complete JSON
                try:
                    if response_bytes.count(b'{') == response_bytes.count(b'}') and response_bytes.count(b'{') > 0:
                        json.loads(response_bytes.decode())
                        break
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
            
            # Parse and return full envelope
            try:
                return json.loads(response_bytes.decode())
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                raise KSIResponseError(f"Invalid response from daemon: {e}")
                
        except socket.timeout:
            raise KSIConnectionError(f"Timeout waiting for daemon response ({self.timeout}s)")
        finally:
            sock.close()
    
    def is_daemon_running(self) -> bool:
        """Check if daemon is running by attempting to connect.
        
        Returns:
            True if daemon is reachable, False otherwise
        """
        try:
            self.send_event("system:health")
            return True
        except KSIConnectionError:
            return False