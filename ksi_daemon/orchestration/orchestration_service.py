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
from typing import Dict, Any, Optional, List, Set
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
    
    async def start_orchestration(self, pattern_name: str, vars: Dict[str, Any]) -> Dict[str, Any]:
        """Start a new orchestration instance."""
        try:
            # Load pattern
            pattern = await self.load_pattern(pattern_name)
            
            # Create instance
            orchestration_id = f"orch_{uuid.uuid4().hex[:8]}"
            instance = OrchestrationInstance(
                orchestration_id=orchestration_id,
                pattern_name=pattern_name,
                pattern=pattern,
                vars=vars
            )
            
            # Parse agents
            for agent_name, agent_config in pattern.get('agents', {}).items():
                agent_id = f"{orchestration_id}_{agent_name}"
                instance.agents[agent_id] = AgentInfo(
                    agent_id=agent_id,
                    profile=agent_config.get('profile', 'default'),
                    prompt_template=agent_config.get('prompt_template'),
                    vars={**vars, **agent_config.get('vars', {})}
                )
            
            # Parse routing rules
            for rule_config in pattern.get('routing', {}).get('rules', []):
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
            
            # Spawn agents
            await self._spawn_agents(instance)
            
            instance.state = "running"
            logger.info(f"Started orchestration {orchestration_id} with pattern {pattern_name}")
            
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
            # Prepare spawn data
            spawn_data = {
                "agent_id": agent_id,
                "profile": agent_info.profile,
                "session_id": f"{instance.orchestration_id}_session"
            }
            
            # Add prompt template if specified
            if agent_info.prompt_template:
                spawn_data["composition"] = agent_info.prompt_template
            
            # Add context variables
            spawn_data["context"] = {
                "orchestration_id": instance.orchestration_id,
                "pattern": instance.pattern_name,
                **instance.vars,
                **agent_info.vars
            }
            
            # Spawn agent
            spawn_task = event_emitter("agent:spawn", spawn_data)
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
@event_handler("system:context")
async def handle_context(context: Dict[str, Any]) -> None:
    """Store event emitter reference."""
    global event_emitter
    # Get router for event emission
    router = get_router()
    event_emitter = router.emit
    logger.info("Orchestration service received context, event_emitter configured")


@event_handler("system:startup")
async def handle_startup(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize orchestration service on startup."""
    
    # Ensure orchestration patterns directory exists
    patterns_dir = orchestration_module.patterns_dir
    patterns_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Orchestration service started - patterns dir: {patterns_dir}")
    
    return {
        "status": "orchestration_ready",
        "patterns_dir": str(patterns_dir)
    }


@event_handler("system:shutdown")
async def handle_shutdown(data: Dict[str, Any]) -> None:
    """Clean up on shutdown."""
    # Terminate all active orchestrations
    for instance in list(orchestrations.values()):
        await orchestration_module._terminate_orchestration(instance, "shutdown")
    
    logger.info("Orchestration service shutdown")


# Orchestration event handlers
@event_handler("orchestration:start")
async def handle_orchestration_start(data: Dict[str, Any]) -> Dict[str, Any]:
    """Start a new orchestration."""
    pattern = data.get("pattern")
    vars = data.get("vars", {})
    
    if not pattern:
        return {"error": "pattern required"}
    
    # Execute async orchestration start
    return await orchestration_module.start_orchestration(pattern, vars)


@event_handler("orchestration:message")
async def handle_orchestration_message(data: Dict[str, Any]) -> Dict[str, Any]:
    """Route a message within an orchestration."""
    return await orchestration_module.route_message(data)


@event_handler("orchestration:status")
async def handle_orchestration_status(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get orchestration status."""
    orchestration_id = data.get("orchestration_id")
    
    if orchestration_id:
        if orchestration_id in orchestrations:
            instance = orchestrations[orchestration_id]
            return {
                "orchestration_id": orchestration_id,
                "state": instance.state,
                "pattern": instance.pattern_name,
                "agents": {
                    aid: {"spawned": info.spawned, "profile": info.profile}
                    for aid, info in instance.agents.items()
                },
                "message_count": instance.message_count,
                "duration": time.time() - instance.start_time
            }
        else:
            return {"error": "Orchestration not found"}
    else:
        # Return all orchestrations
        return {
            "orchestrations": {
                oid: {
                    "state": inst.state,
                    "pattern": inst.pattern_name,
                    "agent_count": len(inst.agents),
                    "message_count": inst.message_count
                }
                for oid, inst in orchestrations.items()
            }
        }


@event_handler("orchestration:terminate")
async def handle_orchestration_terminate(data: Dict[str, Any]) -> Dict[str, Any]:
    """Manually terminate an orchestration."""
    orchestration_id = data.get("orchestration_id")
    
    if not orchestration_id or orchestration_id not in orchestrations:
        return {"error": "Orchestration not found"}
    
    instance = orchestrations[orchestration_id]
    
    # Terminate orchestration
    await orchestration_module._terminate_orchestration(instance, "manual")
    return {"status": "terminated"}


@event_handler("orchestration:list_patterns")
async def handle_list_patterns(data: Dict[str, Any]) -> Dict[str, Any]:
    """List available orchestration patterns."""
    patterns_dir = orchestration_module.patterns_dir
    patterns = []
    
    if patterns_dir.exists():
        for pattern_file in patterns_dir.glob("*.yaml"):
            patterns.append(pattern_file.stem)
        for pattern_file in patterns_dir.glob("*.yml"):
            if pattern_file.stem not in patterns:  # Avoid duplicates
                patterns.append(pattern_file.stem)
    
    return {
        "patterns": sorted(patterns),
        "patterns_dir": str(patterns_dir)
    }


@event_handler("orchestration:load_pattern")
async def handle_load_pattern(data: Dict[str, Any]) -> Dict[str, Any]:
    """Load and validate an orchestration pattern."""
    pattern_name = data.get("pattern")
    
    if not pattern_name:
        return {"error": "pattern name required"}
    
    try:
        pattern = await orchestration_module.load_pattern(pattern_name)
        return {
            "status": "loaded",
            "pattern": pattern
        }
    except FileNotFoundError as e:
        return {"error": f"Pattern not found: {str(e)}"}
    except ValueError as e:
        return {"error": f"Invalid pattern: {str(e)}"}
    except Exception as e:
        return {"error": f"Failed to load pattern: {str(e)}"}


@event_handler("orchestration:get_instance")
async def handle_get_instance(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get detailed information about an orchestration instance."""
    orchestration_id = data.get("orchestration_id")
    
    if not orchestration_id:
        return {"error": "orchestration_id required"}
    
    if orchestration_id not in orchestrations:
        return {"error": "Orchestration not found"}
    
    instance = orchestrations[orchestration_id]
    
    return {
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
    }


