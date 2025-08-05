# Async State and PubSub Architecture

## Executive Summary

This document outlines the architecture for implementing missing async state functionality and creating common pub/sub patterns across KSI by composing existing services. Rather than introducing new services, we enhance the state service with queue operations and leverage dynamic routing for all watch-and-trigger patterns.

**Key Principles**: 
- State is ephemeral - for active tracking and queuing only. Historical data belongs in logs and monitor's index
- Persistence where needed - queues, routing rules, and transformers survive daemon restarts
- Compose existing services - no new architectural concepts

## Architecture Overview

### Core Components

1. **Enhanced State Service** - Adds async queue operations to existing graph database
2. **Dynamic Routing** - All watch-and-trigger patterns use routing rules with TTL and persistence
3. **PubSub API** - Common interface wrapping routing + state + monitor + completion
4. **Event Scheduler** - Handles all time-based operations (TTL, timeouts)

### Design Principles

1. **Compose, Don't Create** - Use existing services in new combinations
2. **State is Ephemeral** - Active queues and tracking only, no history
3. **Event-Driven** - No polling, use routing rules for triggers
4. **Lifecycle Management** - TTL and parent-scoped cleanup everywhere

## Current State Analysis

### Critical Findings

1. **Injection Router Already Expects async_state** - The completion service's injection router references `async_state:push`, `async_state:get_queue`, etc., but these handlers don't exist
2. **Injection Queues Don't Persist** - All injection metadata is in-memory only, lost on daemon restart
3. **Dynamic Routing Rules Need Persistence** - Currently exist only in memory
4. **Dynamic Transformers Need Persistence** - Should be saved to `var/lib/transformers/dynamic/`

## Implementation Design

### 1. Async State Enhancement

Implement the handlers already expected by injection router:

```python
# In ksi_daemon/core/state.py

class AsyncPushData(TypedDict):
    """Push data to an async queue."""
    namespace: str  # Queue namespace (e.g., "injection", "subscription")
    key: str  # Queue key (e.g., session_id, agent_id)
    data: Dict[str, Any]  # Data to queue
    ttl_seconds: NotRequired[int]  # Queue expiration (default: 3600)

@event_handler("async_state:push")
async def handle_async_push(data: AsyncPushData, context) -> Dict[str, Any]:
    """Push data to an async queue for later retrieval."""
    namespace = data["namespace"]
    key = data["key"]
    queue_data = data["data"]
    ttl_seconds = data.get("ttl_seconds", 3600)
    
    # Create queue entity with items array
    queue_id = f"queue:{namespace}:{key}"
    queue_entity = await state_manager.get_entity(queue_id)
    
    if not queue_entity:
        # Create new queue
        await state_manager.create_entity(
            entity_id=queue_id,
            entity_type="async_queue",
            properties={
                "namespace": namespace,
                "key": key,
                "items": [],
                "created_at": time.time()
            }
        )
    
    # Append to queue
    current_items = queue_entity["properties"].get("items", []) if queue_entity else []
    current_items.append({
        "data": queue_data,
        "pushed_at": time.time()
    })
    
    await state_manager.update_entity(queue_id, {"items": current_items})
    
    # Schedule cleanup
    if ttl_seconds > 0:
        await emit_event("scheduler:schedule_once", {
            "event_time": time.time() + ttl_seconds,
            "event": "async_state:expire_queue",
            "data": {"queue_id": queue_id}
        })
    
    return {"status": "pushed", "queue_size": len(current_items)}

@event_handler("async_state:pop")
async def handle_async_pop(data: AsyncPopData, context) -> Dict[str, Any]:
    """Pop items from queue (FIFO)."""
    namespace = data["namespace"]
    key = data["key"]
    count = data.get("count", 1)
    
    queue_id = f"queue:{namespace}:{key}"
    queue_entity = await state_manager.get_entity(queue_id)
    
    if not queue_entity:
        return {"items": [], "remaining": 0}
    
    items = queue_entity["properties"].get("items", [])
    popped = items[:count]
    remaining = items[count:]
    
    # Update queue
    if remaining:
        await state_manager.update_entity(queue_id, {"items": remaining})
    else:
        # Delete empty queue
        await state_manager.delete_entity(queue_id)
    
    return {
        "items": [item["data"] for item in popped],
        "remaining": len(remaining)
    }

@event_handler("async_state:get_queue")
async def handle_get_queue(data: AsyncGetQueueData, context) -> Dict[str, Any]:
    """Get all items from queue without removing them."""
    namespace = data["namespace"]
    key = data["key"]
    
    queue_id = f"queue:{namespace}:{key}"
    queue_entity = await state_manager.get_entity(queue_id)
    
    if not queue_entity:
        return {"items": [], "exists": False}
    
    items = queue_entity["properties"].get("items", [])
    return {
        "items": [item["data"] for item in items],
        "exists": True,
        "queue_size": len(items)
    }

@event_handler("async_state:expire_queue")
async def handle_expire_queue(data: ExpireQueueData, context) -> Dict[str, Any]:
    """Expire a queue (called by scheduler)."""
    queue_id = data["queue_id"]
    
    # Log expiration for debugging
    queue_entity = await state_manager.get_entity(queue_id)
    if queue_entity:
        logger.info(f"Expiring queue {queue_id} with {len(queue_entity['properties'].get('items', []))} items")
    
    await state_manager.delete_entity(queue_id)
    return {"status": "expired", "queue_id": queue_id}
```

