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
    
    def __init__(self, core_daemon, state_manager=None, process_manager=None, agent_manager=None, utils_manager=None, hot_reload_manager=None, message_bus=None):
        # Store references to all managers for cross-module communication
        self.core_daemon = core_daemon
        self.state_manager = state_manager
        self.process_manager = process_manager
        self.agent_manager = agent_manager
        self.utils_manager = utils_manager
        self.hot_reload_manager = hot_reload_manager
        self.message_bus = message_bus
        
        # Command registry - maps command prefixes to handler methods - EXACT copy from daemon_clean.py
        self.handlers = {
            'SPAWN:': self.handle_spawn,
            'SPAWN_ASYNC:': self.handle_spawn_async,
            'RELOAD:': self.handle_reload_module,
            'REGISTER_AGENT:': self.handle_register_agent,
            'SPAWN_AGENT:': self.handle_spawn_agent,
            'GET_AGENTS': self.handle_get_agents,
            'SEND_MESSAGE:': self.handle_send_message,
            'SET_SHARED:': self.handle_set_shared,
            'GET_SHARED:': self.handle_get_shared,
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
            'CONNECT_AGENT:': self.handle_connect_agent,
            'DISCONNECT_AGENT:': self.handle_disconnect_agent,
            'MESSAGE_BUS_STATS': self.handle_message_bus_stats,
            'GET_COMMANDS': self.handle_get_commands
        }
    
    async def handle_command(self, command_text: str, writer: asyncio.StreamWriter) -> bool:
        """Route command to appropriate handler. Returns True if daemon should continue - EXACT copy from daemon_clean.py"""
        try:
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
    
    async def handle_spawn(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle SPAWN command - EXACT copy from daemon_clean.py"""
        logger.info("Processing SPAWN command")
        
        # Parse command format: "SPAWN:[session_id]:<prompt>"
        parts = command[6:].split(':', 1)
        if len(parts) == 2 and parts[0]:
            session_id, prompt = parts[0], parts[1]
        else:
            session_id, prompt = None, command[6:].strip()
        
        logger.info(f"Spawning Claude with prompt: {prompt[:50]}...")
        if self.process_manager:
            result = await self.process_manager.spawn_claude(prompt, session_id)
        else:
            result = {'error': 'No process manager available'}
        logger.info(f"Claude spawn completed")
        
        return await self.send_response(writer, result)
    
    async def handle_spawn_async(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle SPAWN_ASYNC command - EXACT copy from daemon_clean.py"""
        logger.info("Processing SPAWN_ASYNC command")
        
        # Parse format: "SPAWN_ASYNC:[session_id]:[model]:[agent_id]:<prompt>"
        parts = command[12:].split(':', 3)
        if len(parts) == 4:
            session_id = parts[0] if parts[0] else None
            model = parts[1] if parts[1] else 'sonnet'
            agent_id = parts[2] if parts[2] else None
            prompt = parts[3]
        else:
            session_id, model, agent_id = None, 'sonnet', None
            prompt = command[12:].strip()
        
        # Check if agent has a profile with enable_tools setting
        enable_tools = True  # Default to True for backward compatibility
        if agent_id:
            profile_path = Path(f'agent_profiles/{agent_id}.json')
            if profile_path.exists():
                try:
                    with open(profile_path) as f:
                        profile = json.load(f)
                        enable_tools = profile.get('enable_tools', True)
                        logger.info(f"Agent {agent_id} has enable_tools={enable_tools}")
                except Exception as e:
                    logger.warning(f"Could not load profile for {agent_id}: {e}")
        
        if self.process_manager:
            process_id = await self.process_manager.spawn_claude_async(prompt, session_id, model, agent_id, enable_tools)
        else:
            process_id = None
        
        if process_id:
            return await self.send_response(writer, {'process_id': process_id, 'status': 'started'})
        else:
            return await self.send_error_response(writer, 'Failed to start process')
    
    async def handle_reload_module(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle RELOAD command - EXACT copy from daemon_clean.py"""
        module_name = command[7:].strip()
        if self.utils_manager:
            self.utils_manager.reload_module(module_name)
        return await self.send_text_response(writer, 'OK')
    
    async def handle_register_agent(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle REGISTER_AGENT command - EXACT copy from daemon_clean.py"""
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
        """Handle SPAWN_AGENT command - EXACT copy from daemon_clean.py"""
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
        """Handle GET_AGENTS command - EXACT copy from daemon_clean.py"""
        logger.info("Processing GET_AGENTS command")
        if self.agent_manager:
            agents = self.agent_manager.get_all_agents()
            result = await self.send_response(writer, {'agents': agents})
        else:
            result = await self.send_response(writer, {'agents': {}})
        logger.info("Sent GET_AGENTS response")
        return result
    
    async def handle_send_message(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle SEND_MESSAGE command - EXACT copy from daemon_clean.py"""
        # Parse format: "SEND_MESSAGE:from_agent:to_agent:message"
        parts = command[13:].split(':', 2)
        if len(parts) != 3:
            return await self.send_error_response(writer, 'Invalid SEND_MESSAGE format')
        
        from_agent, to_agent, message = parts
        
        if self.agent_manager:
            result = self.agent_manager.log_inter_agent_message(from_agent, to_agent, message)
            return await self.send_response(writer, result)
        else:
            return await self.send_error_response(writer, 'No agent manager available')
    
    async def handle_set_shared(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle SET_SHARED command - EXACT copy from daemon_clean.py"""
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
        """Handle GET_SHARED command - EXACT copy from daemon_clean.py"""
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
        """Handle SUBSCRIBE command for message bus"""
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
        """Handle PUBLISH command for message bus"""
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
    
    async def handle_connect_agent(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle CONNECT_AGENT command"""
        agent_id = command[14:].strip()
        
        if self.message_bus:
            self.message_bus.connect_agent(agent_id, writer)
            return await self.send_response(writer, {
                'status': 'connected',
                'agent_id': agent_id
            })
        else:
            return await self.send_error_response(writer, 'No message bus available')
    
    async def handle_disconnect_agent(self, command: str, writer: asyncio.StreamWriter) -> bool:
        """Handle DISCONNECT_AGENT command"""
        agent_id = command[17:].strip()
        
        if self.message_bus:
            self.message_bus.disconnect_agent(agent_id)
            return await self.send_response(writer, {
                'status': 'disconnected',
                'agent_id': agent_id
            })
        else:
            return await self.send_error_response(writer, 'No message bus available')
    
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
        
        # Extract command info from handlers and their docstrings
        for cmd_prefix, handler_func in self.handlers.items():
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
                        format_match = "SPAWN:[session_id]:<prompt>"
                    elif cmd_name == 'SPAWN_ASYNC':
                        format_match = "SPAWN_ASYNC:[session_id]:[model]:[agent_id]:<prompt>"
                    elif cmd_name == 'SUBSCRIBE':
                        format_match = "SUBSCRIBE:agent_id:event_type1,event_type2,..."
                    elif cmd_name == 'PUBLISH':
                        format_match = "PUBLISH:from_agent:event_type:json_payload"
                    elif cmd_name == 'REGISTER_AGENT':
                        format_match = "REGISTER_AGENT:agent_id:role:capabilities"
                    elif cmd_name == 'SPAWN_AGENT':
                        format_match = "SPAWN_AGENT:profile_name:task:context:agent_id"
                    elif cmd_name == 'SEND_MESSAGE':
                        format_match = "SEND_MESSAGE:from_agent:to_agent:message"
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
                    elif cmd_name == 'CONNECT_AGENT':
                        format_match = "CONNECT_AGENT:agent_id"
                    elif cmd_name == 'DISCONNECT_AGENT':
                        format_match = "DISCONNECT_AGENT:agent_id"
                    else:
                        format_match = f"{cmd_name}:<parameters>"
                
                cmd_key = cmd_prefix[:-1]
            else:
                # Commands without colons (like HEALTH_CHECK, SHUTDOWN)
                format_match = cmd_prefix
                cmd_key = cmd_prefix
            
            commands[cmd_key] = {
                "format": format_match,
                "description": description
            }
        
        result = {
            "commands": commands,
            "total_commands": len(commands)
        }
        
        logger.info(f"Returning {len(commands)} command definitions")
        return await self.send_response(writer, result)