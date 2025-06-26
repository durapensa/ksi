#!/usr/bin/env python3

"""
CompletionManager - Modern completion management using LiteLLM and in-process agents

Manages LLM completion requests and agent spawning using:
- LiteLLM as client library for LLM calls  
- In-process agent controllers for efficient orchestration
- All original functionality preserved with better performance
"""

import asyncio
import json
import os
import sys
import uuid
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

import litellm

from ksi_common import TimestampManager
from .agent_orchestrator import AgentOrchestrator
from .config import config
from ksi_common import get_logger, log_event, async_operation_context
from .event_taxonomy import CLAUDE_EVENTS, format_claude_event

# Import claude_cli_litellm_provider to ensure provider registration
import claude_cli_litellm_provider

logger = get_logger(__name__)


class CompletionManager:
    """Modern completion manager using LiteLLM and in-process agents"""
    
    def __init__(self, state_manager=None):
        self.processes: Dict[str, Dict[str, Any]] = {}
        self.state_manager = state_manager
        self.message_bus = None
        self.agent_manager = None
        self.agent_orchestrator = None
        
        # Ensure directories exist (exact copy from original)
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure required directories exist using config system"""
        # Config system handles directory creation via ensure_directories()
        config.ensure_directories()
        # Agent profiles now managed in var/agent_profiles via config
    
    async def create_completion(
        self, 
        prompt: str, 
        session_id: str = None, 
        model: str = 'sonnet', 
        agent_id: str = None, 
        enable_tools: bool = True
    ) -> Dict[str, Any]:
        """
        Create a completion request and wait for response using LiteLLM
        """
        # Ensure directories exist (exact copy from original)
        self._ensure_directories()
        
        try:
            # Prepare LiteLLM call
            messages = [{"role": "user", "content": prompt}]
            kwargs = {
                "model": f"claude-cli/{model}",
                "messages": messages
            }
            
            # Add session resumption if provided
            if session_id:
                kwargs["session_id"] = session_id
            
            # Add tools if enabled (exact copy from original)
            if enable_tools:
                kwargs["tools"] = [
                    {"type": "function", "function": {"name": "Task"}},
                    {"type": "function", "function": {"name": "Bash"}},
                    {"type": "function", "function": {"name": "Glob"}},
                    {"type": "function", "function": {"name": "Grep"}},
                    {"type": "function", "function": {"name": "LS"}},
                    {"type": "function", "function": {"name": "Read"}},
                    {"type": "function", "function": {"name": "Edit"}},
                    {"type": "function", "function": {"name": "MultiEdit"}},
                    {"type": "function", "function": {"name": "Write"}},
                    {"type": "function", "function": {"name": "WebFetch"}},
                    {"type": "function", "function": {"name": "WebSearch"}}
                ]
            
            # Call LiteLLM (which uses claude_cli_provider)
            response = await litellm.acompletion(**kwargs)
            
        except FileNotFoundError as e:
            log_event(logger, "claude.completion_failed",
                     **format_claude_event("claude.completion_failed", session_id,
                                          error="executable_not_found",
                                          error_details=str(e),
                                          model=model))
            return {'error': 'claude executable not found in PATH', 'details': str(e)}
        except Exception as e:
            log_event(logger, "claude.completion_failed",
                     **format_claude_event("claude.completion_failed", session_id,
                                          error=type(e).__name__,
                                          error_details=str(e),
                                          model=model))
            return {'error': f'Failed to spawn process: {type(e).__name__}', 'details': str(e)}
        
        # Extract Claude CLI response from LiteLLM response
        try:
            # Get the full original Claude response from provider metadata
            if hasattr(response, '_claude_metadata'):
                output = response._claude_metadata.copy()
            else:
                # Fallback: construct from LiteLLM response
                content = response.choices[0].message.content
                output = {
                    "result": content,
                    "message": {
                        "content": [{"text": content}]
                    },
                    "type": "assistant"
                }
            
            # Check for stderr in response (if provider captured it)
            if hasattr(response, '_stderr') and response._stderr:
                stderr_text = response._stderr
                log_event(logger, "claude.completion_stderr",
                         **format_claude_event("claude.completion_stderr", session_id,
                                              stderr_content=stderr_text,
                                              model=model))
                output['stderr'] = stderr_text
            
            # Save to file for debugging/reference (exact copy from original)
            output_file = 'sockets/claude_last_output.json'
            with open(output_file, 'w') as f:
                json.dump(output, f, indent=2)
            
            # Extract session_id (exact copy from original)
            new_session_id = output.get('sessionId') or output.get('session_id')
            
            # Log to JSONL (exact copy from original)
            if new_session_id:
                log_file = str(config.response_log_dir / f'{new_session_id}.jsonl')
                
                # Log human input
                human_entry = {
                    "timestamp": TimestampManager.format_for_logging(),
                    "type": "human",
                    "content": prompt
                }
                with open(log_file, 'a') as f:
                    f.write(json.dumps(human_entry) + '\n')
                
                # Log Claude output
                claude_entry = output.copy()
                claude_entry["timestamp"] = TimestampManager.format_for_logging()
                claude_entry["type"] = "claude"
                with open(log_file, 'a') as f:
                    f.write(json.dumps(claude_entry) + '\n')
                    
                # Update session tracking (exact copy from original)
                if self.state_manager:
                    self.state_manager.track_session(new_session_id, output)
                
                # Update latest symlink (exact copy from original)
                latest_link = str(config.response_log_dir / 'latest.jsonl')
                if os.path.exists(latest_link):
                    os.unlink(latest_link)
                os.symlink(f'{new_session_id}.jsonl', latest_link)
                
                # Save session ID for easy resumption (exact copy from original)
                session_file = 'sockets/last_session_id'
                with open(session_file, 'w') as f:
                    f.write(new_session_id)
            
            # TODO: Call cognitive observer if loaded
            # This functionality was in utils_manager which has been removed
            # Consider implementing through extension module system
            
            # Log successful completion
            log_event(logger, "claude.completion_completed",
                     **format_claude_event("claude.completion_completed", new_session_id,
                                          model=model,
                                          agent_id=agent_id,
                                          response_length=len(str(output.get('result', ''))),
                                          has_session_id=bool(new_session_id)))
            
            return output
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            # Try to get raw output for debugging (like original)
            raw_stdout = getattr(response, '_raw_stdout', 'No raw output available')
            if isinstance(raw_stdout, str):
                logger.error(f"Raw stdout: {raw_stdout[:500]}...")  # First 500 chars
            
            error_response = {
                'error': f'Invalid JSON from claude: {str(e)}',
                'returncode': -1,
                'raw_stdout': raw_stdout[:1000] if isinstance(raw_stdout, str) else str(raw_stdout)  # Include partial stdout for debugging
            }
            if hasattr(response, '_stderr'):
                error_response['stderr'] = response._stderr
            return error_response
            
        except Exception as e:
            logger.error(f"Unexpected error in create_completion: {type(e).__name__}: {str(e)}")
            return {'error': f'{type(e).__name__}: {str(e)}', 'returncode': -1}
    
    async def create_completion_async(
        self, 
        prompt: str, 
        session_id: str = None, 
        model: str = 'sonnet', 
        agent_id: str = None, 
        enable_tools: bool = True
    ) -> str:
        """
        Create a completion request asynchronously and return process_id immediately
        """
        process_id = str(uuid.uuid4())[:8]  # Short ID for tracking
        
        # Ensure directories exist (exact copy from original)
        self._ensure_directories()
        
        # Track the running process (exact copy from original)
        self.processes[process_id] = {
            'type': 'claude_direct',  # Direct Claude calls vs agent_controller
            'prompt': prompt,
            'session_id': session_id,
            'model': model,
            'agent_id': agent_id,
            'started_at': TimestampManager.format_for_logging()
        }
        
        # Log prompt info (exact copy from original)
        prompt_bytes = prompt.encode()
        logger.info(f"Sending prompt to Claude: {len(prompt_bytes)} bytes")
        logger.info(f"Prompt starts with: {prompt[:100]!r}")
        logger.info(f"Prompt ends with: {prompt[-100:]!r}")
        
        # Schedule async completion handling (exact copy from original)
        asyncio.create_task(self._handle_process_completion(process_id))
        
        logger.info(f"Started Claude process {process_id} with model {model}")
        return process_id
    
    async def _handle_process_completion(self, process_id: str):
        """Handle async completion of a Claude process - EXACT copy from original"""
        if process_id not in self.processes:
            return
            
        process_info = self.processes[process_id]
        prompt = process_info['prompt']
        session_id = process_info['session_id']
        model = process_info['model']
        agent_id = process_info['agent_id']
        
        try:
            # Use our internal create_completion method (now using LiteLLM)
            # This preserves the exact same behavior as the original
            output = await self.create_completion(
                prompt,
                session_id,
                model,
                agent_id,
                enable_tools=True  # Default from original
            )
            
            # Only proceed with additional processing if create_completion succeeded
            if 'error' not in output:
                # Add process tracking info (exact copy from original)
                output['process_id'] = process_id
                output['agent_id'] = agent_id
                
                # Extract session_id (exact copy from original)
                new_session_id = output.get('sessionId') or output.get('session_id')
                
                # Log to JSONL with process info (this will be duplicate if create_completion already logged,
                # but we preserve original behavior exactly)
                if new_session_id:
                    log_file = str(config.response_log_dir / f'{new_session_id}.jsonl')
                    
                    # Log human input with process info (exact copy from original)
                    human_entry = {
                        "timestamp": TimestampManager.format_for_logging(),
                        "type": "human",
                        "content": prompt,
                        "process_id": process_id,
                        "agent_id": agent_id
                    }
                    with open(log_file, 'a') as f:
                        f.write(json.dumps(human_entry) + '\n')
                    
                    # Log Claude output with timestamp (exact copy from original)
                    claude_entry = output.copy()
                    claude_entry["timestamp"] = TimestampManager.format_for_logging()
                    claude_entry["type"] = "claude"
                    with open(log_file, 'a') as f:
                        f.write(json.dumps(claude_entry) + '\n')
                        
                    # Update session tracking (exact copy from original)
                    if self.state_manager:
                        self.state_manager.track_session(new_session_id, output)
                    
                    # Update agent registry if agent_id provided (exact copy from original)
                    if agent_id and hasattr(self, 'agent_manager') and self.agent_manager:
                        self.agent_manager.update_agent_session(agent_id, new_session_id)
                    
                    # TODO: Call cognitive observer if loaded
                    # This functionality was in utils_manager which has been removed
                    # Consider implementing through extension module system
                
                # Notify the agent via message bus if available (exact copy from original)
                if agent_id and hasattr(self, 'message_bus') and self.message_bus:
                    await self.message_bus.publish(
                        from_agent='daemon',
                        event_type='PROCESS_COMPLETE',
                        payload={
                            'process_id': process_id,
                            'agent_id': agent_id,
                            'session_id': new_session_id,
                            'result': output.get('result', ''),
                            'status': 'success'
                        }
                    )
                
                logger.info(f"Claude process {process_id} completed successfully")
            else:
                # Handle error case (exact copy from original)
                logger.error(f"Process {process_id} produced error: {output.get('error')}")
                # Notify agent of error
                if agent_id and hasattr(self, 'message_bus') and self.message_bus:
                    await self.message_bus.publish(
                        from_agent='daemon',
                        event_type='PROCESS_COMPLETE',
                        payload={
                            'process_id': process_id,
                            'agent_id': agent_id,
                            'status': 'error',
                            'error': output.get('error', 'Unknown error')
                        }
                    )
                
        except Exception as e:
            logger.error(f"Error handling process {process_id} completion: {e}")
            # Notify agent of error (exact copy from original)
            if agent_id and hasattr(self, 'message_bus') and self.message_bus:
                await self.message_bus.publish(
                    from_agent='daemon',
                    event_type='PROCESS_COMPLETE',
                    payload={
                        'process_id': process_id,
                        'agent_id': agent_id,
                        'status': 'error',
                        'error': str(e)
                    }
                )
        finally:
            # Clean up tracking (exact copy from original)
            if process_id in self.processes:
                del self.processes[process_id]
    
    async def spawn_agent(self, agent_id: str, profile_name: str) -> str:
        """
        Spawn in-process agent controller - Efficient replacement for subprocess approach
        """
        try:
            # Ensure orchestrator is initialized
            if not self.agent_orchestrator:
                if self.message_bus:
                    self.agent_orchestrator = AgentOrchestrator(
                        message_bus=self.message_bus,
                        state_manager=self.state_manager
                    )
                else:
                    raise RuntimeError("Cannot spawn agent: no message bus available")
            
            logger.info(f"Spawning in-process agent {agent_id} with profile {profile_name}")
            
            # Use orchestrator to spawn in-process agent
            actual_agent_id = await self.agent_orchestrator.spawn_agent(agent_id, profile_name)
            
            # Generate process_id for compatibility with existing APIs
            process_id = str(uuid.uuid4())[:8]
            
            # Track the agent (compatible with existing process tracking)
            self.processes[process_id] = {
                'type': 'agent_controller',
                'agent_id': actual_agent_id,
                'profile': profile_name,
                'started_at': TimestampManager.format_for_logging(),
                'orchestrator': self.agent_orchestrator
            }
            
            logger.info(f"Started in-process agent {actual_agent_id} with process ID {process_id}")
            
            # Notify via message bus if available
            if self.message_bus:
                asyncio.create_task(self._notify_agent_spawned(process_id, actual_agent_id, profile_name))
            
            return process_id
            
        except Exception as e:
            logger.error(f"Failed to spawn in-process agent: {e}", exc_info=True)
            return None
    
    async def _notify_agent_spawned(self, process_id: str, agent_id: str, profile_name: str):
        """Notify that an in-process agent was spawned"""
        try:
            await self.message_bus.publish_simple(
                from_agent='daemon',
                event_type='AGENT_SPAWNED',
                payload={
                    'process_id': process_id,
                    'agent_id': agent_id,
                    'profile': profile_name,
                    'type': 'agent_controller',
                    'spawned_at': TimestampManager.format_for_logging()
                }
            )
        except Exception as e:
            logger.warning(f"Failed to notify agent spawn: {e}")
    
    async def terminate_agent(self, process_id: str) -> bool:
        """Terminate an in-process agent"""
        try:
            if process_id not in self.processes:
                logger.warning(f"Process {process_id} not found for termination")
                return False
            
            process_info = self.processes[process_id]
            agent_id = process_info['agent_id']
            
            # All processes are now agent_controller type
            if not self.agent_orchestrator:
                logger.error("No orchestrator available for agent termination")
                return False
                
            success = await self.agent_orchestrator.terminate_agent(agent_id)
            if success:
                # Clean up process tracking
                del self.processes[process_id]
                logger.info(f"Terminated in-process agent {agent_id} (process {process_id})")
                return True
            else:
                logger.warning(f"Failed to terminate agent {agent_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error terminating agent process {process_id}: {e}")
            return False
    
    # Standardized API methods for in-process agents
    
    def list_processes(self) -> list:
        """List all in-process agents"""
        processes = []
        
        for pid, info in self.processes.items():
            # Handle both agent_controller and claude_direct types
            process_type = info.get('type')
            if process_type not in ['agent_controller', 'claude_direct']:
                continue
                
            process_data = {
                'process_id': pid,
                'agent_id': info.get('agent_id', 'unknown'),
                'profile': info.get('profile', 'direct_claude'),
                'started_at': info['started_at'],
                'type': process_type
            }
            
            # Get detailed status from orchestrator (only for agent_controller types)
            if process_type == 'agent_controller' and self.agent_orchestrator:
                agent_status = self.agent_orchestrator.get_agent_status(info.get('agent_id'))
                if agent_status:
                    process_data.update({
                        'status': 'running' if agent_status['is_running'] else 'stopped',
                        'session_id': agent_status['session_id'],
                        'conversation_length': agent_status['conversation_length'],
                        'last_response_preview': agent_status['last_response_preview']
                    })
                else:
                    process_data['status'] = 'terminated'
            elif process_type == 'claude_direct':
                # For direct Claude calls, simple status based on whether process exists
                process_data.update({
                    'status': 'running',  # If it's in the dict, it's running
                    'session_id': info.get('session_id'),
                    'conversation_length': 1,  # Direct calls are typically single turn
                    'last_response_preview': 'Direct Claude call'
                })
            else:
                process_data['status'] = 'no_orchestrator'
            
            processes.append(process_data)
        
        return processes
    
    def get_process(self, process_id: str) -> dict:
        """Get specific agent process info with enhanced details"""
        if process_id not in self.processes:
            return None
            
        info = self.processes[process_id].copy()
        
        # Enhance with orchestrator details if available
        if self.agent_orchestrator and info.get('type') == 'agent_controller':
            agent_status = self.agent_orchestrator.get_agent_status(info['agent_id'])
            if agent_status:
                info.update(agent_status)
        
        return info
    
    def remove_process(self, process_id: str) -> bool:
        """Remove agent process from tracking"""
        if process_id in self.processes:
            info = self.processes[process_id]
            
            # If it's an agent_controller, also clean up from orchestrator
            if info.get('type') == 'agent_controller' and self.agent_orchestrator:
                agent_id = info['agent_id']
                # Note: This only removes from tracking, doesn't terminate the agent
                # Use terminate_agent() for proper termination
                logger.info(f"Removing agent {agent_id} from process tracking")
            
            del self.processes[process_id]
            return True
        return False
    
    def set_agent_manager(self, agent_manager):
        """Set agent manager for cross-module communication"""
        self.agent_manager = agent_manager
    
    def set_message_bus(self, message_bus):
        """Set message bus and initialize multi-agent orchestrator"""
        self.message_bus = message_bus
        
        # Initialize multi-agent orchestrator when message bus is available
        if self.message_bus and not self.agent_orchestrator:
            self.agent_orchestrator = AgentOrchestrator(
                message_bus=self.message_bus,
                state_manager=self.state_manager
            )
    
    # Additional agent-specific API methods
    
    def get_orchestrator_stats(self) -> dict:
        """Get multi-agent orchestrator statistics"""
        if self.agent_orchestrator:
            return self.agent_orchestrator.get_orchestrator_stats()
        return {'error': 'No orchestrator available'}
    
    async def send_agent_message(self, agent_id: str, message: dict) -> bool:
        """Send message to specific agent"""
        if self.agent_orchestrator:
            return await self.agent_orchestrator.send_message_to_agent(agent_id, message)
        return False
    
    async def broadcast_to_agents(self, message: dict, exclude_agent: str = None) -> int:
        """Broadcast message to all agents"""
        if self.agent_orchestrator:
            return await self.agent_orchestrator.broadcast_message(message, exclude_agent)
        return 0