### 2. Persistence Enhancements

#### Dynamic Routing Rule Persistence
```python
@event_handler("routing:add_rule")
async def handle_add_rule_with_persistence(data: AddRuleData, context):
    """Add routing rule with persistence."""
    rule_id = data["rule_id"]
    
    # Create rule in memory as before
    result = await add_routing_rule(data)
    
    # Persist to state for recovery
    await emit_event("state:entity:create", {
        "type": "routing_rule",
        "id": rule_id,
        "properties": {
            "rule_config": data,
            "created_at": time.time(),
            "active": True
        }
    })
    
    # Also save as dynamic transformer
    transformer_yaml = convert_rule_to_transformer(data)
    await emit_event("file:write", {
        "path": f"var/lib/transformers/dynamic/{rule_id}.yaml",
        "content": yaml.dump(transformer_yaml)
    })
    
    return result

# On daemon startup, restore rules
async def restore_routing_rules():
    """Restore routing rules from state on startup."""
    rules = await emit_event("state:entity:query", {
        "type": "routing_rule",
        "filter": {"properties.active": True}
    })
    
    for rule in rules:
        # Check TTL hasn't expired
        rule_config = rule["properties"]["rule_config"]
        if "ttl" in rule_config:
            created_at = rule["properties"]["created_at"]
            if time.time() > created_at + rule_config["ttl"]:
                continue  # Skip expired rules
        
        # Re-register rule
        await add_routing_rule(rule_config)
```

### 3. PubSub Pattern

Create a common API that wraps routing, state, monitor, and completion services:

