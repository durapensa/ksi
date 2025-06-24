#!/usr/bin/env python3

"""
Hot Reload Manager - Zero-downtime daemon reloading
Extracted from daemon_clean.py with 100% functionality preservation
"""

import asyncio
import json
import os
import sys
import subprocess
import time
from pathlib import Path
import logging

logger = logging.getLogger('daemon')

class HotReloadManager:
    """Manages hot reload functionality with state preservation"""
    
    def __init__(self, core_daemon, state_manager, agent_manager=None):
        self.core_daemon = core_daemon
        self.state_manager = state_manager
        self.agent_manager = agent_manager
    
    def serialize_state(self) -> dict:
        """Serialize complete daemon state for hot reload - EXACT copy from daemon_clean.py"""
        state = {}
        
        # Add state manager data
        if self.state_manager:
            state.update(self.state_manager.serialize_state())
        
        # Add agent manager data
        if self.agent_manager:
            state.update(self.agent_manager.serialize_state())
        
        return state
    
    def deserialize_state(self, state: dict):
        """Deserialize complete daemon state from hot reload - EXACT copy from daemon_clean.py"""
        # Load state manager data
        if self.state_manager:
            self.state_manager.deserialize_state(state)
        
        # Load agent manager data  
        if self.agent_manager:
            self.agent_manager.deserialize_state(state)
        
        logger.info("Hot reload state deserialization complete")
    
    async def wait_for_new_daemon(self, temp_socket: str, timeout: int = 10) -> bool:
        """Wait for new daemon to be ready with health check - EXACT copy from daemon_clean.py"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                reader, writer = await asyncio.open_unix_connection(temp_socket)
                # Send health check
                writer.write(b'HEALTH_CHECK\n')
                await writer.drain()
                
                # Read response
                response = await asyncio.wait_for(reader.readline(), timeout=2.0)
                if response.strip() == b'HEALTHY':
                    writer.close()
                    await writer.wait_closed()
                    return True
                    
                writer.close()
                await writer.wait_closed()
            except (ConnectionRefusedError, FileNotFoundError, asyncio.TimeoutError):
                pass
            
            await asyncio.sleep(0.5)
        
        return False
    
    async def transfer_state_to(self, temp_socket: str) -> bool:
        """Transfer state to new daemon - EXACT copy from daemon_clean.py"""
        try:
            reader, writer = await asyncio.open_unix_connection(temp_socket)
            
            # Serialize and send state
            state = self.serialize_state()
            state_json = json.dumps(state)
            
            writer.write(f'LOAD_STATE:{state_json}\n'.encode())
            await writer.drain()
            
            # Read confirmation
            response = await asyncio.wait_for(reader.readline(), timeout=5.0)
            success = response.strip() == b'STATE_LOADED'
            
            writer.close()
            await writer.wait_closed()
            
            logger.info(f"State transfer {'successful' if success else 'failed'}")
            return success
            
        except Exception as e:
            logger.error(f"State transfer failed: {e}")
            return False
    
    async def hot_reload_daemon(self) -> dict:
        """Hot reload daemon process with failure detection - EXACT copy from daemon_clean.py"""
        temp_socket = f"{self.core_daemon.socket_path}.new"
        
        try:
            # Remove temp socket if it exists
            if os.path.exists(temp_socket):
                os.unlink(temp_socket)
            
            # 1. Spawn new daemon on temp socket
            logger.info("Starting hot reload - spawning new daemon")
            new_process = subprocess.Popen([
                sys.executable, __file__,
                '--socket', temp_socket,
                '--hot-reload-from', self.core_daemon.socket_path
            ])
            
            # 2. Health check with timeout
            logger.info("Waiting for new daemon to become healthy")
            if await self.wait_for_new_daemon(temp_socket, timeout=15):
                # 3. Transfer state
                logger.info("New daemon healthy, transferring state")
                if await self.transfer_state_to(temp_socket):
                    # 4. Atomic handover
                    logger.info("State transferred, performing handover")
                    await self.handover_and_exit(temp_socket)
                    return {'status': 'reloaded'}  # This won't be reached due to exit
                else:
                    raise Exception("State transfer failed")
            else:
                raise Exception("New daemon failed health check")
                
        except Exception as e:
            logger.error(f"Hot reload failed: {e}")
            # 5. Rollback - kill new process and clean up
            try:
                new_process.terminate()
                new_process.wait(timeout=5)
            except:
                try:
                    new_process.kill()
                except:
                    pass
            
            if os.path.exists(temp_socket):
                os.unlink(temp_socket)
                
            return {'error': f'Hot reload failed: {str(e)}', 'status': 'rollback_complete'}
    
    async def handover_and_exit(self, temp_socket: str):
        """Perform atomic socket handover and exit - EXACT copy from daemon_clean.py"""
        try:
            # Move temp socket to main socket location
            if os.path.exists(self.core_daemon.socket_path):
                os.unlink(self.core_daemon.socket_path)
            os.rename(temp_socket, self.core_daemon.socket_path)
            
            logger.info("Hot reload handover complete - exiting old daemon")
            
            # Graceful exit
            self.core_daemon.shutdown_event.set()
            
        except Exception as e:
            logger.error(f"Handover failed: {e}")
            raise