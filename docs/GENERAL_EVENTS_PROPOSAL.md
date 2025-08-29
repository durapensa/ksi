# General Events Proposal for KSI

## Overview

Rather than creating benchmark-specific events (like `melting_pot:*`), this document proposes general-purpose events that would benefit any spatial, resource-based, or game-theoretic scenario in KSI. These events emerged from analyzing Melting Pot's needs but are designed to be universally useful.

## Proposed General Events

### 1. Spatial Events

These enable any spatial simulation, from game environments to robotic navigation to geographic modeling.

#### `spatial:query`
Query entities in spatial relationships.

```python
{
    "event": "spatial:query",
    "data": {
        "query_type": "radius",  # radius|rectangle|line_of_sight|nearest_k
        "reference_point": {"x": 10, "y": 20},
        "parameters": {
            "radius": 5,
            "entity_types": ["agent", "resource"],  # Optional filter
            "max_results": 10  # Optional limit
        }
    }
}

# Returns list of entities matching spatial query
```

**Use Cases**:
- Agent vision/perception
- Collision detection
- Resource discovery
- Social proximity

#### `spatial:move`
Request movement with validation.

```python
{
    "event": "spatial:move",
    "data": {
        "entity_id": "agent_123",
        "to": {"x": 15, "y": 25},
        "movement_type": "walk",  # walk|teleport|fly
        "validate_path": true  # Check obstacles/validity
    }
}

# Returns success/failure with actual position
```

**Use Cases**:
- Game character movement
- Robot navigation
- Particle simulation
- Traffic modeling

#### `spatial:interact`
Generic spatial interaction between entities.

```python
{
    "event": "spatial:interact",
    "data": {
        "actor_id": "agent_123",
        "target_id": "resource_456",
        "interaction_type": "collect",  # collect|exchange|attack|heal|communicate
        "range": 1.0,  # Interaction range
        "parameters": {
            "amount": 10
        }
    }
}
```

**Use Cases**:
- Resource collection
- Combat systems
- Trading/exchange
- Communication

### 2. Resource Management Events

Universal resource handling for any economy, game, or allocation system.

#### `resource:create`
Spawn new resources in the environment.

```python
{
    "event": "resource:create",
    "data": {
        "resource_type": "energy",
        "amount": 100,
        "location": {"x": 10, "y": 20},  # Optional spatial
        "owner": "environment",  # Or specific entity
        "properties": {
            "decay_rate": 0.01,
            "max_stack": 1000
        }
    }
}
```

**Use Cases**:
- Game pickups
- Economic goods
- Energy systems
- Computational resources

#### `resource:transfer`
Transfer resources between entities.

```python
{
    "event": "resource:transfer",
    "data": {
        "from_entity": "agent_123",
        "to_entity": "agent_456",
        "resource_type": "credits",
        "amount": 50,
        "transfer_type": "trade",  # trade|gift|steal|tax
        "validate_consent": true  # Check if transfer is allowed
    }
}
```

**Use Cases**:
- Trading systems
- Resource sharing
- Theft/exploitation
- Taxation/fees

#### `resource:transform`
Convert resources from one type to another.

```python
{
    "event": "resource:transform",
    "data": {
        "entity_id": "crafter_123",
        "inputs": [
            {"type": "wood", "amount": 10},
            {"type": "metal", "amount": 5}
        ],
        "outputs": [
            {"type": "tool", "amount": 1}
        ],
        "recipe": "basic_tool"  # Optional recipe reference
    }
}
```

**Use Cases**:
- Crafting systems
- Manufacturing
- Energy conversion
- Chemical reactions

### 3. Observation Events

General perception system for any agent needing environment information.

#### `observation:request`
Request an observation of the environment.

```python
{
    "event": "observation:request",
    "data": {
        "observer_id": "agent_123",
        "observation_type": "visual",  # visual|state|audio|semantic
        "parameters": {
            "view_radius": 5,
            "include_hidden": false,
            "resolution": "high"  # low|medium|high
        }
    }
}
```

**Use Cases**:
- Agent perception
- Sensor readings
- Environment scanning
- Information gathering

#### `observation:deliver`
Deliver observation to requesting entity.

```python
{
    "event": "observation:deliver",
    "data": {
        "observer_id": "agent_123",
        "observation_type": "visual",
        "data": {
            "visible_entities": [...],
            "terrain": [...],
            "rgb_data": "base64_encoded"  # Optional visual data
        },
        "timestamp": 1234567890.123,
        "partial": false  # True if observation is incomplete
    }
}
```

**Use Cases**:
- Providing sensor data
- Delivering game state
- Sharing perceptions
- Updating world models

### 4. Episode Management Events

For any episodic task, game, or bounded interaction.

#### `episode:create`
Initialize a new episode/game/scenario.

```python
{
    "event": "episode:create",
    "data": {
        "episode_id": "game_001",
        "episode_type": "prisoners_dilemma",
        "configuration": {
            "max_steps": 1000,
            "participants": ["agent_1", "agent_2"],
            "victory_conditions": {...},
            "environment_params": {...}
        }
    }
}
```

**Use Cases**:
- Game matches
- Training episodes
- Evaluation runs
- Bounded experiments

#### `episode:step`
Advance episode by one timestep.

