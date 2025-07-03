"""
MCP (Model Context Protocol) integration for KSI daemon.

Provides a single daemon-managed MCP server that exposes KSI events as tools
with dynamic permission filtering based on agent identity.
"""

from .mcp_config_manager import mcp_config_manager

__all__ = ["mcp_config_manager"]