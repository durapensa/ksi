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
from .config import config
from .logging_config import get_logger, bind_socket_context, clear_context, log_event

logger = get_logger(__name__)

class KSIDaemonCore:
    """Core daemon server with dependency injection for all managers - EXACT functionality from daemon_clean.py"""
    
    def __init__(self, socket_path: str, hot_reload_from: str = None):
        self.socket_path = socket_path
        self.hot_reload_from = hot_reload_from
        self.is_hot_reload = hot_reload_from is not None
        self.shutdown_event = asyncio.Event()
        
        # PID file for collision detection
        self.pid_file = config.pid_file
        
        # Manager instances - will be injected by main entry point
        self.state_manager = None
        self.completion_manager = None
        self.agent_manager = None
        self.hot_reload_manager = None
        self.command_handler = None
        self.message_bus = None
        self.identity_manager = None
    
    def set_managers(self, state_manager, completion_manager, agent_manager, hot_reload_manager, command_handler, message_bus=None, identity_manager=None):
        """Dependency injection - wire all managers together"""
        self.state_manager = state_manager
        self.completion_manager = completion_manager
        self.agent_manager = agent_manager
        self.hot_reload_manager = hot_reload_manager
        self.command_handler = command_handler
        self.message_bus = message_bus
        self.identity_manager = identity_manager
        
        # Set up cross-manager dependencies
        if self.completion_manager and self.agent_manager:
            self.completion_manager.set_agent_manager(self.agent_manager)
        if self.completion_manager and self.message_bus:
            self.completion_manager.set_message_bus(self.message_bus)
    
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
        """JSON Protocol v2.0 client handler with context binding"""
        agent_id = None  # Initialize to avoid UnboundLocalError
        request_id = None
        try:
            # Read first JSON command
            first_data = await reader.readline()
            if not first_data:
                return
            
            first_command = first_data.decode().strip()
            
            # All commands must be JSON - no exceptions
            try:
                command_data = json.loads(first_command)
                command_name = command_data.get("command")
                parameters = command_data.get("parameters", {})
                
                # Determine functional domain and bind context
                functional_domain = self._determine_functional_domain(command_name, parameters)
                
                # Bind socket context with domain identification
                extra_context = {}
                if parameters.get("agent_id"):
                    extra_context["agent_id"] = parameters["agent_id"]
                if parameters.get("session_id"):
                    extra_context["session_id"] = parameters["session_id"]
                if command_name == "AGENT_CONNECTION":
                    extra_context["connection_action"] = parameters.get("action", "unknown")
                
                request_id = bind_socket_context(functional_domain, **extra_context)
                
                # Log socket connection event
                log_event(logger, "socket.connected", 
                         command_name=command_name, 
                         functional_domain=functional_domain,
                         peer_info=self._get_peer_info(writer))
                
                # Process the command
                if not self.command_handler:
                    log_event(logger, "command.error", error="No command handler available")
                    return
                
                # Handle the command
                should_continue = await self.command_handler.handle_command(first_command, writer, reader)
                
                # If this is an AGENT_CONNECTION:connect, keep connection open
                if (command_name == "AGENT_CONNECTION" and 
                    parameters.get("action") == "connect"):
                    
                    agent_id = parameters.get("agent_id")
                    log_event(logger, "agent.connection_persistent", 
                             agent_id=agent_id, functional_domain=functional_domain)
                    
                    # Keep connection open for more JSON commands
                    while not self.shutdown_event.is_set() and should_continue:
                        try:
                            data = await asyncio.wait_for(reader.readline(), timeout=1.0)
                            if not data:
                                break
                        except asyncio.TimeoutError:
                            continue
                        except asyncio.CancelledError:
                            break
                        
                        command = data.decode().strip()
                        if command:
                            should_continue = await self.command_handler.handle_command(command, writer, reader)
                        
                    log_event(logger, "agent.connection_closed", agent_id=agent_id)
                
            except json.JSONDecodeError as e:
                # Bind minimal context for invalid JSON
                request_id = bind_socket_context("admin", error_type="invalid_json")
                
                log_event(logger, "socket.invalid_json", error=str(e))
                error_response = {
                    "status": "error",
                    "error": {
                        "code": "INVALID_JSON",
                        "message": f"All commands must be valid JSON: {str(e)}"
                    }
                }
                writer.write((json.dumps(error_response) + '\n').encode())
                await writer.drain()
                
        except Exception as e:
            log_event(logger, "socket.error", error=str(e), error_type=type(e).__name__)
        finally:
            # Clean up agent connection if needed
            if agent_id and self.message_bus:
                self.message_bus.disconnect_agent(agent_id)
                log_event(logger, "agent.disconnected", agent_id=agent_id)
            
            # Log socket disconnection
            if request_id:
                log_event(logger, "socket.disconnected")
            
            # Clear context and close connection
            clear_context()
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
    
    def _determine_functional_domain(self, command_name: str, parameters: dict) -> str:
        """
        Determine functional domain based on command type.
        Maps commands to eventual socket domains for context binding.
        """
        # Admin domain - System operations
        admin_commands = {"HEALTH_CHECK", "SHUTDOWN", "CLEANUP", "GET_PROCESSES", "RELOAD_DAEMON"}
        
        # Agents domain - Agent lifecycle & persona  
        agents_commands = {"SPAWN_AGENT", "REGISTER_AGENT", "GET_AGENTS", "CREATE_IDENTITY", 
                          "UPDATE_IDENTITY", "REMOVE_IDENTITY", "LIST_IDENTITIES", "GET_IDENTITY",
                          "COMPOSE_PROMPT", "VALIDATE_COMPOSITION", "GET_COMPOSITION", "GET_COMPOSITIONS"}
        
        # Messaging domain - Ephemeral communication
        messaging_commands = {"PUBLISH", "SUBSCRIBE", "SEND_MESSAGE", "AGENT_CONNECTION", 
                             "MESSAGE_BUS_STATS"}
        
        # State domain - Persistent KV store  
        state_commands = {"SET_AGENT_KV", "GET_AGENT_KV", "SET_SHARED", "GET_SHARED", "LOAD_STATE"}
        
        # Completion domain - LLM interactions
        completion_commands = {"COMPLETION"}
        
        if command_name in admin_commands:
            return "admin"
        elif command_name in agents_commands:
            return "agents"
        elif command_name in messaging_commands:
            return "messaging"
        elif command_name in state_commands:
            return "state" 
        elif command_name in completion_commands:
            return "completion"
        else:
            return "admin"  # Default unknown commands to admin
    
    def _get_peer_info(self, writer: asyncio.StreamWriter) -> dict:
        """Get connection peer information for logging."""
        try:
            peername = writer.get_extra_info('peername')
            sockname = writer.get_extra_info('sockname')
            return {
                "peer": str(peername) if peername else "unknown",
                "local": str(sockname) if sockname else "unknown"
            }
        except Exception:
            return {"peer": "unknown", "local": "unknown"}
    
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
                    if 'daemon.py' in cmdline or 'ksi_daemon' in cmdline:
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
        
        # Ensure var/ directory structure exists (handled by ensure_var_directories in __init__.py)
        
        # Clean up socket file if it exists
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        # Write PID file for collision detection
        self._write_pid_file()
        
        server = await asyncio.start_unix_server(
            self.handle_client,
            path=self.socket_path
        )
        
        logger.info(f"Modular KSI daemon listening on {self.socket_path}")
        
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
                if self.completion_manager and hasattr(self.completion_manager, 'running_processes'):
                    running_processes = self.completion_manager.running_processes
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