```python
# New handlers in a pubsub module or distributed across services

@event_handler("pubsub:subscribe")
async def handle_subscribe(data: SubscribeData, context) -> Dict[str, Any]:
    """Common subscription that creates appropriate routing rules."""
    subscriber_id = data["subscriber_id"]
    topics = data["topics"]  # Event patterns like ["agent:*", "optimization:result"]
    delivery = data["delivery"]  # "event", "queue", "stream", "inject"
    config = data.get("config", {})
    
    # Create subscription entity for lifecycle management
    sub_entity_id = f"subscription:{subscriber_id}:{uuid.uuid4().hex[:8]}"
    await emit_event("state:entity:create", {
        "type": "subscription",
        "id": sub_entity_id,
        "properties": {
            "subscriber_id": subscriber_id,
            "topics": topics,
            "delivery": delivery,
            "config": config,
            "active": True
        }
    })
    
    # Create routing rules based on delivery method
    rules_created = []
    for topic in topics:
        rule_id = f"sub_{subscriber_id}_{hash(topic)}"
        
        if delivery == "queue":
            # Route to async queue
            rule = {
                "rule_id": rule_id,
                "source_pattern": topic,
                "target": "pubsub:queue_event",
                "mapping": {
                    "subscriber_id": subscriber_id,
                    "topic": topic,
                    "event_data": "{{__all__}}"
                },
                "parent_scope": {"type": "subscription", "id": sub_entity_id}
            }
            
        elif delivery == "event":
            # Direct event emission
            target_event = config.get("target_event", f"subscriber:{subscriber_id}:notify")
            rule = {
                "rule_id": rule_id,
                "source_pattern": topic,
                "target": target_event,
                "mapping": config.get("mapping", {}),
                "parent_scope": {"type": "subscription", "id": sub_entity_id}
            }
            
        elif delivery == "stream":
            # For monitor-style streaming
            rule = {
                "rule_id": rule_id,
                "source_pattern": topic,
                "target": "monitor:broadcast_event",
                "mapping": {
                    "event_name": "{{__source_event__}}",
                    "event_data": "{{__all__}}",
                    "subscriber_filter": [subscriber_id]
                },
                "parent_scope": {"type": "subscription", "id": sub_entity_id}
            }
            
        elif delivery == "inject":
            # For completion injection style
            rule = {
                "rule_id": rule_id,
                "source_pattern": topic,
                "target": "injection:process_result",
                "condition": config.get("condition"),
                "mapping": config.get("mapping", {}),
                "parent_scope": {"type": "subscription", "id": sub_entity_id}
            }
        
        await emit_event("routing:add_rule", rule)
        rules_created.append(rule_id)
    
    return {
        "subscription_id": sub_entity_id,
        "rules_created": rules_created,
        "status": "active"
    }

@event_handler("pubsub:queue_event")
async def handle_queue_event(data: QueueEventData, context) -> Dict[str, Any]:
    """Queue an event for a subscriber (used by routing rules)."""
    subscriber_id = data["subscriber_id"]
    event_data = data["event_data"]
    
    # Use async_state to queue
    await emit_event("async_state:push", {
        "namespace": "pubsub",
        "key": subscriber_id,
        "data": event_data,
        "ttl_seconds": 86400  # 24 hour retention
    })
    
    # Notify subscriber if online
    await emit_event("pubsub:notify_subscriber", {
        "subscriber_id": subscriber_id,
        "has_messages": True
    })
    
    return {"status": "queued"}

@event_handler("pubsub:get_messages")
async def handle_get_messages(data: GetMessagesData, context) -> Dict[str, Any]:
    """Get queued messages for a subscriber."""
    subscriber_id = data["subscriber_id"]
    pop = data.get("pop", True)  # Remove from queue?
    limit = data.get("limit", 100)
    
    if pop:
        result = await emit_event("async_state:pop", {
            "namespace": "pubsub",
            "key": subscriber_id,
            "count": limit
        })
        return {"messages": result["items"], "remaining": result["remaining"]}
    else:
        result = await emit_event("async_state:get_queue", {
            "namespace": "pubsub", 
            "key": subscriber_id
        })
        return {"messages": result["items"][:limit], "total": result["queue_size"]}
```

### 3. Dynamic Routing Patterns

#### Completion Result Watching
```python
# Instead of polling or waiting
async def setup_completion_watch(request_id: str, target: str):
    """Setup routing rule to watch for completion result."""
    await emit_event("routing:add_rule", {
        "rule_id": f"completion_watch_{request_id}",
        "source_pattern": "completion:result",
        "condition": f"data.request_id == '{request_id}'",
        "target": target,
        "ttl": 300,  # 5 minute timeout
        "mapping": {
            "result": "{{data.response}}",
            "request_id": request_id
        }
    })
```

