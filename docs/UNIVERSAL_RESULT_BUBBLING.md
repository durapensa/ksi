# Universal Result Bubbling Architecture

## Core Principle: Every Action Has Feedback

Currently, agents emit events into the void. They have no idea if their events:
- Were received
- Processed successfully  
- Produced results
- Failed with errors
- Are still processing

This creates a **blind system** where agents can't learn from their actions.

## Solution: Automatic Result Routing

### System-Level Routing Rules

Every event handler result automatically routes back to the originator:

```python
# System-wide transformer pattern
class UniversalResultRouter:
    """Automatically routes ALL handler results back to originators."""
    
    @transformer("*:result")  # Catches all handler results
    async def route_result_to_originator(event: str, data: Dict):
        # Extract context from the result
        context = data.get("_ksi_context", {})
        client_id = context.get("_client_id")
        
        if not client_id:
            return  # No originator to route to
        
        # Determine routing based on client type
        if client_id.startswith("agent_"):
            agent_id = client_id.replace("agent_", "")
            
            # Route successful result to agent
            await emit("agent:result", {
                "agent_id": agent_id,
                "original_event": context.get("_root_event_id"),
                "event_type": event.replace(":result", ""),
                "result": data.get("result"),
                "status": data.get("status", "success"),
                "timestamp": data.get("timestamp"),
                "_ksi_context": context
            })
            
            # Also bubble to parent if configured
            if parent := await get_parent_agent(agent_id):
                if should_bubble(agent_id, event):
                    await emit("agent:child_result", {
                        "parent_id": parent,
                        "child_id": agent_id,
                        "result": data,
                        "_ksi_context": context
                    })
```

### Handler Result Standards

All handlers MUST return structured results:

```python
@event_handler("evaluation:run")
async def handle_evaluation_run(data: Dict, context: Dict) -> Dict:
    """Run evaluation and return structured result."""
    
    # ... evaluation logic ...
    
    # MANDATORY: Return structured result
    return {
        "status": "success",  # success|partial|failed
        "result": {
            "component": component_name,
            "tests_passed": 5,
            "tests_total": 5,
            "performance": "improved by 30%"
        },
        "timestamp": timestamp(),
        "_ksi_context": context  # PRESERVE CONTEXT
    }
```

### Agent Result Handler

Agents receive ALL results from their emissions:

```python
@event_handler("agent:result")
async def handle_agent_result(data: Dict):
    """Deliver operation results to agents."""
    
    agent_id = data["agent_id"]
    
    # Store in state for agent introspection
    await emit("state:entity:update", {
        "type": "agent",
        "id": agent_id,
        "properties": {
            "last_result": data["event_type"],
            "result_history": append_to_history({
                "event": data["original_event"],
                "type": data["event_type"],
                "status": data["status"],
                "result": data["result"],
                "timestamp": data["timestamp"]
            })
        }
    })
    
    # Inject into agent conversation
    message = format_result_message(data)
    await emit("completion:inject", {
        "agent_id": agent_id,
        "message": {
            "role": "system",
            "content": message
        }
    })

def format_result_message(data: Dict) -> str:
    """Format result for agent understanding."""
    
    if data["status"] == "success":
        return f"""✅ SUCCESS: {data['event_type']}
Result: {json.dumps(data['result'], indent=2)}
Your event was processed successfully."""
    
    elif data["status"] == "partial":
        return f"""⚠️ PARTIAL: {data['event_type']}
Result: {json.dumps(data['result'], indent=2)}
The operation partially succeeded. See details above."""
    
    else:  # failed
        return f"""❌ FAILED: {data['event_type']}
Error: {data['result'].get('error')}
The operation failed. Please review and retry if needed."""
```

## Bubbling Levels and Configuration

### Agent Configuration

Agents can specify what results they want to see:

```yaml
agent:
  result_subscription_level: 1  # How deep to receive child results
  result_verbosity: "summary"   # summary|detailed|full
  result_filters:
    - include: ["evaluation:*", "optimization:*"]
    - exclude: ["state:*", "monitor:*"]
```

### Hierarchical Result Flow

```
Level -1: All results from entire subtree
Level 0:  Only direct results (my emissions)
Level 1:  Direct + immediate children
Level N:  Results from N levels deep
```

## Implementation Patterns

### 1. Async Operation Results

For long-running operations, provide progressive feedback:

