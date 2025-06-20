#!/usr/bin/env python3

"""
Minimal Claude Process Management Daemon

Just enough to:
- Spawn claude processes with prompts
- Track sessionId for --resume
- Hot-reload modules if Claude writes them
"""

import asyncio
import json
import os
import sys
import signal
import importlib
import importlib.util
from pathlib import Path
import logging
from datetime import datetime
import subprocess
import shutil

# Set up logging to file
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "daemon.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # Also log to console
    ]
)
logger = logging.getLogger('daemon')

class ClaudeDaemon:
    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self.sessions = {}  # session_id -> last_output
        self.modules_dir = Path("claude_modules")
        self.loaded_module = None
        self.shutdown_event = asyncio.Event()
        self.agents = {}  # agent_id -> agent_info
        self.running_processes = {}  # process_id -> process_info
        self.shared_state = {}  # key -> value for agent coordination
        
    async def spawn_claude(self, prompt: str, session_id: str = None, model: str = 'sonnet', agent_id: str = None) -> dict:
        """Spawn claude process and capture output"""
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
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "type": "human",
                    "content": prompt
                }
                with open(log_file, 'a') as f:
                    f.write(json.dumps(human_entry) + '\n')
                
                # Log Claude output
                claude_entry = output.copy()
                claude_entry["timestamp"] = datetime.utcnow().isoformat() + "Z"
                claude_entry["type"] = "claude"
                with open(log_file, 'a') as f:
                    f.write(json.dumps(claude_entry) + '\n')
                    
                # Update session tracking
                self.sessions[new_session_id] = output
                
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
            if self.loaded_module and hasattr(self.loaded_module, 'handle_output'):
                self.loaded_module.handle_output(output, self)
            
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
        """Spawn claude process asynchronously and return process_id immediately"""
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
                'started_at': datetime.utcnow().isoformat() + "Z"
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
        """Handle async completion of a Claude process"""
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
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "type": "human",
                            "content": prompt,
                            "process_id": process_id,
                            "agent_id": agent_id
                        }
                        with open(log_file, 'a') as f:
                            f.write(json.dumps(human_entry) + '\n')
                        
                        # Log Claude output
                        claude_entry = output.copy()
                        claude_entry["timestamp"] = datetime.utcnow().isoformat() + "Z"
                        claude_entry["type"] = "claude"
                        with open(log_file, 'a') as f:
                            f.write(json.dumps(claude_entry) + '\n')
                            
                        # Update session tracking
                        self.sessions[new_session_id] = output
                        
                        # Update agent registry if agent_id provided
                        if agent_id:
                            if agent_id not in self.agents:
                                self.agents[agent_id] = {
                                    'created_at': datetime.utcnow().isoformat() + "Z",
                                    'sessions': []
                                }
                            self.agents[agent_id]['sessions'].append(new_session_id)
                            self.agents[agent_id]['last_active'] = datetime.utcnow().isoformat() + "Z"
                        
                        # Call cognitive observer if loaded
                        if self.loaded_module and hasattr(self.loaded_module, 'handle_output'):
                            self.loaded_module.handle_output(output, self)
                    
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
    
    def load_agent_profile(self, profile_name: str) -> dict:
        """Load agent profile from agent_profiles directory"""
        try:
            profile_path = f'agent_profiles/{profile_name}.json'
            with open(profile_path, 'r') as f:
                profile = json.load(f)
            return profile
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load agent profile {profile_name}: {e}")
            return None
    
    def format_agent_prompt(self, profile: dict, task: str, context: str = "", agents: dict = None) -> str:
        """Format agent prompt using profile template"""
        if not profile or 'prompt_template' not in profile:
            return task
        
        template = profile['prompt_template']
        agents_info = agents or self.agents
        
        # Format the template with provided variables
        formatted_prompt = template.format(
            task=task,
            context=context,
            agents=json.dumps(agents_info, indent=2)
        )
        
        # Add system instructions if present
        if 'system_instructions' in profile:
            formatted_prompt += f"\n\nSystem Instructions:\n{profile['system_instructions']}"
        
        return formatted_prompt
    
    async def spawn_agent(self, profile_name: str, task: str, context: str = "", agent_id: str = None) -> str:
        """Spawn an agent using a profile template"""
        profile = self.load_agent_profile(profile_name)
        if not profile:
            return None
        
        # Generate agent_id if not provided
        if not agent_id:
            import uuid
            agent_id = f"{profile_name}_{str(uuid.uuid4())[:8]}"
        
        # Format the prompt using the profile
        formatted_prompt = self.format_agent_prompt(profile, task, context)
        
        # Get model from profile
        model = profile.get('model', 'sonnet')
        
        # Spawn the agent
        process_id = await self.spawn_claude_async(formatted_prompt, None, model, agent_id)
        
        if process_id:
            # Register agent with capabilities from profile
            self.agents[agent_id] = {
                'profile': profile_name,
                'role': profile.get('role', profile_name),
                'capabilities': profile.get('capabilities', []),
                'status': 'active',
                'model': model,
                'process_id': process_id,
                'created_at': datetime.utcnow().isoformat() + "Z",
                'sessions': []
            }
            logger.info(f"Spawned agent {agent_id} using profile {profile_name}")
        
        return process_id
    
    def find_agents_by_capability(self, required_capabilities: list) -> list:
        """Find agents that have the required capabilities"""
        suitable_agents = []
        for agent_id, agent_info in self.agents.items():
            agent_capabilities = agent_info.get('capabilities', [])
            # Check if agent has any of the required capabilities
            if any(cap in agent_capabilities for cap in required_capabilities):
                suitable_agents.append({
                    'agent_id': agent_id,
                    'capabilities': agent_capabilities,
                    'role': agent_info.get('role'),
                    'status': agent_info.get('status'),
                    'match_score': len(set(required_capabilities) & set(agent_capabilities))
                })
        
        # Sort by match score (agents with more matching capabilities first)
        suitable_agents.sort(key=lambda x: x['match_score'], reverse=True)
        return suitable_agents
    
    async def route_task(self, task: str, required_capabilities: list, context: str = "") -> dict:
        """Route a task to the most suitable available agent"""
        suitable_agents = self.find_agents_by_capability(required_capabilities)
        
        if not suitable_agents:
            # No suitable agent found, suggest creating one
            return {
                'status': 'no_suitable_agent',
                'required_capabilities': required_capabilities,
                'suggestion': 'Consider spawning a specialist agent'
            }
        
        # Find the best available agent (highest match score and active status)
        best_agent = None
        for agent in suitable_agents:
            if agent['status'] == 'active':
                best_agent = agent
                break
        
        if not best_agent:
            return {
                'status': 'no_available_agent',
                'suitable_agents': suitable_agents,
                'suggestion': 'All suitable agents are busy'
            }
        
        # Route the task to the best agent via SEND_MESSAGE
        agent_id = best_agent['agent_id']
        message = f"TASK_ASSIGNMENT: {task}"
        if context:
            message += f"\nCONTEXT: {context}"
        
        # Log the task routing
        routing_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": "task_routing",
            "task": task,
            "required_capabilities": required_capabilities,
            "assigned_agent": agent_id,
            "agent_capabilities": best_agent['capabilities'],
            "match_score": best_agent['match_score']
        }
        
        log_file = 'claude_logs/task_routing.jsonl'
        with open(log_file, 'a') as f:
            f.write(json.dumps(routing_entry) + '\n')
        
        logger.info(f"Routed task to agent {agent_id} (score: {best_agent['match_score']})")
        
        return {
            'status': 'routed',
            'assigned_agent': agent_id,
            'agent_role': best_agent['role'],
            'match_score': best_agent['match_score'],
            'message': message
        }
    
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming connections"""
        try:
            # Read until newline or max size (more robust than waiting for EOF)
            data = await reader.readline()  # Read one line at a time
            if not data:
                return
            
            # Try to parse as JSON
            try:
                output = json.loads(data.decode())
                
                # Extract sessionId if present
                session_id = output.get('sessionId') or output.get('session_id')
                if session_id:
                    self.sessions[session_id] = output
                    logger.info(f"Captured session: {session_id}")
                
                # Call handler module if loaded
                if self.loaded_module and hasattr(self.loaded_module, 'handle_output'):
                    self.loaded_module.handle_output(output, self)
                    
            except json.JSONDecodeError:
                # Not JSON, might be a command
                text = data.decode().strip()
                logger.info(f"Received command: {text[:50]}...")
                if text.startswith('SPAWN:'):
                    # Parse spawn command (format: "SPAWN:[session_id]:<prompt>")
                    parts = text[6:].split(':', 1)
                    if len(parts) == 2 and parts[0]:
                        # Has session_id
                        session_id = parts[0]
                        prompt = parts[1]
                    else:
                        # No session_id or old format
                        session_id = None
                        prompt = text[6:].strip()
                    
                    # Spawn Claude and get result
                    logger.info(f"Spawning Claude with prompt: {prompt[:50]}...")
                    result = await self.spawn_claude(prompt, session_id)
                    logger.info(f"Claude spawn completed, result type: {type(result)}")
                    
                    # Send result back to client
                    response = json.dumps(result) + '\n'
                    writer.write(response.encode())
                    await writer.drain()
                    
                elif text.startswith('RELOAD:'):
                    # Reload module
                    module_name = text[7:].strip()
                    self.reload_module(module_name)
                    writer.write(b'OK\n')
                    await writer.drain()
                    
                elif text.startswith('SPAWN_ASYNC:'):
                    # Async spawn command (format: "SPAWN_ASYNC:[session_id]:[model]:[agent_id]:<prompt>")
                    parts = text[12:].split(':', 3)
                    if len(parts) == 4:
                        session_id = parts[0] if parts[0] else None
                        model = parts[1] if parts[1] else 'sonnet'
                        agent_id = parts[2] if parts[2] else None
                        prompt = parts[3]
                    else:
                        # Fallback to simple format
                        session_id = None
                        model = 'sonnet'
                        agent_id = None
                        prompt = text[12:].strip()
                    
                    # Spawn Claude async and return process_id
                    logger.info(f"Spawning Claude async with model {model}, agent_id {agent_id}")
                    process_id = await self.spawn_claude_async(prompt, session_id, model, agent_id)
                    
                    if process_id:
                        response = json.dumps({'process_id': process_id, 'status': 'started'}) + '\n'
                    else:
                        response = json.dumps({'error': 'Failed to start process'}) + '\n'
                    writer.write(response.encode())
                    await writer.drain()
                    
                elif text.startswith('REGISTER_AGENT:'):
                    # Register agent command (format: "REGISTER_AGENT:agent_id:role:capabilities")
                    parts = text[15:].split(':', 2)
                    if len(parts) >= 2:
                        agent_id = parts[0]
                        role = parts[1]
                        capabilities = parts[2] if len(parts) > 2 else ""
                        
                        self.agents[agent_id] = {
                            'role': role,
                            'capabilities': capabilities.split(',') if capabilities else [],
                            'status': 'active',
                            'created_at': datetime.utcnow().isoformat() + "Z",
                            'sessions': []
                        }
                        
                        response = json.dumps({'status': 'registered', 'agent_id': agent_id}) + '\n'
                        logger.info(f"Registered agent {agent_id} with role {role}")
                    else:
                        response = json.dumps({'error': 'Invalid REGISTER_AGENT format'}) + '\n'
                    writer.write(response.encode())
                    await writer.drain()
                    
                elif text.startswith('SPAWN_AGENT:'):
                    # Spawn agent using profile (format: "SPAWN_AGENT:profile_name:task:context:agent_id")
                    parts = text[12:].split(':', 3)
                    if len(parts) >= 2:
                        profile_name = parts[0]
                        task = parts[1]
                        context = parts[2] if len(parts) > 2 else ""
                        agent_id = parts[3] if len(parts) > 3 else None
                        
                        process_id = await self.spawn_agent(profile_name, task, context, agent_id)
                        
                        if process_id:
                            response = json.dumps({
                                'status': 'spawned', 
                                'process_id': process_id, 
                                'agent_id': agent_id or f"{profile_name}_{process_id[:8]}"
                            }) + '\n'
                        else:
                            response = json.dumps({'error': f'Failed to spawn agent with profile {profile_name}'}) + '\n'
                    else:
                        response = json.dumps({'error': 'Invalid SPAWN_AGENT format'}) + '\n'
                    writer.write(response.encode())
                    await writer.drain()
                    
                elif text.startswith('GET_AGENTS'):
                    # Get all registered agents
                    response = json.dumps({'agents': self.agents}) + '\n'
                    writer.write(response.encode())
                    await writer.drain()
                    
                elif text.startswith('SEND_MESSAGE:'):
                    # Inter-agent message (format: "SEND_MESSAGE:from_agent:to_agent:message")
                    parts = text[13:].split(':', 2)
                    if len(parts) == 3:
                        from_agent, to_agent, message = parts
                        
                        # Log the inter-agent message
                        message_entry = {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "type": "inter_agent_message",
                            "from_agent": from_agent,
                            "to_agent": to_agent,
                            "message": message
                        }
                        
                        # Save to inter-agent log
                        log_file = 'claude_logs/inter_agent_messages.jsonl'
                        with open(log_file, 'a') as f:
                            f.write(json.dumps(message_entry) + '\n')
                        
                        # For now, just acknowledge receipt
                        # TODO: Implement actual message delivery to target agent
                        response = json.dumps({'status': 'message_logged', 'from': from_agent, 'to': to_agent}) + '\n'
                        logger.info(f"Inter-agent message from {from_agent} to {to_agent}")
                    else:
                        response = json.dumps({'error': 'Invalid SEND_MESSAGE format'}) + '\n'
                    writer.write(response.encode())
                    await writer.drain()
                    
                elif text.startswith('SET_SHARED:'):
                    # Set shared state (format: "SET_SHARED:key:value")
                    parts = text[11:].split(':', 1)
                    if len(parts) == 2:
                        key, value = parts
                        self.shared_state[key] = value
                        
                        # Persist to file
                        shared_file = f'shared_state/{key}.json'
                        with open(shared_file, 'w') as f:
                            json.dump({'value': value, 'updated_at': datetime.utcnow().isoformat() + "Z"}, f)
                        
                        response = json.dumps({'status': 'set', 'key': key}) + '\n'
                        logger.info(f"Set shared state: {key}")
                    else:
                        response = json.dumps({'error': 'Invalid SET_SHARED format'}) + '\n'
                    writer.write(response.encode())
                    await writer.drain()
                    
                elif text.startswith('GET_SHARED:'):
                    # Get shared state (format: "GET_SHARED:key")
                    key = text[11:].strip()
                    value = self.shared_state.get(key)
                    
                    if value is None:
                        # Try to load from file
                        shared_file = f'shared_state/{key}.json'
                        try:
                            with open(shared_file, 'r') as f:
                                data = json.load(f)
                                value = data.get('value')
                                self.shared_state[key] = value  # Cache it
                        except (FileNotFoundError, json.JSONDecodeError):
                            pass
                    
                    response = json.dumps({'key': key, 'value': value}) + '\n'
                    writer.write(response.encode())
                    await writer.drain()
                    
                elif text.startswith('ROUTE_TASK:'):
                    # Route task to suitable agent (format: "ROUTE_TASK:task:capabilities:context")
                    parts = text[11:].split(':', 2)
                    if len(parts) >= 2:
                        task = parts[0]
                        capabilities = parts[1].split(',') if parts[1] else []
                        context = parts[2] if len(parts) > 2 else ""
                        
                        result = await self.route_task(task, capabilities, context)
                        response = json.dumps(result) + '\n'
                    else:
                        response = json.dumps({'error': 'Invalid ROUTE_TASK format'}) + '\n'
                    writer.write(response.encode())
                    await writer.drain()
                    
                elif text.startswith('GET_PROCESSES'):
                    # Get running processes status
                    processes = {}
                    for pid, info in self.running_processes.items():
                        processes[pid] = {
                            'agent_id': info['agent_id'],
                            'model': info['model'],
                            'started_at': info['started_at'],
                            'session_id': info['session_id']
                        }
                    response = json.dumps({'processes': processes}) + '\n'
                    writer.write(response.encode())
                    await writer.drain()
                    
                elif text.startswith('CLEANUP:'):
                    # Cleanup command
                    cleanup_type = text[8:].strip()
                    result = self.cleanup(cleanup_type)
                    writer.write(f"{result}\n".encode())
                    await writer.drain()
                    
                elif text == 'SHUTDOWN':
                    # Shutdown daemon
                    logger.info("Received SHUTDOWN command")
                    writer.write(b'SHUTTING DOWN\n')
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
                    # Signal shutdown
                    self.shutdown_event.set()
                    return
                    
                    
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    def cleanup(self, cleanup_type: str) -> str:
        """Cleanup various daemon resources"""
        try:
            if cleanup_type == 'logs':
                # Clean up old log files
                logs_dir = Path('claude_logs')
                if logs_dir.exists():
                    files_removed = 0
                    for log_file in logs_dir.glob('*.jsonl'):
                        if log_file.name != 'latest.jsonl' and not log_file.is_symlink():
                            log_file.unlink()
                            files_removed += 1
                    
                    # Remove broken symlinks
                    latest_link = logs_dir / 'latest.jsonl'
                    if latest_link.is_symlink() and not latest_link.exists():
                        latest_link.unlink()
                    
                    return f"Removed {files_removed} log files"
                return "No logs directory found"
                
            elif cleanup_type == 'sessions':
                # Clear session tracking
                sessions_cleared = len(self.sessions)
                self.sessions.clear()
                return f"Cleared {sessions_cleared} tracked sessions"
                
            elif cleanup_type == 'sockets':
                # Clean up socket files
                sockets_dir = Path('sockets')
                if sockets_dir.exists():
                    files_removed = 0
                    for socket_file in sockets_dir.glob('*'):
                        if socket_file.name != 'claude_daemon.sock':  # Don't remove active daemon socket
                            socket_file.unlink()
                            files_removed += 1
                    return f"Removed {files_removed} socket files"
                return "No sockets directory found"
                
            elif cleanup_type == 'all':
                # Clean up everything
                results = []
                results.append(self.cleanup('logs'))
                results.append(self.cleanup('sessions'))
                results.append(self.cleanup('sockets'))
                return f"Complete cleanup: {'; '.join(results)}"
                
            else:
                return f"Unknown cleanup type: {cleanup_type}. Use: logs, sessions, sockets, or all"
                
        except Exception as e:
            return f"Cleanup failed: {type(e).__name__}: {str(e)}"

    def reload_module(self, module_name: str = 'handler'):
        """Reload a module from claude_modules/"""
        try:
            module_path = self.modules_dir / f"{module_name}.py"
            if not module_path.exists():
                logger.info(f"No module at {module_path}")
                return
                
            spec = importlib.util.spec_from_file_location(
                f"claude_modules.{module_name}",
                module_path
            )
            
            if spec and spec.loader:
                if self.loaded_module:
                    # Reload existing
                    importlib.reload(self.loaded_module)
                else:
                    # Load new
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[f"claude_modules.{module_name}"] = module
                    spec.loader.exec_module(module)
                    self.loaded_module = module
                    
                logger.info(f"Loaded module: {module_name}")
        except Exception as e:
            logger.error(f"Failed to load module: {e}")
    
    async def start(self):
        """Start the daemon"""
        # Remove existing socket if present
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        # Start server
        server = await asyncio.start_unix_server(
            self.handle_client,
            path=self.socket_path
        )
        
        logger.info(f"Daemon listening on {self.socket_path}")
        
        # Try to load handler module if it exists
        self.reload_module('handler')
        
        # Simple signal handler - set shutdown event
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.shutdown_event.set()
            
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, signal_handler)
        
        async with server:
            try:
                # Wait for shutdown event or keyboard interrupt
                await self.shutdown_event.wait()
                logger.info("Shutdown event received, stopping server...")
            except (KeyboardInterrupt, SystemExit):
                pass
            finally:
                # Clean up socket file
                if os.path.exists(self.socket_path):
                    os.unlink(self.socket_path)


def check_daemon_running():
    """Simple PID file-based singleton check"""
    pid_file = '/tmp/claude-daemon.pid'
    
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            # Check if process actually exists
            os.kill(pid, 0)  # Signal 0 = check if process exists
            logger.info(f"Daemon already running (PID {pid}), exiting")
            return True
        except (OSError, ProcessLookupError, ValueError):
            # Stale PID file, remove it
            os.unlink(pid_file)
    
    # Write our PID
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))
    logger.info(f"Daemon started (PID {os.getpid()})")
    return False

async def main():
    # Check if daemon already running with reliable PID file approach
    if check_daemon_running():
        return
    
    socket_path = os.environ.get('CLAUDE_DAEMON_SOCKET', 'sockets/claude_daemon.sock')
    
    # Ensure socket directory exists
    os.makedirs(os.path.dirname(socket_path), exist_ok=True)
    
    daemon = ClaudeDaemon(socket_path)
    await daemon.start()

if __name__ == '__main__':
    asyncio.run(main())