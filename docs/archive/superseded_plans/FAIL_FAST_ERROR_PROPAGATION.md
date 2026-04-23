# Fail-Fast Error Propagation Architecture

## Problem Statement

KSI currently suffers from pervasive silent failure patterns that violate fail-fast principles. When operations fail (template resolution, condition evaluation, transformations), the system often:
- Returns corrupted data (unresolved template strings like `"{{missing}}"`)
- Continues processing with invalid state
- Logs warnings that agents never see
- Breaks accountability chains between agents and their operations

This leads to **silent data corruption** propagating through the system, which is worse than crashing.

## Core Design Flaw

The system was built with optimistic assumptions:
- Templates will resolve
- Conditions will evaluate  
- Data will be present
- Types will match

Production systems need pessimistic handling where every operation that can fail must fail fast and propagate errors to the originating agent.

## Real-World Example

The `{{data.evaluation}}` vs `{{evaluation}}` bug demonstrated this:
```python
# Template: "{{data.evaluation}}" 
# Event data: {"evaluation": {...}, "agent_id": "..."}
# Result: "{{data.evaluation}}" passed as literal string
# Handler received: {"evaluation": "{{data.evaluation}}"} ← CORRUPTED DATA
```

Instead of failing fast with "Cannot resolve data.evaluation", the system passed corrupted data downstream.

## Solution Architecture

### 1. Context Chain Philosophy

Context enables error traceability, but must balance strictness with practicality:

```python
class KSIContext:
    _correlation_id: str      # Traces related events
    _parent_event_id: str     # Direct parent event
    _root_event_id: str       # Original request
    _event_depth: int         # Processing depth
    _client_id: str           # Originating agent/client (e.g., "agent_xyz")
    _timestamp: float         # Event timestamp
    _response_id: str         # Response tracking
```

**Critical**: Agents ONLY know their `agent_id`. They NEVER know `session_id` (private to completion system) or other internal details.

#### Context Requirements

**Agent-Provided (minimal)**:
```python
{
    "_agent_id": "agent_xyz"  # Only thing agents must provide
}
```

**System-Enhanced (helpful)**:
```python
{
    "_client_id": f"agent_{agent_id}",  # Derived from agent_id
    "_event_id": generated,              # System generates
    "_timestamp": current_time,          # System provides
    "_correlation_id": derived_or_new,   # System derives or generates
    "_event_depth": 0,                   # 0 for agent-initiated
    "_root_event_id": event_id           # Same as event_id for roots
}
```

The system helpfully fills in missing context without inventing false relationships.

### 2. Strict Processing - NO Backwards Compatibility

**This is a breaking change by design**. All processing is strict:

```python
def resolve_template(template: str, data: Dict, context: Dict):
    """
    ALWAYS raises TemplateResolutionError on missing variables.
    No strict parameter - strict is the only mode.
    """

def evaluate_condition(condition: str, data: Dict) -> bool:
    """
    Returns False for missing fields (standard boolean logic).
    Does NOT raise errors - missing field means condition not met.
    """
```

### 3. Typed Error Events

Every processing stage emits specific error events on failure:

```python
# Error event types
error:template_resolution   # Template variable not found
error:condition_evaluation  # Condition references missing field
error:transformation       # Transformation failed
error:validation          # Validation check failed
error:handler_execution   # Handler raised exception
error:type_mismatch      # Type coercion failed
```

Error event structure:
```python
{
    "error_type": "template_resolution_failure",
    "error_message": "Cannot resolve variable 'data.evaluation'",
    "operation": "transform",
    "details": {
        "template": "{{data.evaluation}}",
        "missing_variable": "data.evaluation",
        "available_variables": ["evaluation", "agent_id", "result_type"]
    },
    "_ksi_context": {...}  # MANDATORY - preserves accountability
}
```

### 4. Error Propagation Flow

Errors flow through natural system channels to reach agents:

```python
@handler("error:*")
async def propagate_error_to_originator(event: str, data: Dict):
    """Route errors to originating agent using context chain."""
    context = data.get("_ksi_context", {})
    client_id = context.get("_client_id")
    
    if client_id and client_id.startswith("agent_"):
        agent_id = client_id.replace("agent_", "")
        
        # Route to agent:error handler
        await emit("agent:error", {
            "agent_id": agent_id,
            "error_type": event.split(":", 1)[1],
            "error": data,
            "failed_operation": context.get("_root_event_id"),
            "processing_depth": context.get("_event_depth"),
            "_ksi_context": context
        })

@handler("agent:error") 
async def handle_agent_error(data: Dict):
    """Deliver errors to agents via completion:inject."""
    agent_id = data["agent_id"]
    
    # Store in state for introspection by parent agents
    await emit("state:entity:update", {
        "type": "agent",
        "id": agent_id,
        "properties": {
            "last_error": data["error_type"],
            "error_count": increment,
            "errors": append_to_history(data)
        }
    })
    
    # Inject into agent's conversation (natural error delivery)
    await emit("completion:inject", {
        "agent_id": agent_id,
        "message": {
            "role": "system",
            "content": f"ERROR: {data['error_type']}\n"
                      f"{data['error']['error_message']}\n"
                      f"Failed operation: {data.get('failed_operation')}"
        }
    })
```

