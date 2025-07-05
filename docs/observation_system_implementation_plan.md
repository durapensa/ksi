# Observation System Implementation Plan

**Date:** 2025-01-05  
**Estimated Time:** 15-19 hours  
**Priority:** High - Addresses architectural debt

## Overview

This plan implements a **clean break replacement** of the observation system, transforming it into pure infrastructure - ephemeral routing rules that agents re-establish on startup, with historical observations served from the event log.

**Key Decision:** No backward compatibility, no gradual migration. The new implementation wholesale replaces the existing one.

**Critical Addition:** Checkpoint/restore capability for true system continuity scenarios.

## Scope: Surgical Change with Smart Recovery

**What We're Changing:**
- Observation subscription storage: From hybrid (database write/memory read) → Pure memory with checkpoint capability
- Add checkpoint/restore hooks for system continuity

**What We're NOT Changing (Everything Else):**
- ✅ Event Log - Continues SQLite persistence with full history
- ✅ Relational State - All agent data remains in SQLite  
- ✅ Completion Logs - JSONL files unchanged
- ✅ All other persistence - Checkpoints, identities, MCP sessions
- ✅ Event APIs - Same observation:subscribe/unsubscribe interface

**Two Operation Modes:**
1. **Normal Restart** - Subscriptions lost, agents re-subscribe (default)
2. **Checkpoint Restore** - Subscriptions preserved, system continues uninterrupted

