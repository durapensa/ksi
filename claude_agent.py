#!/usr/bin/env python3
"""
Persistent Claude Agent - Maintains connection to daemon and handles messages
"""

import asyncio
import json
import os
import sys
import socket
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
import argparse
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('claude_agent')

class ClaudeAgent:
    """Persistent Claude agent that maintains daemon connection"""
    
    def __init__(self, agent_id: str, profile_name: str = "analyst", daemon_socket: str = 'sockets/claude_daemon.sock'):
        self.agent_id = agent_id
        self.profile_name = profile_name
        self.daemon_socket = daemon_socket
        self.session_id = None
        self.running = True
        self.message_queue = asyncio.Queue()
        self.reader = None
        self.writer = None
        
        # Load profile
        self.profile = self._load_profile()
        
    def _load_profile(self) -> dict:
        """Load agent profile"""
        try:
            profile_path = f'agent_profiles/{self.profile_name}.json'
            with open(profile_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load profile {self.profile_name}: {e}")
            return {
                "role": "Generic Agent",
                "capabilities": ["general"],
                "model": "sonnet"
            }
    
    async def connect_to_daemon(self):
        """Establish persistent connection to daemon"""
        while self.running:
            try:
                # Connect via Unix socket
                reader, writer = await asyncio.open_unix_connection(self.daemon_socket)
                self.reader = reader
                self.writer = writer
                logger.info(f"Agent {self.agent_id} connected to daemon")
                
                # Register with daemon
                await self.register_with_daemon()
                
                # Subscribe to messages
                await self.subscribe_to_messages()
                
                # Start message handler
                await self.handle_daemon_messages()
                
            except Exception as e:
                logger.error(f"Connection error: {e}")
                await asyncio.sleep(5)  # Retry after 5 seconds
    
    async def register_with_daemon(self):
        """Register this agent with the daemon"""
        # First, connect this agent to the message bus
        command = f"AGENT_CONNECTION:connect:{self.agent_id}\n"
        self.writer.write(command.encode())
        await self.writer.drain()
        
        # Read response
        response = await self.reader.readline()
        if response:
            try:
                result = json.loads(response.decode())
                logger.info(f"Connection result: {result}")
            except:
                logger.debug(f"Connection response: {response.decode()}")
        
        # Then register the agent
        capabilities = ','.join(self.profile.get('capabilities', []))
        command = f"REGISTER_AGENT:{self.agent_id}:{self.profile.get('role', 'Agent')}:{capabilities}\n"
        
        self.writer.write(command.encode())
        await self.writer.drain()
        
        # Read response
        response = await self.reader.readline()
        if response:
            try:
                result = json.loads(response.decode())
                logger.info(f"Registration result: {result}")
            except:
                logger.debug(f"Registration response: {response.decode()}")
    
    async def subscribe_to_messages(self):
        """Subscribe to receive messages for this agent"""
        command = f"SUBSCRIBE:{self.agent_id}:DIRECT_MESSAGE,BROADCAST,TASK_ASSIGNMENT\n"
        self.writer.write(command.encode())
        await self.writer.drain()
    
    async def handle_daemon_messages(self):
        """Handle incoming messages from daemon"""
        try:
            while self.running:
                # Read message from daemon
                data = await self.reader.readline()
                if not data:
                    logger.warning("Connection closed by daemon")
                    break
                
                try:
                    message = json.loads(data.decode())
                    await self.process_message(message)
                except json.JSONDecodeError:
                    # Handle non-JSON messages
                    text = data.decode().strip()
                    logger.debug(f"Received text: {text}")
                    
        except Exception as e:
            logger.error(f"Error handling messages: {e}")
    
    async def process_message(self, message: dict):
        """Process incoming message"""
        msg_type = message.get('type')
        
        if msg_type == 'DIRECT_MESSAGE':
            await self.handle_direct_message(message)
        elif msg_type == 'TASK_ASSIGNMENT':
            await self.handle_task_assignment(message)
        elif msg_type == 'BROADCAST':
            await self.handle_broadcast(message)
        else:
            logger.warning(f"Unknown message type: {msg_type}")
    
    async def handle_direct_message(self, message: dict):
        """Handle direct message from another agent"""
        from_agent = message.get('from')
        content = message.get('content')
        context = message.get('context', {})
        
        logger.info(f"Received message from {from_agent}: {content[:50]}...")
        
        # Prepare prompt for Claude
        prompt = f"""You are {self.agent_id}, a {self.profile.get('role', 'Agent')}.

You received this message from {from_agent}:
{content}

Context: {json.dumps(context, indent=2)}

Please respond appropriately based on your role and the message content."""
        
        # Get Claude's response
        response = await self.ask_claude(prompt)
        
        if response:
            # Send response back
            await self.send_message(from_agent, response.get('result', 'No response generated'))
    
    async def handle_task_assignment(self, message: dict):
        """Handle task assignment"""
        task = message.get('task')
        context = message.get('context', '')
        from_agent = message.get('from', 'orchestrator')
        
        logger.info(f"Received task: {task[:50]}...")
        
        # Format task prompt using profile template
        if 'prompt_template' in self.profile:
            prompt = self.profile['prompt_template'].format(
                task=task,
                context=context,
                agents=json.dumps({self.agent_id: self.profile})
            )
        else:
            prompt = f"Task: {task}\nContext: {context}"
        
        # Get Claude's response
        response = await self.ask_claude(prompt)
        
        if response:
            # Report task completion
            result = response.get('result', 'Task completed')
            await self.send_message(from_agent, f"Task completed: {result}")
    
    async def handle_broadcast(self, message: dict):
        """Handle broadcast message"""
        from_agent = message.get('from')
        content = message.get('content')
        
        logger.info(f"Received broadcast from {from_agent}: {content[:50]}...")
        
        # Optionally respond to broadcasts based on content
        if 'request for' in content.lower():
            # This agent might volunteer for certain requests
            capabilities = self.profile.get('capabilities', [])
            if any(cap in content.lower() for cap in capabilities):
                await self.send_message(from_agent, f"I can help with that. My capabilities include: {', '.join(capabilities)}")
    
    async def ask_claude(self, prompt: str) -> dict:
        """Send prompt to Claude and get response"""
        # Build unified spawn command: SPAWN:sync:claude:session_id:model:agent_id:prompt
        command = f"SPAWN:sync:claude:{self.session_id if self.session_id else ''}:sonnet:{self.agent_id}:{prompt}\n"
        
        # Send to daemon
        self.writer.write(command.encode())
        await self.writer.drain()
        
        # Read response
        response_data = await self.reader.readline()
        if response_data:
            try:
                response = json.loads(response_data.decode())
                
                # Update session ID
                new_session_id = response.get('sessionId') or response.get('session_id')
                if new_session_id:
                    self.session_id = new_session_id
                
                return response
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON response: {response_data.decode()}")
                return None
        
        return None
    
    async def send_message(self, to_agent: str, content: str):
        """Send message to another agent via daemon"""
        command = f"PUBLISH:{self.agent_id}:DIRECT_MESSAGE:{json.dumps({'to': to_agent, 'content': content})}\n"
        
        self.writer.write(command.encode())
        await self.writer.drain()
        
        logger.info(f"Sent message to {to_agent}")
    
    async def broadcast_message(self, content: str):
        """Broadcast message to all agents"""
        command = f"PUBLISH:{self.agent_id}:BROADCAST:{json.dumps({'content': content})}\n"
        
        self.writer.write(command.encode())
        await self.writer.drain()
        
        logger.info("Broadcasted message")
    
    async def run(self):
        """Main agent loop"""
        logger.info(f"Starting agent {self.agent_id} with profile {self.profile_name}")
        
        try:
            await self.connect_to_daemon()
        except KeyboardInterrupt:
            logger.info("Agent shutting down...")
            self.running = False
        except Exception as e:
            logger.error(f"Agent error: {e}")
        finally:
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Persistent Claude Agent')
    parser.add_argument('--id', default=None, help='Agent ID (default: auto-generated)')
    parser.add_argument('--profile', default='analyst', help='Agent profile (default: analyst)')
    parser.add_argument('--socket', default='sockets/claude_daemon.sock', help='Daemon socket path')
    
    args = parser.parse_args()
    
    # Generate agent ID if not provided
    agent_id = args.id or f"{args.profile}_{str(uuid.uuid4())[:8]}"
    
    # Create and run agent
    agent = ClaudeAgent(agent_id, args.profile, args.socket)
    await agent.run()

if __name__ == '__main__':
    asyncio.run(main())