```python
@event_handler("optimization:async")
async def handle_optimization_async(data: Dict, context: Dict):
    
    # Immediate acknowledgment
    await emit("agent:result", {
        "agent_id": context["_client_id"].replace("agent_", ""),
        "event_type": "optimization:async",
        "status": "acknowledged",
        "result": {"message": "Optimization started", "job_id": job_id}
    })
    
    # ... optimization runs ...
    
    # Progress updates
    for progress in optimization_progress:
        await emit("agent:result", {
            "agent_id": agent_id,
            "event_type": "optimization:progress",
            "status": "running",
            "result": {"progress": progress, "job_id": job_id}
        })
    
    # Final result
    await emit("agent:result", {
        "agent_id": agent_id,
        "event_type": "optimization:complete",
        "status": "success",
        "result": optimization_result
    })
```

### 2. Spawn Result Bubbling

When agents spawn children, they get detailed feedback:

```python
@event_handler("agent:spawn")
async def handle_agent_spawn(data: Dict, context: Dict):
    # ... spawn logic ...
    
    result = {
        "agent_id": new_agent_id,
        "capabilities_granted": capabilities,
        "components_loaded": component_chain,
        "sandbox_uuid": sandbox_uuid,
        "initial_prompt_delivered": True
    }
    
    # Return to spawning agent
    return {
        "status": "success",
        "result": result,
        "_ksi_context": context
    }
    # This automatically routes back via UniversalResultRouter
```

### 3. Error Result Bubbling

Errors are just another type of result:

```python
@event_handler("some:event")
async def handle_some_event(data: Dict, context: Dict):
    try:
        # ... processing ...
        return {"status": "success", "result": result}
    
    except Exception as e:
        # Error is also a result that bubbles back
        return {
            "status": "failed",
            "result": {
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            },
            "_ksi_context": context
        }
```

## Benefits of Universal Result Bubbling

### 1. Complete Observability
- Agents know the outcome of EVERY action
- Parents can monitor child activities
- System-wide visibility of operation success rates

### 2. Rapid Learning
- Agents immediately learn what works
- Error patterns become obvious
- Success patterns can be reinforced

### 3. Debugging Transparency
- Every event has a traceable result
- No more "did my event work?" questions
- Complete action-result chains visible

### 4. Emergent Coordination
- Parents adapt based on child results
- Agents learn optimal event patterns
- System self-organizes around successful patterns

## System Routing Rules

Create these transformers for automatic bubbling:

```yaml
# var/lib/transformers/system/universal_result_bubbling.yaml
transformers:
  - id: "bubble_handler_results"
    source_pattern: "*"
    condition: "event.endswith(':result') or event.endswith(':complete')"
    target: "routing:result_to_originator"
    mapping:
      agent_id: "{{_ksi_context._client_id|replace('agent_', '')}}"
      original_event: "{{_ksi_context._root_event_id}}"
      result: "{{__source_event_data__}}"
      
  - id: "bubble_spawn_success"
    source_pattern: "agent:spawned"
    target: "agent:child_spawned"
    condition: "_ksi_context._client_id"
    mapping:
      parent_id: "{{_ksi_context._client_id|replace('agent_', '')}}"
      child: "{{__source_event_data__}}"
      
  - id: "bubble_errors"
    source_pattern: "error:*"
    target: "agent:error"
    condition: "_ksi_context._client_id"
    mapping:
      agent_id: "{{_ksi_context._client_id|replace('agent_', '')}}"
      error: "{{__source_event_data__}}"
```

## Migration Path

### Phase 1: Infrastructure
1. Create `agent:result` handler
2. Add result formatting utilities
3. Implement state storage for results

### Phase 2: Handler Updates
1. Update handlers to return structured results
2. Ensure context preservation
3. Add result documentation

### Phase 3: Routing Rules
1. Deploy universal result transformer
2. Configure bubbling levels
3. Test with simple events

### Phase 4: Agent Integration
1. Update agent components to expect results
2. Add result processing patterns
3. Document result handling

## Success Metrics

- **100% Result Delivery**: Every event emission gets a result back
- **Zero Blind Operations**: No more fire-and-forget
- **Reduced Debugging Time**: Clear action-result chains
- **Improved Agent Learning**: Agents adapt based on results

## The Learning Loop Completes

With universal result bubbling, we create a **complete learning system**:

```
Agent Action → Event Emission → Handler Processing → Result Generation
     ↑                                                      ↓
     ← Result Delivery ← Result Routing ← Context Preservation
```

Every action teaches the agent something, whether success or failure.

---

*"In a truly intelligent system, every action produces feedback, every result carries learning, and every agent grows from experience."* - KSI Architecture Philosophy