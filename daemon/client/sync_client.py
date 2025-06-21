#!/usr/bin/env python3
"""
Synchronous Client - Simplified synchronous interface for JSON Protocol v2.0

Provides a clean, synchronous API for simple use cases that don't need async/await.
Uses asyncio internally but exposes synchronous methods.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from .utils import CommandBuilder, ConnectionManager, ResponseHandler

logger = logging.getLogger('daemon.sync_client')

class SyncClient:
    """Synchronous client for daemon communication"""
    
    def __init__(self, socket_path: str = "sockets/claude_daemon.sock", timeout: float = 5.0):
        self.socket_path = socket_path
        self.timeout = timeout
    
    def _run_async(self, coro):
        """Run async coroutine in sync context"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, we can't use run_until_complete
                # This would require using asyncio.create_task() but that's more complex
                raise RuntimeError("SyncClient cannot be used from within async context. Use AsyncClient instead.")
            return loop.run_until_complete(coro)
        except RuntimeError:
            # No existing loop, create new one
            return asyncio.run(coro)
    
    def send_command(self, command: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Send a command synchronously
        
        Args:
            command: Command name
            parameters: Command parameters
            
        Returns:
            Response dict
            
        Raises:
            ConnectionError: If connection fails
            RuntimeError: If called from async context
        """
        cmd_obj = CommandBuilder.build_command(command, parameters)
        return self._run_async(
            ConnectionManager.send_command_once(self.socket_path, cmd_obj, self.timeout)
        )
    
    def health_check(self) -> bool:
        """Check if daemon is healthy"""
        try:
            response = self.send_command("HEALTH_CHECK")
            return ResponseHandler.check_success(response) and \
                   ResponseHandler.get_result_data(response).get("status") == "healthy"
        except Exception:
            return False
    
    def spawn_claude(self, prompt: str, mode: str = "sync", session_id: str = None, 
                    model: str = "sonnet", agent_id: str = None, enable_tools: bool = True) -> str:
        """
        Spawn Claude and return result text (sync mode) or process_id (async mode)
        
        Args:
            prompt: Text prompt for Claude
            mode: "sync" or "async"  
            session_id: Optional session ID for continuity
            model: Claude model to use
            agent_id: Optional agent identifier
            enable_tools: Whether to enable tool usage
            
        Returns:
            For sync mode: Claude's response text
            For async mode: Process ID string
            
        Raises:
            ConnectionError: If connection fails
            ValueError: If response format is unexpected
        """
        cmd_obj = CommandBuilder.build_spawn_command(
            prompt=prompt, mode=mode, session_id=session_id,
            model=model, agent_id=agent_id, enable_tools=enable_tools
        )
        
        response = self._run_async(
            ConnectionManager.send_command_once(self.socket_path, cmd_obj, self.timeout)
        )
        
        if not ResponseHandler.check_success(response):
            error_msg = ResponseHandler.get_error_message(response)
            raise ValueError(f"SPAWN command failed: {error_msg}")
        
        result_data = ResponseHandler.get_result_data(response)
        
        if mode == "sync":
            # Extract response text
            return result_data.get("result", "") or result_data.get("content", "")
        else:
            # Extract process ID
            return result_data.get("process_id", "")
    
    def get_agents(self) -> Dict[str, Any]:
        """Get all registered agents"""
        response = self.send_command("GET_AGENTS")
        if ResponseHandler.check_success(response):
            return ResponseHandler.get_result_data(response).get("agents", {})
        return {}
    
    def set_shared_state(self, key: str, value: Any) -> bool:
        """Set shared state value"""
        response = self.send_command("SET_SHARED", {"key": key, "value": value})
        return ResponseHandler.check_success(response) and \
               ResponseHandler.get_result_data(response).get("status") == "set"
    
    def get_shared_state(self, key: str) -> Any:
        """Get shared state value"""
        response = self.send_command("GET_SHARED", {"key": key})
        if ResponseHandler.check_success(response):
            return ResponseHandler.get_result_data(response).get("value")
        return None
    
    def cleanup(self, cleanup_type: str) -> str:
        """Run cleanup operation"""
        response = self.send_command("CLEANUP", {"cleanup_type": cleanup_type})
        if ResponseHandler.check_success(response):
            return ResponseHandler.get_result_data(response).get("details", "")
        return ResponseHandler.get_error_message(response)
    
    def shutdown_daemon(self) -> bool:
        """Shutdown the daemon"""
        try:
            response = self.send_command("SHUTDOWN")
            return ResponseHandler.check_success(response)
        except ConnectionError:
            # Daemon may close connection before responding
            return True