#### Agent Result Injection
```python
# For evaluation service
async def setup_judge_result_routing(judge_agent_id: str, optimization_id: str):
    """Route judge results back to evaluation."""
    await emit_event("routing:add_rule", {
        "rule_id": f"judge_result_{optimization_id}",
        "source_pattern": "agent:result",
        "condition": f"data.agent_id == '{judge_agent_id}'",
        "target": "evaluation:process_judge_result",
        "mapping": {
            "optimization_id": optimization_id,
            "judgment": "{{data.result}}",
            "judge_agent_id": judge_agent_id
        },
        "ttl": 600,  # 10 minute timeout
        "parent_scope": {
            "type": "agent",
            "id": judge_agent_id
        }
    })
```

### 4. State Management Philosophy

#### What Belongs in State
- **Active Queues**: Messages waiting for delivery
- **Live Subscriptions**: Current routing configurations  
- **Pending Operations**: Temporary tracking during multi-step processes
- **Circuit Breakers**: Rate limiting and safety counters

#### What Does NOT Belong in State
- **Message History**: Use monitor's event log
- **Completed Operations**: Log and delete from state
- **Analytics Data**: Derive from event logs
- **Audit Trails**: Separate append-only logs

#### Cleanup Patterns
```python
# Automatic cleanup via TTL
await emit_event("async_state:push", {
    "namespace": "temp",
    "key": operation_id,
    "data": {"status": "processing"},
    "ttl_seconds": 300  # Auto-cleanup after 5 minutes
})

# Parent-scoped cleanup
await emit_event("routing:add_rule", {
    "parent_scope": {"type": "agent", "id": agent_id}
    # Rule deleted when agent terminates
})

# Explicit cleanup on completion
async def complete_operation(operation_id: str):
    # Log completion
    logger.info(f"Operation {operation_id} completed")
    
    # Clean up state
    await emit_event("state:entity:delete", {
        "type": "operation",
        "id": operation_id
    })
```

## Migration Plan

### Phase 1: Core Infrastructure (Week 1)

1. **Implement async_state handlers**
   - Queue operations in state service (already needed by injection router)
   - TTL-based cleanup via scheduler
   - Test injection router functionality
   - Verify persistence across restarts

2. **Add persistence layer**
   - Dynamic routing rule persistence and restoration
   - Dynamic transformer file generation
   - State-based recovery on startup

3. **Create pubsub handlers**
   - Common subscribe endpoint
   - Queue and retrieval operations
   - Routing rule generation with persistence

### Phase 2: Evaluation Service First (Week 2)

**Goal**: Make evaluation service the first consumer of the new architecture.

```python
# Evaluation service using completion's injection pattern
async def evaluate_optimization_async(optimization_id: str):
    judge_agent_id = f"judge_{optimization_id}"
    
    # Spawn judge agent
    await emit_event("agent:spawn", {
        "agent_id": judge_agent_id,
        "component": "evaluations/judges/optimization_judge",
        "capabilities": ["completion"]
    })
    
    # Send evaluation request with injection config
    # Completion service handles queuing and retry
    await emit_event("completion:async", {
        "agent_id": judge_agent_id,
        "prompt": build_evaluation_prompt(optimization_id),
        "injection_config": {
            "enabled": True,
            "mode": "NEXT",  # Queue for next interaction
            "target": judge_agent_id,
            "trigger_type": "evaluation_complete",
            "metadata": {
                "optimization_id": optimization_id,
                "evaluation_type": "llm_judge"
            }
        }
    })
    
    # Also setup routing for result capture
    await emit_event("routing:add_rule", {
        "rule_id": f"eval_result_{optimization_id}",
        "source_pattern": "agent:result",
        "condition": f"data.agent_id == '{judge_agent_id}'",
        "target": "evaluation:process_result",
        "mapping": {
            "optimization_id": optimization_id,
            "judgment": "{{data.result}}"
        },
        "ttl": 600,
        "parent_scope": {"type": "agent", "id": judge_agent_id}
    })
    
    return {"status": "evaluation_started", "judge_agent_id": judge_agent_id}
```

