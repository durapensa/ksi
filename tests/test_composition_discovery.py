#!/usr/bin/env python3
"""Test composition discovery commands"""

import asyncio
import json
import sys

async def send_command(cmd):
    """Send a command and get response"""
    reader, writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
    
    writer.write((json.dumps(cmd) + '\n').encode())
    await writer.drain()
    
    response = await reader.readline()
    writer.close()
    await writer.wait_closed()
    
    if not response:
        return None
    return json.loads(response.decode())

async def test_composition_discovery():
    """Test the new composition discovery commands"""
    print("=== Testing Composition Discovery Commands ===\n")
    
    # Test 1: GET_COMPOSITIONS
    print("1. Testing GET_COMPOSITIONS...")
    cmd = {
        "command": "GET_COMPOSITIONS",
        "version": "2.0",
        "parameters": {
            "include_metadata": True
        }
    }
    result = await send_command(cmd)
    
    if result.get('status') == 'success':
        compositions = result['result']['compositions']
        print(f"✓ Found {len(compositions)} compositions:")
        for name, info in list(compositions.items())[:5]:  # Show first 5
            print(f"  - {name}: {info.get('description', 'No description')}")
    else:
        print(f"✗ Failed: {result}")
    
    # Test 2: GET_COMPOSITION
    print("\n2. Testing GET_COMPOSITION...")
    cmd = {
        "command": "GET_COMPOSITION",
        "version": "2.0",
        "parameters": {
            "name": "claude_agent_default"
        }
    }
    result = await send_command(cmd)
    
    if result.get('status') == 'success':
        comp = result['result']['composition']
        print(f"✓ Got composition '{comp['name']}':")
        print(f"  Version: {comp['version']}")
        print(f"  Author: {comp['author']}")
        print(f"  Components: {len(comp['components'])}")
        print(f"  Required context: {list(comp['required_context'].keys())}")
    else:
        print(f"✗ Failed: {result}")
    
    # Test 3: LIST_COMPONENTS
    print("\n3. Testing LIST_COMPONENTS...")
    cmd = {
        "command": "LIST_COMPONENTS",
        "version": "2.0",
        "parameters": {}
    }
    result = await send_command(cmd)
    
    if result.get('status') == 'success':
        components = result['result']['components']
        by_dir = result['result']['by_directory']
        print(f"✓ Found {len(components)} components in {len(by_dir)} directories:")
        for dir_name, comps in list(by_dir.items())[:3]:  # Show first 3 dirs
            print(f"  {dir_name or 'root'}/: {len(comps)} components")
    else:
        print(f"✗ Failed: {result}")
    
    # Test 4: VALIDATE_COMPOSITION
    print("\n4. Testing VALIDATE_COMPOSITION...")
    cmd = {
        "command": "VALIDATE_COMPOSITION",
        "version": "2.0",
        "parameters": {
            "name": "claude_agent_default",
            "context": {
                "agent_id": "test_agent",
                "daemon_commands": {},
                "enable_tools": True
            }
        }
    }
    result = await send_command(cmd)
    
    if result.get('status') == 'success':
        validation = result['result']
        if validation['valid']:
            print(f"✓ Composition is valid (prompt length: {validation.get('prompt_length', 'unknown')})")
        else:
            print(f"✗ Composition invalid: {validation}")
    else:
        print(f"✗ Failed: {result}")
    
    # Test 5: COMPOSE_PROMPT
    print("\n5. Testing COMPOSE_PROMPT...")
    cmd = {
        "command": "COMPOSE_PROMPT",
        "version": "2.0",
        "parameters": {
            "composition": "claude_agent_default",
            "context": {
                "agent_id": "test_agent",
                "daemon_commands": {"SPAWN": {"description": "Spawn a process"}},
                "enable_tools": True,
                "user_prompt": "Hello, world!",
                "conversation_history": ""
            }
        }
    }
    result = await send_command(cmd)
    
    if result.get('status') == 'success':
        prompt_info = result['result']
        print(f"✓ Composed prompt:")
        print(f"  Length: {prompt_info['length']} characters")
        print(f"  First 100 chars: {prompt_info['prompt'][:100]}...")
    else:
        print(f"✗ Failed: {result}")
    
    print("\n=== All tests completed ===")

if __name__ == '__main__':
    asyncio.run(test_composition_discovery())