# Agent Observation System Design

## Overview

This document outlines the design and implementation plan for adding originator-construct agent relationships and observation capabilities to the KSI daemon. The system will enable originator agents to spawn, track, and observe construct agents, providing a hierarchical agent architecture with fine-grained event observation.

## Current Architecture Analysis

### Agent Service (`ksi_daemon/agent/agent_service.py`)
- **Event-driven design**: Agents managed through events without complex inheritance
- **In-memory tracking**: Active agents stored in `agents` dictionary
- **Message queues**: Inter-agent communication via async queues
- **Dynamic composition**: Runtime role updates via composition service
- **Capability enforcement**: Fine-grained permissions through capability system

### Event System (`ksi_daemon/event_system.py`)
- **Pure async router**: Core of the plugin architecture
- **Pattern matching**: Wildcard support (e.g., `state:*`)
- **Concurrent execution**: Handlers run in parallel
- **Middleware support**: Extensible event processing pipeline
- **Auto-registration**: Decorators for handler registration

### State Management (`ksi_daemon/core/state.py`)
- **Three state types**:
  1. Session tracking (in-memory)
  2. Shared state (SQLite key-value)
  3. Async state (SQLite queue operations)
- **Namespace convention**: `agent_id.purpose.detail`
- **Event-based API**: Operations exposed as events

### Event Logging (`ksi_daemon/event_log.py`)
- **Ring buffer**: High-performance with configurable size
- **Pull-based**: No broadcast overhead
- **Stripped payloads**: Large data stored separately
- **Query API**: Pattern and time-based filtering

## Design Principles

1. **Maintain event-driven architecture**: No complex inheritance hierarchies
2. **Backward compatibility**: Existing agents continue to work unchanged
3. **Performance first**: Observation should not impact normal operations
4. **Opt-in complexity**: Advanced features only when needed
5. **Clear relationships**: Explicit originator-construct tracking

## Proposed Architecture

### 1. Agent Metadata Enhancement

Add lightweight metadata to track agent relationships:

```python
@dataclass
class AgentMetadata:
    agent_id: str
    originator_agent_id: Optional[str] = None
    agent_type: Literal["originator", "construct", "system"] = "system"
    spawned_at: float = field(default_factory=time.time)
    purpose: Optional[str] = None
    
    @property
    def is_construct(self) -> bool:
        return self.originator_agent_id is not None
        
    @property
    def is_originator(self) -> bool:
        return self.agent_type == "originator"
```

### 2. State-Based Construct Tracking

Originators track their constructs in state using namespaced keys:

```python
# State key pattern
{originator_id}.constructs.{construct_id} = {
    "spawned_at": timestamp,
    "purpose": "observer_type_a",
    "status": "active",
    "config": {...},
    "capabilities": ["state_read", "agent_messaging"]
}

# Aggregate tracking
{originator_id}.constructs.active_count = 3
{originator_id}.constructs.lifetime_count = 10
```

### 3. Observation System Architecture

#### A. Subscription-Based Model

Originators subscribe to specific events from their constructs:

```python
# Subscribe to construct events
await emit_event("observation:subscribe", {
    "observer": originator_agent_id,
    "target": construct_agent_id,
    "events": ["message:*", "state:*", "error:*"],
    "filter": {
        "exclude": ["system:health"],
        "include_responses": True,
        "sampling_rate": 1.0  # Observe 100% of matching events
    }
})

# Unsubscribe
await emit_event("observation:unsubscribe", {
    "observer": originator_agent_id,
    "target": construct_agent_id
})
```

#### B. Event Flow with Observation

```
1. Construct emits event
2. Event router checks subscriptions
3. If observed:
   a. Emit "observe:begin" to observers
   b. Process original event
   c. Emit "observe:end" with results
4. Continue normal flow
```

#### C. Observation Events

```python
# Observation begin event
{
    "event": "observe:begin",
    "data": {
        "source": construct_agent_id,
        "original_event": "message:send",
        "original_data": {...},
        "timestamp": time.time(),
        "observation_id": unique_id
    }
}

# Observation end event
{
    "event": "observe:end",
    "data": {
        "source": construct_agent_id,
        "original_event": "message:send",
        "result": {...},
        "timestamp": time.time(),
        "observation_id": unique_id,
        "duration_ms": 123
    }
}
```

### 4. Implementation Components

#### A. Observation Manager

New component to manage subscriptions and routing:

```python
class ObservationManager:
    def __init__(self):
        self.subscriptions: Dict[str, List[Subscription]] = {}
        self.observers: Dict[str, Set[str]] = {}
        
    async def subscribe(self, observer: str, target: str, 
                       events: List[str], filter: Dict):
        """Add observation subscription"""
        
    async def unsubscribe(self, observer: str, target: str):
        """Remove observation subscription"""
        
    def should_observe(self, event_name: str, source: str) -> List[str]:
        """Return list of observers for this event"""
        
    async def notify_observers(self, observers: List[str], 
                              event_type: str, data: Dict):
        """Send observation events to observers"""
```

