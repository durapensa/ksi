#!/usr/bin/env python3

"""
Core Daemon - Main server logic and manager coordination
Extracted from daemon_clean.py with 100% functionality preservation
"""

import asyncio
import json
import os
import logging
import signal
import psutil
from pathlib import Path

logger = logging.getLogger('daemon')

class ClaudeDaemonCore:
    """Core daemon server with dependency injection for all managers - EXACT functionality from daemon_clean.py"""
    
    def __init__(self, socket_path: str, hot_reload_from: str = None):
        self.socket_path = socket_path
        self.hot_reload_from = hot_reload_from
        self.is_hot_reload = hot_reload_from is not None
        self.shutdown_event = asyncio.Event()
        
        # PID file for collision detection
        self.pid_file = Path("sockets/claude_daemon.pid")
        
        # Manager instances - will be injected by main entry point
        self.state_manager = None
        self.process_manager = None
        self.agent_manager = None
        self.utils_manager = None
        self.hot_reload_manager = None
        self.command_handler = None
        self.message_bus = None
        self.identity_manager = None
    
    def set_managers(self, state_manager, process_manager, agent_manager, utils_manager, hot_reload_manager, command_handler, message_bus=None, identity_manager=None):
        """Dependency injection - wire all managers together"""
        self.state_manager = state_manager
        self.process_manager = process_manager
        self.agent_manager = agent_manager
        self.utils_manager = utils_manager
        self.hot_reload_manager = hot_reload_manager
        self.command_handler = command_handler
        self.message_bus = message_bus
        self.identity_manager = identity_manager
        
        # Set up cross-manager dependencies
        if self.process_manager and self.agent_manager:
            self.process_manager.set_agent_manager(self.agent_manager)
        if self.process_manager and self.message_bus:
            self.process_manager.set_message_bus(self.message_bus)
    
    def serialize_state(self) -> dict:
        """Serialize complete daemon state for hot reload - EXACT copy from daemon_clean.py"""
        state = {}
        
        # Collect state from all managers
        if self.state_manager:
            state.update(self.state_manager.serialize_state())
        
        if self.agent_manager:
            state.update(self.agent_manager.serialize_state())
        
        return state
    
    def deserialize_state(self, state: dict):
        """Deserialize complete daemon state from hot reload - EXACT copy from daemon_clean.py"""
        # Distribute state to all managers
        if self.state_manager:
            self.state_manager.deserialize_state(state)
        
        if self.agent_manager:
            self.agent_manager.deserialize_state(state)
        
        logger.info(f"Loaded state: {len(state.get('sessions', {}))} sessions, {len(state.get('agents', {}))} agents")
    
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Clean, simple client handler - Extended for persistent connections"""
        agent_id = None
        try:
            # Set a timeout for client operations to prevent hanging
            reader._transport.set_write_buffer_limits(high=16*1024, low=4*1024)
            # Check if this is a persistent agent connection
            first_data = await reader.readline()
            if not first_data:
                return
            
            first_command = first_data.decode().strip()
            
            # Check if this is an AGENT_CONNECTION:connect command for persistent connection
            if first_command.startswith('AGENT_CONNECTION:connect:'):
                # This is a persistent agent connection
                agent_id = first_command[25:].strip()
                logger.info(f"Persistent agent connection from {agent_id}")
                
                # Process the connection command
                if self.command_handler:
                    await self.command_handler.handle_command(first_command, writer, reader)
                
                # Keep connection open for persistent agent
                while not self.shutdown_event.is_set():
                    try:
                        # Use wait_for with timeout to allow checking shutdown event
                        data = await asyncio.wait_for(reader.readline(), timeout=1.0)
                        if not data:
                            break
                    except asyncio.TimeoutError:
                        # Check if we should shutdown
                        if self.shutdown_event.is_set():
                            logger.info(f"Shutting down connection for agent {agent_id}")
                            break
                        continue
                    except asyncio.CancelledError:
                        logger.info(f"Connection cancelled for agent {agent_id}")
                        raise
                    
                    command = data.decode().strip()
                    logger.debug(f"Agent {agent_id} command: {command[:50]}...")
                    
                    if self.command_handler:
                        should_continue = await self.command_handler.handle_command(command, writer, reader)
                        if not should_continue:
                            break
            else:
                # Handle single command (original behavior)
                try:
                    # Try JSON first
                    output = json.loads(first_command)
                    # Handle JSON output (session tracking, etc.)
                    session_id = output.get('sessionId') or output.get('session_id')
                    if session_id and self.state_manager:
                        self.state_manager.track_session(session_id, output)
                        logger.info(f"Captured session: {session_id}")
                    return
                    
                except json.JSONDecodeError:
                    # Handle as command
                    logger.info(f"Received command: {first_command[:50]}...")
                    
                    # Route to command handler - clean and simple!
                    if self.command_handler:
                        should_continue = await self.command_handler.handle_command(first_command, writer, reader)
                        if not should_continue:
                            return  # Shutdown requested
                    else:
                        logger.error("No command handler available")
                
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            # Clean up agent connection if needed
            if agent_id and self.message_bus:
                self.message_bus.disconnect_agent(agent_id)
                logger.info(f"Disconnected agent {agent_id}")
            
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
    
    def _check_daemon_running(self) -> tuple[bool, int]:
        """Check if daemon is already running - returns (is_running, pid)"""
        if not self.pid_file.exists():
            return False, 0
        
        try:
            pid = int(self.pid_file.read_text().strip())
            
            # Check if process with this PID exists and is our daemon
            if psutil.pid_exists(pid):
                try:
                    proc = psutil.Process(pid)
                    cmdline = ' '.join(proc.cmdline())
                    
                    # Check if it's actually our daemon process
                    if 'daemon.py' in cmdline or 'claude_daemon' in cmdline:
                        return True, pid
                    else:
                        # PID exists but it's a different process - clean up stale PID file
                        logger.warning(f"PID {pid} exists but is not our daemon (cmdline: {cmdline}), cleaning up")
                        self.pid_file.unlink()
                        return False, 0
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # Process doesn't exist or we can't access it - clean up stale PID file
                    logger.info(f"PID {pid} no longer accessible, cleaning up stale PID file")
                    self.pid_file.unlink()
                    return False, 0
            else:
                # PID doesn't exist - clean up stale PID file
                logger.info(f"PID {pid} no longer exists, cleaning up stale PID file")
                self.pid_file.unlink()
                return False, 0
                
        except (ValueError, FileNotFoundError):
            # Invalid PID file content - clean it up
            logger.warning("Invalid PID file content, cleaning up")
            if self.pid_file.exists():
                self.pid_file.unlink()
            return False, 0
    
    async def _test_daemon_health(self, pid: int) -> bool:
        """Test if the existing daemon is healthy by connecting to its socket"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(self.socket_path),
                timeout=2.0
            )
            
            # Send health check command
            writer.write(b'HEALTH_CHECK\n')
            await writer.drain()
            
            # Read response
            response = await asyncio.wait_for(reader.readline(), timeout=2.0)
            
            writer.close()
            await writer.wait_closed()
            
            # Check if we got a valid response
            return response.strip() == b'HEALTHY'
            
        except (ConnectionRefusedError, FileNotFoundError, asyncio.TimeoutError, OSError):
            # Daemon socket is not responding - it's probably dead
            logger.warning(f"Daemon PID {pid} exists but socket not responding")
            return False
    
    def _write_pid_file(self):
        """Write current process PID to PID file"""
        self.pid_file.parent.mkdir(exist_ok=True)
        self.pid_file.write_text(str(os.getpid()))
        logger.info(f"PID file written: {self.pid_file} (PID {os.getpid()})")
    
    def _cleanup_pid_file(self):
        """Clean up PID file on shutdown"""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
                logger.info("PID file cleaned up")
        except Exception as e:
            logger.warning(f"Could not clean up PID file: {e}")
    
    async def start(self):
        """Start the daemon server with collision detection and improved graceful shutdown"""
        # Skip collision detection for hot reload
        if not self.is_hot_reload:
            # Check for existing daemon
            is_running, existing_pid = self._check_daemon_running()
            
            if is_running:
                # Test if the existing daemon is healthy
                is_healthy = await self._test_daemon_health(existing_pid)
                
                if is_healthy:
                    logger.info(f"Daemon already running (PID {existing_pid}), exiting")
                    return  # Exit gracefully - don't start another instance
                else:
                    logger.warning(f"Found stale daemon (PID {existing_pid}), cleaning up and starting new instance")
                    # Clean up stale resources
                    self._cleanup_pid_file()
                    if os.path.exists(self.socket_path):
                        os.unlink(self.socket_path)
        
        # Create directories
        for dir_name in ['shared_state', 'sockets', 'claude_logs', 'agent_profiles']:
            os.makedirs(dir_name, exist_ok=True)
        
        # Clean up socket file if it exists
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        # Write PID file for collision detection
        self._write_pid_file()
        
        server = await asyncio.start_unix_server(
            self.handle_client,
            path=self.socket_path
        )
        
        logger.info(f"Modular daemon listening on {self.socket_path}")
        
        # Keep track of server task for cleanup
        server_task = None
        
        try:
            async with server:
                # Create server task
                server_task = asyncio.create_task(server.serve_forever())
                
                # Wait for shutdown signal or cancellation
                try:
                    await self.shutdown_event.wait()
                    logger.info("Shutdown event received, stopping server...")
                except asyncio.CancelledError:
                    logger.info("Server cancelled, initiating shutdown...")
                    self.shutdown_event.set()
                
                # Cancel server task
                if server_task and not server_task.done():
                    server_task.cancel()
                    try:
                        await server_task
                    except asyncio.CancelledError:
                        pass
                
                # Close server to stop accepting new connections
                server.close()
                await server.wait_closed()
                logger.info("Server closed")
                
                # Clean up any running processes
                if self.process_manager and hasattr(self.process_manager, 'running_processes'):
                    running_processes = self.process_manager.running_processes
                    if running_processes:
                        logger.info(f"Cleaning up {len(running_processes)} running processes...")
                        for process_id, process_info in list(running_processes.items()):
                            try:
                                process = process_info.get('process')
                                if process and process.poll() is None:
                                    logger.info(f"Terminating process {process_id}")
                                    process.terminate()
                                    # Give process a moment to terminate gracefully
                                    try:
                                        # Use a simple timeout approach instead of asyncio.to_thread
                                        for _ in range(30):  # 3 seconds timeout (30 * 0.1s)
                                            if process.poll() is not None:
                                                break
                                            await asyncio.sleep(0.1)
                                        else:
                                            # Process didn't terminate gracefully
                                            logger.warning(f"Process {process_id} didn't terminate gracefully, killing...")
                                            process.kill()
                                            process.wait()
                                    except Exception as kill_error:
                                        logger.error(f"Error killing process {process_id}: {kill_error}")
                            except Exception as e:
                                logger.error(f"Error terminating process {process_id}: {e}")
                        
                        # Clear the running processes dict
                        running_processes.clear()
                        logger.info("All processes cleaned up")
                
                # Clean up socket file
                try:
                    if os.path.exists(self.socket_path):
                        os.unlink(self.socket_path)
                        logger.info(f"Removed socket file: {self.socket_path}")
                except Exception as e:
                    logger.warning(f"Error removing socket file: {e}")
                
                logger.info("Graceful shutdown complete")
                
        except Exception as e:
            logger.error(f"Error during daemon operation: {e}")
            raise
        except asyncio.CancelledError:
            logger.info("Daemon operation cancelled")
            raise
        finally:
            # Cancel all remaining tasks
            tasks = [t for t in asyncio.all_tasks() if t != asyncio.current_task()]
            if tasks:
                logger.info(f"Cancelling {len(tasks)} remaining tasks...")
                for task in tasks:
                    task.cancel()
                # Wait briefly for tasks to cancel
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # Ensure cleanup even if there was an error
            try:
                if os.path.exists(self.socket_path):
                    os.unlink(self.socket_path)
            except:
                pass
            
            # Clean up PID file
            self._cleanup_pid_file()