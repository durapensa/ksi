#!/usr/bin/env python3
"""
Simple Hello/Goodbye test for two Claude agents
Demonstrates clean message exchange with proper termination
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('hello_goodbye')


async def start_hello_goodbye_exchange():
    """Start a simple Hello/Goodbye exchange between two agents"""
    
    # Create special agent profiles for this test
    profiles = {
        'hello_agent': {
            'model': 'sonnet',
            'role': 'greeter',
            'system_prompt': (
                'You are participating in a simple greeting exchange. '
                'When someone says Hello to you, respond with "Hello! Nice to meet you!" '
                'When someone says Goodbye to you, respond with "Goodbye! It was nice talking to you!" and stop the conversation. '
                'Do not send any additional messages after saying Goodbye.'
            )
        },
        'goodbye_agent': {
            'model': 'sonnet', 
            'role': 'responder',
            'system_prompt': (
                'You are participating in a simple greeting exchange. '
                'You will start by saying "Hello!" to begin the conversation. '
                'After receiving a Hello response, wait for the other person to say something, then say "Goodbye!" '
                'Do not send any additional messages after saying Goodbye.'
            )
        }
    }
    
    # Save profiles
    profiles_dir = Path('agent_profiles')
    profiles_dir.mkdir(exist_ok=True)
    
    for name, config in profiles.items():
        with open(profiles_dir / f'{name}.json', 'w') as f:
            json.dump(config, f, indent=2)
    
    # Start daemon if needed
    await ensure_daemon_running()
    
    # Start the two agents
    import subprocess
    
    logger.info("Starting hello_agent...")
    hello_process = subprocess.Popen([
        'python3', 'claude_node.py', 
        '--id', 'hello_agent',
        '--profile', 'hello_agent'
    ])
    
    await asyncio.sleep(2)  # Let first agent connect
    
    logger.info("Starting goodbye_agent...")
    goodbye_process = subprocess.Popen([
        'python3', 'claude_node.py',
        '--id', 'goodbye_agent', 
        '--profile', 'goodbye_agent',
        '--start-conversation',
        '--with-agents', 'hello_agent',
        '--topic', 'Hello!'
    ])
    
    logger.info("Exchange started! Monitoring for completion...")
    
    # Monitor the processes
    try:
        while True:
            await asyncio.sleep(1)
            
            hello_running = hello_process.poll() is None
            goodbye_running = goodbye_process.poll() is None
            
            if not hello_running and not goodbye_running:
                logger.info("Both agents have completed the exchange")
                break
            elif not hello_running or not goodbye_running:
                logger.info("One agent has stopped, waiting for the other...")
                await asyncio.sleep(3)  # Give time for final messages
                break
                
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    
    # Clean up
    for process in [hello_process, goodbye_process]:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    
    # Clean up profiles
    for name in profiles.keys():
        profile_path = profiles_dir / f'{name}.json'
        if profile_path.exists():
            profile_path.unlink()
    
    logger.info("Hello/Goodbye exchange complete!")


async def ensure_daemon_running():
    """Ensure daemon is running"""
    try:
        reader, writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
        writer.write(b"HEALTH_CHECK\n")
        await writer.drain()
        response = await reader.readline()
        writer.close()
        await writer.wait_closed()
        
        if response.strip() == b"HEALTHY":
            logger.info("Daemon is running")
            return
            
    except (FileNotFoundError, ConnectionRefusedError):
        logger.info("Starting daemon...")
        import subprocess
        subprocess.Popen(['python3', 'daemon.py'])
        await asyncio.sleep(3)  # Wait for startup


if __name__ == '__main__':
    asyncio.run(start_hello_goodbye_exchange())