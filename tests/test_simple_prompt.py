#!/usr/bin/env python3
"""Test simple direct prompt without agent framework"""

import asyncio
import json

async def test_simple_spawn():
    """Test spawning Claude with a simple hello/goodbye prompt"""
    
    # Connect to daemon
    reader, writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
    
    # Simple direct prompt
    prompt = """You are participating in a hello/goodbye conversation pattern.

You are the RESPONDER. The other agent just said "Hello!" to you.

Your ONLY valid response is: "Hello! Nice to meet you!"

Do not analyze code. Do not explain anything. Just respond with exactly: "Hello! Nice to meet you!"
"""
    
    # Spawn with simple prompt
    command = f"SPAWN_ASYNC::sonnet:test_agent:{prompt}\n"
    writer.write(command.encode())
    await writer.drain()
    
    response = await reader.readline()
    result = json.loads(response.decode().strip())
    print(f"Spawn result: {result}")
    
    # Close
    writer.close()
    await writer.wait_closed()

if __name__ == '__main__':
    asyncio.run(test_simple_spawn())