**Why This Approach Works:**
- No data to migrate (subscriptions already volatile)
- Same API (agents don't need code changes)
- Checkpoint integration for critical scenarios
- Clear semantics based on restart type

## Guiding Principles

1. **Observations are routing rules**, not application data
2. **Agents own their observation needs** and re-establish them
3. **Event log is the source of truth** for historical data
4. **Memory-first design** - subscriptions ephemeral by default
5. **Checkpoint capability** - preserve routing state for system continuity
6. **Clean lifecycle integration** - no orphaned subscriptions
7. **Clean break** - no legacy code, no compatibility layers

## Implementation Phases

### Phase 1: Clean Break - Remove All Persistence (2 hours)

**Goal**: Transform observation system into pure ephemeral infrastructure

**File**: `ksi_daemon/observation/observation_manager.py`

**Clean Break Approach**:
1. **DELETE** all entity/relationship creation code (lines 105-138)
2. **DELETE** any imports related to state persistence
3. **REMOVE** subscription_id from state storage
4. **ADD** clear documentation about ephemeral design
5. **ADD** system:ready handler for agent notification

**Specific Changes**:
```python
# REMOVE these imports if present:
# from ksi_daemon.state import state_manager  # Not needed

# DELETE lines 105-138 entirely (entity and relationship creation)
# This code pretended to persist but never recovered - remove it completely

# UPDATE subscription creation to be explicitly ephemeral:
logger.info(f"Created ephemeral subscription {subscription_id} (will not survive restart)")

# ADD new handler for clean startup signaling:
@event_handler("system:ready")
async def observation_system_ready(data: Dict[str, Any]) -> Dict[str, Any]:
    """Signal that observation system is ready for subscriptions.
    
    This is a clean slate - no subscriptions persist across restarts.
    Agents must re-establish any needed observations.
    """
    logger.info("Observation system ready - ephemeral routing active")
    await emit("observation:ready", {
        "status": "ready",
        "ephemeral": True,
        "message": "Subscriptions must be re-established by agents"
    })
    return {"status": "ready", "subscriptions_active": 0}
```

**Tests to Update**:
- Remove assertions about entity creation
- Add test for observation:ready event
- Verify subscriptions are lost on restart

### Phase 2: Agent Lifecycle Integration (3 hours)

**Goal**: Ensure clean subscription lifecycle management

**Files**: 
- `ksi_daemon/observation/observation_manager.py`
- `ksi_daemon/agent/agent_service.py`

**Changes**:

1. **Add agent termination cleanup**:
```python
@event_handler("agent:terminated")
async def cleanup_agent_subscriptions(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove all subscriptions for terminated agent."""
    agent_id = data.get("agent_id")
    if not agent_id:
        return {"error": "No agent_id provided"}
    
    removed_count = 0
    
    # Remove as observer
    if agent_id in _observers:
        targets = list(_observers[agent_id])
        for target in targets:
            if target in _subscriptions:
                before = len(_subscriptions[target])
                _subscriptions[target] = [
                    sub for sub in _subscriptions[target]
                    if sub["observer"] != agent_id
                ]
                removed_count += before - len(_subscriptions[target])
                
                # Clean up empty lists
                if not _subscriptions[target]:
                    del _subscriptions[target]
        
        del _observers[agent_id]
        logger.info(f"Removed {agent_id} as observer of {len(targets)} targets")
    
    # Remove as target
    if agent_id in _subscriptions:
        observer_count = len(_subscriptions[agent_id])
        
        # Notify observers that target is gone
        for subscription in _subscriptions[agent_id]:
            observer_id = subscription["observer"]
            await emit("observation:target_terminated", {
                "observer": observer_id,
                "target": agent_id,
                "subscription_id": subscription["id"]
            })
        
        del _subscriptions[agent_id]
        removed_count += observer_count
        logger.info(f"Removed {observer_count} observers of {agent_id}")
    
    # Clean up rate limiters
    keys_to_remove = [
        key for key in _rate_limiters.keys()
        if key.startswith(f"{agent_id}_") or key.endswith(f"_{agent_id}")
    ]
    for key in keys_to_remove:
        del _rate_limiters[key]
    
    return {
        "agent_id": agent_id,
        "subscriptions_removed": removed_count,
        "status": "cleaned"
    }
```

2. **Add subscription validation**:
```python
async def _validate_subscription(observer_id: str, target_id: str) -> Dict[str, Any]:
    """Validate that both observer and target agents exist."""
    # Check observer exists
    observer_result = await emit("state:entity:get", {
        "id": observer_id,
        "type": "agent"
    })
    
    if observer_result.get("error") or not observer_result.get("entity"):
        return {"valid": False, "error": f"Observer agent {observer_id} not found"}
    
    # Check target exists
    target_result = await emit("state:entity:get", {
        "id": target_id,
        "type": "agent"
    })
    
    if target_result.get("error") or not target_result.get("entity"):
        return {"valid": False, "error": f"Target agent {target_id} not found"}
    
    return {"valid": True}

# Update subscribe handler to use validation
@event_handler("observation:subscribe")
async def handle_subscribe(data: Dict[str, Any]) -> Dict[str, Any]:
    # ... existing validation ...
    
    # Validate agents exist
    validation = await _validate_subscription(observer, target)
    if not validation["valid"]:
        logger.warning(f"Invalid subscription attempt: {validation['error']}")
        return {"error": validation["error"]}
    
    # ... rest of existing code ...
```

### Phase 3: Agent Re-subscription Pattern (4 hours)

**Goal**: Enable agents to declare and re-establish observations

**Files**:
- `ksi_daemon/agent/agent_service.py`
- `var/lib/fragments/base_multi_agent.yaml`
- New: `var/lib/fragments/observation_patterns.yaml`

**Changes**:

1. **Add observation capabilities to agent profiles**:
```yaml
# In base_multi_agent.yaml or custom fragments
- name: "observation_config"
  inline:
    subscriptions:
      - target_pattern: "child_*"  # Observe all children
        events: ["task:completed", "error:*"]
        filter:
          sampling_rate: 1.0
      - target_pattern: "coordinator"  # Observe coordinator
        events: ["directive:*"]
```

2. **Implement auto-subscription in agent service**:
```python
# In agent_service.py, add to handle_spawn_agent:

async def _setup_agent_observations(agent_id: str, profile: Dict[str, Any]) -> None:
    """Set up observations based on agent profile."""
    observation_config = profile.get("observation_config", {})
    subscriptions = observation_config.get("subscriptions", [])
    
    if not subscriptions:
        return
    
    # Wait for observation system to be ready
    max_retries = 5
    for i in range(max_retries):
        ready_check = await emit("system:service:status", {"service": "observation"})
        if ready_check.get("status") == "ready":
            break
        await asyncio.sleep(0.5 * (i + 1))  # Exponential backoff
    
    # Set up each subscription
    for sub_config in subscriptions:
        target_pattern = sub_config.get("target_pattern")
        
        # Resolve target pattern to actual agent IDs
        if "*" in target_pattern:
            # Query agents matching pattern
            agents_result = await emit("agent:list", {"pattern": target_pattern})
            target_ids = [a["id"] for a in agents_result.get("agents", [])]
        else:
            target_ids = [target_pattern]
        
        # Subscribe to each target
        for target_id in target_ids:
            result = await emit("observation:subscribe", {
                "observer": agent_id,
                "target": target_id,
                "events": sub_config.get("events", ["*"]),
                "filter": sub_config.get("filter", {})
            })
            
            if result.get("error"):
                logger.warning(f"Failed to subscribe {agent_id} to {target_id}: {result['error']}")

# Add to agent spawn success path:
await _setup_agent_observations(agent_id, resolved_profile)
```

3. **Add re-subscription on observation:ready**:
```python
@event_handler("observation:ready")
async def reestablish_observations(data: Dict[str, Any]) -> None:
    """Re-establish observations for all active agents."""
    # Get all active agents
    agents_result = await emit("agent:list", {"status": "active"})
    agents = agents_result.get("agents", [])
    
    logger.info(f"Re-establishing observations for {len(agents)} active agents")
    
    # Set up observations for each agent
    for agent in agents:
        agent_id = agent["id"]
        profile = agent.get("profile", {})
        await _setup_agent_observations(agent_id, profile)
```

### Phase 4: Historical Observation API (3 hours)

**Goal**: Enable querying past observations from event log

**Files**:
- `ksi_daemon/observation/observation_manager.py`
- `ksi_daemon/observation/historical.py` (new)

**New Module**: `ksi_daemon/observation/historical.py`
```python
"""Historical observation queries against event log."""
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from ksi_common.util import get_bound_logger
from ksi_daemon.events import event_handler, emit as event_emitter

logger = get_bound_logger(__name__)


@event_handler("observation:query")
async def query_historical_observations(data: Dict[str, Any]) -> Dict[str, Any]:
    """Query historical observations from event log.
    
    Args:
        observer: Observer agent ID
        target: Target agent ID
        events: List of event patterns to match
        time_range: Dict with 'start' and 'end' ISO timestamps
        limit: Maximum results (default 100)
        offset: Pagination offset
    
    Returns:
        events: List of matching events
        total: Total count of matching events
        has_more: Whether more results exist
    """
    observer = data.get("observer")
    target = data.get("target")
    events = data.get("events", ["*"])
    time_range = data.get("time_range", {})
    limit = min(data.get("limit", 100), 1000)  # Cap at 1000
    offset = data.get("offset", 0)
    
    # Build event log query
    query = {
        "source_agent": target,
        "limit": limit,
        "offset": offset
    }
    
    # Add time range if specified
    if time_range.get("start"):
        query["start_time"] = time_range["start"]
    if time_range.get("end"):
        query["end_time"] = time_range["end"]
    
    # Add event pattern matching
    if events != ["*"]:
        query["event_patterns"] = events
    
    # Query event log
    result = await event_emitter("event_log:query", query)
    
    if result.get("error"):
        return {"error": f"Event log query failed: {result['error']}"}
    
    # Format results
    matching_events = result.get("events", [])
    
    return {
        "observer": observer,
        "target": target,
        "events": matching_events,
        "total": result.get("total", len(matching_events)),
        "has_more": result.get("has_more", False),
        "query": {
            "events": events,
            "time_range": time_range,
            "limit": limit,
            "offset": offset
        }
    }


@event_handler("observation:replay")
async def replay_observations(data: Dict[str, Any]) -> Dict[str, Any]:
    """Replay historical observations to an observer.
    
    Like observation:query but sends results as observation events.
    """
    observer = data.get("observer")
    if not observer:
        return {"error": "Observer agent ID required"}
    
    # Query historical events
    query_result = await query_historical_observations(data)
    
    if query_result.get("error"):
        return query_result
    
    # Replay each event as an observation
    replayed = 0
    for event in query_result["events"]:
        # Send as observation event
        await event_emitter(f"agent:{observer}:observation", {
            "type": "replay",
            "original_event": event["event"],
            "source_agent": event["source_agent"],
            "data": event["data"],
            "timestamp": event["timestamp"],
            "metadata": {
                "replayed_at": datetime.now(timezone.utc).isoformat(),
                "query": query_result["query"]
            }
        })
        replayed += 1
    
    return {
        "observer": observer,
        "replayed_events": replayed,
        "total_available": query_result["total"],
        "has_more": query_result["has_more"]
    }
```

**Update daemon_core.py** to import historical module:
```python
# Add to imports section
from ksi_daemon.observation import historical  # noqa: F401
```

### Phase 5: Performance & Error Handling (2 hours)

**Goal**: Move observation out of hot path, add error recovery

**Changes**:

1. **Async observation queue**:
```python
# In observation_manager.py
_observation_queue: asyncio.Queue = None
_observation_task: Optional[asyncio.Task] = None

@event_handler("system:ready")
async def start_observation_processor(data: Dict[str, Any]) -> Dict[str, Any]:
    global _observation_queue, _observation_task
    
    _observation_queue = asyncio.Queue(maxsize=1000)
    _observation_task = asyncio.create_task(_process_observations())
    
    return {"status": "started"}

async def _process_observations():
    """Process observations asynchronously."""
    while True:
        try:
            batch = []
            # Collect up to 10 observations or wait 100ms
            deadline = asyncio.get_event_loop().time() + 0.1
            
            while len(batch) < 10:
                try:
                    timeout = max(0, deadline - asyncio.get_event_loop().time())
                    item = await asyncio.wait_for(
                        _observation_queue.get(), 
                        timeout=timeout
                    )
                    batch.append(item)
                except asyncio.TimeoutError:
                    break
            
            if batch:
                await _process_observation_batch(batch)
                
        except Exception as e:
            logger.error(f"Observation processor error: {e}")
            await asyncio.sleep(1)  # Back off on errors
```

2. **Circuit breaker for observers**:
```python
from collections import defaultdict
from datetime import datetime, timedelta

_observer_failures = defaultdict(list)
_observer_circuit_open = {}

async def _notify_observer_with_circuit_breaker(
    observer_id: str, 
    event: str, 
    data: Dict[str, Any]
) -> bool:
    """Notify observer with circuit breaker pattern."""
    # Check if circuit is open
    if _observer_circuit_open.get(observer_id, False):
        if datetime.now() < _observer_circuit_open[observer_id]:
            logger.warning(f"Circuit open for observer {observer_id}")
            return False
        else:
            # Try to close circuit
            del _observer_circuit_open[observer_id]
            logger.info(f"Closing circuit for observer {observer_id}")
    
    try:
        # Send observation
        result = await event_emitter(f"agent:{observer_id}:observation", {
            "event": event,
            "data": data
        })
        
        if result.get("error"):
            raise Exception(result["error"])
        
        # Success - clear failures
        if observer_id in _observer_failures:
            del _observer_failures[observer_id]
        
        return True
        
    except Exception as e:
        # Record failure
        _observer_failures[observer_id].append(datetime.now())
        
        # Keep only recent failures (last 5 minutes)
        cutoff = datetime.now() - timedelta(minutes=5)
        _observer_failures[observer_id] = [
            f for f in _observer_failures[observer_id] 
            if f > cutoff
        ]
        
        # Open circuit if too many failures
        if len(_observer_failures[observer_id]) >= 5:
            _observer_circuit_open[observer_id] = datetime.now() + timedelta(minutes=1)
            logger.error(f"Opening circuit for observer {observer_id} due to repeated failures")
        
        return False
```

### Phase 6: Checkpoint/Restore Integration (3 hours)

**Goal**: Enable system continuity through checkpoint/restore

**Files**:
- `ksi_daemon/observation/observation_manager.py`
- Integration with existing checkpoint system

**Implementation**:

1. **Add checkpoint handler**:
```python
@event_handler("checkpoint:collect")
async def collect_observation_state(data: Dict[str, Any]) -> Dict[str, Any]:
    """Collect observation subscriptions for checkpoint.
    
    Only called during system checkpoint operations.
    Normal restarts do NOT trigger this.
    """
    # Flatten subscription data for storage
    subscriptions = []
    for target_id, target_subs in _subscriptions.items():
        for sub in target_subs:
            subscriptions.append({
                "id": sub["id"],
                "observer": sub["observer"],
                "target": target_id,
                "events": sub["events"],
                "filter": sub.get("filter", {}),
                "metadata": sub.get("metadata", {})
            })
    
    logger.info(f"Checkpointing {len(subscriptions)} active subscriptions")
    
    return {
        "observation_subscriptions": {
            "version": "1.0",
            "subscriptions": subscriptions,
            "checkpointed_at": datetime.now(timezone.utc).isoformat()
        }
    }

@event_handler("checkpoint:restore")
async def restore_observation_state(data: Dict[str, Any]) -> Dict[str, Any]:
    """Restore observation subscriptions from checkpoint.
    
    Only called during checkpoint restore operations.
    Normal system starts do NOT trigger this.
    """
    checkpoint_data = data.get("observation_subscriptions", {})
    if not checkpoint_data:
        logger.info("No observation subscriptions in checkpoint")
        return {"restored": 0}
    
    subscriptions = checkpoint_data.get("subscriptions", [])
    restored = 0
    
    # Clear current state
    _subscriptions.clear()
    _observers.clear()
    _rate_limiters.clear()
    
    # Restore each subscription
    for sub in subscriptions:
        try:
            # Reconstruct internal state
            target_id = sub["target"]
            observer_id = sub["observer"]
            
            if target_id not in _subscriptions:
                _subscriptions[target_id] = []
            
            _subscriptions[target_id].append({
                "id": sub["id"],
                "observer": observer_id,
                "events": sub["events"],
                "filter": sub.get("filter", {}),
                "metadata": sub.get("metadata", {})
            })
            
            if observer_id not in _observers:
                _observers[observer_id] = set()
            _observers[observer_id].add(target_id)
            
            # Recreate rate limiter if needed
            if sub.get("filter", {}).get("rate_limit"):
                _rate_limiters[sub["id"]] = RateLimiter(
                    max_events=sub["filter"]["rate_limit"]["max_events"],
                    window_seconds=sub["filter"]["rate_limit"]["window_seconds"]
                )
            
            restored += 1
            
        except Exception as e:
            logger.error(f"Failed to restore subscription {sub.get('id')}: {e}")
    
    logger.info(f"Restored {restored}/{len(subscriptions)} observation subscriptions")
    
    # Notify that observations are ready (different from normal startup)
    await emit("observation:restored", {
        "subscriptions_restored": restored,
        "from_checkpoint": checkpoint_data.get("checkpointed_at")
    })
    
    return {"restored": restored}
```

2. **Distinguish startup modes**:
```python
# Track whether we're in normal or checkpoint restore mode
_restore_mode = False

@event_handler("system:ready")
async def observation_system_ready(data: Dict[str, Any]) -> Dict[str, Any]:
    """Signal observation system ready - mode depends on startup type."""
    global _restore_mode
    
    # Check if we're in checkpoint restore mode
    _restore_mode = data.get("checkpoint_restored", False)
    
    if _restore_mode:
        logger.info("Observation system ready - checkpoint restore mode")
        # Don't emit observation:ready - agents shouldn't re-subscribe
    else:
        logger.info("Observation system ready - normal startup mode")
        # Emit observation:ready for agents to re-subscribe
        await emit("observation:ready", {
            "status": "ready",
            "ephemeral": True,
            "message": "Subscriptions must be re-established by agents"
        })
    
    return {
        "status": "ready",
        "mode": "checkpoint_restore" if _restore_mode else "normal",
        "subscriptions_active": len(_observers)
    }
```

3. **Agent-side handling**:
```python
# Agents should handle both modes
@event_handler("observation:ready")
async def handle_observation_ready(data: Dict[str, Any]) -> None:
    """Re-establish observations on normal startup."""
    # This event only fires on normal startup
    await setup_my_observations()

@event_handler("observation:restored")  
async def handle_observation_restored(data: Dict[str, Any]) -> None:
    """Observations restored from checkpoint - no action needed."""
    logger.info(f"My observations restored: {data['subscriptions_restored']}")
    # Agent continues operating with restored subscriptions
```

**Testing**:
- Test normal restart (subscriptions lost)
- Test checkpoint save/restore (subscriptions preserved)
- Test mixed scenarios (some agents checkpointed, others new)
- Verify rate limiters restore correctly

### Phase 7: Testing & Documentation (2 hours)

**Goal**: Comprehensive tests and clear documentation

**Test Scenarios**:

1. **Lifecycle Tests** (`tests/test_observation_lifecycle.py`):
```python
async def test_subscriptions_cleared_on_restart():
    """Verify subscriptions don't persist across restarts."""
    # Create subscription
    await emit("observation:subscribe", {
        "observer": "test_observer",
        "target": "test_target",
        "events": ["test:*"]
    })
    
    # Simulate restart by clearing module state
    observation_manager._subscriptions.clear()
    observation_manager._observers.clear()
    
    # Verify subscription is gone
    result = await emit("observation:list", {"observer": "test_observer"})
    assert len(result["subscriptions"]) == 0

async def test_agent_termination_cleanup():
    """Verify subscriptions cleaned up on agent termination."""
    # ... test implementation ...

async def test_resubscription_pattern():
    """Verify agents can re-establish subscriptions."""
    # ... test implementation ...
```

2. **Performance Tests** (`tests/test_observation_performance.py`):
```python
async def test_async_observation_performance():
    """Verify observations don't block event emission."""
    # ... test implementation ...

async def test_circuit_breaker():
    """Verify circuit breaker protects against failing observers."""
    # ... test implementation ...
```

**Documentation Updates**:

1. Update `docs/architecture/observation_system.md` with ephemeral design
2. Update agent development guide with re-subscription patterns
3. Add clear examples of observation lifecycle management

## Rollout Plan

### Day 1: Core Infrastructure
- Implement Phase 1-2 (remove persistence, lifecycle integration)
- Run existing tests, fix failures
- Manual testing with basic scenarios

### Day 2: Agent Integration  
- Implement Phase 3-4 (re-subscription patterns, historical API)
- Update agent spawning logic
- Test with multi-agent scenarios

### Day 3: Advanced Features
- Implement Phase 5 (async processing, error handling)
- Implement Phase 6 (checkpoint/restore capability)
- Integration testing with checkpoint system

### Day 4: Finalization
- Implement Phase 7 (comprehensive testing, documentation)
- Performance benchmarking
- Code review and validation
- Final testing of all scenarios

## Success Criteria

1. **Functional**:
   - ✅ Subscriptions are ephemeral on normal restart
   - ✅ Subscriptions preserve correctly via checkpoint/restore
   - ✅ Agents successfully re-subscribe on normal startup
   - ✅ Dead agent subscriptions are cleaned up
   - ✅ Historical observations queryable from event log
   - ✅ Checkpoint restore returns system to exact prior state

2. **Performance**:
   - ✅ Event emission latency < 1ms with observations
   - ✅ Can handle 1000+ active subscriptions
   - ✅ Failed observers don't impact system

3. **Operational**:
   - ✅ Clean daemon restart with auto-recovery
   - ✅ No orphaned subscriptions
   - ✅ Clear error messages and logging

## What Changes vs What Persists

### What Becomes Ephemeral (This Implementation)
- **Observation subscriptions** - In-memory routing rules only
- **Rate limiter state** - Reset on restart
- **Observer mappings** - Rebuilt by agents

### What Remains Persistent (Unchanged)
- **Event Log** - Full SQLite persistence with 30-day retention
- **Relational State** - All agent entities, properties, relationships  
- **Completion Logs** - JSONL files in `var/logs/responses/`
- **Agent Identities** - JSON files on disk
- **Checkpoint System** - SQLite persistence
- **MCP Sessions** - SQLite cache

## Architectural Elegance

This approach achieves the best of both worlds:

1. **Normal Operation** - Simple and clean:
   - Subscriptions are pure ephemeral routing rules
   - No persistence overhead during normal operation
   - Agents naturally re-establish what they need
   - System self-heals through re-subscription

2. **Checkpoint/Restore** - System continuity when needed:
   - Exact routing state preserved for critical scenarios
   - Agents continue uninterrupted with their context
   - No re-negotiation or re-analysis required
   - True system restoration capability

3. **Clear Mental Model**:
   - **Default**: Like SSH connections - reconnect after restart
   - **Checkpoint**: Like hibernation - exact state restored
   - Developers understand exactly when subscriptions persist

## Risk Assessment

**Minimal Risk Due to Clean Break Approach:**

1. **No Migration Complexity**:
   - No dual code paths to maintain
   - No feature flags to test
   - No compatibility bugs
   - Simple git revert if needed

2. **Agent Impact**:
   - Agents already handle observation:ready events
   - Re-subscription pattern is natural
   - No API changes required

3. **Performance**:
   - Removing database writes improves performance
   - Memory-only operations are faster
   - No regression risk

## Clean Break Benefits

1. **Simplicity**: One implementation, one set of tests
2. **Clarity**: No confusion about which mode is active
3. **Speed**: No compatibility overhead
4. **Confidence**: Either it works or it doesn't - no partial states

## Conclusion

This implementation plan executes a **clean break replacement** of the observation system, transforming it from a confused hybrid model to an elegant infrastructure service with two clear modes:

1. **Ephemeral by default** - Simple, self-healing through agent re-subscription
2. **Checkpoint-capable** - Exact state preservation for system continuity

By avoiding backward compatibility complexity and adding strategic checkpoint integration, we achieve:
- Simpler architecture (no fake persistence)
- Better operational semantics (clear when state persists)
- True system continuity capability (via checkpoint/restore)
- Clean mental model (like SSH vs hibernation)

The surgical nature of this change - touching only observation subscriptions while preserving all other persistence layers - combined with checkpoint capability makes this the optimal solution for both normal operations and critical system recovery scenarios.