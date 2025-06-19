#!/usr/bin/env python3
"""
Client library for communicating with the Claude daemon via Unix domain socket.
This shows how `claude -p` processes would interact with the daemon.
"""

import socket
import json
import os
from typing import Dict, Any, Optional, List

class ClaudeClient:
    """Client for communicating with the Claude daemon"""
    
    def __init__(self, socket_path: str = None):
        self.socket_path = socket_path or os.environ.get('CLAUDE_DAEMON_SOCKET', '/tmp/claude_daemon.sock')
        self.socket = None
    
    def connect(self):
        """Connect to the daemon"""
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.connect(self.socket_path)
    
    def disconnect(self):
        """Disconnect from the daemon"""
        if self.socket:
            self.socket.close()
            self.socket = None
    
    def send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Send a command and wait for response"""
        if not self.socket:
            raise RuntimeError("Not connected to daemon")
        
        # Send command as JSONL
        request_line = json.dumps(command) + '\n'
        self.socket.sendall(request_line.encode())
        
        # Read response
        response_data = b''
        while b'\n' not in response_data:
            chunk = self.socket.recv(4096)
            if not chunk:
                raise ConnectionError("Connection closed by daemon")
            response_data += chunk
        
        # Parse response
        response_line = response_data.split(b'\n')[0]
        return json.loads(response_line.decode())
    
    def spawn_process(self, cmd: List[str], process_id: str = None) -> Dict[str, Any]:
        """Spawn a new process via the daemon"""
        command = {
            'command': 'spawn_process',
            'cmd': cmd
        }
        if process_id:
            command['process_id'] = process_id
        return self.send_command(command)
    
    def list_processes(self) -> Dict[str, Any]:
        """List all processes managed by the daemon"""
        return self.send_command({'command': 'list_processes'})
    
    def get_process_info(self, process_id: str) -> Dict[str, Any]:
        """Get information about a specific process"""
        return self.send_command({
            'command': 'process_info',
            'process_id': process_id
        })
    
    def load_module(self, module_name: str) -> Dict[str, Any]:
        """Load or reload a Python module in the daemon"""
        return self.send_command({
            'command': 'load_module',
            'module_name': module_name
        })
    
    def call_function(self, module_name: str, function_name: str, 
                     args: List[Any] = None, kwargs: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call a function in a loaded module"""
        return self.send_command({
            'command': 'call_function',
            'module_name': module_name,
            'function_name': function_name,
            'args': args or [],
            'kwargs': kwargs or {}
        })
    
    def list_modules(self) -> Dict[str, Any]:
        """List all loaded modules and their functions"""
        return self.send_command({'command': 'list_modules'})
    
    def ping(self) -> Dict[str, Any]:
        """Health check"""
        return self.send_command({'command': 'ping'})
    
    def shutdown(self) -> Dict[str, Any]:
        """Request daemon shutdown"""
        return self.send_command({'command': 'shutdown'})

# Convenience functions for one-shot operations
def spawn_claude_process(cmd: List[str], process_id: str = None) -> Dict[str, Any]:
    """Spawn a claude process through the daemon"""
    client = ClaudeClient()
    try:
        client.connect()
        return client.spawn_process(cmd, process_id)
    finally:
        client.disconnect()

def call_daemon_function(module: str, function: str, *args, **kwargs) -> Dict[str, Any]:
    """Call a function in a daemon-loaded module"""
    client = ClaudeClient()
    try:
        client.connect()
        return client.call_function(module, function, list(args), kwargs)
    finally:
        client.disconnect()

# Example usage
if __name__ == '__main__':
    import sys
    
    # Simple CLI for testing
    if len(sys.argv) < 2:
        print("Usage: python client.py <command> [args...]")
        print("Commands: spawn, list, info, load, call, ping, shutdown")
        sys.exit(1)
    
    client = ClaudeClient()
    client.connect()
    
    try:
        cmd = sys.argv[1]
        
        if cmd == 'spawn':
            if len(sys.argv) < 3:
                print("Usage: python client.py spawn <command> [args...]")
                sys.exit(1)
            result = client.spawn_process(sys.argv[2:])
            print(json.dumps(result, indent=2))
        
        elif cmd == 'list':
            result = client.list_processes()
            print(json.dumps(result, indent=2))
        
        elif cmd == 'info':
            if len(sys.argv) < 3:
                print("Usage: python client.py info <process_id>")
                sys.exit(1)
            result = client.get_process_info(sys.argv[2])
            print(json.dumps(result, indent=2))
        
        elif cmd == 'load':
            if len(sys.argv) < 3:
                print("Usage: python client.py load <module_name>")
                sys.exit(1)
            result = client.load_module(sys.argv[2])
            print(json.dumps(result, indent=2))
        
        elif cmd == 'call':
            if len(sys.argv) < 4:
                print("Usage: python client.py call <module> <function> [args...]")
                sys.exit(1)
            module = sys.argv[2]
            function = sys.argv[3]
            args = sys.argv[4:] if len(sys.argv) > 4 else []
            result = client.call_function(module, function, args)
            print(json.dumps(result, indent=2))
        
        elif cmd == 'modules':
            result = client.list_modules()
            print(json.dumps(result, indent=2))
        
        elif cmd == 'ping':
            result = client.ping()
            print(json.dumps(result, indent=2))
        
        elif cmd == 'shutdown':
            result = client.shutdown()
            print(json.dumps(result, indent=2))
        
        else:
            print(f"Unknown command: {cmd}")
            sys.exit(1)
            
    finally:
        client.disconnect()