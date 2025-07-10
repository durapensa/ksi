#!/usr/bin/env python3
"""
Orchestration Primitives - Minimal high-level coordination primitives for orchestrator agents

Design Philosophy:
- Parameters over Primitives: Flexible primitives with rich parameters
- Composition over Prescription: Build complex behaviors from simple parts
- Context over Control: Rich metadata, not rigid workflows
- General over Specific: Track anything, query anything, coordinate anything
"""

import asyncio
import uuid
import time
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime, timezone

from ksi_daemon.event_system import event_handler, event_transformer, get_router
from ksi_common.logging import get_bound_logger
from ksi_common.timestamps import timestamp_utc

logger = get_bound_logger("orchestration_primitives")

# Global event emitter (set during context)
event_emitter = None

# Global orchestration context tracking
_orchestration_contexts = {}  # execution_id -> context
_agent_orchestrations = {}    # agent_id -> {execution_id, pattern, ...}


class OrchestrationContext:
    """Tracks context for an orchestration execution."""
    
    def __init__(self, execution_id: str, pattern: str, orchestrator_id: str):
        self.execution_id = execution_id
        self.pattern = pattern
        self.orchestrator_id = orchestrator_id
        self.start_time = time.time()
        self.agents = set()  # Agents involved in this orchestration
        self.metadata = {}
        self.tracked_data = []  # All tracked decisions/metrics/state
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for inclusion in messages."""
        return {
            "execution_id": self.execution_id,
            "pattern": self.pattern,
            "orchestrator_id": self.orchestrator_id,
            "start_time": self.start_time,
            "duration": time.time() - self.start_time,
            "agents": list(self.agents),
            **self.metadata
        }


def get_or_create_context(data: Dict[str, Any]) -> OrchestrationContext:
    """Get existing context or create new one from request data."""
    execution_id = data.get('execution_id')
    
    if execution_id and execution_id in _orchestration_contexts:
        return _orchestration_contexts[execution_id]
    
    # Create new context
    execution_id = execution_id or str(uuid.uuid4())
    pattern = data.get('pattern', 'unknown')
    orchestrator_id = data.get('orchestrator_id', data.get('agent_id', 'unknown'))
    
    context = OrchestrationContext(execution_id, pattern, orchestrator_id)
    context.metadata.update(data.get('metadata', {}))
    
    _orchestration_contexts[execution_id] = context
    return context


# Core Orchestration Primitives

@event_handler("orchestration:spawn")
async def handle_orchestration_spawn(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create agent(s) with orchestration context.
    
    Parameters:
        profile: str - Agent profile to use
        count: int - Number of agents to spawn (default: 1)
        purpose: str - Purpose/role for the agent(s)
        metadata: Dict - Agent-specific metadata
        pattern: str - Orchestration pattern being used
        execution_id: str - Orchestration execution ID (auto-generated if not provided)
        orchestrator_id: str - ID of orchestrating agent
        
    Returns:
        agents: List[Dict] - Spawned agent details with IDs
        execution_id: str - Orchestration execution ID
        duration: float - Time taken to spawn
    """
    start_time = time.time()
    context = get_or_create_context(data)
    
    profile = data.get('profile', 'base_agent')
    count = data.get('count', 1)
    purpose = data.get('purpose', '')
    agent_metadata = data.get('metadata', {})
    
    spawned_agents = []
    
    for i in range(count):
        # Add orchestration context to agent metadata
        enriched_metadata = {
            **agent_metadata,
            "_orchestration": context.to_dict(),
            "agent_index": i if count > 1 else None
        }
        
        try:
            # Spawn agent with context
            result = await event_emitter("agent:spawn", {
                "profile": profile,
                "purpose": f"{purpose} ({i+1}/{count})" if count > 1 else purpose,
                "metadata": enriched_metadata
            })
            
            if result and isinstance(result, list) and result[0].get('agent_id'):
                agent_info = result[0]
                agent_id = agent_info['agent_id']
                
                # Track agent in context
                context.agents.add(agent_id)
                _agent_orchestrations[agent_id] = {
                    "execution_id": context.execution_id,
                    "pattern": context.pattern,
                    "orchestrator_id": context.orchestrator_id
                }
                
                spawned_agents.append(agent_info)
            else:
                logger.warning(f"Failed to spawn agent {i+1}/{count}")
                
        except Exception as e:
            logger.error(f"Error spawning agent {i+1}/{count}: {e}")
    
    return {
        "status": "success",
        "agents": spawned_agents,
        "count": len(spawned_agents),
        "requested": count,
        "execution_id": context.execution_id,
        "duration": time.time() - start_time
    }


