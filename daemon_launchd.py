#!/usr/bin/env python3
"""
KSI Daemon Control using macOS launchd
Simple daemon management without external dependencies
"""

import subprocess
import sys
from pathlib import Path
import json
import socket
import os

# Configuration
PLIST_FILE = "com.ksi.daemon.plist"
DAEMON_LABEL = "com.ksi.daemon"
PROJECT_DIR = Path(__file__).parent
PLIST_PATH = PROJECT_DIR / PLIST_FILE
DAEMON_SOCKET = Path("/tmp/ksi/daemon.sock")

def run_command(cmd, check=True):
    """Run shell command and return result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if check and result.returncode != 0:
            print(f"Error: {result.stderr.strip()}")
            return None
        return result
    except Exception as e:
        print(f"Command failed: {e}")
        return None

def daemon_status():
    """Check if daemon is running via launchctl"""
    result = run_command(f"launchctl list | grep {DAEMON_LABEL}", check=False)
    if result and result.returncode == 0:
        # Parse launchctl output: PID STATUS LABEL
        parts = result.stdout.strip().split()
        if len(parts) >= 3:
            pid = parts[0] if parts[0] != '-' else None
            status = parts[1]
            if pid:
                print(f"✓ Daemon is running (PID: {pid})")
                return True
            else:
                print(f"✗ Daemon is loaded but not running (status: {status})")
                return False
    print("✗ Daemon is not loaded")
    return False

def daemon_health():
    """Check daemon health via socket"""
    if not daemon_status():
        return False
    
    if not ADMIN_SOCKET.exists():
        print("⚠ Daemon running but socket not found")
        return False
    
    try:
        # Test socket connection
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect(str(DAEMON_SOCKET))
        
        # Send health check event
        health_event = {"event": "system:health", "data": {}}
        sock.send(json.dumps(health_event).encode() + b'\n')
        
        response = sock.recv(4096).decode()
        sock.close()
        
        data = json.loads(response)
        if data.get('status') == 'success':
            print("✓ Daemon is healthy")
            return True
        else:
            print(f"✗ Daemon health check failed: {data}")
            return False
            
    except Exception as e:
        print(f"✗ Socket connection failed: {e}")
        return False

def start_daemon():
    """Start daemon using launchctl"""
    print("Starting KSI daemon via launchd...")
    
    # Ensure directories exist
    (PROJECT_DIR / "var/logs/daemon").mkdir(parents=True, exist_ok=True)
    (PROJECT_DIR / "sockets").mkdir(parents=True, exist_ok=True)
    
    # Load the plist
    result = run_command(f"launchctl load {PLIST_PATH}")
    if not result:
        return False
    
    # Start the service
    result = run_command(f"launchctl start {DAEMON_LABEL}")
    if not result:
        return False
    
    # Wait a moment and check status
    import time
    time.sleep(2)
    
    if daemon_status():
        print("✓ Daemon started successfully")
        daemon_health()
        return True
    else:
        print("✗ Daemon failed to start")
        return False

def stop_daemon():
    """Stop daemon using launchctl"""
    print("Stopping KSI daemon...")
    
    # Try graceful shutdown via socket first
    try:
        if ADMIN_SOCKET.exists():
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect(str(ADMIN_SOCKET))
            
            shutdown_cmd = {"version": "2.0", "command": "SHUTDOWN"}
            sock.send(json.dumps(shutdown_cmd).encode() + b'\n')
            sock.close()
            print("Sent graceful shutdown command")
            
            import time
            time.sleep(2)
    except:
        pass  # Ignore errors, proceed with force stop
    
    # Stop via launchctl
    run_command(f"launchctl stop {DAEMON_LABEL}", check=False)
    run_command(f"launchctl unload {PLIST_PATH}", check=False)
    
    print("✓ Daemon stopped")
    return True

def restart_daemon():
    """Restart daemon"""
    print("Restarting KSI daemon...")
    stop_daemon()
    return start_daemon()

def show_logs():
    """Show recent daemon logs"""
    log_file = PROJECT_DIR / "var/logs/daemon/daemon.log"
    if log_file.exists():
        print("Recent daemon logs:")
        print("=" * 50)
        result = run_command(f"tail -50 {log_file}")
        if result:
            print(result.stdout)
    else:
        print("No log file found")

def main():
    """Main command handler"""
    if len(sys.argv) != 2:
        print("Usage: python3 daemon_launchd.py {start|stop|restart|status|health|logs}")
        print("")
        print("KSI Daemon Control using macOS launchd")
        print("Commands:")
        print("  start    - Start the daemon")
        print("  stop     - Stop the daemon")
        print("  restart  - Restart the daemon")
        print("  status   - Check if daemon is running")
        print("  health   - Check daemon health via socket")
        print("  logs     - Show recent daemon logs")
        sys.exit(1)
    
    command = sys.argv[1]
    
    # Verify plist file exists
    if not PLIST_PATH.exists():
        print(f"Error: {PLIST_FILE} not found")
        sys.exit(1)
    
    if command == "start":
        sys.exit(0 if start_daemon() else 1)
    elif command == "stop":
        sys.exit(0 if stop_daemon() else 1)
    elif command == "restart":
        sys.exit(0 if restart_daemon() else 1)
    elif command == "status":
        sys.exit(0 if daemon_status() else 1)
    elif command == "health":
        sys.exit(0 if daemon_health() else 1)
    elif command == "logs":
        show_logs()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()