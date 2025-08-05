# Universal WatchService and PubSub Architecture

## Executive Summary

This document outlines the design and implementation plan for two foundational KSI services:
1. **WatchService** - A universal event watching and triggering service (event futures)
2. **PubSubService** - A unified publish/subscribe infrastructure

These services will consolidate scattered watch-and-trigger patterns across KSI into a coherent, reusable architecture that integrates seamlessly with existing capabilities like transformers, dynamic routing, and event scheduling.

## Current State Analysis

### Existing Watch-and-Trigger Patterns

KSI currently has multiple services implementing similar patterns:

1. **Monitor Service**
   - Subscription management for event streams
   - Pattern-based matching with wildcards
   - Direct delivery to client writers

2. **Message Bus**
   - Agent-to-agent pub/sub
   - Topic-based routing
   - Offline message queuing

3. **Injection Router**
   - Watches for completion results
   - State-based matching by request_id
   - Queued injection delivery

4. **Evaluation Service (Planned)**
   - Needs to watch for agent:result events
   - Match by agent_id
   - Inject results back to waiting process

### Architectural Challenges

1. **Pattern Duplication** - Each service reimplements similar logic
2. **State Management** - No unified approach to tracking "waiting for" state
3. **Performance Concerns** - Risk of O(n*m) complexity if watching all events
4. **Integration Gaps** - Services can't easily share watch patterns

## Proposed Architecture

### WatchService Design

The WatchService provides **event futures** - the ability to register interest in future events and trigger actions when they arrive.

#### Core Concepts

1. **Targeted Registration** - Watch only specific event patterns, not all events
2. **Declarative Patterns** - YAML-based watch definitions in `var/lib/watchers`
3. **State Management** - Track active watches with lifecycle management
4. **Efficient Matching** - Use event system's existing routing for performance

#### Watch Pattern Schema

```yaml
# var/lib/watchers/evaluation/judge_completion.yaml
watchers:
  - name: "judge_result_watcher"
    description: "Watch for LLM judge completion results"
    
    # What to watch for
    match:
      events: ["agent:result"]  # Event patterns to watch
      criteria:                 # Dynamic matching criteria
        result_type: "optimization_evaluation"
        agent_id: "{{agent_id}}"  # From registration data
    
    # How to deliver matches
    delivery:
      method: "inject"          # Always inject for now
      target: "{{requester_id}}" # Who registered the watch
      format: "system_reminder"
      
    # Lifecycle management
    lifecycle:
      ttl: 300                  # 5 minute timeout
      max_matches: 1            # Complete after first match
      on_timeout: 
        event: "evaluation:judge_timeout"
        data:
          optimization_id: "{{optimization_id}}"
```

#### Implementation Strategy

```python
class WatchService:
    def __init__(self):
        self.watchers = {}  # watch_id -> WatchConfig
        self.watches_by_event = {}  # event_pattern -> [watch_ids]
        self.patterns = {}  # Loaded from YAML
        self.scheduler = EventScheduler()  # For TTL/timeouts
        
    async def register_watch(self, data: WatchRegistration):
        """Register a new watch with targeted event handlers"""
        watch_id = generate_id()
        pattern_name = data["pattern"]
        watch_data = data["watch_data"]
        
        # Load pattern from YAML
        pattern = self.patterns[pattern_name]
        
        # Create watch config with resolved variables
        watch_config = self.resolve_pattern(pattern, watch_data)
        
        # Register targeted handlers for each event pattern
        for event_pattern in watch_config["match"]["events"]:
            handler = self.create_targeted_handler(watch_id)
            
            # Dynamic registration with event system
            await self.event_router.register_handler(
                event_pattern, 
                handler,
                priority=EventPriority.FIRST
            )
            
            # Track for cleanup
            self.watches_by_event[event_pattern].append(watch_id)
        
        # Schedule timeout if specified
        if watch_config["lifecycle"]["ttl"]:
            self.scheduler.schedule_event(
                time.time() + watch_config["lifecycle"]["ttl"],
                {"event": "watch:timeout", "data": {"watch_id": watch_id}}
            )
        
        self.watchers[watch_id] = watch_config
        return watch_id
```

### PubSubService Design

A unified pub/sub service that all KSI services can use for publish/subscribe patterns.

#### Core Features

1. **Universal Subscription Management**
2. **Multiple Delivery Methods** (event, stream, queue, inject)
3. **Pattern-Based Topic Matching**
4. **Subscriber Lifecycle Management**

#### API Design

```python
@event_handler("pubsub:subscribe")
async def subscribe(data: SubscriptionRequest, context):
    """Universal subscription endpoint"""
    # data = {
    #     "subscriber_id": "unique_id",
    #     "topics": ["pattern1", "pattern2"],
    #     "delivery_method": "inject|event|stream|queue",
    #     "delivery_config": {...},
    #     "match_criteria": {...}  # Optional content matching
    # }

@event_handler("pubsub:publish")
async def publish(data: PublishRequest, context):
    """Publish to all matching subscribers"""
    # data = {
    #     "topic": "event:name",
    #     "content": {...},
    #     "metadata": {...}
    # }

@event_handler("pubsub:unsubscribe")
async def unsubscribe(data: UnsubscribeRequest, context):
    """Remove subscription"""
```

## Integration with Existing Systems

### 1. Transformer Integration

WatchService patterns are similar to transformers but with state:

