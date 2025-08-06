# Universal Response Architecture

## Core Principle

**Every operation in KSI MUST return a response** - either immediately for synchronous operations or via guaranteed delivery for asynchronous operations. No operation can fail silently. No agent should ever poll for results.

## The Dual Response Pattern

### 1. Synchronous Operations (Immediate Response)
```python
# Agent calls
result = await emit("state:get", {"key": "value"})
# Gets IMMEDIATE response (success or error)
```

- **Handler returns directly** → Response flows back through event system → Agent receives result
- **Handler throws exception** → Wrapped in error_response() → Agent receives error
- **No polling, no waiting, no uncertainty**

### 2. Asynchronous Operations (Acknowledgment + Delivery)
```python
# Agent calls
ack = await emit("completion:async", {"prompt": "..."})
# Gets IMMEDIATE acknowledgment with request_id

# Later, agent receives via completion:inject
{"role": "system", "content": "Result: ..."} # or
{"role": "system", "content": "Error: ..."}
```

- **Handler returns acknowledgment** → Agent knows request was received
- **Processing happens async** → Result/error delivered via completion:inject
- **Guaranteed delivery** → Every async operation MUST complete or error

## The Universal Operation Decorator

```python
# ksi_common/universal_operation.py

def ksi_operation(operation_type="handler", async_pattern=None):
    """
    Universal decorator ensuring ALL operations follow response architecture.
    
    This decorator:
    - Wraps all returns in event_response_builder
    - Catches all exceptions and emits system:error events
    - Preserves _ksi_context (as reference string) through all operations
    - Handles async patterns with proper acknowledgment
    
    Args:
        operation_type: Type of operation (handler|transformer|service)
        async_pattern: If set, indicates async operation pattern (e.g., "completion")
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(data, context=None, **kwargs):
            try:
                # Run the actual operation
                result = await func(data, context, **kwargs)
                
                # For async patterns, ensure acknowledgment format
                if async_pattern == "completion":
                    if not isinstance(result, dict) or "request_id" not in result:
                        result = async_response(
                            request_id=data.get("request_id", generate_request_id()),
                            status="processing",
                            context=context
                        )
                
                # Ensure response uses standard builder
                elif not isinstance(result, dict) or "_ksi_context" not in result:
                    result = event_response_builder(result, context)
                
                return result
                
            except Exception as e:
                # PYTHONIC CONTEXT REFACTOR: _ksi_context is now a reference string
                ksi_context_ref = None
                if isinstance(data, dict):
                    ksi_context_ref = data.get("_ksi_context")
                if not ksi_context_ref and context:
                    ksi_context_ref = context.get("_ksi_context")
                if not ksi_context_ref:
                    ksi_context_ref = ""
                
                # Build comprehensive error event
                error_event = {
                    "error_type": f"{operation_type}_failure",
                    "error_class": type(e).__name__,
                    "error_message": str(e),
                    "source": {
                        "operation": func.__name__,
                        "module": func.__module__,
                        "operation_type": operation_type
                    },
                    "original_data": data if isinstance(data, dict) else {"data": str(data)},
                    "_ksi_context": ksi_context_ref  # Pass the reference string as-is
                }
                
                # Emit to universal error handler for propagation
                await emit("system:error", error_event)
                
                # Return standardized error response for immediate consumption
                return error_response(str(e), context=original_context)
```

## Universal Error Handler with Hierarchical Propagation

