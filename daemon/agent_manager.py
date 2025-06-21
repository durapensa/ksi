#!/usr/bin/env python3

"""
Agent Manager - Agent lifecycle and task routing
Extracted from daemon_clean.py with 100% functionality preservation
"""

import json
import os
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger('daemon')

class AgentManager:
    """Manages agent lifecycle, capabilities, and task routing"""
    
    def __init__(self, process_manager=None):
        self.agents = {}  # agent_id -> agent_info
        self.process_manager = process_manager
        
        # Ensure directories exist
        os.makedirs('agent_profiles', exist_ok=True)
        os.makedirs('claude_logs', exist_ok=True)
    
    def load_agent_profile(self, profile_name: str) -> dict:
        """Load agent profile from agent_profiles directory - EXACT copy from daemon_clean.py"""
        try:
            profile_path = f'agent_profiles/{profile_name}.json'
            with open(profile_path, 'r') as f:
                profile = json.load(f)
            return profile
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load agent profile {profile_name}: {e}")
            return None
    
    def format_agent_prompt(self, profile: dict, task: str, context: str = "", agents: dict = None) -> str:
        """Format agent prompt using profile template - EXACT copy from daemon_clean.py"""
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
        """Spawn an agent using a profile template - EXACT copy from daemon_clean.py"""
        profile = self.load_agent_profile(profile_name)
        if not profile:
            return None
        
        # Generate agent_id if not provided
        if not agent_id:
            import uuid
            agent_id = f"{profile_name}_{str(uuid.uuid4())[:8]}"
        
        # Spawn agent process (agent_process.py) instead of raw Claude
        # This allows agents to participate in the message bus system
        if self.process_manager:
            process_id = await self.process_manager.spawn_agent_process_async(agent_id, profile_name)
        else:
            logger.error("No process manager available for spawning agent")
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
                'created_at': datetime.utcnow().isoformat() + "Z",
                'sessions': []
            }
            logger.info(f"Spawned agent {agent_id} using profile {profile_name} with initial task: {task}")
        
        return process_id
    
    def register_agent(self, agent_id: str, role: str, capabilities: str = "") -> dict:
        """Register an agent manually - EXACT logic from daemon_clean.py command handler"""
        self.agents[agent_id] = {
            'role': role,
            'capabilities': capabilities.split(',') if capabilities else [],
            'status': 'active',
            'created_at': datetime.utcnow().isoformat() + "Z",
            'sessions': []
        }
        
        logger.info(f"Registered agent {agent_id} with role {role}")
        return {'status': 'registered', 'agent_id': agent_id}
    
    def get_agents(self) -> dict:
        """Get all registered agents"""
        return self.agents.copy()
    
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
    
    async def route_task(self, task: str, required_capabilities: list, context: str = "") -> dict:
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
    
    def log_inter_agent_message(self, from_agent: str, to_agent: str, message: str) -> dict:
        """Log inter-agent message - EXACT logic from daemon_clean.py command handler"""
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
        
        logger.info(f"Inter-agent message from {from_agent} to {to_agent}")
        return {'status': 'message_logged', 'from': from_agent, 'to': to_agent}
    
    def get_all_agents(self) -> dict:
        """Get all registered agents"""
        return self.agents.copy()
    
    def update_agent_session(self, agent_id: str, session_id: str):
        """Update agent with new session - called from process completion"""
        if agent_id in self.agents:
            if agent_id not in self.agents:
                self.agents[agent_id] = {
                    'created_at': datetime.utcnow().isoformat() + "Z",
                    'sessions': []
                }
            self.agents[agent_id]['sessions'].append(session_id)
            self.agents[agent_id]['last_active'] = datetime.utcnow().isoformat() + "Z"
    
    def serialize_state(self) -> dict:
        """Serialize agent state for hot reload"""
        return {'agents': self.agents}
    
    def deserialize_state(self, state: dict):
        """Deserialize agent state from hot reload"""
        self.agents = state.get('agents', {})
        logger.info(f"Loaded agents: {len(self.agents)} agents")