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
import subprocess
import shutil

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger('daemon')

class ClaudeDaemon:
    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self.sessions = {}  # session_id -> last_output
        self.modules_dir = Path("claude_modules")
        self.loaded_module = None
        self.shutdown_event = asyncio.Event()
        
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
        
        try:
            # Execute claude with prompt as stdin - explicitly inherit environment
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ
            )
        except FileNotFoundError as e:
            logger.error(f"Claude executable not found: {e}")
            return {'error': 'claude executable not found in PATH', 'details': str(e)}
        except Exception as e:
            logger.error(f"Failed to spawn Claude process: {e}")
            return {'error': f'Failed to spawn process: {type(e).__name__}', 'details': str(e)}
        
        # Send prompt and get output
        stdout, stderr = await process.communicate(prompt.encode())
        
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
                
                # Save session ID for easy resumption
                session_file = 'sockets/last_session_id'
                with open(session_file, 'w') as f:
                    f.write(new_session_id)
            
            # Call cognitive observer if loaded
            if self.loaded_module and hasattr(self.loaded_module, 'handle_output'):
                self.loaded_module.handle_output(output, self)
            
            return output
            
        except json.JSONDecodeError as e:
            return {'error': f'Invalid JSON from claude: {str(e)}', 'returncode': process.returncode}
        except Exception as e:
            return {'error': f'{type(e).__name__}: {str(e)}', 'returncode': -1}
    
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming connections"""
        try:
            # Read until newline or max size (more robust than waiting for EOF)
            data = await reader.readline()  # Read one line at a time
            if not data:
                return
            
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
                logger.info(f"Received command: {text[:50]}...")
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
                    logger.info(f"Spawning Claude with prompt: {prompt[:50]}...")
                    result = await self.spawn_claude(prompt, session_id)
                    logger.info(f"Claude spawn completed, result type: {type(result)}")
                    
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
                    
                elif text.startswith('CLEANUP:'):
                    # Cleanup command
                    cleanup_type = text[8:].strip()
                    result = self.cleanup(cleanup_type)
                    writer.write(f"{result}\n".encode())
                    await writer.drain()
                    
                elif text == 'SHUTDOWN':
                    # Shutdown daemon
                    logger.info("Received SHUTDOWN command")
                    writer.write(b'SHUTTING DOWN\n')
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
                    # Signal shutdown
                    self.shutdown_event.set()
                    return
                    
                    
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    def cleanup(self, cleanup_type: str) -> str:
        """Cleanup various daemon resources"""
        try:
            if cleanup_type == 'logs':
                # Clean up old log files
                logs_dir = Path('claude_logs')
                if logs_dir.exists():
                    files_removed = 0
                    for log_file in logs_dir.glob('*.jsonl'):
                        if log_file.name != 'latest.jsonl' and not log_file.is_symlink():
                            log_file.unlink()
                            files_removed += 1
                    
                    # Remove broken symlinks
                    latest_link = logs_dir / 'latest.jsonl'
                    if latest_link.is_symlink() and not latest_link.exists():
                        latest_link.unlink()
                    
                    return f"Removed {files_removed} log files"
                return "No logs directory found"
                
            elif cleanup_type == 'sessions':
                # Clear session tracking
                sessions_cleared = len(self.sessions)
                self.sessions.clear()
                return f"Cleared {sessions_cleared} tracked sessions"
                
            elif cleanup_type == 'sockets':
                # Clean up socket files
                sockets_dir = Path('sockets')
                if sockets_dir.exists():
                    files_removed = 0
                    for socket_file in sockets_dir.glob('*'):
                        if socket_file.name != 'claude_daemon.sock':  # Don't remove active daemon socket
                            socket_file.unlink()
                            files_removed += 1
                    return f"Removed {files_removed} socket files"
                return "No sockets directory found"
                
            elif cleanup_type == 'all':
                # Clean up everything
                results = []
                results.append(self.cleanup('logs'))
                results.append(self.cleanup('sessions'))
                results.append(self.cleanup('sockets'))
                return f"Complete cleanup: {'; '.join(results)}"
                
            else:
                return f"Unknown cleanup type: {cleanup_type}. Use: logs, sessions, sockets, or all"
                
        except Exception as e:
            return f"Cleanup failed: {type(e).__name__}: {str(e)}"

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
        # Remove existing socket if present
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
        
        # Simple signal handler - set shutdown event
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.shutdown_event.set()
            
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, signal_handler)
        
        async with server:
            try:
                # Wait for shutdown event or keyboard interrupt
                await self.shutdown_event.wait()
                logger.info("Shutdown event received, stopping server...")
            except (KeyboardInterrupt, SystemExit):
                pass
            finally:
                # Clean up socket file
                if os.path.exists(self.socket_path):
                    os.unlink(self.socket_path)


def check_daemon_running():
    """Simple PID file-based singleton check"""
    pid_file = '/tmp/claude-daemon.pid'
    
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            # Check if process actually exists
            os.kill(pid, 0)  # Signal 0 = check if process exists
            logger.info(f"Daemon already running (PID {pid}), exiting")
            return True
        except (OSError, ProcessLookupError, ValueError):
            # Stale PID file, remove it
            os.unlink(pid_file)
    
    # Write our PID
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))
    logger.info(f"Daemon started (PID {os.getpid()})")
    return False

async def main():
    # Check if daemon already running with reliable PID file approach
    if check_daemon_running():
        return
    
    socket_path = os.environ.get('CLAUDE_DAEMON_SOCKET', 'sockets/claude_daemon.sock')
    
    # Ensure socket directory exists
    os.makedirs(os.path.dirname(socket_path), exist_ok=True)
    
    daemon = ClaudeDaemon(socket_path)
    await daemon.start()

if __name__ == '__main__':
    asyncio.run(main())