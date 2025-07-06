#!/usr/bin/env python3
"""
KSI MCP (Model Context Protocol) Server

Exposes KSI events as tools for Claude to use directly.
This allows Claude to interact with KSI without needing file system
or bash access - just through the standardized MCP tool interface.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from pathlib import Path

# MCP server base (hypothetical - based on MCP spec)
from mcp.server import MCPServer, Tool, ToolResult, ToolParameter

from ksi_client import EventClient
from ksi_client.prompt_generator import KSIPromptGenerator


class KSIMCPServer(MCPServer):
    """MCP server that exposes KSI events as tools."""
    
    def __init__(self, socket_path: Optional[Path] = None):
        super().__init__()
        self.socket_path = socket_path
        self.client: Optional[EventClient] = None
        self._discovered_tools: List[Tool] = []
        
    async def initialize(self):
        """Initialize KSI connection and discover events."""
        self.client = EventClient(socket_path=self.socket_path)
        await self.client.connect()
        
        # Ensure discovery
        if not self.client._discovered:
            await self.client.discover()
        
        # Generate tools from discovered events
        self._discovered_tools = self._generate_tools_from_events()
        
    def _generate_tools_from_events(self) -> List[Tool]:
        """Convert KSI events to MCP tools."""
        tools = []
        
        # Add a meta-tool for raw event sending
        tools.append(Tool(
            name="ksi_send_event",
            description="Send a raw event to KSI daemon",
            parameters=[
                ToolParameter(
                    name="event",
                    type="string",
                    description="Event name (e.g., 'completion:async')",
                    required=True
                ),
                ToolParameter(
                    name="data",
                    type="object",
                    description="Event data/parameters as JSON object",
                    required=False,
                    default={}
                )
            ],
            examples=[{
                "event": "system:health",
                "data": {}
            }, {
                "event": "completion:async",
                "data": {
                    "prompt": "Hello",
                    "model": "claude-cli/sonnet"
                }
            }]
        ))
        
        # Generate specific tools for high-value events
        priority_events = [
            "completion:async",
            "conversation:list",
            "conversation:get",
            "state:set",
            "state:get",
            "agent:spawn",
            "system:health"
        ]
        
        for event_name in priority_events:
            event_info = self.client.get_event_info(event_name)
            if event_info:
                tool = self._event_to_tool(event_info)
                if tool:
                    tools.append(tool)
        
        return tools
    
    def _event_to_tool(self, event_info: Dict[str, Any]) -> Optional[Tool]:
        """Convert a single KSI event to an MCP tool."""
        event_name = event_info.get("event", "")
        if not event_name:
            return None
        
        # Create tool-friendly name
        tool_name = f"ksi_{event_name.replace(':', '_')}"
        
        # Build parameters from event parameters
        params = []
        for param_name, param_info in event_info.get("parameters", {}).items():
            param = ToolParameter(
                name=param_name,
                type=self._ksi_type_to_mcp_type(param_info.get("type", "string")),
                description=param_info.get("description", f"{param_name} parameter"),
                required=param_info.get("required", False),
                default=param_info.get("default"),
                enum=param_info.get("allowed_values")
            )
            params.append(param)
        
        # Build examples from event examples
        examples = []
        for example in event_info.get("examples", []):
            examples.append(example.get("data", {}))
        
        return Tool(
            name=tool_name,
            description=event_info.get("summary", f"Execute {event_name} event"),
            parameters=params,
            examples=examples
        )
    
    def _ksi_type_to_mcp_type(self, ksi_type: str) -> str:
        """Convert KSI type to MCP type."""
        type_map = {
            "str": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
            "dict": "object",
            "list": "array",
            "any": "any"
        }
        return type_map.get(ksi_type, "string")
    
    async def list_tools(self) -> List[Tool]:
        """List available tools."""
        return self._discovered_tools
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool by sending the corresponding KSI event."""
        try:
            # Handle raw event tool
            if tool_name == "ksi_send_event":
                event_name = arguments.get("event")
                data = arguments.get("data", {})
                
                result = await self.client.send_event(event_name, data)
                
                return ToolResult(
                    success=True,
                    result=result,
                    metadata={
                        "event": event_name,
                        "response_type": type(result).__name__
                    }
                )
            
            # Handle specific event tools
            elif tool_name.startswith("ksi_"):
                # Convert tool name back to event name
                event_name = tool_name[4:].replace('_', ':')
                
                # Send event with tool arguments as data
                result = await self.client.send_event(event_name, arguments)
                
                return ToolResult(
                    success=True,
                    result=result,
                    metadata={
                        "event": event_name,
                        "tool": tool_name
                    }
                )
            
            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown tool: {tool_name}"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                metadata={
                    "tool": tool_name,
                    "arguments": arguments
                }
            )
    
    async def get_tool_documentation(self, tool_name: str) -> Optional[str]:
        """Get detailed documentation for a tool."""
        if tool_name == "ksi_send_event":
            return """Send any event to the KSI daemon.
            
This is the most flexible tool - it can send any of the 94+ available events.
Use system:discover to find all events, and system:help to get details on specific events.

Common events:
- completion:async - Send a prompt to an LLM
- conversation:list - List available conversations  
- state:set/get - Manage persistent state
- agent:spawn - Create autonomous agents
"""
        
        elif tool_name.startswith("ksi_"):
            event_name = tool_name[4:].replace('_', ':')
            
            # Get detailed help from KSI
            try:
                help_response = await self.client.system.help(event=event_name)
                
                doc = f"KSI Event: {event_name}\n\n"
                doc += f"{help_response.get('summary', 'No description')}\n\n"
                
                if help_response.get('parameters'):
                    doc += "Parameters:\n"
                    for name, info in help_response['parameters'].items():
                        doc += f"  - {name}: {info}\n"
                
                if help_response.get('examples'):
                    doc += "\nExamples:\n"
                    for ex in help_response['examples']:
                        doc += f"  {json.dumps(ex, indent=2)}\n"
                
                return doc
                
            except Exception:
                return f"Execute KSI event: {event_name}"
        
        return None


# MCP server configuration for KSI
MCP_CONFIG = {
    "name": "ksi",
    "version": "1.0.0",
    "description": "KSI daemon interface - provides access to completion, conversation, state, and agent services",
    "server_class": "KSIMCPServer",
    "configuration_schema": {
        "type": "object",
        "properties": {
            "socket_path": {
                "type": "string",
                "description": "Path to KSI daemon socket",
                "default": "var/run/daemon.sock"
            }
        }
    }
}