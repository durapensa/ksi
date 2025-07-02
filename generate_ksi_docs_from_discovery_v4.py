#!/usr/bin/env python3
"""
Generate KSI documentation from system:discover - Simplified Version.

This script leverages the new unified discovery system that returns
complete information in a single call.
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any, List

from ksi_client import EventClient


def format_parameters(params: Dict[str, Any]) -> List[str]:
    """Format parameters for documentation."""
    if not params:
        return ["None"]
    
    lines = []
    for name, info in params.items():
        param_type = info.get('type', 'Any')
        required = info.get('required', False)
        default = info.get('default')
        description = info.get('description', '')
        
        # Build parameter line
        parts = [f"- {name}"]
        if param_type and param_type != 'Any':
            parts.append(f"({param_type})")
        if required:
            parts.append("[required]")
        elif default is not None:
            parts.append(f"[default: {default}]")
        
        # Add description on same line or next line
        if description:
            if len(' '.join(parts)) < 40:
                parts.append(f"- {description}")
            else:
                lines.append(' '.join(parts))
                lines.append(f"  {description}")
                continue
        
        lines.append(' '.join(parts))
    
    return lines


async def generate_documentation():
    """Generate comprehensive KSI documentation."""
    
    async with EventClient(client_id="doc_generator") as client:
        # Single call to get everything!
        print("Discovering all events...")
        discovery = await client.send_event("system:discover", {"detail": True})
        
        if not discovery:
            print("Failed to get discovery data")
            return
        
        events = discovery.get("events", {})
        total = discovery.get("total", 0)
        namespaces = discovery.get("namespaces", [])
        
        print(f"\nDiscovered {total} events across {len(namespaces)} namespaces")
        
        # Organize events by namespace
        by_namespace = defaultdict(list)
        for event_name, event_info in events.items():
            namespace = event_name.split(':', 1)[0]
            by_namespace[namespace].append((event_name, event_info))
        
        # Sort namespaces and events
        for namespace in by_namespace:
            by_namespace[namespace].sort(key=lambda x: x[0])
        
        # Generate markdown documentation
        lines = [
            "# KSI Event Documentation",
            "",
            f"Generated: {datetime.now().isoformat()}",
            "",
            f"Total Events: {total}",
            f"Namespaces: {len(namespaces)}",
            "",
            "## Table of Contents",
            ""
        ]
        
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
                module = event_info.get('module', 'unknown')
                handler = event_info.get('handler', 'unknown')
                is_async = event_info.get('async', True)
                summary = event_info.get('summary', 'No description available')
                parameters = event_info.get('parameters', {})
                triggers = event_info.get('triggers', [])
                
                lines.extend([
                    f"### {event_name}",
                    "",
                    f"**Summary**: {summary}",
                    "",
                    f"**Module**: `{module}`",
                    f"**Handler**: `{handler}` ({'async' if is_async else 'sync'})",
                    "",
                    "**Parameters**:",
                ])
                
                # Format parameters
                param_lines = format_parameters(parameters)
                lines.extend(param_lines)
                
                # Show triggers if any
                if triggers:
                    lines.extend([
                        "",
                        "**Triggers**:",
                    ])
                    for trigger in triggers:
                        lines.append(f"- {trigger}")
                
                lines.extend(["", "---", ""])
        
        # Write to file
        output_path = Path("generated_ksi_docs_v4.md")
        output_path.write_text('\n'.join(lines))
        print(f"\nDocumentation written to: {output_path}")
        
        # Also create a JSON version for programmatic use
        json_output = {
            "generated": datetime.now().isoformat(),
            "total_events": total,
            "namespaces": namespaces,
            "events": events
        }
        
        json_path = Path("generated_ksi_discovery.json")
        json_path.write_text(json.dumps(json_output, indent=2))
        print(f"JSON discovery data written to: {json_path}")


if __name__ == "__main__":
    asyncio.run(generate_documentation())