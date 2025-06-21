#!/usr/bin/env python3
"""
Hello/Goodbye Conversation Pattern - Responder Script

This script implements the responder side of a simple hello/goodbye exchange.
It waits for a "Hello!" message and responds appropriately, then waits for
"Goodbye!" and ends the conversation.
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
logger = logging.getLogger('hello_goodbye_responder')


class HelloGoodbyeResponder:
    """Handles the responder side of hello/goodbye exchange"""
    
    def __init__(self, agent_id='hello_responder', target_agent='hello_initiator'):
        self.agent_id = agent_id
        self.target_agent = target_agent
        self.message_count = 0
        self.conversation_active = False
        
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
                "role": "responder",
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
    
    async def handle_message(self, message):
        """Handle incoming message and respond appropriately"""
        content = message.get('content', '').strip()
        from_agent = message.get('from_agent', 'unknown')
        
        logger.info(f"Received from {from_agent}: '{content}'")
        
        content_lower = content.lower()
        
        if content_lower.startswith('hello'):
            # Respond to hello message
            await asyncio.sleep(0.5)  # Brief pause before responding
            response = "Hello! Nice to meet you. How are you doing?"
            await self.send_message(response)
            self.conversation_active = True
            return True
            
        elif content_lower.startswith('goodbye'):
            # Respond to goodbye message and end conversation
            await asyncio.sleep(0.5)  # Brief pause before responding
            response = "Goodbye! It was nice chatting with you!"
            await self.send_message(response)
            self.conversation_active = False
            logger.info("Conversation completed successfully!")
            return False
            
        else:
            # Handle other messages during conversation
            if self.conversation_active:
                response = f"I received: '{content}'. What else would you like to talk about?"
                await self.send_message(response)
                return True
            else:
                logger.warning(f"Received unexpected message when not in conversation: {content}")
                return True
    
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
    
    async def listen_for_messages(self):
        """Listen for messages from other agents"""
        logger.info("Listening for messages...")
        
        while True:
            response = await self.receive_response()
            
            if not response:
                logger.warning("No response received, continuing...")
                await asyncio.sleep(1)
                continue
                
            if response.get('type') == 'message':
                should_continue = await self.handle_message(response)
                if not should_continue:
                    # Conversation ended, but keep listening for new conversations
                    logger.info("Ready for new conversation...")
                    continue
            else:
                logger.debug(f"Received non-message response: {response}")
    
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
            
            # Start listening for messages
            await self.listen_for_messages()
            
            return True
            
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            return True
        except Exception as e:
            logger.error(f"Error in responder: {e}")
            return False
        finally:
            await self.cleanup()


async def main():
    """Main function"""
    agent_id = sys.argv[1] if len(sys.argv) > 1 else 'hello_responder'
    target_agent = sys.argv[2] if len(sys.argv) > 2 else 'hello_initiator'
    
    responder = HelloGoodbyeResponder(agent_id, target_agent)
    success = await responder.run()
    
    if success:
        logger.info("Hello/Goodbye responder completed successfully")
        sys.exit(0)
    else:
        logger.error("Hello/Goodbye responder failed")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())