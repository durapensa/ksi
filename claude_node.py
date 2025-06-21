#!/usr/bin/env python3
"""
Claude Node - Persistent Claude process that maintains connection to daemon
This enables Claude-to-Claude conversations and autonomous agent behavior
"""

import asyncio
import json
import os
import sys
import logging
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('claude_node')


class ClaudeNode:
    """A persistent Claude instance that can converse with other Claudes"""
    
    def __init__(self, node_id: str, profile: str = 'default', daemon_socket: str = 'sockets/claude_daemon.sock'):
        self.node_id = node_id
        self.profile = profile
        self.daemon_socket = daemon_socket
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.session_id: Optional[str] = None
        self.conversation_context: List[Dict] = []
        self.active_conversations: Dict[str, Dict] = {}  # conversation_id -> conversation state
        self.running = True
        
        # Load agent profile if specified
        self.profile_config = self._load_profile(profile)
        
    def _load_profile(self, profile_name: str) -> Dict:
        """Load agent profile configuration"""
        if profile_name == 'default':
            return {
                'model': 'sonnet',
                'role': 'general',
                'capabilities': ['conversation', 'analysis', 'coding'],
                'system_prompt': None
            }
        
        profile_path = Path(f'agent_profiles/{profile_name}.json')
        if profile_path.exists():
            with open(profile_path) as f:
                return json.load(f)
        else:
            logger.warning(f"Profile {profile_name} not found, using default")
            return self._load_profile('default')
    
    async def connect(self):
        """Connect to the daemon and register as persistent agent"""
        try:
            self.reader, self.writer = await asyncio.open_unix_connection(self.daemon_socket)
            logger.info(f"Connected to daemon at {self.daemon_socket}")
            
            # Register as persistent agent
            command = f"CONNECT_AGENT:{self.node_id}\n"
            self.writer.write(command.encode())
            await self.writer.drain()
            
            # Read response
            response = await self.reader.readline()
            result = json.loads(response.decode().strip())
            
            if result.get('status') == 'connected':
                logger.info(f"Successfully registered as agent {self.node_id}")
                
                # Subscribe to relevant events
                await self._subscribe_to_events()
                return True
            else:
                logger.error(f"Failed to register: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to daemon: {e}")
            return False
    
    async def _subscribe_to_events(self):
        """Subscribe to message bus events"""
        event_types = ['DIRECT_MESSAGE', 'BROADCAST', 'TASK_ASSIGNMENT', 'CONVERSATION_INVITE']
        
        # Need separate connection for subscription
        sub_reader, sub_writer = await asyncio.open_unix_connection(self.daemon_socket)
        
        command = f"SUBSCRIBE:{self.node_id}:{','.join(event_types)}\n"
        sub_writer.write(command.encode())
        await sub_writer.drain()
        
        response = await sub_reader.readline()
        sub_writer.close()
        await sub_writer.wait_closed()
        
        result = json.loads(response.decode().strip())
        
        if result.get('status') == 'subscribed':
            logger.info(f"Subscribed to events: {event_types}")
        else:
            logger.error(f"Failed to subscribe: {result}")
    
    async def listen_for_messages(self):
        """Listen for incoming messages from daemon"""
        try:
            while self.running:
                if not self.reader:
                    logger.warning("Reader connection lost")
                    break
                    
                try:
                    data = await self.reader.readline()
                    if not data:
                        logger.warning("Connection closed by daemon")
                        break
                    
                    try:
                        message = json.loads(data.decode().strip())
                        await self.handle_message(message)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid message format: {data}")
                        
                except asyncio.CancelledError:
                    logger.info("Message listener cancelled")
                    break
                except ConnectionResetError:
                    logger.error("Connection reset by daemon")
                    break
                except BrokenPipeError:
                    logger.error("Broken pipe - daemon connection lost")
                    break
                    
        except Exception as e:
            logger.error(f"Error in message listener: {e}")
        finally:
            logger.info(f"Node {self.node_id} shutting down")
            await self.disconnect()
    
    async def handle_message(self, message: Dict):
        """Handle incoming message from another Claude or the system"""
        msg_type = message.get('type')
        msg_from = message.get('from')
        
        logger.info(f"Received {msg_type} from {msg_from}")
        
        if msg_type == 'DIRECT_MESSAGE':
            await self.handle_direct_message(message)
        elif msg_type == 'CONVERSATION_INVITE':
            await self.handle_conversation_invite(message)
        elif msg_type == 'TASK_ASSIGNMENT':
            await self.handle_task_assignment(message)
        elif msg_type == 'BROADCAST':
            await self.handle_broadcast(message)
        else:
            logger.warning(f"Unknown message type: {msg_type}")
    
    async def handle_direct_message(self, message: Dict):
        """Handle direct message from another Claude"""
        conversation_id = message.get('conversation_id')
        content = message.get('content')
        from_agent = message.get('from')
        
        # Add to conversation context
        if conversation_id not in self.active_conversations:
            self.active_conversations[conversation_id] = {
                'participants': [from_agent, self.node_id],
                'history': []
            }
        
        self.active_conversations[conversation_id]['history'].append({
            'from': from_agent,
            'content': content,
            'timestamp': message.get('timestamp')
        })
        
        # Generate response using Claude
        response = await self.generate_claude_response(content, conversation_id)
        
        # Send response back
        if response:
            await self.send_message(from_agent, response, conversation_id)
    
    async def generate_claude_response(self, prompt: str, conversation_id: str) -> Optional[str]:
        """Generate response using Claude CLI"""
        try:
            # Build conversation context
            context = self._build_conversation_context(conversation_id)
            
            # Prepare the full prompt with context
            if context:
                full_prompt = f"{context}\n\nRespond to: {prompt}"
            else:
                full_prompt = prompt
            
            # Add role-specific instructions if available
            if self.profile_config.get('system_prompt'):
                full_prompt = f"{self.profile_config['system_prompt']}\n\n{full_prompt}"
            
            # Create or resume session
            cmd = [
                'claude',
                '--model', self.profile_config.get('model', 'sonnet'),
                '--print',
                '--output-format', 'json',
                '--allowedTools', 'Task,Bash,Glob,Grep,LS,Read,Edit,MultiEdit,Write,WebFetch,WebSearch'
            ]
            
            if self.session_id:
                cmd.extend(['--resume', self.session_id])
            
            # Run Claude
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(input=full_prompt)
            
            if process.returncode != 0:
                logger.error(f"Claude CLI failed with code {process.returncode}")
                logger.error(f"Command: {' '.join(cmd)}")
                logger.error(f"Stderr: {stderr}")
                logger.error(f"Stdout: {stdout}")
                return None
            
            # Parse output
            try:
                for line in stdout.strip().split('\n'):
                    if line.strip():
                        output = json.loads(line)
                        # Handle new claude CLI output format
                        if output.get('type') == 'result' and output.get('result'):
                            # Store session_id for future use
                            if output.get('session_id'):
                                self.session_id = output['session_id']
                            return output.get('result', '').strip()
                        # Legacy format support
                        elif output.get('type') == 'text':
                            return output.get('text', '').strip()
                        elif output.get('sessionId'):
                            self.session_id = output['sessionId']
            except json.JSONDecodeError:
                logger.error(f"Failed to parse Claude output: {stdout}")
                
        except Exception as e:
            logger.error(f"Error generating Claude response: {e}")
            
        return None
    
    def _build_conversation_context(self, conversation_id: str) -> str:
        """Build conversation context for Claude"""
        if conversation_id not in self.active_conversations:
            return ""
        
        history = self.active_conversations[conversation_id]['history']
        if not history:
            return ""
        
        # Include last N messages for context
        context_messages = history[-10:]  # Last 10 messages
        
        context = "Previous conversation:\n"
        for msg in context_messages:
            context += f"{msg['from']}: {msg['content']}\n"
        
        return context
    
    async def send_message(self, to_agent: str, content: str, conversation_id: str):
        """Send message to another agent"""
        try:
            message = {
                'to': to_agent,
                'content': content,
                'conversation_id': conversation_id
            }
            
            # Use a separate connection for sending commands
            cmd_reader, cmd_writer = await asyncio.open_unix_connection(self.daemon_socket)
            
            command = f"PUBLISH:{self.node_id}:DIRECT_MESSAGE:{json.dumps(message)}\n"
            cmd_writer.write(command.encode())
            await cmd_writer.drain()
            
            # Read response
            response = await cmd_reader.readline()
            if response:
                result = json.loads(response.decode().strip())
                logger.info(f"Message sent: {result}")
            
            cmd_writer.close()
            await cmd_writer.wait_closed()
            
            # Add to our conversation history
            if conversation_id in self.active_conversations:
                self.active_conversations[conversation_id]['history'].append({
                    'from': self.node_id,
                    'content': content,
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                })
                
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
    
    async def start_conversation(self, with_agents: List[str], topic: str):
        """Start a new conversation with other agents"""
        conversation_id = f"conv_{self.node_id}_{datetime.utcnow().timestamp()}"
        
        # Initialize conversation
        self.active_conversations[conversation_id] = {
            'participants': [self.node_id] + with_agents,
            'topic': topic,
            'history': []
        }
        
        # Invite other agents
        for agent in with_agents:
            try:
                invite = {
                    'to': agent,
                    'conversation_id': conversation_id,
                    'topic': topic,
                    'initiator': self.node_id
                }
                
                # Use separate connection for sending command
                cmd_reader, cmd_writer = await asyncio.open_unix_connection(self.daemon_socket)
                
                command = f"PUBLISH:{self.node_id}:CONVERSATION_INVITE:{json.dumps(invite)}\n"
                cmd_writer.write(command.encode())
                await cmd_writer.drain()
                
                # Read response
                response = await cmd_reader.readline()
                if response:
                    result = json.loads(response.decode().strip())
                    logger.info(f"Invite sent: {result}")
                
                cmd_writer.close()
                await cmd_writer.wait_closed()
                
            except Exception as e:
                logger.error(f"Failed to send invite to {agent}: {e}")
        
        # Send initial message
        await self.send_message(with_agents[0], topic, conversation_id)
        
        return conversation_id
    
    async def handle_conversation_invite(self, message: Dict):
        """Handle invitation to join a conversation"""
        conversation_id = message.get('conversation_id')
        topic = message.get('topic')
        initiator = message.get('initiator')
        
        logger.info(f"Invited to conversation {conversation_id} about '{topic}' by {initiator}")
        
        # Accept the invitation by adding to active conversations
        self.active_conversations[conversation_id] = {
            'participants': [initiator, self.node_id],
            'topic': topic,
            'history': []
        }
    
    async def handle_task_assignment(self, message: Dict):
        """Handle task assignment"""
        task = message.get('task')
        context = message.get('context', '')
        
        logger.info(f"Assigned task: {task}")
        
        # Generate response for the task
        response = await self.generate_claude_response(f"Task: {task}\nContext: {context}", "task")
        
        # Send result back
        if response and message.get('from'):
            await self.send_message(message['from'], response, f"task_{message.get('id', 'unknown')}")
    
    async def handle_broadcast(self, message: Dict):
        """Handle broadcast message"""
        logger.info(f"Broadcast from {message.get('from')}: {message.get('content', '')[:100]}...")
        # Could respond to broadcasts if needed
    
    async def disconnect(self):
        """Disconnect from daemon"""
        if self.writer:
            try:
                command = f"DISCONNECT_AGENT:{self.node_id}\n"
                self.writer.write(command.encode())
                await self.writer.drain()
                
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
        
        self.running = False
        logger.info(f"Node {self.node_id} disconnected")
    
    async def run(self):
        """Main run loop"""
        if not await self.connect():
            return
        
        try:
            # Listen for messages
            await self.listen_for_messages()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await self.disconnect()


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Claude Node - Persistent Claude agent')
    parser.add_argument('--id', required=True, help='Unique node ID')
    parser.add_argument('--profile', default='default', help='Agent profile to use')
    parser.add_argument('--socket', default='sockets/claude_daemon.sock', help='Daemon socket path')
    parser.add_argument('--start-conversation', action='store_true', help='Start a conversation with other nodes')
    parser.add_argument('--with-agents', nargs='+', help='Agents to converse with')
    parser.add_argument('--topic', help='Conversation topic')
    
    args = parser.parse_args()
    
    # Create and run node
    node = ClaudeNode(args.id, args.profile, args.socket)
    
    if args.start_conversation and args.with_agents and args.topic:
        # Start conversation mode
        await node.connect()
        conversation_id = await node.start_conversation(args.with_agents, args.topic)
        logger.info(f"Started conversation {conversation_id}")
        await node.listen_for_messages()
    else:
        # Just run as listener
        await node.run()


if __name__ == '__main__':
    asyncio.run(main())