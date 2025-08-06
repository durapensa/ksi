# Async State and PubSub Architecture

## Executive Summary

This document outlines the architecture for async state and pub/sub patterns in KSI. We compose existing services rather than creating new ones, using the state service for queuing and dynamic routing for all watch-and-trigger patterns.

**Key Principles**: 
- State is ephemeral - for active tracking and queuing only
- Everything is async and event-driven - no blocking operations
- Routing patterns as data (YAML) - not embedded in code
- Services as pattern libraries - teaching agents coordination

## Core Patterns

### 1. Async State Queues

The state service provides queue operations for async coordination:
- `async_state:push` - Add items to a queue with TTL
- `async_state:pop` - Remove and return items (FIFO)
- `async_state:get_queue` - Peek without removing
- `async_state:expire` - TTL-based cleanup

### 2. Hybrid Routing Persistence

Routing rules support three persistence classes:
- **ephemeral** - State DB only, cleared on restart
- **persistent** - State DB + YAML files in `var/lib/routes/`
- **system** - Defined in transformer YAML files

Example routing rule with persistence:
```python
await emit_event("routing:add_rule", {
    "rule_id": f"watch_{request_id}",
    "source_pattern": "completion:result",
    "condition": f"data.request_id == '{request_id}'",
    "target": "my_service:handle_result",
    "ttl": 300,  # 5 minute timeout
    "persistence_class": "ephemeral",  # or "persistent" 
    "parent_scope": {"type": "agent", "id": agent_id}  # Cleanup with parent
})
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
            # For completion priority injection style
            rule = {
                "rule_id": rule_id,
                "source_pattern": topic,
                "target": "completion:inject",  # Priority completion queue
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

## Next Steps

### Phase 2: Agent-Ready Evaluation Pattern

**Goal**: Make evaluation service the first consumer of async patterns, building vocabulary for future agent orchestration.

#### Key Insight: Services as Pattern Libraries

The evaluation service is **temporary scaffolding** - we're establishing **event-driven patterns** that agents will eventually use directly. Every service handler we write is teaching agents how to coordinate.

#### Agent-Ready Async Pattern

```python
# PATTERN: Async evaluation with routing-based result delivery
# This will eventually be replaced by agents creating these routing rules directly

@event_handler("evaluation:async")
async def handle_evaluation_async(data, context):
    """Non-blocking evaluation - returns immediately."""
    optimization_id = data["optimization_id"]
    optimization_result = data["optimization_result"]
    
    # Generate tracking IDs
    evaluation_id = f"eval_{optimization_id}_{uuid.uuid4().hex[:8]}"
    judge_agent_id = f"judge_{evaluation_id}"
    
    # Create routing rule for result capture (will be YAML template)
    await emit_event("routing:add_rule", {
        "rule_id": f"judge_complete_{evaluation_id}",
        "source_pattern": "completion:result",
        "condition": f"data.agent_id == '{judge_agent_id}'",
        "target": "evaluation:judge_completed",
        "mapping": {
            "evaluation_id": evaluation_id,
            "optimization_id": optimization_id,
            "judge_response": "{{data.response}}",
            "optimization_result": optimization_result
        },
        "ttl": 600,  # 10 minute timeout
        "persistence_class": "ephemeral",  # Or "persistent" for debugging
        "parent_scope": {"type": "agent", "id": judge_agent_id}
    })
    
    # Spawn judge (agents will learn this pattern)
    await emit_event("agent:spawn", {
        "agent_id": judge_agent_id,
        "component": "evaluations/judges/optimization_judge",
        "metadata": {"evaluation_id": evaluation_id}
    })
    
    # Send prompt (using regular async, not inject)
    await emit_event("completion:async", {
        "agent_id": judge_agent_id,
        "prompt": build_evaluation_prompt(optimization_result)
    })
    
    # Return immediately - caller listens for evaluation:result
    return {
        "status": "evaluation_started",
        "evaluation_id": evaluation_id,
        "judge_agent_id": judge_agent_id
    }

@event_handler("evaluation:judge_completed")
async def handle_judge_completed(data, context):
    """Process routed judge results."""
    # Extract and process evaluation
    evaluation = extract_evaluation(data["judge_response"])
    
    # Emit result event for listeners
    await emit_event("evaluation:result", {
        "evaluation_id": data["evaluation_id"],
        "optimization_id": data["optimization_id"],
        "recommendation": evaluation["recommendation"],
        "evaluation": evaluation
    })
    
    # Trigger downstream actions if accepted
    if evaluation["recommendation"] == "accept":
        await emit_event("composition:update_component", {...})
```

#### YAML Routing Templates

Instead of hardcoding routing rules, we'll use loadable templates:

```yaml
# var/lib/transformers/evaluation/judge_result_routing.yaml
name: judge_result_routing
description: Routes judge completion results back to evaluation service
version: 1.0.0
transformers:
  - name: judge_completion_to_evaluation
    source_pattern: "completion:result"
    target: "evaluation:judge_completed"
    condition: |
      data.agent_id and data.agent_id.startswith('judge_')
    mapping:
      evaluation_id: "{{data.metadata.evaluation_id}}"
      judge_response: "{{data.response}}"
    enabled: true
```

#### Future Agent Composition Pattern

Agents will eventually compose these patterns directly:

```python
# Future agent internal reasoning (not code):
"""
To evaluate an optimization:
1. Create routing rule: completion:result → evaluation:judge_completed
2. Spawn judge agent with evaluation component
3. Send evaluation prompt via completion:async
4. Listen for evaluation:result event
5. Act on recommendation (accept/reject/revise)
"""

# Agent might emit this pattern:
await emit_event("workflow:create", {
    "workflow_id": "evaluate_optimization",
    "agents": [
        {
            "id": "judge",
            "component": "evaluations/judges/optimization_judge",
            "routing_rules": [
                {
                    "source": "completion:result",
                    "target": "evaluation:judge_completed",
                    "condition": "data.agent_id == '{{agent.id}}'"
                }
            ]
        }
    ]
})
```

#### Why This Pattern is Agent-Ready

1. **No Hidden State** - Everything flows through observable events
2. **Composable Primitives** - Routing rules, agent spawning, event emission
3. **Pattern Recognition** - Agents can learn by observing event sequences
4. **No Blocking** - Fully async enables parallel agent coordination
5. **YAML Templates** - Routing patterns as data, not code

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

#### Completion Priority Queue Integration
```python
# The completion service now uses priority queues
# completion:inject provides high-priority processing

# Direct priority completion:
await emit_event("completion:inject", {
    "agent_id": target_agent,
    "messages": [{"role": "user", "content": "High priority task"}],
    "priority": "high",  # Jumps ahead of queued async requests
    "originator_id": requesting_agent
})

# Dynamic routing controls result flow
await emit_event("routing:add_rule", {
    "source_pattern": "completion:result",
    "condition": f"data.agent_id == '{target_agent}'",
    "target": "evaluation:process_result"
})
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

### Evaluation Service Refactoring
1. Implement `evaluation:async` handler for non-blocking evaluation
2. Add `evaluation:judge_completed` handler for routed results
3. Create YAML routing templates for common patterns
4. Test async flow with dynamic routing rules

### Service Migrations
- Monitor service to use pubsub patterns
- Message bus to use async state queues
- Completion service documentation updates

## Key Insights

- **"Watching" is just routing with lifecycle management** - Create routing rules with TTL to watch for events
- **Services are pattern libraries for agents** - We're teaching coordination patterns, not building permanent services
- **Everything async, everything events** - No blocking operations enable parallel agent coordination
- **Routing patterns as YAML** - Configuration as data enables agent learning and composition