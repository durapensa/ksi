#!/usr/bin/env python3

"""
Core Daemon - Main server logic and manager coordination
Extracted from daemon_clean.py with 100% functionality preservation
"""

import asyncio
import json
import os
import logging
from pathlib import Path

logger = logging.getLogger('daemon')

class ClaudeDaemonCore:
    """Core daemon server with dependency injection for all managers - EXACT functionality from daemon_clean.py"""
    
    def __init__(self, socket_path: str, hot_reload_from: str = None):
        self.socket_path = socket_path
        self.hot_reload_from = hot_reload_from
        self.is_hot_reload = hot_reload_from is not None
        self.shutdown_event = asyncio.Event()
        
        # Manager instances - will be injected by main entry point
        self.state_manager = None
        self.process_manager = None
        self.agent_manager = None
        self.utils_manager = None
        self.hot_reload_manager = None
        self.command_handler = None
    
    def set_managers(self, state_manager, process_manager, agent_manager, utils_manager, hot_reload_manager, command_handler):
        """Dependency injection - wire all managers together"""
        self.state_manager = state_manager
        self.process_manager = process_manager
        self.agent_manager = agent_manager
        self.utils_manager = utils_manager
        self.hot_reload_manager = hot_reload_manager
        self.command_handler = command_handler
        
        # Set up cross-manager dependencies
        if self.process_manager and self.agent_manager:
            self.process_manager.set_agent_manager(self.agent_manager)
    
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
        """Clean, simple client handler - EXACT copy from daemon_clean.py"""
        try:
            data = await reader.readline()
            if not data:
                return
            
            # Try JSON first
            try:
                output = json.loads(data.decode())
                # Handle JSON output (session tracking, etc.)
                session_id = output.get('sessionId') or output.get('session_id')
                if session_id and self.state_manager:
                    self.state_manager.track_session(session_id, output)
                    logger.info(f"Captured session: {session_id}")
                return
                
            except json.JSONDecodeError:
                # Handle as command
                command = data.decode().strip()
                logger.info(f"Received command: {command[:50]}...")
                
                # Route to command handler - clean and simple!
                if self.command_handler:
                    should_continue = await self.command_handler.handle_command(command, writer)
                    if not should_continue:
                        return  # Shutdown requested
                else:
                    logger.error("No command handler available")
                
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
    
    async def start(self):
        """Start the daemon server - EXACT copy from daemon_clean.py"""
        # Create directories - EXACT copy from daemon_clean.py
        for dir_name in ['shared_state', 'sockets', 'claude_logs', 'agent_profiles']:
            os.makedirs(dir_name, exist_ok=True)
        
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        server = await asyncio.start_unix_server(
            self.handle_client,
            path=self.socket_path
        )
        
        logger.info(f"Modular daemon listening on {self.socket_path}")
        
        async with server:
            await self.shutdown_event.wait()