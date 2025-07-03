#!/usr/bin/env python3
"""
Dynamic MCP Server for KSI

A FastMCP-based server that dynamically generates tools based on agent permissions
and implements thin handshakes for efficient session continuity.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from ksi_client import EventClient
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("mcp_dynamic_server")


class KSIDynamicMCPServer(FastMCP):
    """
    MCP server that exposes KSI events as tools with permission-based filtering.
    
    Features:
    - Dynamic tool generation based on agent permissions
    - Thin handshake support for session continuity
    - Agent isolation via header-based identification
    - Automatic session cleanup
    """
    
    def __init__(self):
        super().__init__(
            name="ksi-mcp",
            instructions="KSI daemon interface - provides access to system events and services"
        )
        
        # Session management for thin handshakes
        self.session_cache: Dict[str, Dict[str, Any]] = {}
        self.session_last_seen: Dict[str, datetime] = {}
        
        # KSI client for event communication
        self.ksi_client: Optional[EventClient] = None
        
        # Register default tool
        @self.tool
        async def ksi_raw_event(
            event: str,
            ctx: Context,
            data: Dict[str, Any] = {}
        ) -> Dict[str, Any]:
            """
            Send a raw event to KSI daemon (requires trusted permissions).
            
            Args:
                event: Event name (e.g., 'system:health')
                data: Event parameters
                ctx: MCP context with agent information
            """
            # Check permissions
            agent_id = ctx.request_context.headers.get("X-KSI-Agent-ID", "unknown")
            if not await self._check_raw_event_permission(agent_id):
                raise ToolError("Permission denied for raw event access")
            
            # Send event
            return await self._send_ksi_event(event, data, ctx)
        
        # Start session cleanup task
        self._start_session_cleanup()
    
    async def initialize(self):
        """Initialize KSI client connection."""
        if not self.ksi_client:
            self.ksi_client = EventClient(socket_path=config.socket_path)
            await self.ksi_client.connect()
            logger.info("KSI client connected")
    
    async def list_tools(self, ctx: Context) -> List[Dict[str, Any]]:
        """
        List available tools based on agent permissions.
        
        Implements thin handshake by returning minimal schemas for known sessions.
        """
        await self.initialize()
        
        # Extract agent identity from headers
        agent_id = ctx.request_context.headers.get("X-KSI-Agent-ID", "unknown")
        conversation_id = ctx.request_context.headers.get("X-KSI-Conversation-ID", "unknown")
        session_key = f"{agent_id}:{conversation_id}"
        
        # Update last seen time
        self.session_last_seen[session_key] = datetime.now()
        
        # Check if this is a known session (thin handshake)
        if session_key in self.session_cache:
            logger.debug(
                "Thin handshake for known session",
                agent_id=agent_id,
                conversation_id=conversation_id
            )
            # Return cached tool names with minimal schemas
            return self._get_minimal_tools(self.session_cache[session_key])
        
        # Full handshake - generate tools based on permissions
        logger.info(
            "Full handshake for new session",
            agent_id=agent_id,
            conversation_id=conversation_id
        )
        
        # Get agent permissions
        permissions = await self._get_agent_permissions(agent_id)
        
        # Generate available tools
        tools = await self._generate_tools_for_permissions(permissions)
        
        # Cache for future thin handshakes
        self.session_cache[session_key] = {
            "agent_id": agent_id,
            "conversation_id": conversation_id,
            "permissions": permissions,
            "tools": tools,
            "created": datetime.now()
        }
        
        return tools
    
    async def _get_agent_permissions(self, agent_id: str) -> Dict[str, Any]:
        """Get permissions for an agent from KSI daemon."""
        try:
            result = await self.ksi_client.send_event(
                "permission:get_agent",
                {"agent_id": agent_id}
            )
            return result if isinstance(result, dict) else {}
        except Exception as e:
            logger.warning(
                "Failed to get agent permissions, using defaults",
                agent_id=agent_id,
                error=str(e)
            )
            # Default minimal permissions
            return {
                "allowed_tools": ["system:health"],
                "profile": "restricted"
            }
    
    async def _generate_tools_for_permissions(
        self, 
        permissions: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate MCP tools based on agent permissions."""
        tools = []
        
        # Get allowed events
        allowed_tools = set(permissions.get("allowed_tools", []))
        allowed_modules = permissions.get("allowed_modules", [])
        disallowed_tools = set(permissions.get("disallowed_tools", []))
        
        # Get events from allowed modules
        for module in allowed_modules:
            try:
                module_events = await self.ksi_client.send_event(
                    "module:list_events",
                    {"module_name": module, "detail": False}
                )
                if isinstance(module_events, dict) and "events" in module_events:
                    allowed_tools.update(module_events["events"].keys())
            except Exception as e:
                logger.warning(f"Failed to get events for module {module}: {e}")
        
        # Remove disallowed tools
        allowed_tools -= disallowed_tools
        
        # Generate tool for each allowed event
        for event_name in allowed_tools:
            tool = await self._create_tool_for_event(event_name)
            if tool:
                tools.append(tool)
        
        # Add raw event tool for trusted profiles
        if permissions.get("profile") in ["trusted", "researcher"]:
            tools.append(self._get_raw_event_tool())
        
        return tools
    
    async def _create_tool_for_event(self, event_name: str) -> Optional[Dict[str, Any]]:
        """Create an MCP tool definition for a KSI event."""
        try:
            # Get event details using system:help with MCP format
            help_response = await self.ksi_client.send_event(
                "system:help",
                {"event": event_name, "format_style": "mcp"}
            )
            
            if not isinstance(help_response, dict):
                return None
            
            # Convert to MCP tool format
            tool_name = f"ksi_{event_name.replace(':', '_')}"
            
            # Register dynamic tool handler
            @self.tool(name=tool_name)
            async def event_tool(**kwargs) -> Dict[str, Any]:
                """Dynamic tool handler for KSI event."""
                ctx = kwargs.pop('ctx', None)
                return await self._send_ksi_event(event_name, kwargs, ctx)
            
            return {
                "name": tool_name,
                "description": help_response.get("description", f"Execute {event_name} event"),
                "inputSchema": help_response.get("inputSchema", {
                    "type": "object",
                    "properties": {}
                })
            }
            
        except Exception as e:
            logger.warning(f"Failed to create tool for {event_name}: {e}")
            return None
    
    async def _send_ksi_event(
        self, 
        event_name: str, 
        data: Dict[str, Any],
        ctx: Optional[Context] = None
    ) -> Dict[str, Any]:
        """Send an event to KSI daemon and return the result."""
        # Log tool usage
        agent_id = "unknown"
        if ctx and hasattr(ctx, 'request_context'):
            agent_id = ctx.request_context.headers.get("X-KSI-Agent-ID", "unknown")
        
        logger.info(
            "MCP tool invoked",
            agent_id=agent_id,
            event=event_name,
            tool=f"ksi_{event_name.replace(':', '_')}"
        )
        
        try:
            result = await self.ksi_client.send_event(event_name, data)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"KSI event failed: {e}", event=event_name)
            return {"success": False, "error": str(e)}
    
    def _get_minimal_tools(self, session_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return minimal tool schemas for thin handshake."""
        tools = []
        for tool in session_data.get("tools", []):
            # Return just enough for tool to be available
            tools.append({
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": {"type": "object"}  # Minimal schema
            })
        return tools
    
    def _get_raw_event_tool(self) -> Dict[str, Any]:
        """Get the raw event tool definition."""
        return {
            "name": "ksi_raw_event",
            "description": "Send a raw event to KSI daemon (requires trusted permissions)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "event": {
                        "type": "string",
                        "description": "Event name (e.g., 'system:health')"
                    },
                    "data": {
                        "type": "object",
                        "description": "Event parameters",
                        "default": {}
                    }
                },
                "required": ["event"]
            }
        }
    
    async def _check_raw_event_permission(self, agent_id: str) -> bool:
        """Check if agent has permission to use raw events."""
        permissions = await self._get_agent_permissions(agent_id)
        return permissions.get("profile") in ["trusted", "researcher"]
    
    def _start_session_cleanup(self):
        """Start background task to clean up old sessions."""
        async def cleanup_sessions():
            while True:
                try:
                    await asyncio.sleep(300)  # Run every 5 minutes
                    
                    now = datetime.now()
                    expired_sessions = []
                    
                    # Find sessions older than 2 hours
                    for session_key, last_seen in self.session_last_seen.items():
                        if now - last_seen > timedelta(hours=2):
                            expired_sessions.append(session_key)
                    
                    # Clean up expired sessions
                    for session_key in expired_sessions:
                        self.session_cache.pop(session_key, None)
                        self.session_last_seen.pop(session_key, None)
                        logger.debug(f"Cleaned up expired session: {session_key}")
                    
                    if expired_sessions:
                        logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
                        
                except Exception as e:
                    logger.error(f"Session cleanup error: {e}")
        
        asyncio.create_task(cleanup_sessions())
    
    async def clear_sessions(self, agent_id: str) -> int:
        """Clear sessions for a specific agent."""
        cleared = 0
        keys_to_remove = []
        
        for session_key in list(self.session_cache.keys()):
            if session_key.startswith(f"{agent_id}:"):
                keys_to_remove.append(session_key)
        
        for key in keys_to_remove:
            self.session_cache.pop(key, None)
            self.session_last_seen.pop(key, None)
            cleared += 1
        
        return cleared
    
    async def clear_all_sessions(self) -> int:
        """Clear all cached sessions."""
        count = len(self.session_cache)
        self.session_cache.clear()
        self.session_last_seen.clear()
        return count