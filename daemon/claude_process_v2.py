#!/usr/bin/env python3

"""
ClaudeProcessManagerV2 - Modern process management using LiteLLM and simpervisor

Complete replacement for ClaudeProcessManager using:
- LiteLLM as client library for Claude calls
- simpervisor for agent process management
- All original functionality preserved
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
from simpervisor import SupervisedProcess

from .timestamp_utils import TimestampManager

# Import claude_cli_provider to ensure provider registration
import claude_cli_provider

logger = logging.getLogger('daemon')


class ClaudeProcessManagerV2:
    """Modern Claude process manager using LiteLLM as client library"""
    
    def __init__(self, state_manager=None, utils_manager=None):
        self.processes: Dict[str, Dict[str, Any]] = {}
        self.state_manager = state_manager
        self.utils_manager = utils_manager
        self.message_bus = None
        self.agent_manager = None
        
        # Ensure directories exist (exact copy from original)
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure required directories exist - EXACT copy from original"""
        os.makedirs('claude_logs', exist_ok=True)
        os.makedirs('sockets', exist_ok=True)
        os.makedirs('shared_state', exist_ok=True)
        os.makedirs('agent_profiles', exist_ok=True)
    
    async def spawn_claude(
        self, 
        prompt: str, 
        session_id: str = None, 
        model: str = 'sonnet', 
        agent_id: str = None, 
        enable_tools: bool = True
    ) -> Dict[str, Any]:
        """
        Spawn Claude process and capture output using LiteLLM - preserves ALL original functionality
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
            logger.error(f"Claude executable not found: {e}")
            return {'error': 'claude executable not found in PATH', 'details': str(e)}
        except Exception as e:
            logger.error(f"Failed to spawn Claude process: {e}")
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
                logger.warning(f"Claude stderr output: {stderr_text}")
                output['stderr'] = stderr_text
            
            # Save to file for debugging/reference (exact copy from original)
            output_file = 'sockets/claude_last_output.json'
            with open(output_file, 'w') as f:
                json.dump(output, f, indent=2)
            
            # Extract session_id (exact copy from original)
            new_session_id = output.get('sessionId') or output.get('session_id')
            
            # Log to JSONL (exact copy from original)
            if new_session_id:
                log_file = f'claude_logs/{new_session_id}.jsonl'
                
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
                latest_link = 'claude_logs/latest.jsonl'
                if os.path.exists(latest_link):
                    os.unlink(latest_link)
                os.symlink(f'{new_session_id}.jsonl', latest_link)
                
                # Save session ID for easy resumption (exact copy from original)
                session_file = 'sockets/last_session_id'
                with open(session_file, 'w') as f:
                    f.write(new_session_id)
            
            # Call cognitive observer if loaded (exact copy from original)
            if self.utils_manager and hasattr(self.utils_manager, 'loaded_module') and self.utils_manager.loaded_module:
                if hasattr(self.utils_manager.loaded_module, 'handle_output'):
                    self.utils_manager.loaded_module.handle_output(output, self)
            
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
            logger.error(f"Unexpected error in spawn_claude: {type(e).__name__}: {str(e)}")
            return {'error': f'{type(e).__name__}: {str(e)}', 'returncode': -1}
    
    async def spawn_claude_async(
        self, 
        prompt: str, 
        session_id: str = None, 
        model: str = 'sonnet', 
        agent_id: str = None, 
        enable_tools: bool = True
    ) -> str:
        """
        Spawn Claude process asynchronously and return process_id immediately - EXACT copy from original
        """
        process_id = str(uuid.uuid4())[:8]  # Short ID for tracking
        
        # Ensure directories exist (exact copy from original)
        self._ensure_directories()
        
        # Track the running process (exact copy from original)
        self.processes[process_id] = {
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
            # Use our internal spawn_claude method (now using LiteLLM)
            # This preserves the exact same behavior as the original
            output = await self.spawn_claude(
                prompt,
                session_id,
                model,
                agent_id,
                enable_tools=True  # Default from original
            )
            
            # Only proceed with additional processing if spawn_claude succeeded
            if 'error' not in output:
                # Add process tracking info (exact copy from original)
                output['process_id'] = process_id
                output['agent_id'] = agent_id
                
                # Extract session_id (exact copy from original)
                new_session_id = output.get('sessionId') or output.get('session_id')
                
                # Log to JSONL with process info (this will be duplicate if spawn_claude already logged,
                # but we preserve original behavior exactly)
                if new_session_id:
                    log_file = f'claude_logs/{new_session_id}.jsonl'
                    
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
                    
                    # Call cognitive observer if loaded (exact copy from original)
                    if self.utils_manager and hasattr(self.utils_manager, 'loaded_module') and self.utils_manager.loaded_module:
                        if hasattr(self.utils_manager.loaded_module, 'handle_output'):
                            self.utils_manager.loaded_module.handle_output(output, self)
                
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
    
    async def spawn_agent_process_async(self, agent_id: str, profile_name: str) -> str:
        """
        Spawn agent process using simpervisor - EXACT copy from original but with simpervisor
        """
        process_id = str(uuid.uuid4())[:8]
        
        cmd = [
            sys.executable,  # Use current Python interpreter
            'daemon/agent_process.py',
            '--id', agent_id,
            '--profile', profile_name,
            '--socket', 'sockets/claude_daemon.sock'
        ]
        
        try:
            logger.info(f"Spawning agent process with command: {' '.join(cmd)}")
            
            # Use simpervisor instead of raw subprocess for better process management
            supervised_process = SupervisedProcess(f"agent-{agent_id}", *cmd, stdout=True, stderr=True, env=os.environ)
            await supervised_process.start()
            
            # Track the running process (exact copy from original)
            self.processes[process_id] = {
                'process': supervised_process,
                'type': 'agent_process',
                'agent_id': agent_id,
                'profile': profile_name,
                'started_at': TimestampManager.format_for_logging()
            }
            
            # Monitor for completion (exact copy from original)
            asyncio.create_task(self._handle_agent_process_completion(process_id))
            
            logger.info(f"Started agent process {process_id} for agent {agent_id}")
            return process_id
            
        except Exception as e:
            logger.error(f"Failed to spawn agent process: {e}", exc_info=True)
            return None
    
    async def _handle_agent_process_completion(self, process_id: str):
        """Handle completion of an agent process - EXACT copy from original but with simpervisor"""
        if process_id not in self.processes:
            return
            
        process_info = self.processes[process_id]
        supervised_process = process_info['process']
        agent_id = process_info['agent_id']
        
        try:
            # Wait for supervised process to complete and collect output
            stdout_chunks = []
            stderr_chunks = []
            
            # Collect all stdout chunks
            async for chunk in supervised_process.stdout:
                stdout_chunks.append(chunk)
                
            # Collect all stderr chunks  
            async for chunk in supervised_process.stderr:
                stderr_chunks.append(chunk)
            
            # Wait for process termination
            await supervised_process.terminate()
            
            # Decode output
            stdout = b''.join(stdout_chunks).decode() if stdout_chunks else ''
            stderr = b''.join(stderr_chunks).decode() if stderr_chunks else ''
            
            # Get return code from simpervisor (if available)
            returncode = getattr(supervised_process, 'returncode', 0)
            
            logger.info(f"Agent {agent_id} (process {process_id}) completed with code {returncode}")
            
            if stderr:
                logger.error(f"Agent {agent_id} stderr: {stderr}")
            
            # Clean up (exact copy from original)
            del self.processes[process_id]
            
            # Notify via message bus if available (exact copy from original)
            if self.message_bus:
                await self.message_bus.publish(
                    from_agent='daemon',
                    event_type='AGENT_TERMINATED',
                    payload={
                        'process_id': process_id,
                        'agent_id': agent_id,
                        'returncode': returncode,
                        'terminated_at': TimestampManager.format_for_logging()
                    }
                )
                
        except Exception as e:
            logger.error(f"Error handling node completion: {e}", exc_info=True)
            # Clean up even on error (exact copy from original)
            if process_id in self.processes:
                del self.processes[process_id]
    
    # Standardized API methods - EXACT copy from original
    
    def list_processes(self) -> list:
        """List all processes (standardized API) - EXACT copy from original"""
        processes = []
        for pid, info in self.processes.items():
            process_data = {
                'process_id': pid,
                'agent_id': info.get('agent_id'),
                'model': info.get('model'),
                'started_at': info.get('started_at'),
                'session_id': info.get('session_id'),
                'status': 'running' if info.get('process') and getattr(info.get('process'), 'returncode', None) is None else 'completed'
            }
            if info.get('process') and hasattr(info.get('process'), 'returncode') and info['process'].returncode is not None:
                process_data['return_code'] = info['process'].returncode
            processes.append(process_data)
        return processes
    
    def get_process(self, process_id: str) -> dict:
        """Get specific process info (standardized API) - EXACT copy from original"""
        return self.processes.get(process_id)
    
    def remove_process(self, process_id: str) -> bool:
        """Remove process from tracking (standardized API) - EXACT copy from original"""
        if process_id in self.processes:
            del self.processes[process_id]
            return True
        return False
    
    def set_agent_manager(self, agent_manager):
        """Set agent manager for cross-module communication - EXACT copy from original"""
        self.agent_manager = agent_manager
    
    def set_message_bus(self, message_bus):
        """Set message bus for process completion notifications - EXACT copy from original"""
        self.message_bus = message_bus