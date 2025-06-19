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
from datetime import datetime

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
        # Ensure directories exist
        os.makedirs('claude_logs', exist_ok=True)
        os.makedirs('sockets', exist_ok=True)
        
        # Build command
        cmd = [
            'claude',
            '--model', 'sonnet',
            '--print',
            '--output-format', 'json',
            '--allowedTools', 'Task Bash Glob Grep LS Read Edit MultiEdit Write WebFetch WebSearch'
        ]
        
        if session_id:
            cmd.extend(['--resume', session_id])
        
        logger.info(f"Spawning: {' '.join(cmd)}")
        
        # Execute claude with prompt as stdin
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Send prompt and get output
        stdout, stderr = await process.communicate(prompt.encode())
        
        logger.info(f"Process returncode: {process.returncode}")
        if stderr:
            logger.error(f"Process stderr: {stderr.decode()}")
        
        # Parse output
        try:
            if not stdout:
                return {'error': 'No output from claude', 'returncode': process.returncode}
            
            # Parse JSON output
            output = json.loads(stdout.decode())
            
            # Save to file for debugging/reference
            output_file = 'sockets/claude_last_output.json'
            with open(output_file, 'w') as f:
                json.dump(output, f, indent=2)
            
            # Extract session_id
            new_session_id = output.get('sessionId') or output.get('session_id')
            
            # Log to JSONL
            if new_session_id:
                log_file = f'claude_logs/{new_session_id}.jsonl'
                
                # Log human input
                human_entry = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "type": "human",
                    "content": prompt
                }
                with open(log_file, 'a') as f:
                    f.write(json.dumps(human_entry) + '\n')
                
                # Log Claude output
                claude_entry = output.copy()
                claude_entry["timestamp"] = datetime.utcnow().isoformat() + "Z"
                claude_entry["type"] = "claude"
                with open(log_file, 'a') as f:
                    f.write(json.dumps(claude_entry) + '\n')
                    
                # Update session tracking
                self.sessions[new_session_id] = output
                
                # Update latest symlink
                latest_link = 'claude_logs/latest.jsonl'
                if os.path.exists(latest_link):
                    os.unlink(latest_link)
                os.symlink(f'{new_session_id}.jsonl', latest_link)
            
            return output
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse claude output as JSON: {e}")
            if stdout:
                logger.error(f"Raw stdout: {stdout.decode()[:500]}")
            return {'error': f'Invalid JSON from claude: {str(e)}', 'returncode': process.returncode, 'stdout': stdout.decode()[:500] if stdout else None}
    
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
                session_id = output.get('sessionId') or output.get('session_id')
                if session_id:
                    self.sessions[session_id] = output
                    logger.info(f"Captured session: {session_id}")
                
                # Call handler module if loaded
                if self.loaded_module and hasattr(self.loaded_module, 'handle_output'):
                    self.loaded_module.handle_output(output, self)
                    
            except json.JSONDecodeError:
                # Not JSON, might be a command
                text = data.decode().strip()
                if text.startswith('SPAWN:'):
                    # Parse spawn command (format: "SPAWN:[session_id]:<prompt>")
                    parts = text[6:].split(':', 1)
                    if len(parts) == 2 and parts[0]:
                        # Has session_id
                        session_id = parts[0]
                        prompt = parts[1]
                    else:
                        # No session_id or old format
                        session_id = None
                        prompt = text[6:].strip()
                    
                    # Spawn Claude and get result
                    result = await self.spawn_claude(prompt, session_id)
                    
                    # Send result back to client
                    response = json.dumps(result) + '\n'
                    writer.write(response.encode())
                    await writer.drain()
                    
                elif text.startswith('RELOAD:'):
                    # Reload module
                    module_name = text[7:].strip()
                    self.reload_module(module_name)
                    writer.write(b'OK\n')
                    await writer.drain()
                    
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
    socket_path = os.environ.get('CLAUDE_DAEMON_SOCKET', 'sockets/claude_daemon.sock')
    
    # Ensure socket directory exists
    os.makedirs(os.path.dirname(socket_path), exist_ok=True)
    
    daemon = ClaudeDaemon(socket_path)
    await daemon.start()

if __name__ == '__main__':
    asyncio.run(main())