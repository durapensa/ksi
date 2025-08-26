#!/usr/bin/env python3
"""
Generate KSI documentation - Ultra-Compact Version.

Maximum token efficiency while maintaining full information:
- Single-line event definitions where possible
- Compact parameter notation
- Minimal JSON structure
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any, List, Union

from ksi_client import EventClient


def param_notation(name: str, info: Dict[str, Any]) -> str:
    """Create ultra-compact parameter notation."""
    t = info.get('type', 'Any')
    req = info.get('required', False)
    default = info.get('default')
    desc = info.get('description', '')
    
    # Build notation
    notation = name
    
    # Add type if not Any
    if t != 'Any':
        notation += f":{t}"
    
    # Add requirement/default
    if req:
        notation += "*"  # Required marker
    elif default is not None:
        if default == "":
            notation += '=""'
        elif default == "default":
            notation += '="default"'
        else:
            notation += f"={json.dumps(default)}"
    else:
        notation += "?"  # Optional marker
    
    return notation, desc


async def generate_documentation():
    """Generate ultra-compact KSI documentation."""
    
    async with EventClient(client_id="doc_generator") as client:
        print("Discovering all events...")
        discovery = await client.send_event("system:discover", {"detail": True})
        
        if not discovery:
            print("Failed to get discovery data")
            return
        
        events = discovery.get("events", {})
        total = discovery.get("total", 0)
        namespaces = discovery.get("namespaces", [])
        
        print(f"\nDiscovered {total} events across {len(namespaces)} namespaces")
        
        # Generate ultra-compact markdown
        lines = [
            "# KSI Events Reference",
            "",
            f"{total} events | {len(namespaces)} namespaces | Generated: {datetime.now().strftime('%Y-%m-%d')}",
            "",
            "## Notation",
            "- `param*` = required",
            "- `param?` = optional", 
            "- `param=value` = default value",
            "- `param:type` = typed parameter",
            "",
        ]
        
        # Group by namespace
        by_namespace = defaultdict(list)
        for event_name, event_info in events.items():
            namespace = event_name.split(':', 1)[0]
            by_namespace[namespace].append((event_name, event_info))
        
        # Generate content
        for namespace in sorted(by_namespace.keys()):
            events_list = sorted(by_namespace[namespace], key=lambda x: x[0])
            lines.append(f"## {namespace} ({len(events_list)})")
            lines.append("")
            
            for event_name, info in events_list:
                # Extract key info
                summary = info.get('summary', '')
                params = info.get('parameters', {})
                module = info['module'].replace('ksi_daemon.', '')
                handler = info['handler']
                is_sync = not info.get('async', True)
                triggers = info.get('triggers', [])
                
                # Build compact line
                event_line = f"**{event_name}**"
                
                # Add sync marker if needed
                if is_sync:
                    event_line += " [sync]"
                
                # Add parameters inline if few
                if params and len(params) <= 3:
                    param_parts = []
                    for pname, pinfo in params.items():
                        notation, _ = param_notation(pname, pinfo)
                        param_parts.append(notation)
                    event_line += f" ({', '.join(param_parts)})"
                
                # Add summary
                event_line += f" - {summary}"
                lines.append(event_line)
                
                # If many parameters, list them
                if params and len(params) > 3:
                    for pname, pinfo in params.items():
                        notation, desc = param_notation(pname, pinfo)
                        if desc and desc != f"{pname} parameter":
                            lines.append(f"  - {notation}: {desc}")
                        else:
                            lines.append(f"  - {notation}")
                
                # Add triggers if any
                if triggers:
                    lines.append(f"  → {', '.join(triggers)}")
                
                # Add module reference (ultra-compact)
                lines.append(f"  `{module}.{handler}`")
                lines.append("")
        
        # Write markdown
        output_path = Path("ksi_events_ultra_compact.md")
        output_path.write_text('\n'.join(lines))
        print(f"\nDocumentation written to: {output_path}")
        
        # Create ultra-compact JSON
        # Use single-letter keys for common fields
        compact_events = {}
        for event_name, event_info in events.items():
            ce = {
                "m": event_info["module"].replace('ksi_daemon.', ''),  # module
                "h": event_info["handler"],  # handler
                "s": event_info.get("summary", "")  # summary
            }
            
            # Only include if different from default
            if not event_info.get("async", True):
                ce["y"] = 0  # sync=0, async=1 (default)
            
            # Ultra-compact parameters
            if event_info.get("parameters"):
                ce["p"] = []
                for pname, pinfo in event_info["parameters"].items():
                    # Pack as [name, type?, required?, default?, desc?]
                    p = [pname]
                    if pinfo.get('type') != 'Any':
                        p.append(pinfo['type'])
                    if pinfo.get('required'):
                        p.append(1)  # 1=required
                    elif pinfo.get('default') is not None:
                        p.extend([0, pinfo['default']])  # 0=optional with default
                    # Only add description if meaningful
                    desc = pinfo.get('description', '')
                    if desc and desc != f"{pname} parameter":
                        # Pad array if needed
                        while len(p) < 4:
                            p.append(None)
                        p.append(desc)
                    ce["p"].append(p)
            
            # Only include triggers if present
            if event_info.get("triggers"):
                ce["t"] = event_info["triggers"]
            
            compact_events[event_name] = ce
        
        compact_json = {
            "v": 1,  # version
            "generated": datetime.now().strftime('%Y-%m-%d'),
            "total": total,
            "namespaces": namespaces,
            "events": compact_events,
            "_legend": {
                "m": "module (without ksi_daemon prefix)",
                "h": "handler function",
                "s": "summary",
                "y": "sync flag (omitted=async)",
                "p": "parameters [[name, type?, required?, default?, desc?], ...]",
                "t": "triggers array"
            }
        }
        
        json_path = Path("ksi_discovery_ultra_compact.json")
        json_path.write_text(json.dumps(compact_json, separators=(',', ':')))  # No spaces
        print(f"Ultra-compact JSON written to: {json_path}")
        
        # Calculate savings
        original = len(json.dumps(discovery.get("events", {}), indent=2))
        compact = len(json.dumps(compact_events, separators=(',', ':')))
        print(f"\nJSON size: {original:,} → {compact:,} bytes ({(1-compact/original)*100:.1f}% smaller)")


if __name__ == "__main__":
    asyncio.run(generate_documentation())