#!/usr/bin/env python3

"""
Orchestration Initialization Router - Flexible message routing for diverse orchestration patterns
"""

from typing import Dict, List, Any, Optional
import structlog
from ksi_common.template_utils import substitute_variables

logger = structlog.get_logger("orchestration.initialization")


class InitializationRouter:
    """Routes initialization messages based on strategy and coordination patterns."""
    
    def __init__(self):
        self.timing_precedence = {
            'immediate': 0,
            'concurrent': 0,
            'after_initialization': 10
        }
    
    def route_messages(self, orchestration_config: Dict[str, Any], agent_list: List[str]) -> List[Dict[str, Any]]:
        """
        Route initialization messages based on orchestration strategy.
        
        Args:
            orchestration_config: Full orchestration configuration
            agent_list: List of agent IDs that were spawned
            
        Returns:
            List of message routing instructions with timing
        """
        initialization = orchestration_config.get('initialization', {})
        strategy = initialization.get('strategy', 'legacy')
        
        logger.info(f"Routing initialization messages with strategy: {strategy}")
        
        if strategy == 'role_based':
            return self._route_role_based(orchestration_config, agent_list)
        elif strategy == 'peer_to_peer':
            return self._route_peer_to_peer(orchestration_config, agent_list)
        elif strategy == 'distributed':
            return self._route_distributed(orchestration_config, agent_list)
        elif strategy == 'custom':
            return self._route_custom(orchestration_config, agent_list)
        elif strategy == 'leader_first':
            return self._route_leader_first(orchestration_config, agent_list)
        elif strategy == 'broadcast':
            return self._route_broadcast(orchestration_config, agent_list)
        else:
            # Legacy behavior - use existing orchestration_logic DSL
            return self._route_legacy(orchestration_config, agent_list)
    
    def _route_role_based(self, config: Dict[str, Any], agents: List[str]) -> List[Dict[str, Any]]:
        """Route messages based on agent roles."""
        initialization = config['initialization']
        roles = initialization.get('roles', {})
        broadcasts = initialization.get('broadcasts', [])
        message_plan = []
        
        logger.info(f"Role-based routing for {len(roles)} roles and {len(agents)} agents")
        
        # Add broadcast messages
        for broadcast in broadcasts:
            message_plan.append({
                'type': 'broadcast',
                'target': 'all',
                'message': broadcast.get('content', ''),
                'timing': broadcast.get('timing', 'immediate'),
                'variables': {}
            })
        
        # Group agents by role
        for role_name, role_config in roles.items():
            role_agents = role_config.get('agents', [])
            message = role_config.get('message', '')
            timing = role_config.get('timing', 'immediate')
            
            # Resolve agent patterns (e.g., "workers" -> actual worker agent IDs)
            resolved_agents = self._resolve_agent_patterns(role_agents, agents, config)
            
            for agent_id in resolved_agents:
                if agent_id in agents:
                    variables = self._extract_role_variables(role_config, agents, agent_id)
                    
                    message_plan.append({
                        'type': 'targeted',
                        'agent_id': agent_id,
                        'role': role_name,
                        'message': message,
                        'timing': timing,
                        'variables': variables
                    })
        
        return self._sequence_by_timing(message_plan)
    
    def _route_peer_to_peer(self, config: Dict[str, Any], agents: List[str]) -> List[Dict[str, Any]]:
        """Route messages for peer-to-peer coordination."""
        initialization = config['initialization']
        peer_message = initialization.get('peer_message', '')
        shared_context = initialization.get('shared_context', {})
        
        logger.info(f"Peer-to-peer routing for {len(agents)} peer agents")
        
        message_plan = []
        for agent_id in agents:
            variables = shared_context.copy()
            variables.update({
                'peer_list': [a for a in agents if a != agent_id],
                'agent_id': agent_id,
                'peer_count': len(agents) - 1,
                'total_agents': len(agents)
            })
            
            message_plan.append({
                'type': 'targeted',
                'agent_id': agent_id,
                'role': 'peer',
                'message': peer_message,
                'timing': 'immediate',
                'variables': variables
            })
        
        return message_plan
    
    def _route_distributed(self, config: Dict[str, Any], agents: List[str]) -> List[Dict[str, Any]]:
        """Route messages for distributed coordination."""
        initialization = config['initialization']
        domains = initialization.get('coordinator_domains', {})
        cross_protocol = initialization.get('cross_coordinator_protocol', '')
        
        logger.info(f"Distributed routing for {len(domains)} coordination domains")
        
        message_plan = []
        coordinator_list = []
        
        # First pass: identify all coordinators
        for domain_name, domain_config in domains.items():
            domain_agents = domain_config.get('agents', [])
            for agent_id in domain_agents:
                if agent_id in agents:
                    coordinator_list.append({
                        'agent_id': agent_id,
                        'domain': domain_config.get('domain', domain_name)
                    })
        
        # Second pass: route domain-specific messages
        for domain_name, domain_config in domains.items():
            domain_agents = domain_config.get('agents', [])
            domain_message = domain_config.get('message', '')
            
            for agent_id in domain_agents:
                if agent_id in agents:
                    variables = {
                        'domain': domain_config.get('domain', domain_name),
                        'domain_name': domain_name,
                        'other_coordinators': [c for c in coordinator_list if c['agent_id'] != agent_id],
                        'coordinator_count': len(coordinator_list),
                        'cross_coordinator_protocol': cross_protocol
                    }
                    
                    # Combine domain message with cross-coordinator protocol
                    full_message = domain_message
                    if cross_protocol:
                        full_message += '\\n\\n' + cross_protocol
                    
                    message_plan.append({
                        'type': 'targeted',
                        'agent_id': agent_id,
                        'role': 'domain_coordinator',
                        'message': full_message,
                        'timing': 'immediate',
                        'variables': variables
                    })
        
        return message_plan
    
    def _route_custom(self, config: Dict[str, Any], agents: List[str]) -> List[Dict[str, Any]]:
        """Route messages using custom routing rules."""
        initialization = config['initialization']
        routing_rules = initialization.get('message_routing', [])
        
        logger.info(f"Custom routing with {len(routing_rules)} rules")
        
        message_plan = []
        for rule in routing_rules:
            pattern = rule.get('pattern', '')
            content = rule.get('content', '')
            target = rule.get('target', 'matched_agents')
            timing = rule.get('timing', 'immediate')
            
            # Evaluate pattern against agents (simplified evaluation)
            matched_agents = self._evaluate_pattern(pattern, agents, config)
            
            if target == 'all_agents':
                target_agents = agents
            elif target == 'matched_agents':
                target_agents = matched_agents
            else:
                target_agents = [target] if target in agents else []
            
            for agent_id in target_agents:
                message_plan.append({
                    'type': 'targeted',
                    'agent_id': agent_id,
                    'role': 'custom',
                    'message': content,
                    'timing': timing,
                    'variables': {'agent_id': agent_id}
                })
        
        return message_plan
    
    def _route_legacy(self, config: Dict[str, Any], agents: List[str]) -> List[Dict[str, Any]]:
        """Route messages using legacy orchestration_logic DSL."""
        orchestration_logic = config.get('orchestration_logic', {})
        
        if not orchestration_logic:
            return []
        
        logger.info("Using legacy orchestration_logic DSL routing")
        
        # Find orchestrator agents (those with 'orchestrator' in component name)
        message_plan = []
        for agent_id, agent_config in config.get('agents', {}).items():
            if agent_id not in agents:
                continue
                
            agent_profile = agent_config.get('profile', '') or agent_config.get('component', '')
            agent_vars = agent_config.get('vars', {})
            has_explicit_prompt = 'prompt' in agent_vars or 'initial_prompt' in agent_vars
            
            # Only send DSL to orchestrators without explicit prompts
            if 'orchestrator' in agent_profile.lower() and not has_explicit_prompt:
                strategy = orchestration_logic.get('strategy', '')
                description = orchestration_logic.get('description', '')
                pattern_name = config.get('name', 'unknown')
                
                dsl_message = f"""## ORCHESTRATION PATTERN: {pattern_name}

{description}

## YOUR ORCHESTRATION STRATEGY (EXECUTE THIS NOW):

{strategy}

## VARIABLES:
{config.get('variables', {})}

## YOUR ROLE:
You are the orchestrator for pattern '{pattern_name}'. 
IMMEDIATELY begin executing the strategy above. 
DO NOT wait for further instructions.
START the orchestration NOW by following the DSL strategy."""
                
                message_plan.append({
                    'type': 'targeted',
                    'agent_id': agent_id,
                    'role': 'legacy_orchestrator',
                    'message': dsl_message,
                    'timing': 'immediate',
                    'variables': {}
                })
        
        return message_plan
    
    def _route_leader_first(self, config: Dict[str, Any], agents: List[str]) -> List[Dict[str, Any]]:
        """Route messages using leader-first strategy."""
        initialization = config['initialization']
        leader = initialization.get('leader', '')
        message = initialization.get('message', '')
        
        logger.info(f"Leader-first routing with leader: {leader}")
        
        message_plan = []
        
        # Map leader role to actual agent ID
        leader_agent_id = None
        for agent_id in agents:
            # Match by role name in agent ID (e.g., "coordinator" matches "orch_123_coordinator")
            if leader in agent_id:
                leader_agent_id = agent_id
                break
        
        if leader_agent_id and message:
            # Extract variables from orchestration config  
            variables = config.get('variables', {}).copy()
            
            # Find worker and other role-based agents
            worker_id = next((a for a in agents if 'worker' in a), None)
            coordinator_id = next((a for a in agents if 'coordinator' in a), None)
            
            variables.update({
                'agent_id': leader_agent_id,
                'leader': leader,
                'all_agents': agents,
                'other_agents': [a for a in agents if a != leader_agent_id],
                'worker_id': worker_id,
                'coordinator_id': coordinator_id
            })
            
            # Substitute variables in the message content
            substituted_message = substitute_variables(message, variables)
            
            message_plan.append({
                'type': 'targeted',
                'agent_id': leader_agent_id,
                'role': 'leader',
                'message': substituted_message,
                'timing': 'immediate',
                'variables': variables
            })
            
            logger.info(f"Scheduled leader message for {leader_agent_id}")
        else:
            logger.warning(f"Leader '{leader}' not found in agents {agents} or no message provided")
        
        return message_plan
    
    def _route_broadcast(self, config: Dict[str, Any], agents: List[str]) -> List[Dict[str, Any]]:
        """Route messages as broadcast to all agents."""
        initialization = config['initialization']
        message = initialization.get('message', '')
        
        logger.info(f"Broadcast routing to {len(agents)} agents")
        
        message_plan = []
        if message:
            for agent_id in agents:
                variables = config.get('variables', {}).copy()
                variables.update({
                    'agent_id': agent_id,
                    'all_agents': agents,
                    'other_agents': [a for a in agents if a != agent_id],
                    'agent_count': len(agents)
                })
                
                # Substitute variables in the message content
                substituted_message = substitute_variables(message, variables)
                
                message_plan.append({
                    'type': 'targeted',
                    'agent_id': agent_id,
                    'role': 'participant',
                    'message': substituted_message,
                    'timing': 'immediate',
                    'variables': variables
                })
        
        return message_plan
    
    def _resolve_agent_patterns(self, role_agents: List[str], actual_agents: List[str], config: Dict[str, Any]) -> List[str]:
        """Resolve agent patterns like 'workers' to actual agent IDs."""
        resolved = []
        
        for pattern in role_agents:
            if pattern in actual_agents:
                # Direct agent ID
                resolved.append(pattern)
            elif pattern == 'workers':
                # Pattern: find agents with 'worker' in their ID
                resolved.extend([a for a in actual_agents if 'worker' in a])
            elif pattern == 'observers':
                # Pattern: find agents with 'observer' in their ID
                resolved.extend([a for a in actual_agents if 'observer' in a])
            elif pattern.endswith('*'):
                # Wildcard pattern
                prefix = pattern[:-1]
                resolved.extend([a for a in actual_agents if a.startswith(prefix)])
        
        return resolved
    
    def _extract_role_variables(self, role_config: Dict[str, Any], all_agents: List[str], agent_id: str) -> Dict[str, Any]:
        """Extract variables for role-based message substitution."""
        variables = role_config.get('variables', {}).copy()
        
        # Add standard variables
        variables.update({
            'agent_id': agent_id,
            'all_agents': all_agents,
            'agent_count': len(all_agents),
            'other_agents': [a for a in all_agents if a != agent_id]
        })
        
        # Add role-specific variables
        role_name = role_config.get('role', 'unknown')
        if role_name == 'coordinator':
            workers = [a for a in all_agents if 'worker' in a]
            variables.update({
                'workers': workers,
                'worker_count': len(workers)
            })
        
        return variables
    
    def _evaluate_pattern(self, pattern: str, agents: List[str], config: Dict[str, Any]) -> List[str]:
        """Evaluate a pattern against agent list (simplified)."""
        # This is a simplified pattern evaluator
        # In a full implementation, this would support complex expressions
        
        matched = []
        for agent_id in agents:
            # Simple pattern matching
            if 'agent_role' in pattern and 'coordinator' in pattern:
                if 'coordinator' in agent_id:
                    matched.append(agent_id)
            elif 'agent_id.startswith' in pattern:
                # Extract prefix from pattern like "agent_id.startswith('specialist_')"
                if 'specialist_' in pattern and agent_id.startswith('specialist_'):
                    matched.append(agent_id)
        
        return matched
    
    def _sequence_by_timing(self, message_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sequence messages based on timing constraints."""
        # Parse timing dependencies
        sequenced = []
        immediate = []
        concurrent = []
        delayed = []
        
        for message in message_plan:
            timing = message.get('timing', 'immediate')
            
            if timing == 'immediate':
                immediate.append(message)
            elif timing == 'concurrent':
                concurrent.append(message)
            elif timing.startswith('after:'):
                # Dependency-based timing
                dependency = timing.split(':', 1)[1]
                message['dependency'] = dependency
                delayed.append(message)
            else:
                # Default to immediate
                immediate.append(message)
        
        # Sequence: immediate -> concurrent -> dependency-resolved
        sequenced.extend(immediate)
        sequenced.extend(concurrent)
        
        # Resolve dependencies (simplified - just append in order)
        sequenced.extend(delayed)
        
        return sequenced