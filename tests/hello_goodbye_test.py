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


async def spawn_agent_via_daemon(profile_name: str, task: str, context: str) -> bool:
    """Spawn an agent using daemon SPAWN_AGENT command"""
    try:
        reader, writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
        command = f"SPAWN_AGENT:{profile_name}:{task}:{context}:{profile_name}\n"
        writer.write(command.encode())
        await writer.drain()
        
        response = await reader.readline()
        writer.close()
        await writer.wait_closed()
        
        result = json.loads(response.decode())
        if result.get('status') == 'spawned':
            logger.info(f"Spawned {profile_name} with process_id {result.get('process_id')}")
            return True
        else:
            logger.error(f"Failed to spawn {profile_name}: {result}")
            return False
            
    except Exception as e:
        logger.error(f"Error spawning agent: {e}")
        return False


async def send_initial_message(from_agent: str, to_agent: str, message: str):
    """Send initial message between agents"""
    try:
        reader, writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
        
        # Publish a DIRECT_MESSAGE event
        payload = {
            'to': to_agent,
            'content': message,
            'conversation_id': 'hello_goodbye_test'
        }
        command = f"PUBLISH:{from_agent}:DIRECT_MESSAGE:{json.dumps(payload)}\n"
        writer.write(command.encode())
        await writer.drain()
        
        response = await reader.readline()
        writer.close()
        await writer.wait_closed()
        
        logger.info(f"Sent initial message from {from_agent} to {to_agent}")
        
    except Exception as e:
        logger.error(f"Error sending initial message: {e}")


async def check_agents_connected() -> dict:
    """Check which agents are connected"""
    try:
        reader, writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
        writer.write(b"GET_AGENTS\n")
        await writer.drain()
        
        response = await reader.readline()
        writer.close()
        await writer.wait_closed()
        
        result = json.loads(response.decode())
        return result.get('agents', {})
        
    except Exception as e:
        logger.error(f"Error checking agents: {e}")
        return {}


async def start_hello_goodbye_exchange():
    """Start a simple Hello/Goodbye exchange between two agents"""
    
    # Create special agent profiles for this test
    profiles = {
        'hello_agent': {
            'model': 'sonnet',
            'role': 'responder',
            'composition': 'simple_hello_goodbye'
        },
        'goodbye_agent': {
            'model': 'sonnet', 
            'role': 'initiator',
            'composition': 'simple_hello_goodbye'
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
    
    # Start the two agents using daemon commands
    logger.info("Starting hello_agent...")
    hello_result = await spawn_agent_via_daemon('hello_agent', 'Respond to greetings', '')
    if not hello_result:
        logger.error("Failed to spawn hello_agent")
        return
    
    await asyncio.sleep(2)  # Let first agent connect
    
    logger.info("Starting goodbye_agent...")
    goodbye_result = await spawn_agent_via_daemon('goodbye_agent', 'Start a greeting', 'Say hello to hello_agent')
    if not goodbye_result:
        logger.error("Failed to spawn goodbye_agent")
        return
    
    # Give agents time to connect
    await asyncio.sleep(2)
    
    # Start the conversation by sending initial message
    await send_initial_message('goodbye_agent', 'hello_agent', 'Hello!')
    
    logger.info("Exchange started! Monitoring for completion...")
    
    # Monitor the agents
    max_wait = 30  # Maximum seconds to wait
    start_time = asyncio.get_event_loop().time()
    
    try:
        while True:
            await asyncio.sleep(2)
            
            # Check if agents are still connected
            agents = await check_agents_connected()
            hello_connected = 'hello_agent' in agents
            goodbye_connected = 'goodbye_agent' in agents
            
            elapsed = asyncio.get_event_loop().time() - start_time
            
            if not hello_connected and not goodbye_connected:
                logger.info("Both agents have disconnected - exchange complete!")
                break
            elif elapsed > max_wait:
                logger.warning(f"Timeout after {max_wait} seconds")
                break
            else:
                logger.info(f"Agents connected - hello: {hello_connected}, goodbye: {goodbye_connected}")
                
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    
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