@event_handler("orchestration:send")
async def handle_orchestration_send(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flexible message sending with orchestration context.
    
    Parameters:
        message: Dict - Message content to send
        to: Union[str, List[str], Dict] - Target specification:
            - str: Single agent ID
            - List[str]: Multiple agent IDs (multicast)
            - Dict: Selection criteria like {"role": "evaluator", "status": "ready"}
        wait_for_ack: bool - Wait for acknowledgments (default: False)
        timeout: float - Acknowledgment timeout in seconds
        pattern: str - Orchestration pattern being used
        execution_id: str - Orchestration execution ID
        
    Returns:
        sent_to: List[str] - Agents that received the message
        acknowledged: List[str] - Agents that acknowledged (if wait_for_ack)
        failed: List[str] - Agents that failed to receive
        duration: float - Time taken
    """
    start_time = time.time()
    context = get_or_create_context(data)
    
    to = data.get('to')
    message = data.get('message', {})
    wait_for_ack = data.get('wait_for_ack', False)
    timeout = data.get('timeout', 30.0)
    
    # Determine target agents
    if isinstance(to, str):
        # Single agent
        target_agents = [to]
    elif isinstance(to, list):
        # Multiple specific agents (multicast)
        target_agents = to
    elif isinstance(to, dict):
        # Selection criteria
        target_agents = await select_agents_by_criteria(to)
    else:
        return {"error": "Invalid 'to' parameter"}
    
    # Add orchestration context to message
    enriched_message = {
        **message,
        "_orchestration": context.to_dict()
    }
    
    # Send to each agent
    sent_to = []
    failed = []
    
    for agent_id in target_agents:
        try:
            result = await event_emitter("agent:send_message", {
                "agent_id": agent_id,
                "message": enriched_message
            })
            
            if result and result[0].get("status") == "sent":
                sent_to.append(agent_id)
                context.agents.add(agent_id)  # Track involvement
            else:
                failed.append(agent_id)
                
        except Exception as e:
            failed.append(agent_id)
            logger.warning(f"Failed to send to {agent_id}: {e}")
    
    # Handle acknowledgments if requested
    acknowledged = []
    if wait_for_ack and sent_to:
        # TODO: Implement acknowledgment collection
        # This would involve listening for ack messages with a timeout
        pass
    
    return {
        "status": "success",
        "sent_to": sent_to,
        "acknowledged": acknowledged,
        "failed": failed,
        "total_agents": len(target_agents),
        "duration": time.time() - start_time,
        "execution_id": context.execution_id
    }


@event_handler("orchestration:await")
async def handle_orchestration_await(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wait for responses with flexible conditions.
    
    Parameters:
        from: Union[str, List[str], Dict] - Agents to wait for
        event_pattern: str - Event pattern to match (e.g., "result:*")
        min_responses: int - Minimum responses needed (default: all)
        timeout: float - Maximum wait time in seconds
        collect_partial: bool - Return partial results on timeout (default: True)
        execution_id: str - Orchestration execution ID
        
    Returns:
        responses: List[Dict] - Collected responses
        responded: List[str] - Agents that responded
        pending: List[str] - Agents that didn't respond
        timed_out: bool - Whether timeout occurred
        duration: float - Time taken
    """
    start_time = time.time()
    context = get_or_create_context(data)
    
    from_agents = data.get('from')
    event_pattern = data.get('event_pattern', 'message:*')
    timeout = data.get('timeout', 60.0)
    collect_partial = data.get('collect_partial', True)
    
    # Determine which agents to wait for
    if isinstance(from_agents, str):
        if from_agents == "all":
            # Wait for all agents in this orchestration
            target_agents = list(context.agents)
        else:
            target_agents = [from_agents]
    elif isinstance(from_agents, list):
        target_agents = from_agents
    elif isinstance(from_agents, dict):
        target_agents = await select_agents_by_criteria(from_agents)
    else:
        return {"error": "Invalid 'from' parameter"}
    
    # Default min_responses to all if not specified
    min_responses = data.get('min_responses', len(target_agents))
    
    # Track responses
    responses = []
    responded = set()
    pending = set(target_agents)
    
    # Create response collector
    response_queue = asyncio.Queue()
    
    # Temporary event handler for collecting responses
    handler_id = f"await_{context.execution_id}_{uuid.uuid4().hex[:8]}"
    
    async def response_collector(event_data: Dict[str, Any]) -> None:
        """Collect responses matching our pattern."""
        # Check if this is from one of our target agents
        agent_id = event_data.get('agent_id') or event_data.get('from_agent_id')
        if agent_id and agent_id in pending:
            await response_queue.put({
                "agent_id": agent_id,
                "event": event_data.get('event', 'unknown'),
                "data": event_data,
                "timestamp": time.time()
            })
    
    # Register temporary handler for the pattern
    # Note: This is a simplified implementation. In production, we'd need
    # to properly register with the event router for pattern matching
    import fnmatch
    
    # Subscribe to events (simplified - in real implementation would use proper subscription)
    original_emit = event_emitter
    collected_events = []
    
    async def intercepting_emit(event_name: str, event_data: Dict[str, Any]) -> Any:
        """Intercept events to check for matches."""
        # Check if event matches pattern
        if fnmatch.fnmatch(event_name, event_pattern):
            agent_id = event_data.get('agent_id') or event_data.get('from_agent_id')
            if agent_id in pending:
                collected_events.append({
                    "agent_id": agent_id,
                    "event": event_name,
                    "data": event_data,
                    "timestamp": time.time()
                })
        
        # Call original emit
        return await original_emit(event_name, event_data)
    
    # Temporarily replace emitter (this is a hack for the prototype)
    # In production, use proper event subscription
    event_emitter = intercepting_emit
    
    try:
        # Wait for responses with timeout
        deadline = time.time() + timeout
        timed_out = False
        
        while len(responded) < min_responses and time.time() < deadline:
            remaining_time = deadline - time.time()
            if remaining_time <= 0:
                timed_out = True
                break
            
            # Check collected events
            for event in collected_events:
                if event['agent_id'] not in responded:
                    agent_id = event['agent_id']
                    responses.append(event)
                    responded.add(agent_id)
                    pending.discard(agent_id)
            
            # Clear processed events
            collected_events.clear()
            
            # Short sleep to prevent busy waiting
            await asyncio.sleep(0.1)
        
        # Check if we timed out
        if time.time() >= deadline:
            timed_out = True
        
        # Collect any final events
        for event in collected_events:
            if event['agent_id'] not in responded:
                agent_id = event['agent_id']
                responses.append(event)
                responded.add(agent_id)
                pending.discard(agent_id)
        
    finally:
        # Restore original emitter
        event_emitter = original_emit
    
    # Determine success based on conditions
    success = len(responded) >= min_responses
    
    # Return results
    result = {
        "status": "success" if success else "timeout",
        "responses": responses,
        "responded": list(responded),
        "pending": list(pending),
        "timed_out": timed_out,
        "min_responses": min_responses,
        "total_expected": len(target_agents),
        "duration": time.time() - start_time,
        "execution_id": context.execution_id
    }
    
    # If not collecting partial results and timed out, clear responses
    if timed_out and not collect_partial:
        result["responses"] = []
        result["status"] = "timeout"
    
    return result


@event_handler("orchestration:track")
async def handle_orchestration_track(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Record any orchestration data (decisions, metrics, state).
    
    Parameters:
        type: str - Type of data being tracked (decision, metric, state, etc.)
        data: Dict - The data to track
        execution_id: str - Orchestration execution ID
        pattern: str - Orchestration pattern being used
        
    Returns:
        tracked_id: str - ID of tracked data
        execution_id: str - Orchestration execution ID
    """
    context = get_or_create_context(data)
    
    track_type = data.get('type', 'general')
    track_data = data.get('data', {})
    
    # Create tracked record
    tracked_record = {
        "id": str(uuid.uuid4()),
        "type": track_type,
        "timestamp": timestamp_utc(),
        "data": track_data,
        "execution_id": context.execution_id,
        "pattern": context.pattern,
        "orchestrator_id": context.orchestrator_id
    }
    
    # Store in context
    context.tracked_data.append(tracked_record)
    
    # Also emit for persistence/analysis
    await event_emitter("composition:track_decision", {
        "pattern": context.pattern,
        "decision": track_type,
        "context": track_data,
        "outcome": track_data.get('outcome', 'tracked'),
        "confidence": track_data.get('confidence', 1.0),
        "agent_id": context.orchestrator_id
    })
    
    return {
        "status": "success",
        "tracked_id": tracked_record["id"],
        "execution_id": context.execution_id,
        "total_tracked": len(context.tracked_data)
    }


@event_handler("orchestration:query")
async def handle_orchestration_query(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get information about orchestration state.
    
    Parameters:
        query_type: str - Type of query (agents, context, tracked, status)
        execution_id: str - Specific execution to query (optional)
        filters: Dict - Additional filters for the query
        
    Returns:
        results: Dict - Query results based on type
    """
    query_type = data.get('query_type', 'status')
    execution_id = data.get('execution_id')
    filters = data.get('filters', {})
    
    if query_type == 'agents':
        # Query agent states
        if execution_id:
            context = _orchestration_contexts.get(execution_id)
            if context:
                # Get status of agents in this orchestration
                agent_statuses = []
                for agent_id in context.agents:
                    # Query individual agent status
                    status_result = await event_emitter("agent:info", {"agent_id": agent_id})
                    if status_result:
                        agent_statuses.append(status_result[0])
                
                return {
                    "status": "success",
                    "execution_id": execution_id,
                    "agents": agent_statuses,
                    "total": len(context.agents)
                }
        else:
            # Return all orchestration-managed agents
            return {
                "status": "success",
                "orchestrated_agents": len(_agent_orchestrations),
                "executions": len(_orchestration_contexts)
            }
    
    elif query_type == 'context':
        # Get orchestration context
        if execution_id:
            context = _orchestration_contexts.get(execution_id)
            if context:
                return {
                    "status": "success",
                    "context": context.to_dict(),
                    "tracked_count": len(context.tracked_data)
                }
        else:
            # Return all contexts
            return {
                "status": "success",
                "contexts": {
                    eid: ctx.to_dict() 
                    for eid, ctx in _orchestration_contexts.items()
                }
            }
    
    elif query_type == 'tracked':
        # Get tracked data
        if execution_id:
            context = _orchestration_contexts.get(execution_id)
            if context:
                # Apply filters if provided
                tracked = context.tracked_data
                if filters.get('type'):
                    tracked = [t for t in tracked if t['type'] == filters['type']]
                
                return {
                    "status": "success",
                    "execution_id": execution_id,
                    "tracked_data": tracked,
                    "count": len(tracked)
                }
    
    return {
        "status": "success",
        "message": f"Query type '{query_type}' completed"
    }


@event_handler("orchestration:coordinate")
async def handle_orchestration_coordinate(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flexible synchronization (barrier, turns, checkpoint).
    
    Parameters:
        type: str - Coordination type (barrier, turns, checkpoint, custom)
        agents: Union[List[str], str] - Agents to coordinate ("all" for all in execution)
        timeout: float - Maximum wait time
        execution_id: str - Orchestration execution ID
        options: Dict - Type-specific options
        
    Returns:
        coordinated: List[str] - Agents that reached coordination point
        timed_out: List[str] - Agents that timed out
        duration: float - Time taken
    """
    start_time = time.time()
    context = get_or_create_context(data)
    
    coord_type = data.get('type', 'barrier')
    agents_spec = data.get('agents', 'all')
    timeout = data.get('timeout', 60.0)
    options = data.get('options', {})
    
    # Determine which agents to coordinate
    if agents_spec == "all":
        target_agents = list(context.agents)
    elif isinstance(agents_spec, list):
        target_agents = agents_spec
    else:
        return {"error": "Invalid 'agents' parameter"}
    
    # Create coordination ID
    coord_id = f"coord_{context.execution_id}_{uuid.uuid4().hex[:8]}"
    
    # Track coordination state
    coordinated = []
    timed_out = []
    pending = set(target_agents)
    
    if coord_type == "barrier":
        # Barrier: All agents must reach this point before any can proceed
        barrier_point = options.get('point', 'default')
        
        # Notify all agents about the barrier
        for agent_id in target_agents:
            try:
                await event_emitter("agent:send_message", {
                    "agent_id": agent_id,
                    "message": {
                        "_coordination": {
                            "type": "barrier",
                            "id": coord_id,
                            "point": barrier_point,
                            "wait_for": target_agents,
                            "timeout": timeout
                        },
                        "instruction": f"Wait at barrier '{barrier_point}' until all agents are ready"
                    }
                })
            except Exception as e:
                logger.warning(f"Failed to notify {agent_id} about barrier: {e}")
        
        # Wait for all agents to acknowledge reaching the barrier
        deadline = time.time() + timeout
        acknowledged = set()
        
        # Simplified implementation - in production would use proper event subscription
        while len(acknowledged) < len(target_agents) and time.time() < deadline:
            # In production, would listen for coordination acknowledgments
            # For now, simulate with a delay
            await asyncio.sleep(0.5)
            
            # Simulate some agents acknowledging (in production, from real events)
            if len(acknowledged) < len(target_agents) * 0.8:  # 80% succeed
                for agent_id in list(pending)[:1]:  # One at a time
                    acknowledged.add(agent_id)
                    pending.discard(agent_id)
                    coordinated.append(agent_id)
        
        # Mark remaining as timed out
        timed_out = list(pending)
        
        # Release the barrier for coordinated agents
        for agent_id in coordinated:
            try:
                await event_emitter("agent:send_message", {
                    "agent_id": agent_id,
                    "message": {
                        "_coordination": {
                            "type": "barrier_release",
                            "id": coord_id,
                            "point": barrier_point
                        },
                        "instruction": f"Barrier '{barrier_point}' released - proceed"
                    }
                })
            except Exception as e:
                logger.warning(f"Failed to release barrier for {agent_id}: {e}")
    
    elif coord_type == "turns":
        # Turn-based coordination: Agents proceed in order
        turn_order = options.get('order', target_agents)  # Default to given order
        turn_duration = options.get('turn_duration', 10.0)
        
        current_turn = 0
        deadline = time.time() + timeout
        
        while current_turn < len(turn_order) and time.time() < deadline:
            agent_id = turn_order[current_turn]
            
            # Grant turn to agent
            try:
                await event_emitter("agent:send_message", {
                    "agent_id": agent_id,
                    "message": {
                        "_coordination": {
                            "type": "turn_grant",
                            "id": coord_id,
                            "turn": current_turn,
                            "duration": turn_duration
                        },
                        "instruction": f"Your turn ({current_turn + 1}/{len(turn_order)})"
                    }
                })
                
                # Wait for turn duration or completion signal
                turn_deadline = min(time.time() + turn_duration, deadline)
                await asyncio.sleep(min(turn_duration, deadline - time.time()))
                
                coordinated.append(agent_id)
                pending.discard(agent_id)
                
            except Exception as e:
                logger.warning(f"Failed to coordinate turn for {agent_id}: {e}")
                timed_out.append(agent_id)
                pending.discard(agent_id)
            
            current_turn += 1
        
        # Any remaining agents are timed out
        timed_out.extend(list(pending))
    
    elif coord_type == "checkpoint":
        # Checkpoint: Agents can proceed after reaching checkpoint, no need to wait
        checkpoint_name = options.get('name', 'checkpoint')
        
        # Notify agents about checkpoint
        for agent_id in target_agents:
            try:
                await event_emitter("agent:send_message", {
                    "agent_id": agent_id,
                    "message": {
                        "_coordination": {
                            "type": "checkpoint",
                            "id": coord_id,
                            "name": checkpoint_name
                        },
                        "instruction": f"Checkpoint '{checkpoint_name}' - acknowledge when reached"
                    }
                })
                
                # In checkpoint mode, we don't wait - just mark as coordinated
                coordinated.append(agent_id)
                pending.discard(agent_id)
                
            except Exception as e:
                logger.warning(f"Failed to send checkpoint to {agent_id}: {e}")
                timed_out.append(agent_id)
                pending.discard(agent_id)
    
    elif coord_type == "custom":
        # Custom coordination logic provided in options
        custom_logic = options.get('logic', {})
        
        # This is where orchestrators can implement their own coordination patterns
        # For now, just acknowledge all agents
        coordinated = target_agents
        pending.clear()
    
    else:
        return {
            "error": f"Unknown coordination type: {coord_type}",
            "supported_types": ["barrier", "turns", "checkpoint", "custom"]
        }
    
    # Track the coordination event
    await event_emitter("composition:track_decision", {
        "pattern": context.pattern,
        "decision": f"coordination_{coord_type}",
        "context": {
            "type": coord_type,
            "agents": len(target_agents),
            "coordinated": len(coordinated),
            "timed_out": len(timed_out),
            "options": options
        },
        "outcome": "success" if len(coordinated) == len(target_agents) else "partial",
        "agent_id": context.orchestrator_id
    })
    
    return {
        "status": "success",
        "type": coord_type,
        "coordinated": coordinated,
        "timed_out": timed_out,
        "total_agents": len(target_agents),
        "success_rate": len(coordinated) / len(target_agents) if target_agents else 0,
        "duration": time.time() - start_time,
        "execution_id": context.execution_id,
        "coordination_id": coord_id
    }


# Helper Functions

async def select_agents_by_criteria(criteria: Dict[str, Any]) -> List[str]:
    """Select agents based on criteria like role, status, capabilities."""
    # Query all agents
    all_agents_result = await event_emitter("agent:list", {})
    if not all_agents_result:
        return []
    
    all_agents = all_agents_result[0].get('agents', [])
    selected = []
    
    for agent in all_agents:
        # Check each criterion
        match = True
        
        if 'role' in criteria:
            # Check if agent has the required role in metadata
            agent_role = agent.get('metadata', {}).get('role')
            if agent_role != criteria['role']:
                match = False
                
        if 'status' in criteria:
            # Check agent status
            if agent.get('status') != criteria['status']:
                match = False
                
        if 'orchestration' in criteria:
            # Check if agent is part of specific orchestration
            agent_orch = _agent_orchestrations.get(agent['agent_id'], {})
            if agent_orch.get('execution_id') != criteria['orchestration']:
                match = False
        
        if match:
            selected.append(agent['agent_id'])
    
    return selected


# Helper functions for aggregation
def extract_value(item: Dict[str, Any], path: str) -> Any:
    """Extract value from nested dict using dot notation."""
    parts = path.split('.')
    value = item
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def calculate_statistics(values: List[float]) -> Dict[str, float]:
    """Calculate common statistics for a list of values."""
    import statistics
    
    if not values:
        return {}
    
    stats = {
        "count": len(values),
        "mean": statistics.mean(values),
        "min": min(values),
        "max": max(values)
    }
    
    if len(values) > 1:
        stats["std_dev"] = statistics.stdev(values)
        stats["variance"] = statistics.variance(values)
        
        # Calculate median
        stats["median"] = statistics.median(values)
        
        # Calculate confidence interval (95%)
        if "std_dev" in stats:
            margin = 1.96 * stats["std_dev"] / (len(values) ** 0.5)
            stats["confidence_interval_95"] = {
                "lower": stats["mean"] - margin,
                "upper": stats["mean"] + margin
            }
    
    return stats


@event_handler("orchestration:aggregate")
async def handle_orchestration_aggregate(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flexible aggregation for collected data.
    
    Parameters:
        data: List[Dict] - Data to aggregate (e.g., responses, scores, votes)
        method: str - Aggregation method: vote, statistical, consensus, custom
        options: Dict - Method-specific options
        group_by: str - Optional field to group before aggregating
        filters: Dict - Pre-aggregation filters
        execution_id: str - Orchestration execution ID
    """
    import statistics
    from collections import Counter
    
    context = get_or_create_context(data)
    
    items = data.get('data', [])
    method = data.get('method', 'statistical')
    options = data.get('options', {})
    group_by = data.get('group_by')
    filters = data.get('filters', {})
    
    # Apply filters
    if filters:
        filtered_items = []
        for item in items:
            include = True
            for field, value in filters.items():
                if extract_value(item, field) != value:
                    include = False
                    break
            if include:
                filtered_items.append(item)
        items = filtered_items
    
    # Group if requested
    if group_by:
        groups = {}
        for item in items:
            key = extract_value(item, group_by)
            if key not in groups:
                groups[key] = []
            groups[key].append(item)
        
        # Aggregate each group
        results = {}
        for key, group_items in groups.items():
            results[key] = await _aggregate_items(group_items, method, options)
        
        return {
            "status": "success",
            "method": method,
            "grouped_by": group_by,
            "results": results,
            "group_count": len(groups),
            "total_items": len(items),
            "execution_id": context.execution_id
        }
    else:
        # Single aggregation
        result = await _aggregate_items(items, method, options)
        
        return {
            "status": "success",
            "method": method,
            **result,
            "execution_id": context.execution_id
        }


async def _aggregate_items(items: List[Dict[str, Any]], method: str, options: Dict[str, Any]) -> Dict[str, Any]:
    """Perform aggregation on a list of items."""
    import statistics
    from collections import Counter
    
    if method == "vote":
        # Voting aggregation
        vote_type = options.get('type', 'majority')
        extract_field = options.get('extract_field', 'data.choice')
        min_votes = options.get('min_votes', 1)
        
        # Extract votes
        votes = []
        for item in items:
            vote = extract_value(item, extract_field)
            if vote is not None:
                votes.append(vote)
        
        if len(votes) < min_votes:
            return {
                "result": None,
                "error": f"Insufficient votes: {len(votes)} < {min_votes}",
                "metadata": {"votes_cast": len(votes), "min_required": min_votes}
            }
        
        if vote_type == "majority":
            # Simple majority
            vote_counts = Counter(votes)
            winner, count = vote_counts.most_common(1)[0]
            
            return {
                "result": winner,
                "confidence": count / len(votes),
                "metadata": {
                    "vote_counts": dict(vote_counts),
                    "total_votes": len(votes),
                    "winner_votes": count
                }
            }
        
        elif vote_type == "plurality":
            # Top N choices
            top_n = options.get('top_n', 3)
            vote_counts = Counter(votes)
            top_choices = vote_counts.most_common(top_n)
            
            return {
                "result": [choice for choice, _ in top_choices],
                "metadata": {
                    "vote_counts": dict(vote_counts),
                    "total_votes": len(votes),
                    "top_choices": [{"choice": c, "votes": v} for c, v in top_choices]
                }
            }
        
        elif vote_type == "ranked":
            # Instant runoff or other ranked choice methods
            algorithm = options.get('algorithm', 'instant_runoff')
            # Simplified implementation - would need full ranked choice logic
            vote_counts = Counter(votes)
            
            return {
                "result": vote_counts.most_common(1)[0][0],
                "metadata": {
                    "algorithm": algorithm,
                    "rounds": 1,  # Would track elimination rounds
                    "final_counts": dict(vote_counts)
                }
            }
    
    elif method == "statistical":
        # Statistical aggregation
        metric = options.get('metric', 'mean')
        extract_field = options.get('extract_field', 'data.value')
        confidence_level = options.get('confidence_level', 0.95)
        include = options.get('include', [])
        
        # Extract numeric values
        values = []
        for item in items:
            value = extract_value(item, extract_field)
            if value is not None and isinstance(value, (int, float)):
                values.append(float(value))
        
        if not values:
            return {
                "result": None,
                "error": "No numeric values found",
                "metadata": {"items_processed": len(items)}
            }
        
        # Calculate requested metric
        if metric == "mean":
            result = statistics.mean(values)
        elif metric == "median":
            result = statistics.median(values)
        elif metric == "trimmed_mean":
            trim_percent = options.get('trim_percent', 0.1)
            trim_count = int(len(values) * trim_percent)
            if trim_count > 0:
                sorted_values = sorted(values)
                trimmed = sorted_values[trim_count:-trim_count]
                result = statistics.mean(trimmed) if trimmed else statistics.mean(values)
            else:
                result = statistics.mean(values)
        else:
            result = statistics.mean(values)
        
        # Calculate additional statistics if requested
        stats = calculate_statistics(values)
        metadata = {"base_stats": stats}
        
        # Add requested additional metrics
        if "variance" in include:
            metadata["variance"] = stats.get("variance")
        if "std_dev" in include:
            metadata["std_dev"] = stats.get("std_dev")
        if "confidence_interval" in include:
            metadata["confidence_interval"] = stats.get("confidence_interval_95")
        
        return {
            "result": result,
            "confidence": 1.0 - (stats.get("std_dev", 0) / stats.get("mean", 1) if stats.get("mean") else 0),
            "metadata": metadata
        }
    
    elif method == "consensus":
        # Weighted consensus
        weights = options.get('weights', {})
        threshold = options.get('threshold', 0.5)
        extract_field = options.get('extract_field', 'data.value')
        
        # Calculate weighted average
        total_weight = 0
        weighted_sum = 0
        
        for item in items:
            # Get agent ID for weight lookup
            agent_id = item.get('agent_id') or extract_value(item, 'data.agent_id')
            weight = weights.get(agent_id, 1.0)
            
            value = extract_value(item, extract_field)
            if value is not None and isinstance(value, (int, float)):
                weighted_sum += float(value) * weight
                total_weight += weight
        
        if total_weight == 0:
            return {
                "result": None,
                "error": "No weighted values found",
                "metadata": {"items_processed": len(items)}
            }
        
        consensus_value = weighted_sum / total_weight
        
        # Check if consensus meets threshold
        participation = len(items) / len(weights) if weights else 1.0
        confidence = participation * (1.0 - abs(consensus_value - 0.5) * 2)  # Higher confidence near extremes
        
        return {
            "result": consensus_value,
            "confidence": confidence,
            "metadata": {
                "weighted_average": consensus_value,
                "total_weight": total_weight,
                "participation": participation,
                "threshold_met": confidence >= threshold
            }
        }
    
    elif method == "custom":
        # Custom aggregation function
        function_name = options.get('function')
        parameters = options.get('parameters', {})
        
        # This would call a registered custom aggregation function
        # For now, return error
        return {
            "error": f"Custom function '{function_name}' not implemented",
            "metadata": {"requested_function": function_name}
        }
    
    else:
        return {
            "error": f"Unknown aggregation method: {method}",
            "metadata": {"supported_methods": ["vote", "statistical", "consensus", "custom"]}
        }


# System event handlers
@event_handler("system:context")
async def handle_context(context: Dict[str, Any]) -> None:
    """Receive module context with event emitter."""
    global event_emitter
    # Get router for event emission
    router = get_router()
    event_emitter = router.emit
    logger.info("Orchestration primitives received context, event_emitter configured")


# Cleanup and Context Management

@event_handler("orchestration:cleanup")
async def handle_orchestration_cleanup(data: Dict[str, Any]) -> Dict[str, Any]:
    """Clean up orchestration context when done."""
    execution_id = data.get('execution_id')
    
    if execution_id and execution_id in _orchestration_contexts:
        context = _orchestration_contexts[execution_id]
        
        # Remove agent associations
        for agent_id in context.agents:
            if agent_id in _agent_orchestrations:
                del _agent_orchestrations[agent_id]
        
        # Remove context
        del _orchestration_contexts[execution_id]
        
        return {
            "status": "success",
            "execution_id": execution_id,
            "cleaned_up": True
        }
    
    return {
        "status": "error",
        "error": f"Execution {execution_id} not found"
    }


# Note: We keep orchestration primitives as handlers rather than transformers
# because we need to track responses and maintain orchestration context.
# While transformers would reduce event duplication, they don't allow us to
# capture the results of the transformed events, which is essential for
# tracking spawned agents, message delivery status, etc.