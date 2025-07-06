#!/usr/bin/env python3
"""Test MCP stdio transport with FastMCP"""

import asyncio
from fastmcp import FastMCP

# Create minimal server
server = FastMCP("test-stdio")

@server.tool
async def hello(name: str = "world") -> str:
    """Say hello"""
    return f"Hello, {name}!"

# Run with stdio
if __name__ == "__main__":
    server.run()  # Default is stdio