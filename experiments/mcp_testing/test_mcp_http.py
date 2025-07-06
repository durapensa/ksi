#!/usr/bin/env python3
"""Test MCP HTTP transport with FastMCP"""

import asyncio
from fastmcp import FastMCP

# Create minimal server
server = FastMCP("test-http")

@server.tool
async def hello(name: str = "world") -> str:
    """Say hello"""
    return f"Hello, {name}!"

# Run with stateful HTTP
if __name__ == "__main__":
    print("Starting MCP server on http://localhost:8080")
    print("Transport: stateful HTTP")
    asyncio.run(server.run_http_async(
        transport="http",  # Stateful HTTP
        port=8080,
        log_level="DEBUG"
    ))