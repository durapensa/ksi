#!/usr/bin/env python3
"""
Orchestration Module - Event-Based Version

Core orchestration engine with declarative patterns.

Provides:
- Pattern loading from YAML compositions
- Agent lifecycle management
- Message routing based on patterns
- Coordination primitives (turn-taking, termination)
- State tracking and checkpointing
"""

import asyncio
import json
import yaml
import uuid
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Set, TypedDict, Literal
from typing_extensions import NotRequired, Required
from dataclasses import dataclass, field
import re

from ksi_daemon.event_system import event_handler, get_router
from ksi_common.timestamps import timestamp_utc, format_for_logging
from ksi_common.config import config
from ksi_common.logging import get_bound_logger

# Orchestration primitives removed - patterns now define their own transformers

# Module state
logger = get_bound_logger("orchestration", version="1.0.0")
orchestrations: Dict[str, 'OrchestrationInstance'] = {}  # Active orchestrations
event_emitter = None  # Set during context


@dataclass
class AgentInfo:
    """Information about an agent in an orchestration."""
    agent_id: str
    profile: str
    prompt_template: Optional[str] = None
    vars: Dict[str, Any] = field(default_factory=dict)
    spawned: bool = False
    spawn_result: Optional[Dict[str, Any]] = None


@dataclass
class RoutingRule:
    """A message routing rule."""
    pattern: str
    from_agent: str
    to_agent: str
    condition: Optional[str] = None
    broadcast: bool = False
    
    def matches(self, event_name: str, from_agent: str) -> bool:
        """Check if this rule matches the event."""
        # Check event pattern
        if not self._matches_pattern(event_name, self.pattern):
            return False
            
        # Check from_agent
        if self.from_agent != "*" and self.from_agent != from_agent:
            return False
            
        return True
    
    def _matches_pattern(self, event_name: str, pattern: str) -> bool:
        """Check if event name matches pattern (supports wildcards)."""
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return event_name.startswith(prefix)
        return event_name == pattern
    
    def get_targets(self, agents: Dict[str, AgentInfo], sender: str) -> List[str]:
        """Get target agents for this rule."""
        if self.broadcast:
            # Send to all agents except sender if to_agent is "!sender"
            if self.to_agent == "!sender":
                return [aid for aid in agents.keys() if aid != sender]
            else:
                return list(agents.keys())
        else:
            # Handle special notations
            if self.to_agent == "!sender":
                # Send to all except sender (non-broadcast)
                return [aid for aid in agents.keys() if aid != sender]
            elif self.to_agent.startswith("!"):
                # Exclude specific agent
                exclude = self.to_agent[1:]
                return [aid for aid in agents.keys() if aid != exclude]
            else:
                # Direct routing
                return [self.to_agent] if self.to_agent in agents else []


@dataclass
class OrchestrationInstance:
    """An active orchestration instance."""
    orchestration_id: str
    pattern_name: str
    pattern: Dict[str, Any]
    agents: Dict[str, AgentInfo] = field(default_factory=dict)
    routing_rules: List[RoutingRule] = field(default_factory=list)
    state: str = "initializing"
    start_time: float = field(default_factory=time.time)
    message_count: int = 0
    vars: Dict[str, Any] = field(default_factory=dict)
    
    # Coordination state
    turn_order: List[str] = field(default_factory=list)
    current_turn: int = 0
    last_activity: float = field(default_factory=time.time)
    
    # New features
    default_routing_target: Optional[str] = None
    
    # Termination tracking
    rounds_completed: int = 0
    termination_conditions: Dict[str, Any] = field(default_factory=dict)


