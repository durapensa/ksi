# Transformer Replacement Opportunities in KSI

## Overview

This document identifies specific event handlers in the KSI codebase that could be replaced with declarative transformers, reducing code complexity and improving maintainability.

## High-Priority Replacement Candidates

### 1. Simple Event Forwarding in Hierarchical Routing

**Current Handler Pattern** (hierarchical_routing.py):
```python
async def _route_to_agent(self, agent_id: str, source_agent_id: str, 
                         event_name: str, event_data: Dict[str, Any]) -> None:
    """Route event to a specific agent."""
    await self._event_emitter("agent:event_notification", {
        "agent_id": agent_id,
        "source_agent_id": source_agent_id,
        "event_name": event_name,
        "event_data": event_data
    })
```

**Transformer Replacement**:
```yaml
transformers:
  - source: "hierarchical:route_to_agent"
    target: "agent:event_notification"
    mapping:
      agent_id: "{{target_agent_id}}"
      source_agent_id: "{{source_agent_id}}"
      event_name: "{{event_name}}"
      event_data: "{{event_data}}"
```

### 2. Agent Status Propagation

**Current Pattern** (commonly seen in agent communication):
```python
@event_handler("agent:status_changed")
async def propagate_status(data, context):
    # Just forward to orchestration
    result = await emit_event("orchestration:agent_status", {
        "agent_id": data.get("agent_id"),
        "status": data.get("status"),
        "timestamp": data.get("timestamp")
    })
    return result
```

**Transformer Replacement**:
```yaml
transformers:
  - source: "agent:status_changed"
    target: "orchestration:agent_status"
    mapping:
      agent_id: "{{agent_id}}"
      status: "{{status}}"
      timestamp: "{{timestamp}}"
```

### 3. Error Event Routing

**Current Pattern** (error propagation):
```python
@event_handler("agent:error")
async def route_agent_error(data, context):
    if data.get("severity") == "critical":
        await emit_event("orchestration:critical_error", data)
    else:
        await emit_event("orchestration:error", data)
```

**Transformer Replacement**:
```yaml
transformers:
  - source: "agent:error"
    target: "orchestration:critical_error"
    condition: "severity == 'critical'"
    mapping: "{{$}}"  # Pass through all data
    
  - source: "agent:error"
    target: "orchestration:error"
    condition: "severity != 'critical'"
    mapping: "{{$}}"
```

### 4. State Change Notifications

**Current Pattern** (state service):
```python
# When state changes, notify interested parties
await emit_event("state:changed", {
    "entity_id": entity_id,
    "entity_type": entity_type,
    "old_value": old_state,
    "new_value": new_state,
    "changed_by": context.get("_agent_id")
})
```

**Transformer Enhancement**:
```yaml
transformers:
  - source: "state:entity:update"
    target: "state:changed"
    mapping:
      entity_id: "{{id}}"
      entity_type: "{{type}}"
      old_value: "{{$previous}}"  # Enhanced: access previous state
      new_value: "{{properties}}"
      changed_by: "{{_ksi_context._agent_id}}"
```

### 5. Completion Request Routing

**Current Pattern** (simplified version):
```python
# Route completion requests to appropriate provider
if model.startswith("claude"):
    await emit_event("provider:claude:complete", request_data)
elif model.startswith("gpt"):
    await emit_event("provider:openai:complete", request_data)
```

**Transformer Replacement**:
```yaml
transformers:
  - source: "completion:route"
    target: "provider:claude:complete"
    condition: "model ~= '^claude'"  # Enhanced: regex support
    mapping: "{{$}}"
    
  - source: "completion:route"
    target: "provider:openai:complete"
    condition: "model ~= '^gpt'"
    mapping: "{{$}}"
```

## Specific Files with High Replacement Potential

### 1. `ksi_daemon/core/hierarchical_routing.py`
- Multiple routing methods that just forward events
- Could be replaced with a set of conditional transformers
- Would reduce ~200 lines of code to ~50 lines of YAML

### 2. `ksi_daemon/observation/observation_manager.py`
- Observer notification routing
- Event filtering and forwarding
- Rate limiting could be added as transformer feature

### 3. `ksi_daemon/orchestration/orchestration_service.py`
- Event distribution to agents
- Status aggregation
- Pattern-based routing

## Implementation Strategy

### Phase 1: Simple Replacements
1. Identify handlers that only map and forward data
2. Create transformer definitions in pattern files
3. Test transformer behavior matches handler behavior
4. Remove handler code

### Phase 2: Enhanced Features
1. Add regex support to conditions: `condition: "event_name ~= '^test:.*'"`
2. Add function support: `mapping: { timestamp: "{{$now()}}" }`
3. Add state access: `mapping: { count: "{{$state('counter').value + 1}}" }`

### Phase 3: Advanced Patterns
1. Multi-target transformers (one source, multiple targets)
2. Aggregation transformers (collect events, emit batch)
3. Stateful transformers (maintain transformation state)

## Benefits of Replacement

### 1. Code Reduction
- ~30-50% reduction in routing/forwarding code
- Easier to understand event flow
- Less boilerplate

### 2. Declarative Configuration
- Event flow visible in YAML
- Hot-reload capability
- No compilation needed

### 3. Performance
- Transformers run in core router (no handler overhead)
- Parallel execution for multi-target patterns
- Built-in async support

### 4. Maintainability
- Centralized routing logic
- Version control friendly (YAML diffs)
- Pattern reuse across orchestrations

## Recommended Next Steps

1. **Pilot Project**: Replace hierarchical routing forwarding methods
2. **Measure Impact**: Compare code size, performance, maintainability
3. **Enhance Language**: Add missing features based on pilot feedback
4. **Gradual Migration**: Replace handlers module by module

## Caution Areas

### Keep as Handlers
- Complex business logic
- Multi-step async operations
- External API calls
- Stateful processing
- Error recovery logic

### Consider Hybrid Approach
- Use transformers for routing
- Keep handlers for processing
- Chain transformers and handlers

## Example Migration

### Before (Python Handler):
```python
@event_handler("workflow:step_complete")
async def handle_step_complete(data, context):
    step_id = data.get("step_id")
    status = data.get("status")
    
    # Update state
    await emit_event("state:entity:update", {
        "id": f"step_{step_id}",
        "type": "workflow_step",
        "properties": {
            "status": status,
            "completed_at": timestamp_utc()
        }
    })
    
    # Notify orchestration
    await emit_event("orchestration:step_update", {
        "step_id": step_id,
        "status": status
    })
    
    # Check if workflow complete
    if status == "success":
        await emit_event("workflow:check_completion", {
            "workflow_id": data.get("workflow_id")
        })
```

### After (Transformer):
```yaml
transformers:
  # Update state
  - source: "workflow:step_complete"
    target: "state:entity:update"
    mapping:
      id: "step_{{step_id}}"
      type: "workflow_step"
      properties:
        status: "{{status}}"
        completed_at: "{{$now()}}"
  
  # Notify orchestration
  - source: "workflow:step_complete"
    target: "orchestration:step_update"
    mapping:
      step_id: "{{step_id}}"
      status: "{{status}}"
  
  # Check completion on success
  - source: "workflow:step_complete"
    target: "workflow:check_completion"
    condition: "status == 'success'"
    mapping:
      workflow_id: "{{workflow_id}}"
```

## Conclusion

The transformer system offers significant opportunities to reduce code complexity in KSI, particularly for event routing and data transformation handlers. By identifying and replacing appropriate handlers with declarative transformers, the system can become more maintainable, performant, and easier to understand.