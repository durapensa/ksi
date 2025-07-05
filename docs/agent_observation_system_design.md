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

### 6. Use Cases

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

## Implementation Phases

### Phase 1: Agent Metadata (Immediate)
- Add `AgentMetadata` class
- Update agent spawn to include `originator_agent_id`
- Modify agent service to track relationships
- Update agent info endpoints

### Phase 2: State-Based Tracking (High Priority)
- Implement construct tracking in state
- Add helper methods for construct management
- Create construct lifecycle events
- Add construct discovery endpoints

### Phase 3: Observation Subscription (Medium Priority)
- Create `ObservationManager` component
- Implement subscription/unsubscription
- Add subscription persistence
- Create subscription query endpoints

### Phase 4: Event Routing Integration (Medium Priority)
- Integrate observation into event router
- Implement `observe:begin` and `observe:end` events
- Add performance monitoring
- Create observation filtering

### Phase 5: Historical Analysis (Low Priority)
- Add observation event logging
- Implement replay capabilities
- Create analysis tools
- Add observation metrics

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