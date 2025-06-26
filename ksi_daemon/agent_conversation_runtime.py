#!/usr/bin/env python3
"""
AgentConversationRuntime - In-process runtime for agent conversations
Manages conversation threads with LLMs for efficient multi-agent orchestration
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List
from .config import config

import litellm
from ksi_common import TimestampManager

# Add path for prompt composer  
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prompts.composer import PromptComposer
from prompts.composition_selector import CompositionSelector, SelectionContext

logger = logging.getLogger('daemon')

class AgentConversationRuntime:
    """In-process runtime that manages an LLM conversation thread"""
    
    def __init__(
        self,
        agent_id: str,
        profile_name: str,
        message_bus,
        state_manager=None,
        orchestrator=None
    ):
        self.agent_id = agent_id
        self.profile_name = profile_name
        self.message_bus = message_bus
        self.state_manager = state_manager
        self.orchestrator = orchestrator
        
        # Agent state
        self.session_id: Optional[str] = None
        self.profile: Optional[Dict] = None
        self.is_running = False
        self.message_queue = asyncio.Queue()
        
        # Conversation state
        self.conversation_history = []
        self.last_response = None
        
        logger.info(f"Initialized AgentController {agent_id} with profile {profile_name}")
    
    async def start(self):
        """Start the agent controller"""
        try:
            # Load agent profile
            await self._load_profile()
            
            # Start message processing loop
            self.is_running = True
            logger.info(f"Starting agent {self.agent_id}")
            
            # Start async tasks
            message_task = asyncio.create_task(self._message_processing_loop())
            
            # Return the task so orchestrator can track it
            return message_task
            
        except Exception as e:
            logger.error(f"Failed to start agent {self.agent_id}: {e}")
            raise
    
    async def stop(self):
        """Stop the agent controller"""
        self.is_running = False
        logger.info(f"Stopping agent {self.agent_id}")
    
    async def _load_profile(self):
        """Load agent profile from JSON file"""
        profile_file = config.agent_profiles_dir / f"{self.profile_name}.json"
        
        if not profile_file.exists():
            raise FileNotFoundError(f"Agent profile not found: {profile_file}")
        
        with open(profile_file, 'r') as f:
            self.profile = json.load(f)
        
        logger.info(f"Loaded profile {self.profile_name} for agent {self.agent_id}")
    
    async def _message_processing_loop(self):
        """Main message processing loop"""
        try:
            while self.is_running:
                try:
                    # Wait for messages with timeout
                    message = await asyncio.wait_for(
                        self.message_queue.get(), 
                        timeout=1.0
                    )
                    await self._process_message(message)
                except asyncio.TimeoutError:
                    # Continue loop on timeout (allows checking is_running)
                    continue
                except Exception as e:
                    logger.error(f"Error processing message in agent {self.agent_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Message processing loop failed for agent {self.agent_id}: {e}")
        finally:
            logger.info(f"Message processing loop ended for agent {self.agent_id}")
    
    async def _process_message(self, message: Dict[str, Any]):
        """Process incoming message and generate Claude response"""
        try:
            event_type = message.get('type')
            content = message.get('content', '')
            from_agent = message.get('from')
            
            logger.info(f"Agent {self.agent_id} processing {event_type} from {from_agent}")
            
            # Build prompt using agent profile and message context
            prompt = await self._build_prompt(message)
            
            # Call Claude via LiteLLM
            response = await self._call_claude(prompt)
            
            # Store in conversation history
            self.conversation_history.append({
                'timestamp': TimestampManager.format_for_logging(),
                'input_message': message,
                'prompt': prompt,
                'response': response
            })
            
            # Extract response content
            response_content = self._extract_response_content(response)
            self.last_response = response_content
            
            # Publish response via message bus
            await self._publish_response(message, response_content)
            
        except Exception as e:
            logger.error(f"Error processing message in agent {self.agent_id}: {e}")
            # Send error response
            await self._publish_error_response(message, str(e))
    
    async def _process_prompt(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process a prompt message and return response directly (for sync mode)"""
        try:
            # Build prompt using agent profile and message context
            prompt = await self._build_prompt(message)
            
            # Call Claude via LiteLLM
            response = await self._call_claude(prompt)
            
            # Store in conversation history
            self.conversation_history.append({
                'timestamp': TimestampManager.format_for_logging(),
                'input_message': message,
                'prompt': prompt,
                'response': response
            })
            
            # Extract response content
            response_content = self._extract_response_content(response)
            self.last_response = response_content
            
            # Return the full Claude response for sync mode
            if hasattr(response, '_claude_metadata') and isinstance(response._claude_metadata, dict):
                return response._claude_metadata
            
            # Build response dict
            return {
                'result': response_content,
                'session_id': self.session_id,
                'agent_id': self.agent_id,
                'model': self.profile.get('model', 'sonnet')
            }
            
        except Exception as e:
            logger.error(f"Error processing prompt in agent {self.agent_id}: {e}")
            return {
                'error': str(e),
                'agent_id': self.agent_id
            }
    
    async def _build_prompt(self, message: Dict[str, Any]) -> str:
        """Build Claude prompt using agent profile and message context"""
        try:
            # Use prompt composer for sophisticated prompt building
            composer = PromptComposer()
            
            # Try to select appropriate composition based on context
            selector = CompositionSelector()
            context = SelectionContext(
                user_prompt=message.get('content', ''),
                conversation_history=self.conversation_history[-5:] if self.conversation_history else [],
                agent_role=self.profile.get('role', 'assistant'),
                available_tools=self.profile.get('allowed_tools', [])
            )
            
            # Select composition (fallback to simple format if none found)
            try:
                composition = await selector.select_composition(context)
                prompt = composer.compose(composition, context)
            except Exception:
                # Fallback to simple prompt building
                prompt = self._build_simple_prompt(message)
                
            return prompt
            
        except Exception as e:
            logger.warning(f"Error building sophisticated prompt for agent {self.agent_id}: {e}, using fallback")
            return self._build_simple_prompt(message)
    
    def _build_simple_prompt(self, message: Dict[str, Any]) -> str:
        """Build simple prompt as fallback"""
        system_prompt = self.profile.get('system_prompt', 'You are a helpful assistant.')
        user_content = message.get('content', '')
        
        # Add context from conversation history if available
        context = ""
        if self.conversation_history:
            recent_exchanges = self.conversation_history[-3:]  # Last 3 exchanges
            context = "\\n\\nRecent conversation context:\\n"
            for exchange in recent_exchanges:
                context += f"Input: {exchange.get('input_message', {}).get('content', 'N/A')}\\n"
                context += f"Response: {exchange.get('response_content', 'N/A')}\\n\\n"
        
        return f"{system_prompt}\\n\\n{context}User message: {user_content}"
    
    async def _call_claude(self, prompt: str) -> Dict[str, Any]:
        """Call Claude via LiteLLM with agent's session continuity"""
        try:
            # Prepare LiteLLM call
            model = self.profile.get('model', 'sonnet')
            allowed_tools = self.profile.get('allowed_tools', [])
            
            kwargs = {
                'model': f'claude-cli/{model}',
                'messages': [{'role': 'user', 'content': prompt}]
            }
            
            # Add session continuity
            if self.session_id:
                kwargs['session_id'] = self.session_id
            
            # Add tools if specified
            if allowed_tools:
                kwargs['tools'] = [
                    {'type': 'function', 'function': {'name': tool}}
                    for tool in allowed_tools
                ]
            else:
                # Disable tools by default for agent conversations
                kwargs['disallowed_tools'] = ['Bash', 'Read', 'Edit', 'Write', 'WebFetch', 'WebSearch', 'Task', 'Glob', 'Grep', 'LS', 'MultiEdit']
            
            # Call Claude via LiteLLM
            response = await litellm.acompletion(**kwargs)
            
            # Extract session ID for continuity
            if hasattr(response, 'sessionId'):
                self.session_id = response.sessionId
            elif hasattr(response, '_claude_metadata'):
                metadata = response._claude_metadata
                if isinstance(metadata, dict):
                    self.session_id = metadata.get('sessionId') or metadata.get('session_id')
            
            # Log the interaction
            self._log_claude_interaction(prompt, response)
            
            return response
            
        except Exception as e:
            logger.error(f"Claude call failed for agent {self.agent_id}: {e}")
            raise
    
    def _extract_response_content(self, response) -> str:
        """Extract text content from Claude response"""
        try:
            if hasattr(response, '_claude_metadata') and response._claude_metadata:
                # Extract from Claude metadata
                metadata = response._claude_metadata
                if isinstance(metadata, dict):
                    message = metadata.get('message', {})
                    content = message.get('content', [])
                    if content and isinstance(content, list):
                        return ''.join(seg.get('text', '') for seg in content if isinstance(seg, dict))
                    elif 'result' in metadata:
                        return str(metadata['result'])
            
            # Fallback to LiteLLM response format
            if hasattr(response, 'choices') and response.choices:
                return response.choices[0].message.content
            
            return str(response)
            
        except Exception as e:
            logger.error(f"Error extracting response content: {e}")
            return "Error processing response"
    
    def _log_claude_interaction(self, prompt: str, response):
        """Log Claude interaction to JSONL if session ID available"""
        if not self.session_id:
            return
            
        try:
            log_file = str(config.session_log_dir / f"{self.session_id}.jsonl")
            
            # Log human input
            human_entry = {
                'timestamp': TimestampManager.format_for_logging(),
                'type': 'human',
                'content': prompt,
                'agent_id': self.agent_id,
                'profile': self.profile_name
            }
            
            with open(log_file, 'a') as f:
                f.write(json.dumps(human_entry) + '\\n')
            
            # Log Claude response
            if hasattr(response, '_claude_metadata') and response._claude_metadata:
                claude_entry = response._claude_metadata.copy()
                claude_entry['timestamp'] = TimestampManager.format_for_logging()
                claude_entry['type'] = 'claude'
                claude_entry['agent_id'] = self.agent_id
                
                with open(log_file, 'a') as f:
                    f.write(json.dumps(claude_entry) + '\\n')
                    
        except Exception as e:
            logger.warning(f"Failed to log Claude interaction for agent {self.agent_id}: {e}")
    
    async def _publish_response(self, original_message: Dict[str, Any], response_content: str):
        """Publish agent response via message bus"""
        try:
            # Determine response event type based on original message
            original_type = original_message.get('type', 'MESSAGE')
            
            if original_type == 'DEBATE_OPENING':
                event_type = 'DEBATE_RESPONSE'
            elif original_type == 'DEBATE_RESPONSE':
                event_type = 'DEBATE_COUNTER'
            elif original_type == 'COLLABORATION_REQUEST':
                event_type = 'COLLABORATION_RESPONSE'
            else:
                event_type = 'AGENT_RESPONSE'
            
            # Publish via simplified message bus interface
            await self._simple_publish(
                event_type=event_type,
                payload={
                    'content': response_content,
                    'responding_to': original_message.get('from'),
                    'session_id': self.session_id,
                    'profile': self.profile_name
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to publish response from agent {self.agent_id}: {e}")
    
    async def _publish_error_response(self, original_message: Dict[str, Any], error: str):
        """Publish error response"""
        await self._simple_publish(
            event_type='AGENT_ERROR',
            payload={
                'error': error,
                'responding_to': original_message.get('from'),
                'original_message': original_message
            }
        )
    
    async def _simple_publish(self, event_type: str, payload: Dict[str, Any]):
        """Simplified message bus publish for in-process agents"""
        try:
            # For in-process agents, we'll add a simple interface to the message bus
            if hasattr(self.message_bus, 'publish_simple'):
                await self.message_bus.publish_simple(
                    from_agent=self.agent_id,
                    event_type=event_type,
                    payload=payload
                )
            else:
                # Fallback: direct orchestrator notification
                if self.orchestrator:
                    await self.orchestrator.handle_agent_message(
                        from_agent=self.agent_id,
                        event_type=event_type,
                        payload=payload
                    )
                    
        except Exception as e:
            logger.error(f"Failed to publish message from agent {self.agent_id}: {e}")
    
    # Public interface methods
    
    async def send_message(self, message: Dict[str, Any]):
        """Send message to agent for processing"""
        await self.message_queue.put(message)
    
    async def send_prompt(self, prompt: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Send prompt and wait for response (synchronous)"""
        # Override session_id if provided
        if session_id:
            self.session_id = session_id
        
        # Create message
        message = {
            'type': 'PROMPT',
            'content': prompt,
            'session_id': session_id,
            'timestamp': TimestampManager.format_for_logging()
        }
        
        # Process directly (synchronous)
        response = await self._process_prompt(message)
        
        # Return the Claude response data
        if isinstance(response, dict):
            return response
        elif hasattr(response, '_claude_metadata'):
            # Extract metadata from LiteLLM response
            metadata = response._claude_metadata
            if isinstance(metadata, dict):
                return metadata
        
        # Fallback - return basic response
        return {
            'result': str(response),
            'session_id': self.session_id,
            'agent_id': self.agent_id
        }
    
    async def queue_prompt(self, prompt: str, session_id: Optional[str], message_id: str):
        """Queue prompt for async processing"""
        message = {
            'type': 'PROMPT',
            'content': prompt,
            'session_id': session_id,
            'message_id': message_id,
            'timestamp': TimestampManager.format_for_logging()
        }
        await self.message_queue.put(message)
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status"""
        return {
            'agent_id': self.agent_id,
            'profile': self.profile_name,
            'session_id': self.session_id,
            'is_running': self.is_running,
            'conversation_length': len(self.conversation_history),
            'last_response_preview': self.last_response[:100] if self.last_response else None
        }