```python
{
    "event": "episode:step",
    "data": {
        "episode_id": "game_001",
        "step_number": 42,
        "actions": {
            "agent_1": {"type": "move", "direction": "north"},
            "agent_2": {"type": "collect", "target": "resource_5"}
        }
    }
}
```

**Use Cases**:
- Turn-based games
- Simulation steps
- Training iterations
- Synchronized updates

#### `episode:terminate`
End an episode with results.

```python
{
    "event": "episode:terminate",
    "data": {
        "episode_id": "game_001",
        "reason": "max_steps_reached",  # victory|defeat|timeout|abort
        "final_state": {...},
        "results": {
            "winner": "agent_1",
            "scores": {"agent_1": 100, "agent_2": 75},
            "metrics": {...}
        }
    }
}
```

**Use Cases**:
- Game completion
- Episode termination
- Result recording
- Cleanup triggers

### 5. Metric Calculation Events

General metrics for any evaluation or monitoring need.

#### `metrics:calculate`
Request calculation of specific metrics.

```python
{
    "event": "metrics:calculate",
    "data": {
        "metric_types": ["gini", "variance", "efficiency"],
        "data_source": {
            "entity_type": "agent",
            "property": "wealth",
            "episode_id": "game_001"  # Optional scope
        },
        "grouping": {
            "by": "population_type",  # Optional grouping
            "groups": ["focal", "background"]
        }
    }
}
```

**Use Cases**:
- Fairness metrics
- Performance evaluation
- Statistical analysis
- Research measurements

#### `metrics:report`
Report calculated metrics.

```python
{
    "event": "metrics:report",
    "data": {
        "source": "game_episode_001",
        "timestamp": 1234567890.123,
        "metrics": {
            "gini_coefficient": 0.35,
            "collective_return": 250.5,
            "cooperation_rate": 0.75,
            "custom_metric": 42
        },
        "metadata": {
            "num_agents": 10,
            "episode_length": 1000
        }
    }
}
```

**Use Cases**:
- Performance reporting
- Research data collection
- Monitoring dashboards
- Optimization feedback

## Integration with Existing KSI Events

These new events complement existing KSI events:

### Spatial events work with state system:
```python
# Spatial query finds entities
spatial:query -> returns entity IDs

# Then use state system for details
state:entity:get -> returns full entity data

# Update position via state
state:entity:update -> modifies spatial properties
```

### Resource events trigger state updates:
```python
# Resource transfer modifies state
resource:transfer -> triggers -> state:entity:update

# Resource creation creates entities
resource:create -> triggers -> state:entity:create
```

### Observations can trigger completions:
```python
# Agent requests observation
observation:request -> 

# System delivers observation
observation:deliver ->

# Agent processes via completion
completion:async (with observation in prompt)
```

## Benefits of General Events

### 1. Reusability
- Any spatial simulation can use spatial events
- Any economy can use resource events
- Any episodic task can use episode events

### 2. Composability
- Events can be combined for complex behaviors
- Standard patterns emerge across different domains
- Components become more portable

### 3. Monitoring
- Standard metrics across all applications
- Consistent observation patterns
- Unified episode management

### 4. Future-Proofing
- New benchmarks can use existing events
- No proliferation of specialized events
- Clean, maintainable event taxonomy

## Implementation Priority

### Phase 1: Core Events (Week 1)
- [ ] `spatial:query` - Most fundamental spatial operation
- [ ] `resource:transfer` - Core economic primitive
- [ ] `episode:create/step/terminate` - Basic episode flow
- [ ] `observation:request/deliver` - Agent perception

### Phase 2: Extended Events (Week 2)
- [ ] `spatial:move` - Movement with validation
- [ ] `spatial:interact` - Generic interactions
- [ ] `resource:create` - Resource spawning
- [ ] `metrics:calculate/report` - Metric system

### Phase 3: Advanced Events (Week 3)
- [ ] `resource:transform` - Crafting/conversion
- [ ] Additional spatial queries (line of sight, etc.)
- [ ] Advanced metric types
- [ ] Performance optimizations

## Discussion Points

### 1. Event Naming
- Should we use `spatial:*` or `space:*`?
- Should `episode` be `game` or `scenario`?
- Should `observation` be `perception` or `sense`?

### 2. Parameter Standardization
- How to handle different coordinate systems (2D/3D)?
- Standard units for distance, time, amounts?
- How to represent partial/uncertain information?

### 3. Performance Considerations
- Should spatial queries be async or sync?
- How to batch multiple resource transfers?
- When to use events vs direct state access?

### 4. Validation Patterns
- Where should validation happen (sender/receiver)?
- How to handle invalid requests?
- What requires consent/authorization?

## Conclusion

These general events provide the foundation for implementing any spatial, resource-based, or game-theoretic scenario in KSI without creating specialized events for each benchmark. They emerged from Melting Pot's requirements but are designed to be universally useful.

By implementing these events, we can:
1. Run Melting Pot scenarios using standard KSI events
2. Support future benchmarks without new events
3. Enable new types of KSI applications
4. Maintain a clean, logical event taxonomy

The key insight is that most multi-agent scenarios share common patterns: spatial relationships, resource management, episodic structure, and metric evaluation. By providing general events for these patterns, we make KSI more powerful while keeping it elegant.

---

*Document Version: 1.0*
*Created: 2025-08-28*
*Status: For Discussion*
*Next Step: Review and refine event definitions*