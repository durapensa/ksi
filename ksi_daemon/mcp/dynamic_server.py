#!/usr/bin/env python3
"""
Dynamic MCP Server for KSI

A FastMCP-based server that dynamically generates tools based on agent permissions
and implements thin handshakes for efficient session continuity.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiosqlite
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
        
        # Session persistence database path
        self.session_db_path = config.db_dir / "mcp_sessions.db"
        
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
        self._cleanup_task = None
        self._start_session_cleanup()
        
        # Initialize session persistence
        self._load_sessions_task = None
        self._init_session_persistence()
    
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
            # Calculate approximate token savings
            full_tools = self.session_cache[session_key].get("tools", [])
            minimal_tools = self._get_minimal_tools(self.session_cache[session_key])
            
            # Rough estimation: 1 token per 4 characters
            full_chars = sum(len(str(t)) for t in full_tools)
            minimal_chars = sum(len(str(t)) for t in minimal_tools)
            token_savings = (full_chars - minimal_chars) // 4
            
            logger.info(
                "Thin handshake for known session",
                agent_id=agent_id,
                conversation_id=conversation_id,
                tools_count=len(minimal_tools),
                estimated_token_savings=token_savings
            )
            return minimal_tools
        
        # Full handshake - generate tools based on agent config
        logger.info(
            "Full handshake for new session",
            agent_id=agent_id,
            conversation_id=conversation_id,
            session_key=session_key
        )
        
        # Get agent info (includes resolved tool lists)
        agent_info = await self._get_agent_info(agent_id)
        
        # Generate available tools
        tools = await self._generate_tools_for_agent(agent_info)
        
        # Cache for future thin handshakes
        self.session_cache[session_key] = {
            "agent_id": agent_id,
            "conversation_id": conversation_id,
            "agent_info": agent_info,
            "tools": tools,
            "created": datetime.now()
        }
        
        return tools
    
    async def _get_agent_info(self, agent_id: str) -> Dict[str, Any]:
        """Get agent info including resolved tool lists from KSI daemon."""
        try:
            # Try to get agent info first (includes resolved tools)
            result = await self.ksi_client.send_event(
                "agent:status",
                {"agent_id": agent_id}
            )
            
            if isinstance(result, dict) and "config" in result:
                agent_config = result["config"]
                # Use resolved tool lists if available
                return {
                    "allowed_events": agent_config.get("allowed_events", []),
                    "allowed_claude_tools": agent_config.get("allowed_claude_tools", []),
                    "profile": result.get("permission_profile", "standard")
                }
                
        except Exception as e:
            logger.debug(f"Failed to get agent info for {agent_id}: {e}")
            
        # Fallback to permission query for backward compatibility
        try:
            result = await self.ksi_client.send_event(
                "permission:get_agent",
                {"agent_id": agent_id}
            )
            
            if isinstance(result, dict) and "permissions" in result:
                perms = result["permissions"]
                return {
                    "allowed_events": perms.get("tools", {}).get("allowed", []),
                    "allowed_claude_tools": [],
                    "profile": perms.get("level", "restricted")
                }
                
        except Exception as e:
            logger.warning(
                "Failed to get agent permissions, using defaults",
                agent_id=agent_id,
                error=str(e)
            )
            
        # Default minimal permissions
        return {
            "allowed_events": ["system:health"],
            "allowed_claude_tools": [],
            "profile": "restricted"
        }
    
    async def _generate_tools_for_agent(
        self, 
        agent_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate MCP tools based on agent's resolved capabilities."""
        tools = []
        
        # Get allowed events from agent's resolved capabilities
        allowed_events = agent_info.get("allowed_events", [])
        profile = agent_info.get("profile", "restricted")
        
        # Generate tool for each allowed event
        for event_name in allowed_events:
            tool = await self._create_tool_for_event(event_name)
            if tool:
                tools.append(tool)
        
        # Add raw event tool for trusted profiles
        if profile in ["trusted", "researcher"]:
            tools.append(self._get_raw_event_tool())
        
        logger.info(
            "Generated MCP tools for agent",
            event_count=len(allowed_events),
            tool_count=len(tools),
            profile=profile
        )
        
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
        """Return minimal tool schemas for thin handshake.
        
        This dramatically reduces token usage by providing only essential info.
        Tool names are required for security, but descriptions can be minimal.
        """
        tools = []
        for tool in session_data.get("tools", []):
            # Extract just the event name for a short description
            tool_name = tool["name"]
            if tool_name.startswith("ksi_"):
                # Convert ksi_system_health -> "system health"
                event_desc = tool_name[4:].replace("_", " ")
            else:
                event_desc = tool_name
            
            tools.append({
                "name": tool_name,
                "description": event_desc,  # Minimal description (3-5 words)
                "inputSchema": {"type": "object", "properties": {}}  # Minimal but valid schema
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
        
        self._cleanup_task = asyncio.create_task(cleanup_sessions())
    
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
    
    async def cleanup(self):
        """Clean up resources on shutdown."""
        # Disconnect KSI client
        if self.ksi_client:
            await self.ksi_client.disconnect()
            self.ksi_client = None
        
        # Cancel background cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        
        # Cancel load sessions task if still running
        if self._load_sessions_task and not self._load_sessions_task.done():
            self._load_sessions_task.cancel()
            try:
                await self._load_sessions_task
            except asyncio.CancelledError:
                pass
            self._load_sessions_task = None
        
        # Save sessions before clearing
        await self._save_sessions()
        
        # Clear session caches
        self.session_cache.clear()
        self.session_last_seen.clear()
        
        logger.info("Cleaned up MCP server resources")
    
    def _init_session_persistence(self):
        """Initialize session persistence database."""
        # Create task to load sessions after server starts
        self._load_sessions_task = asyncio.create_task(self._load_sessions())
    
    async def _load_sessions(self):
        """Load persisted sessions from database."""
        try:
            # Ensure DB directory exists
            self.session_db_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiosqlite.connect(self.session_db_path) as db:
                # Create table if not exists
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS mcp_sessions (
                        session_key TEXT PRIMARY KEY,
                        session_data TEXT NOT NULL,
                        last_seen TIMESTAMP NOT NULL
                    )
                """)
                await db.commit()
                
                # Load sessions less than 24 hours old
                cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
                async with db.execute(
                    "SELECT session_key, session_data, last_seen FROM mcp_sessions WHERE last_seen > ?",
                    (cutoff,)
                ) as cursor:
                    async for row in cursor:
                        session_key, session_data_json, last_seen_str = row
                        try:
                            session_data = json.loads(session_data_json)
                            self.session_cache[session_key] = session_data
                            self.session_last_seen[session_key] = datetime.fromisoformat(last_seen_str)
                        except Exception as e:
                            logger.warning(f"Failed to load session {session_key}: {e}")
                
                logger.info(f"Loaded {len(self.session_cache)} MCP sessions from persistence")
                
        except Exception as e:
            logger.error(f"Failed to load MCP sessions: {e}")
    
    async def _save_sessions(self):
        """Save current sessions to database."""
        if not self.session_cache:
            return
            
        try:
            async with aiosqlite.connect(self.session_db_path) as db:
                # Save all current sessions
                for session_key, session_data in self.session_cache.items():
                    last_seen = self.session_last_seen.get(session_key, datetime.now())
                    
                    # Don't save full tool schemas to save space
                    save_data = session_data.copy()
                    if "tools" in save_data:
                        # Only save tool names, not full definitions
                        save_data["tools"] = [
                            {"name": t.get("name")} if isinstance(t, dict) else t
                            for t in save_data["tools"]
                        ]
                    
                    await db.execute(
                        "INSERT OR REPLACE INTO mcp_sessions (session_key, session_data, last_seen) VALUES (?, ?, ?)",
                        (session_key, json.dumps(save_data), last_seen.isoformat())
                    )
                
                # Clean up old sessions
                cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
                await db.execute("DELETE FROM mcp_sessions WHERE last_seen < ?", (cutoff,))
                
                await db.commit()
                logger.debug(f"Saved {len(self.session_cache)} MCP sessions to persistence")
                
        except Exception as e:
            logger.error(f"Failed to save MCP sessions: {e}")
