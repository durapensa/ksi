#!/usr/bin/env python3
"""
Test script to verify unified SPAWN async implementation with agent_process.py
"""

import asyncio
import json
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('test_async')

async def test_spawn_async():
    """Test unified SPAWN async command directly"""
    try:
        # Connect to daemon
        reader, writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
        logger.info("Connected to daemon")
        
        # Test unified SPAWN async format
        command = "SPAWN:async:claude::sonnet:test_agent:Hello, what is 2+2?\n"
        writer.write(command.encode())
        await writer.drain()
        
        # Get response
        response = await reader.readline()
        result = json.loads(response.decode().strip())
        logger.info(f"SPAWN async response: {result}")
        
        if 'process_id' in result:
            logger.info(f"Process started with ID: {result['process_id']}")
            
            # Now connect as agent to receive completion notification
            writer.write(b"CONNECT_AGENT:test_agent\n")
            await writer.drain()
            
            response = await reader.readline()
            connect_result = json.loads(response.decode().strip())
            logger.info(f"CONNECT_AGENT response: {connect_result}")
            
            # Subscribe to PROCESS_COMPLETE events
            writer.write(b"SUBSCRIBE:test_agent:PROCESS_COMPLETE\n")
            await writer.drain()
            
            response = await reader.readline()
            sub_result = json.loads(response.decode().strip())
            logger.info(f"SUBSCRIBE response: {sub_result}")
            
            # Wait for process completion
            logger.info("Waiting for process completion...")
            while True:
                data = await reader.readline()
                if not data:
                    break
                    
                message = json.loads(data.decode().strip())
                logger.info(f"Received message: {message}")
                
                if message.get('type') == 'PROCESS_COMPLETE':
                    payload = message.get('payload', {})
                    logger.info(f"Process completed: {payload}")
                    break
        
        writer.close()
        await writer.wait_closed()
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)

async def test_multi_claude_async():
    """Test multiple Claudes conversing with async spawning"""
    logger.info("Starting multi-Claude async test...")
    
    # Start two claude nodes
    claude1 = await asyncio.create_subprocess_exec(
        sys.executable, 'claude_node.py', '--id', 'claude1_async', '--profile', 'default',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    claude2 = await asyncio.create_subprocess_exec(
        sys.executable, 'claude_node.py', '--id', 'claude2_async', '--profile', 'default',
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    # Give them time to connect
    await asyncio.sleep(2)
    
    # Start conversation between them
    logger.info("Starting conversation...")
    try:
        reader, writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
        
        # Send message from orchestrator to claude1
        message = {
            'to': 'claude1_async',
            'content': 'Hello Claude1! Can you explain async programming in simple terms?',
            'conversation_id': 'test_async_conv'
        }
        
        command = f"PUBLISH:orchestrator:DIRECT_MESSAGE:{json.dumps(message)}\n"
        writer.write(command.encode())
        await writer.drain()
        
        response = await reader.readline()
        logger.info(f"Message sent: {response}")
        
        writer.close()
        await writer.wait_closed()
        
    except Exception as e:
        logger.error(f"Failed to start conversation: {e}")
    
    # Let them converse for a bit
    await asyncio.sleep(30)
    
    # Terminate
    claude1.terminate()
    claude2.terminate()
    await claude1.wait()
    await claude2.wait()
    
    logger.info("Test completed")

async def main():
    """Run tests"""
    # Test direct SPAWN async
    logger.info("=== Testing unified SPAWN async directly ===")
    await test_spawn_async()
    
    # Test multi-Claude with async
    logger.info("\n=== Testing Multi-Claude with async ===")
    await test_multi_claude_async()

if __name__ == '__main__':
    asyncio.run(main())