#!/usr/bin/env python3
"""
Test the new EventClient with discovery and prompt generation.

This script:
1. Tests basic EventClient connectivity
2. Tests discovery functionality
3. Tests dynamic namespace access
4. Generates a Claude-friendly prompt
5. Tests some actual event calls
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime

from ksi_client import EventClient
from ksi_client.prompt_generator import KSIPromptGenerator


async def test_event_client():
    """Comprehensive test of EventClient functionality."""
    
    print("=" * 80)
    print("KSI EventClient Discovery Test")
    print("=" * 80)
    
    async with EventClient(client_id="test_discovery") as client:
        # Test 1: Basic connectivity
        print("\n1. Testing basic connectivity...")
        try:
            health = await client.send_event("system:health")
            print(f"✓ Connected! Status: {health.get('status')}")
            print(f"  Daemon version: {health.get('daemon_version', 'unknown')}")
            print(f"  Python version: {health.get('python_version', 'unknown')}")
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return
        
        # Test 2: Discovery
        print("\n2. Testing discovery system...")
        if not client._discovered:
            print("✗ Auto-discovery failed, trying manual discovery...")
            try:
                await client.discover()
                print("✓ Manual discovery succeeded!")
            except Exception as e:
                print(f"✗ Discovery failed: {e}")
                return
        
        print(f"✓ Discovered {sum(len(events) for events in client._event_cache.values())} events")
        print(f"  Namespaces: {', '.join(client.get_namespaces())}")
        
        # Test 3: Dynamic namespace access
        print("\n3. Testing dynamic namespace access...")
        try:
            # Test if we can access namespaces dynamically
            assert hasattr(client, 'system'), "No system namespace"
            assert hasattr(client, 'completion'), "No completion namespace"
            print("✓ Dynamic namespaces working!")
            
            # Show what's available in completion namespace
            completion_events = client.get_events_in_namespace("completion")
            print(f"  Completion events: {[e['event'] for e in completion_events]}")
        except Exception as e:
            print(f"✗ Dynamic namespace access failed: {e}")
        
        # Test 4: Generate Claude prompt
        print("\n4. Generating Claude-friendly prompt...")
        try:
            generator = KSIPromptGenerator.from_client(client)
            prompt = generator.generate_prompt(
                include_examples=True,
                include_workflows=True,
                focus_namespaces=["system", "completion", "conversation", "state"]
            )
            
            # Save prompt
            prompt_path = Path("generated_ksi_prompt.txt")
            prompt_path.write_text(prompt)
            
            print(f"✓ Generated {len(prompt)} character prompt")
            print(f"  Saved to: {prompt_path}")
            
            # Show first few lines
            lines = prompt.split('\n')[:10]
            print("  Preview:")
            for line in lines:
                print(f"    {line}")
            print("    ...")
            
        except Exception as e:
            print(f"✗ Prompt generation failed: {e}")
        
        # Test 5: Test actual event calls
        print("\n5. Testing event calls...")
        
        # Test 5a: system:help
        try:
            help_response = await client.system.help(event="completion:async")
            print(f"✓ system:help worked!")
            print(f"  Event: {help_response.get('event')}")
            print(f"  Summary: {help_response.get('summary', 'N/A')}")
            params = help_response.get('parameters', {})
            print(f"  Parameters: {list(params.keys())}")
        except Exception as e:
            print(f"✗ system:help failed: {e}")
        
        # Test 5b: state operations
        try:
            test_key = f"test_key_{datetime.now().isoformat()}"
            test_value = {"test": "data", "timestamp": datetime.now().isoformat()}
            
            # Set state
            set_result = await client.state.set(
                key=test_key,
                value=test_value,
                namespace="test"
            )
            print(f"✓ state:set worked! Status: {set_result.get('status')}")
            
            # Get state
            get_result = await client.state.get(
                key=test_key,
                namespace="test"
            )
            if get_result.get('found'):
                print(f"✓ state:get worked! Retrieved value: {get_result.get('value')}")
            else:
                print(f"✗ state:get failed: key not found")
            
            # Delete state
            delete_result = await client.state.delete(
                key=test_key,
                namespace="test"
            )
            print(f"✓ state:delete worked! Status: {delete_result.get('status')}")
            
        except Exception as e:
            print(f"✗ state operations failed: {e}")
        
        # Test 5c: Permission profiles (if available)
        if client.has_event("permission:list_profiles"):
            try:
                profiles = await client.permission.list_profiles()
                print(f"✓ permission:list_profiles worked!")
                print(f"  Available profiles: {list(profiles.get('profiles', {}).keys())}")
            except Exception as e:
                print(f"✗ permission:list_profiles failed: {e}")
        else:
            print("ℹ permission:list_profiles not available")
        
        # Test 6: Completion (skip in non-interactive mode)
        print("\n6. Completion test")
        print("ℹ  Skipping interactive completion test")
        print("  To test completion, run with environment variable: TEST_COMPLETION=1")
        
        import os
        if os.environ.get('TEST_COMPLETION') == '1':
            try:
                # Use the completion namespace with async_
                result = await client.completion.async_(
                    prompt="Say 'Hello from KSI EventClient test!' and nothing else.",
                    model="claude-cli/sonnet",
                    request_id=f"test_{datetime.now().timestamp()}"
                )
                
                print(f"✓ completion:async worked!")
                print(f"  Request ID: {result.get('request_id')}")
                print(f"  Status: {result.get('status')}")
                
                # For async completion, we'd need to wait for completion:result event
                # This is just testing that the event was accepted
                
            except Exception as e:
                print(f"✗ completion:async failed: {e}")
    
    print("\n" + "=" * 80)
    print("Test completed!")
    print("=" * 80)


def analyze_discovery_format():
    """Analyze the raw discovery format for prompt generation insights."""
    print("\n" + "=" * 80)
    print("Analyzing Discovery Format")
    print("=" * 80)
    
    async def _analyze():
        async with EventClient(client_id="analyzer") as client:
            # Get raw discovery data
            raw_discovery = await client.send_event("system:discover")
            
            print("\nRaw discovery structure:")
            print(f"- Total events: {raw_discovery.get('total_events')}")
            print(f"- Namespaces: {len(raw_discovery.get('namespaces', []))}")
            
            # Analyze parameter patterns
            param_types = set()
            required_counts = {"required": 0, "optional": 0}
            events_with_examples = 0
            
            for namespace, events in raw_discovery.get('events', {}).items():
                for event in events:
                    if event.get('examples'):
                        events_with_examples += 1
                    
                    for param_name, param_info in event.get('parameters', {}).items():
                        if param_info.get('type'):
                            param_types.add(param_info['type'])
                        
                        if param_info.get('required'):
                            required_counts['required'] += 1
                        else:
                            required_counts['optional'] += 1
            
            print(f"\nParameter analysis:")
            print(f"- Types found: {param_types}")
            print(f"- Required params: {required_counts['required']}")
            print(f"- Optional params: {required_counts['optional']}")
            print(f"- Events with examples: {events_with_examples}")
            
            # Find events missing from discovery
            print("\nChecking for missing key events...")
            critical_events = [
                "completion:async",
                "completion:result", 
                "conversation:list",
                "conversation:get",
                "state:set",
                "state:get"
            ]
            
            discovered_events = set()
            for events in raw_discovery.get('events', {}).values():
                for event in events:
                    discovered_events.add(event.get('event'))
            
            missing = [e for e in critical_events if e not in discovered_events]
            if missing:
                print(f"⚠️  Missing critical events: {missing}")
            else:
                print("✓ All critical events discovered!")
    
    asyncio.run(_analyze())


if __name__ == "__main__":
    print("Testing KSI EventClient with discovery system...\n")
    
    # Run main tests
    asyncio.run(test_event_client())
    
    # Analyze discovery format
    analyze_discovery_format()
    
    print("\n✨ All tests completed! Check generated_ksi_prompt.txt for the Claude-friendly prompt.")