#!/usr/bin/env python3
"""
Claude Process Management Daemon

A reliable daemon that:
- Accepts commands via Unix domain socket using JSONL protocol
- Spawns and manages `claude -p` processes
- Dynamically loads and reloads Python modules from claude_modules/
- Provides a generic way to call functions in loaded modules
"""

import asyncio
import json
import logging
import os
import sys
import signal
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('claude_daemon')

class ProcessManager:
    """Manages spawned processes and tracks their state"""
    
    def __init__(self):
        self.processes: Dict[str, asyncio.subprocess.Process] = {}
        self.process_info: Dict[str, Dict[str, Any]] = {}
    
    async def spawn_process(self, process_id: str, cmd: List[str], **kwargs) -> Dict[str, Any]:
        """Spawn a new process and track it"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                **kwargs
            )
            
            self.processes[process_id] = process
            self.process_info[process_id] = {
                'cmd': cmd,
                'pid': process.pid,
                'started_at': datetime.now().isoformat(),
                'status': 'running'
            }
            
            # Start monitoring task
            asyncio.create_task(self._monitor_process(process_id, process))
            
            return {
                'success': True,
                'process_id': process_id,
                'pid': process.pid
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _monitor_process(self, process_id: str, process: asyncio.subprocess.Process):
        """Monitor a process and update its status when it exits"""
        return_code = await process.wait()
        self.process_info[process_id]['status'] = 'exited'
        self.process_info[process_id]['return_code'] = return_code
        self.process_info[process_id]['ended_at'] = datetime.now().isoformat()
    
    def get_process_info(self, process_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific process"""
        return self.process_info.get(process_id)
    
    def list_processes(self) -> Dict[str, Dict[str, Any]]:
        """List all tracked processes"""
        return self.process_info.copy()
    
    async def cleanup(self):
        """Terminate all running processes"""
        for process_id, process in self.processes.items():
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()

