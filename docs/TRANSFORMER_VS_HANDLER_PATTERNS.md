# Transformer vs Handler Patterns

This document explains when to use YAML-based transformers versus Python event handlers in KSI.

## Related Issues

### Variable Substitution in Components
**Issue**: Variables like `{{agent_id}}` were not being substituted in behavior components.
**Root Cause**: Component renderer was using `context.variables` (component-defined vars) instead of runtime variables passed during rendering.
**Fix**: Merge runtime variables with component variables, giving runtime variables precedence.
**Lesson**: Always use the shared `template_utils.substitute_template()` function and ensure runtime variables are passed through the entire rendering chain.

## Key Architectural Insight

**Transformers and handlers serve different purposes and have different execution characteristics.**

## Execution Order

When an event is emitted in KSI:

1. **Transformers are processed first** - They are spawned as tasks (async or sync)
2. **Handlers run immediately after** - They execute synchronously in priority order
3. **All transformer tasks ARE awaited** - Via `asyncio.gather()` before event emission returns

```
Event Emitted → Transformers Spawned → Handlers Execute → Await All Transformers → Return
                     ↓                      ↓                      ↓
                (as tasks)            (synchronously)       (asyncio.gather)
```

## Why Transformers Spawn as Tasks (Not Inline)

**Critical Insight**: Transformers MUST spawn as tasks to prevent deadlocks and enable parallelism.

### The Architecture is Deliberate
```python
# From event_system.py line 369:
# Spawn transformation as task to allow multiple transformers and handlers to run
```

### Benefits of Task Spawning
1. **Prevents Recursive Deadlocks**: Each emit() gets its own execution context
2. **Enables Parallelism**: Multiple transformers for same event run concurrently
3. **Avoids Stack Overflow**: Deep transformer chains don't grow the call stack
4. **Non-blocking Handlers**: Handlers can execute while transformers run

### If Transformers Were Inline/Blocking
- **Sequential Bottleneck**: Each transformer would block the next
- **Deadlock Risk**: emit() within emit() could cause infinite recursion
- **No Parallelism**: Transformers would execute one by one
- **Handler Delays**: All handlers wait for all transformers sequentially

### The Await Pattern
```python
# Transformers ARE awaited, just not individually:
await asyncio.gather(*transformer_tasks, return_exceptions=True)
```
- **Best of Both Worlds**: Parallelism during execution, completion guarantee before return
- **Error Isolation**: `return_exceptions=True` prevents one failure from canceling others

## When to Use Transformers (YAML)

Transformers are best for:
- **Declarative routing patterns** - Simple event A → event B transformations
- **Fire-and-forget operations** - Monitoring, logging, notifications
- **Cleanup cascades** - Termination sequences, resource cleanup
- **Parallel operations** - Tasks that can run alongside main processing
- **Hot-reloadable configuration** - Changes without daemon restart

### Example: Good Transformer Use Case
```yaml
# Monitoring cascade - can run in parallel
- name: "agent_status_to_monitor"
  source: "agent:status"
  target: "monitor:agent_status"
  async: true  # Fine to run in background
  mapping:
    agent_id: "{{agent_id}}"
    status: "{{status}}"
```

## When to Use Handlers (Python)

Handlers are required for:
- **Critical path operations** - Must complete before other handlers run
- **Operations with dependencies** - Other handlers rely on the result
- **Complex logic** - Needs access to service state or multiple operations
- **Synchronous requirements** - Must complete before event processing continues

### Example: Handler Required
```python
@event_handler("agent:spawned", schema=AgentSpawnedData)
async def handle_agent_spawned(data: AgentSpawnedData, context: Optional[Dict[str, Any]] = None):
    """Create state entity when agent is spawned.
    
    This MUST be a handler because:
    1. Completion system needs the state entity immediately
    2. Other handlers depend on the entity existing
    3. Must complete synchronously before event processing continues
    """
    # Create state entity that other handlers will need
    await event_emitter("state:entity:create", {
        "type": "agent",
        "id": data["agent_id"],
        "properties": {
            "sandbox_uuid": data["sandbox_uuid"],  # Critical for completion system
            # ... other properties
        }
    })
```

## The `async: true` Trap

Adding `async: true` to a transformer makes it run in parallel with handler execution:

```yaml
# DON'T DO THIS for critical operations
- name: "agent_spawned_state_create"
  source: "agent:spawned"
  target: "state:entity:create"
  async: true  # ❌ Runs too late! Handlers need this entity NOW
```

## Decision Tree

```
Is this operation critical for other handlers?
├─ YES → Use a Handler
└─ NO → Can it be expressed declaratively?
         ├─ YES → Use a Transformer
         └─ NO → Use a Handler
```

## Real-World Example: Agent State Entity Creation

**Why the transformer approach failed:**
1. Transformer was marked `async: true`
2. Completion handler runs immediately after agent:spawned
3. Needs state entity to find sandbox_uuid
4. Async transformer hasn't created entity yet
5. Completion fails with "missing sandbox_uuid"

**Why the handler approach works:**
1. Handler runs synchronously during event processing
2. Creates state entity before any other handler runs
3. Completion handler finds entity successfully
4. Agent operations proceed normally

## Best Practices

1. **Start with transformers** for simple routing and monitoring
2. **Use handlers** when timing matters or logic is complex
3. **Never use async transformers** for critical path operations
4. **Document why** you chose handler over transformer
5. **Test timing** if operations depend on each other

## Summary

- **Transformers**: Declarative, parallel, fire-and-forget
- **Handlers**: Imperative, synchronous, critical path
- **The "workaround" of using handlers is often the correct architectural choice**

When in doubt, ask: "Do other operations depend on this completing first?" If yes, use a handler.