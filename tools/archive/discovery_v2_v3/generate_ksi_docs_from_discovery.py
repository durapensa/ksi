#!/usr/bin/env python3
"""
Generate KSI documentation from system:discover output.

This script is completely agnostic to the contents of system:discover and
generates documentation based purely on the structure and patterns found
in the discovery data.
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any, List

from ksi_client import EventClient


async def get_event_details(client: EventClient, event_name: str) -> Dict[str, Any]:
    """Get detailed information for a specific event using system:help."""
    try:
        return await client.send_event("system:help", {"event": event_name})
    except Exception as e:
        print(f"  Warning: Could not get details for {event_name}: {e}")
        return None


async def generate_documentation():
    """Generate documentation from system:discover and system:help."""
    
    async with EventClient(client_id="doc_generator") as client:
        # Get discovery data
        print("Discovering events...")
        discovery = await client.send_event("system:discover")
        
        # Build documentation sections
        sections = []
        
        # Header
        sections.append("# KSI System Interface")
        sections.append("")
        sections.append("Generated from system:discover on " + datetime.now().isoformat())
        sections.append("")
        
        # Overview from discovery metadata
        if 'overview' in discovery:
            sections.append("## Overview")
            sections.append("")
            sections.append(discovery['overview'])
            sections.append("")
        
        # System statistics
        if 'total_events' in discovery:
            sections.append("## System Statistics")
            sections.append("")
            sections.append(f"- Total Events: {discovery['total_events']}")
            if 'namespaces' in discovery:
                sections.append(f"- Namespaces: {len(discovery['namespaces'])}")
            sections.append("")
        
        # Quick start if present
        if 'quick_start' in discovery:
            sections.append("## Quick Start")
            sections.append("")
            sections.append(discovery['quick_start'])
            sections.append("")
        
        # Event format
        sections.append("## Event Format")
        sections.append("")
        sections.append("All events follow this JSON format:")
        sections.append("```json")
        sections.append('{"event": "namespace:action", "data": {parameters}}')
        sections.append("```")
        sections.append("")
        
        # Namespaces and Events
        if 'events' in discovery:
            sections.append("## Available Events")
            sections.append("")
            
            # Get detailed info for each event
            all_event_details = {}
            events_by_namespace = discovery['events']
            total_events = sum(len(events) for events in events_by_namespace.values())
            
            print(f"Fetching detailed information for {total_events} events...")
            
            # Collect all unique events (some may appear multiple times)
            unique_events = set()
            for namespace, events in events_by_namespace.items():
                for event in events:
                    unique_events.add(event.get('event'))
            
            # Fetch details for each unique event
            event_count = 0
            for event_name in sorted(unique_events):
                event_count += 1
                print(f"  [{event_count}/{len(unique_events)}] Getting details for {event_name}...")
                details = await get_event_details(client, event_name)
                if details:
                    all_event_details[event_name] = details
            
            # Process each namespace in the order provided
            for namespace, events in events_by_namespace.items():
                sections.append(f"### {namespace.title().replace('_', ' ')} Namespace")
                sections.append("")
                
                # Add namespace description if available
                namespace_info = discovery.get('namespace_info', {}).get(namespace, {})
                if 'description' in namespace_info:
                    sections.append(namespace_info['description'])
                    sections.append("")
                
                # Get unique events in this namespace
                seen_events = set()
                namespace_events = []
                for event in events:
                    event_name = event.get('event', 'unknown')
                    if event_name not in seen_events:
                        seen_events.add(event_name)
                        # Merge basic info with detailed info
                        if event_name in all_event_details:
                            detailed = all_event_details[event_name]
                            event['parameters'] = detailed.get('parameters', {})
                            event['examples'] = detailed.get('examples', [])
                            if detailed.get('summary'):
                                event['summary'] = detailed['summary']
                        namespace_events.append(event)
                
                # Process unique events in the namespace
                for event in namespace_events:
                    event_name = event.get('event', 'unknown')
                    sections.append(f"#### `{event_name}`")
                    sections.append("")
                    
                    # Add summary if available
                    if 'summary' in event and event['summary']:
                        sections.append(event['summary'])
                        sections.append("")
                    
                    # Parameters
                    params = event.get('parameters', {})
                    if params:
                        sections.append("**Parameters:**")
                        sections.append("")
                        for param_name, param_info in params.items():
                            required = param_info.get('required', False)
                            param_type = param_info.get('type', 'any')
                            description = param_info.get('description', '')
                            default = param_info.get('default', '')
                            
                            req_marker = " *(required)*" if required else " *(optional)*"
                            default_text = f" - default: `{default}`" if default and not required else ""
                            sections.append(f"- `{param_name}` ({param_type}){req_marker}: {description}{default_text}")
                        sections.append("")
                    else:
                        sections.append("**Parameters:** None")
                        sections.append("")
                    
                    # Examples if available
                    examples = event.get('examples', [])
                    if examples:
                        sections.append("**Example:**")
                        sections.append("")
                        # Show first example
                        example = examples[0]
                        if isinstance(example, dict) and 'data' in example:
                            sections.append("```json")
                            sections.append(json.dumps({
                                "event": event_name,
                                "data": example['data']
                            }, indent=2))
                            sections.append("```")
                        elif isinstance(example, dict):
                            sections.append("```json")
                            sections.append(json.dumps({
                                "event": event_name,
                                "data": example
                            }, indent=2))
                            sections.append("```")
                        else:
                            sections.append(f"{example}")
                        sections.append("")
                    
                    sections.append("---")
                    sections.append("")
        
        # Common patterns and workflows
        sections.append("## Common Workflows")
        sections.append("")
        
        # Check if we have completion events
        if 'completion:async' in all_event_details:
            sections.append("### Multi-turn Conversation")
            sections.append("```bash")
            sections.append("# First message - no session_id")
            sections.append('{"event": "completion:async", "data": {"prompt": "Hello", "model": "claude-cli/sonnet"}}')
            sections.append("# Returns: request_id and creates file with NEW session_id")
            sections.append("")
            sections.append("# Continue conversation using previous session_id")
            sections.append('{"event": "completion:async", "data": {')
            sections.append('  "prompt": "What did we just discuss?",')
            sections.append('  "model": "claude-cli/sonnet",')
            sections.append('  "session_id": "session-id-from-previous-response"')
            sections.append('}}')
            sections.append("```")
            sections.append("")
        
        # Best practices
        sections.append("## Best Practices")
        sections.append("")
        sections.append("1. **Event Discovery**: Use `system:discover` to list all available events")
        sections.append("2. **Event Help**: Use `system:help` to get detailed parameter information")
        sections.append("3. **Error Handling**: Check response status and handle errors appropriately")
        sections.append("4. **Async Operations**: Many operations are asynchronous and return immediately")
        sections.append("")
        
        # Footer
        sections.append("---")
        sections.append(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(sections)


async def main():
    """Main entry point."""
    print("Generating KSI documentation from system:discover...")
    
    try:
        # Generate documentation
        docs = await generate_documentation()
        
        # Save to file
        output_path = Path("generated_ksi_docs.md")
        output_path.write_text(docs)
        
        print(f"\n✓ Documentation generated successfully!")
        print(f"  Output: {output_path}")
        print(f"  Size: {len(docs):,} characters")
        print(f"  Lines: {docs.count(chr(10)):,}")
        
        # Show preview
        lines = docs.split('\n')[:50]
        print("\nPreview:")
        print("-" * 60)
        for line in lines:
            print(line)
        print("...")
        print("-" * 60)
        
    except Exception as e:
        print(f"✗ Error generating documentation: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())