class OrchestrationModule:
    """Core orchestration plugin implementation."""
    
    def __init__(self):
        # Use same pattern as composition service - relative to project root
        self.patterns_dir = Path("var") / "lib" / "compositions" / "orchestrations"
        self.providers = {}
        self._load_providers()
    
    def _load_providers(self):
        """Load optional providers if enabled."""
        # Provider loading not yet implemented
        pass
    
    async def load_pattern(self, pattern_name: str, load_transformers: bool = True) -> Dict[str, Any]:
        """Load an orchestration pattern from YAML."""
        # Try to load via composition service first
        if event_emitter:
            try:
                logger.info(f"Attempting to load orchestration pattern: {pattern_name}")
                # Try exact match first - composition service expects names without "orchestrations/" prefix
                results = await event_emitter("composition:get", {
                    "name": pattern_name,
                    "type": "orchestration"
                })
                # event_emitter returns a list of results from handlers
                result = results[0] if results else None
                logger.info(f"composition:get result for {pattern_name}: {result.get('status') if result else 'None'}")
                if result and result.get('status') == 'success' and 'composition' in result:
                    pattern = result['composition']
                    logger.debug(f"Loaded orchestration pattern {pattern_name} via composition service")
                    # Continue to validation and transformer loading below
                else:
                    raise FileNotFoundError(f"Pattern not found via composition service: {pattern_name}")
            except Exception as e:
                logger.error(f"Failed to load pattern '{pattern_name}' via composition service: {e}")
                # Fall through to direct file access
                pattern = None
        else:
            pattern = None
            
        # Fallback to direct file access
        if pattern is None:
            pattern_file = self.patterns_dir / f"{pattern_name}.yaml"
            
            if not pattern_file.exists():
                # Try with .yml extension
                pattern_file = self.patterns_dir / f"{pattern_name}.yml"
                
            if not pattern_file.exists():
                raise FileNotFoundError(f"Orchestration pattern not found: {pattern_name}")
            
            with open(pattern_file, 'r') as f:
                pattern = yaml.safe_load(f)
        
        # Validate required fields (relaxed - only name is truly required)
        if 'name' not in pattern:
            raise ValueError("Orchestration pattern missing required field: name")
        
        # Load transformers via transformer service if requested and present
        if load_transformers and 'transformers' in pattern and event_emitter:
            try:
                await event_emitter("transformer:load_pattern", {
                    "pattern": pattern_name,
                    "source": "orchestration"
                })
                logger.debug(f"Requested transformer loading for pattern {pattern_name}")
            except Exception as e:
                logger.warning(f"Failed to load transformers for pattern {pattern_name}: {e}")
        
        return pattern
    
    async def _validate_pattern(self, pattern: Dict[str, Any]) -> List[str]:
        """Validate orchestration pattern and return list of errors."""
        errors = []
        
        # Check if agents are defined
        if 'agents' not in pattern:
            # Check if this might be an evaluation pattern with orchestration_logic
            if 'orchestration_logic' in pattern:
                errors.append("This appears to be an evaluation pattern with 'orchestration_logic' DSL. "
                            "Orchestration patterns require an 'agents' section with concrete agent definitions. "
                            "Example: agents: { agent1: { profile: 'base_multi_agent' } }")
            else:
                errors.append("Pattern must define at least one agent in 'agents' section. "
                            "Example: agents: { hello: { profile: 'hello_agent' } }")
        elif not pattern['agents']:
            errors.append("The 'agents' section is empty. At least one agent must be defined. "
                        "Example: agents: { agent1: { profile: 'base_multi_agent' } }")
        
        # Get available compositions for validation - unified architecture principle
        available_profiles = set()
        if event_emitter:
            try:
                # Get ALL compositions regardless of type - everything is a composition
                results = await event_emitter("composition:discover", {"limit": 1000})
                result = results[0] if results else None
                if result and isinstance(result, dict) and 'compositions' in result:
                    for comp in result['compositions']:
                        available_profiles.add(comp.get('name', ''))
            except Exception as e:
                logger.warning(f"Could not fetch available profiles for validation: {e}")
        
        # Validate agent profiles
        agents = pattern.get('agents', {})
        for agent_name, agent_config in agents.items():
            if not isinstance(agent_config, dict):
                errors.append(f"Agent '{agent_name}' must be a dictionary with at least a 'profile' field")
                continue
                
            # Support both 'profile' and 'component' fields
            profile = agent_config.get('profile') or agent_config.get('component')
            if agent_config.get('component'):
                # Component field takes precedence
                profile = agent_config.get('component')
            if not profile:
                errors.append(f"Agent '{agent_name}' missing required 'component' or 'profile' field. "
                            f"Example: component: 'components/core/base_agent'")
            elif available_profiles and profile not in available_profiles:
                # Find similar components
                similar = [p for p in available_profiles if profile.lower() in p.lower() or p.lower() in profile.lower()]
                if similar:
                    errors.append(f"Agent '{agent_name}' references unknown component: '{profile}'. "
                                f"Did you mean one of these? {', '.join(sorted(similar)[:5])}")
                else:
                    errors.append(f"Agent '{agent_name}' references unknown component: '{profile}'. "
                                f"Available components include: {', '.join(sorted(list(available_profiles))[:10])}...")
        
        # Validate routing rules
        routing = pattern.get('routing', {})
        if routing and 'rules' in routing:
            for i, rule in enumerate(routing['rules']):
                if not isinstance(rule, dict):
                    errors.append(f"Routing rule {i} must be a dictionary with 'pattern', 'from', and 'to' fields")
                    continue
                    
                to_agent = rule.get('to')
                from_agent = rule.get('from', '*')
                
                # Check if target agent exists
                if to_agent and to_agent != '*' and not to_agent.startswith('!') and to_agent not in agents:
                    errors.append(f"Routing rule {i} targets undefined agent: '{to_agent}'. "
                                f"Available agents: {', '.join(agents.keys())}")
                
                # Check if source agent exists
                if from_agent and from_agent != '*' and from_agent not in agents:
                    errors.append(f"Routing rule {i} from undefined agent: '{from_agent}'. "
                                f"Available agents: {', '.join(agents.keys())}")
        
        # Check default routing target if specified
        default_target = routing.get('default')
        if default_target and default_target not in agents:
            errors.append(f"Default routing target '{default_target}' not found in agents. "
                        f"Available agents: {', '.join(agents.keys())}")
        
        # Warn about unreachable agents (but not an error)
        if agents and routing.get('rules'):
            agents_with_incoming = set()
            for rule in routing['rules']:
                to_agent = rule.get('to')
                if to_agent and to_agent != '*' and not to_agent.startswith('!'):
                    agents_with_incoming.add(to_agent)
            
            # Add default target to reachable agents
            if default_target:
                agents_with_incoming.add(default_target)
            
            orphaned = set(agents.keys()) - agents_with_incoming
            if orphaned:
                # This is a warning, not an error
                logger.warning(f"Agents with no incoming routes: {orphaned}")
        
        return errors
    
    async def start_orchestration(self, pattern_name: str, vars: Dict[str, Any]) -> Dict[str, Any]:
        """Start a new orchestration instance."""
        try:
            # Load pattern
            pattern = await self.load_pattern(pattern_name)
            
            # Validate pattern
            validation_errors = await self._validate_pattern(pattern)
            if validation_errors:
                return {
                    "error": "Pattern validation failed",
                    "validation_errors": validation_errors,
                    "status": "failed"
                }
            
            # Create instance
            orchestration_id = f"orch_{uuid.uuid4().hex[:8]}"
            instance = OrchestrationInstance(
                orchestration_id=orchestration_id,
                pattern_name=pattern_name,
                pattern=pattern,
                vars=vars
            )
            
            # Parse routing configuration
            routing_config = pattern.get('routing', {})
            instance.default_routing_target = routing_config.get('default')
            
            # Parse agents
            for agent_name, agent_config in pattern.get('agents', {}).items():
                agent_id = f"{orchestration_id}_{agent_name}"
                instance.agents[agent_id] = AgentInfo(
                    agent_id=agent_id,
                    # Support both 'profile' and 'component' fields
                    profile=agent_config.get('profile') or agent_config.get('component', 'default'),
                    prompt_template=agent_config.get('prompt_template'),
                    vars={**vars, **agent_config.get('vars', {})}
                )
            
            # Parse routing rules
            for rule_config in routing_config.get('rules', []):
                rule = RoutingRule(
                    pattern=rule_config.get('pattern', '*'),
                    from_agent=rule_config.get('from', '*'),
                    to_agent=rule_config.get('to', '*'),
                    condition=rule_config.get('condition'),
                    broadcast=rule_config.get('broadcast', False)
                )
                instance.routing_rules.append(rule)
            
            # Parse coordination
            coord = pattern.get('coordination', {})
            if 'turn_taking' in coord:
                turn_config = coord['turn_taking']
                if turn_config.get('mode') == 'strict_alternation':
                    instance.turn_order = list(instance.agents.keys())
            
            # Parse termination conditions
            instance.termination_conditions = pattern.get('coordination', {}).get('termination', {})
            
            # Store instance
            orchestrations[orchestration_id] = instance
            
            # Create orchestration state entity
            if event_emitter:
                await event_emitter("state:entity:create", {
                    "entity_type": "orchestration",
                    "entity_id": orchestration_id,
                    "properties": {
                        "orchestration_id": orchestration_id,
                        "pattern": pattern_name,
                        "pattern_path": pattern_path,
                        "agents": list(instance.agents.keys()),
                        "parent_orchestration": data.get("parent_orchestration_id"),
                        "event_subscription_level": pattern.get("event_propagation", {}).get("subscription_level", 1),
                        "error_handling": pattern.get("event_propagation", {}).get("error_handling", "bubble"),
                        "created_at": timestamp_utc(),
                        "state": "initializing",
                        "variables": instance.vars,
                        "initialization_strategy": pattern.get("initialization", {}).get("strategy", "legacy")
                    }
                })
            
            # Spawn agents
            await self._spawn_agents(instance)
            
            instance.state = "running"
            logger.info(f"Started orchestration {orchestration_id} with pattern {pattern_name}")
            
            # Update orchestration state to running
            if event_emitter:
                await event_emitter("state:entity:update", {
                    "entity_id": orchestration_id,
                    "properties": {
                        "state": "running"
                    }
                })
            
            # Emit start event
            if event_emitter:
                await event_emitter("orchestration:started", {
                    "orchestration_id": orchestration_id,
                    "pattern": pattern_name,
                    "agents": list(instance.agents.keys())
                })
            
            return {
                "orchestration_id": orchestration_id,
                "status": "started",
                "agents": list(instance.agents.keys())
            }
            
        except Exception as e:
            logger.error(f"Failed to start orchestration: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }
    
    async def _spawn_agents(self, instance: OrchestrationInstance):
        """Spawn all agents for an orchestration."""
        if not event_emitter:
            raise RuntimeError("Event emitter not available")
        
        spawn_tasks = []
        for agent_id, agent_info in instance.agents.items():
            # Detect if this is a component path
            if agent_info.profile.startswith("components/"):
                # Use component-based spawning
                spawn_event = "agent:spawn_from_component"
                spawn_data = {
                    "agent_id": agent_id,
                    "component": agent_info.profile,
                    "model": agent_info.vars.get('model', 'claude-cli/sonnet')
                }
            else:
                # Use traditional profile spawning
                spawn_event = "agent:spawn" 
                spawn_data = {
                    "agent_id": agent_id,
                    "profile": agent_info.profile
                }
                if 'model' in agent_info.vars:
                    spawn_data['model'] = agent_info.vars['model']
                    
            # Add prompt template if specified
            if agent_info.prompt_template:
                spawn_data["composition"] = agent_info.prompt_template
            
            # Add context variables with orchestration hierarchy
            spawn_data["context"] = {
                "orchestration_id": instance.orchestration_id,
                "orchestration_depth": instance.vars.get("orchestration_depth", 0) + 1,
                "parent_agent_id": instance.vars.get("coordinator_agent_id"),  # If this orchestration has a coordinator
                "root_orchestration_id": instance.vars.get("root_orchestration_id", instance.orchestration_id),
                "event_subscription_level": instance.pattern.get("event_propagation", {}).get("subscription_level", 1),
                "pattern": instance.pattern_name,
                **instance.vars,
                **agent_info.vars
            }
            
            # Spawn agent
            spawn_task = event_emitter(spawn_event, spawn_data)
            spawn_tasks.append((agent_id, spawn_task))
        
        # Wait for all spawns
        for agent_id, task in spawn_tasks:
            try:
                result = await task
                instance.agents[agent_id].spawned = True
                instance.agents[agent_id].spawn_result = result
                logger.info(f"Spawned agent {agent_id}")
            except Exception as e:
                logger.error(f"Failed to spawn agent {agent_id}: {e}")
        
        # Send initial messages to spawned agents
        await self._send_initial_messages(instance)
    
    async def _send_initial_messages(self, instance: OrchestrationInstance):
        """Send initial messages using flexible initialization router."""
        if not event_emitter:
            return
        
        pattern = instance.pattern
        
        # Get list of successfully spawned agents
        spawned_agents = [
            agent_id for agent_id, agent_info in instance.agents.items() 
            if agent_info and agent_info.spawned
        ]
        
        if not spawned_agents:
            logger.warning("No spawned agents found for initialization")
            return
        
        # Import and use initialization router
        from .initialization_router import InitializationRouter
        router = InitializationRouter()
        
        # Route initialization messages
        message_plan = router.route_messages(pattern, spawned_agents)
        logger.info(f"Generated initialization plan with {len(message_plan)} messages")
        
        # Execute message plan
        for message_spec in message_plan:
            await self._execute_initialization_message(message_spec, instance)
    
    async def _execute_initialization_message(self, message_spec: Dict[str, Any], instance: OrchestrationInstance):
        """Execute a single initialization message from the routing plan."""
        message_type = message_spec.get('type', 'targeted')
        
        try:
            if message_type == 'broadcast':
                await self._send_broadcast_message(message_spec, instance)
            elif message_type == 'targeted':
                await self._send_targeted_message(message_spec, instance)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except Exception as e:
            logger.error(f"Failed to execute initialization message: {e}")
    
    async def _send_broadcast_message(self, message_spec: Dict[str, Any], instance: OrchestrationInstance):
        """Send broadcast message to all agents."""
        content = message_spec.get('message', '')
        variables = message_spec.get('variables', {})
        
        # Apply variable substitution
        from ksi_common.template_utils import substitute_variables
        content = substitute_variables(content, variables)
        
        # Send to all spawned agents
        for agent_id in instance.agents:
            agent_info = instance.agents.get(agent_id)
            if agent_info and agent_info.spawned:
                await event_emitter("agent:send_message", {
                    "agent_id": agent_id,
                    "message": {
                        "role": "system",
                        "content": content
                    }
                })
        
        logger.info(f"Sent broadcast message to {len(instance.agents)} agents")
    
    async def _send_targeted_message(self, message_spec: Dict[str, Any], instance: OrchestrationInstance):
        """Send targeted message to specific agent."""
        agent_id = message_spec.get('agent_id')
        content = message_spec.get('message', '')
        variables = message_spec.get('variables', {})
        role = message_spec.get('role', 'agent')
        
        if not agent_id or agent_id not in instance.agents:
            logger.warning(f"Agent {agent_id} not found for targeted message")
            return
        
        agent_info = instance.agents.get(agent_id)
        if not agent_info or not agent_info.spawned:
            logger.warning(f"Agent {agent_id} not spawned for targeted message")
            return
        
        # Apply variable substitution
        from ksi_common.template_utils import substitute_variables
        content = substitute_variables(content, variables)
        
        # Send the message
        await event_emitter("agent:send_message", {
            "agent_id": agent_id,
            "message": {
                "role": "user",
                "content": content
            }
        })
        
        logger.info(f"Sent {role} initialization message to {agent_id}")
    
    async def _send_legacy_initial_messages(self, instance: OrchestrationInstance):
        """Legacy method for backward compatibility - handles composition references and DSL."""
        pattern = instance.pattern
        agents_config = pattern.get('agents', {})
        
        for agent_name, agent_config in agents_config.items():
            agent_id = f"{instance.orchestration_id}_{agent_name}"
            
            # Check if agent was successfully spawned
            agent_info = instance.agents.get(agent_id)
            if not agent_info or not agent_info.spawned:
                continue
            
            # Check for initial_message composition reference
            initial_message_ref = agent_config.get('initial_message')
            if initial_message_ref:
                try:
                    # Get the composition content
                    comp_results = await event_emitter("composition:get", {
                        "name": initial_message_ref
                    })
                    comp_result = comp_results[0] if comp_results else None
                    
                    if comp_result and 'content' in comp_result:
                        # Send the initial message
                        await event_emitter("agent:send_message", {
                            "agent_id": agent_id,
                            "message": {
                                "role": "system",
                                "content": comp_result['content']
                            }
                        })
                        logger.info(f"Sent initial message to {agent_id} from composition {initial_message_ref}")
                    else:
                        logger.warning(f"Could not find composition {initial_message_ref} for agent {agent_id}")
                        
                except Exception as e:
                    logger.error(f"Failed to send initial message to {agent_id}: {e}")
            
            # Check if this is an orchestrator agent and send the DSL strategy
            # ONLY if the agent doesn't already have a prompt or initial_prompt defined
            agent_profile = agent_config.get('profile', '') or agent_config.get('component', '')
            agent_vars = agent_config.get('vars', {})
            has_prompt = 'prompt' in agent_vars or 'initial_prompt' in agent_vars
            
            if 'orchestrator' in agent_profile.lower() and 'orchestration_logic' in pattern and not has_prompt:
                try:
                    # Build orchestration instruction with the DSL
                    orchestration_logic = pattern.get('orchestration_logic', {})
                    strategy = orchestration_logic.get('strategy', '')
                    description = orchestration_logic.get('description', '')
                    
                    # Build the orchestration message
                    orchestration_message = f"""## ORCHESTRATION PATTERN: {instance.pattern_name}

{description}

## YOUR ORCHESTRATION STRATEGY (EXECUTE THIS NOW):

{strategy}

## VARIABLES:
{instance.vars}

## YOUR ROLE:
You are the orchestrator for pattern '{instance.pattern_name}'. 
IMMEDIATELY begin executing the strategy above. 
DO NOT wait for further instructions.
START the orchestration NOW by following the DSL strategy."""
                    
                    # Send the orchestration strategy
                    await event_emitter("agent:send_message", {
                        "agent_id": agent_id,
                        "message": {
                            "role": "user",
                            "content": orchestration_message
                        }
                    })
                    logger.info(f"Sent orchestration strategy to {agent_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to send orchestration strategy to {agent_id}: {e}")
            elif 'orchestrator' in agent_profile.lower() and has_prompt:
                logger.info(f"Skipping orchestration_logic DSL for {agent_id} - agent already has prompt defined")
            
            # Also check for initial_prompt in vars
            else:
                agent_vars = agent_config.get('vars', {})
                initial_prompt = agent_vars.get('initial_prompt')
                if initial_prompt:
                    try:
                        # Substitute variables in the prompt
                        # Combine instance vars with agent-specific vars
                        all_vars = {**instance.vars, **agent_vars}
                        
                        # Simple variable substitution for {{var}} patterns
                        prompt_content = initial_prompt
                        for var_name, var_value in all_vars.items():
                            prompt_content = prompt_content.replace(f"{{{{{var_name}}}}}", str(var_value))
                        
                        # Send the initial prompt as a user message
                        await event_emitter("agent:send_message", {
                            "agent_id": agent_id,
                            "message": {
                                "role": "user",
                                "content": prompt_content
                            }
                        })
                        logger.info(f"Sent initial prompt to {agent_id}")
                    except Exception as e:
                        logger.error(f"Failed to send initial prompt to {agent_id}: {e}")
    
    async def route_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Route a message according to orchestration rules."""
        orchestration_id = data.get("orchestration_id")
        from_agent = data.get("from_agent")
        event_name = data.get("event", "message")
        payload = data.get("payload", {})
        
        if not orchestration_id or orchestration_id not in orchestrations:
            return {"error": "Unknown orchestration"}
        
        instance = orchestrations[orchestration_id]
        instance.message_count += 1
        instance.last_activity = time.time()
        
        # Find matching routing rules
        targets = set()
        for rule in instance.routing_rules:
            if rule.matches(event_name, from_agent):
                rule_targets = rule.get_targets(instance.agents, from_agent)
                targets.update(rule_targets)
        
        # Apply turn-taking if enabled
        if instance.turn_order and not self._is_agents_turn(instance, from_agent):
            logger.debug(f"Blocking message from {from_agent} - not their turn")
            return {"status": "blocked", "reason": "not_agents_turn"}
        
        # If no targets found and we have a default, use it
        if not targets and instance.default_routing_target:
            if instance.default_routing_target in instance.agents:
                targets.add(instance.default_routing_target)
                logger.info(f"No routing rules matched for {event_name}, using default target: {instance.default_routing_target}")
            else:
                logger.warning(f"Default routing target {instance.default_routing_target} not found in agents")
        
        # Route to targets
        routed_to = []
        if event_emitter:
            for target in targets:
                if target in instance.agents:
                    # Send message to agent
                    await event_emitter("agent:send_message", {
                        "agent_id": target,
                        "message": {
                            "type": event_name,
                            "from": from_agent,
                            "orchestration_id": orchestration_id,
                            "payload": payload
                        }
                    })
                    routed_to.append(target)
        
        # Update turn if using turn-taking
        if instance.turn_order:
            instance.current_turn = (instance.current_turn + 1) % len(instance.turn_order)
        
        # Check termination conditions
        await self._check_termination(instance)
        
        return {
            "status": "routed",
            "targets": routed_to,
            "message_count": instance.message_count
        }
    
    def _is_agents_turn(self, instance: OrchestrationInstance, agent_id: str) -> bool:
        """Check if it's the agent's turn to speak."""
        if not instance.turn_order:
            return True
        
        current_agent = instance.turn_order[instance.current_turn]
        return agent_id == current_agent
    
    async def _check_termination(self, instance: OrchestrationInstance):
        """Check if orchestration should terminate."""
        conditions = instance.termination_conditions.get('conditions', [])
        
        for condition in conditions:
            # Check rounds
            if 'rounds' in condition:
                if instance.message_count >= condition['rounds'] * len(instance.agents):
                    await self._terminate_orchestration(instance, "rounds_completed")
                    return
            
            # Check timeout
            if 'timeout' in condition:
                if time.time() - instance.start_time > condition['timeout']:
                    await self._terminate_orchestration(instance, "timeout")
                    return
            
            # Check event
            if 'event' in condition:
                # Event-based termination not yet implemented
                pass
    
    async def _terminate_orchestration(self, instance: OrchestrationInstance, reason: str):
        """Terminate an orchestration."""
        logger.info(f"Terminating orchestration {instance.orchestration_id}: {reason}")
        
        # Terminate all agents
        if event_emitter:
            for agent_id in instance.agents:
                await event_emitter("agent:terminate", {"agent_id": agent_id})
        
        # Unload pattern transformers via transformer service
        if event_emitter:
            try:
                await event_emitter("transformer:unload_pattern", {
                    "pattern": instance.pattern_name,
                    "source": "orchestration"
                })
                logger.debug(f"Requested transformer unloading for pattern {instance.pattern_name}")
            except Exception as e:
                logger.warning(f"Failed to unload transformers for pattern {instance.pattern_name}: {e}")
        
        # Update state
        instance.state = "terminated"
        
        # Emit termination event
        if event_emitter:
            await event_emitter("orchestration:terminated", {
                "orchestration_id": instance.orchestration_id,
                "reason": reason,
                "duration": time.time() - instance.start_time,
                "message_count": instance.message_count
            })
        
        # Clean up
        del orchestrations[instance.orchestration_id]


# Create module instance
orchestration_module = OrchestrationModule()


# System event handlers
class SystemContextData(TypedDict):
    """System context with runtime references."""
    emit_event: NotRequired[Any]  # Event emitter function
    shutdown_event: NotRequired[Any]  # Shutdown event object


@event_handler("system:context")
async def handle_context(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
    """Store event emitter reference."""
    from ksi_common.event_parser import event_format_linter
    data = event_format_linter(raw_data, SystemContextData)
    global event_emitter
    # Get router for event emission
    router = get_router()
    event_emitter = router.emit
    logger.info("Orchestration service received context, event_emitter configured")


class SystemStartupData(TypedDict):
    """System startup configuration."""
    # No specific fields required for this handler
    pass


@event_handler("system:startup")
async def handle_startup(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Initialize orchestration service on startup."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder
    data = event_format_linter(raw_data, SystemStartupData)
    
    # Ensure orchestration patterns directory exists
    patterns_dir = orchestration_module.patterns_dir
    patterns_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Orchestration service started - patterns dir: {patterns_dir}")
    
    return event_response_builder({
        "status": "orchestration_ready",
        "patterns_dir": str(patterns_dir)
    }, context)


class SystemShutdownData(TypedDict):
    """System shutdown notification."""
    # No specific fields for shutdown
    pass


@event_handler("system:shutdown")
async def handle_shutdown(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> None:
    """Clean up on shutdown."""
    from ksi_common.event_parser import event_format_linter
    data = event_format_linter(raw_data, SystemShutdownData)
    # Terminate all active orchestrations
    for instance in list(orchestrations.values()):
        await orchestration_module._terminate_orchestration(instance, "shutdown")
    
    logger.info("Orchestration service shutdown")


# Orchestration event handlers
class OrchestrationStartData(TypedDict):
    """Start a new orchestration."""
    pattern: Required[str]  # Pattern name to load
    vars: NotRequired[Dict[str, Any]]  # Variables to pass to orchestration


@event_handler("orchestration:start")
async def handle_orchestration_start(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Start a new orchestration."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, OrchestrationStartData)
    pattern = data.get("pattern")
    vars = data.get("vars", {})
    
    if not pattern:
        return error_response("pattern required", context)
    
    # Execute async orchestration start
    return await orchestration_module.start_orchestration(pattern, vars)


class OrchestrationMessageData(TypedDict):
    """Route a message within an orchestration."""
    orchestration_id: Required[str]  # Orchestration ID
    from_agent: Required[str]  # Source agent ID
    event: NotRequired[str]  # Event name (default: "message")
    payload: NotRequired[Dict[str, Any]]  # Message payload


@event_handler("orchestration:message")
async def handle_orchestration_message(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Route a message within an orchestration."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, OrchestrationMessageData)
    return await orchestration_module.route_message(data)


class OrchestrationStatusData(TypedDict):
    """Get orchestration status."""
    orchestration_id: NotRequired[str]  # Specific orchestration ID (omit for all)


@event_handler("orchestration:status")
async def handle_orchestration_status(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get orchestration status."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, OrchestrationStatusData)
    orchestration_id = data.get("orchestration_id")
    
    if orchestration_id:
        if orchestration_id in orchestrations:
            instance = orchestrations[orchestration_id]
            return event_response_builder({
                "orchestration_id": orchestration_id,
                "state": instance.state,
                "pattern": instance.pattern_name,
                "agents": {
                    aid: {"spawned": info.spawned, "profile": info.profile}
                    for aid, info in instance.agents.items()
                },
                "message_count": instance.message_count,
                "duration": time.time() - instance.start_time
            }, context)
        else:
            return error_response("Orchestration not found", context)
    else:
        # Return all orchestrations
        return event_response_builder({
            "orchestrations": {
                oid: {
                    "state": inst.state,
                    "pattern": inst.pattern_name,
                    "agent_count": len(inst.agents),
                    "message_count": inst.message_count
                }
                for oid, inst in orchestrations.items()
            }
        }, context)


class OrchestrationTerminateData(TypedDict):
    """Manually terminate an orchestration."""
    orchestration_id: Required[str]  # Orchestration ID to terminate


@event_handler("orchestration:terminate")
async def handle_orchestration_terminate(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Manually terminate an orchestration."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, OrchestrationTerminateData)
    orchestration_id = data.get("orchestration_id")
    
    if not orchestration_id or orchestration_id not in orchestrations:
        return error_response("Orchestration not found", context)
    
    instance = orchestrations[orchestration_id]
    
    # Terminate orchestration
    await orchestration_module._terminate_orchestration(instance, "manual")
    return event_response_builder({"status": "terminated"}, context)


class OrchestrationRequestTerminationData(TypedDict):
    """Allow an agent to request orchestration termination."""
    agent_id: Required[str]  # Agent requesting termination
    reason: NotRequired[str]  # Termination reason (default: "completed")


@event_handler("orchestration:request_termination")
async def handle_orchestration_request_termination(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Allow an agent within an orchestration to request termination."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, OrchestrationRequestTerminationData)
    agent_id = data.get("agent_id")
    reason = data.get("reason", "completed")
    
    if not agent_id:
        return error_response("No agent_id provided", context)
    
    # Find the orchestration this agent belongs to
    orchestration_id = None
    instance = None
    
    for orch_id, orch_instance in orchestrations.items():
        if agent_id in orch_instance.agents:
            orchestration_id = orch_id
            instance = orch_instance
            break
    
    if not instance:
        return error_response(f"Agent {agent_id} not found in any orchestration", context)
    
    # Verify the agent is an orchestrator (has orchestration capabilities)
    agent_info = instance.agents.get(agent_id)
    if agent_info and agent_info.profile in ["base_orchestrator"]:
        # Allow termination
        logger.info(f"Agent {agent_id} requested termination of orchestration {orchestration_id}: {reason}")
        await orchestration_module._terminate_orchestration(instance, f"agent_requested: {reason}")
        return event_response_builder({"status": "terminated", "orchestration_id": orchestration_id}, context)
    else:
        return error_response("Only orchestrator agents can request termination", context)


# orchestration:list_patterns removed - use composition:discover --type orchestration instead


class OrchestrationLoadPatternData(TypedDict):
    """Load and validate an orchestration pattern."""
    pattern: Required[str]  # Pattern name to load


@event_handler("orchestration:load_pattern")
async def handle_load_pattern(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load and validate an orchestration pattern."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, OrchestrationLoadPatternData)
    pattern_name = data.get("pattern")
    
    if not pattern_name:
        return error_response("pattern name required", context)
    
    try:
        pattern = await orchestration_module.load_pattern(pattern_name)
        return event_response_builder({
            "status": "loaded",
            "pattern": pattern
        }, context)
    except FileNotFoundError as e:
        return error_response(f"Pattern not found: {str(e)}", context)
    except ValueError as e:
        return error_response(f"Invalid pattern: {str(e)}", context)
    except Exception as e:
        return error_response(f"Failed to load pattern: {str(e)}", context)


@event_handler("orchestration:event")
async def handle_orchestration_event(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Handle hierarchically routed events for orchestrations."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder
    
    orchestration_id = raw_data.get("orchestration_id")
    source_agent = raw_data.get("source_agent")
    event_name = raw_data.get("event")
    event_data = raw_data.get("data", {})
    
    if not orchestration_id:
        return {"error": "orchestration_id required"}
    
    instance = orchestrations.get(orchestration_id)
    if not instance:
        return {"error": f"Orchestration {orchestration_id} not found"}
    
    # Log the event for orchestration-level monitoring
    logger.info(f"Orchestration {orchestration_id} received event {event_name} from {source_agent}")
    
    # Store event in orchestration state for potential pattern analysis
    if not hasattr(instance, 'received_events'):
        instance.received_events = []
    
    instance.received_events.append({
        "timestamp": timestamp_utc(),
        "source_agent": source_agent,
        "event": event_name,
        "data": event_data
    })
    
    # Keep only last 100 events to prevent memory issues
    if len(instance.received_events) > 100:
        instance.received_events = instance.received_events[-100:]
    
    return event_response_builder({
        "status": "received",
        "orchestration_id": orchestration_id
    }, context)


class OrchestrationGetInstanceData(TypedDict):
    """Get detailed information about an orchestration instance."""
    orchestration_id: Required[str]  # Orchestration ID to get details for


@event_handler("orchestration:get_instance")
async def handle_get_instance(raw_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get detailed information about an orchestration instance."""
    from ksi_common.event_parser import event_format_linter
    from ksi_common.event_response_builder import event_response_builder, error_response
    
    data = event_format_linter(raw_data, OrchestrationGetInstanceData)
    orchestration_id = data.get("orchestration_id")
    
    if not orchestration_id:
        return error_response("orchestration_id required", context)
    
    if orchestration_id not in orchestrations:
        return error_response("Orchestration not found", context)
    
    instance = orchestrations[orchestration_id]
    
    return event_response_builder({
        "orchestration_id": orchestration_id,
        "pattern_name": instance.pattern_name,
        "state": instance.state,
        "start_time": instance.start_time,
        "last_activity": instance.last_activity,
        "message_count": instance.message_count,
        "duration": time.time() - instance.start_time,
        "vars": instance.vars,
        "agents": {
            aid: {
                "agent_id": info.agent_id,
                "profile": info.profile,
                "prompt_template": info.prompt_template,
                "vars": info.vars,
                "spawned": info.spawned,
                "spawn_result": info.spawn_result
            }
            for aid, info in instance.agents.items()
        },
        "routing_rules": [
            {
                "pattern": rule.pattern,
                "from_agent": rule.from_agent,
                "to_agent": rule.to_agent,
                "condition": rule.condition,
                "broadcast": rule.broadcast
            }
            for rule in instance.routing_rules
        ],
        "coordination": {
            "turn_order": instance.turn_order,
            "current_turn": instance.current_turn,
            "turn_agent": instance.turn_order[instance.current_turn] if instance.turn_order else None
        },
        "termination_conditions": instance.termination_conditions
    }, context)


