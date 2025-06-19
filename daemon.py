#!/usr/bin/env python3
"""
Minimal Claude Process Management Daemon

Just enough to:
- Spawn claude processes with prompts
- Track sessionId for --resume
- Hot-reload modules if Claude writes them
"""

import asyncio
import json
import os
import sys
import signal
import importlib
import importlib.util
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger('daemon')

class ClaudeDaemon:
    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self.sessions = {}  # session_id -> last_output
        self.modules_dir = Path("claude_modules")
        self.loaded_module = None
        
    async def spawn_claude(self, prompt: str, session_id: str = None) -> dict:
        """Spawn claude process and capture output"""
        # Build command
        cmd_parts = [
            'echo', f'"{prompt}"', '|',
            'claude', '--model', 'sonnet', '--print', '--output-format', 'json',
            '--allowedTools', '"Task Bash Glob Grep LS Read Edit MultiEdit Write WebFetch WebSearch"'
        ]
        
        if session_id:
            cmd_parts.extend(['--resume', session_id])
        
        # Note: We'll tee the output so we can both capture it and send to socket
        cmd_parts.extend(['|', 'tee', '/tmp/claude_last_output.json', '|', 
                         'socat', 'STDIO', f'UNIX-CONNECT:{self.socket_path}'])
        
        cmd = ' '.join(cmd_parts)
        logger.info(f"Spawning: {cmd}")
        
        # Execute
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if stderr:
            logger.error(f"Process stderr: {stderr.decode()}")
            
        return {'command': cmd, 'pid': process.pid, 'returncode': process.returncode}
    
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming connections"""
        try:
            # Read all data
            data = b''
            while True:
                chunk = await reader.read(4096)
                if not chunk:
                    break
                data += chunk
            
            # Try to parse as JSON
            try:
                output = json.loads(data.decode())
                
                # Extract sessionId if present
                if 'sessionId' in output:
                    session_id = output['sessionId']
                    self.sessions[session_id] = output
                    logger.info(f"Captured session: {session_id}")
                
                # Call handler module if loaded
                if self.loaded_module and hasattr(self.loaded_module, 'handle_output'):
                    self.loaded_module.handle_output(output, self)
                    
            except json.JSONDecodeError:
                # Not JSON, might be a command
                text = data.decode().strip()
                if text.startswith('SPAWN:'):
                    # Command to spawn new claude
                    prompt = text[6:].strip()
                    await self.spawn_claude(prompt)
                elif text.startswith('RELOAD:'):
                    # Reload module
                    module_name = text[7:].strip()
                    self.reload_module(module_name)
                    writer.write(b'OK\n')
                    
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    def reload_module(self, module_name: str = 'handler'):
        """Reload a module from claude_modules/"""
        try:
            module_path = self.modules_dir / f"{module_name}.py"
            if not module_path.exists():
                logger.info(f"No module at {module_path}")
                return
                
            spec = importlib.util.spec_from_file_location(
                f"claude_modules.{module_name}",
                module_path
            )
            
            if spec and spec.loader:
                if self.loaded_module:
                    # Reload existing
                    importlib.reload(self.loaded_module)
                else:
                    # Load new
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[f"claude_modules.{module_name}"] = module
                    spec.loader.exec_module(module)
                    self.loaded_module = module
                    
                logger.info(f"Loaded module: {module_name}")
        except Exception as e:
            logger.error(f"Failed to load module: {e}")
    
    async def start(self):
        """Start the daemon"""
        # Remove existing socket
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
            
        # Start server
        server = await asyncio.start_unix_server(
            self.handle_client,
            path=self.socket_path
        )
        
        logger.info(f"Daemon listening on {self.socket_path}")
        
        # Try to load handler module if it exists
        self.reload_module('handler')
        
        # Handle shutdown
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda s, f: asyncio.create_task(self.shutdown(server)))
        
        async with server:
            await server.serve_forever()
    
    async def shutdown(self, server):
        """Graceful shutdown"""
        logger.info("Shutting down...")
        server.close()
        await server.wait_closed()
        asyncio.get_event_loop().stop()

async def main():
    socket_path = os.environ.get('CLAUDE_DAEMON_SOCKET', '/tmp/claude_daemon.sock')
    daemon = ClaudeDaemon(socket_path)
    await daemon.start()

if __name__ == '__main__':
    asyncio.run(main()