#### B. Event Router Integration

Extend event router to support observation:

```python
# In EventRouter.emit_event
async def emit_event(self, event_name: str, data: dict, 
                    client_id: str = None, source_agent: str = None):
    # Check for observers
    if source_agent:
        observers = self.observation_manager.should_observe(
            event_name, source_agent
        )
        if observers:
            await self._emit_observation_begin(
                observers, event_name, data, source_agent
            )
    
    # Normal event processing
    result = await self._process_event(event_name, data, client_id)
    
    # Notify observers of completion
    if source_agent and observers:
        await self._emit_observation_end(
            observers, event_name, result, source_agent
        )
    
    return result
```

### 5. Capability Integration

New capabilities for the observation system:

```yaml
# In capability_mappings.yaml
spawn_constructs:
  description: "Ability to spawn and manage construct agents"
  events:
    - "agent:spawn"
    - "agent:terminate"
    - "observation:subscribe"
    - "observation:unsubscribe"
    - "state:set"  # For tracking constructs
    - "state:get"
    
observe_agents:
  description: "Ability to observe other agents' events"
  events:
    - "observation:subscribe"
    - "observation:unsubscribe"
    - "observe:query"  # Query observation history
```

### 6. Relational State Foundation

The observation system is built on KSI's universal relational state system:

#### Entity-Property-Relationship Model
- **Entities**: Agents, subscriptions, observation records
- **Properties**: Stored as key-value pairs with type preservation
- **Relationships**: spawned, observes, owns, monitors

#### Graph Operations for Observation
The relational state provides efficient graph operations perfect for observation patterns:
- **Traversal**: Find all constructs of an originator at any depth
- **Bulk Creation**: Spawn multiple observers in one operation
- **Aggregation**: Count active observers by type or status
- **Bidirectional Queries**: Find who observes an agent or who an agent observes

#### Example State Operations
```python
# Agent entity
await emit_event("state:entity:create", {
    "type": "agent",
    "id": agent_id,
    "properties": {
        "status": "active",
        "agent_type": agent_type,
        "profile": profile_name
    }
})

# Spawned relationship
await emit_event("state:relationship:create", {
    "from": originator_id,
    "to": construct_id,
    "type": "spawned",
    "metadata": {"purpose": purpose}
})

# Query constructs (simple)
result = await emit_event("state:relationship:query", {
    "from": originator_id,
    "type": "spawned"
})

# Graph traversal (efficient for hierarchies)
result = await emit_event("state:graph:traverse", {
    "from": originator_id,
    "direction": "outgoing",
    "types": ["spawned", "observes"],
    "depth": 2,
    "include_entities": True
})

# Count constructs by type
result = await emit_event("state:aggregate:count", {
    "target": "entities",
    "group_by": "type",
    "where": {"agent_type": "construct"}
})
```

### 7. Use Cases

#### A. Multi-Aspect Observation

An originator spawns multiple constructs to observe different aspects:

```python
# Originator spawns specialized observers
construct_1 = await spawn_construct("error_observer", 
    subscribe_to=["error:*", "exception:*"])
    
construct_2 = await spawn_construct("performance_observer",
    subscribe_to=["timing:*", "metric:*"])
    
construct_3 = await spawn_construct("behavior_observer", 
    subscribe_to=["message:*", "decision:*"])
```

#### B. Hierarchical Observation

Constructs can spawn their own sub-constructs:

```
Originator
├── AnalysisConstruct
│   ├── DataCollector
│   └── DataProcessor
└── ReportingConstruct
    ├── Formatter
    └── Publisher
```

#### C. Filtered Observation

Observe only specific patterns or conditions:

```python
await emit_event("observation:subscribe", {
    "observer": originator_id,
    "target": construct_id,
    "events": ["state:set"],
    "filter": {
        "key_pattern": "*.results.*",
        "value_contains": "error",
        "rate_limit": 10  # Max 10 events per second
    }
})
```

## Implementation Status

### Phase 1: Agent Metadata ✓ COMPLETED
- Added `AgentMetadata` dataclass with originator tracking
- Updated agent spawn to include relationship metadata
- Enhanced agent info with quick-access fields
- Added `agent:list_constructs` event handler

### Phase 2: Universal Relational State System ✓ COMPLETED
- Replaced key-value state with entity-property-relationship model
- Implemented clean event API for relational operations
- Database schema with entities, properties, and relationships tables
- Automatic ISO timestamp conversion for display
- Tested with comprehensive test script

**Key Design Decision**: Instead of a specialized agent relationship store, we implemented a universal relational state system that can handle all types of entities and relationships. This provides maximum flexibility for future features.

