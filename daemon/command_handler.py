#!/usr/bin/env python3

"""
Command Handler - Command routing and processing
Extracted from daemon_clean.py with 100% functionality preservation
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger('daemon')

class CommandHandler:
    """Handler for daemon commands using Command Pattern - EXACT copy from daemon_clean.py"""
    
    def __init__(self, core_daemon, state_manager=None, process_manager=None, agent_manager=None, utils_manager=None, hot_reload_manager=None, message_bus=None, identity_manager=None):
        # Store references to all managers for cross-module communication
        self.core_daemon = core_daemon
        self.state_manager = state_manager
        self.process_manager = process_manager
        self.agent_manager = agent_manager
        self.utils_manager = utils_manager
        self.hot_reload_manager = hot_reload_manager
        self.message_bus = message_bus
        self.identity_manager = identity_manager
        
        # Command registry - maps command prefixes to handler methods
        self.handlers = {
            'SPAWN:': self.handle_spawn_unified,  # Unified handler with sync/async mode
            'S:': self.handle_spawn_unified,  # Alias for SPAWN
            'RELOAD:': self.handle_reload_module,
            'R:': self.handle_reload_module,  # Alias for RELOAD
            'REGISTER_AGENT:': self.handle_register_agent,
            'SPAWN_AGENT:': self.handle_spawn_agent,
            'SA:': self.handle_spawn_agent,  # Alias for SPAWN_AGENT
            'GET_AGENTS': self.handle_get_agents,
            'GA': self.handle_get_agents,  # Alias for GET_AGENTS
            'SET_SHARED:': self.handle_set_shared,
            'SET:': self.handle_set_shared,  # Alias for SET_SHARED
            'GET_SHARED:': self.handle_get_shared,
            'GET:': self.handle_get_shared,  # Alias for GET_SHARED
            'ROUTE_TASK:': self.handle_route_task,
            'GET_PROCESSES': self.handle_get_processes,
            'CLEANUP:': self.handle_cleanup,
            'HEALTH_CHECK': self.handle_health_check,
            'LOAD_STATE:': self.handle_load_state,
            'RELOAD_DAEMON': self.handle_reload_daemon,
            'SHUTDOWN': self.handle_shutdown,
            # New message bus commands
            'SUBSCRIBE:': self.handle_subscribe,
            'PUBLISH:': self.handle_publish,
            'AGENT_CONNECTION:': self.handle_agent_connection,
            'MESSAGE_BUS_STATS': self.handle_message_bus_stats,
            'GET_COMMANDS': self.handle_get_commands,
            # Identity management commands
            'CREATE_IDENTITY:': self.handle_create_identity,
            'UPDATE_IDENTITY:': self.handle_update_identity,
            'GET_IDENTITY:': self.handle_get_identity,
            'LIST_IDENTITIES': self.handle_list_identities,
            'REMOVE_IDENTITY:': self.handle_remove_identity
        }
    
    async def handle_command(self, command_text: str, writer: asyncio.StreamWriter, reader: asyncio.StreamReader = None) -> bool:
        """Route command to appropriate handler. Returns True if daemon should continue - EXACT copy from daemon_clean.py"""
        try:
            # Store reader for length-prefixed protocol support
            self._current_reader = reader
            
            # Find matching handler
            handler = None
            for prefix, handler_func in self.handlers.items():
                if command_text.startswith(prefix):
                    handler = handler_func
                    break
            
            if handler:
                return await handler(command_text, writer)
            else:
                return await self.handle_unknown(command_text, writer)
                
        except Exception as e:
            logger.error(f"Error processing command '{command_text[:50]}...': {e}")
            return await self.send_error_response(writer, f"Command processing failed: {type(e).__name__}", str(e))
    
    async def send_response(self, writer: asyncio.StreamWriter, response: dict) -> bool:
        """Send JSON response to client - EXACT copy from daemon_clean.py"""
        try:
            response_json = json.dumps(response) + '\n'
            writer.write(response_json.encode())
            await writer.drain()
            return True
        except Exception as e:
            logger.error(f"Failed to send response: {e}")
            return True
    
    async def send_error_response(self, writer: asyncio.StreamWriter, error: str, details: str = "") -> bool:
        """Send error response to client - EXACT copy from daemon_clean.py"""
        return await self.send_response(writer, {
            'error': error,
            'details': details
        })
    
    async def send_text_response(self, writer: asyncio.StreamWriter, text: str) -> bool:
        """Send plain text response - EXACT copy from daemon_clean.py"""
        try:
            writer.write(text.encode() + b'\n')
            await writer.drain()
            return True
        except Exception as e:
            logger.error(f"Failed to send text response: {e}")
            return True
    
    # Individual command handlers - clean, focused, testable - EXACT copies from daemon_clean.py
    
    
    async def handle_spawn_unified(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle SPAWN command - Spawn Claude processes in sync or async mode
        Format: SPAWN:[sync|async]:claude:[session_id]:[model]:[agent_id]:<prompt>
        Length-prefixed format: SPAWN:[sync|async]:claude:[session_id]:[model]:[agent_id]:<length> + prompt_bytes
        Sync mode: Waits for Claude response before returning
        Async mode: Returns immediately with process_id"""
        logger.info("Processing unified SPAWN command")
        
        # Parse unified format: "SPAWN:[mode]:[type]:[session_id]:[model]:[agent_id]:<prompt_or_length>"
        command_body = command[6:]  # Remove "SPAWN:"
        
        # Check if this is the new unified format
        parts = command_body.split(':', 5)
        
        if len(parts) >= 6 and parts[0] in ['sync', 'async'] and parts[1] == 'claude':
            # New unified format: mode:type:session_id:model:agent_id:prompt_or_length
            mode = parts[0]  # sync or async
            process_type = parts[1]  # claude
            session_id = parts[2] if parts[2] else None
            model = parts[3] if parts[3] else 'sonnet'
            agent_id = parts[4] if parts[4] else None
            last_field = parts[5]
            
            # Check if last field is a length (numeric)
            try:
                prompt_length = int(last_field)
                # Length-prefixed protocol: read prompt_length bytes from socket
                logger.info(f"Reading {prompt_length} bytes for length-prefixed prompt")
                
                if self._current_reader:
                    prompt_bytes = await self._current_reader.read(prompt_length)
                    prompt = prompt_bytes.decode('utf-8')
                    logger.info(f"Successfully read length-prefixed prompt ({len(prompt)} chars)")
                else:
                    logger.error("Length-prefixed protocol detected but no reader available")
                    prompt = ""
                
            except ValueError:
                # Not a number, treat as legacy prompt
                prompt = last_field
            
            if mode == 'sync':
                return await self._handle_spawn_sync(writer, session_id, model, agent_id, prompt)
            elif mode == 'async':
                return await self._handle_spawn_async(writer, session_id, model, agent_id, prompt)
            else:
                return await self.send_error_response(writer, f'Invalid mode: {mode}. Use sync or async.')
                
        else:
            # Invalid format
            return await self.send_error_response(writer, 'Invalid SPAWN format. Use SPAWN:[sync|async]:claude:[session_id]:[model]:[agent_id]:<prompt_or_length>')
    
    async def _handle_spawn_sync(self, writer: asyncio.StreamWriter, session_id: str, model: str, agent_id: str, prompt: str) -> bool:
        """Handle synchronous Claude spawning"""
        logger.info(f"Synchronous Claude spawn: {prompt[:50]}...")
        
        # Check if agent has a profile with enable_tools setting
        enable_tools = True  # Default to True
        
        # Look for agent-specific profile based on agent_id
        if agent_id and self.agent_manager:
            # Try to get agent's profile from registry
            agents = self.agent_manager.get_agents()
            agent_info = agents.get(agent_id, {})
            profile_name = agent_info.get('profile')
            
            if profile_name:
                profile_path = Path(f'agent_profiles/{profile_name}.json')
                if profile_path.exists():
                    try:
                        with open(profile_path) as f:
                            profile = json.load(f)
                            enable_tools = profile.get('enable_tools', True)
                            logger.info(f"Agent {agent_id} using profile {profile_name} has enable_tools={enable_tools}")
                    except Exception as e:
                        logger.warning(f"Could not load profile {profile_name} for agent {agent_id}: {e}")
        
        if self.process_manager:
            result = await self.process_manager.spawn_claude(prompt, session_id, model, agent_id, enable_tools)
        else:
            result = {'error': 'No process manager available'}
            
        logger.info("Synchronous Claude spawn completed")
        return await self.send_response(writer, result)
    
    async def _handle_spawn_async(self, writer: asyncio.StreamWriter, session_id: str, model: str, agent_id: str, prompt: str) -> bool:
        """Handle asynchronous Claude spawning"""
        logger.info(f"Asynchronous Claude spawn: {prompt[:50]}...")
        
        # Check if agent has a profile with enable_tools setting
        enable_tools = True  # Default to True
        
        # Look for agent-specific profile based on agent_id
        if agent_id and self.agent_manager:
            # Try to get agent's profile from registry
            agents = self.agent_manager.get_agents()
            agent_info = agents.get(agent_id, {})
            profile_name = agent_info.get('profile')
            
            if profile_name:
                profile_path = Path(f'agent_profiles/{profile_name}.json')
                if profile_path.exists():
                    try:
                        with open(profile_path) as f:
                            profile = json.load(f)
                            enable_tools = profile.get('enable_tools', True)
                            logger.info(f"Agent {agent_id} using profile {profile_name} has enable_tools={enable_tools}")
                    except Exception as e:
                        logger.warning(f"Could not load profile {profile_name} for agent {agent_id}: {e}")
        
        if self.process_manager:
            process_id = await self.process_manager.spawn_claude_async(prompt, session_id, model, agent_id, enable_tools)
        else:
            process_id = None
        
        if process_id:
            return await self.send_response(writer, {'process_id': process_id, 'status': 'started', 'type': 'claude'})
        else:
            return await self.send_error_response(writer, 'Failed to start Claude process')
    
    
    async def handle_reload_module(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle RELOAD command - Hot-reload Python modules without restarting daemon
        Format: RELOAD:<module_name>
        Useful for updating claude_modules handlers during development"""
        module_name = command[7:].strip()
        if self.utils_manager:
            self.utils_manager.reload_module(module_name)
        return await self.send_text_response(writer, 'OK')
    
    async def handle_register_agent(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle REGISTER_AGENT command - Register an agent with the system
        Format: REGISTER_AGENT:agent_id:role:capabilities
        Makes agent discoverable for task routing and inter-agent messaging"""
        logger.info("Processing REGISTER_AGENT command")
        
        # Parse format: "REGISTER_AGENT:agent_id:role:capabilities"
        parts = command[15:].split(':', 2)
        if len(parts) < 2:
            return await self.send_error_response(writer, 'Invalid REGISTER_AGENT format')
        
        agent_id, role = parts[0], parts[1]
        capabilities = parts[2] if len(parts) > 2 else ""
        
        if self.agent_manager:
            result = self.agent_manager.register_agent(agent_id, role, capabilities)
            return await self.send_response(writer, result)
        else:
            return await self.send_error_response(writer, 'No agent manager available')
    
    async def handle_spawn_agent(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle SPAWN_AGENT command - Spawn agent process using predefined profile
        Format: SPAWN_AGENT:profile_name:task:context:agent_id
        Creates message-bus-aware agent that can participate in conversations"""
        logger.info("Processing SPAWN_AGENT command")
        
        # Parse format: "SPAWN_AGENT:profile_name:task:context:agent_id"
        parts = command[12:].split(':', 3)
        if len(parts) < 2:
            return await self.send_error_response(writer, 'Invalid SPAWN_AGENT format')
        
        profile_name, task = parts[0], parts[1]
        context = parts[2] if len(parts) > 2 else ""
        agent_id = parts[3] if len(parts) > 3 else None
        
        if self.agent_manager:
            process_id = await self.agent_manager.spawn_agent(profile_name, task, context, agent_id)
        else:
            process_id = None
        
        if process_id:
            return await self.send_response(writer, {
                'status': 'spawned', 
                'process_id': process_id, 
                'agent_id': agent_id or f"{profile_name}_{process_id[:8]}"
            })
        else:
            return await self.send_error_response(writer, f'Failed to spawn agent with profile {profile_name}')
    
    async def handle_get_agents(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle GET_AGENTS command - List all registered agents and their capabilities
        Returns agent profiles, roles, and current status"""
        logger.info("Processing GET_AGENTS command")
        if self.agent_manager:
            agents = self.agent_manager.get_all_agents()
            result = await self.send_response(writer, {'agents': agents})
        else:
            result = await self.send_response(writer, {'agents': {}})
        logger.info("Sent GET_AGENTS response")
        return result
    
    
    async def handle_set_shared(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle SET_SHARED command - Store shared state accessible by all agents
        Format: SET_SHARED:key:value
        Persists to shared_state/ directory for cross-agent coordination"""
        logger.info("Processing SET_SHARED command")
        
        # Parse format: "SET_SHARED:key:value"
        parts = command[11:].split(':', 1)
        if len(parts) != 2:
            return await self.send_error_response(writer, 'Invalid SET_SHARED format')
        
        key, value = parts
        
        if self.state_manager:
            result = self.state_manager.set_shared_state(key, value)
            logger.info(f"Set shared state: {key}")
            result = await self.send_response(writer, {'status': 'set', 'key': key})
            logger.info("Sent SET_SHARED response")
            return result
        else:
            return await self.send_error_response(writer, 'No state manager available')
    
    async def handle_get_shared(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle GET_SHARED command - Retrieve shared state by key
        Format: GET_SHARED:key
        Returns value stored with SET_SHARED or null if not found"""
        logger.info("Processing GET_SHARED command")
        
        key = command[11:].strip()
        
        if self.state_manager:
            value = self.state_manager.get_shared_state(key)
            result = await self.send_response(writer, {'key': key, 'value': value})
            logger.info(f"Sent GET_SHARED response for key: {key}")
            return result
        else:
            return await self.send_error_response(writer, 'No state manager available')
    
    async def handle_route_task(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle ROUTE_TASK command - EXACT copy from daemon_clean.py"""
        # Parse format: "ROUTE_TASK:task:capabilities:context"
        parts = command[11:].split(':', 2)
        if len(parts) < 2:
            return await self.send_error_response(writer, 'Invalid ROUTE_TASK format')
        
        task = parts[0]
        capabilities = parts[1].split(',') if parts[1] else []
        context = parts[2] if len(parts) > 2 else ""
        
        if self.agent_manager:
            result = await self.agent_manager.route_task(task, capabilities, context)
            return await self.send_response(writer, result)
        else:
            return await self.send_error_response(writer, 'No agent manager available')
    
    async def handle_get_processes(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle GET_PROCESSES command - EXACT copy from daemon_clean.py"""
        if self.process_manager:
            processes = self.process_manager.get_running_processes()
            return await self.send_response(writer, {'processes': processes})
        else:
            return await self.send_response(writer, {'processes': {}})
    
    async def handle_cleanup(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle CLEANUP command - EXACT copy from daemon_clean.py"""
        cleanup_type = command[8:].strip()
        if self.utils_manager:
            result = self.utils_manager.cleanup(cleanup_type)
        else:
            result = 'No utils manager available'
        return await self.send_text_response(writer, result)
    
    async def handle_health_check(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle HEALTH_CHECK command - EXACT copy from daemon_clean.py"""
        return await self.send_text_response(writer, 'HEALTHY')
    
    async def handle_load_state(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle LOAD_STATE command - EXACT copy from daemon_clean.py"""
        state_json = command[11:]
        try:
            state = json.loads(state_json)
            if self.hot_reload_manager:
                self.hot_reload_manager.deserialize_state(state)
            logger.info("State loaded successfully during hot reload")
            return await self.send_text_response(writer, 'STATE_LOADED')
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return await self.send_text_response(writer, 'STATE_LOAD_FAILED')
    
    async def handle_reload_daemon(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle RELOAD_DAEMON command - EXACT copy from daemon_clean.py"""
        logger.info("Received RELOAD_DAEMON command")
        if self.hot_reload_manager:
            result = await self.hot_reload_manager.hot_reload_daemon()
            return await self.send_response(writer, result)
        else:
            return await self.send_error_response(writer, 'No hot reload manager available')
    
    async def handle_shutdown(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle SHUTDOWN command - EXACT copy from daemon_clean.py"""
        logger.info("Received SHUTDOWN command")
        await self.send_text_response(writer, 'SHUTTING DOWN')
        writer.close()
        await writer.wait_closed()
        if self.core_daemon:
            self.core_daemon.shutdown_event.set()
        return False  # Signal to stop handling
    
    async def handle_unknown(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle unknown command - EXACT copy from daemon_clean.py"""
        logger.warning(f"Unknown command: {command[:100]}")
        command_name = command.split(':')[0] if ':' in command else command
        return await self.send_error_response(writer, f'Unknown command: {command_name}')
    
    # New message bus command handlers
    
    async def handle_subscribe(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle SUBSCRIBE command - Subscribe agent to message bus events
        Format: SUBSCRIBE:agent_id:event_type1,event_type2,...
        Prerequisite: Call AGENT_CONNECTION:connect first
        Common events: DIRECT_MESSAGE, BROADCAST, TASK_ASSIGNMENT, PROCESS_COMPLETE"""
        # Parse format: "SUBSCRIBE:agent_id:event_type1,event_type2,..."
        parts = command[10:].split(':', 1)
        if len(parts) != 2:
            return await self.send_error_response(writer, 'Invalid SUBSCRIBE format')
        
        agent_id, event_types_str = parts
        event_types = [et.strip() for et in event_types_str.split(',')]
        
        if self.message_bus:
            success = self.message_bus.subscribe(agent_id, event_types)
            if success:
                return await self.send_response(writer, {
                    'status': 'subscribed',
                    'agent_id': agent_id,
                    'event_types': event_types
                })
            else:
                return await self.send_error_response(writer, f'Agent {agent_id} not connected')
        else:
            return await self.send_error_response(writer, 'No message bus available')
    
    async def handle_publish(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle PUBLISH command - Publish event to message bus subscribers
        Format: PUBLISH:from_agent:event_type:json_payload
        Events are delivered to all agents subscribed to the event_type
        Use DIRECT_MESSAGE for point-to-point, BROADCAST for all agents"""
        # Parse format: "PUBLISH:from_agent:event_type:json_payload"
        parts = command[8:].split(':', 2)
        if len(parts) != 3:
            return await self.send_error_response(writer, 'Invalid PUBLISH format')
        
        from_agent, event_type, payload_str = parts
        
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError:
            return await self.send_error_response(writer, 'Invalid JSON payload')
        
        if self.message_bus:
            result = await self.message_bus.publish(from_agent, event_type, payload)
            return await self.send_response(writer, result)
        else:
            return await self.send_error_response(writer, 'No message bus available')
    
    async def handle_agent_connection(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle unified AGENT_CONNECTION command for connect/disconnect operations"""
        # Parse format: "AGENT_CONNECTION:action:agent_id" where action is "connect" or "disconnect"
        parts = command[17:].split(':', 1)
        if len(parts) != 2:
            return await self.send_error_response(writer, 'Invalid AGENT_CONNECTION format. Use: AGENT_CONNECTION:connect|disconnect:agent_id')
        
        action, agent_id = parts
        action = action.lower()
        
        if action == 'connect':
            if self.message_bus:
                self.message_bus.connect_agent(agent_id, writer)
                return await self.send_response(writer, {
                    'status': 'connected',
                    'agent_id': agent_id,
                    'action': 'connect'
                })
            else:
                return await self.send_error_response(writer, 'No message bus available')
                
        elif action == 'disconnect':
            if self.message_bus:
                self.message_bus.disconnect_agent(agent_id)
                return await self.send_response(writer, {
                    'status': 'disconnected',
                    'agent_id': agent_id,
                    'action': 'disconnect'
                })
            else:
                return await self.send_error_response(writer, 'No message bus available')
        else:
            return await self.send_error_response(writer, f'Invalid action: {action}. Use "connect" or "disconnect"')
    
    
    async def handle_message_bus_stats(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle MESSAGE_BUS_STATS command"""
        if self.message_bus:
            stats = self.message_bus.get_stats()
            return await self.send_response(writer, stats)
        else:
            return await self.send_response(writer, {'error': 'No message bus available'})
    
    async def handle_get_commands(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle GET_COMMANDS - Returns available daemon commands with documentation"""
        logger.info("Processing GET_COMMANDS")
        
        commands = {}
        
        # Define aliases mapping for documentation
        aliases = {
            'S:': 'SPAWN:',
            'R:': 'RELOAD:',
            'SA:': 'SPAWN_AGENT:',
            'GA': 'GET_AGENTS',
            'SET:': 'SET_SHARED:',
            'GET:': 'GET_SHARED:'
        }
        
        # Extract command info from handlers and their docstrings
        for cmd_prefix, handler_func in self.handlers.items():
            # Skip aliases in main listing (they'll be added as metadata)
            if cmd_prefix in aliases:
                continue
                
            # Parse docstring for description
            docstring = handler_func.__doc__ or ""
            description = docstring.split(' - ')[1].strip() if ' - ' in docstring else docstring.strip()
            
            # Determine format based on command prefix
            if cmd_prefix.endswith(':'):
                # Extract format from docstring if available
                format_match = None
                for line in docstring.split('\n'):
                    if 'format:' in line.lower() or 'parse format:' in line.lower():
                        format_match = line.split(':', 1)[1].strip().strip('"')
                        break
                
                # If not found in docstring, use generic format
                if not format_match:
                    cmd_name = cmd_prefix[:-1]
                    if cmd_name == 'SPAWN':
                        format_match = "SPAWN:[sync|async]:claude:[session_id]:[model]:[agent_id]:<prompt>"
                    elif cmd_name == 'SUBSCRIBE':
                        format_match = "SUBSCRIBE:agent_id:event_type1,event_type2,..."
                    elif cmd_name == 'PUBLISH':
                        format_match = "PUBLISH:from_agent:event_type:json_payload"
                    elif cmd_name == 'REGISTER_AGENT':
                        format_match = "REGISTER_AGENT:agent_id:role:capabilities"
                    elif cmd_name == 'SPAWN_AGENT':
                        format_match = "SPAWN_AGENT:profile_name:task:context:agent_id"
                    elif cmd_name == 'SET_SHARED':
                        format_match = "SET_SHARED:key:value"
                    elif cmd_name == 'GET_SHARED':
                        format_match = "GET_SHARED:key"
                    elif cmd_name == 'ROUTE_TASK':
                        format_match = "ROUTE_TASK:task:capabilities:context"
                    elif cmd_name == 'LOAD_STATE':
                        format_match = "LOAD_STATE:<json_state>"
                    elif cmd_name == 'CLEANUP':
                        format_match = "CLEANUP:<cleanup_type>"
                    elif cmd_name == 'RELOAD':
                        format_match = "RELOAD:<module_name>"
                    elif cmd_name == 'AGENT_CONNECTION':
                        format_match = "AGENT_CONNECTION:connect|disconnect:agent_id"
                    else:
                        format_match = f"{cmd_name}:<parameters>"
                
                cmd_key = cmd_prefix[:-1]
            else:
                # Commands without colons (like HEALTH_CHECK, SHUTDOWN)
                format_match = cmd_prefix
                cmd_key = cmd_prefix
            
            # Find aliases for this command
            command_aliases = [alias.rstrip(':') for alias, parent in aliases.items() if parent == cmd_prefix]
            
            commands[cmd_key] = {
                "format": format_match,
                "description": description,
                "aliases": command_aliases
            }
        
        # Group commands by functional area
        grouped_commands = {
            "Process Spawning": {},
            "Agent Management": {},
            "Communication & Events": {},
            "State Management": {},
            "Identity Management": {},
            "System Management": {}
        }
        
        # Categorize commands
        for cmd_name, cmd_info in commands.items():
            if cmd_name in ['SPAWN', 'SPAWN_AGENT']:
                grouped_commands["Process Spawning"][cmd_name] = cmd_info
            elif cmd_name in ['REGISTER_AGENT', 'GET_AGENTS', 'ROUTE_TASK']:
                grouped_commands["Agent Management"][cmd_name] = cmd_info
            elif cmd_name in ['SUBSCRIBE', 'PUBLISH', 'AGENT_CONNECTION', 'MESSAGE_BUS_STATS']:
                grouped_commands["Communication & Events"][cmd_name] = cmd_info
            elif cmd_name in ['SET_SHARED', 'GET_SHARED', 'LOAD_STATE']:
                grouped_commands["State Management"][cmd_name] = cmd_info
            elif cmd_name in ['CREATE_IDENTITY', 'UPDATE_IDENTITY', 'GET_IDENTITY', 'LIST_IDENTITIES', 'REMOVE_IDENTITY']:
                grouped_commands["Identity Management"][cmd_name] = cmd_info
            else:
                grouped_commands["System Management"][cmd_name] = cmd_info
        
        # Add workflow guidance
        workflows = {
            "agent_startup": [
                "1. AGENT_CONNECTION:connect:your_agent_id - Establish connection",
                "2. SUBSCRIBE:your_agent_id:DIRECT_MESSAGE,BROADCAST,PROCESS_COMPLETE - Listen for events", 
                "3. REGISTER_AGENT:your_agent_id:role:capabilities - Register capabilities (optional)",
                "4. Start processing messages and tasks"
            ],
            "spawn_claude": [
                "Sync: SPAWN:sync:claude::sonnet::your_prompt - Wait for response",
                "Async: SPAWN:async:claude::sonnet:agent_id:your_prompt - Get process_id immediately",
                "Then: Wait for PROCESS_COMPLETE event with matching process_id"
            ],
            "inter_agent_communication": [
                "1. Both agents must be connected (AGENT_CONNECTION:connect)",
                "2. Both agents must subscribe to DIRECT_MESSAGE events",
                "3. PUBLISH:sender:DIRECT_MESSAGE:{\"to\":\"recipient\",\"content\":\"message\"}"
            ],
            "shared_state": [
                "SET_SHARED:config_key:{\"some\":\"data\"} - Store shared configuration",
                "GET_SHARED:config_key - Retrieve from any agent"
            ]
        }
        
        result = {
            "commands": commands,
            "grouped_commands": grouped_commands,
            "total_commands": len(commands),
            "groups": list(grouped_commands.keys()),
            "workflows": workflows
        }
        
        logger.info(f"Returning {len(commands)} command definitions")
        return await self.send_response(writer, result)
    
    async def handle_create_identity(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle CREATE_IDENTITY command"""
        if not self.identity_manager:
            return await self.send_error_response(writer, "Identity manager not available")
        
        try:
            # Format: CREATE_IDENTITY:agent_id:display_name:role:personality_traits_json
            parts = command.split(':', 4)
            if len(parts) < 3:
                return await self.send_error_response(writer, "Invalid format. Expected: CREATE_IDENTITY:agent_id:display_name:role:traits_json")
            
            agent_id = parts[1]
            display_name = parts[2] if len(parts) > 2 else None
            role = parts[3] if len(parts) > 3 else None
            
            # Parse personality traits if provided
            personality_traits = None
            if len(parts) > 4 and parts[4]:
                try:
                    personality_traits = json.loads(parts[4])
                except json.JSONDecodeError:
                    return await self.send_error_response(writer, "Invalid JSON for personality traits")
            
            identity = self.identity_manager.create_identity(
                agent_id=agent_id,
                display_name=display_name,
                role=role,
                personality_traits=personality_traits
            )
            
            return await self.send_response(writer, {
                'status': 'identity_created',
                'identity': identity
            })
            
        except Exception as e:
            logger.error(f"Error creating identity: {e}")
            return await self.send_error_response(writer, "Failed to create identity", str(e))
    
    async def handle_update_identity(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle UPDATE_IDENTITY command"""
        if not self.identity_manager:
            return await self.send_error_response(writer, "Identity manager not available")
        
        try:
            # Format: UPDATE_IDENTITY:agent_id:updates_json
            parts = command.split(':', 2)
            if len(parts) != 3:
                return await self.send_error_response(writer, "Invalid format. Expected: UPDATE_IDENTITY:agent_id:updates_json")
            
            agent_id = parts[1]
            try:
                updates = json.loads(parts[2])
            except json.JSONDecodeError:
                return await self.send_error_response(writer, "Invalid JSON for updates")
            
            identity = self.identity_manager.update_identity(agent_id, updates)
            
            if identity:
                return await self.send_response(writer, {
                    'status': 'identity_updated',
                    'identity': identity
                })
            else:
                return await self.send_error_response(writer, f"Identity not found for agent {agent_id}")
            
        except Exception as e:
            logger.error(f"Error updating identity: {e}")
            return await self.send_error_response(writer, "Failed to update identity", str(e))
    
    async def handle_get_identity(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle GET_IDENTITY command"""
        if not self.identity_manager:
            return await self.send_error_response(writer, "Identity manager not available")
        
        try:
            # Format: GET_IDENTITY:agent_id
            parts = command.split(':', 1)
            if len(parts) != 2:
                return await self.send_error_response(writer, "Invalid format. Expected: GET_IDENTITY:agent_id")
            
            agent_id = parts[1]
            identity = self.identity_manager.get_identity(agent_id)
            
            if identity:
                return await self.send_response(writer, {
                    'status': 'identity_found',
                    'identity': identity
                })
            else:
                return await self.send_error_response(writer, f"Identity not found for agent {agent_id}")
            
        except Exception as e:
            logger.error(f"Error getting identity: {e}")
            return await self.send_error_response(writer, "Failed to get identity", str(e))
    
    async def handle_list_identities(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle LIST_IDENTITIES command"""
        if not self.identity_manager:
            return await self.send_error_response(writer, "Identity manager not available")
        
        try:
            identities = self.identity_manager.list_identities()
            
            return await self.send_response(writer, {
                'status': 'identities_listed',
                'identities': identities,
                'count': len(identities)
            })
            
        except Exception as e:
            logger.error(f"Error listing identities: {e}")
            return await self.send_error_response(writer, "Failed to list identities", str(e))
    
    async def handle_remove_identity(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle REMOVE_IDENTITY command"""
        if not self.identity_manager:
            return await self.send_error_response(writer, "Identity manager not available")
        
        try:
            # Format: REMOVE_IDENTITY:agent_id
            parts = command.split(':', 1)
            if len(parts) != 2:
                return await self.send_error_response(writer, "Invalid format. Expected: REMOVE_IDENTITY:agent_id")
            
            agent_id = parts[1]
            success = self.identity_manager.remove_identity(agent_id)
            
            if success:
                return await self.send_response(writer, {
                    'status': 'identity_removed',
                    'agent_id': agent_id
                })
            else:
                return await self.send_error_response(writer, f"Identity not found for agent {agent_id}")
            
        except Exception as e:
            logger.error(f"Error removing identity: {e}")
            return await self.send_error_response(writer, "Failed to remove identity", str(e))