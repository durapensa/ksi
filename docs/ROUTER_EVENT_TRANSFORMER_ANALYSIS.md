# Router Event Transformer System Analysis

## Overview

The KSI event transformer system is a powerful declarative pattern for routing and transforming events without writing Python handlers. It's implemented in the core event router (`event_system.py`) and managed by the transformer service (`transformer_service.py`).

## Core Implementation

### 1. Event Router Integration

The transformer system is built directly into the EventRouter class in `event_system.py`:

```python
# In EventRouter.__init__
self._transformers: Dict[str, Dict[str, Any]] = {}  # source -> transformer config
self._async_transformers: Dict[str, str] = {}  # transform_id -> source event
self._transform_contexts: Dict[str, Dict[str, Any]] = {}  # transform_id -> context
```

When an event is emitted, the router first checks if a transformer is registered for that event:

```python
# In EventRouter.emit()
if event in self._transformers:
    transformer = self._transformers[event]
    # Apply transformation logic...
```

### 2. Transformer Capabilities

#### Basic Field Mapping
```yaml
transformers:
  - source: "test:hello"
    target: "agent:send_message"
    mapping:
      agent_id: "test_agent_123"
      message:
        type: "greeting"
        content: "{{message}}"  # Template substitution
```

#### Conditional Transformation
```yaml
transformers:
  - source: "test:conditional"
    target: "orchestration:track"
    condition: "priority == 'high'"  # Simple condition evaluation
    mapping:
      type: "high_priority_event"
      data: "{{event_data}}"
```

#### Async Transformation with Response Routing
```yaml
transformers:
  - source: "test:async_task"
    target: "completion:async"
    async: true
    mapping:
      prompt: "Test async completion: {{task_description}}"
      request_id: "{{transform_id}}"  # Auto-generated UUID
    response_route:
      from: "completion:result"
      to: "test:async_complete"
      filter: "request_id == {{transform_id}}"
```

### 3. Template Substitution

The `_apply_mapping` method supports:
- Simple field access: `{{field_name}}`
- Nested field access: `{{user.name}}`
- Array indexing: `{{metadata.tags.0}}`
- Static values: `"constant"`

### 4. Transformer Service

The transformer service (`transformer_service.py`) provides high-level management:
- Load transformers from YAML pattern files
- Reference counting for shared patterns
- Hot-reload support
- Usage tracking by system

## Current Usage Patterns

### 1. Agent Communication
```yaml
# From agent_messaging_pattern.yaml
transformers:
  - source: "message:send_direct"
    target: "agent:send_message"
    mapping:
      agent_id: "{{data.to}}"
      message:
        role: "assistant"
        content: "{{data.content}}"
        metadata:
          from: "{{data.from}}"
```

### 2. Game Theory Orchestrations
```yaml
# From game_theory_orchestration_v2.yaml
transformers:
  - source: "state:entity:update"
    target: "agent:spawn_from_component"
    condition: "type == 'game_environment' AND phase == 'agent_spawning'"
    mapping:
      component: "base/agent_core"
      agent_id: "strategy_{{index}}_{{agent_id}}"
```

### 3. Pattern Discovery
```yaml
# From strategy_discovery_pattern.yaml
transformers:
  - source: "discovery:generate_hypothesis"
    target: "completion:async"
    async: true
    mapping:
      prompt: |
        Generate a strategy for the Iterated Prisoner's Dilemma:
        Context: {{generation_context}}
        Role: {{generator_type}}
```

## Opportunities for Handler Replacement

### 1. Simple Routing Handlers

Many handlers that just route data between events could be replaced:

**Current Handler Pattern:**
```python
@event_handler("domain:event")
async def handle_domain_event(data, context):
    # Just transform and forward
    result = await emit_event("system:event", {
        "field1": data.get("source_field"),
        "field2": transform_value(data.get("other_field"))
    })
    return result
```

**Transformer Replacement:**
```yaml
transformers:
  - source: "domain:event"
    target: "system:event"
    mapping:
      field1: "{{source_field}}"
      field2: "{{other_field}}"  # Add transform functions support
```

### 2. Conditional Routing

**Current Handler Pattern:**
```python
@event_handler("workflow:step")
async def handle_workflow_step(data, context):
    if data.get("status") == "complete":
        await emit_event("workflow:next_step", data)
    else:
        await emit_event("workflow:retry", data)
```

**Transformer Replacement:**
```yaml
transformers:
  - source: "workflow:step"
    target: "workflow:next_step"
    condition: "status == 'complete'"
    mapping: "{{$}}"  # Pass through all data
    
  - source: "workflow:step"
    target: "workflow:retry"
    condition: "status != 'complete'"
    mapping: "{{$}}"
```

### 3. Event Aggregation/Batching

Patterns like async batch processing could use transformers:

```yaml
transformers:
  - source: "item:process"
    target: "batch:add"
    mapping:
      batch_id: "{{batch_id}}"
      item: "{{$}}"
    
  - source: "batch:ready"
    target: "orchestration:process_batch"
    async: true
    mapping:
      items: "{{items}}"
      transform_id: "{{transform_id}}"
```

## Enhancement Opportunities

### 1. Expression Language
The current condition evaluation is basic. Could enhance with:
- Boolean operators: `condition: "(priority == 'high' OR urgent == true) AND status != 'complete'"`
- Functions: `condition: "len(items) > 10"`
- Regex matching: `condition: "event_name ~= '^test:.*'"`

### 2. Transform Functions
Add built-in transform functions:
```yaml
mapping:
  timestamp: "{{$now()}}"
  uuid: "{{$uuid()}}"
  formatted_name: "{{$upper(name)}}"
  items_count: "{{$len(items)}}"
```

### 3. Multi-Target Transformers
Allow one source to trigger multiple targets:
```yaml
transformers:
  - source: "user:signup"
    targets:
      - event: "email:send_welcome"
        mapping:
          to: "{{email}}"
      - event: "analytics:track"
        mapping:
          event: "signup"
          user_id: "{{user_id}}"
```

### 4. State-Aware Transformers
Allow transformers to access state:
```yaml
transformers:
  - source: "counter:increment"
    target: "state:entity:update"
    mapping:
      id: "counter_{{name}}"
      properties:
        value: "{{$state('counter_' + name).value + 1}}"
```

## Best Practices

### 1. When to Use Transformers
- Simple event routing/renaming
- Field mapping/transformation
- Conditional event flow
- Async request/response patterns
- Domain event → System event translation

### 2. When to Keep Handlers
- Complex business logic
- Multiple async operations
- Error handling/recovery
- Stateful processing
- Side effects (file I/O, external APIs)

### 3. Pattern Organization
- Group related transformers in pattern files
- Use clear naming conventions
- Document transformer purpose
- Test with `test_transformer_flow.yaml` pattern

## Completion Queue Analysis

The `completion:async` flow demonstrates proper queue processing:

1. **Request Received**: `completion:async` event with agent_id and prompt
2. **Queue Entry**: Request gets unique request_id and enters session queue
3. **Progress Update**: `completion:progress` with status "calling_provider"
4. **Result**: Either `completion:result` (success) or `completion:error` (failure)

The queue ensures:
- Sequential processing per session
- Automatic session continuity for agents
- Proper error propagation
- Request tracking and recovery

## Conclusion

The router event transformer system is a powerful feature that can significantly reduce code complexity by replacing simple routing handlers with declarative configurations. The system is already well-integrated and proven in production with orchestration patterns. Key opportunities include enhancing the expression language and adding transform functions to handle more complex scenarios declaratively.