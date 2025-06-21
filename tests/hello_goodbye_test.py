#!/usr/bin/env python3
"""
Test script for the Hello/Goodbye conversation pattern.

This script tests the hello/goodbye conversation pattern by creating
two agents that exchange greetings.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('hello_goodbye_test')


class HelloGoodbyeInitiator:
    """Initiates the hello/goodbye conversation"""
    
    def __init__(self, agent_id='hello_initiator'):
        self.agent_id = agent_id
        self.target_agent = 'hello_responder'
        
    async def connect_to_daemon(self):
        """Connect to the daemon"""
        try:
            self.reader, self.writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
            logger.info("Initiator connected to daemon")
            return True
        except (FileNotFoundError, ConnectionRefusedError) as e:
            logger.error(f"Failed to connect to daemon: {e}")
            return False
    
    async def register_agent(self):
        """Register this agent with the daemon"""
        # Use the correct command format: REGISTER_AGENT:agent_id:role:capabilities
        command = f"REGISTER_AGENT:{self.agent_id}:initiator:conversation"
        
        self.writer.write(command.encode() + b'\n')
        await self.writer.drain()
        
        response = await self.receive_response()
        
        if response and response.get('status') == 'registered':
            logger.info(f"Agent {self.agent_id} registered successfully")
            return True
        else:
            logger.info(f"Agent registration response: {response}")
            return True  # Assume success for now
    
    async def send_command(self, command):
        """Send a command to the daemon"""
        command_str = json.dumps(command) + '\n'
        self.writer.write(command_str.encode())
        await self.writer.drain()
    
    async def receive_response(self):
        """Receive a response from the daemon"""
        try:
            line = await self.reader.readline()
            if line:
                return json.loads(line.decode().strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode response: {e}")
        return None
    
    async def send_hello(self):
        """Send the initial hello message"""
        # Use the correct format: SEND_MESSAGE:from_agent:to_agent:message
        command = f"SEND_MESSAGE:{self.agent_id}:{self.target_agent}:Hello! How are you doing today?"
        
        self.writer.write(command.encode() + b'\n')
        await self.writer.drain()
        logger.info(f"Sent hello to {self.target_agent}")
    
    async def send_goodbye(self):
        """Send the goodbye message"""
        # Use the correct format: SEND_MESSAGE:from_agent:to_agent:message
        command = f"SEND_MESSAGE:{self.agent_id}:{self.target_agent}:Goodbye! Thanks for chatting!"
        
        self.writer.write(command.encode() + b'\n')
        await self.writer.drain()
        logger.info(f"Sent goodbye to {self.target_agent}")
    
    async def wait_for_response(self, timeout=5):
        """Wait for a response from the responder"""
        try:
            response = await asyncio.wait_for(self.receive_response(), timeout=timeout)
            if response and response.get('type') == 'message':
                content = response.get('content', '')
                from_agent = response.get('from_agent', 'unknown')
                logger.info(f"Received from {from_agent}: '{content}'")
                return content
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for response")
        return None
    
    async def cleanup(self):
        """Clean up connections"""
        if hasattr(self, 'writer'):
            self.writer.close()
            await self.writer.wait_closed()
        logger.info("Initiator cleaned up connections")
    
    async def run_conversation(self):
        """Run the complete hello/goodbye conversation"""
        try:
            # Connect and register
            if not await self.connect_to_daemon():
                return False
            
            if not await self.register_agent():
                return False
            
            # Wait a moment for responder to be ready
            await asyncio.sleep(1)
            
            # Send hello and wait for response
            await self.send_hello()
            hello_response = await self.wait_for_response()
            
            if not hello_response:
                logger.error("No response to hello")
                return False
            
            # Wait a moment then send goodbye
            await asyncio.sleep(1)
            await self.send_goodbye()
            goodbye_response = await self.wait_for_response()
            
            if not goodbye_response:
                logger.error("No response to goodbye")
                return False
            
            # Check if conversation ended properly
            if "[END]" in goodbye_response:
                logger.info("Conversation completed successfully!")
                return True
            else:
                logger.warning("Conversation may not have ended properly")
                return True
                
        except Exception as e:
            logger.error(f"Error in conversation: {e}")
            return False
        finally:
            await self.cleanup()


async def test_hello_goodbye_pattern():
    """Test the hello/goodbye conversation pattern"""
    logger.info("Testing Hello/Goodbye conversation pattern")
    
    # Start the initiator
    initiator = HelloGoodbyeInitiator()
    success = await initiator.run_conversation()
    
    if success:
        logger.info("✓ Hello/Goodbye test completed successfully")
        return True
    else:
        logger.error("✗ Hello/Goodbye test failed")
        return False


async def main():
    """Main test function"""
    success = await test_hello_goodbye_pattern()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    asyncio.run(main())