#!/usr/bin/env python3
"""
KSI Daemon Manager

Handles daemon lifecycle management including:
- Automatic venv activation
- Starting daemon if not running
- Health checks and restarts
- Graceful shutdown
"""

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any
import structlog

from .exceptions import KSIDaemonError, KSITimeoutError

logger = structlog.get_logger("ksi.client.daemon_manager")


class DaemonManager:
    """Manages KSI daemon lifecycle."""
    
    def __init__(self):
        """Initialize with paths from current working directory."""
        # Paths relative to project root
        self.project_root = Path.cwd()
        self.venv_path = self.project_root / ".venv"
        self.daemon_script = "ksi-daemon.py"
        self.pid_file = self.project_root / "var/run/ksi_daemon.pid"
        self.socket_path = self.project_root / "var/run/daemon.sock"
        self.log_dir = self.project_root / "var/logs"
        self.daemon_log_dir = self.log_dir / "daemon"
        
        # Daemon startup timeout
        self.startup_timeout = 10.0  # seconds
        self.health_check_retries = 5
        self.health_check_delay = 1.0  # seconds between retries
    
    def _ensure_directories(self):
        """Ensure required directories exist."""
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.daemon_log_dir.mkdir(parents=True, exist_ok=True)
    
    def _check_venv(self) -> bool:
        """Check if virtual environment exists."""
        if not self.venv_path.exists():
            logger.error(f"Virtual environment not found: {self.venv_path}")
            return False
        
        python_path = self.venv_path / "bin" / "python3"
        if not python_path.exists():
            logger.error(f"Python not found in venv: {python_path}")
            return False
            
        return True
    
    def _read_pid(self) -> Optional[int]:
        """Read PID from PID file."""
        try:
            if not self.pid_file.exists():
                return None
            
            pid_str = self.pid_file.read_text().strip()
            if not pid_str:
                return None
                
            return int(pid_str)
        except (ValueError, OSError) as e:
            logger.warning(f"Error reading PID file: {e}")
            return None
    
    def _is_process_running(self, pid: int) -> bool:
        """Check if process is running."""
        try:
            os.kill(pid, 0)  # Signal 0 just checks if process exists
            return True
        except (OSError, ProcessLookupError):
            return False
    
    async def _check_socket_health(self) -> bool:
        """Check if daemon is healthy via socket."""
        try:
            # Try to connect and send health check
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(str(self.socket_path)),
                timeout=2.0
            )
            
            # Send health check event
            health_event = json.dumps({
                "event": "system:health",
                "data": {}
            }) + '\n'
            
            writer.write(health_event.encode())
            await writer.drain()
            
            # Read response
            response_data = await asyncio.wait_for(
                reader.readline(),
                timeout=2.0
            )
            
            writer.close()
            await writer.wait_closed()
            
            # Parse response - socket now returns JSON envelope with REST pattern
            envelope = json.loads(response_data.decode().strip())
            
            # Handle envelope format
            if "error" in envelope:
                return False
            
            # Handle REST pattern: single object or array
            response_data = envelope.get("data")
            if isinstance(response_data, dict):
                # Single health response
                return response_data.get("status") == "healthy"
            elif isinstance(response_data, list):
                # Multiple health responses
                return any(
                    isinstance(item, dict) and item.get("status") == "healthy" 
                    for item in response_data
                )
            else:
                return False
            
        except Exception as e:
            logger.debug(f"Socket health check failed: {e}")
            return False
    
    def _clean_stale_files(self):
        """Clean up stale PID and socket files."""
        if self.pid_file.exists():
            logger.info("Cleaning up stale PID file")
            self.pid_file.unlink()
        
        if self.socket_path.exists():
            logger.info("Cleaning up stale socket file")
            self.socket_path.unlink()
    
    async def _start_daemon(self) -> bool:
        """Start the daemon process."""
        logger.info("Starting KSI daemon...")
        
        # Ensure directories exist
        self._ensure_directories()
        
        # Clean up stale files
        self._clean_stale_files()
        
        # Prepare environment
        env = os.environ.copy()
        env.update({
            "KSI_LOG_LEVEL": os.environ.get("KSI_LOG_LEVEL", "INFO"),
            "KSI_LOG_FORMAT": os.environ.get("KSI_LOG_FORMAT", "console"),
            "KSI_LOG_STRUCTURED": "true"
        })
        
        # Start daemon process
        try:
            python_path = self.venv_path / "bin" / "python3"
            cmd = [str(python_path), self.daemon_script]
            
            # Redirect output to startup log
            startup_log = self.daemon_log_dir / "daemon_startup.log"
            
            with open(startup_log, 'w') as log_file:
                process = subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    cwd=str(self.project_root)
                )
            
            # Wait for daemon to start
            await asyncio.sleep(2.0)
            
            # Check if daemon started successfully
            pid = self._read_pid()
            if pid and self._is_process_running(pid):
                logger.info(f"Daemon started successfully (PID: {pid})")
                return True
            else:
                logger.error("Daemon failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start daemon: {e}")
            return False
    
    async def _stop_daemon(self) -> bool:
        """Stop the daemon gracefully."""
        pid = self._read_pid()
        if not pid:
            logger.debug("No daemon PID found")
            return True
        
        if not self._is_process_running(pid):
            logger.debug("Daemon process not running")
            self._clean_stale_files()
            return True
        
        logger.info(f"Stopping daemon (PID: {pid})...")
        
        # Try graceful shutdown via socket first
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(str(self.socket_path)),
                timeout=2.0
            )
            
            shutdown_event = json.dumps({
                "event": "system:shutdown",
                "data": {}
            }) + '\n'
            
            writer.write(shutdown_event.encode())
            await writer.drain()
            
            writer.close()
            await writer.wait_closed()
            
            # Wait for process to exit
            for _ in range(10):
                if not self._is_process_running(pid):
                    logger.info("Daemon stopped gracefully")
                    self._clean_stale_files()
                    return True
                await asyncio.sleep(0.5)
                
        except Exception as e:
            logger.warning(f"Graceful shutdown failed: {e}")
        
        # Force kill if still running
        try:
            os.kill(pid, signal.SIGKILL)
            logger.warning("Daemon force killed")
            self._clean_stale_files()
            return True
        except Exception as e:
            logger.error(f"Failed to kill daemon: {e}")
            return False
    
    async def ensure_daemon_running(self) -> bool:
        """
        Ensure daemon is running and healthy.
        
        Returns:
            True if daemon is running and healthy, False otherwise
        """
        if not self._check_venv():
            raise KSIDaemonError("Virtual environment not found")
        
        # Check if daemon process exists
        pid = self._read_pid()
        if pid and self._is_process_running(pid):
            # Process exists, check health
            for i in range(self.health_check_retries):
                if await self._check_socket_health():
                    logger.debug("Daemon is healthy")
                    return True
                
                if i < self.health_check_retries - 1:
                    await asyncio.sleep(self.health_check_delay)
            
            # Daemon unhealthy, restart
            logger.warning("Daemon unhealthy, restarting...")
            await self._stop_daemon()
        
        # Start daemon
        if not await self._start_daemon():
            raise KSIDaemonError("Failed to start daemon")
        
        # Wait for daemon to be ready
        start_time = time.time()
        while time.time() - start_time < self.startup_timeout:
            if await self._check_socket_health():
                logger.info("Daemon is ready")
                return True
            await asyncio.sleep(0.5)
        
        raise KSITimeoutError("Daemon startup timeout")
    
    async def stop_daemon(self) -> bool:
        """Stop the daemon if running."""
        return await self._stop_daemon()
    
    def get_daemon_info(self) -> Dict[str, Any]:
        """Get current daemon status information."""
        pid = self._read_pid()
        running = pid and self._is_process_running(pid) if pid else False
        
        return {
            "pid": pid,
            "running": running,
            "pid_file": str(self.pid_file),
            "socket_path": str(self.socket_path),
            "socket_exists": self.socket_path.exists(),
            "log_dir": str(self.log_dir)
        }