**Key insights**:
- Errors stored in state enable parent agent introspection
- completion:inject delivers errors naturally in conversation
- Agents NEVER see internal details like session_id

## Implementation Plan

### Phase 1: Template Resolution Strictness (BREAKING CHANGE)

**File: `ksi_common/template_utils.py`**

1. Add `TemplateResolutionError` exception class
2. Remove all `strict` parameters - strict is the ONLY mode
3. Always raise exceptions for missing variables
4. Fix `validate_template()` to actually detect unresolvable variables

### Phase 2: Error Event Infrastructure  

**File: `ksi_daemon/error_propagation.py`** (new)

1. Create error event router handler
2. Implement context-based error routing
3. Add error aggregation for monitoring
4. Create error type registry

### Phase 3: Context Enforcement

**File: `ksi_daemon/event_system.py`**

1. Make `_ksi_context` mandatory in `emit()` method
2. Auto-generate context if not provided (with warning)
3. Validate context structure on emission
4. Add context preservation through transformations

### Phase 4: Agent Error Handling

**File: `ksi_daemon/agent_service.py`**

1. Add `agent:error` handler to agent service
2. Implement error delivery to agent threads
3. Add error tracking in agent state
4. Create error recovery patterns

### Phase 5: Condition Evaluation Strictness

**File: `ksi_common/condition_evaluator.py`**

1. Add `ConditionEvaluationError` exception class
2. Add `strict` parameter to `evaluate_condition()`
3. Implement strict field checking
4. Add detailed error reporting

## Migration Strategy

### Backwards Compatibility

During transition, we support both modes:
- New code uses `strict=True` by default
- Legacy code can explicitly use `strict=False`
- Gradual migration of existing transformers

### Rollout Phases

1. **Phase 1**: Deploy strict template resolution (with `strict=False` for existing code)
2. **Phase 2**: Deploy error routing infrastructure
3. **Phase 3**: Enable strict mode for new transformers
4. **Phase 4**: Gradually migrate existing transformers
5. **Phase 5**: Make strict mode mandatory

## Success Metrics

1. **Zero silent failures**: All processing failures generate error events
2. **100% error traceability**: Every error can be traced to originating agent
3. **Reduced MTTR**: Agents immediately know when operations fail
4. **Data integrity**: No corrupted data (template strings) in production

## Anti-Patterns to Eliminate

### Silent Failure Anti-Pattern
```python
# ANTI-PATTERN
if not result:
    logger.warning("Operation failed")
    return None  # Silent corruption
```

### Fail-Fast Pattern
```python
# CORRECT PATTERN  
if not result:
    error = OperationError("Operation failed: specific reason")
    await emit_error_event(error, context)
    raise error  # Stop processing
```

### Missing Context Anti-Pattern
```python
# ANTI-PATTERN
await emit("some:event", {"data": "value"})  # No context!
```

### Context-Preserving Pattern
```python
# CORRECT PATTERN
await emit("some:event", {
    "data": "value",
    "_ksi_context": context  # Preserves accountability
})
```

## Testing Strategy

### Unit Tests
- Test strict mode for all processing functions
- Verify error event generation
- Validate context propagation

### Integration Tests  
- End-to-end error propagation from transformation to agent
- Context chain preservation through multiple hops
- Error aggregation and monitoring

### Chaos Testing
- Inject missing variables in templates
- Inject missing fields in conditions  
- Verify fail-fast behavior

## Long-Term Vision

This fail-fast architecture enables:
1. **Self-healing systems**: Agents can detect and recover from errors
2. **Observability**: Complete visibility into failure patterns
3. **Debugging**: Clear error traces from origin to failure point
4. **Reliability**: No silent corruptions, only explicit failures

## References

- Original issue: Template mapping `{{data.evaluation}}` silently failed
- Related: `/docs/ASYNC_STATE_AND_PUBSUB_ARCHITECTURE.md`
- Philosophy: `/docs/KSI_PHILOSOPHY_ELEGANT_ARCHITECTURE.md`

---

*Last updated: 2025-01-06*