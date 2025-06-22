#!/usr/bin/env python3

"""
Claude Process Manager - Process spawning and management
Extracted from daemon_clean.py with 100% functionality preservation
"""

import asyncio
import json
import os
import sys
from pathlib import Path
import logging

from .timestamp_utils import TimestampManager

logger = logging.getLogger('daemon')

class ClaudeProcessManager:
    """Manages Claude process spawning and lifecycle"""
    
    def __init__(self, state_manager=None, utils_manager=None):
        self.running_processes = {}  # process_id -> process_info
        self.state_manager = state_manager
        self.utils_manager = utils_manager
        self.message_bus = None  # Will be set via set_message_bus()
    
    async def spawn_claude(self, prompt: str, session_id: str = None, model: str = 'sonnet', agent_id: str = None, enable_tools: bool = True) -> dict:
        """Spawn claude process and capture output - EXACT copy from daemon_clean.py"""
        # Ensure directories exist
        os.makedirs('claude_logs', exist_ok=True)
        os.makedirs('sockets', exist_ok=True)
        os.makedirs('shared_state', exist_ok=True)
        os.makedirs('agent_profiles', exist_ok=True)
        
        # Build command
        cmd = [
            'claude',
            '--model', model,
            '--print',
            '--output-format', 'json'
        ]
        
        # Only add tools if explicitly enabled (for conversation patterns, we don't want tools)
        if enable_tools:
            cmd.extend(['--allowedTools', 'Task Bash Glob Grep LS Read Edit MultiEdit Write WebFetch WebSearch'])
        
        if session_id:
            cmd.extend(['--resume', session_id])
        
        try:
            # Execute claude with prompt as stdin - explicitly inherit environment and set cwd
            # Use the directory where daemon was started (project root)
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ,
                cwd=project_root  # Ensure Claude CLI runs from project root
            )
        except FileNotFoundError as e:
            logger.error(f"Claude executable not found: {e}")
            return {'error': 'claude executable not found in PATH', 'details': str(e)}
        except Exception as e:
            logger.error(f"Failed to spawn Claude process: {e}")
            return {'error': f'Failed to spawn process: {type(e).__name__}', 'details': str(e)}
        
        # Send prompt and get output
        stdout, stderr = await process.communicate(prompt.encode())
        
        # Log stderr if present
        if stderr:
            stderr_text = stderr.decode()
            logger.warning(f"Claude stderr output: {stderr_text}")
        
        # Parse output
        try:
            if not stdout:
                error_response = {
                    'error': 'No output from claude',
                    'returncode': process.returncode
                }
                if stderr:
                    error_response['stderr'] = stderr.decode()
                return error_response
            
            # Parse JSON output
            output = json.loads(stdout.decode())
            
            # Add stderr to output if present (for debugging)
            if stderr:
                output['stderr'] = stderr.decode()
            
            # Save to file for debugging/reference
            output_file = 'sockets/claude_last_output.json'
            with open(output_file, 'w') as f:
                json.dump(output, f, indent=2)
            
            # Extract session_id
            new_session_id = output.get('sessionId') or output.get('session_id')
            
            # Log to JSONL
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
                    
                # Update session tracking
                if self.state_manager:
                    self.state_manager.track_session(new_session_id, output)
                
                # Update latest symlink
                latest_link = 'claude_logs/latest.jsonl'
                if os.path.exists(latest_link):
                    os.unlink(latest_link)
                os.symlink(f'{new_session_id}.jsonl', latest_link)
                
                # Save session ID for easy resumption
                session_file = 'sockets/last_session_id'
                with open(session_file, 'w') as f:
                    f.write(new_session_id)
            
            # Call cognitive observer if loaded
            if self.utils_manager and hasattr(self.utils_manager, 'loaded_module') and self.utils_manager.loaded_module:
                if hasattr(self.utils_manager.loaded_module, 'handle_output'):
                    self.utils_manager.loaded_module.handle_output(output, self)
            
            return output
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            logger.error(f"Raw stdout: {stdout.decode()[:500]}...")  # First 500 chars
            if stderr:
                logger.error(f"Raw stderr: {stderr.decode()}")
            
            error_response = {
                'error': f'Invalid JSON from claude: {str(e)}',
                'returncode': process.returncode,
                'raw_stdout': stdout.decode()[:1000]  # Include partial stdout for debugging
            }
            if stderr:
                error_response['stderr'] = stderr.decode()
            return error_response
            
        except Exception as e:
            logger.error(f"Unexpected error in spawn_claude: {type(e).__name__}: {str(e)}")
            return {'error': f'{type(e).__name__}: {str(e)}', 'returncode': -1}
    
    async def spawn_claude_async(self, prompt: str, session_id: str = None, model: str = 'sonnet', agent_id: str = None, enable_tools: bool = True) -> str:
        """Spawn claude process asynchronously and return process_id immediately - EXACT copy from daemon_clean.py"""
        import uuid
        process_id = str(uuid.uuid4())[:8]  # Short ID for tracking
        
        # Ensure directories exist
        os.makedirs('claude_logs', exist_ok=True)
        os.makedirs('sockets', exist_ok=True)
        os.makedirs('shared_state', exist_ok=True)
        os.makedirs('agent_profiles', exist_ok=True)
        
        # Build command
        cmd = [
            'claude',
            '--model', model,
            '--print',
            '--output-format', 'json'
        ]
        
        # Only add tools if explicitly enabled (for conversation patterns, we don't want tools)
        if enable_tools:
            cmd.extend(['--allowedTools', 'Task Bash Glob Grep LS Read Edit MultiEdit Write WebFetch WebSearch'])
        
        if session_id:
            cmd.extend(['--resume', session_id])
        
        try:
            # Execute claude with prompt as stdin
            # Use the directory where daemon was started (project root) 
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ,
                cwd=project_root  # Ensure Claude CLI runs from project root
            )
            
            # Track the running process
            self.running_processes[process_id] = {
                'process': process,
                'prompt': prompt,
                'session_id': session_id,
                'model': model,
                'agent_id': agent_id,
                'started_at': TimestampManager.format_for_logging()
            }
            
            # Send prompt to process (don't wait for completion)
            prompt_bytes = prompt.encode()
            logger.info(f"Sending prompt to Claude: {len(prompt_bytes)} bytes")
            logger.info(f"Prompt starts with: {prompt[:100]!r}")
            logger.info(f"Prompt ends with: {prompt[-100:]!r}")
            
            process.stdin.write(prompt_bytes)
            await process.stdin.drain()  # Ensure data is written
            process.stdin.close()
            
            # Schedule async completion handling
            asyncio.create_task(self._handle_process_completion(process_id))
            
            logger.info(f"Started Claude process {process_id} with model {model}")
            return process_id
            
        except Exception as e:
            logger.error(f"Failed to spawn Claude process: {e}")
            return None
    
    async def _handle_process_completion(self, process_id: str):
        """Handle async completion of a Claude process - EXACT copy from daemon_clean.py"""
        if process_id not in self.running_processes:
            return
            
        process_info = self.running_processes[process_id]
        process = process_info['process']
        prompt = process_info['prompt']
        session_id = process_info['session_id']
        agent_id = process_info['agent_id']
        
        try:
            # Wait for process to complete
            stdout, stderr = await process.communicate()
            
            # Log stderr if present
            if stderr:
                stderr_text = stderr.decode()
                logger.warning(f"Claude process {process_id} stderr: {stderr_text}")
            
            # Parse and log output
            if stdout:
                try:
                    output = json.loads(stdout.decode())
                    
                    # Add process tracking info
                    output['process_id'] = process_id
                    output['agent_id'] = agent_id
                    
                    # Extract session_id
                    new_session_id = output.get('sessionId') or output.get('session_id')
                    
                    # Log to JSONL
                    if new_session_id:
                        log_file = f'claude_logs/{new_session_id}.jsonl'
                        
                        # Log human input
                        human_entry = {
                            "timestamp": TimestampManager.format_for_logging(),
                            "type": "human",
                            "content": prompt,
                            "process_id": process_id,
                            "agent_id": agent_id
                        }
                        with open(log_file, 'a') as f:
                            f.write(json.dumps(human_entry) + '\n')
                        
                        # Log Claude output
                        claude_entry = output.copy()
                        claude_entry["timestamp"] = TimestampManager.format_for_logging()
                        claude_entry["type"] = "claude"
                        with open(log_file, 'a') as f:
                            f.write(json.dumps(claude_entry) + '\n')
                            
                        # Update session tracking
                        if self.state_manager:
                            self.state_manager.track_session(new_session_id, output)
                        
                        # Update agent registry if agent_id provided (delegated to agent_manager if available)
                        if agent_id and hasattr(self, 'agent_manager') and self.agent_manager:
                            self.agent_manager.update_agent_session(agent_id, new_session_id)
                        
                        # Call cognitive observer if loaded
                        if self.utils_manager and hasattr(self.utils_manager, 'loaded_module') and self.utils_manager.loaded_module:
                            if hasattr(self.utils_manager.loaded_module, 'handle_output'):
                                self.utils_manager.loaded_module.handle_output(output, self)
                    
                    # Notify the agent via message bus if available
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
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Process {process_id} JSON decode error: {e}")
                    # Notify agent of error
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
            else:
                logger.error(f"Process {process_id} produced no output")
                # Notify agent of error
                if agent_id and hasattr(self, 'message_bus') and self.message_bus:
                    await self.message_bus.publish(
                        from_agent='daemon',
                        event_type='PROCESS_COMPLETE',
                        payload={
                            'process_id': process_id,
                            'agent_id': agent_id,
                            'status': 'error',
                            'error': 'No output produced'
                        }
                    )
                
        except Exception as e:
            logger.error(f"Error handling process {process_id} completion: {e}")
        finally:
            # Clean up tracking
            if process_id in self.running_processes:
                del self.running_processes[process_id]
    
    def get_running_processes(self) -> dict:
        """Get running processes status - EXACT copy from daemon_clean.py"""
        processes = {}
        for pid, info in self.running_processes.items():
            processes[pid] = {
                'agent_id': info['agent_id'],
                'model': info['model'],
                'started_at': info['started_at'],
                'session_id': info['session_id']
            }
        return processes
    
    def set_agent_manager(self, agent_manager):
        """Set agent manager for cross-module communication"""
        self.agent_manager = agent_manager
    
    def set_message_bus(self, message_bus):
        """Set message bus for process completion notifications"""
        self.message_bus = message_bus
    
    async def spawn_agent_process_async(self, agent_id: str, profile_name: str) -> str:
        """Spawn agent process (agent_process.py) for message-bus-aware agents"""
        import uuid
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
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ
            )
            
            # Track the running process
            self.running_processes[process_id] = {
                'process': process,
                'type': 'agent_process',
                'agent_id': agent_id,
                'profile': profile_name,
                'started_at': TimestampManager.format_for_logging()
            }
            
            # Monitor for completion
            asyncio.create_task(self._handle_agent_process_completion(process_id))
            
            logger.info(f"Started agent process {process_id} for agent {agent_id}")
            return process_id
            
        except Exception as e:
            logger.error(f"Failed to spawn agent process: {e}", exc_info=True)
            return None
    
    async def _handle_agent_process_completion(self, process_id: str):
        """Handle completion of an agent process"""
        if process_id not in self.running_processes:
            return
            
        process_info = self.running_processes[process_id]
        process = process_info['process']
        agent_id = process_info['agent_id']
        
        try:
            # Wait for process to complete
            stdout, stderr = await process.communicate()
            
            logger.info(f"Agent {agent_id} (process {process_id}) completed with code {process.returncode}")
            
            if stderr:
                logger.error(f"Agent {agent_id} stderr: {stderr.decode()}")
            
            # Clean up
            del self.running_processes[process_id]
            
            # Notify via message bus if available
            if self.message_bus:
                await self.message_bus.publish(
                    from_agent='daemon',
                    event_type='AGENT_TERMINATED',
                    payload={
                        'process_id': process_id,
                        'agent_id': agent_id,
                        'returncode': process.returncode,
                        'terminated_at': TimestampManager.format_for_logging()
                    }
                )
                
        except Exception as e:
            logger.error(f"Error handling node completion: {e}", exc_info=True)
            # Clean up even on error
            if process_id in self.running_processes:
                del self.running_processes[process_id]
    
