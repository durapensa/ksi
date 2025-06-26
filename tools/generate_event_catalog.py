#!/usr/bin/env python3
"""
Generate EVENT_CATALOG.md from plugin introspection.

This script connects to the daemon and uses the discovery service
to automatically generate comprehensive event documentation.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from ksi_client import AsyncClient


class EventCatalogGenerator:
    """Generate event catalog documentation from live daemon introspection."""
    
    def __init__(self):
        self.client = AsyncClient(client_id="catalog_generator")
        self.events_by_namespace = {}
        
    async def connect(self) -> bool:
        """Connect to the daemon."""
        try:
            await self.client.connect()
            return True
        except Exception as e:
            print(f"Failed to connect to daemon: {e}")
            print("Please ensure daemon is running: ./daemon_control.sh start")
            return False
    
    async def discover_events(self) -> Dict[str, List[Dict[str, Any]]]:
        """Discover all available events organized by namespace."""
        try:
            # Get all events
            result = await self.client.request_event("system:discover", {})
            
            if "events" not in result:
                print("No events found in discovery response")
                return {}
            
            # Events are already organized by namespace in the response
            events_by_namespace = result["events"]
            
            # Sort namespaces
            sorted_namespaces = {}
            for ns in sorted(events_by_namespace.keys()):
                sorted_namespaces[ns] = events_by_namespace[ns]
            
            return sorted_namespaces
            
        except Exception as e:
            print(f"Failed to discover events: {e}")
            return {}
    
    async def get_event_details(self, event_name: str) -> Dict[str, Any]:
        """Get detailed help for a specific event."""
        try:
            result = await self.client.request_event("system:help", {
                "event": event_name
            })
            return result
        except Exception as e:
            print(f"Failed to get details for {event_name}: {e}")
            return {}
    
    def format_parameter(self, name: str, param_info: Dict[str, Any]) -> str:
        """Format a parameter for documentation."""
        parts = []
        
        # Parameter name and type
        param_type = param_info.get("type", "Any")
        required = param_info.get("required", False)
        
        parts.append(f"- `{name}` ({param_type})")
        
        # Required/optional
        if required:
            parts.append(" **[Required]**")
        else:
            parts.append(" [Optional]")
        
        # Description (if available from help)
        if "description" in param_info:
            parts.append(f" - {param_info['description']}")
        
        # Default value
        if "default" in param_info and not required:
            default_val = param_info["default"]
            if isinstance(default_val, str):
                parts.append(f" (default: `'{default_val}'`)")
            else:
                parts.append(f" (default: `{default_val}`)")
        
        # Validation info
        validation_parts = []
        
        # String validation
        if "pattern" in param_info:
            validation_parts.append(f"Pattern: `{param_info['pattern']}`")
        if "min_length" in param_info:
            validation_parts.append(f"Min length: {param_info['min_length']}")
        if "max_length" in param_info:
            validation_parts.append(f"Max length: {param_info['max_length']}")
        
        # Numeric validation
        if "min" in param_info:
            validation_parts.append(f"Min: {param_info['min']}")
        if "max" in param_info:
            validation_parts.append(f"Max: {param_info['max']}")
        
        # Allowed values for enums
        if "allowed_values" in param_info:
            values = ", ".join(f"`{v}`" for v in param_info["allowed_values"])
            validation_parts.append(f"Allowed values: {values}")
        
        # Schema for complex types
        if "schema" in param_info:
            validation_parts.append(f"Schema: see documentation")
        
        if validation_parts:
            parts.append(f"\n  - Validation: {', '.join(validation_parts)}")
        
        return "".join(parts)
    
    def generate_markdown(self, events_by_namespace: Dict[str, List[Dict[str, Any]]]) -> str:
        """Generate the markdown content for EVENT_CATALOG.md."""
        lines = []
        
        # Header
        lines.append("# KSI Event Catalog")
        lines.append("")
        lines.append("This document provides a comprehensive reference of all events available in the KSI daemon.")
        lines.append("Generated automatically from plugin introspection.")
        lines.append("")
        lines.append(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        lines.append("")
        
        # Table of Contents
        lines.append("## Table of Contents")
        lines.append("")
        for namespace in events_by_namespace:
            anchor = namespace.lower().replace(":", "")
            lines.append(f"- [{namespace.title()} Events](#{anchor}-events)")
        lines.append("")
        
        # Event details by namespace
        for namespace, events in events_by_namespace.items():
            anchor = namespace.lower().replace(":", "")
            lines.append(f"## {namespace.title()} Events")
            lines.append("")
            
            # Namespace summary
            event_names = [e["event"].split(":", 1)[1] for e in events]
            lines.append(f"Available events: {', '.join(f'`{name}`' for name in event_names)}")
            lines.append("")
            
            # Each event in the namespace
            for event in events:
                lines.append(f"### {event['event']}")
                lines.append("")
                
                # Summary/Description
                if "summary" in event:
                    lines.append(event["summary"])
                    lines.append("")
                elif "description" in event:
                    lines.append(event["description"])
                    lines.append("")
                
                # Plugin info (if available from detailed help)
                if "plugin" in event:
                    lines.append(f"**Plugin:** `{event['plugin']}`")
                    lines.append("")
                
                # Parameters
                params = event.get("parameters", {})
                if params:
                    lines.append("**Parameters:**")
                    lines.append("")
                    for param_name, param_info in params.items():
                        lines.append(self.format_parameter(param_name, param_info))
                    lines.append("")
                else:
                    lines.append("**Parameters:** None")
                    lines.append("")
                
                # Example usage
                lines.append("**Example:**")
                lines.append("```json")
                
                # Build example based on parameters
                example_data = {}
                params = event.get("parameters", {})
                for param_name, param_info in params.items():
                    if param_info.get("required", False):
                        # Add required parameters with example values
                        param_type = param_info.get("type", "str")
                        
                        if param_type in ["str", "string"]:
                            example_data[param_name] = f"example_{param_name}"
                        elif param_type in ["int", "integer"]:
                            example_data[param_name] = 123
                        elif param_type in ["bool", "boolean"]:
                            example_data[param_name] = True
                        elif param_type in ["list", "array"]:
                            example_data[param_name] = ["item1", "item2"]
                        elif param_type in ["dict", "object"]:
                            example_data[param_name] = {"key": "value"}
                        elif param_type == "float":
                            example_data[param_name] = 1.5
                        elif param_type == "Any":
                            example_data[param_name] = "any_value"
                        else:
                            example_data[param_name] = f"<{param_type}>"
                
                example = {
                    "event": event["event"],
                    "data": example_data
                }
                lines.append(json.dumps(example, indent=2))
                lines.append("```")
                lines.append("")
                
                # Response format if available
                if "response_format" in event:
                    lines.append("**Response Format:**")
                    lines.append("```json")
                    lines.append(json.dumps(event["response_format"], indent=2))
                    lines.append("```")
                    lines.append("")
                
                lines.append("---")
                lines.append("")
        
        # Footer
        lines.append("## Notes")
        lines.append("")
        lines.append("- All events follow the namespace:action pattern")
        lines.append("- Events are handled by plugins in a non-blocking manner")
        lines.append("- The first plugin to return a non-None response handles the event")
        lines.append("- Use correlation_id for request/response patterns")
        lines.append("")
        
        return "\n".join(lines)
    
    async def generate_catalog(self) -> bool:
        """Generate the event catalog."""
        # Connect to daemon
        if not await self.connect():
            return False
        
        print("Discovering events...")
        events_by_namespace = await self.discover_events()
        
        if not events_by_namespace:
            print("No events discovered")
            await self.client.disconnect()
            return False
        
        # Get detailed help for each event
        print(f"Found {sum(len(events) for events in events_by_namespace.values())} events across {len(events_by_namespace)} namespaces")
        print("Fetching detailed information...")
        
        # Enhance events with detailed help
        for namespace, events in events_by_namespace.items():
            for event in events:
                details = await self.get_event_details(event["event"])
                if details:
                    # Merge detailed info
                    event.update(details)
        
        # Generate markdown
        print("Generating markdown...")
        markdown_content = self.generate_markdown(events_by_namespace)
        
        # Write to file
        output_path = Path(__file__).parent.parent / "ksi_daemon" / "EVENT_CATALOG.md"
        output_path.write_text(markdown_content)
        print(f"✓ Generated {output_path}")
        
        # Also show summary
        print("\nEvent Summary:")
        for namespace, events in events_by_namespace.items():
            print(f"  {namespace}: {len(events)} events")
        
        await self.client.disconnect()
        return True


async def main():
    """Generate the event catalog."""
    generator = EventCatalogGenerator()
    
    success = await generator.generate_catalog()
    if not success:
        sys.exit(1)
    
    print("\n✓ EVENT_CATALOG.md generated successfully!")


if __name__ == "__main__":
    asyncio.run(main())