```python
# ksi_daemon/system_error_handler.py

@event_handler("system:error")
async def universal_error_handler(data, context):
    """
    Universal error handler - routes ALL errors based on context.
    
    This is the single source of truth for error propagation in KSI.
    Every error in the system flows through this handler.
    """
    # PYTHONIC CONTEXT REFACTOR: Resolve context reference
    ksi_context_ref = data.get("_ksi_context", "")
    
    if isinstance(ksi_context_ref, str) and ksi_context_ref.startswith("ctx_"):
        cm = get_context_manager()
        ksi_context = await cm.get_context(ksi_context_ref) or {}
    else:
        ksi_context = {}
    
    client_id = ksi_context.get("_client_id", "")
    
    # Store error for debugging/monitoring
    error_id = generate_error_id()
    await emit("state:entity:create", {
        "type": "error",
        "id": error_id,
        "properties": {
            **data,
            "error_id": error_id,
            "processed_at": timestamp_utc()
        }
    })
    
    # Route to originator based on client type
    if client_id.startswith("agent_"):
        agent_id = client_id[6:]
        
        # Format informative error message
        error_message = format_agent_error(data)
        
        # Deliver error to agent
        await emit("completion:inject", {
            "agent_id": agent_id,
            "messages": [{
                "role": "system",
                "content": error_message
            }]
        })
        
        # HIERARCHICAL ERROR PROPAGATION
        # Check agent's error propagation preference
        agent_state = await emit_first("state:entity:get", {
            "type": "agent",
            "id": agent_id
        })
        
        if agent_state and agent_state.get("properties"):
            propagation_level = agent_state["properties"].get("error_propagation_level", 0)
            
            if propagation_level != 0:
                await propagate_error_hierarchically(
                    agent_id, 
                    error_data=data,
                    error_message=error_message,
                    level=propagation_level
                )
        
    elif client_id.startswith("workflow_"):
        # Route to workflow error handler
        workflow_id = client_id[9:]
        await emit("workflow:error", {
            "workflow_id": workflow_id,
            "error": data
        })
        
    # Check for critical errors requiring escalation
    if data.get("error_type") in CRITICAL_ERROR_TYPES:
        await emit("monitor:critical_error", data)
    
    # Check for recoverable errors
    if data.get("error_type") in RECOVERABLE_ERROR_TYPES:
        await emit("error:recovery:attempt", data)
    
    return success_response({
        "error_id": error_id,
        "handled": True,
        "routed_to": client_id
    })
```

## Hierarchical Error Propagation

### Agent-Controlled Error Propagation Levels

Agents can control how far their errors propagate through the hierarchy:

```python
# Agent sets its error propagation preference
await emit("state:entity:update", {
    "type": "agent", 
    "id": agent_id,
    "properties": {
        "error_propagation_level": 1  # Propagate to direct parents only
    }
})
```

**Propagation Levels:**
- `0` = No propagation (default) - Only the agent receives its own errors
- `1` = Direct parents - Errors propagate to immediate parent agents
- `2` = Two levels up - Errors reach parents and grandparents
- `-1` = Full hierarchy - Errors propagate to all ancestors

### Dynamic Parent Discovery

Instead of static `is_ancestor()` functions, parent relationships are discovered through routing rules:

```python
async def find_parent_agents(agent_id, level):
    """
    Find parent agents using dynamic routing rules.
    
    Parents are agents that have routing rules targeting this agent.
    """
    if level == 0:
        return []
    
    # Query routing rules where this agent is a target
    routing_rules = await emit_first("routing:query", {
        "target_agent": agent_id,
        "relationship": "parent_child"
    })
    
    parents = set()
    for rule in routing_rules:
        source_agent = rule.get("source_agent")
        if source_agent:
            parents.add(source_agent)
            
            # Recursively find ancestors if level > 1 or level == -1
            if level > 1 or level == -1:
                ancestors = await find_parent_agents(
                    source_agent, 
                    level - 1 if level > 1 else -1
                )
                parents.update(ancestors)
    
    return list(parents)
```

### Hierarchical Error Delivery

```python
async def propagate_error_hierarchically(agent_id, error_data, error_message, level):
    """
    Propagate error to parent agents based on propagation level.
    """
    # Find parents based on dynamic routing rules
    parent_agents = await find_parent_agents(agent_id, level)
    
    for parent_id in parent_agents:
        # Format error for parent context
        parent_message = f"[Error from child {agent_id}]\n{error_message}"
        
        # Deliver to parent agent
        await emit("completion:inject", {
            "agent_id": parent_id,
            "messages": [{
                "role": "system",
                "content": parent_message,
                "metadata": {
                    "error_source": agent_id,
                    "error_id": error_data.get("error_id"),
                    "propagation_type": "hierarchical"
                }
            }]
        })
```

