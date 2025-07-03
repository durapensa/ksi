#!/usr/bin/env python3
"""
KSI Daemon Control Script

Python-based daemon control using ksi_common configuration system.
Eliminates hardcoded paths and provides proper environment variable support.

Usage: python3 daemon_control.py {start|stop|restart|status|health|dev}
"""

import argparse
import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, Set

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
            # No timeout - we'll handle responses appropriately
            sock.connect(str(self.socket_path))
            
            message = json.dumps(event_json) + '\n'
            sock.send(message.encode())
            
            # For shutdown events, listen for the shutdown notification
            if event == "system:shutdown":
                try:
                    # Set a short timeout just for shutdown
                    sock.settimeout(0.5)
                    response = sock.recv(4096).decode()
                    
                    # Check if we got a shutdown notification
                    if response:
                        try:
                            msg = json.loads(response.strip())
                            if msg.get("event") == "system:shutdown_notification":
                                logger.info("Received shutdown notification from daemon")
                                sock.close()
                                return {"status": "shutdown_confirmed"}
                        except json.JSONDecodeError:
                            pass
                    
                    sock.close()
                    return {"status": "sent"}
                    
                except socket.timeout:
                    # This is OK for shutdown
                    sock.close()
                    return {"status": "sent"}
                except Exception:
                    # Connection closed by daemon - this is expected
                    sock.close()
                    return {"status": "sent"}
            
            # For other events, read the response normally
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
            
            # Remove any stale PID file first
            if self.pid_file.exists():
                self.pid_file.unlink()
            
            with open(startup_log, 'w') as log_file:
                # Start daemon in background with startup log
                process = subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True
                )
            
            # Wait for daemon to create PID file
            async def wait_for_pid():
                """Poll for PID file creation."""
                for _ in range(50):  # 5 seconds total
                    if self.pid_file.exists():
                        content = self.pid_file.read_text().strip()
                        if content and content.isdigit():
                            return int(content)
                    await asyncio.sleep(0.1)
                return None
            
            # Check for PID file
            pid = asyncio.run(wait_for_pid())
            if pid and self._is_process_running(pid):
                print(f"✓ Daemon started successfully (PID: {pid})")
                print(f"  Socket: {self.socket_path}")
                print(f"  Logs: {self.log_dir}")
                return 0
            else:
                print("✗ Daemon failed to start (no PID file created)")
                # Show startup log if it exists
                if startup_log.exists():
                    print("\nStartup log:")
                    print(startup_log.read_text()[-500:])  # Last 500 chars
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
            if result.get("status") == "shutdown_confirmed":
                print("✓ Daemon acknowledged shutdown")
            else:
                print("Sent graceful shutdown command")
            
            # Watch for PID file removal instead of sleeping
            async def wait_for_pid_removal():
                """Wait for daemon to remove its PID file."""
                if not self.pid_file.exists():
                    return True
                    
                from watchfiles import awatch
                try:
                    async for changes in awatch(str(self.pid_file.parent), stop_event=asyncio.Event()):
                        for change_type, path in changes:
                            if path == str(self.pid_file) and not self.pid_file.exists():
                                return True
                except Exception:
                    # Fallback to checking if file still exists
                    return not self.pid_file.exists()
            
            try:
                # Wait up to 3 seconds for PID file removal (shorter if we got confirmation)
                timeout = 3.0 if result.get("status") == "shutdown_confirmed" else 5.0
                removed = asyncio.run(asyncio.wait_for(wait_for_pid_removal(), timeout=timeout))
                
                if removed:
                    print("✓ Daemon stopped gracefully")
                    return 0
                else:
                    print("Graceful shutdown timeout, sending SIGTERM...")
            except asyncio.TimeoutError:
                print("Graceful shutdown timeout, sending SIGTERM...")
        
        # Send SIGTERM
        try:
            os.kill(pid, signal.SIGTERM)
            
            # Watch for process termination
            async def wait_for_process_exit():
                """Wait for process to exit."""
                while self._is_process_running(pid):
                    await asyncio.sleep(0.1)
                return True
            
            try:
                # Wait up to 3 seconds for process to terminate
                asyncio.run(asyncio.wait_for(wait_for_process_exit(), timeout=3.0))
                print("✓ Daemon stopped")
                return 0
            except asyncio.TimeoutError:
                pass  # Fall through to SIGKILL
            
            # Force kill if still running
            print("Process still running, sending SIGKILL...")
            try:
                os.kill(pid, signal.SIGKILL)
                
                # SIGKILL should be immediate, just verify
                time.sleep(0.1)  # Brief pause to let OS clean up
                if not self._is_process_running(pid):
                    print("✓ Daemon force-stopped")
                    return 0
                else:
                    print("✗ Failed to stop daemon")
                    return 1
            except (OSError, ProcessLookupError):
                # Process died between checks
                print("✓ Daemon stopped")
                return 0
                
        except (OSError, ProcessLookupError) as e:
            # Process doesn't exist or we don't have permission
            logger.info(f"Process {pid} not found: {e}")
            print("✓ Daemon already stopped")
            # Clean up stale PID file
            if self.pid_file.exists():
                self.pid_file.unlink()
            return 0
    
    def restart(self) -> int:
        """Restart the daemon."""
        print("Restarting daemon...")
        stop_result = self.stop()
        if stop_result != 0:
            return stop_result
        
        # Start immediately after stop
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

    async def dev(self) -> int:
        """Run daemon in development mode with auto-restart on file changes."""
        print("Starting KSI daemon in development mode...")
        print("Watching for changes in .py files...")
        print("Press Ctrl+C to stop\n")
        
        # Set dev mode environment variable
        os.environ["KSI_DEV_MODE"] = "true"
        
        # Import watchfiles here to avoid dependency for non-dev usage
        try:
            from watchfiles import awatch
        except ImportError:
            logger.error("watchfiles not installed. Run: pip install watchfiles")
            return 1
        
        # Directories to watch
        watch_dirs = [
            Path("ksi_daemon"),
            Path("ksi_common"),
            Path("ksi_client")
        ]
        
        # Filter out non-existent directories
        watch_paths = [str(d) for d in watch_dirs if d.exists()]
        
        if not watch_paths:
            logger.error("No source directories found to watch")
            return 1
        
        # Start daemon initially
        print("Starting daemon with checkpoint support...")
        start_result = self.start()
        if start_result != 0:
            return start_result
        
        print("✓ Daemon started in dev mode")
        
        restart_count = 0
        
        try:
            # Watch for changes
            async for changes in awatch(*watch_paths):
                # Filter for Python files only
                py_changes = [
                    (change_type, path) 
                    for change_type, path in changes 
                    if path.endswith('.py')
                ]
                
                if not py_changes:
                    continue
                
                restart_count += 1
                print(f"\n{'='*60}")
                print(f"[Restart #{restart_count}] Detected changes:")
                for change_type, path in py_changes[:5]:  # Show first 5 changes
                    print(f"  - {change_type.name}: {path}")
                if len(py_changes) > 5:
                    print(f"  ... and {len(py_changes) - 5} more changes")
                
                print("\nCreating checkpoint...")
                
                # Try to checkpoint state before restart
                checkpoint_result = self._send_socket_event("dev:checkpoint")
                if checkpoint_result and checkpoint_result.get("status") == "saved":
                    print(f"✓ Checkpoint saved: {checkpoint_result.get('sessions', 0)} sessions, "
                          f"{checkpoint_result.get('active_requests', 0)} active requests")
                else:
                    print("⚠ Checkpoint failed - state will be lost")
                
                print("Restarting daemon...")
                
                # Restart daemon
                self.restart()
                
                print("Daemon restarted successfully")
                print("Watching for changes...\n")
                
        except KeyboardInterrupt:
            print("\n\nStopping development mode...")
            self.stop()
            print("Development mode stopped")
            return 0
        except Exception as e:
            logger.error(f"Dev mode error: {e}", exc_info=True)
            self.stop()
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
  python3 daemon_control.py dev      # Development mode with auto-restart
        """
    )
    
    parser.add_argument(
        "command",
        choices=["start", "stop", "restart", "status", "health", "dev"],
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
    elif args.command == "dev":
        return asyncio.run(controller.dev())
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())