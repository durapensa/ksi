#!/usr/bin/env python3
"""
Agent Process - Persistent Claude agent that maintains connection to daemon
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
import re

# Add path for prompt composer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prompts.composer import PromptComposer
from daemon.timestamp_utils import TimestampManager
from daemon.client import CommandBuilder, ResponseHandler, ConnectionManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('agent_process')


class AgentProcess:
    """A persistent Claude instance that can converse with other Claudes"""
    
    def __init__(self, agent_id: str, profile: str = 'default', daemon_socket: str = 'sockets/claude_daemon.sock'):
        self.agent_id = agent_id
        self.profile = profile
        self.daemon_socket = daemon_socket
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.session_id: Optional[str] = None
        self.conversation_context: List[Dict] = []
        self.active_conversations: Dict[str, Dict] = {}  # conversation_id -> conversation state
        self.running = True
        self.prompt_composer = PromptComposer()
        self.pending_processes: Dict[str, Dict] = {}  # process_id -> pending response info
        
        # Load agent profile if specified
        logger.info(f"Loading profile '{profile}' for agent {agent_id}")
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
            
            # Register as persistent agent using JSON protocol
            cmd_obj = CommandBuilder.build_agent_connection_command("connect", self.agent_id)
            
            command_str = json.dumps(cmd_obj) + '\n'
            self.writer.write(command_str.encode())
            await self.writer.drain()
            
            # Read response
            response = await self.reader.readline()
            result = json.loads(response.decode().strip())
            
            if result.get('status') == 'success' and result.get('result', {}).get('status') == 'connected':
                logger.info(f"Successfully registered as agent {self.agent_id}")
                
                # Create or update identity for this agent
                await self._ensure_identity()
                
                # Subscribe to relevant events
                await self._subscribe_to_events()
                return True
            else:
                logger.error(f"Failed to register: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to daemon: {e}")
            return False
    
    async def _ensure_identity(self):
        """Create or update identity for this agent"""
        try:
            # Try to get existing identity first
            result = await self._send_daemon_command("GET_IDENTITY", {"agent_id": self.agent_id})
            
            if result and result.get('status') == 'success' and result.get('result', {}).get('status') == 'identity_found':
                identity = result.get('result', {}).get('identity', {})
                logger.info(f"Found existing identity for {self.agent_id}: {identity.get('display_name')}")
                return
            
            # Create new identity
            role = self.profile_config.get('role', self.profile)
            display_name = f"{role.title()}-{self.agent_id[-4:]}" if role != 'default' else f"Agent-{self.agent_id[-8:]}"
            
            # Get personality traits from profile capabilities
            capabilities = self.profile_config.get('capabilities', [])
            traits = self._capabilities_to_traits(capabilities)
            
            create_params = {
                "agent_id": self.agent_id,
                "display_name": display_name,
                "role": role,
                "personality_traits": traits
            }
            result = await self._send_daemon_command("CREATE_IDENTITY", create_params)
            
            if result and result.get('status') == 'success' and result.get('result', {}).get('status') == 'identity_created':
                logger.info(f"Created identity '{display_name}' for agent {self.agent_id}")
            else:
                logger.warning(f"Failed to create identity: {result}")
                
        except Exception as e:
            logger.error(f"Error ensuring identity: {e}")
    
    def _capabilities_to_traits(self, capabilities):
        """Convert capabilities to personality traits"""
        trait_mapping = {
            'web_search': 'research-oriented',
            'information_gathering': 'thorough', 
            'analysis': 'analytical',
            'fact_checking': 'precise',
            'coding': 'logical',
            'debugging': 'systematic',
            'testing': 'methodical',
            'code_review': 'detail-oriented',
            'architecture': 'strategic',
            'conversation': 'communicative',
            'teaching': 'patient',
            'learning': 'curious',
            'debate': 'articulate',
            'collaboration': 'cooperative',
            'creativity': 'imaginative',
            'problem_solving': 'resourceful'
        }
        
        traits = []
        for cap in capabilities:
            if cap in trait_mapping:
                traits.append(trait_mapping[cap])
        
        # Add default traits if none found
        if not traits:
            traits = ['helpful', 'professional', 'reliable']
            
        return traits[:4]  # Limit to 4 traits
    
    async def _subscribe_to_events(self):
        """Subscribe to message bus events"""
        event_types = ['DIRECT_MESSAGE', 'BROADCAST', 'TASK_ASSIGNMENT', 'CONVERSATION_INVITE', 'PROCESS_COMPLETE']
        
        # Need separate connection for subscription
        sub_reader, sub_writer = await asyncio.open_unix_connection(self.daemon_socket)
        
        # Build JSON SUBSCRIBE command
        cmd_obj = CommandBuilder.build_subscribe_command(self.agent_id, event_types)
        
        command_str = json.dumps(cmd_obj) + '\n'
        sub_writer.write(command_str.encode())
        await sub_writer.drain()
        
        response = await sub_reader.readline()
        sub_writer.close()
        await sub_writer.wait_closed()
        
        result = json.loads(response.decode().strip())
        
        if result.get('status') == 'success' and result.get('result', {}).get('status') == 'subscribed':
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
            logger.info(f"Agent {self.agent_id} shutting down")
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
        elif msg_type == 'PROCESS_COMPLETE':
            await self.handle_process_complete(message)
        else:
            logger.warning(f"Unknown message type: {msg_type}")
    
    def _extract_control_signals(self, text: str) -> tuple[str, list[str]]:
        """Extract control signals from response text"""
        control_signals = []
        clean_text = text
        
        # Look for control signals at the end of the message
        control_pattern = r'\[(END|NO_RESPONSE|TERMINATE)\]'
        matches = re.findall(control_pattern, text)
        
        if matches:
            control_signals = matches
            # Remove control signals from the text
            clean_text = re.sub(control_pattern, '', text).strip()
        
        return clean_text, control_signals
    
    def _should_send_response(self, response: str) -> bool:
        """Check if response should be sent based on control signals"""
        _, signals = self._extract_control_signals(response)
        return 'NO_RESPONSE' not in signals
    
    def _should_terminate(self, response: str) -> bool:
        """Check if agent should terminate based on control signals"""
        _, signals = self._extract_control_signals(response)
        return 'END' in signals or 'TERMINATE' in signals
    
    async def handle_direct_message(self, message: Dict):
        """Handle direct message from another Claude"""
        conversation_id = message.get('conversation_id')
        content = message.get('content')
        from_agent = message.get('from')
        
        # Check if incoming message contains termination signal
        if content and self._should_terminate(content):
            logger.info(f"Agent {self.agent_id} received [END] signal from {from_agent}, preparing to shut down")
            self.running = False
            # Send acknowledgment before shutting down
            await self.send_message(from_agent, "Acknowledged [END] signal. Shutting down.", conversation_id)
            asyncio.create_task(self._delayed_shutdown())
            return
        
        # Add to conversation context
        if conversation_id not in self.active_conversations:
            self.active_conversations[conversation_id] = {
                'participants': [from_agent, self.agent_id],
                'history': []
            }
        
        self.active_conversations[conversation_id]['history'].append({
            'from': from_agent,
            'content': content,
            'timestamp': message.get('timestamp')
        })
        
        # Start async Claude response generation
        process_id = await self.start_claude_response(content, conversation_id, from_agent)
        
        if not process_id:
            logger.error("Failed to start Claude response generation")
    
    async def _send_daemon_command(self, command_name: str, parameters: dict = None) -> Optional[dict]:
        """Send JSON command to daemon and get response"""
        try:
            reader, writer = await asyncio.open_unix_connection(self.daemon_socket)
            
            # Build JSON command
            cmd_obj = CommandBuilder.build_command(command_name, parameters)
            
            # Send JSON command
            command_str = json.dumps(cmd_obj) + '\n'
            writer.write(command_str.encode())
            await writer.drain()
            
            # Read response
            response = await reader.readline()
            writer.close()
            await writer.wait_closed()
            
            if response:
                return json.loads(response.decode().strip())
            return None
            
        except Exception as e:
            logger.error(f"Error communicating with daemon: {e}")
            return None
    
    async def _send_spawn_command(self, mode: str, session_id: str, model: str, agent_id: str, prompt: str) -> dict:
        """Send SPAWN command with JSON protocol"""
        try:
            reader, writer = await asyncio.open_unix_connection(self.daemon_socket)
            
            # Build JSON SPAWN command using shared utilities
            cmd_obj = CommandBuilder.build_spawn_command(
                prompt=prompt,
                mode=mode,
                session_id=session_id,
                model=model,
                agent_id=agent_id,
                enable_tools=True
            )
            
            # Send JSON command
            command_str = json.dumps(cmd_obj) + '\n'
            writer.write(command_str.encode())
            await writer.drain()
            
            # Wait for response
            response = await reader.readline()
            writer.close()
            await writer.wait_closed()
            
            if response:
                return json.loads(response.decode().strip())
            return None
        except Exception as e:
            logger.error(f"Error sending spawn command: {e}")
            return None
    
    async def get_daemon_commands(self) -> dict:
        """Get available daemon commands dynamically"""
        result = await self._send_daemon_command("GET_COMMANDS")
        if result and 'commands' in result:
            return result['commands']
        return {}

    async def start_claude_response(self, prompt: str, conversation_id: str, from_agent: str) -> Optional[str]:
        """Start async Claude response generation and return process_id"""
        try:
            # Get daemon commands dynamically
            daemon_commands = await self.get_daemon_commands()
            
            # Use agent role from profile for conversation patterns
            agent_role = self.profile_config.get('role', 'responder')
            
            # Build context for prompt composer
            context = {
                'agent_id': self.agent_id,
                'agent_role': agent_role,
                'conversation_id': conversation_id,
                'daemon_commands': daemon_commands,
                'user_prompt': prompt,
                'conversation_history': self._build_conversation_context(conversation_id),
                'enable_tools': self.profile_config.get('enable_tools', True)
            }
            
            # Use composition from profile or default
            composition_name = self.profile_config.get('composition', 'claude_agent_default')
            
            # Compose the full prompt
            try:
                logger.info(f"Composing prompt with {composition_name}, context keys: {list(context.keys())}")
                full_prompt = self.prompt_composer.compose(composition_name, context)
                logger.info(f"Successfully composed prompt ({len(full_prompt)} chars)")
            except (FileNotFoundError, ValueError, Exception) as e:
                if isinstance(e, FileNotFoundError):
                    logger.warning(f"Composition error: {e}\nFalling back to legacy prompt")
                elif isinstance(e, ValueError):
                    logger.error(f"Context validation error: {e}\nFalling back to legacy prompt")
                else:
                    logger.error(f"Unexpected composition error: {e}\nFalling back to legacy prompt")
                
                # Fallback to legacy prompt construction
                logger.info("Using legacy prompt construction as fallback")
                context_str = self._build_conversation_context(conversation_id)
                if context_str:
                    full_prompt = f"{context_str}\n\nRespond to: {prompt}"
                else:
                    full_prompt = prompt
                
                # Add role-specific instructions if available
                if self.profile_config.get('system_prompt'):
                    full_prompt = f"{self.profile_config['system_prompt']}\n\n{full_prompt}"
            
            # Send async SPAWN command using JSON protocol
            model = self.profile_config.get('model', 'sonnet')
            result = await self._send_spawn_command("async", self.session_id, model, self.agent_id, full_prompt)
            
            if not result:
                logger.error("No response from daemon")
                return None
            
            if result.get('status') == 'error':
                logger.error(f"Daemon error: {result.get('error', {}).get('message', 'Unknown error')}")
                return None
            
            # SPAWN async returns process_id immediately
            result_data = result.get('result', {})
            process_id = result_data.get('process_id')
            if not process_id:
                logger.error(f"No process_id in daemon response: {result}")
                return None
                
            logger.info(f"Started async Claude process {process_id}")
            
            # Track pending process
            self.pending_processes[process_id] = {
                'conversation_id': conversation_id,
                'from_agent': from_agent,
                'started_at': TimestampManager.timestamp_utc()
            }
            
            return process_id
                
        except Exception as e:
            logger.error(f"Error starting Claude response: {e}", exc_info=True)
            return None
    
    async def generate_claude_response(self, prompt: str, conversation_id: str) -> Optional[str]:
        """Generate response using daemon SPAWN command synchronously (for backward compatibility)"""
        # This method is kept for task assignments that need synchronous responses
        try:
            # Get daemon commands dynamically
            daemon_commands = await self.get_daemon_commands()
            
            # Use agent role from profile for conversation patterns
            agent_role = self.profile_config.get('role', 'responder')
            
            # Build context for prompt composer
            context = {
                'agent_id': self.agent_id,
                'agent_role': agent_role,
                'conversation_id': conversation_id,
                'daemon_commands': daemon_commands,
                'user_prompt': prompt,
                'conversation_history': self._build_conversation_context(conversation_id),
                'enable_tools': self.profile_config.get('enable_tools', True)
            }
            
            # Use composition from profile or default
            composition_name = self.profile_config.get('composition', 'claude_agent_default')
            
            # Compose the full prompt
            try:
                logger.info(f"Composing prompt with {composition_name}, context keys: {list(context.keys())}")
                full_prompt = self.prompt_composer.compose(composition_name, context)
                logger.info(f"Successfully composed prompt ({len(full_prompt)} chars)")
            except (FileNotFoundError, ValueError, Exception) as e:
                if isinstance(e, FileNotFoundError):
                    logger.warning(f"Composition error: {e}\nFalling back to legacy prompt")
                elif isinstance(e, ValueError):
                    logger.error(f"Context validation error: {e}\nFalling back to legacy prompt")
                else:
                    logger.error(f"Unexpected composition error: {e}\nFalling back to legacy prompt")
                
                # Fallback to legacy prompt construction
                logger.info("Using legacy prompt construction as fallback")
                context_str = self._build_conversation_context(conversation_id)
                if context_str:
                    full_prompt = f"{context_str}\n\nRespond to: {prompt}"
                else:
                    full_prompt = prompt
                
                # Add role-specific instructions if available
                if self.profile_config.get('system_prompt'):
                    full_prompt = f"{self.profile_config['system_prompt']}\n\n{full_prompt}"
            
            # Send sync SPAWN command using JSON protocol
            model = self.profile_config.get('model', 'sonnet')
            result = await self._send_spawn_command("sync", self.session_id, model, self.agent_id, full_prompt)
            
            if not result:
                return None
            
            if result.get('status') == 'error':
                logger.error(f"Daemon error: {result.get('error', {}).get('message', 'Unknown error')}")
                return None
            
            # Extract response and session_id from JSON daemon result
            result_data = result.get('result', {})
            if result_data:
                # Store session_id for future use
                if result_data.get('sessionId'):
                    self.session_id = result_data['sessionId']
                elif result_data.get('session_id'):
                    self.session_id = result_data['session_id']
                
                # Extract the Claude response
                if result_data.get('result'):
                    return result_data['result'].strip()
                elif result_data.get('content'):
                    return result_data['content'].strip()
                else:
                    logger.error(f"No result content in daemon response: {result}")
                    return None
            else:
                logger.error(f"No result data in daemon response: {result}")
                return None
                
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
            
            # Build JSON PUBLISH command using shared utilities
            cmd_obj = CommandBuilder.build_publish_command(self.agent_id, "DIRECT_MESSAGE", message)
            
            command_str = json.dumps(cmd_obj) + '\n'
            cmd_writer.write(command_str.encode())
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
                    'from': self.agent_id,
                    'content': content,
                    'timestamp': TimestampManager.timestamp_utc()
                })
                
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
    
    async def start_conversation(self, with_agents: List[str], topic: str):
        """Start a new conversation with other agents"""
        conversation_id = f"conv_{self.agent_id}_{TimestampManager.utc_now().timestamp()}"
        
        # Initialize conversation
        self.active_conversations[conversation_id] = {
            'participants': [self.agent_id] + with_agents,
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
                    'initiator': self.agent_id
                }
                
                # Use separate connection for sending command
                cmd_reader, cmd_writer = await asyncio.open_unix_connection(self.daemon_socket)
                
                # Build JSON PUBLISH command using shared utilities
                cmd_obj = CommandBuilder.build_publish_command(self.agent_id, "CONVERSATION_INVITE", invite)
                
                command_str = json.dumps(cmd_obj) + '\n'
                cmd_writer.write(command_str.encode())
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
            'participants': [initiator, self.agent_id],
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
    
    async def handle_process_complete(self, message: Dict):
        """Handle process completion notification"""
        # Message bus spreads payload directly into message
        process_id = message.get('process_id')
        status = message.get('status')
        
        logger.info(f"Process {process_id} completed with status: {status}")
        
        # Find pending process
        if process_id not in self.pending_processes:
            logger.warning(f"Received completion for unknown process {process_id}")
            return
        
        pending_info = self.pending_processes.pop(process_id)
        conversation_id = pending_info['conversation_id']
        from_agent = pending_info['from_agent']
        
        if status == 'success':
            # Update session_id if provided
            if message.get('session_id'):
                self.session_id = message['session_id']
            
            # Get the result
            response = message.get('result', '').strip()
            
            if response:
                # Check control signals
                if self._should_send_response(response):
                    # Remove control signals before sending
                    clean_response, _ = self._extract_control_signals(response)
                    await self.send_message(from_agent, clean_response, conversation_id)
                else:
                    logger.info("Response contains NO_RESPONSE signal, not sending")
                
                # Check if we should terminate
                if self._should_terminate(response):
                    logger.info(f"Agent {self.agent_id} received termination signal [END], shutting down")
                    self.running = False
                    # Force immediate disconnect to exit cleanly
                    asyncio.create_task(self._delayed_shutdown())
        else:
            # Process failed
            error = message.get('error', 'Unknown error')
            logger.error(f"Process {process_id} failed: {error}")
            # Could send error message to other agent
    
    async def _delayed_shutdown(self):
        """Delayed shutdown to ensure clean exit after [END] signal"""
        await asyncio.sleep(0.5)  # Brief delay to ensure message is sent
        logger.info(f"Agent {self.agent_id} terminating process")
        # Exit the entire process
        import os
        os._exit(0)
    
    async def disconnect(self):
        """Disconnect from daemon"""
        if self.writer:
            try:
                # Build JSON AGENT_CONNECTION disconnect command using shared utilities
                cmd_obj = CommandBuilder.build_agent_connection_command("disconnect", self.agent_id)
                
                command_str = json.dumps(cmd_obj) + '\n'
                self.writer.write(command_str.encode())
                await self.writer.drain()
                
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
        
        self.running = False
        logger.info(f"Agent {self.agent_id} disconnected")
    
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
    parser = argparse.ArgumentParser(description='Agent Process - Persistent Claude agent')
    parser.add_argument('--id', required=True, help='Unique agent ID')
    parser.add_argument('--profile', default='default', help='Agent profile to use')
    parser.add_argument('--socket', default='sockets/claude_daemon.sock', help='Daemon socket path')
    parser.add_argument('--start-conversation', action='store_true', help='Start a conversation with other nodes')
    parser.add_argument('--with-agents', nargs='+', help='Agents to converse with')
    parser.add_argument('--topic', help='Conversation topic')
    
    args = parser.parse_args()
    
    # Create and run agent
    agent = AgentProcess(args.id, args.profile, args.socket)
    
    if args.start_conversation and args.with_agents and args.topic:
        # Start conversation mode
        await agent.connect()
        conversation_id = await agent.start_conversation(args.with_agents, args.topic)
        logger.info(f"Started conversation {conversation_id}")
        await agent.listen_for_messages()
    else:
        # Just run as listener
        await agent.run()


if __name__ == '__main__':
    asyncio.run(main())