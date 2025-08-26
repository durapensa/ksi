#!/usr/bin/env python3
"""
Generate KSI documentation from system:discover output - Fixed Version.

This script:
- Batches API calls to avoid socket overload
- Adds delays between calls
- Organizes by system internals (modules, namespaces)
- Handles connection errors gracefully
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any, List

from ksi_client import EventClient


async def get_event_details_batch(client: EventClient, event_names: List[str], batch_size: int = 10) -> Dict[str, Any]:
    """Get detailed information for events in batches to avoid socket overload."""
    all_details = {}
    
    for i in range(0, len(event_names), batch_size):
        batch = event_names[i:i + batch_size]
        print(f"  Fetching batch {i//batch_size + 1}/{(len(event_names) + batch_size - 1)//batch_size} ({len(batch)} events)...")
        
        for event_name in batch:
            try:
                details = await client.send_event("system:help", {"event": event_name})
                if details:
                    all_details[event_name] = details
            except Exception as e:
                print(f"    Warning: Could not get details for {event_name}: {e}")
        
        # Add delay between batches to avoid socket overload
        if i + batch_size < len(event_names):
            await asyncio.sleep(0.5)  # 500ms delay between batches
    
    return all_details


async def generate_documentation():
    """Generate documentation focused on system internals."""
    
    async with EventClient(client_id="doc_generator") as client:
        # Get discovery data
        print("Discovering events...")
        discovery = await client.send_event("system:discover")
        
        # Get module information
        print("Getting module information...")
        try:
            module_info = await client.send_event("module:list", {})
        except Exception as e:
            print(f"  Warning: Could not get module list: {e}")
            module_info = {}
        
        # Build documentation sections
        sections = []
        
        # Header
        sections.append("# KSI System Reference")
        sections.append("")
        sections.append("Generated from system internals on " + datetime.now().isoformat())
        sections.append("")
        
        # System Overview
        sections.append("## System Overview")
        sections.append("")
        sections.append("### Architecture")
        sections.append("")
        if 'total_events' in discovery:
            sections.append(f"- **Total Events**: {discovery['total_events']}")
        if 'namespaces' in discovery:
            sections.append(f"- **Namespaces**: {len(discovery['namespaces'])}")
        if module_info and 'count' in module_info:
            sections.append(f"- **Modules**: {module_info['count']}")
        sections.append("")
        
        # Namespace hierarchy
        events_by_namespace = discovery.get('events', {})
        if events_by_namespace:
            sections.append("### Namespace Hierarchy")
            sections.append("")
            sections.append("```")
            for ns in sorted(events_by_namespace.keys()):
                event_count = len(set(e.get('event') for e in events_by_namespace[ns]))
                sections.append(f"{ns:20} {event_count:3} events")
            sections.append("```")
            sections.append("")
        
        # Module hierarchy
        if module_info and 'modules' in module_info:
            sections.append("### Module Hierarchy")
            sections.append("")
            sections.append("```")
            sections.append("ksi_daemon/")
            
            # Parse module paths to create tree structure
            module_tree = defaultdict(lambda: defaultdict(list))
            for mod in module_info['modules']:
                parts = mod['name'].split('.')
                if len(parts) >= 3 and parts[0] == 'ksi_daemon':
                    category = parts[1]
                    module = parts[2] if len(parts) > 2 else ''
                    module_tree[category][module].append(mod)
            
            for category in sorted(module_tree.keys()):
                sections.append(f"├── {category}/")
                for module in sorted(module_tree[category].keys()):
                    for mod in module_tree[category][module]:
                        sections.append(f"│   └── {module}.py ({mod['handlers']} handlers)")
            sections.append("```")
            sections.append("")
        
        # Event format
        sections.append("## Event Protocol")
        sections.append("")
        sections.append("### Request Format")
        sections.append("```json")
        sections.append('{"event": "namespace:action", "data": {parameters}}')
        sections.append("```")
        sections.append("")
        sections.append("### Response Format")
        sections.append("```json")
        sections.append('{')
        sections.append('  "event": "namespace:action",')
        sections.append('  "data": {response_data},')
        sections.append('  "correlation_id": "optional-trace-id",')
        sections.append('  "timestamp": 1234567.890')
        sections.append('}')
        sections.append("```")
        sections.append("")
        
        # Get detailed info for events - in controlled batches
        all_event_details = {}
        if events_by_namespace:
            # Collect unique events
            unique_events = set()
            for namespace, events in events_by_namespace.items():
                for event in events:
                    unique_events.add(event.get('event'))
            
            unique_events_list = sorted(list(unique_events))
            print(f"\nFetching detailed information for {len(unique_events_list)} events (in batches)...")
            
            # Fetch in batches with delays
            all_event_details = await get_event_details_batch(client, unique_events_list, batch_size=20)
            
            print(f"Successfully fetched details for {len(all_event_details)} events")
        
        # Event relationships and patterns
        sections.append("## System Internals")
        sections.append("")
        
        # Analyze event patterns
        sections.append("### Event Patterns")
        sections.append("")
        sections.append("Events follow consistent patterns within each namespace:")
        sections.append("")
        
        # Common patterns
        patterns = {
            "CRUD Operations": ["get", "set", "list", "delete", "update"],
            "Lifecycle": ["create", "start", "stop", "terminate", "restart"],
            "Async Operations": ["async", "status", "result", "cancel", "progress"],
            "Discovery": ["discover", "inspect", "list", "help", "capabilities"],
            "Coordination": ["lock", "unlock", "acquire", "release"],
        }
        
        for pattern_name, keywords in patterns.items():
            matching_events = []
            for event_name in all_event_details.keys():
                event_action = event_name.split(':')[-1] if ':' in event_name else ''
                if any(keyword in event_action for keyword in keywords):
                    matching_events.append(event_name)
            
            if matching_events:
                sections.append(f"**{pattern_name}**:")
                for event in sorted(matching_events)[:5]:  # Show first 5 examples
                    sections.append(f"- `{event}`")
                if len(matching_events) > 5:
                    sections.append(f"- ... and {len(matching_events) - 5} more")
                sections.append("")
        
        # Module coupling analysis
        sections.append("### Module Coupling")
        sections.append("")
        sections.append("Modules that handle events from multiple namespaces:")
        sections.append("")
        
        module_namespaces = defaultdict(set)
        for namespace, events in events_by_namespace.items():
            for event in events:
                module = event.get('module', 'unknown')
                module_namespaces[module].add(namespace)
        
        for module, namespaces in sorted(module_namespaces.items()):
            if len(namespaces) > 1:
                module_short = module.split('.')[-1]
                ns_list = ', '.join(sorted(namespaces))
                sections.append(f"- **{module_short}**: handles {ns_list}")
        sections.append("")
        
        # Core system events
        sections.append("### Core System Events")
        sections.append("")
        sections.append("Essential events for system operation:")
        sections.append("")
        
        core_events = ["system:health", "system:startup", "system:shutdown", "system:context", "system:discover"]
        for event_name in core_events:
            if event_name in all_event_details:
                event = all_event_details[event_name]
                sections.append(f"- **`{event_name}`** - {event.get('summary', 'Core system event')}")
        sections.append("")
        
        # Event Reference by category
        sections.append("## Event Reference")
        sections.append("")
        
        # Categorize namespaces
        namespace_categories = {
            "Core Infrastructure": ["system", "state", "async_state", "module", "api"],
            "Request Processing": ["correlation", "monitor", "transport"],
            "AI Services": ["completion", "conversation", "agent"],
            "Coordination": ["message", "message_bus", "orchestration"],
            "Composition": ["composition", "permission", "sandbox"],
            "Response Flow": ["injection"],
            "Storage": ["file", "config"],
        }
        
        for category, namespaces in namespace_categories.items():
            sections.append(f"### {category}")
            sections.append("")
            
            for namespace in namespaces:
                if namespace not in events_by_namespace:
                    continue
                    
                sections.append(f"#### {namespace.title().replace('_', ' ')} Namespace")
                sections.append("")
                
                # Get unique events with details
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
                    sections.append(f"##### `{event_name}`")
                    
                    # Module implementation
                    if 'module' in event:
                        module_path = event['module']
                        module_name = module_path.split('.')[-1]
                        handler = event.get('handler', 'unknown')
                        sections.append(f"*Implementation: `{module_name}.{handler}()`*")
                    
                    sections.append("")
                    
                    # Summary
                    if 'summary' in event and event['summary']:
                        sections.append(event['summary'])
                        sections.append("")
                    
                    # Parameters
                    params = event.get('parameters', {})
                    if params:
                        sections.append("**Parameters:**")
                        for param_name, param_info in params.items():
                            required = param_info.get('required', False)
                            param_type = param_info.get('type', 'any')
                            description = param_info.get('description', '')
                            default = param_info.get('default', '')
                            
                            req_marker = "required" if required else "optional"
                            type_str = f"`{param_type}`" if param_type != 'any' else 'any'
                            default_str = f" (default: `{default}`)" if default and not required else ""
                            
                            sections.append(f"- **{param_name}** ({type_str}, {req_marker}): {description}{default_str}")
                        sections.append("")
                    
                    # Example
                    examples = event.get('examples', [])
                    if examples and len(examples) > 0:
                        example = examples[0]
                        if isinstance(example, dict) and 'data' in example:
                            sections.append("**Example:**")
                            sections.append("```json")
                            sections.append(json.dumps({
                                "event": event_name,
                                "data": example['data']
                            }, indent=2))
                            sections.append("```")
                            sections.append("")
                    
                    sections.append("")
            sections.append("")
        
        # System patterns
        sections.append("## System Patterns")
        sections.append("")
        sections.append("### Request-Response Pattern")
        sections.append("Many operations follow an async request-response pattern:")
        sections.append("1. Send request event (e.g., `completion:async`)")
        sections.append("2. Receive immediate acknowledgment with `request_id`")
        sections.append("3. Operation runs asynchronously")
        sections.append("4. Result delivered via response event (e.g., `completion:result`)")
        sections.append("")
        
        sections.append("### Session Management")
        sections.append("Sessions provide conversation continuity:")
        sections.append("1. First request: omit `session_id`")
        sections.append("2. Response includes new `session_id`")
        sections.append("3. Subsequent requests: include previous `session_id`")
        sections.append("4. Each response provides a new `session_id` for the next turn")
        sections.append("")
        
        # Footer
        sections.append("---")
        sections.append(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        sections.append(f"Total documented events: {len(all_event_details)}")
        
        return "\n".join(sections)


async def main():
    """Main entry point."""
    print("Generating KSI system documentation...")
    print("This will take a few moments to avoid overloading the socket connection.")
    
    try:
        # Generate documentation
        docs = await generate_documentation()
        
        # Save to file
        output_path = Path("generated_ksi_system_docs.md")
        output_path.write_text(docs)
        
        print(f"\n✓ Documentation generated successfully!")
        print(f"  Output: {output_path}")
        print(f"  Size: {len(docs):,} characters")
        print(f"  Lines: {docs.count(chr(10)):,}")
        
    except Exception as e:
        print(f"✗ Error generating documentation: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())