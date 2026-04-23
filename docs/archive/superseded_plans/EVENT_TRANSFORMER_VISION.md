# Event Transformer Architecture Vision

## Executive Summary

The KSI event transformer system represents a paradigm shift from imperative to declarative event handling. By replacing Python handler code with YAML-based transformation rules, we can achieve:
- **50-70% code reduction** in routing/forwarding scenarios
- **Hot-reloadable configurations** without daemon restarts
- **Visual event flow** that's easier to understand and modify
- **Performance improvements** by running in the core router
- **Unified patterns** across the entire system

## Current State Analysis ✅ INFRASTRUCTURE COMPLETE

### Implemented Capabilities
The event transformer system in `ksi_daemon/event_system.py` provides:
- **Dynamic registration** of transformers from YAML ✅
- **Template-based field mapping** with nested object support ✅
- **Conditional transformation** based on expressions ✅
- **Async transformations** with response routing ✅
- **Pattern-level management** via transformer service ✅
- **State-based configuration** (removed services.json anti-pattern) ✅

### Production Usage
Transformers actively deployed in:
- Agent communication routing in orchestrations
- Async pattern analysis workflows
- Service lifecycle management
- Event forwarding and conditional routing

## Transformer Replacement Opportunities

### 1. Simple Event Forwarding (30% of handlers)

**Current Python Handler:**
```python
@event_handler("agent:message")
async def handle_agent_message(data, context):
    # Forward to monitor
    await emit_event("monitor:agent_activity", {
        "agent_id": data["agent_id"],
        "activity_type": "message",
        "timestamp": timestamp_utc()
    })
    return success_response(data, context)
```

**Transformer Replacement:**
```yaml
transformers:
  - source: "agent:message"
    target: "monitor:agent_activity"
    mapping:
      agent_id: "data.agent_id"
      activity_type: "'message'"
      timestamp: "timestamp_utc()"
```

### 2. Conditional Routing (25% of handlers)

**Current Python Handler:**
```python
@event_handler("completion:result")
async def handle_completion_result(data, context):
    if data.get("status") == "error":
        await emit_event("alert:completion_error", data)
    elif data.get("tokens", {}).get("total", 0) > 10000:
        await emit_event("alert:high_token_usage", data)
    return success_response(data, context)
```

**Transformer Replacement:**
```yaml
transformers:
  - source: "completion:result"
    condition: "data.status == 'error'"
    target: "alert:completion_error"
    
  - source: "completion:result"
    condition: "data.tokens.total > 10000"
    target: "alert:high_token_usage"
```

### 3. Multi-Target Distribution (20% of handlers)

**Current Python Handler:**
```python
@event_handler("orchestration:completed")
async def handle_orchestration_completed(data, context):
    # Notify multiple systems
    await emit_event("monitor:orchestration_status", data)
    await emit_event("metrics:orchestration_completed", data)
    await emit_event("cleanup:orchestration_resources", {"id": data["orchestration_id"]})
    return success_response("Notifications sent", context)
```

**Transformer Replacement:**
```yaml
transformers:
  - source: "orchestration:completed"
    targets:
      - event: "monitor:orchestration_status"
        mapping: "data"
      - event: "metrics:orchestration_completed"
        mapping: "data"
      - event: "cleanup:orchestration_resources"
        mapping:
          id: "data.orchestration_id"
```

### 4. Data Transformation (15% of handlers)

**Current Python Handler:**
```python
@event_handler("agent:status_update")
async def handle_agent_status(data, context):
    transformed = {
        "entity_id": f"agent_{data['agent_id']}",
        "entity_type": "agent",
        "status": data["status"],
        "metadata": {
            "profile": data.get("profile"),
            "uptime": time.time() - data.get("started_at", time.time())
        }
    }
    await emit_event("entity:status_changed", transformed)
    return success_response("Status transformed", context)
```

**Transformer Replacement:**
```yaml
transformers:
  - source: "agent:status_update"
    target: "entity:status_changed"
    mapping:
      entity_id: "'agent_' + data.agent_id"
      entity_type: "'agent'"
      status: "data.status"
      metadata:
        profile: "data.profile"
        uptime: "time() - data.get('started_at', time())"
```

## Advanced Transformer Patterns

