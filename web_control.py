#!/usr/bin/env python3
"""
KSI Web UI Control Script

Manages the KSI web visualization system:
- KSI Daemon status check (via daemon_control.py)  
- HTTP Server (serving ksi_web_ui/)

The daemon now includes native WebSocket transport, so no separate bridge is needed.

Usage:
    ./web_control.py start      # Start HTTP server
    ./web_control.py stop       # Stop HTTP server  
    ./web_control.py restart    # Restart HTTP server
    ./web_control.py status     # Show status of components
"""

import os
import sys
import subprocess
import signal
import time
import argparse
from pathlib import Path

class WebUIControl:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.ui_port = 8080
        self.websocket_port = 8765  # Native WebSocket transport port
        
    def get_daemon_status(self):
        """Check KSI daemon status via daemon_control.py"""
        try:
            result = subprocess.run(
                [sys.executable, "daemon_control.py", "status"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=5
            )
            return "running" if result.returncode == 0 else "stopped"
        except:
            return "unknown"
    
    def check_websocket_port(self):
        """Check if WebSocket transport is listening"""
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{self.websocket_port}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0 and result.stdout.strip()
        except:
            return False
    
    def find_process_by_port(self, port):
        """Find process ID using a specific port"""
        try:
            # Use lsof to find process using the port
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip().split('\n')[0])
        except:
            pass
        return None
    
    def find_ui_process(self):
        """Find UI HTTP server process"""
        return self.find_process_by_port(self.ui_port)
    
    def start_ui_server(self):
        """Start UI HTTP server"""
        if self.find_ui_process():
            print(f"✓ UI server already running on port {self.ui_port}")
            return True
            
        print(f"Starting UI server on port {self.ui_port}...")
        try:
            ui_dir = self.project_root / "ksi_web_ui"
            process = subprocess.Popen(
                [sys.executable, "-m", "http.server", str(self.ui_port)],
                cwd=ui_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Wait a moment and check if it started successfully
            time.sleep(2)
            if process.poll() is None:  # Still running
                print(f"✓ UI server started (PID: {process.pid})")
                print(f"  → Open http://localhost:{self.ui_port} in your browser")
                return True
            else:
                print("✗ UI server failed to start")
                return False
        except Exception as e:
            print(f"✗ Failed to start UI server: {e}")
            return False
    
    def stop_process(self, pid, name):
        """Stop a process by PID"""
        if not pid:
            return True
            
        try:
            os.kill(pid, signal.SIGTERM)
            
            # Wait for graceful shutdown
            for _ in range(5):
                try:
                    os.kill(pid, 0)  # Check if still exists
                    time.sleep(1)
                except ProcessLookupError:
                    print(f"✓ {name} stopped")
                    return True
            
            # Force kill if still running
            try:
                os.kill(pid, signal.SIGKILL)
                print(f"✓ {name} force stopped")
                return True
            except ProcessLookupError:
                print(f"✓ {name} stopped")
                return True
                
        except ProcessLookupError:
            return True
        except Exception as e:
            print(f"✗ Failed to stop {name}: {e}")
            return False
    
    def start(self):
        """Start UI server and check daemon status"""
        print("🚀 Starting KSI Web UI...")
        print()
        
        # Check daemon status
        daemon_status = self.get_daemon_status()
        if daemon_status == "running":
            print("✓ KSI daemon is running")
            
            # Check WebSocket transport
            if self.check_websocket_port():
                print(f"✓ WebSocket transport available on port {self.websocket_port}")
            else:
                print(f"⚠️  WebSocket transport not detected on port {self.websocket_port}")
                print("   Ensure daemon was started with: KSI_TRANSPORTS=unix,websocket ./daemon_control.py start")
        else:
            print("⚠️  KSI daemon is not running")
            print("   Start it with: KSI_TRANSPORTS=unix,websocket ./daemon_control.py start")
        
        print()
        
        # Start UI server
        success = self.start_ui_server()
        
        print()
        if success:
            print("🎉 KSI Web UI ready!")
            print(f"   → Web UI: http://localhost:{self.ui_port}")
            print(f"   → WebSocket endpoint: ws://localhost:{self.websocket_port}")
        else:
            print("❌ Failed to start UI server")
        
        return success
    
    def stop(self):
        """Stop UI server"""
        print("🛑 Stopping KSI Web UI...")
        print()
        
        # Stop UI server
        ui_pid = self.find_ui_process()
        if ui_pid:
            self.stop_process(ui_pid, "UI server")
        else:
            print("✓ UI server not running")
        
        print()
        print("ℹ️  KSI daemon left running (use ./daemon_control.py stop to stop)")
        print("🏁 KSI Web UI stopped")
    
    def restart(self):
        """Restart UI server"""
        self.stop()
        time.sleep(1)
        self.start()
    
    def show_status(self):
        """Show status of components"""
        print("📊 KSI Web UI Status")
        print("=" * 30)
        
        # Daemon status
        daemon_status = self.get_daemon_status()
        daemon_icon = "✅" if daemon_status == "running" else "❌" if daemon_status == "stopped" else "❓"
        print(f"{daemon_icon} KSI Daemon: {daemon_status}")
        
        # WebSocket transport status
        ws_available = self.check_websocket_port() if daemon_status == "running" else False
        ws_icon = "✅" if ws_available else "❌"
        ws_status = "available" if ws_available else "not available"
        print(f"{ws_icon} WebSocket Transport: {ws_status}")
        if ws_available:
            print(f"   → ws://localhost:{self.websocket_port}")
        
        # UI status
        ui_pid = self.find_ui_process()
        ui_status = f"running (PID: {ui_pid})" if ui_pid else "stopped"
        ui_icon = "✅" if ui_pid else "❌"
        print(f"{ui_icon} UI Server: {ui_status}")
        if ui_pid:
            print(f"   → http://localhost:{self.ui_port}")


def main():
    parser = argparse.ArgumentParser(description="KSI Web UI Control")
    parser.add_argument(
        "action", 
        choices=["start", "stop", "restart", "status"],
        help="Action to perform"
    )
    
    args = parser.parse_args()
    control = WebUIControl()
    
    if args.action == "start":
        control.start()
    elif args.action == "stop":
        control.stop()
    elif args.action == "restart":
        control.restart()
    elif args.action == "status":
        control.show_status()


if __name__ == "__main__":
    main()