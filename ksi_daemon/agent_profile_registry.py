#!/usr/bin/env python3

"""
Agent Profile Registry - Agent profile management and task routing
Manages agent profiles, capabilities, and routes tasks to appropriate agents
"""

import json
import uuid
import warnings
from typing import Dict, Any, Optional, List
from pathlib import Path
from .manager_framework import BaseManager, with_error_handling, log_operation
from .file_operations import FileOperations, LogEntry
from .timestamp_utils import TimestampManager
from .config import config

class AgentProfileRegistry(BaseManager):
    """Registry for agent profiles, capabilities, and task routing"""
    
    def __init__(self, completion_manager=None):
        self.completion_manager = completion_manager
        super().__init__(
            manager_name="agent",
            required_dirs=["agent_profiles"]  # session_logs handled by config system
        )
    
    def _initialize(self):
        """Initialize manager-specific state"""
        self.agents = {}  # agent_id -> agent_info
    
    @log_operation()
    def load_agent_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """Load agent profile from agent_profiles directory - DEPRECATED: Use composition system instead"""
        import warnings
        warnings.warn("load_agent_profile is deprecated. Use composition system instead.", DeprecationWarning, stacklevel=2)
        
        try:
            profile_path = f'agent_profiles/{profile_name}.json'
            with open(profile_path, 'r') as f:
                profile = json.load(f)
            return profile
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.error(f"Failed to load agent profile {profile_name}: {e}")
            return None
    
    def format_agent_prompt(self, profile: dict, task: str, context: str = "", agents: dict = None) -> str:
        """Format agent prompt using profile template - DEPRECATED: Use composition system instead"""
        import warnings
        warnings.warn("format_agent_prompt is deprecated. Use composition system instead.", DeprecationWarning, stacklevel=2)
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
    
    @log_operation()
    @with_error_handling("spawn_agent")
    async def spawn_agent(self, profile_name: str, task: str, context: str = "", agent_id: str = None) -> Optional[str]:
        """Spawn an agent using a profile template - DEPRECATED: Use spawn_agent_with_composition instead"""
        import warnings
        warnings.warn("spawn_agent is deprecated. Use spawn_agent_with_composition instead.", DeprecationWarning, stacklevel=2)
        profile = self.load_agent_profile(profile_name)
        if not profile:
            return None
        
        # Generate agent_id if not provided
        if not agent_id:
            import uuid
            agent_id = f"{profile_name}_{str(uuid.uuid4())[:8]}"
        
        # Spawn agent process (agent_process.py) instead of raw Claude
        # This allows agents to participate in the message bus system
        if self.completion_manager:
            process_id = await self.completion_manager.spawn_agent(agent_id, profile_name)
        else:
            self.logger.error("No process manager available for spawning agent")
            return None
        
        if process_id:
            # Register agent with capabilities from profile
            self.agents[agent_id] = {
                'profile': profile_name,
                'role': profile.get('role', profile_name),
                'capabilities': profile.get('capabilities', []),
                'status': 'active',
                'model': profile.get('model', 'sonnet'),
                'process_id': process_id,
                'initial_task': task,  # Save for reference
                'initial_context': context,  # Save for reference
                'created_at': TimestampManager.timestamp_utc(),
                'sessions': []
            }
            self.logger.info(f"Spawned agent {agent_id} using profile {profile_name} with initial task: {task}")
        
        return process_id
    
    @log_operation()
    @with_error_handling("spawn_agent_with_composition")
    async def spawn_agent_with_composition(self, composition_name: str, task: str, context: str = "", agent_id: str = None, profile_fallback: str = None) -> Optional[str]:
        """Spawn an agent using composition-based approach with profile fallback"""
        # First try to find an existing profile that references this composition
        composition_profile = None
        for profile_file in Path('agent_profiles').glob('*.json'):
            try:
                with open(profile_file) as f:
                    profile = json.load(f)
                    if profile.get('composition') == composition_name:
                        composition_profile = profile
                        break
            except (json.JSONDecodeError, FileNotFoundError):
                continue
        
        # If no profile references this composition, create a minimal profile
        if not composition_profile:
            self.logger.info(f"No existing profile found for composition '{composition_name}', creating minimal profile")
            composition_profile = {
                'name': composition_name,
                'role': composition_name.replace('_', ' ').title(),
                'model': 'sonnet',
                'composition': composition_name,
                'capabilities': [],  # Will be determined by composition
                'enable_tools': True  # Default to enabled
            }
        
        # Generate agent_id if not provided
        if not agent_id:
            import uuid
            agent_id = f"{composition_name}_{str(uuid.uuid4())[:8]}"
        
        # Spawn agent process using composition
        if self.completion_manager:
            # Pass composition name as the "profile" - agent_process.py will handle it
            process_id = await self.completion_manager.spawn_agent(agent_id, composition_name)
        else:
            self.logger.error("No process manager available for spawning agent")
            return None
        
        if process_id:
            # Register agent with information from composition profile
            self.agents[agent_id] = {
                'composition': composition_name,
                'profile_fallback': profile_fallback,
                'role': composition_profile.get('role', composition_name),
                'capabilities': composition_profile.get('capabilities', []),
                'status': 'active',
                'model': composition_profile.get('model', 'sonnet'),
                'process_id': process_id,
                'initial_task': task,
                'initial_context': context,
                'created_at': TimestampManager.timestamp_utc(),
                'sessions': []
            }
            self.logger.info(f"Spawned agent {agent_id} using composition {composition_name} with initial task: {task}")
        
        return process_id
    
    @log_operation()
    def register_agent(self, agent_id: str, role: str, capabilities: str = "") -> Dict[str, Any]:
        """Register an agent (legacy method for compatibility)"""
        agent_id = self.create_agent({
            'agent_id': agent_id,
            'role': role,
            'capabilities': capabilities
        })
        return {'status': 'registered', 'agent_id': agent_id}
    
    def create_agent(self, agent_data: Dict[str, Any]) -> str:
        """Create agent (standardized API)"""
        agent_id = agent_data.get('agent_id') or str(uuid.uuid4())[:8]
        capabilities = agent_data.get('capabilities', '')
        
        self.agents[agent_id] = {
            'role': agent_data.get('role', 'assistant'),
            'capabilities': capabilities.split(',') if isinstance(capabilities, str) else capabilities,
            'status': agent_data.get('status', 'active'),
            'created_at': TimestampManager.timestamp_utc(),
            'sessions': []
        }
        
        self.logger.info(f"Created agent {agent_id}")
        return agent_id
    
    def update_agent(self, agent_id: str, agent_data: Dict[str, Any]) -> bool:
        """Update agent (standardized API)"""
        if agent_id not in self.agents:
            return False
        
        # Update only provided fields
        agent = self.agents[agent_id]
        for key, value in agent_data.items():
            if key != 'agent_id':  # Don't allow changing ID
                agent[key] = value
        
        return True
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List all agents (standardized API)"""
        from typing import List
        return [
            {
                'agent_id': agent_id,
                'role': info.get('role'),
                'status': info.get('status'),
                'capabilities': info.get('capabilities', [])
            }
            for agent_id, info in self.agents.items()
        ]
    
    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get specific agent (standardized API)"""
        from typing import Optional
        return self.agents.get(agent_id)
    
    def remove_agent(self, agent_id: str) -> bool:
        """Remove agent (standardized API)"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            return True
        return False
    
    def clear_agents(self) -> int:
        """Clear all agents (standardized API)"""
        count = len(self.agents)
        self.agents.clear()
        return count
    
    def find_agents_by_capability(self, required_capabilities: list) -> list:
        """Find agents that have the required capabilities - EXACT copy from daemon_clean.py"""
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
    
    @log_operation()
    @with_error_handling("route_task")
    async def route_task(self, task: str, required_capabilities: List[str], context: str = "") -> Dict[str, Any]:
        """Route a task to the most suitable available agent - EXACT copy from daemon_clean.py"""
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
            "timestamp": TimestampManager.timestamp_utc(),
            "type": "task_routing",
            "task": task,
            "required_capabilities": required_capabilities,
            "assigned_agent": agent_id,
            "agent_capabilities": best_agent['capabilities'],
            "match_score": best_agent['match_score']
        }
        
        log_file = str(config.session_log_dir / 'task_routing.jsonl')
        FileOperations.append_jsonl(log_file, routing_entry)
        
        self.logger.info(f"Routed task to agent {agent_id} (score: {best_agent['match_score']})")
        
        return {
            'status': 'routed',
            'assigned_agent': agent_id,
            'agent_role': best_agent['role'],
            'match_score': best_agent['match_score'],
            'message': message
        }
    
    def log_inter_agent_message(self, from_agent: str, to_agent: str, message: str) -> dict:
        """Log inter-agent message - EXACT logic from daemon_clean.py command handler"""
        # Log the inter-agent message
        message_entry = {
            "timestamp": TimestampManager.timestamp_utc(),
            "type": "inter_agent_message",
            "from_agent": from_agent,
            "to_agent": to_agent,
            "message": message
        }
        
        # Save to inter-agent log
        log_file = str(config.session_log_dir / 'inter_agent_messages.jsonl')
        FileOperations.append_jsonl(log_file, message_entry)
        
        self.logger.info(f"Inter-agent message from {from_agent} to {to_agent}")
        return {'status': 'message_logged', 'from': from_agent, 'to': to_agent}
    
    def get_all_agents(self) -> dict:
        """Get all registered agents"""
        return self.agents.copy()
    
    def update_agent_session(self, agent_id: str, session_id: str):
        """Update agent with new session - called from process completion"""
        if agent_id in self.agents:
            if agent_id not in self.agents:
                self.agents[agent_id] = {
                    'created_at': TimestampManager.timestamp_utc(),
                    'sessions': []
                }
            self.agents[agent_id]['sessions'].append(session_id)
            self.agents[agent_id]['last_active'] = TimestampManager.timestamp_utc()
    
    def serialize_state(self) -> dict:
        """Serialize agent state for hot reload"""
        return {'agents': self.agents}
    
    def deserialize_state(self, state: dict):
        """Deserialize agent state from hot reload"""
        self.agents = state.get('agents', {})
        self.logger.info(f"Loaded agents: {len(self.agents)} agents")