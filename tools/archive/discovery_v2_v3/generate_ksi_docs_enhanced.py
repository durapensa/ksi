#!/usr/bin/env python3
"""
Enhanced KSI documentation generator using the new discovery:usage patterns.
"""

import asyncio
import json
import socket
from typing import Dict, Any, List
from pathlib import Path


async def send_request(event: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Send request to daemon and get response."""
    request = json.dumps({"event": event, "data": data})
    
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect("var/run/daemon.sock")
        sock.sendall(request.encode() + b'\n')
        
        response = b''
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if b'\n' in response:
                break
                
        return json.loads(response.decode().strip())
    finally:
        sock.close()


async def generate_enhanced_documentation():
    """Generate comprehensive KSI documentation using enhanced discovery."""
    
    print("Fetching comprehensive discovery data...")
    
    # Get full discovery data with implementation analysis
    full_data = await send_request("discovery:usage", {"pattern": "full"})
    
    # Get event relationships
    relationships = await send_request("discovery:usage", {"pattern": "relationships"})
    
    # Get capability usage
    capabilities = await send_request("discovery:usage", {"pattern": "capabilities"})
    
    print(f"Found {full_data['data']['total_events']} events")
    
    # Generate markdown documentation
    lines = ["# KSI System Documentation", ""]
    lines.append("*Generated using enhanced discovery system with AST analysis*")
    lines.append("")
    
    # Add summary
    lines.append("## System Overview")
    lines.append("")
    lines.append(f"- **Total Events**: {full_data['data']['total_events']}")
    lines.append(f"- **Namespaces**: {len(full_data['data']['events'])}")
    lines.append(f"- **Capabilities**: {', '.join(capabilities['data']['capabilities'])}")
    lines.append("")
    
    # Add event relationships if any
    if relationships['data']['event_graph']:
        lines.append("## Event Relationships")
        lines.append("")
        lines.append("Events that trigger other events:")
        lines.append("")
        for event, triggers in relationships['data']['event_graph'].items():
            if triggers:
                lines.append(f"- **{event}** triggers: {', '.join(triggers)}")
        lines.append("")
    
    # Add events by namespace
    lines.append("## Events by Namespace")
    lines.append("")
    
    for namespace in sorted(full_data['data']['events'].keys()):
        events = full_data['data']['events'][namespace]
        if not events:
            continue
            
        lines.append(f"### {namespace.title()}")
        lines.append("")
        lines.append(f"*{len(events)} events*")
        lines.append("")
        
        for event in events:
            lines.append(f"#### `{event['event']}`")
            lines.append("")
            
            # Summary and description
            if event.get('summary'):
                lines.append(f"**Summary**: {event['summary']}")
                lines.append("")
            
            if event.get('description') and event['description'] != event.get('summary'):
                lines.append("**Description**:")
                lines.append("")
                for line in event['description'].strip().split('\n'):
                    lines.append(f"> {line}")
                lines.append("")
            
            # Parameters
            if event.get('parameters'):
                lines.append("**Parameters**:")
                lines.append("")
                for param_name, param_info in event['parameters'].items():
                    req = "required" if param_info.get('required', False) else "optional"
                    param_type = param_info.get('type', 'Any')
                    desc = param_info.get('description', '')
                    
                    line = f"- `{param_name}` ({param_type}, {req})"
                    if desc:
                        line += f": {desc}"
                    if 'default' in param_info and param_info['default'] is not None:
                        line += f" [default: {param_info['default']}]"
                    lines.append(line)
                lines.append("")
            
            # Implementation details
            if event.get('implementation'):
                impl = event['implementation']
                
                # Complexity
                if impl.get('complexity', 1) > 10:
                    lines.append(f"**Complexity**: High ({impl['complexity']})")
                    lines.append("")
                
                # Triggers
                if impl.get('triggers'):
                    lines.append("**Triggers**:")
                    for trigger in impl['triggers']:
                        lines.append(f"- {trigger['event']}")
                    lines.append("")
                
                # State mutations
                if impl.get('state_mutations'):
                    lines.append("**State Mutations**:")
                    for mutation in impl['state_mutations']:
                        lines.append(f"- {mutation['operation']} ({mutation['type']})")
                    lines.append("")
                
                # File operations
                if impl.get('file_operations'):
                    lines.append("**File Operations**:")
                    for op in impl['file_operations']:
                        lines.append(f"- {op['operation']} ({op['type']})")
                    lines.append("")
            
            # Performance characteristics
            if event.get('performance'):
                perf = event['performance']
                if perf.get('async_response'):
                    lines.append("**Async Response**: Yes")
                if perf.get('typical_duration_ms'):
                    lines.append(f"**Typical Duration**: {perf['typical_duration_ms']}ms")
                if perf.get('has_side_effects'):
                    lines.append("**Has Side Effects**: Yes")
                if perf.get('idempotent'):
                    lines.append("**Idempotent**: Yes")
                if any([perf.get(k) for k in ['async_response', 'typical_duration_ms', 'has_side_effects', 'idempotent']]):
                    lines.append("")
            
            # Examples
            if event.get('examples'):
                lines.append("**Examples**:")
                lines.append("")
                for i, example in enumerate(event['examples'], 1):
                    if example.get('description'):
                        lines.append(f"Example {i}: {example['description']}")
                    lines.append("```json")
                    lines.append(json.dumps({
                        "event": event['event'],
                        "data": example.get('data', {})
                    }, indent=2))
                    lines.append("```")
                    lines.append("")
            
            lines.append("---")
            lines.append("")
    
    # Write to file
    output_path = Path("generated_ksi_docs_enhanced.md")
    output_path.write_text('\n'.join(lines))
    print(f"Documentation written to {output_path}")
    
    # Also generate a summary
    summary_lines = ["# KSI System Summary", ""]
    summary_lines.append("## Namespace Event Counts")
    summary_lines.append("")
    for ns, count in capabilities['data']['namespace_event_counts'].items():
        summary_lines.append(f"- **{ns}**: {count} events")
    summary_lines.append("")
    
    summary_path = Path("generated_ksi_summary.md")
    summary_path.write_text('\n'.join(summary_lines))
    print(f"Summary written to {summary_path}")


async def main():
    """Main entry point."""
    await generate_enhanced_documentation()


if __name__ == "__main__":
    asyncio.run(main())