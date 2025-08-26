#!/usr/bin/env python3
"""
Generate KSI documentation from system:discover - Compact Version.

Uses a more token-efficient format for parameters while maintaining readability:
- Parameters as arrays: [type, required, default, description]
- Omits empty triggers arrays
- More compact JSON structure
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any, List, Optional, Union

from ksi_client import EventClient


def compact_parameter(param_info: Dict[str, Any]) -> List[Union[str, bool, Any]]:
    """Convert verbose parameter dict to compact array format."""
    return [
        param_info.get('type', 'Any'),
        param_info.get('required', False),
        param_info.get('default'),
        param_info.get('description', '')
    ]


def expand_parameter(param_array: List[Union[str, bool, Any]]) -> Dict[str, Any]:
    """Convert compact array back to verbose format for display."""
    if len(param_array) >= 4:
        return {
            'type': param_array[0],
            'required': param_array[1],
            'default': param_array[2],
            'description': param_array[3]
        }
    return {}


def format_parameters_compact(params: Dict[str, List]) -> List[str]:
    """Format compact parameters for markdown documentation."""
    if not params:
        return ["None"]
    
    lines = []
    for name, param_array in params.items():
        param_type, required, default, description = param_array[:4]
        
        # Build parameter line
        parts = [f"- **{name}**"]
        
        # Type
        if param_type and param_type != 'Any':
            parts.append(f"`{param_type}`")
        
        # Required/optional with default
        if required:
            parts.append("(required)")
        elif default is not None:
            if default == "":
                parts.append('(default: "")')
            else:
                parts.append(f"(default: {default})")
        else:
            parts.append("(optional)")
        
        # Description
        if description:
            parts.append(f"- {description}")
        
        lines.append(' '.join(parts))
    
    return lines


async def generate_documentation():
    """Generate compact KSI documentation."""
    
    async with EventClient(client_id="doc_generator") as client:
        # Single call to get everything
        print("Discovering all events...")
        discovery = await client.send_event("system:discover", {"detail": True})
        
        if not discovery:
            print("Failed to get discovery data")
            return
        
        events = discovery.get("events", {})
        total = discovery.get("total", 0)
        namespaces = discovery.get("namespaces", [])
        
        print(f"\nDiscovered {total} events across {len(namespaces)} namespaces")
        
        # Create compact version of events
        compact_events = {}
        for event_name, event_info in events.items():
            compact_event = {
                "module": event_info["module"],
                "handler": event_info["handler"],
                "summary": event_info.get("summary", "")
            }
            
            # Only include async if false (true is default)
            if not event_info.get("async", True):
                compact_event["async"] = False
            
            # Compact parameters
            if event_info.get("parameters"):
                compact_event["params"] = {
                    name: compact_parameter(param_info)
                    for name, param_info in event_info["parameters"].items()
                }
            
            # Only include triggers if non-empty
            if event_info.get("triggers"):
                compact_event["triggers"] = event_info["triggers"]
            
            compact_events[event_name] = compact_event
        
        # Generate markdown documentation
        lines = [
            "# KSI Event Documentation (Compact)",
            "",
            f"Generated: {datetime.now().isoformat()}",
            f"Total Events: {total} | Namespaces: {len(namespaces)}",
            "",
            "## Parameter Format",
            "",
            "Parameters are shown as: `[type, required, default, description]`",
            "- When type is 'Any', it may be omitted in display",
            "- When required is true, shown as '(required)'",
            "- When required is false with a default, shown as '(default: value)'",
            "- When required is false without default, shown as '(optional)'",
            "",
            "## Table of Contents",
            ""
        ]
        
        # Organize events by namespace
        by_namespace = defaultdict(list)
        for event_name, event_info in compact_events.items():
            namespace = event_name.split(':', 1)[0]
            by_namespace[namespace].append((event_name, event_info))
        
        # Sort namespaces and events
        for namespace in by_namespace:
            by_namespace[namespace].sort(key=lambda x: x[0])
        
        # TOC
        for namespace in sorted(by_namespace.keys()):
            count = len(by_namespace[namespace])
            lines.append(f"- [{namespace}](#{namespace}) ({count} events)")
        
        lines.extend(["", "---", ""])
        
        # Event details by namespace
        for namespace in sorted(by_namespace.keys()):
            lines.extend([
                f"## {namespace}",
                "",
                f"**{len(by_namespace[namespace])} events**",
                ""
            ])
            
            for event_name, event_info in by_namespace[namespace]:
                module = event_info['module']
                handler = event_info['handler']
                is_async = event_info.get('async', True)
                summary = event_info.get('summary', 'No description available')
                params = event_info.get('params', {})
                triggers = event_info.get('triggers', [])
                
                # Compact header
                lines.extend([
                    f"### {event_name}",
                    "",
                    summary,
                    f"*{module}.{handler}*" + (" [sync]" if not is_async else ""),
                    ""
                ])
                
                # Parameters
                if params:
                    lines.append("**Parameters**:")
                    param_lines = format_parameters_compact(params)
                    lines.extend(param_lines)
                    lines.append("")
                
                # Triggers (only if present)
                if triggers:
                    lines.append("**Triggers**: " + ", ".join(triggers))
                    lines.append("")
                
                lines.append("---")
                lines.append("")
        
        # Write markdown
        output_path = Path("ksi_events_compact.md")
        output_path.write_text('\n'.join(lines))
        print(f"\nDocumentation written to: {output_path}")
        
        # Create compact JSON version
        compact_json = {
            "generated": datetime.now().isoformat(),
            "total": total,
            "namespaces": namespaces,
            "events": compact_events,
            "_format": {
                "params": "[type, required, default, description]",
                "async": "omitted when true (default)",
                "triggers": "omitted when empty"
            }
        }
        
        json_path = Path("ksi_discovery_compact.json")
        json_path.write_text(json.dumps(compact_json, indent=2))
        print(f"Compact JSON written to: {json_path}")
        
        # Calculate savings
        original_size = len(json.dumps(events, indent=2))
        compact_size = len(json.dumps(compact_events, indent=2))
        savings = (original_size - compact_size) / original_size * 100
        
        print(f"\nSize reduction: {original_size:,} → {compact_size:,} bytes ({savings:.1f}% smaller)")


if __name__ == "__main__":
    asyncio.run(generate_documentation())