class ModuleManager:
    """Manages dynamic loading and reloading of Python modules"""
    
    def __init__(self, modules_dir: Path):
        self.modules_dir = modules_dir
        self.loaded_modules: Dict[str, Any] = {}
    
    def load_module(self, module_name: str) -> Dict[str, Any]:
        """Load or reload a module from the modules directory"""
        try:
            module_path = self.modules_dir / f"{module_name}.py"
            
            if not module_path.exists():
                return {
                    'success': False,
                    'error': f"Module {module_name}.py not found in {self.modules_dir}"
                }
            
            # Ensure parent package is in sys.modules
            if 'claude_modules' not in sys.modules:
                # Create parent package
                parent_spec = importlib.util.spec_from_file_location(
                    "claude_modules",
                    self.modules_dir / "__init__.py"
                )
                parent_module = importlib.util.module_from_spec(parent_spec)
                sys.modules['claude_modules'] = parent_module
            
            # Create module spec
            spec = importlib.util.spec_from_file_location(
                f"claude_modules.{module_name}",
                module_path
            )
            
            if spec is None or spec.loader is None:
                return {
                    'success': False,
                    'error': f"Failed to create spec for module {module_name}"
                }
            
            # Load or reload the module
            if module_name in self.loaded_modules:
                # Reload existing module
                module = self.loaded_modules[module_name]
                importlib.reload(module)
            else:
                # Load new module
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"claude_modules.{module_name}"] = module
                spec.loader.exec_module(module)
                self.loaded_modules[module_name] = module
            
            # Get available functions (exclude imported modules)
            functions = []
            for name in dir(module):
                attr = getattr(module, name)
                if callable(attr) and not name.startswith('_'):
                    # Check if it's defined in this module
                    if hasattr(attr, '__module__') and attr.__module__ == f"claude_modules.{module_name}":
                        functions.append(name)
            
            return {
                'success': True,
                'module': module_name,
                'functions': functions
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to load module: {str(e)}",
                'traceback': traceback.format_exc()
            }
    
    def call_function(self, module_name: str, function_name: str, args: List[Any] = None, kwargs: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call a function in a loaded module"""
        try:
            if module_name not in self.loaded_modules:
                return {
                    'success': False,
                    'error': f"Module {module_name} not loaded"
                }
            
            module = self.loaded_modules[module_name]
            
            if not hasattr(module, function_name):
                return {
                    'success': False,
                    'error': f"Function {function_name} not found in module {module_name}"
                }
            
            func = getattr(module, function_name)
            
            if not callable(func):
                return {
                    'success': False,
                    'error': f"{function_name} is not a callable function"
                }
            
            # Call the function
            args = args or []
            kwargs = kwargs or {}
            result = func(*args, **kwargs)
            
            return {
                'success': True,
                'result': result
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Function call failed: {str(e)}",
                'traceback': traceback.format_exc()
            }
    
    def list_modules(self) -> Dict[str, List[str]]:
        """List all loaded modules and their functions"""
        result = {}
        for name, module in self.loaded_modules.items():
            functions = []
            for fname in dir(module):
                attr = getattr(module, fname)
                if callable(attr) and not fname.startswith('_'):
                    # Check if it's defined in this module
                    if hasattr(attr, '__module__') and attr.__module__ == f"claude_modules.{name}":
                        functions.append(fname)
            result[name] = functions
        return result

class ClaudeDaemon:
    """Main daemon class that handles client connections and command dispatch"""
    
    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self.process_manager = ProcessManager()
        self.module_manager = ModuleManager(Path("claude_modules"))
        self.running = True
        self.server = None
        self.client_counter = 0
    
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a client connection"""
        self.client_counter += 1
        client_id = f"client_{self.client_counter}"
        logger.info(f"New client connected: {client_id}")
        
        try:
            while True:
                # Read line (JSONL format)
                line = await reader.readline()
                if not line:
                    break
                
                try:
                    # Parse JSON request
                    request = json.loads(line.decode().strip())
                    logger.info(f"Received request from {client_id}: {request.get('command')}")
                    
                    # Process command
                    response = await self.process_command(request)
                    
                    # Send response
                    response_line = json.dumps(response) + '\n'
                    writer.write(response_line.encode())
                    await writer.drain()
                    
                except json.JSONDecodeError as e:
                    error_response = {
                        'success': False,
                        'error': f"Invalid JSON: {str(e)}"
                    }
                    writer.write((json.dumps(error_response) + '\n').encode())
                    await writer.drain()
                
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {str(e)}")
        finally:
            writer.close()
            await writer.wait_closed()
            logger.info(f"Client disconnected: {client_id}")
    
    async def process_command(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process a command from a client"""
        command = request.get('command')
        
        if command == 'spawn_process':
            # Spawn a new process
            process_id = request.get('process_id', f"process_{datetime.now().timestamp()}")
            cmd = request.get('cmd', [])
            if not cmd:
                return {'success': False, 'error': 'No command specified'}
            return await self.process_manager.spawn_process(process_id, cmd)
        
        elif command == 'list_processes':
            # List all processes
            return {
                'success': True,
                'processes': self.process_manager.list_processes()
            }
        
        elif command == 'process_info':
            # Get info about a specific process
            process_id = request.get('process_id')
            if not process_id:
                return {'success': False, 'error': 'No process_id specified'}
            info = self.process_manager.get_process_info(process_id)
            if info:
                return {'success': True, 'info': info}
            else:
                return {'success': False, 'error': f'Process {process_id} not found'}
        
        elif command == 'load_module':
            # Load or reload a module
            module_name = request.get('module_name')
            if not module_name:
                return {'success': False, 'error': 'No module_name specified'}
            return self.module_manager.load_module(module_name)
        
        elif command == 'call_function':
            # Call a function in a loaded module
            module_name = request.get('module_name')
            function_name = request.get('function_name')
            args = request.get('args', [])
            kwargs = request.get('kwargs', {})
            
            if not module_name or not function_name:
                return {'success': False, 'error': 'module_name and function_name required'}
            
            return self.module_manager.call_function(module_name, function_name, args, kwargs)
        
        elif command == 'list_modules':
            # List all loaded modules
            return {
                'success': True,
                'modules': self.module_manager.list_modules()
            }
        
        elif command == 'ping':
            # Health check
            return {'success': True, 'pong': True}
        
        elif command == 'shutdown':
            # Graceful shutdown
            logger.info("Shutdown requested")
            self.running = False
            return {'success': True, 'message': 'Shutting down'}
        
        else:
            return {'success': False, 'error': f'Unknown command: {command}'}
    
    async def start(self):
        """Start the daemon"""
        # Remove existing socket if it exists
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        # Create socket directory if needed
        os.makedirs(os.path.dirname(self.socket_path) or '.', exist_ok=True)
        
        # Start server
        self.server = await asyncio.start_unix_server(
            self.handle_client,
            path=self.socket_path
        )
        
        logger.info(f"Daemon started, listening on {self.socket_path}")
        
        # Handle shutdown signals
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda s, f: asyncio.create_task(self.shutdown()))
        
        # Serve forever
        async with self.server:
            await self.server.serve_forever()
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down daemon...")
        self.running = False
        
        # Stop accepting new connections
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # Clean up processes
        await self.process_manager.cleanup()
        
        logger.info("Daemon shutdown complete")
        
        # Stop the event loop
        asyncio.get_event_loop().stop()

async def main():
    """Main entry point"""
    socket_path = os.environ.get('CLAUDE_DAEMON_SOCKET', '/tmp/claude_daemon.sock')
    daemon = ClaudeDaemon(socket_path)
    
    try:
        await daemon.start()
    except KeyboardInterrupt:
        await daemon.shutdown()

if __name__ == '__main__':
    asyncio.run(main())