## Context Reference Architecture (PYTHONIC CONTEXT REFACTOR)

### Context as References

To reduce event size by 66%, context is stored as references:

```python
# Instead of embedding full context in every event:
data["_ksi_context"] = {
    "_event_id": "evt_123",
    "_correlation_id": "corr_456",
    "_client_id": "agent_abc",
    # ... many more fields
}

# We store a reference:
data["_ksi_context"] = "ctx_evt_db79f277"  # Compact reference string
```

### Context Resolution

When context data is needed:

```python
# In handlers that need context data
ksi_context_ref = data.get("_ksi_context")
if isinstance(ksi_context_ref, str) and ksi_context_ref.startswith("ctx_"):
    cm = get_context_manager()
    ksi_context = await cm.get_context(ksi_context_ref)
else:
    # Legacy support for embedded context
    ksi_context = ksi_context_ref if isinstance(ksi_context_ref, dict) else {}
```

## Transformer Error Propagation

Transformers participate in universal error propagation:

```python
# In transformer execution
try:
    transformed_data = apply_mapping(transformer['mapping'], data, context)
    await emit(target, transformed_data, context)
except Exception as e:
    # Transformer errors flow through system:error
    error_event = {
        "error_type": "transformer_failure",
        "error_class": type(e).__name__,
        "error_message": str(e),
        "source": {
            "transformer": transformer.get('name'),
            "source_event": event,
            "target_event": target
        },
        "_ksi_context": data.get("_ksi_context", "")
    }
    await emit("system:error", error_event)
```

## Universal Monitoring

ALL events are automatically monitored via the universal transformer:

```yaml
# System transformer (auto-loaded)
- name: "universal_broadcast"
  source: "*"  # Match ALL events
  target: "monitor:broadcast_event"
  condition: "not internal_plumbing_event()"
```

This eliminates the need for explicit monitor routing in other transformers.

## Anti-Patterns to Avoid

### ❌ Silent Failure
```python
try:
    result = operation()
except:
    logger.error("Failed")  # Agent never knows!
    return None
```

### ❌ Polling
```python
while True:
    status = await check_status(request_id)
    if status.done:
        break
    sleep(1)  # Wasteful!
```

### ❌ Raw Dict Returns
```python
return {"status": "success"}  # No context!
```

### ❌ Static Hierarchy
```python
if is_ancestor(agent1, agent2):  # Hardcoded!
    route_to(agent1)
```

## Correct Patterns

### ✅ Let Exceptions Flow
```python
@event_handler("my:event")
async def handle(data, context):
    return process(data)  # Exceptions auto-handled
```

### ✅ Push-Based Async
```python
@event_handler("async:op", async_pattern="completion")
async def handle(data, context):
    request_id = queue_work(data)
    return {"request_id": request_id}  # Ack

# Later:
await emit("completion:inject", {"agent_id": agent, "messages": [result]})
```

### ✅ Dynamic Relationships
```python
# Agents define relationships via routing rules
await emit("routing:add_rule", {
    "source_agent": parent_id,
    "target_agent": child_id,
    "relationship": "parent_child"
})

# Errors flow based on these dynamic relationships
```

## Key Guarantees

1. **Every operation responds** - No silent failures
2. **Context always propagates** - Via compact references
3. **Errors reach originators** - And optionally their hierarchy
4. **No polling needed** - Everything is push-based
5. **Dynamic relationships** - No hardcoded hierarchies
6. **Universal monitoring** - All events tracked automatically

---

*Architecture Version: 2.0.0*  
*Last Updated: 2025-08-06*