#!/usr/bin/env python3
"""Test the composition-based multi-agent system"""

import asyncio
import json
import sys

async def test_get_commands():
    """Test GET_COMMANDS functionality"""
    print("Testing GET_COMMANDS...")
    try:
        reader, writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
        writer.write(b'GET_COMMANDS\n')
        await writer.drain()
        response = await reader.readline()
        writer.close()
        await writer.wait_closed()
        
        result = json.loads(response.decode())
        print(f"Found {result.get('total_commands', 0)} commands")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

async def test_prompt_composition():
    """Test prompt composer integration"""
    print("\nTesting prompt composition...")
    sys.path.insert(0, '.')
    from prompts.composer import PromptComposer
    
    composer = PromptComposer()
    
    # Test that compositions exist
    compositions = composer.list_compositions()
    print(f"Found {len(compositions)} compositions: {compositions}")
    
    # Test hello/goodbye composition
    if 'conversation_hello_goodbye' in compositions:
        print("✓ conversation_hello_goodbye composition found")
        
        # Test composition with mock context
        context = {
            'agent_id': 'test_agent',
            'agent_role': 'initiator',
            'daemon_commands': {'SPAWN': {'format': 'SPAWN:<prompt>'}},
            'user_prompt': 'Hello!',
            'conversation_history': ''
        }
        
        try:
            prompt = composer.compose('conversation_hello_goodbye', context)
            print("✓ Successfully composed prompt")
            print(f"Prompt length: {len(prompt)} characters")
            return True
        except Exception as e:
            print(f"✗ Failed to compose: {e}")
            return False
    else:
        print("✗ conversation_hello_goodbye composition not found")
        return False

async def main():
    """Run all tests"""
    print("=== Testing Composition-Based Multi-Agent System ===\n")
    
    # Test daemon commands
    commands_ok = await test_get_commands()
    
    # Test prompt composition
    composition_ok = await test_prompt_composition()
    
    print("\n=== Test Summary ===")
    print(f"GET_COMMANDS: {'✓ PASS' if commands_ok else '✗ FAIL'}")
    print(f"Prompt Composition: {'✓ PASS' if composition_ok else '✗ FAIL'}")
    
    if commands_ok and composition_ok:
        print("\nAll tests passed! System is ready for multi-agent conversations.")
    else:
        print("\nSome tests failed. Please check the implementation.")

if __name__ == '__main__':
    asyncio.run(main())