### Phase 3: Observation Subscription System ✓ COMPLETED
- Created `ObservationManager` component in `ksi_daemon/observation/`
- Implemented subscription event handlers: subscribe/unsubscribe/list
- Integrated observation into event router's emit method
- Added pattern matching with fnmatch for flexible event filtering
- Implemented sampling rate support for high-volume events
- Created notify_observers for sending observe:begin/end events
- Prevented observation loops by excluding observe:* and observation:* events
- Added comprehensive test script in examples/

**Key Implementation Details**:
- Source agent detection from context or data (`agent_id`, `source_agent`)
- Observation events include original data, results, errors, and handler count
- Subscriptions stored both in memory and relational state
- Clean integration without modifying existing event handler signatures

### Phase 4: Enhanced Filtered Event Routing ✓ COMPLETED
- Added comprehensive filter utilities to event_system.py
- Enhanced observation system to support content-based filtering
- Implemented rate limiting for observation subscriptions
- Created reusable filter functions for common patterns
- Added examples demonstrating filtered routing
- Documented the previously hidden filter_func feature

**Filter Utilities Added**:
- `RateLimiter`: Configurable rate limiting with time windows
- `content_filter`: Field-based filtering with operators
- `source_filter`: Allow/block lists for event sources
- `context_filter`: Filter by execution context
- `data_shape_filter`: Validate data structure
- `combine_filters`: Compose multiple filters with AND/OR logic

**Observation Enhancements**:
- Content matching on any data field with dot notation
- Per-subscription rate limiting with automatic cleanup
- Integration with event router's existing filter system
- Support for complex filtering scenarios

## Implementation Phases

### Phase 1: Agent Metadata (Immediate) ✓ COMPLETED
- Add `AgentMetadata` class
- Update agent spawn to include `originator_agent_id`
- Modify agent service to track relationships
- Update agent info endpoints

### Phase 2: State-Based Tracking (High Priority) ✓ COMPLETED
- Implement construct tracking in state
- Add helper methods for construct management
- Create construct lifecycle events
- Add construct discovery endpoints

### Phase 3: Observation Subscription (Medium Priority) ✓ COMPLETED
- Create `ObservationManager` component
- Implement subscription/unsubscription
- Add subscription persistence
- Create subscription query endpoints

### Phase 4: Event Routing Integration (Medium Priority) ✓ COMPLETED
- Integrate observation into event router
- Implement `observe:begin` and `observe:end` events
- Add performance monitoring
- Create observation filtering

### Phase 5: Historical Analysis (Low Priority) ✓ COMPLETED
- Add observation event logging
- Implement replay capabilities
- Create analysis tools
- Add observation metrics

## Phase 5 Implementation Details

### Observation Recording
- Automatic recording of all observe:begin and observe:end events
- Stored in relational state as observation_record entities
- Captures event data, results, timing, and duration

### Query Capabilities
```python
{"event": "observation:query_history", "data": {
    "observer": "originator_1",
    "target": "construct_1",
    "event_name": "message:*",
    "since": timestamp,
    "until": timestamp,
    "limit": 100,
    "include_data": true
}}
```

### Replay System
```python
{"event": "observation:replay", "data": {
    "filter": {...},  # Same as query_history
    "speed": 2.0,     # Replay speed multiplier
    "target_agent": "agent_id",  # Optional target override
    "as_new_events": true  # Re-emit as original events
}}
```

### Pattern Analysis
```python
{"event": "observation:analyze_patterns", "data": {
    "filter": {...},
    "analysis_type": "frequency|sequence|performance|errors"
}}
```

Analysis types:
- **frequency**: Event counts, observer-target pairs, time distribution
- **sequence**: Common event sequences (n-grams)
- **performance**: Duration statistics by event type
- **errors**: Error pattern detection (placeholder)

## Performance Considerations

1. **Minimal overhead**: Observation checks only when subscriptions exist
2. **Async notification**: Observers notified asynchronously
3. **Sampling support**: Reduce observation frequency for high-volume events
4. **Circuit breakers**: Disable observation if observer is overwhelmed
5. **Selective logging**: Only log observed events when configured

## Security Considerations

1. **Permission model**: Observers need explicit permission to observe targets
2. **Capability enforcement**: Use existing capability system
3. **Data filtering**: Sensitive data can be excluded from observations
4. **Audit trail**: All observation subscriptions logged

## Future Extensions

1. **Cross-system observation**: Observe agents in federated KSI instances
2. **ML integration**: Use observations for behavior modeling
3. **Debugging tools**: Enhanced TUI for observation visualization
4. **Policy engine**: Rule-based observation triggers
5. **Observation aggregation**: Combine observations from multiple constructs

## Migration Strategy

1. **Backward compatible**: Existing agents work without changes
2. **Opt-in adoption**: New features only for agents that need them
3. **Gradual rollout**: Start with internal testing agents
4. **Documentation**: Clear examples and patterns

## Success Metrics

1. **Performance impact**: < 1% overhead for non-observed events
2. **Scalability**: Support 100+ active observations
3. **Reliability**: No dropped observation events
4. **Usability**: Clear API and debugging tools