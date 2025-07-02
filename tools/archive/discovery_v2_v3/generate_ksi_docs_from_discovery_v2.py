#!/usr/bin/env python3
"""
Generate KSI documentation from system:discover output - Enhanced Version.

This script generates documentation with multiple organization methods:
- By namespace (current)
- By module (implementation)
- With module context and relationships
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


async def get_module_info(client: EventClient) -> Dict[str, Any]:
    """Get module organization information."""
    try:
        return await client.send_event("module:list", {})
    except Exception as e:
        print(f"  Warning: Could not get module list: {e}")
        return {}


async def get_api_schema(client: EventClient) -> Dict[str, Any]:
    """Get API schema information."""
    try:
        return await client.send_event("api:schema", {})
    except Exception as e:
        print(f"  Warning: Could not get API schema: {e}")
        return {}


def organize_events_by_module(events_by_namespace: Dict[str, List], all_event_details: Dict[str, Any]) -> Dict[str, List]:
    """Reorganize events by their implementation module."""
    events_by_module = defaultdict(list)
    
    for namespace, events in events_by_namespace.items():
        for event in events:
            event_name = event.get('event')
            module = event.get('module', 'unknown')
            
            # Merge with detailed info if available
            if event_name in all_event_details:
                event.update(all_event_details[event_name])
            
            events_by_module[module].append(event)
    
    return dict(events_by_module)


def get_module_category(module_path: str) -> str:
    """Determine the category of a module based on its path."""
    if '.core.' in module_path:
        return "Core Services"
    elif '.transport.' in module_path:
        return "Transport Layer"
    elif '.completion.' in module_path:
        return "Completion Services"
    elif '.agent.' in module_path:
        return "Agent Management"
    elif '.messaging.' in module_path or '.message_bus.' in module_path:
        return "Messaging System"
    elif '.composition.' in module_path:
        return "Composition Engine"
    elif '.conversation.' in module_path:
        return "Conversation Management"
    elif '.permissions.' in module_path or '.sandbox.' in module_path:
        return "Security & Permissions"
    elif '.orchestration.' in module_path:
        return "Orchestration"
    elif '.injection.' in module_path:
        return "Response Injection"
    elif '.file.' in module_path or '.config.' in module_path:
        return "File & Configuration"
    else:
        return "Other Services"


async def generate_documentation():
    """Generate enhanced documentation from system:discover and related endpoints."""
    
    async with EventClient(client_id="doc_generator") as client:
        # Get discovery data
        print("Discovering events...")
        discovery = await client.send_event("system:discover")
        
        # Get module information
        print("Getting module information...")
        module_info = await get_module_info(client)
        
        # Get API schema
        print("Getting API schema...")
        api_schema = await get_api_schema(client)
        
        # Build documentation sections
        sections = []
        
        # Header
        sections.append("# KSI System Interface - Complete Reference")
        sections.append("")
        sections.append("Generated from system:discover on " + datetime.now().isoformat())
        sections.append("")
        
        # Table of Contents
        sections.append("## Table of Contents")
        sections.append("")
        sections.append("1. [System Overview](#system-overview)")
        sections.append("2. [Module Architecture](#module-architecture)")
        sections.append("3. [Events by Namespace](#events-by-namespace)")
        sections.append("4. [Events by Module](#events-by-module)")
        sections.append("5. [Common Workflows](#common-workflows)")
        sections.append("6. [Best Practices](#best-practices)")
        sections.append("")
        
        # System Overview
        sections.append("## System Overview")
        sections.append("")
        if 'total_events' in discovery:
            sections.append(f"- **Total Events**: {discovery['total_events']}")
        if 'namespaces' in discovery:
            sections.append(f"- **Namespaces**: {len(discovery['namespaces'])} ({', '.join(sorted(discovery['namespaces']))})")
        if module_info and 'count' in module_info:
            sections.append(f"- **Modules**: {module_info['count']}")
        sections.append("")
        
        # Module Architecture
        if module_info and 'modules' in module_info:
            sections.append("## Module Architecture")
            sections.append("")
            sections.append("The KSI daemon is organized into the following modules:")
            sections.append("")
            
            # Group modules by category
            modules_by_category = defaultdict(list)
            for mod in module_info['modules']:
                category = get_module_category(mod['name'])
                modules_by_category[category].append(mod)
            
            for category in sorted(modules_by_category.keys()):
                sections.append(f"### {category}")
                sections.append("")
                for mod in sorted(modules_by_category[category], key=lambda x: x['name']):
                    module_name = mod['name'].split('.')[-1]
                    sections.append(f"- **{module_name}** (`{mod['name']}`) - {mod['handlers']} handlers")
                sections.append("")
        
        # Event format
        sections.append("## Event Format")
        sections.append("")
        sections.append("All events follow this JSON format:")
        sections.append("```json")
        sections.append('{"event": "namespace:action", "data": {parameters}}')
        sections.append("```")
        sections.append("")
        
        # Get detailed info for each event
        all_event_details = {}
        events_by_namespace = discovery.get('events', {})
        
        if events_by_namespace:
            # Collect unique events
            unique_events = set()
            for namespace, events in events_by_namespace.items():
                for event in events:
                    unique_events.add(event.get('event'))
            
            print(f"Fetching detailed information for {len(unique_events)} unique events...")
            
            # Fetch details for each unique event
            event_count = 0
            for event_name in sorted(unique_events):
                event_count += 1
                if event_count % 10 == 0:
                    print(f"  Progress: {event_count}/{len(unique_events)} events...")
                details = await get_event_details(client, event_name)
                if details:
                    all_event_details[event_name] = details
            
            # Section 1: Events by Namespace
            sections.append("## Events by Namespace")
            sections.append("")
            sections.append("Events organized by their functional namespace:")
            sections.append("")
            
            for namespace in sorted(events_by_namespace.keys()):
                events = events_by_namespace[namespace]
                sections.append(f"### {namespace.title().replace('_', ' ')} Namespace")
                sections.append("")
                
                # Get unique events in this namespace
                seen_events = set()
                unique_namespace_events = []
                for event in events:
                    event_name = event.get('event', 'unknown')
                    if event_name not in seen_events:
                        seen_events.add(event_name)
                        # Merge basic info with detailed info
                        if event_name in all_event_details:
                            detailed = all_event_details[event_name]
                            event = {**event, **detailed}
                        unique_namespace_events.append(event)
                
                # Add summary
                sections.append(f"*{len(unique_namespace_events)} events in this namespace*")
                sections.append("")
                
                # List events with module info
                for event in sorted(unique_namespace_events, key=lambda x: x.get('event', '')):
                    event_name = event.get('event', 'unknown')
                    module = event.get('module', 'unknown').split('.')[-1]
                    summary = event.get('summary', '')
                    
                    sections.append(f"- **`{event_name}`** (_{module}_) - {summary}")
                
                sections.append("")
            
            # Section 2: Events by Module
            sections.append("## Events by Module")
            sections.append("")
            sections.append("Events organized by their implementation module:")
            sections.append("")
            
            # Organize events by module
            events_by_module = organize_events_by_module(events_by_namespace, all_event_details)
            
            # Group modules by category
            modules_by_category = defaultdict(list)
            for module_path in events_by_module.keys():
                category = get_module_category(module_path)
                modules_by_category[category].append(module_path)
            
            for category in sorted(modules_by_category.keys()):
                sections.append(f"### {category}")
                sections.append("")
                
                for module_path in sorted(modules_by_category[category]):
                    module_events = events_by_module[module_path]
                    module_name = module_path.split('.')[-1]
                    
                    sections.append(f"#### {module_name} (`{module_path}`)")
                    sections.append("")
                    sections.append(f"*{len(module_events)} events*")
                    sections.append("")
                    
                    # Group events by namespace within module
                    events_by_ns_in_module = defaultdict(list)
                    for event in module_events:
                        ns = event.get('event', ':').split(':')[0]
                        events_by_ns_in_module[ns].append(event)
                    
                    for ns in sorted(events_by_ns_in_module.keys()):
                        ns_events = events_by_ns_in_module[ns]
                        sections.append(f"**{ns}** namespace:")
                        for event in sorted(ns_events, key=lambda x: x.get('event', '')):
                            event_name = event.get('event', 'unknown')
                            params = event.get('parameters', {})
                            param_list = [p for p, info in params.items() if info.get('required', False)]
                            param_str = f" - requires: {', '.join(param_list)}" if param_list else ""
                            sections.append(f"- `{event_name}`{param_str}")
                        sections.append("")
            
            # Detailed Event Reference
            sections.append("## Detailed Event Reference")
            sections.append("")
            sections.append("Complete documentation for each event:")
            sections.append("")
            
            # Process events by namespace for detailed reference
            for namespace in sorted(events_by_namespace.keys()):
                sections.append(f"### {namespace.title().replace('_', ' ')} Events")
                sections.append("")
                
                # Get unique events
                seen_events = set()
                namespace_events = []
                for event in events_by_namespace[namespace]:
                    event_name = event.get('event', 'unknown')
                    if event_name not in seen_events:
                        seen_events.add(event_name)
                        if event_name in all_event_details:
                            namespace_events.append(all_event_details[event_name])
                        else:
                            namespace_events.append(event)
                
                # Document each event
                for event in sorted(namespace_events, key=lambda x: x.get('event', '')):
                    event_name = event.get('event', 'unknown')
                    sections.append(f"#### `{event_name}`")
                    
                    # Add module info
                    if 'module' in event:
                        module_name = event['module'].split('.')[-1]
                        sections.append(f"*Module: {module_name} (`{event['module']}`)*")
                    
                    sections.append("")
                    
                    # Add summary
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
                    
                    # Example
                    examples = event.get('examples', [])
                    if examples:
                        sections.append("**Example:**")
                        sections.append("")
                        example = examples[0]
                        if isinstance(example, dict) and 'data' in example:
                            sections.append("```json")
                            sections.append(json.dumps({
                                "event": event_name,
                                "data": example['data']
                            }, indent=2))
                            sections.append("```")
                        sections.append("")
                    
                    sections.append("---")
                    sections.append("")
        
        # Common workflows
        sections.append("## Common Workflows")
        sections.append("")
        
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
        sections.append("3. **Module Inspection**: Use `module:list` and `module:inspect` to understand system organization")
        sections.append("4. **Error Handling**: Always check response status and handle errors appropriately")
        sections.append("5. **Async Operations**: Many operations are asynchronous and return immediately")
        sections.append("")
        
        # Footer
        sections.append("---")
        sections.append(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(sections)


async def main():
    """Main entry point."""
    print("Generating enhanced KSI documentation...")
    
    try:
        # Generate documentation
        docs = await generate_documentation()
        
        # Save to file
        output_path = Path("generated_ksi_docs_enhanced.md")
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