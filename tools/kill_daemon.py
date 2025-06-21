#!/usr/bin/env python3
"""
Kill daemon with proper signal escalation
"""

import os
import sys
import time
import signal
import psutil
from pathlib import Path

def kill_daemon_gracefully(pid_file_path="sockets/claude_daemon.pid", timeout=5):
    """Kill daemon gracefully with signal escalation"""
    
    # Check if PID file exists
    pid_file = Path(pid_file_path)
    if not pid_file.exists():
        print("No PID file found - daemon may not be running")
        return True
    
    try:
        pid = int(pid_file.read_text().strip())
        print(f"Found daemon PID: {pid}")
        
        # Check if process exists
        if not psutil.pid_exists(pid):
            print("Process no longer exists, cleaning up PID file")
            pid_file.unlink()
            return True
        
        try:
            proc = psutil.Process(pid)
            
            # First try SIGTERM
            print(f"Sending SIGTERM to {pid}...")
            proc.terminate()
            
            # Wait for graceful shutdown
            try:
                proc.wait(timeout=timeout)
                print(f"Daemon {pid} terminated gracefully")
                return True
            except psutil.TimeoutExpired:
                print(f"Daemon {pid} did not terminate within {timeout}s, sending SIGKILL...")
                
                # Force kill
                proc.kill()
                proc.wait(timeout=2)
                print(f"Daemon {pid} killed forcefully")
                return True
                
        except psutil.NoSuchProcess:
            print("Process disappeared, cleaning up")
            return True
        except psutil.AccessDenied:
            print(f"Access denied to kill process {pid}")
            return False
            
    except Exception as e:
        print(f"Error killing daemon: {e}")
        return False
    finally:
        # Clean up PID file if it still exists
        if pid_file.exists():
            try:
                pid_file.unlink()
                print("PID file cleaned up")
            except:
                pass

if __name__ == "__main__":
    timeout = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    success = kill_daemon_gracefully(timeout=timeout)
    sys.exit(0 if success else 1)