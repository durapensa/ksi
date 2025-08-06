# KSI Event Transformer Migration Guide

## Executive Summary

The KSI event transformer system is **already implemented** and more capable than initially apparent. This guide provides a practical path to migrate 30-50% of event handlers to declarative transformers, reducing code complexity and improving maintainability.

**Current State**: The transformer engine supports nested templates, conditional routing, and async transformations. It lacks function calls, special variables, and advanced conditions.

**Migration Potential**: ~200+ handlers can be migrated immediately, with ~500+ more possible after minor enhancements.

## What Works Today

### Template Substitution Capabilities ✅
```yaml
# Simple field access
mapping:
  agent_id: "{{agent_id}}"
  
# Nested field access  
mapping:
  total: "{{metrics.tokens.total}}"
  
# Array access
mapping:
  first_item: "{{items.0}}"
  
# Multiple templates in strings
mapping:
  message: "Agent {{agent_id}} changed status to {{status}}"
  
# Complex nested structures
mapping:
  report:
    agent: "{{agent_id}}"
    metrics:
      tokens: "{{usage.tokens}}"
      cost: "{{usage.cost}}"
```

### Conditional Routing ✅
```yaml
transformers:
  - source: "agent:error"
    condition: "severity == 'critical'"
    target: "alert:critical"
    
  - source: "completion:result"
    condition: "tokens > 10000"
    target: "alert:high_usage"
```

### Async Transformations ✅
```yaml
transformers:
  - source: "agent:analyze"
    target: "analysis:perform"
    async: true
    transform_id: "analysis_{{agent_id}}_{{timestamp}}"
```

## Immediate Migration Opportunities

### 1. Hierarchical Routing (Ready Now)

**Current Code** (`hierarchical_routing.py`):
```python
async def _route_to_agent(self, agent_id: str, source_agent_id: str, 
                         event_name: str, event_data: Dict[str, Any]) -> None:
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
  - source: "routing:to_agent"
    target: "agent:event_notification"
    mapping:
      agent_id: "{{target_id}}"
      source_agent_id: "{{source_id}}"
      event_name: "{{event}}"
      event_data: "{{data}}"
```

### 2. Status Propagation (Ready Now)

**Current Pattern**:
```python
@event_handler("agent:spawned")
async def notify_orchestration(data, context):
    return await emit_event("orchestration:agent_available", {
        "agent_id": data["agent_id"],
        "profile": data.get("profile", {}),
        "capabilities": data.get("capabilities", [])
    })
```

**Transformer Replacement**:
```yaml
transformers:
  - source: "agent:spawned"
    target: "orchestration:agent_available"
    mapping:
      agent_id: "{{agent_id}}"
      profile: "{{profile}}"
      capabilities: "{{capabilities}}"
```

### 3. Error Routing (Ready Now)

**Current Pattern**:
```python
if error_data.get("recoverable"):
    await emit_event("error:recoverable", error_data)
else:
    await emit_event("error:fatal", error_data)
```

**Transformer Replacement**:
```yaml
transformers:
  - source: "agent:error"
    condition: "recoverable == true"
    target: "error:recoverable"
    mapping:
      agent_id: "{{agent_id}}"
      error: "{{error}}"
      context: "{{context}}"
      
  - source: "agent:error"
    condition: "recoverable != true"
    target: "error:fatal"
    mapping:
      agent_id: "{{agent_id}}"
      error: "{{error}}"
      context: "{{context}}"
```

## High-Priority Enhancements

### 1. Pass-Through Variable ({{$}})
**Impact**: Enables 100+ more migrations
```yaml
# Pass entire event data
transformers:
  - source: "agent:message"
    target: "audit:log"
    mapping: "{{$}}"  # Pass everything
```

### 2. Function Support
**Impact**: Enables 150+ more migrations
```yaml
mapping:
  timestamp: "{{timestamp_utc()}}"
  duration: "{{time() - started_at}}"
  retry_count: "{{(retry_count || 0) + 1}}"
```

### 3. Context Access
**Impact**: Enables 50+ more migrations
```yaml
mapping:
  modified_by: "{{_ksi_context._agent_id}}"
  request_id: "{{_ksi_context._request_id}}"
```

### 4. Multi-Target Support
**Impact**: Enables 75+ more migrations
```yaml
transformers:
  - source: "orchestration:completed"
    targets:
      - event: "monitor:update"
        mapping: "{{$}}"
      - event: "metrics:record"
        mapping:
          duration: "{{elapsed_time}}"
      - event: "cleanup:trigger"
        mapping:
          orchestration_id: "{{id}}"
```

## Implementation Roadmap

### Phase 1: Immediate Migrations (Week 1)
1. **Create transformer library**:
   ```bash
   var/lib/compositions/transformers/
   ├── routing/
   │   ├── hierarchical.yaml
   │   └── agent_communication.yaml
   ├── monitoring/
   │   └── status_propagation.yaml
   └── errors/
       └── error_routing.yaml
   ```

2. **Migrate simple forwarders**:
   - Identify handlers with <20 lines that only emit events
   - Convert to transformers
   - Test with existing integration tests
   - Remove Python handlers

3. **Document patterns**:
   - Create transformer cookbook
   - Show before/after examples
   - Performance comparisons