```yaml
# Transformer (stateless)
- source: "agent:result"
  target: "evaluation:process"
  condition: "agent_id == 'specific_agent'"

# Watch (stateful, with lifecycle)
- match:
    events: ["agent:result"]
    criteria:
      agent_id: "{{agent_id}}"
  lifecycle:
    ttl: 300
    max_matches: 1
```

### 2. Dynamic Routing Integration

Watches can create dynamic routing rules:

```python
# When registering a watch
await emit_event("routing:add_rule", {
    "rule_id": f"watch_{watch_id}",
    "source_event": "agent:result",
    "target_event": "watch:matched",
    "condition": f"agent_id == '{agent_id}'",
    "priority": 100,
    "ttl": 300  # Auto-cleanup
})
```

### 3. Event Scheduler Integration

```python
# Use existing scheduler for all timing
self.scheduler.schedule_event(
    event_time=time.time() + ttl,
    event_data={
        "event": "watch:timeout",
        "data": {"watch_id": watch_id}
    }
)
```

### 4. State Service Integration

```python
# Persist watches for recovery
await emit_event("state:entity:create", {
    "type": "watch",
    "id": watch_id,
    "properties": watch_config,
    "relationships": [{
        "type": "registered_by",
        "target_type": "agent",
        "target_id": agent_id
    }]
})
```

## Migration Plan

### Phase 1: Core Infrastructure (Week 1-2)

1. **Implement PubSubService**
   - Core subscription management
   - Delivery method abstraction
   - Pattern matching engine

2. **Implement WatchService**
   - YAML pattern loading
   - Targeted event registration
   - Lifecycle management
   - Integration with scheduler

### Phase 2: Service Migration (Week 3-4)

#### Monitor Service Migration
```python
# Before
client_subscriptions[client_id] = patterns
client_writers[client_id] = writer

# After
await emit_event("pubsub:subscribe", {
    "subscriber_id": f"monitor_{client_id}",
    "topics": patterns,
    "delivery_method": "stream",
    "delivery_config": {"writer": writer}
})
```

#### Message Bus Migration
```python
# Before
self.subscriptions[agent_id] = event_types
self.offline_queue[agent_id].append(message)

# After
await emit_event("pubsub:subscribe", {
    "subscriber_id": f"agent_{agent_id}",
    "topics": event_types,
    "delivery_method": "queue",
    "delivery_config": {"queue_on_offline": True}
})
```

#### Injection Router Migration
```python
# Before
injection_metadata_store[request_id] = metadata
# Complex state management

# After
await emit_event("watch:register", {
    "pattern": "completion_result",
    "watch_data": {
        "request_id": request_id,
        "injection_metadata": metadata
    }
})
```

### Phase 3: Evaluation Service Implementation (Week 5)

```python
# New evaluation service using WatchService
async def spawn_judge_and_wait(self, judge_agent_id, optimization_id):
    # Register watch for judge result
    watch_id = await emit_event("watch:register", {
        "pattern": "judge_result_watcher",
        "watch_data": {
            "agent_id": judge_agent_id,
            "requester_id": "evaluation_service",
            "optimization_id": optimization_id
        }
    })
    
    # Spawn judge agent
    await emit_event("agent:spawn", {
        "agent_id": judge_agent_id,
        "component": "evaluations/quality/optimization_judge"
    })
    
    # Watch will automatically deliver result via injection
```

### Phase 4: Advanced Features (Week 6+)

1. **Watch Chains** - Watches that create new watches
2. **Watch Groups** - Coordinate multiple watches
3. **Conditional Watches** - Complex matching logic
4. **Performance Optimization** - Index by event prefix

## Performance Considerations

### Targeted Registration Benefits

- **No Universal Polling** - Only process relevant events
- **O(1) Handler Lookup** - Use event system's hash-based routing
- **Minimal Memory** - Only active watches in memory
- **Lazy Pattern Loading** - Load YAML patterns on demand

### Scalability Design

```python
# Efficient event indexing
watches_by_event = {
    "agent:result": ["watch_1", "watch_2"],
    "optimization:complete": ["watch_3"],
    # Scales linearly with unique event patterns, not total watches
}

# Quick rejection for non-watched events
if event_name not in self.watches_by_event:
    return  # No watches for this event
```

## Success Metrics

1. **Performance**
   - Sub-millisecond watch registration
   - < 5% overhead on event emission
   - Linear scaling with watch count

2. **Adoption**
   - All 4 existing services migrated
   - 50% reduction in service-specific watch code
   - New services use WatchService by default

3. **Reliability**
   - Zero missed events
   - Proper timeout handling
   - Clean recovery after restart

## Future Enhancements

1. **Persistent Watches** - Survive daemon restarts
2. **Watch Analytics** - Monitor watch patterns and performance
3. **Smart Indexing** - Optimize based on usage patterns
4. **Cross-Instance Watches** - Distributed KSI deployments

## Conclusion

The WatchService and PubSubService represent a fundamental evolution in KSI's event-driven architecture. By providing a unified, efficient way to watch for future events and manage pub/sub patterns, these services will:

1. Simplify development of async workflows
2. Improve system performance through targeted registration
3. Enable new patterns of agent coordination
4. Provide a foundation for future distributed capabilities

The design leverages KSI's existing strengths (event routing, scheduling, state management) while adding the missing piece: efficient, stateful event watching with lifecycle management.