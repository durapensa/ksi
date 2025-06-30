# Dynamic Self-Organizing Agent System

## Overview

KSI now supports dynamic, self-organizing agent systems that can adapt their compositions at runtime, spawn peers, and negotiate roles based on task requirements.

## Key Features

### 1. Dynamic Composition Selection
Agents can be spawned with intelligent composition selection based on context:

```bash
# Fixed mode (default) - uses predetermined composition
python3 interfaces/orchestrate.py "AI ethics" --mode debate --spawn-mode fixed

# Dynamic mode - selects best composition based on context
python3 interfaces/orchestrate.py "AI ethics" --mode debate --spawn-mode dynamic

# Emergent mode - allows full self-organization
python3 interfaces/orchestrate.py "AI ethics" --mode debate --spawn-mode emergent
```

### 2. Self-Modification
Agents can update their own compositions during runtime:

```python
# Agent requests composition change
await event_client.request("agent:update_composition", {
    "agent_id": self.agent_id,
    "new_composition": "specialist_researcher",
    "reason": "Task requires deep technical research"
})
```

### 3. Peer Discovery
Agents can discover other agents by capabilities:

```python
# Find agents with specific capabilities
peers = await event_client.request("agent:discover_peers", {
    "agent_id": self.agent_id,
    "capabilities": ["data_analysis", "visualization"],
    "roles": ["analyst"]
})
```

### 4. Role Negotiation
Agents can coordinate to negotiate optimal role assignments:

```python
# Initiate role negotiation
result = await event_client.request("agent:negotiate_roles", {
    "participants": ["agent_1", "agent_2", "agent_3"],
    "type": "collaborative",
    "context": {"task": "Complex analysis project"}
})
```

## Composition Metadata

Enhanced compositions support new metadata fields:

```yaml
name: adaptive_researcher
type: profile
version: 1.0.0
metadata:
  # What this composition provides
  capabilities_provided:
    - information_gathering
    - source_validation
    - dynamic_adaptation
  
  # What system capabilities it needs
  capabilities_required:
    - web_search
    - event_client
  
  # Other compositions it works well with
  compatible_with:
    - analyst
    - writer
    - validator
  
  # Can spawn other agents
  spawns_agents: true
  
  # Can modify itself
  self_modifiable: true
  
  # Spawning permissions
  spawn_permissions:
    max_children: 3
    allowed_types:
      - validator
      - analyst
  
  # Modification limits
  modification_permissions:
    allow_capability_changes: true
    allow_role_changes: true
    rate_limit: 5  # per hour
```

## Runtime Composition Creation

Agents can create new compositions on the fly:

```python
# Create custom composition
await event_client.request("composition:create", {
    "name": "custom_analyst",
    "type": "profile",
    "role": "data_analyst",
    "capabilities": ["data_analysis", "visualization"],
    "prompt": "You are a specialized data analyst...",
    "metadata": {
        "self_modifiable": True,
        "dynamic": True
    }
})
```

## Selection Algorithm

The composition selection service scores compositions based on:

1. **Role compatibility** (30%)
2. **Capability matching** (40%) 
3. **Task relevance** (20%)
4. **Metadata alignment** (10%)

## Use Cases

### Research Team Self-Organization
```python
# Spawn initial researcher with dynamic mode
spawn_result = await client.request("agent:spawn", {
    "spawn_mode": "dynamic",
    "selection_context": {
        "task": "Research quantum computing applications",
        "required_capabilities": ["research", "technical_writing"]
    }
})

# Agent can spawn specialized peers as needed
# Agent can modify composition based on findings
# Team self-organizes around emerging sub-topics
```

### Adaptive Problem Solving
```python
# Start with general problem solver
# Agent discovers it needs data analysis
# Updates composition to analyst
# Spawns visualization specialist
# Team collaborates on solution
```

### Dynamic Orchestration
```bash
# Let agents figure out optimal configuration
python3 interfaces/orchestrate.py "Solve climate change" \
    --agents 5 --spawn-mode emergent
```

## Best Practices

1. **Start Simple**: Use fixed mode for predictable scenarios
2. **Add Constraints**: Use metadata to limit self-modification
3. **Monitor Adaptation**: Track composition changes for patterns
4. **Capture Success**: Save effective configurations for reuse
5. **Test Incrementally**: Enable features progressively

## Future Enhancements

- **Pattern Recognition**: Detect successful agent configurations
- **Pattern Persistence**: Save and reuse effective patterns
- **Spawn Chains**: Multi-generation agent hierarchies
- **Consensus Mechanisms**: Group decision making for roles
- **Resource Management**: Prevent runaway agent creation

## Testing

Run the test suite to see features in action:

```bash
python3 tests/test_dynamic_composition.py
```

This demonstrates:
- Dynamic composition selection
- Agent self-modification
- Peer discovery
- Runtime composition creation