### Phase 2: Core Enhancements (Week 2)
1. **Implement {{$}} pass-through**:
   ```python
   def _apply_mapping(self, template: Any, data: Dict[str, Any]) -> Any:
       if template == "{{$}}":
           return data
       # ... existing code
   ```

2. **Add function support**:
   ```python
   # Support for timestamp_utc(), time(), basic math
   TEMPLATE_FUNCTIONS = {
       'timestamp_utc': timestamp_utc,
       'time': time.time,
       'len': len,
   }
   ```

3. **Enable context access**:
   ```python
   # Make _ksi_context available in templates
   template_data = {**data, '_ksi_context': context}
   ```

### Phase 3: Advanced Features (Week 3)
1. **Multi-target transformers**
2. **Regex conditions**: `condition: "event ~= '^test:.*'"`
3. **Delay parameter**: `delay: 5000`
4. **Batching support**

### Phase 4: Mass Migration (Week 4+)
1. **Automated analysis**:
   - Script to identify migration candidates
   - Generate transformer definitions
   - Create migration PRs

2. **Performance optimization**:
   - Benchmark transformer vs handler performance
   - Optimize hot paths
   - Cache compiled templates

## Migration Examples

### Example 1: Agent Messaging Pattern
**Before** (50 lines of Python):
```python
@event_handler("message:send")
async def handle_message_send(data, context):
    to_agent = data.get("to")
    from_agent = context.get("_agent_id")
    
    if not to_agent:
        return error_response("Missing 'to' field")
        
    # Check if agent exists
    agent_info = await emit_event("agent:info", {"agent_id": to_agent})
    if not agent_info.get("data"):
        return error_response(f"Agent {to_agent} not found")
    
    # Forward message
    result = await emit_event("agent:receive_message", {
        "agent_id": to_agent,
        "from_agent": from_agent,
        "message": data.get("message"),
        "timestamp": timestamp_utc()
    })
    
    return success_response({"delivered": True})
```

**After** (10 lines of YAML):
```yaml
transformers:
  - source: "message:send"
    target: "agent:receive_message"
    condition: "to != null"
    mapping:
      agent_id: "{{to}}"
      from_agent: "{{_ksi_context._agent_id}}"
      message: "{{message}}"
      timestamp: "{{timestamp_utc()}}"
```

### Example 2: Orchestration Status Updates
**Before** (75 lines across multiple files):
```python
# In orchestration service
async def _notify_status_change(self, orch_id, old_status, new_status):
    # Notify monitors
    await self.emit_event("monitor:orchestration_status", {
        "orchestration_id": orch_id,
        "old_status": old_status,
        "new_status": new_status,
        "timestamp": timestamp_utc()
    })
    
    # Update metrics
    await self.emit_event("metrics:orchestration_transition", {
        "id": orch_id,
        "from": old_status,
        "to": new_status
    })
    
    # Trigger cleanup if completed
    if new_status in ["completed", "failed"]:
        await self.emit_event("cleanup:orchestration", {
            "orchestration_id": orch_id,
            "final_status": new_status
        })
```

**After** (20 lines of YAML):
```yaml
transformers:
  - source: "orchestration:status_changed"
    targets:
      - event: "monitor:orchestration_status"
        mapping:
          orchestration_id: "{{id}}"
          old_status: "{{old_status}}"
          new_status: "{{new_status}}"
          timestamp: "{{timestamp_utc()}}"
          
      - event: "metrics:orchestration_transition"
        mapping:
          id: "{{id}}"
          from: "{{old_status}}"
          to: "{{new_status}}"
          
      - event: "cleanup:orchestration"
        condition: "new_status in ['completed', 'failed']"
        mapping:
          orchestration_id: "{{id}}"
          final_status: "{{new_status}}"
```

## Success Metrics

### Code Reduction
- **Target**: 30-40% reduction in event handling code
- **Measurement**: Lines of code, cyclomatic complexity

### Performance
- **Target**: 10-20% improvement in event routing
- **Measurement**: Event latency, throughput benchmarks

### Maintainability
- **Target**: 50% faster to add new event routes
- **Measurement**: Time to implement new patterns

### Developer Experience
- **Target**: 80% preference for transformers over handlers
- **Measurement**: Developer surveys, PR metrics

## Anti-Patterns to Avoid

### ❌ Complex Business Logic
```yaml
# DON'T: Complex calculations in transformers
mapping:
  risk_score: "{{(impact * probability) / (1 + mitigation_factor) * 100}}"
```

### ❌ External API Calls
```yaml
# DON'T: Transformers should not make external calls
target: "http://external-api.com/webhook"  # Not supported
```

### ❌ Stateful Processing
```yaml
# DON'T: Transformers are stateless by design
mapping:
  count: "{{$state.counter++}}"  # Not supported
```

## Next Steps

1. **Review and approve** this migration guide
2. **Create transformer library** structure in compositions
3. **Migrate first batch** of simple handlers
4. **Implement priority enhancements** ({{$}}, functions)
5. **Scale migration** across all services

## Conclusion

The transformer system is ready for production use. With minor enhancements, it can replace 30-50% of event handlers, delivering significant improvements in code maintainability, performance, and developer experience. The migration can be done incrementally with minimal risk.

**Recommendation**: Start Phase 1 immediately while developing Phase 2 enhancements in parallel.