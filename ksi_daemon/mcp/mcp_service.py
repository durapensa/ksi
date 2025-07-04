#!/usr/bin/env python3
"""
MCP Service Module

Manages the lifecycle of the daemon's MCP server, providing KSI functionality
to agents through the Model Context Protocol.
"""

import asyncio
from typing import Any, Dict, Optional

from ksi_common.config import config
from ksi_common.logging import get_bound_logger
from ksi_daemon.event_system import event_handler, shutdown_handler, get_router

from .dynamic_server import KSIDynamicMCPServer

logger = get_bound_logger("mcp_service")

# Module state
mcp_server: Optional[KSIDynamicMCPServer] = None
server_task: Optional[asyncio.Task] = None


@event_handler("system:startup")
async def handle_startup(data: Dict[str, Any]) -> Dict[str, Any]:
    """Start MCP server on daemon startup."""
    global mcp_server, server_task
    
    if not config.mcp_enabled:
        logger.info("MCP server disabled in configuration")
        return {"status": "mcp_disabled"}
    
    try:
        # Create server instance
        mcp_server = KSIDynamicMCPServer()
        
        # Start server in background
        server_task = asyncio.create_task(
            mcp_server.run_http_async(
                transport="streamable-http",
                host="127.0.0.1",  # Localhost only for security
                port=config.mcp_server_port,
                log_level="INFO"
            ),
            name="mcp_http_server"
        )
        
        logger.info(
            "MCP server started",
            port=config.mcp_server_port,
            transport="streamable-http"
        )
        
        return {
            "status": "mcp_started",
            "port": config.mcp_server_port,
            "url": f"http://127.0.0.1:{config.mcp_server_port}"
        }
        
    except Exception as e:
        logger.error("Failed to start MCP server", error=str(e))
        return {"status": "mcp_failed", "error": str(e)}


@shutdown_handler("mcp_service")
async def handle_shutdown(data: Dict[str, Any]) -> None:
    """Stop MCP server on daemon shutdown.
    
    This is a critical shutdown handler that ensures the HTTP server
    is properly shut down before the daemon exits.
    """
    global mcp_server, server_task
    
    # Clean up MCP server resources first
    if mcp_server:
        logger.info("Cleaning up MCP server resources")
        try:
            await mcp_server.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up MCP server: {e}")
    
    # Then handle the server task shutdown more gracefully
    if server_task and not server_task.done():
        logger.info("Initiating graceful MCP server shutdown")
        
        # First, try to let uvicorn shutdown gracefully
        # The server task will complete when uvicorn finishes its shutdown sequence
        server_task.cancel()
        
        try:
            # Give uvicorn time to handle the cancellation gracefully
            # Use shield to prevent immediate cancellation propagation
            await asyncio.wait_for(
                asyncio.shield(server_task),
                timeout=2.0
            )
            logger.info("MCP server shut down gracefully")
        except asyncio.TimeoutError:
            logger.warning("MCP server shutdown timeout, forcing stop")
            # Server didn't stop in time, but that's OK
        except asyncio.CancelledError:
            # This is expected when the server task is cancelled
            logger.info("MCP server task cancelled successfully")
        except Exception as e:
            # Log any other unexpected errors but don't fail
            logger.error(f"Error during MCP server shutdown: {e}")
    
    mcp_server = None
    server_task = None
    
    # Acknowledge shutdown completion
    router = get_router()
    await router.acknowledge_shutdown("mcp_service")
    logger.info("MCP service shutdown acknowledged")
    logger.info("MCP server stopped")


@event_handler("mcp:status")
async def handle_mcp_status(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get MCP server status."""
    if not mcp_server:
        return {
            "running": False,
            "enabled": config.mcp_enabled
        }
    
    return {
        "running": server_task and not server_task.done(),
        "enabled": config.mcp_enabled,
        "port": config.mcp_server_port,
        "url": f"http://127.0.0.1:{config.mcp_server_port}",
        "sessions": len(mcp_server.session_cache) if hasattr(mcp_server, 'session_cache') else 0
    }


@event_handler("mcp:clear_sessions")
async def handle_clear_sessions(data: Dict[str, Any]) -> Dict[str, Any]:
    """Clear MCP session cache for specific agent or all."""
    if not mcp_server:
        return {"error": "MCP server not running"}
    
    agent_id = data.get("agent_id")
    
    if hasattr(mcp_server, 'clear_sessions'):
        if agent_id:
            cleared = await mcp_server.clear_sessions(agent_id)
            return {"cleared": cleared, "agent_id": agent_id}
        else:
            cleared = await mcp_server.clear_all_sessions()
            return {"cleared": cleared, "agent_id": "all"}
    
    return {"error": "Session management not available"}