### Phase 3: Service Migration (Week 3-4)

#### Monitor Service (Breaking Change)
```python
# Direct migration - no compatibility wrapper
# OLD: client_subscriptions[client_id] = patterns
# NEW:
await emit_event("pubsub:subscribe", {
    "subscriber_id": client_id,
    "topics": patterns,
    "delivery": "queue",
    "config": {
        "stream_on_connect": True,
        "batch_size": 100,
        "retention": 86400
    }
})
```

#### Message Bus (Breaking Change)
```python
# Direct migration - no compatibility wrapper
# OLD: self.subscriptions[event_type].add((agent_id, writer))
# NEW:
await emit_event("pubsub:subscribe", {
    "subscriber_id": agent_id,
    "topics": event_types,
    "delivery": "queue",
    "config": {
        "deliver_on_connect": True,
        "max_queue_size": 1000,
        "overflow_policy": "drop_oldest"
    }
})
```

#### Injection Router Enhancement
```python
# The injection router already uses async_state!
# Just need to ensure persistence works

# Current code in injection_router.py:
result = await event_emitter("async_state:push", {
    "namespace": "injection",
    "key": session_id,
    "data": injection_data,
    "ttl_seconds": 3600  # Already has TTL!
})

# Our implementation will make this actually persist!
```

### Phase 4: Advanced Features (Week 5)

1. **Pattern Compilation**
   - Wildcard to regex conversion
   - Efficient matching in routing engine
   - Performance optimization

2. **Delivery Plugins**
   - Webhook delivery option
   - Batch delivery for high-volume
   - Priority queues

3. **Monitoring Integration**
   - Subscription metrics
   - Queue depth monitoring
   - Delivery success rates

## Benefits Over Previous Architecture

1. **No New Services** - Enhances existing services instead
2. **Proven Patterns** - Uses battle-tested routing and state systems
3. **Clean Separation** - State for active data, logs for history
4. **Automatic Cleanup** - TTL and parent-scoping prevent leaks
5. **Unified Interface** - Single pubsub API for all use cases

## Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Implement async_state handlers in state service
- [ ] Test injection router with persistent queues
- [ ] Add routing rule persistence and restoration
- [ ] Create dynamic transformer file generation
- [ ] Implement startup recovery mechanisms

### Phase 2: Evaluation Service
- [ ] Update evaluation service to use async patterns
- [ ] Test with completion injection system
- [ ] Verify persistence across daemon restarts
- [ ] Add timeout handling via routing TTL

### Phase 3: Service Migration
- [ ] Migrate monitor service (breaking change)
- [ ] Migrate message bus (breaking change)
- [ ] Update injection router documentation
- [ ] Test all services with persistence

### Phase 4: Enhancement
- [ ] Add introspection for routing rules by parent
- [ ] Implement queue overflow policies
- [ ] Add performance metrics
- [ ] Create migration guide

## Key Design Decisions

1. **Leverage Existing Expectations** - The injection router already expects async_state handlers
2. **Persistence Where Needed** - Queues, routing rules, and transformers survive restarts
3. **Breaking Changes Are OK** - Clean migration without compatibility debt
4. **Evaluation Service First** - Perfect test case for async patterns
5. **Introspection Over Limits** - Rich observability instead of hard constraints

## Conclusion

This architecture achieves all the goals of the original WatchService design while maintaining KSI's event-driven philosophy. By composing existing services and adding minimal new functionality, we create a powerful pub/sub infrastructure without architectural debt.

The key insights:
- "Watching" is just routing with lifecycle management
- "Pub/Sub" is just routing with queuing
- The injection router already needs what we're building
- Persistence enables reliability for autonomous agent coordination