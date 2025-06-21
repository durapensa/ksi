#!/usr/bin/env python3
"""
Hello/Goodbye Conversation Pattern - Initiator Script

This script implements the initiator side of a simple hello/goodbye exchange.
It sends "Hello!" to start the conversation, waits for a response, 
then sends "Goodbye!" to end it.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('hello_goodbye_initiator')


class HelloGoodbyeInitiator:
    """Handles the initiator side of hello/goodbye exchange"""
    
    def __init__(self, agent_id='hello_initiator', target_agent='hello_responder'):
        self.agent_id = agent_id
        self.target_agent = target_agent
        self.message_count = 0
        self.max_messages = 2
        self.conversation_started = False
        
    async def connect_to_daemon(self):
        """Connect to the daemon"""
        try:
            self.reader, self.writer = await asyncio.open_unix_connection('sockets/claude_daemon.sock')
            logger.info("Connected to daemon")
            return True
        except (FileNotFoundError, ConnectionRefusedError) as e:
            logger.error(f"Failed to connect to daemon: {e}")
            return False
    
    async def register_agent(self):
        """Register this agent with the daemon"""
        command = {
            "action": "REGISTER_AGENT",
            "agent_id": self.agent_id,
            "profile": {
                "model": "sonnet",
                "role": "initiator",
                "composition": "simple_hello_goodbye"
            }
        }
        
        await self.send_command(command)
        response = await self.receive_response()
        
        if response and response.get('status') == 'registered':
            logger.info(f"Agent {self.agent_id} registered successfully")
            return True
        else:
            logger.error(f"Failed to register agent: {response}")
            return False
    
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
    
    async def handle_response(self, message):
        """Handle incoming response and send next message if needed"""
        content = message.get('content', '').strip()
        from_agent = message.get('from_agent', 'unknown')
        
        logger.info(f"Received from {from_agent}: '{content}'")
        
        if self.message_count == 1 and content.lower().startswith('hello'):
            # Got response to hello - now send goodbye
            await asyncio.sleep(1)  # Brief pause
            await self.send_goodbye()
            return True
            
        elif self.message_count == 2 and content.lower().startswith('goodbye'):
            # Got response to goodbye - conversation complete
            logger.info("Conversation completed successfully!")
            return False
            
        else:
            logger.warning(f"Unexpected response at count {self.message_count}: {content}")
            return False
    
    async def send_message(self, content):
        """Send a message to the target agent"""
        command = {
            "action": "SEND_MESSAGE",
            "to_agent": self.target_agent,
            "content": content,
            "from_agent": self.agent_id
        }
        
        await self.send_command(command)
        logger.info(f"Sent to {self.target_agent}: '{content}'")
        self.message_count += 1
    
    async def send_hello(self):
        """Send the initial hello message"""
        await self.send_message("Hello! I'm starting a conversation.")
    
    async def send_goodbye(self):
        """Send the goodbye message"""
        await self.send_message("Goodbye! Thanks for the chat.")
    
    async def listen_for_responses(self):
        """Listen for responses from the target agent"""
        logger.info("Listening for responses...")
        
        while True:
            response = await self.receive_response()
            
            if not response:
                logger.warning("No response received, continuing...")
                await asyncio.sleep(1)
                continue
                
            if response.get('type') == 'message':
                should_continue = await self.handle_response(response)
                if not should_continue:
                    break
            else:
                logger.debug(f"Received non-message response: {response}")
    
    async def start_conversation(self):
        """Start the conversation by sending hello"""
        if not self.conversation_started:
            await asyncio.sleep(2)  # Wait for responder to be ready
            await self.send_hello()
            self.conversation_started = True
    
    async def cleanup(self):
        """Clean up connections"""
        if hasattr(self, 'writer'):
            self.writer.close()
            await self.writer.wait_closed()
        logger.info("Cleaned up connections")
    
    async def run(self):
        """Main run loop"""
        try:
            # Connect to daemon
            if not await self.connect_to_daemon():
                return False
            
            # Register agent
            if not await self.register_agent():
                return False
            
            # Start conversation and listen for responses
            await asyncio.gather(
                self.start_conversation(),
                self.listen_for_responses()
            )
            
            return True
            
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            return True
        except Exception as e:
            logger.error(f"Error in initiator: {e}")
            return False
        finally:
            await self.cleanup()


async def main():
    """Main function"""
    agent_id = sys.argv[1] if len(sys.argv) > 1 else 'hello_initiator'
    target_agent = sys.argv[2] if len(sys.argv) > 2 else 'hello_responder'
    
    initiator = HelloGoodbyeInitiator(agent_id, target_agent)
    success = await initiator.run()
    
    if success:
        logger.info("Hello/Goodbye initiator completed successfully")
        sys.exit(0)
    else:
        logger.error("Hello/Goodbye initiator failed")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())