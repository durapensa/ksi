#!/usr/bin/env python3
"""
KSI Daemon Control Script

Python-based daemon control using ksi_common configuration system.
Eliminates hardcoded paths and provides proper environment variable support.

Usage: python3 daemon_control.py {start|stop|restart|status|health}
"""

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

# Configure logging BEFORE importing ksi modules
from ksi_common.logging import configure_structlog

# Get configuration from environment or defaults
log_level = os.environ.get('KSI_LOG_LEVEL', 'INFO')
log_format = os.environ.get('KSI_LOG_FORMAT', 'console')

# Configure structlog for daemon_control only (daemon will configure separately)
configure_structlog(
    log_level=log_level,
    log_format=log_format,
    force_disable_console=False  # Allow console for daemon_control itself
)

# NOW import ksi modules
from ksi_common import config
import structlog

logger = structlog.get_logger("ksi.daemon_control")

class DaemonController:
    """Controls KSI daemon using proper config system."""
    
    def __init__(self):
        """Initialize controller with config-based paths."""
        # All paths from config - no hardcoding
        self.daemon_script = "ksi-daemon.py"
        self.pid_file = config.daemon_pid_file
        self.socket_path = config.socket_path
        self.log_dir = config.log_dir
        self.venv_dir = Path(".venv")
        
        # Ensure directories exist using config
        config.ensure_directories()
    
    def _check_venv(self) -> bool:
        """Check if virtual environment exists."""
        if not self.venv_dir.exists():
            logger.error(f"Virtual environment not found: {self.venv_dir}")
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
    
    def _send_socket_event(self, event: str, data: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Send JSON event to daemon socket."""
        if data is None:
            data = {}
        
        event_json = {
            "event": event,
            "data": data
        }
        
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect(str(self.socket_path))
            
            message = json.dumps(event_json) + '\n'
            sock.send(message.encode())
            
            response = sock.recv(4096).decode()
            sock.close()
            
            return json.loads(response.strip())
        except Exception as e:
            logger.warning(f"Socket communication failed: {e}")
            return None
    
    def start(self) -> int:
        """Start the daemon."""
        if not self._check_venv():
            return 1
        
        # Check if already running
        pid = self._read_pid()
        if pid and self._is_process_running(pid):
            print(f"Daemon already running (PID: {pid})")
            return 0
        
        # Clean up stale PID file
        if self.pid_file.exists():
            logger.info("Cleaning up stale PID file")
            self.pid_file.unlink()
        
        # Clean up stale socket file
        if self.socket_path.exists():
            logger.info("Cleaning up stale socket file")
            self.socket_path.unlink()
        
        print("Starting KSI daemon...")
        
        # Prepare environment with config values
        env = os.environ.copy()
        env.update({
            "KSI_LOG_LEVEL": config.log_level,
            "KSI_LOG_FORMAT": config.log_format,
            "KSI_LOG_STRUCTURED": "true"
        })
        
        # Start daemon process
        try:
            python_path = self.venv_dir / "bin" / "python3"
            cmd = [str(python_path), self.daemon_script]
            
            # Redirect stdout/stderr to startup log using config paths
            startup_log = config.daemon_log_dir / "daemon_startup.log"
            
            with open(startup_log, 'w') as log_file:
                # Start daemon in background with startup log
                process = subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True
                )
            
            # Wait a moment for daemon to start
            time.sleep(2)
            
            # Check if daemon started successfully
            pid = self._read_pid()
            if pid and self._is_process_running(pid):
                print(f"✓ Daemon started successfully (PID: {pid})")
                print(f"  Socket: {self.socket_path}")
                print(f"  Logs: {self.log_dir}")
                return 0
            else:
                print("✗ Daemon failed to start")
                return 1
                
        except Exception as e:
            logger.error(f"Failed to start daemon: {e}")
            print(f"✗ Failed to start daemon: {e}")
            return 1
    
    def stop(self) -> int:
        """Stop the daemon gracefully."""
        pid = self._read_pid()
        if not pid:
            print("Daemon not running (no PID file)")
            return 0
        
        if not self._is_process_running(pid):
            print("Daemon not running (process not found)")
            # Clean up stale PID file
            if self.pid_file.exists():
                self.pid_file.unlink()
            return 0
        
        print(f"Stopping daemon (PID: {pid})...")
        
        # Try graceful shutdown via socket first
        result = self._send_socket_event("system:shutdown")
        if result:
            print("Sent graceful shutdown command")
            
            # Wait for graceful shutdown
            for i in range(10):  # Wait up to 10 seconds
                time.sleep(1)
                if not self._is_process_running(pid):
                    print("✓ Daemon stopped gracefully")
                    return 0
            
            print("Graceful shutdown timeout, sending SIGTERM...")
        
        # Send SIGTERM
        try:
            os.kill(pid, signal.SIGTERM)
            
            # Wait for process to terminate
            for i in range(5):  # Wait up to 5 seconds
                time.sleep(1)
                if not self._is_process_running(pid):
                    print("✓ Daemon stopped")
                    return 0
            
            # Force kill if still running
            print("Process still running, sending SIGKILL...")
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)
            
            if not self._is_process_running(pid):
                print("✓ Daemon force-stopped")
                return 0
            else:
                print("✗ Failed to stop daemon")
                return 1
                
        except (OSError, ProcessLookupError) as e:
            logger.warning(f"Error stopping process: {e}")
            print("✓ Daemon already stopped")
            return 0
    
    def restart(self) -> int:
        """Restart the daemon."""
        print("Restarting daemon...")
        stop_result = self.stop()
        if stop_result != 0:
            return stop_result
        
        # Brief pause between stop and start
        time.sleep(1)
        return self.start()
    
    def status(self) -> int:
        """Show daemon status."""
        pid = self._read_pid()
        
        if not pid:
            print("Daemon: Not running (no PID file)")
            return 1
        
        if not self._is_process_running(pid):
            print(f"Daemon: Not running (stale PID file: {pid})")
            return 1
        
        print(f"Daemon: Running (PID: {pid})")
        print(f"  PID file: {self.pid_file}")
        print(f"  Socket: {self.socket_path}")
        print(f"  Socket exists: {self.socket_path.exists()}")
        print(f"  Log directory: {self.log_dir}")
        print(f"  Response logs: {config.response_log_dir}")
        
        return 0
    
    def health(self) -> int:
        """Check daemon health via socket."""
        pid = self._read_pid()
        
        if not pid or not self._is_process_running(pid):
            print("Daemon not running")
            return 1
        
        print(f"Daemon running (PID: {pid})")
        
        # Check socket health
        result = self._send_socket_event("system:health")
        if result:
            print("✓ Socket communication working")
            
            if "agents" in result:
                agents = result["agents"]
                print(f"  Active agents: {len(agents)}")
                for agent in agents[:5]:  # Show first 5
                    print(f"    - {agent}")
            
            if "processes" in result:
                processes = result["processes"]
                print(f"  Active processes: {len(processes)}")
            
            return 0
        else:
            print("✗ Socket communication failed")
            return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="KSI Daemon Control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 daemon_control.py start    # Start daemon
  python3 daemon_control.py stop     # Stop daemon gracefully
  python3 daemon_control.py restart  # Restart daemon
  python3 daemon_control.py status   # Show status
  python3 daemon_control.py health   # Check health via socket
        """
    )
    
    parser.add_argument(
        "command",
        choices=["start", "stop", "restart", "status", "health"],
        help="Command to execute"
    )
    
    args = parser.parse_args()
    
    controller = DaemonController()
    
    if args.command == "start":
        return controller.start()
    elif args.command == "stop":
        return controller.stop()
    elif args.command == "restart":
        return controller.restart()
    elif args.command == "status":
        return controller.status()
    elif args.command == "health":
        return controller.health()
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())