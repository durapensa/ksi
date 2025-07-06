#!/usr/bin/env python3
"""
Dynamic KSI MCP (Model Context Protocol) Server

Exposes KSI events as MCP tools dynamically based on discovery.
Tools and modules can be filtered via command-line arguments.
"""

import argparse
import asyncio
import sys
from typing import Any, Dict, List, Optional, Set

from mcp import Tool
from mcp.server import Server
from mcp.server.stdio import stdio_server

from ksi_client import EventClient
from ksi_common.config import config


class DynamicKSIMCPServer(Server):
    """MCP server that dynamically exposes KSI events as tools."""

    def __init__(
        self,
        allowed_tools: Optional[List[str]] = None,
        allowed_modules: Optional[List[str]] = None,
        disallowed_tools: Optional[List[str]] = None,
        subscriptions: Optional[List[str]] = None,
    ):
        super().__init__("ksi-dynamic")
        self.allowed_tools = allowed_tools or []
        self.allowed_modules = allowed_modules or []
        self.disallowed_tools = set(disallowed_tools) if disallowed_tools else set()
        self.subscriptions = subscriptions or []
        self.client: Optional[EventClient] = None
        self._tool_cache: Dict[str, Any] = {}  # Cache help responses

        # Register handlers
        @self.list_tools()
        async def list_tools() -> List[Tool]:
            return await self._generate_tools()

        @self.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> Any:
            return await self._execute_tool(name, arguments)

    async def _initialize_client(self):
        """Initialize KSI client and discover events."""
        if not self.client:
            self.client = EventClient(socket_path=config.socket_path)
            await self.client.connect()

            # Get full discovery data
            discovery_result = await self.client.send_event("system:discover", {"detail": True})
            if isinstance(discovery_result, dict) and "events" in discovery_result:
                self._discovered_events = discovery_result["events"]

    async def _get_allowed_events(self) -> Set[str]:
        """Get the set of allowed events based on filters."""
        allowed_events = set()

        # Add specific allowed tools
        if self.allowed_tools:
            allowed_events.update(self.allowed_tools)

        # Add events from allowed modules
        if self.allowed_modules:
            for module in self.allowed_modules:
                # Ensure full module name
                if not module.startswith("ksi_daemon."):
                    module = f"ksi_daemon.{module}"

                try:
                    # Get events for this module
                    module_events = await self.client.send_event(
                        "module:list_events", {"module_name": module, "detail": False}
                    )
                    if isinstance(module_events, dict) and "events" in module_events:
                        allowed_events.update(module_events["events"].keys())
                except Exception:
                    # Module might not exist or have events
                    pass

        # Remove any disallowed tools (disallowed takes precedence)
        allowed_events -= self.disallowed_tools

        return allowed_events

    async def _generate_tools(self) -> List[Tool]:
        """Generate MCP tools from discovered KSI events."""
        await self._initialize_client()

        tools = []

        # Always include a raw event tool for flexibility
        tools.append(
            Tool(
                name="ksi_raw_event",
                description="Send any event directly to KSI daemon (bypasses filters)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "event": {"type": "string", "description": "Event name (e.g., 'system:health')"},
                        "data": {"type": "object", "description": "Event parameters", "default": {}},
                    },
                    "required": ["event"],
                },
            )
        )

        # Get allowed events and generate tools
        allowed_events = await self._get_allowed_events()

        for event_name in allowed_events:
            # Get MCP-formatted help for this event
            try:
                help_response = await self.client.send_event(
                    "system:help", {"event": event_name, "format_style": "mcp"}
                )

                if isinstance(help_response, dict):
                    # Response is already in MCP format
                    tool_name = f"ksi_{event_name.replace(':', '_')}"
                    tool = Tool(
                        name=tool_name,
                        description=help_response.get("description", f"Execute {event_name} event"),
                        inputSchema=help_response.get(
                            "inputSchema", {"type": "object", "properties": {}, "required": []}
                        ),
                    )
                    tools.append(tool)
            except Exception:
                # Event might not exist or help might fail
                pass

        return tools

    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool by sending the corresponding KSI event."""
        await self._initialize_client()

        try:
            # Handle raw event tool
            if tool_name == "ksi_raw_event":
                event_name = arguments.get("event")
                data = arguments.get("data", {})
                result = await self.client.send_event(event_name, data)
                return {"success": True, "result": result}

            # Handle specific event tools
            elif tool_name.startswith("ksi_"):
                # Convert tool name back to event name
                event_name = tool_name[4:].replace("_", ":")

                # Send event with tool arguments as data
                result = await self.client.send_event(event_name, arguments)
                return {"success": True, "result": result, "event": event_name}

            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            return {"success": False, "error": str(e), "tool": tool_name}

    async def _setup_subscriptions(self):
        """Set up event subscriptions for push notifications."""
        if not self.subscriptions:
            return

        await self._initialize_client()

        # Subscribe to specified events
        # TODO: Implement monitor:subscribe and forward as MCP notifications
        # For now, this is a placeholder for future implementation
        pass


async def main():
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="Dynamic KSI MCP Server")
    parser.add_argument(
        "--allowedTools",
        nargs="*",
        help="Specific event names to expose as tools (e.g., system:health completion:async)",
    )
    parser.add_argument(
        "--allowedModules", nargs="*", help="Modules whose events to expose (e.g., core.discovery conversation)"
    )
    parser.add_argument(
        "--disallowedTools", nargs="*", help="Specific event names to exclude (takes precedence over allowed)"
    )
    parser.add_argument("--subscriptions", nargs="*", help="Events to subscribe to for push notifications")
    parser.add_argument(
        "--list-tools", 
        action="store_true",
        help="List tool names that would be generated and exit (no KSI connection)"
    )
    parser.add_argument(
        "--exclude-raw-event",
        action="store_true", 
        help="Exclude ksi_raw_event tool (default behavior for basic profiles)"
    )

    args = parser.parse_args()

    # Handle --list-tools mode
    if args.list_tools:
        # Just compute and print tool names without connecting to KSI
        tool_names = []
        
        # Add raw event tool unless excluded
        if not args.exclude_raw_event:
            tool_names.append("ksi_raw_event")
        
        # Add specific allowed tools
        if args.allowedTools:
            for event_name in args.allowedTools:
                tool_name = f"ksi_{event_name.replace(':', '_')}"
                tool_names.append(tool_name)
        
        # Note: For modules, we'd need to connect to KSI to discover their events
        # In --list-tools mode, we can't support --allowedModules without a connection
        if args.allowedModules:
            print("Warning: --allowedModules requires KSI connection, skipping in --list-tools mode", file=sys.stderr)
        
        # Remove disallowed tools
        if args.disallowedTools:
            disallowed_tool_names = {f"ksi_{name.replace(':', '_')}" for name in args.disallowedTools}
            tool_names = [t for t in tool_names if t not in disallowed_tool_names]
        
        # Print one tool name per line
        for tool_name in tool_names:
            print(tool_name)
        sys.exit(0)

    # Normal server mode
    server = DynamicKSIMCPServer(
        allowed_tools=args.allowedTools,
        allowed_modules=args.allowedModules,
        disallowed_tools=args.disallowedTools,
        subscriptions=args.subscriptions,
    )

    # Run with stdio transport
    async with stdio_server() as transport:
        await server.run(transport)


if __name__ == "__main__":
    asyncio.run(main())