### 1. Conversation Monitoring Pipeline
```yaml
# Monitor all conversation summaries and trigger actions
transformers:
  - source: "completion:get_conversation_summary"
    target: "analytics:conversation_metrics"
    async: true
    mapping:
      agent_id: "data.agent_id"
      metrics:
        length: "response.context_chain_length"
        session_active: "response.status == 'active_session'"
        
  - source: "analytics:conversation_metrics"
    condition: "data.metrics.length > 50"
    target: "agent:suggest_summary"
    mapping:
      agent_id: "data.agent_id"
      suggestion: "'Consider summarizing this long conversation'"
```

### 2. Automatic Error Recovery
```yaml
transformers:
  - source: "completion:error"
    condition: "data.error_type == 'timeout'"
    target: "completion:retry"
    delay: 5000  # 5 second delay
    mapping:
      request_id: "data.request_id"
      retry_count: "(data.retry_count || 0) + 1"
      max_retries: 3
```

### 3. Event Aggregation
```yaml
transformers:
  - source: "agent:*"
    target: "metrics:agent_events"
    batch:
      size: 100
      timeout: 60000  # 1 minute
    mapping:
      events: "batch"
      event_count: "batch.length"
      time_window: 
        start: "batch[0]._timestamp"
        end: "batch[-1]._timestamp"
```

## Implementation Strategy

### Phase 1: Identify and Migrate Simple Forwarders
1. Scan for handlers that only emit events
2. Convert to declarative transformers
3. Remove Python handler code
4. Test with existing integration tests

### Phase 2: Conditional Routing Migration
1. Identify handlers with simple if/else logic
2. Convert to conditional transformers
3. Validate condition syntax and behavior
4. Performance test complex conditions

### Phase 3: Complex Transformations
1. Build transformer functions library
2. Extend mapping syntax for complex operations
3. Migrate data transformation handlers
4. Create debugging tools for transformers

### Phase 4: System-Wide Patterns
1. Create transformer templates for common patterns
2. Build transformer composition system
3. Implement transformer versioning
4. Create migration tools for handlers

## Benefits Analysis

### Code Reduction
- **Simple forwarders**: 90% less code
- **Conditional routing**: 70% less code
- **Data transformations**: 50% less code
- **Overall system**: 30-40% reduction in event handling code

### Performance Improvements
- No Python function call overhead
- Direct routing in EventRouter
- Batching and aggregation at router level
- Conditional evaluation before handler invocation

### Maintainability
- Visual event flow in YAML
- Hot-reload without restarts
- Centralized routing logic
- Reusable transformation patterns

### Developer Experience
- Declarative > Imperative for routing
- Less boilerplate code
- Easier to understand event flow
- Better testability with transformation isolation

## Future Possibilities

### 1. Visual Event Flow Designer
Create a web UI to:
- Visualize active transformers
- Design new transformations
- Test transformations with sample data
- Monitor transformation performance

### 2. Transformer Marketplace
- Share transformer patterns
- Import/export transformer sets
- Version and dependency management
- Community transformer library

### 3. AI-Powered Transformer Generation
- Analyze existing handlers
- Suggest transformer replacements
- Optimize transformation chains
- Learn from usage patterns

### 4. Advanced Features
- **Stateful transformers**: Remember previous events
- **ML transformers**: Use models for routing decisions
- **Distributed transformers**: Cross-node event routing
- **Time-based transformers**: Scheduled and delayed routing

## Conversation Monitoring Example

Based on our conversation work, here's how transformers could enhance the system:

```yaml
# Automatic conversation quality monitoring
transformers:
  - source: "agent:conversation_summary"
    target: "quality:analyze_conversation"
    async: true
    response_route:
      - condition: "response.quality_score < 0.7"
        target: "agent:coaching_suggestion"
        mapping:
          agent_id: "data.agent_id"
          suggestion: "response.improvement_tips"
          
  - source: "agent:conversation_reset"
    target: "metrics:conversation_reset"
    mapping:
      agent_id: "data.agent_id"
      had_session: "response.had_active_session"
      timestamp: "timestamp_utc()"
      
  # Archive long conversations before reset
  - source: "agent:conversation_reset"
    condition: "data._pre_check.context_count > 10"
    target: "archive:save_conversation"
    priority: "high"
    before: true  # Run before the actual reset
```

## Conclusion

The event transformer system represents the future of KSI's event handling architecture. By systematically migrating from imperative handlers to declarative transformers, we can create a more maintainable, performant, and understandable system. The vision extends beyond simple replacements to enabling new patterns of event-driven development that would be impractical with traditional handler code.

The path forward is clear:
1. Start with simple replacements
2. Build confidence and tools
3. Tackle complex scenarios
4. Enable new possibilities

This transformation will position KSI as a leader in declarative event-driven architectures.