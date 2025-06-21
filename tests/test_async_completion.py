#!/usr/bin/env python3
"""Test async process completion notifications"""

import asyncio
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('test')

async def test_async_completion():
    """Test that PROCESS_COMPLETE notifications work"""
    
    # Connect to daemon
    reader, writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
    
    # Register as test agent
    writer.write(b"CONNECT_AGENT:test_agent\n")
    await writer.drain()
    response = await reader.readline()
    logger.info(f"Connect response: {response.decode().strip()}")
    
    # Subscribe to PROCESS_COMPLETE events
    sub_reader, sub_writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
    sub_writer.write(b"SUBSCRIBE:test_agent:PROCESS_COMPLETE\n")
    await sub_writer.drain()
    response = await sub_reader.readline()
    logger.info(f"Subscribe response: {response.decode().strip()}")
    sub_writer.close()
    await sub_writer.wait_closed()
    
    # Spawn async process
    cmd_reader, cmd_writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
    cmd_writer.write(b"SPAWN_ASYNC::sonnet:test_agent:Say hello\n")
    await cmd_writer.drain()
    response = await cmd_reader.readline()
    result = json.loads(response.decode().strip())
    process_id = result.get('process_id')
    logger.info(f"Spawn response: {result}")
    cmd_writer.close()
    await cmd_writer.wait_closed()
    
    # Wait for completion notification
    logger.info("Waiting for PROCESS_COMPLETE event...")
    try:
        data = await asyncio.wait_for(reader.readline(), timeout=60.0)
        if data:
            message = json.loads(data.decode().strip())
            logger.info(f"Received event: {json.dumps(message, indent=2)}")
            
            # Check if it's our process
            if message.get('process_id') == process_id:
                logger.info("SUCCESS: Received completion for our process!")
            else:
                logger.error(f"Received completion for different process: {message.get('process_id')} != {process_id}")
    except asyncio.TimeoutError:
        logger.error("TIMEOUT: No completion event received in 60 seconds")
    
    # Disconnect
    writer.write(b"DISCONNECT_AGENT:test_agent\n")
    await writer.drain()
    writer.close()
    await writer.wait_closed()

if __name__ == '__main__':
    asyncio.run(test_async_completion())