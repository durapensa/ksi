#!/usr/bin/env python3
"""
JSON Command Handlers - Clean implementation for JSON protocol v2.0
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger('daemon')

class CommandHandlers:
    """JSON protocol command handlers for the daemon"""
    
    def __init__(self, command_handler):
        # Reference to main command handler for access to managers
        self.cmd_handler = command_handler
    
    # Process Control Commands
    
    async def _handle_spawn(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle SPAWN command with JSON parameters"""
        mode = parameters.get("mode")
        process_type = parameters.get("type")
        session_id = parameters.get("session_id")
        model = parameters.get("model", "sonnet")
        agent_id = parameters.get("agent_id")
        prompt = parameters.get("prompt")
        enable_tools = parameters.get("enable_tools", True)
        
        if mode == "sync":
            return await self._spawn_sync(writer, session_id, model, agent_id, prompt, enable_tools)
        elif mode == "async":
            return await self._spawn_async(writer, session_id, model, agent_id, prompt, enable_tools)
        else:
            return await self.cmd_handler.send_error_response(writer, "INVALID_MODE", f"Invalid mode: {mode}")
    
    async def _spawn_sync(self, writer, session_id, model, agent_id, prompt, enable_tools):
        """Handle synchronous Claude spawning"""
        logger.info(f"Synchronous Claude spawn: {prompt[:50]}...")
        
        if self.cmd_handler.process_manager:
            result = await self.cmd_handler.process_manager.spawn_claude(prompt, session_id, model, agent_id, enable_tools)
        else:
            result = {'error': 'No process manager available'}
            
        return await self.cmd_handler.send_response(writer, {
            'status': 'success',
            'command': 'SPAWN',
            'result': result
        })
    
    async def _spawn_async(self, writer, session_id, model, agent_id, prompt, enable_tools):
        """Handle asynchronous Claude spawning"""
        logger.info(f"Asynchronous Claude spawn: {prompt[:50]}...")
        
        if self.cmd_handler.process_manager:
            process_id = await self.cmd_handler.process_manager.spawn_claude_async(prompt, session_id, model, agent_id, enable_tools)
        else:
            process_id = None
        
        if process_id:
            return await self.cmd_handler.send_response(writer, {
                'status': 'success',
                'command': 'SPAWN',
                'result': {
                    'process_id': process_id,
                    'status': 'started',
                    'type': 'claude',
                    'mode': 'async'
                }
            })
        else:
            return await self.cmd_handler.send_error_response(writer, "SPAWN_FAILED", "Failed to start Claude process")
    
    async def _handle_cleanup(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle CLEANUP command"""
        cleanup_type = parameters.get("cleanup_type")
        
        if self.cmd_handler.utils_manager:
            result = self.cmd_handler.utils_manager.cleanup(cleanup_type)
            return await self.cmd_handler.send_response(writer, {
                'status': 'success',
                'command': 'CLEANUP',
                'result': {
                    'status': 'cleaned',
                    'cleanup_type': cleanup_type,
                    'details': result
                }
            })
        else:
            return await self.cmd_handler.send_error_response(writer, "NO_UTILS_MANAGER", "Utils manager not available")
    
    async def _handle_reload(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle RELOAD command"""
        module_name = parameters.get("module_name")
        
        if self.cmd_handler.utils_manager:
            self.cmd_handler.utils_manager.reload_module(module_name)
            return await self.cmd_handler.send_response(writer, {
                'status': 'success',
                'command': 'RELOAD',
                'result': {
                    'status': 'reloaded',
                    'module': module_name,
                    'message': 'Module reloaded successfully'
                }
            })
        else:
            return await self.cmd_handler.send_error_response(writer, "NO_UTILS_MANAGER", "Utils manager not available")
    
    # Agent Management Commands
    
    async def _handle_register_agent(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle REGISTER_AGENT command"""
        agent_id = parameters.get("agent_id")
        role = parameters.get("role")
        capabilities = parameters.get("capabilities", [])
        
        if self.cmd_handler.agent_manager:
            # Convert list back to string for compatibility
            capabilities_str = ",".join(capabilities) if isinstance(capabilities, list) else capabilities
            result = self.cmd_handler.agent_manager.register_agent(agent_id, role, capabilities_str)
            
            return await self.cmd_handler.send_response(writer, {
                'status': 'success',
                'command': 'REGISTER_AGENT',
                'result': result
            })
        else:
            return await self.cmd_handler.send_error_response(writer, "NO_AGENT_MANAGER", "Agent manager not available")
    
    async def _handle_get_agents(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle GET_AGENTS command"""
        if self.cmd_handler.agent_manager:
            agents = self.cmd_handler.agent_manager.get_all_agents()
            return await self.cmd_handler.send_response(writer, {
                'status': 'success',
                'command': 'GET_AGENTS',
                'result': {'agents': agents}
            })
        else:
            return await self.cmd_handler.send_response(writer, {
                'status': 'success',
                'command': 'GET_AGENTS',
                'result': {'agents': {}}
            })
    
    async def _handle_spawn_agent(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle SPAWN_AGENT command"""
        profile_name = parameters.get("profile_name")
        task = parameters.get("task")
        context = parameters.get("context", "")
        agent_id = parameters.get("agent_id")
        
        if self.cmd_handler.agent_manager:
            process_id = await self.cmd_handler.agent_manager.spawn_agent(profile_name, task, context, agent_id)
        else:
            process_id = None
        
        if process_id:
            return await self.cmd_handler.send_response(writer, {
                'status': 'success',
                'command': 'SPAWN_AGENT',
                'result': {
                    'status': 'spawned',
                    'process_id': process_id,
                    'agent_id': agent_id or f"{profile_name}_{process_id[:8]}"
                }
            })
        else:
            return await self.cmd_handler.send_error_response(writer, "SPAWN_AGENT_FAILED", f"Failed to spawn agent with profile {profile_name}")
    
    async def _handle_route_task(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle ROUTE_TASK command"""
        task = parameters.get("task")
        required_capabilities = parameters.get("required_capabilities", [])
        context = parameters.get("context", "")
        
        if self.cmd_handler.agent_manager:
            result = await self.cmd_handler.agent_manager.route_task(task, required_capabilities, context)
            return await self.cmd_handler.send_response(writer, {
                'status': 'success',
                'command': 'ROUTE_TASK',
                'result': result
            })
        else:
            return await self.cmd_handler.send_error_response(writer, "NO_AGENT_MANAGER", "Agent manager not available")
    
    # Message Bus Commands
    
    async def _handle_subscribe(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle SUBSCRIBE command"""
        agent_id = parameters.get("agent_id")
        event_types = parameters.get("event_types", [])
        
        if self.cmd_handler.message_bus:
            success = self.cmd_handler.message_bus.subscribe(agent_id, event_types)
            if success:
                return await self.cmd_handler.send_response(writer, {
                    'status': 'success',
                    'command': 'SUBSCRIBE',
                    'result': {
                        'status': 'subscribed',
                        'agent_id': agent_id,
                        'event_types': event_types
                    }
                })
            else:
                return await self.cmd_handler.send_error_response(writer, "SUBSCRIBE_FAILED", f"Agent {agent_id} not connected")
        else:
            return await self.cmd_handler.send_error_response(writer, "NO_MESSAGE_BUS", "Message bus not available")
    
    async def _handle_publish(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle PUBLISH command"""
        from_agent = parameters.get("from_agent")
        event_type = parameters.get("event_type")
        payload = parameters.get("payload")
        
        if self.cmd_handler.message_bus:
            result = await self.cmd_handler.message_bus.publish(from_agent, event_type, payload)
            return await self.cmd_handler.send_response(writer, {
                'status': 'success',
                'command': 'PUBLISH',
                'result': result
            })
        else:
            return await self.cmd_handler.send_error_response(writer, "NO_MESSAGE_BUS", "Message bus not available")
    
    async def _handle_agent_connection(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle AGENT_CONNECTION command"""
        action = parameters.get("action")
        agent_id = parameters.get("agent_id")
        
        if action == "connect":
            if self.cmd_handler.message_bus:
                self.cmd_handler.message_bus.connect_agent(agent_id, writer)
                return await self.cmd_handler.send_response(writer, {
                    'status': 'success',
                    'command': 'AGENT_CONNECTION',
                    'result': {
                        'status': 'connected',
                        'agent_id': agent_id,
                        'action': 'connect'
                    }
                })
            else:
                return await self.cmd_handler.send_error_response(writer, "NO_MESSAGE_BUS", "Message bus not available")
        
        elif action == "disconnect":
            if self.cmd_handler.message_bus:
                self.cmd_handler.message_bus.disconnect_agent(agent_id)
                return await self.cmd_handler.send_response(writer, {
                    'status': 'success',
                    'command': 'AGENT_CONNECTION',
                    'result': {
                        'status': 'disconnected',
                        'agent_id': agent_id,
                        'action': 'disconnect'
                    }
                })
            else:
                return await self.cmd_handler.send_error_response(writer, "NO_MESSAGE_BUS", "Message bus not available")
        else:
            return await self.cmd_handler.send_error_response(writer, "INVALID_ACTION", f"Invalid action: {action}")
    
    # State Management Commands
    
    async def _handle_set_shared(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle SET_SHARED command"""
        key = parameters.get("key")
        value = parameters.get("value")
        
        if self.cmd_handler.state_manager:
            self.cmd_handler.state_manager.set_shared_state(key, value)
            return await self.cmd_handler.send_response(writer, {
                'status': 'success',
                'command': 'SET_SHARED',
                'result': {
                    'status': 'set',
                    'key': key
                }
            })
        else:
            return await self.cmd_handler.send_error_response(writer, "NO_STATE_MANAGER", "State manager not available")
    
    async def _handle_get_shared(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle GET_SHARED command"""
        key = parameters.get("key")
        
        if self.cmd_handler.state_manager:
            value = self.cmd_handler.state_manager.get_shared_state(key)
            return await self.cmd_handler.send_response(writer, {
                'status': 'success',
                'command': 'GET_SHARED',
                'result': {
                    'key': key,
                    'value': value
                }
            })
        else:
            return await self.cmd_handler.send_error_response(writer, "NO_STATE_MANAGER", "State manager not available")
    
    async def _handle_load_state(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle LOAD_STATE command"""
        state_data = parameters.get("state_data")
        
        try:
            if self.cmd_handler.hot_reload_manager:
                self.cmd_handler.hot_reload_manager.deserialize_state(state_data)
            
            return await self.cmd_handler.send_response(writer, {
                'status': 'success',
                'command': 'LOAD_STATE',
                'result': {
                    'status': 'loaded',
                    'message': 'State loaded successfully',
                    'state_keys': list(state_data.keys()) if isinstance(state_data, dict) else None
                }
            })
        except Exception as e:
            return await self.cmd_handler.send_error_response(writer, "LOAD_STATE_FAILED", str(e))
    
    # System Status Commands
    
    async def _handle_health_check(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle HEALTH_CHECK command"""
        return await self.cmd_handler.send_response(writer, {
            'status': 'success',
            'command': 'HEALTH_CHECK',
            'result': {
                'status': 'healthy',
                'message': 'HEALTHY',
                'uptime_info': 'Daemon is running normally'
            }
        })
    
    async def _handle_get_processes(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle GET_PROCESSES command"""
        if self.cmd_handler.process_manager:
            processes = self.cmd_handler.process_manager.get_running_processes()
            return await self.cmd_handler.send_response(writer, {
                'status': 'success',
                'command': 'GET_PROCESSES',
                'result': {'processes': processes}
            })
        else:
            return await self.cmd_handler.send_response(writer, {
                'status': 'success',
                'command': 'GET_PROCESSES',
                'result': {'processes': {}}
            })
    
    async def _handle_message_bus_stats(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle MESSAGE_BUS_STATS command"""
        if self.cmd_handler.message_bus:
            stats = self.cmd_handler.message_bus.get_stats()
            return await self.cmd_handler.send_response(writer, {
                'status': 'success',
                'command': 'MESSAGE_BUS_STATS',
                'result': stats
            })
        else:
            return await self.cmd_handler.send_response(writer, {
                'status': 'success',
                'command': 'MESSAGE_BUS_STATS',
                'result': {'error': 'Message bus not available'}
            })
    
    async def _handle_get_commands(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle GET_COMMANDS command"""
        # Import here to avoid circular dependency
        from .command_schemas import COMMAND_MAPPINGS, CommandType
        
        # Build command info from schemas
        commands = {}
        for cmd_name, cmd_type in COMMAND_MAPPINGS.items():
            commands[cmd_name] = {
                "type": cmd_type.value,
                "protocol": "JSON v2.0"
            }
        
        return await self.cmd_handler.send_response(writer, {
            'status': 'success',
            'command': 'GET_COMMANDS',
            'result': {
                'commands': commands,
                'total_commands': len(commands),
                'protocol_version': '2.0'
            }
        })
    
    # System Control Commands
    
    async def _handle_reload_daemon(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle RELOAD_DAEMON command"""
        if self.cmd_handler.hot_reload_manager:
            result = await self.cmd_handler.hot_reload_manager.hot_reload_daemon()
            return await self.cmd_handler.send_response(writer, {
                'status': 'success',
                'command': 'RELOAD_DAEMON',
                'result': result
            })
        else:
            return await self.cmd_handler.send_error_response(writer, "NO_HOT_RELOAD_MANAGER", "Hot reload manager not available")
    
    async def _handle_shutdown(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle SHUTDOWN command"""
        logger.info("Received SHUTDOWN command")
        await self.cmd_handler.send_response(writer, {
            'status': 'success',
            'command': 'SHUTDOWN',
            'result': {
                'status': 'shutting_down',
                'message': 'SHUTTING DOWN',
                'details': 'Daemon shutdown initiated'
            }
        })
        writer.close()
        await writer.wait_closed()
        if self.cmd_handler.core_daemon:
            self.cmd_handler.core_daemon.shutdown_event.set()
        return False  # Signal to stop handling
    
    # Identity Management Commands
    
    async def _handle_create_identity(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle CREATE_IDENTITY command"""
        if not self.cmd_handler.identity_manager:
            return await self.cmd_handler.send_error_response(writer, "NO_IDENTITY_MANAGER", "Identity manager not available")
        
        try:
            agent_id = parameters.get("agent_id")
            display_name = parameters.get("display_name")
            role = parameters.get("role")
            personality_traits = parameters.get("personality_traits")
            
            identity = self.cmd_handler.identity_manager.create_identity(
                agent_id=agent_id,
                display_name=display_name,
                role=role,
                personality_traits=personality_traits
            )
            
            return await self.cmd_handler.send_response(writer, {
                'status': 'success',
                'command': 'CREATE_IDENTITY',
                'result': {
                    'status': 'identity_created',
                    'identity': identity
                }
            })
        except Exception as e:
            return await self.cmd_handler.send_error_response(writer, "CREATE_IDENTITY_FAILED", str(e))
    
    async def _handle_update_identity(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle UPDATE_IDENTITY command"""
        if not self.cmd_handler.identity_manager:
            return await self.cmd_handler.send_error_response(writer, "NO_IDENTITY_MANAGER", "Identity manager not available")
        
        try:
            agent_id = parameters.get("agent_id")
            updates = parameters.get("updates")
            
            identity = self.cmd_handler.identity_manager.update_identity(agent_id, updates)
            
            if identity:
                return await self.cmd_handler.send_response(writer, {
                    'status': 'success',
                    'command': 'UPDATE_IDENTITY',
                    'result': {
                        'status': 'identity_updated',
                        'identity': identity
                    }
                })
            else:
                return await self.cmd_handler.send_error_response(writer, "IDENTITY_NOT_FOUND", f"Identity not found for agent {agent_id}")
        except Exception as e:
            return await self.cmd_handler.send_error_response(writer, "UPDATE_IDENTITY_FAILED", str(e))
    
    async def _handle_get_identity(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle GET_IDENTITY command"""
        if not self.cmd_handler.identity_manager:
            return await self.cmd_handler.send_error_response(writer, "NO_IDENTITY_MANAGER", "Identity manager not available")
        
        try:
            agent_id = parameters.get("agent_id")
            identity = self.cmd_handler.identity_manager.get_identity(agent_id)
            
            if identity:
                return await self.cmd_handler.send_response(writer, {
                    'status': 'success',
                    'command': 'GET_IDENTITY',
                    'result': {
                        'status': 'identity_found',
                        'identity': identity
                    }
                })
            else:
                return await self.cmd_handler.send_error_response(writer, "IDENTITY_NOT_FOUND", f"Identity not found for agent {agent_id}")
        except Exception as e:
            return await self.cmd_handler.send_error_response(writer, "GET_IDENTITY_FAILED", str(e))
    
    async def _handle_list_identities(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle LIST_IDENTITIES command"""
        if not self.cmd_handler.identity_manager:
            return await self.cmd_handler.send_error_response(writer, "NO_IDENTITY_MANAGER", "Identity manager not available")
        
        try:
            identities = self.cmd_handler.identity_manager.list_identities()
            
            return await self.cmd_handler.send_response(writer, {
                'status': 'success',
                'command': 'LIST_IDENTITIES',
                'result': {
                    'status': 'identities_listed',
                    'identities': identities,
                    'count': len(identities)
                }
            })
        except Exception as e:
            return await self.cmd_handler.send_error_response(writer, "LIST_IDENTITIES_FAILED", str(e))
    
    async def _handle_remove_identity(self, parameters: dict, writer: asyncio.StreamWriter, full_command: dict) -> bool:
        """Handle REMOVE_IDENTITY command"""
        if not self.cmd_handler.identity_manager:
            return await self.cmd_handler.send_error_response(writer, "NO_IDENTITY_MANAGER", "Identity manager not available")
        
        try:
            agent_id = parameters.get("agent_id")
            success = self.cmd_handler.identity_manager.remove_identity(agent_id)
            
            if success:
                return await self.cmd_handler.send_response(writer, {
                    'status': 'success',
                    'command': 'REMOVE_IDENTITY',
                    'result': {
                        'status': 'identity_removed',
                        'agent_id': agent_id
                    }
                })
            else:
                return await self.cmd_handler.send_error_response(writer, "IDENTITY_NOT_FOUND", f"Identity not found for agent {agent_id}")
        except Exception as e:
            return await self.cmd_handler.send_error_response(writer, "REMOVE_IDENTITY_FAILED", str(e))