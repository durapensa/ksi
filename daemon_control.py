#!/usr/bin/env python3
"""
KSI Daemon Control Script

Python-based daemon control using ksi_common configuration system.
Eliminates hardcoded paths and provides proper environment variable support.

Usage: ./daemon_control.py {start|stop|restart|status|health|dev}
"""

import os
import sys
from pathlib import Path

# Ensure we're running in the virtual environment
venv_dir = Path(__file__).parent / ".venv"
if venv_dir.exists() and hasattr(sys, 'real_prefix') is False and hasattr(sys, 'base_prefix') and sys.base_prefix == sys.prefix:
    # We're not in a venv, re-execute with venv python
    venv_python = venv_dir / "bin" / "python3"
    if venv_python.exists():
        os.execv(str(venv_python), [str(venv_python)] + sys.argv)
    else:
        print(f"Error: Virtual environment python not found at {venv_python}")
        print("Please run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt")
        sys.exit(1)

# Now we can safely import everything
import argparse
import asyncio
import json
import signal
import socket
import subprocess
import time
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
            
            # For shutdown events, listen for both notification and completion events
            if event == "system:shutdown":
                try:
                    # Set timeout for shutdown events  
                    sock.settimeout(config.daemon_shutdown_socket_timeout)
                    
                    # Collect all messages until socket closes or timeout
                    messages = []
                    buffer = ""
                    
                    while True:
                        try:
                            chunk = sock.recv(4096).decode()
                            if not chunk:
                                break  # Socket closed
                            
                            buffer += chunk
                            # Split on newlines to handle multiple JSON messages
                            lines = buffer.split('\n')
                            buffer = lines[-1]  # Keep incomplete line in buffer
                            
                            for line in lines[:-1]:
                                line = line.strip()
                                if line:
                                    try:
                                        msg = json.loads(line)
                                        messages.append(msg)
                                    except json.JSONDecodeError:
                                        pass
                                        
                        except socket.timeout:
                            break  # No more data
                        except Exception:
                            break  # Connection closed
                    
                    sock.close()
                    
                    # Check if we received shutdown notification
                    got_notification = any(msg.get("event") == "system:shutdown_notification" for msg in messages)
                    
                    if got_notification:
                        return {"status": "shutdown_confirmed"}
                    else:
                        return {"status": "sent"}
                        
                except Exception:
                    # Connection closed or other error - this is expected during shutdown
                    sock.close()
                    return {"status": "sent"}
            
            # For other events, read the response normally
            response = sock.recv(4096).decode()
            sock.close()
            
            return json.loads(response.strip())
            
        except Exception as e:
            logger.warning(f"Socket communication failed: {e}")
            return None
    
    async def start(self, debug: bool = False) -> int:
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
        
        if debug:
            print("Starting KSI daemon with DEBUG logging...")
        else:
            print("Starting KSI daemon...")
        
        # Prepare environment with config values
        env = os.environ.copy()
        env.update({
            "KSI_LOG_LEVEL": "DEBUG" if debug else config.log_level,
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
            pid = await wait_for_pid()
            if pid and self._is_process_running(pid):
                print(f"✓ Daemon started successfully (PID: {pid})")
                print(f"  Socket: {self.socket_path}")
                print(f"  Logs: {self.log_dir}")
                return 0
            else:
                print("✗ Daemon failed to start (no PID file created)")
                # Show startup log if it exists and has content
                if startup_log.exists() and startup_log.stat().st_size > 0:
                    print("\nStartup log:")
                    print(startup_log.read_text()[-500:])  # Last 500 chars
                else:
                    # If startup log is empty (due to daemonization), check daemon.log
                    daemon_log = config.daemon_log_file
                    if daemon_log.exists():
                        print("\nRecent daemon log entries:")
                        try:
                            # Read last few lines of daemon.log
                            result = subprocess.run(
                                ["tail", "-n", "20", str(daemon_log)],
                                capture_output=True,
                                text=True
                            )
                            if result.stdout:
                                print(result.stdout)
                        except Exception:
                            # Fallback to reading file directly
                            content = daemon_log.read_text()
                            lines = content.splitlines()
                            print('\n'.join(lines[-20:]))  # Last 20 lines
                return 1
                
        except Exception as e:
            logger.error(f"Failed to start daemon: {e}")
            print(f"✗ Failed to start daemon: {e}")
            return 1
    
    async def stop(self) -> int:
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
                # We received the shutdown_notification event
                print("✓ Daemon shutdown confirmed")
                # Socket closure is the definitive shutdown signal
            else:
                # Shutdown command was sent but we didn't get the notification
                # Socket may have closed before sending notification
                print("Shutdown command sent")
                # Wait for graceful shutdown using config timeout
                grace_period = config.daemon_shutdown_grace_period
                waited = 0.0
                check_interval = 0.1
                
                while waited < grace_period:
                    if not self._is_process_running(pid):
                        print(f"✓ Daemon stopped gracefully after {waited:.1f}s")
                        # Clean up files
                        if self.pid_file.exists():
                            self.pid_file.unlink()
                        if self.socket_path.exists():
                            self.socket_path.unlink()
                        return 0
                    await asyncio.sleep(check_interval)
                    waited += check_interval
                
                print(f"Daemon still running after {grace_period}s grace period")
        else:
            # Socket already closed or unreachable
            print("Socket not responding, checking process...")
        
        # If we get here, graceful shutdown failed - use SIGTERM as fallback
        try:
            os.kill(pid, signal.SIGTERM)
            print("Sent SIGTERM to force shutdown")
            
            # Wait for process to terminate using config timeout
            wait_time = config.daemon_kill_timeout
            check_interval = 0.1
            waited = 0.0
            
            while waited < wait_time:
                if not self._is_process_running(pid):
                    print(f"✓ Daemon stopped after {waited:.1f}s")
                    # Clean up PID file if it exists
                    if self.pid_file.exists():
                        self.pid_file.unlink()
                    # Clean up socket file if it exists
                    if self.socket_path.exists():
                        self.socket_path.unlink()
                    return 0
                await asyncio.sleep(check_interval)
                waited += check_interval
            
            # If still running after wait, check one more time
            if not self._is_process_running(pid):
                print("✓ Daemon stopped")
                if self.pid_file.exists():
                    self.pid_file.unlink()
                if self.socket_path.exists():
                    self.socket_path.unlink()
                return 0
            else:
                print(f"✗ Daemon still running after {wait_time}s wait")
                return 1
                
        except (OSError, ProcessLookupError) as e:
            # Process doesn't exist
            print("✓ Daemon already stopped")
            # Clean up stale PID file
            if self.pid_file.exists():
                self.pid_file.unlink()
            # Clean up stale socket file
            if self.socket_path.exists():
                self.socket_path.unlink()
            return 0
    
    async def restart(self, debug: bool = False) -> int:
        """Restart the daemon."""
        print("Restarting daemon...")
        stop_result = await self.stop()
        if stop_result != 0:
            return stop_result
        
        # Start immediately after stop
        return await self.start(debug=debug)
    
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

    async def dev(self, debug: bool = False) -> int:
        """Run daemon in development mode with auto-restart on file changes."""
        print("Starting KSI daemon in development mode...")
        if debug:
            print("Debug logging enabled")
        print("Ensuring clean development mode startup...")
        
        # Always stop any running daemon first (like restart command)
        await self.stop()
        
        # Set dev mode environment variable
        os.environ["KSI_DEV_MODE"] = "true"
        
        print("Watching for changes in .py files...")
        print("Press Ctrl+C to stop\n")
        
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
        start_result = await self.start(debug=debug)
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
                await self.restart()
                
                print("Daemon restarted successfully")
                print("Watching for changes...\n")
                
        except KeyboardInterrupt:
            print("\n\nStopping development mode...")
            await self.stop()
            print("Development mode stopped")
            return 0
        except Exception as e:
            logger.error(f"Dev mode error: {e}", exc_info=True)
            await self.stop()
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
  python3 daemon_control.py --debug start  # Start with debug logging
        """
    )
    
    parser.add_argument(
        "command",
        choices=["start", "stop", "restart", "status", "health", "dev"],
        help="Command to execute"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging (sets KSI_LOG_LEVEL=DEBUG)"
    )
    
    args = parser.parse_args()
    
    controller = DaemonController()
    
    if args.command == "start":
        return asyncio.run(controller.start(debug=args.debug))
    elif args.command == "stop":
        return asyncio.run(controller.stop())
    elif args.command == "restart":
        return asyncio.run(controller.restart(debug=args.debug))
    elif args.command == "status":
        return controller.status()
    elif args.command == "health":
        return controller.health()
    elif args.command == "dev":
        return asyncio.run(controller.dev(debug=args.debug))
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())