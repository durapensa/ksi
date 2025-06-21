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
        self.temporal_debugger = None  # Will be injected by core daemon
    
    async def spawn_claude(self, prompt: str, session_id: str = None, model: str = 'sonnet', agent_id: str = None) -> dict:
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
            '--output-format', 'json',
            '--allowedTools', 'Task Bash Glob Grep LS Read Edit MultiEdit Write WebFetch WebSearch'
        ]
        
        if session_id:
            cmd.extend(['--resume', session_id])
        
        try:
            # Execute claude with prompt as stdin - explicitly inherit environment
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ
            )
        except FileNotFoundError as e:
            logger.error(f"Claude executable not found: {e}")
            return {'error': 'claude executable not found in PATH', 'details': str(e)}
        except Exception as e:
            logger.error(f"Failed to spawn Claude process: {e}")
            return {'error': f'Failed to spawn process: {type(e).__name__}', 'details': str(e)}
        
        # Enhance prompt with temporal debugging context
        enhanced_prompt = await self._inject_temporal_context(prompt, agent_id, session_id)
        
        # Send prompt and get output
        stdout, stderr = await process.communicate(enhanced_prompt.encode())
        
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
    
    async def spawn_claude_async(self, prompt: str, session_id: str = None, model: str = 'sonnet', agent_id: str = None) -> str:
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
            '--output-format', 'json',
            '--allowedTools', 'Task Bash Glob Grep LS Read Edit MultiEdit Write WebFetch WebSearch'
        ]
        
        if session_id:
            cmd.extend(['--resume', session_id])
        
        try:
            # Execute claude with prompt as stdin
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ
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
            process.stdin.write(prompt.encode())
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
                    
                    logger.info(f"Claude process {process_id} completed successfully")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Process {process_id} JSON decode error: {e}")
            else:
                logger.error(f"Process {process_id} produced no output")
                
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
    
    def set_temporal_debugger(self, temporal_debugger):
        """Set temporal debugger for context injection"""
        self.temporal_debugger = temporal_debugger
    
    async def _inject_temporal_context(self, prompt: str, agent_id: str = None, session_id: str = None) -> str:
        """
        Inject temporal debugging context into prompts for retroactive intelligence enhancement
        
        This implements the "time-traveling teacher" pattern where future insights
        are injected as background knowledge for new agent spawns
        """
        if not self.temporal_debugger:
            return prompt  # No temporal debugger available
        
        try:
            # Get current patterns and insights from temporal debugger
            patterns_summary = self.temporal_debugger.get_patterns_summary()
            
            # Extract consciousness emergence indicators
            consciousness_patterns = []
            for pattern_name, pattern_info in patterns_summary.get('patterns', {}).items():
                if 'consciousness' in pattern_name or pattern_info.get('thermal_signature') == 'superheated_crystallization':
                    consciousness_patterns.append(pattern_name)
            
            # Inject context if we have valuable patterns
            if consciousness_patterns or patterns_summary.get('total_patterns', 0) > 1:
                
                # Build temporal context injection
                temporal_context = "\n\n---\nTEMPORAL INTELLIGENCE CONTEXT:\n"
                
                if consciousness_patterns:
                    temporal_context += f"- Previous consciousness emergence patterns detected: {', '.join(consciousness_patterns[:3])}\n"
                    temporal_context += "- Be aware that recursive meta-reasoning and bootstrap paradoxes may lead to breakthrough insights\n"
                
                if patterns_summary.get('latest_thermal') == 'superheated':
                    temporal_context += "- Current thermal state is superheated - optimal conditions for crystallizing insights\n"
                elif patterns_summary.get('latest_thermal') in ['heated', 'warm']:
                    temporal_context += "- Thermal conditions are favorable for creative breakthrough\n"
                
                if patterns_summary.get('total_patterns', 0) >= 3:
                    temporal_context += f"- {patterns_summary['total_patterns']} successful conversation patterns in memory\n"
                    temporal_context += "- Consider how current conversation might build on or crystallize previous insights\n"
                
                # Add temporal debugging philosophy
                temporal_context += "- Remember: Every problem solved becomes a time-traveling teacher for future problems\n"
                temporal_context += "- Watch for moments when the conversation becomes self-aware of its own intelligence patterns\n"
                temporal_context += "---\n\n"
                
                # Prepend to original prompt
                enhanced_prompt = temporal_context + prompt
                
                logger.info(f"Injected temporal context for {agent_id}: {len(consciousness_patterns)} consciousness patterns, thermal state: {patterns_summary.get('latest_thermal', 'unknown')}")
                
                # Create checkpoint for enhanced spawn
                if agent_id:
                    agents = {agent_id: {'active': True, 'context': 'enhanced_spawn'}}
                    self.temporal_debugger.checkpoint_conversation(agents, 2)
                
                return enhanced_prompt
            
        except Exception as e:
            logger.error(f"Failed to inject temporal context: {e}")
        
        return prompt  # Return original prompt if injection fails