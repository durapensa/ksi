# KSI Enhanced Session Management & Multi-Agent Coordination Design

## Executive Summary

This document presents a comprehensive design for enhancing the KSI (Knowledge System Interface) multi-agent system with robust session management, conversation locking, and flexible event delivery mechanisms. The design ensures linear consistency per agent while supporting complex multi-agent orchestrations with natural conversation patterns.

## Table of Contents

1. [Core Requirements](#core-requirements)
2. [Session Management Architecture](#session-management-architecture)
3. [Conversation Locking & Fork Prevention](#conversation-locking--fork-prevention)
4. [Message Routing with Natural Conversations](#message-routing-with-natural-conversations)
5. [Multicast Completion Layer](#multicast-completion-layer)
6. [Race Condition Detection](#race-condition-detection)
7. [Flexible Event Delivery Modes](#flexible-event-delivery-modes)
8. [Implementation Architecture](#implementation-architecture)
9. [Integration with Existing KSI Systems](#integration-with-existing-ksi-systems)
10. [Implementation Roadmap](#implementation-roadmap)

## Core Requirements

### Linear Consistency Per Agent
- Each agent maintains its own linearly consistent event stream
- No global ordering required or desired
- Session chains begin with initial completion request (no session_id)
- Subsequent requests maintain session continuity via session_id

### Conversation Patterns
- Support N-way conversations with all agents as participants
- Enable point-to-point and point-to-multipoint conversations
- Natural message routing with from/to fields (like human conversations)
- Complete conversation history tracking and reconstruction

### Delivery Flexibility
- Per-agent configurable event delivery modes
- Immediate delivery for urgent events
- Queued delivery for agent-controlled processing
- Emergency broadcast override capability

### Persistence & Reliability
- Session state survives daemon restarts
- Minimal storage for efficient reconstruction
- SQLite-backed persistence using existing state system

## Session Management Architecture

### Persistent Session Registry

The session registry prevents conversation forking by enforcing single --resume per session_id per agent, with SQLite persistence for daemon restart survival.

```sql
-- session_registry table
CREATE TABLE session_registry (
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    started_at REAL NOT NULL,  -- time.time() epoch seconds
    last_active REAL NOT NULL,
    status TEXT DEFAULT 'active',  -- active, completed, expired
    metadata TEXT,  -- JSON: correlation_id, parent_session, etc.
    PRIMARY KEY (session_id, agent_id)
);

-- conversation_events table (for history reconstruction)
CREATE TABLE conversation_events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- message, completion, state_change
    timestamp REAL NOT NULL,
    from_agent TEXT,
    to_agents TEXT,  -- JSON array for multicast
    event_data TEXT NOT NULL,  -- Minimal JSON: type, correlation_id
    FOREIGN KEY (session_id, agent_id) REFERENCES session_registry
);

CREATE INDEX idx_session_timeline ON conversation_events(session_id, timestamp);
CREATE INDEX idx_agent_timeline ON conversation_events(agent_id, timestamp);
```

### Session Registry Plugin Implementation

```python
# plugins/session/session_registry.py
import time
import json
from uuid import uuid4

class SessionRegistry:
    def __init__(self, db_connection):
        self.db = db_connection
        self._init_tables()
        
    async def validate_resume(self, agent_id, session_id):
        """Enforce single --resume per session_id per agent"""
        cursor = self.db.execute(
            "SELECT status FROM session_registry WHERE session_id = ? AND agent_id = ?",
            (session_id, agent_id)
        )
        row = cursor.fetchone()
        
        if row and row[0] == 'active':
            return {"error": "Session already active", "status": "rejected"}
            
        # Register new session or reactivate
        self.db.execute(
            """INSERT OR REPLACE INTO session_registry 
               (session_id, agent_id, started_at, last_active, status) 
               VALUES (?, ?, ?, ?, 'active')""",
            (session_id, agent_id, time.time(), time.time())
        )
        self.db.commit()
        
        return {"status": "allowed", "session_id": session_id}
        
    async def record_event(self, event_data):
        """Record conversation event for history reconstruction"""
        event_record = {
            "event_id": str(uuid4()),
            "session_id": event_data.get("session_id"),
            "agent_id": event_data.get("agent_id"),
            "event_type": event_data.get("type"),
            "timestamp": time.time(),
            "from_agent": event_data.get("from"),
            "to_agents": json.dumps(event_data.get("to", [])),
            "event_data": json.dumps({
                "correlation_id": event_data.get("correlation_id"),
                "msg_type": event_data.get("msg_type"),
                # NOT storing full content - that's in logs
            })
        }
        
        self.db.execute(
            """INSERT INTO conversation_events 
               (event_id, session_id, agent_id, event_type, timestamp, 
                from_agent, to_agents, event_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            tuple(event_record.values())
        )
        self.db.commit()
```

### Session Lifecycle Management

```python
# Session state transitions
async def handle_session_lifecycle(event_name, data, context):
    session_id = data.get("session_id")
    agent_id = data.get("agent_id")
    
    if event_name == "session:start":
        # New session without session_id (first request)
        if not session_id:
            session_id = f"sess_{uuid4()}"
            data["session_id"] = session_id
            
        return await registry.create_session(agent_id, session_id)
        
    elif event_name == "session:resume":
        # Validate resume attempt
        return await registry.validate_resume(agent_id, session_id)
        
    elif event_name == "session:end":
        # Mark session as completed
        return await registry.end_session(agent_id, session_id)
```

## Conversation Locking & Fork Prevention

### Fork Detection Scenarios

#### Scenario 1: Resume Conflict
```
Agent A receives: --resume session_123
Agent A receives: --resume session_123 (again, different client)
Result: Second attempt rejected - conversation would fork
```

#### Scenario 2: Completion Response Mismatch
```
Agent A sends: completion:async (gets completion_id: abc)
Agent A receives: completion:result with unexpected session_id
Result: Fork detected - conversation continuity broken
```

#### Scenario 3: Multi-Party Drift
```
N-way conversation with Agents A, B, C
Agent B processes old message while A & C have moved forward
Result: B's response could create timeline inconsistency
```

### Fork Prevention Implementation

```python
class ConversationLockManager:
    def __init__(self):
        self.active_locks = {}  # {conversation_id: lock_info}
        
    async def acquire_lock(self, conversation_id, agent_id, timeout=30):
        """Acquire conversation lock with timeout"""
        lock_key = f"conv_lock:{conversation_id}"
        
        # Check existing lock
        if lock_key in self.active_locks:
            lock_info = self.active_locks[lock_key]
            if time.time() - lock_info["acquired_at"] < timeout:
                return {
                    "status": "denied",
                    "holder": lock_info["agent_id"],
                    "expires_in": timeout - (time.time() - lock_info["acquired_at"])
                }
                
        # Acquire lock
        self.active_locks[lock_key] = {
            "agent_id": agent_id,
            "acquired_at": time.time(),
            "timeout": timeout
        }
        
        return {"status": "acquired", "lock_id": lock_key}
```

## Message Routing with Natural Conversations

### Enhanced Message Format

Messages include explicit routing information to support natural conversation patterns:

```python
# Enhanced message format with routing
{
    "event": "agent:message",
    "data": {
        "content": "What's the status of the web scraper?",
        "conversation_type": "point-to-point",  # or "multicast", "broadcast"
    },
    "routing": {
        "from": "orchestrator_agent",
        "to": ["scraper_agent"],  # Always a list for consistency
        "cc": [],  # Optional carbon-copy recipients
        "conversation_id": "conv_web_scraper_status",
        "reply_to": "msg_123",  # For threading
    },
    "metadata": {
        "session_id": "sess_abc",
        "timestamp": 1735500000.123,
        "requires_response": true,
        "delivery_mode": "immediate"  # or "queued"
    }
}
```

### Conversation Types

- **Point-to-Point**: Single sender, single recipient
- **Multicast**: Single sender, specific multiple recipients
- **Broadcast**: Single sender, all agents in group
- **Reply**: Response to specific message (threading)

### Message Router Implementation

```python
# plugins/messaging/message_router.py
async def route_message(message):
    """Route messages based on conversation type and recipients"""
    routing = message.get("routing", {})
    from_agent = routing.get("from")
    to_agents = routing.get("to", [])
    cc_agents = routing.get("cc", [])
    conversation_type = message["data"].get("conversation_type")
    
    # Store in conversation history
    await store_conversation_event(message)
    
    # Handle different conversation types
    if conversation_type == "broadcast":
        # Override to_agents with all active agents
        to_agents = await get_all_active_agents()
    
    # Deliver to primary recipients
    for agent_id in to_agents:
        await deliver_to_agent(agent_id, message, "to")
        
    # Deliver to CC recipients (lower priority)
    for agent_id in cc_agents:
        await deliver_to_agent(agent_id, message, "cc")
        
    # Track conversation participation
    await update_conversation_participants(
        routing.get("conversation_id"),
        from_agent, 
        to_agents + cc_agents
    )
    
    # Record routing event
    await registry.record_event({
        "type": "message_routed",
        "session_id": message["metadata"].get("session_id"),
        "agent_id": from_agent,
        "from": from_agent,
        "to": to_agents + cc_agents,
        "conversation_id": routing.get("conversation_id"),
        "correlation_id": message["metadata"].get("correlation_id")
    })
```

## Multicast Completion Layer

### completion:agents Event Handler

A new layer above `completion:async` for coordinated multi-agent completions:

```python
# plugins/completion/multicast_completion.py
async def handle_completion_agents(data, context):
    """
    Multicast completion to multiple agents
    Each agent gets its own completion:async request
    """
    prompt = data.get("prompt")
    target_agents = data.get("agents", [])
    coordination = data.get("coordination", {})
    
    if not target_agents:
        return {"error": "No target agents specified"}
    
    # Generate parent completion ID for tracking
    parent_id = f"multicast_{uuid4()}"
    results = {}
    
    # Coordination options
    wait_for_all = coordination.get("wait_for_all", True)
    timeout = coordination.get("timeout", 300)
    aggregation = coordination.get("aggregation", "none")  # none, merge, vote
    delivery_priority = coordination.get("priority", "normal")
    
    # Create individual completion requests
    completion_tasks = []
    for agent_id in target_agents:
        # Each agent gets personalized context
        agent_prompt = f"[To: {agent_id}] {prompt}"
        
        task = emit_event("completion:async", {
            "prompt": agent_prompt,
            "agent_id": agent_id,
            "parent_completion": parent_id,
            "priority": delivery_priority,
            "routing": {
                "from": context.get("requester_agent"),
                "to": [agent_id],
                "conversation_id": parent_id
            }
        }, context)
        
        completion_tasks.append((agent_id, task))
    
    # Wait strategies
    if wait_for_all:
        # Wait for all completions with timeout
        for agent_id, task in completion_tasks:
            try:
                result = await asyncio.wait_for(task, timeout=timeout)
                results[agent_id] = result
            except asyncio.TimeoutError:
                results[agent_id] = {"error": "timeout", "agent_id": agent_id}
    else:
        # Return first responder
        done, pending = await asyncio.wait(
            [task for _, task in completion_tasks],
            return_when=asyncio.FIRST_COMPLETED
        )
        # Cancel remaining tasks
        for task in pending:
            task.cancel()
        
        # Extract first result
        for agent_id, task in completion_tasks:
            if task in done:
                results[agent_id] = await task
                break
            
    # Apply aggregation strategies
    if aggregation == "merge":
        # Merge all responses into single result
        merged = await merge_completion_results(results)
        return {
            "multicast_id": parent_id,
            "merged_result": merged,
            "individual_results": results
        }
    elif aggregation == "vote":
        # Agents vote on best response
        best = await coordinate_voting(results, target_agents)
        return {
            "multicast_id": parent_id,
            "selected": best,
            "vote_results": results
        }
    else:
        # Return all individual results
        return {
            "multicast_id": parent_id,
            "results": results,
            "summary": {
                "total": len(target_agents),
                "completed": len([r for r in results.values() if "error" not in r]),
                "errors": len([r for r in results.values() if "error" in r])
            }
        }
```

### Aggregation Strategies

```python
async def merge_completion_results(results):
    """Merge multiple completion results intelligently"""
    # Extract successful responses
    responses = [r["response"] for r in results.values() 
                 if "response" in r and "error" not in r]
    
    if not responses:
        return {"error": "No successful completions to merge"}
    
    # Simple concatenation with agent attribution
    merged = []
    for agent_id, result in results.items():
        if "response" in result:
            merged.append(f"[{agent_id}]: {result['response']}")
    
    return {
        "merged_response": "\n\n".join(merged),
        "contributor_count": len(merged)
    }

async def coordinate_voting(results, agents):
    """Have agents vote on best response"""
    # Present options to each agent
    options = {
        agent_id: result.get("response", "")
        for agent_id, result in results.items()
        if "response" in result
    }
    
    if len(options) < 2:
        # No need to vote with single option
        return list(options.items())[0] if options else None
    
    # Collect votes
    votes = {}
    for voter_agent in agents:
        vote_prompt = f"Select the best response:\n"
        for i, (agent_id, response) in enumerate(options.items()):
            vote_prompt += f"\n{i+1}. [{agent_id}]: {response[:100]}..."
        
        vote_result = await emit_event("completion:async", {
            "prompt": vote_prompt,
            "agent_id": voter_agent,
            "max_tokens": 10
        })
        
        # Parse vote (simplified)
        votes[voter_agent] = vote_result
    
    # Tally and return winner
    # (Implementation details omitted for brevity)
    return best_response
```

## Race Condition Detection

### Circuit Breaker for Concurrent Operations

Instead of global ordering, detect and handle race conditions on specific resources:

```python
# plugins/safety/race_detector.py
class RaceConditionDetector:
    def __init__(self):
        self.operation_windows = {}  # Track operations per resource
        self.conflict_threshold = 1.0  # seconds
        
    async def check_race_condition(self, operation):
        """Detect concurrent modifications without global ordering"""
        resource = operation.get("resource")  # e.g., "state:project_config"
        agent_id = operation.get("agent_id")
        op_type = operation.get("type")  # read, write, delete
        
        # Check for concurrent modifications
        window_key = f"{resource}:write"
        current_time = time.time()
        
        # Get recent operations on this resource
        recent_ops = self.operation_windows.get(window_key, [])
        
        # Clean old operations outside window
        recent_ops = [op for op in recent_ops 
                      if current_time - op["time"] < self.conflict_threshold]
        
        # Detect write-write races
        if op_type == "write":
            concurrent_writes = [op for op in recent_ops 
                                if op["agent"] != agent_id and op["type"] == "write"]
            if concurrent_writes:
                # Race detected!
                return {
                    "race_detected": True,
                    "conflict_type": "write-write",
                    "conflicting_agents": [op["agent"] for op in concurrent_writes],
                    "resolution": "retry_with_backoff",
                    "suggested_backoff": 0.1 * (len(concurrent_writes) + 1)
                }
        
        # Detect read-write races (optional, for consistency)
        if op_type == "read":
            concurrent_writes = [op for op in recent_ops if op["type"] == "write"]
            if concurrent_writes:
                return {
                    "race_detected": True,
                    "conflict_type": "read-write",
                    "warning": "Reading potentially stale data",
                    "writers": [op["agent"] for op in concurrent_writes]
                }
                
        # Track this operation
        recent_ops.append({
            "agent": agent_id,
            "time": current_time,
            "type": op_type,
            "resource": resource
        })
        self.operation_windows[window_key] = recent_ops
        
        return {"race_detected": False}
        
    async def apply_backoff(self, agent_id, backoff_time):
        """Apply exponential backoff for race resolution"""
        await asyncio.sleep(backoff_time)
        
        # Could also implement priority-based ordering
        # Higher priority agents get shorter backoffs
        
# Integration with state operations
async def safe_state_write(key, value, agent_id):
    """Write with race detection"""
    detector = RaceConditionDetector()
    
    max_retries = 3
    for attempt in range(max_retries):
        # Check for races
        race_check = await detector.check_race_condition({
            "resource": f"state:{key}",
            "agent_id": agent_id,
            "type": "write"
        })
        
        if race_check["race_detected"]:
            if attempt < max_retries - 1:
                # Apply backoff
                await detector.apply_backoff(
                    agent_id, 
                    race_check.get("suggested_backoff", 0.1)
                )
                continue
            else:
                # Final attempt failed
                return {
                    "error": "Race condition persists",
                    "details": race_check
                }
        
        # Proceed with write
        return await emit_event("state:set", {"key": key, "value": value})
    
    return {"error": "Max retries exceeded"}
```

## Flexible Event Delivery Modes

### Per-Agent Delivery Preferences

Agents can configure how they receive events, balancing responsiveness with focus:

```python
# Agent profile with delivery preferences
{
    "agent_id": "analyzer_001",
    "profile": {
        "name": "Deep Analyzer",
        "model": "opus",
        "delivery_preferences": {
            "default_mode": "queued",  # Don't interrupt deep analysis
            "immediate_types": ["emergency", "completion:result", "shutdown"],
            "queued_types": ["status_request", "info_update", "todo:delegated"],
            "queue_fetch_strategy": "periodic",  # or "manual", "event_driven"
            "queue_fetch_interval": 30,  # seconds, 0 = manual only
            "queue_size_limit": 100,
            "overflow_strategy": "drop_oldest"  # or "reject_new"
        }
    }
}
```

### Event Delivery Handler

```python
# plugins/delivery/event_delivery.py
async def deliver_event_to_agent(agent_id, event):
    """Deliver event based on agent preferences"""
    agent_prefs = await get_agent_preferences(agent_id)
    event_type = event.get("event")
    priority = event.get("metadata", {}).get("priority")
    
    # Emergency always goes through immediately
    if priority == "EMERGENCY":
        return await force_immediate_delivery(agent_id, event)
    
    # System events may override preferences
    if event_type in ["system:shutdown", "system:emergency_broadcast"]:
        return await force_immediate_delivery(agent_id, event)
        
    # Check agent delivery preferences
    delivery_prefs = agent_prefs.get("delivery_preferences", {})
    delivery_mode = delivery_prefs.get("default_mode", "immediate")
    
    # Event-specific overrides
    if event_type in delivery_prefs.get("immediate_types", []):
        delivery_mode = "immediate"
    elif event_type in delivery_prefs.get("queued_types", []):
        delivery_mode = "queued"
        
    # Deliver based on mode
    if delivery_mode == "queued":
        # Store in agent's event queue
        queue_key = f"event_queue:{agent_id}"
        
        # Get current queue with size limit check
        queue = await get_state(queue_key, [])
        size_limit = delivery_prefs.get("queue_size_limit", 100)
        
        if len(queue) >= size_limit:
            # Handle overflow
            overflow_strategy = delivery_prefs.get("overflow_strategy", "drop_oldest")
            if overflow_strategy == "drop_oldest":
                queue = queue[1:]  # Remove oldest
            else:  # reject_new
                return {
                    "delivered": False,
                    "error": "Queue full",
                    "queue_size": len(queue)
                }
        
        # Add event to queue
        queue.append({
            "id": str(uuid4()),
            "event": event,
            "queued_at": time.time(),
            "status": "pending"
        })
        await set_state(queue_key, queue)
        
        # Notify agent if configured
        if delivery_prefs.get("notify_on_queue", False):
            await send_queue_notification(agent_id, len(queue))
            
        return {"delivered": True, "mode": "queued", "queue_size": len(queue)}
    else:
        # Immediate delivery to message queue
        await agent_message_queues[agent_id].put(event)
        return {"delivered": True, "mode": "immediate"}
```

### Event Queue Management Tools

```python
# Tools for agents to manage their event queues
async def EventQueueRead(types=None, status="pending", limit=10, mark_read=False):
    """
    Read events from agent's queue
    
    Args:
        types: Optional list of event types to filter
        status: Filter by status (pending, read, processed)
        limit: Maximum events to return
        mark_read: Mark returned events as read
    """
    agent_id = get_current_agent_id()
    queue_key = f"event_queue:{agent_id}"
    
    queue = await get_state(queue_key, [])
    
    # Apply filters
    filtered = queue
    if types:
        filtered = [e for e in filtered 
                   if e["event"]["event"] in types]
    if status:
        filtered = [e for e in filtered 
                   if e.get("status", "pending") == status]
    
    # Get limited results
    results = filtered[:limit]
    
    # Mark as read if requested
    if mark_read:
        for event in results:
            event["status"] = "read"
            event["read_at"] = time.time()
        await set_state(queue_key, queue)
    
    return results

async def EventQueueProcess(event_ids, action="processed"):
    """
    Update status of events in queue
    
    Args:
        event_ids: List of event IDs to update
        action: New status (processed, dismissed, deferred)
    """
    agent_id = get_current_agent_id()
    queue_key = f"event_queue:{agent_id}"
    
    queue = await get_state(queue_key, [])
    updated = 0
    
    for event in queue:
        if event.get("id") in event_ids:
            event["status"] = action
            event[f"{action}_at"] = time.time()
            updated += 1
            
    await set_state(queue_key, queue)
    
    # Clean processed events if configured
    if action == "processed":
        # Keep only non-processed events
        queue = [e for e in queue if e.get("status") != "processed"]
        await set_state(queue_key, queue)
    
    return {"updated": updated, "action": action}

async def EventQueueSubscribe(event_types, delivery_mode="queued"):
    """
    Subscribe to specific event types with delivery preference
    """
    agent_id = get_current_agent_id()
    prefs = await get_agent_preferences(agent_id)
    
    delivery_prefs = prefs.get("delivery_preferences", {})
    
    if delivery_mode == "immediate":
        immediate_types = set(delivery_prefs.get("immediate_types", []))
        immediate_types.update(event_types)
        delivery_prefs["immediate_types"] = list(immediate_types)
    else:  # queued
        queued_types = set(delivery_prefs.get("queued_types", []))
        queued_types.update(event_types)
        delivery_prefs["queued_types"] = list(queued_types)
    
    # Update preferences
    prefs["delivery_preferences"] = delivery_prefs
    await update_agent_preferences(agent_id, prefs)
    
    return {
        "subscribed": event_types,
        "delivery_mode": delivery_mode
    }
```

### Emergency Broadcast System

```python
# Emergency broadcast implementation
async def emergency_broadcast(message, source="system", targets="all"):
    """
    Override all delivery modes for critical events
    
    Args:
        message: Emergency message content
        source: Originator of emergency
        targets: "all" or list of specific agent_ids
    """
    event = {
        "event": "system:emergency_broadcast",
        "data": {
            "message": message,
            "source": source,
            "timestamp": time.time(),
            "severity": "critical"
        },
        "metadata": {
            "priority": "EMERGENCY",
            "delivery_mode": "broadcast",
            "bypass_queues": True,
            "require_acknowledgment": True
        }
    }
    
    # Determine target agents
    if targets == "all":
        target_agents = await get_all_active_agents()
    else:
        target_agents = targets
    
    # Force immediate delivery to all target agents
    delivery_results = {}
    for agent_id in target_agents:
        try:
            # Bypass normal queue, inject directly
            await force_inject_to_agent(agent_id, event)
            delivery_results[agent_id] = "delivered"
            
            # Track acknowledgment requirement
            await set_state(
                f"emergency_ack:{agent_id}:{event['data']['timestamp']}", 
                {"status": "pending", "event": event}
            )
        except Exception as e:
            delivery_results[agent_id] = f"failed: {str(e)}"
    
    # Log for audit
    await emit_event("monitor:emergency_broadcast", {
        "event": event,
        "targets": target_agents,
        "results": delivery_results,
        "timestamp": time.time()
    })
    
    return {
        "broadcast_id": f"emergency_{int(event['data']['timestamp'])}",
        "delivered_to": len([r for r in delivery_results.values() if r == "delivered"]),
        "failed": len([r for r in delivery_results.values() if r.startswith("failed")]),
        "details": delivery_results
    }

async def acknowledge_emergency(broadcast_id, agent_id):
    """Acknowledge receipt of emergency broadcast"""
    ack_key = f"emergency_ack:{agent_id}:{broadcast_id}"
    ack_data = await get_state(ack_key)
    
    if not ack_data:
        return {"error": "No pending emergency acknowledgment"}
    
    ack_data["status"] = "acknowledged"
    ack_data["ack_time"] = time.time()
    await set_state(ack_key, ack_data)
    
    # Notify monitoring
    await emit_event("monitor:emergency_acknowledged", {
        "broadcast_id": broadcast_id,
        "agent_id": agent_id,
        "ack_time": ack_data["ack_time"]
    })
    
    return {"status": "acknowledged"}
```

## Implementation Architecture

### Plugin Structure

```
ksi_daemon/plugins/
├── session/
│   ├── __init__.py
│   ├── session_registry.py      # Core session management
│   └── session_plugin.py        # Plugin registration
├── routing/
│   ├── __init__.py
│   ├── message_router.py        # Message routing logic
│   └── routing_plugin.py        # Plugin registration
├── completion/
│   ├── __init__.py
│   ├── multicast_completion.py  # completion:agents handler
│   └── completion_plugin.py     # Plugin registration
├── delivery/
│   ├── __init__.py
│   ├── event_delivery.py        # Flexible delivery modes
│   ├── event_queue_tools.py     # Agent queue management
│   └── delivery_plugin.py       # Plugin registration
└── safety/
    ├── __init__.py
    ├── race_detector.py         # Race condition detection
    ├── emergency_broadcast.py   # Emergency system
    └── safety_plugin.py         # Plugin registration
```

### Event Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Enhanced KSI Event Flow                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Agent A                    Core Daemon                Agent B│
│     │                           │                         │   │
│     ├──[session:start]─────────>│                         │   │
│     │<─[session_id: sess_123]───┤                         │   │
│     │                           │                         │   │
│     ├──[completion:agents]─────>│                         │   │
│     │   agents: [B, C]          ├──[completion:async]────>│   │
│     │   coordination: wait_all  ├──[completion:async]────>│C  │
│     │                           │                         │   │
│     │                           │<─[completion:result]────┤   │
│     │                           │<─[completion:result]────┤C  │
│     │<─[multicast results]──────┤                         │   │
│     │                           │                         │   │
│     ├──[agent:message]─────────>│                         │   │
│     │   routing.to: [B]         ├──[Check delivery mode]  │   │
│     │                           ├──[Queue if configured]  │   │
│     │                           ├──[Or immediate]────────>│   │
│     │                           │                         │   │
│     │                           │<─[EventQueueRead]───────┤   │
│     │                           ├──[Return queued events]>│   │
│     │                           │                         │   │
└─────────────────────────────────────────────────────────────┘
```

## Integration with Existing KSI Systems

### Leveraging Existing Infrastructure

1. **State Service Integration**
   - Use existing SQLite backend for session registry
   - Leverage namespace patterns for event queues
   - Maintain ACID properties for concurrent access

2. **Event System Integration**
   - New events follow existing taxonomy patterns
   - Correlation ID support maintained
   - Plugin hooks for all new functionality

3. **Composition System Integration**
   - Agent delivery preferences in profiles
   - Tool access patterns for queue management
   - Capability-based feature enablement

### New Event Taxonomy Additions

```yaml
# Session Management
session:start         # Initialize new session
session:resume        # Resume with session_id validation
session:end          # Mark session completed
session:validate     # Check session status

# Enhanced Routing
routing:message      # Route message with from/to
routing:multicast    # Multicast to multiple agents
routing:broadcast    # Broadcast to all agents

# Multicast Completions
completion:agents    # Multi-agent completion request

# Event Delivery
delivery:queue       # Queue event for agent
delivery:immediate   # Force immediate delivery
delivery:subscribe   # Update delivery preferences

# Emergency System
system:emergency_broadcast    # Override all delivery modes
system:emergency_acknowledge  # Confirm emergency receipt

# Queue Management (Agent Tools)
queue:read          # Read from event queue
queue:process       # Update event status
queue:subscribe     # Manage subscriptions
```

## Implementation Roadmap

### Phase 1: Core Session Management (Days 1-2)
1. **Session Registry Plugin**
   - SQLite tables creation
   - Session validation logic
   - Basic lifecycle management
   - Fork prevention checks

2. **Integration Points**
   - Hook into completion flow
   - Add session_id validation
   - Conversation event logging

### Phase 2: Message Routing Enhancement (Days 2-3)
1. **Message Router Plugin**
   - From/to/cc routing logic
   - Conversation type handling
   - Message threading support

2. **History Tracking**
   - Conversation event storage
   - Timeline reconstruction
   - Participant tracking

### Phase 3: Event Delivery System (Days 3-4)
1. **Delivery Mode Plugin**
   - Agent preference management
   - Queue implementation
   - Delivery mode routing

2. **Event Queue Tools**
   - EventQueueRead implementation
   - EventQueueProcess implementation
   - Subscription management

### Phase 4: Multicast & Emergency (Days 4-5)
1. **Multicast Completion**
   - completion:agents handler
   - Coordination strategies
   - Result aggregation

2. **Emergency Broadcast**
   - Override mechanisms
   - Acknowledgment tracking
   - Audit logging

### Phase 5: Testing & Refinement (Days 5-6)
1. **Integration Testing**
   - Multi-agent scenarios
   - Race condition testing
   - Emergency broadcast drills

2. **Performance Optimization**
   - Queue performance tuning
   - Index optimization
   - Circuit breaker calibration

## Key Design Principles

1. **Linear Consistency Per Agent**
   - Each agent maintains ordered event stream
   - No global ordering required or desired
   - Session chains preserve conversation context

2. **Natural Conversation Patterns**
   - Human-like from/to/cc routing
   - Support for all conversation types
   - Threading and reply tracking

3. **Agent Autonomy**
   - Agents control event processing
   - Flexible delivery preferences
   - Queue management tools

4. **Persistent & Reliable**
   - SQLite-backed critical data
   - Survives daemon restarts
   - Minimal storage footprint

5. **Emergency Override**
   - System can force delivery
   - Acknowledgment tracking
   - Complete audit trail

## Success Metrics

1. **Session Integrity**
   - Zero conversation forks
   - 100% session continuity
   - Complete history reconstruction

2. **Message Delivery**
   - Correct routing 100% of time
   - Delivery mode compliance
   - Emergency broadcast reliability

3. **Performance**
   - Sub-second message routing
   - Efficient queue operations
   - Minimal storage overhead

4. **Agent Experience**
   - Natural conversation flow
   - Uninterrupted deep work
   - Responsive to emergencies

## Conclusion

This design provides KSI with a robust, scalable session management and multi-agent coordination system that maintains linear consistency per agent while supporting flexible, natural conversation patterns. By building on KSI's existing infrastructure and philosophy, the implementation requires minimal core changes while delivering powerful new capabilities for sophisticated multi-agent orchestrations.

The combination of persistent session management, flexible event delivery, and emergency override mechanisms ensures both reliability and agent autonomy, making KSI suitable for complex, long-running multi-agent collaborations.