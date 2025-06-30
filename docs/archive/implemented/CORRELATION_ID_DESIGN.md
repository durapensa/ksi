# Correlation ID Design for Event Tracing

## Overview

Design for comprehensive event tracing in KSI using correlation IDs to track complex event flows, async operations, and multi-agent interactions.

## Current State

### Existing Implementation
- **EventBasedClient**: Basic correlation IDs for request-response patterns
- **EventRouter**: Correlation ID handling in `route_event()` 
- **EventLog**: Correlation IDs logged for basic monitoring
- **Scope**: Limited to direct client → daemon → client flows

### Limitations
- No chain tracing for cascading events
- No context propagation through async operations
- No visualization of event dependencies
- No trace analysis for debugging complex flows

## Design Goals

### Core Requirements
1. **Chain Tracing**: Track events that trigger other events
2. **Context Propagation**: Preserve trace context across async boundaries
3. **Multi-hop Flows**: Trace complex agent-to-agent interactions
4. **Performance**: Minimal overhead for high-throughput operations
5. **Debuggability**: Clear visualization of event relationships

### Use Cases
- **Completion Injection**: Trace completion → injection → coordinator → response
- **Agent Coordination**: Follow message flows between multiple agents
- **Error Debugging**: Identify root causes in complex event chains
- **Performance Analysis**: Understand bottlenecks in async flows

## Architecture Design

### Correlation ID Structure

```
<root_id>.<span_id>.<depth>
```

- **root_id**: Original request ID (8 chars hex)
- **span_id**: Current operation ID (4 chars hex) 
- **depth**: Chain depth (prevents infinite loops)

**Examples:**
- `abc12345.0001.0` - Root request
- `abc12345.0002.1` - First derived operation
- `abc12345.0003.2` - Second-level derived operation

### Trace Context

```python
@dataclass
class TraceContext:
    root_id: str           # Original request ID
    parent_span: str       # Parent span ID
    current_span: str      # Current span ID
    depth: int            # Chain depth
    metadata: Dict        # Operation metadata
    start_time: float     # Span start time
    tags: Dict[str, str]  # Searchable tags
```

### Context Propagation

```python
# Event emission with trace context
async def emit_event_traced(event_name: str, data: Dict, 
                           trace_context: Optional[TraceContext] = None):
    # Generate new span for this operation
    if trace_context:
        new_span = TraceSpan.from_parent(trace_context)
    else:
        new_span = TraceSpan.new_root(event_name)
    
    # Add trace headers to event data
    data["_trace"] = new_span.to_headers()
    
    # Route event with correlation
    await route_event(event_name, data, new_span.correlation_id)
```

## Implementation Plan

### Phase 1: Core Infrastructure

1. **TraceContext Class**
   - Span ID generation
   - Parent-child relationships
   - Depth tracking and limits

2. **Enhanced EventRouter**
   - Extract trace context from events
   - Propagate context to handlers
   - Generate child spans automatically

3. **Plugin Hook Enhancement**
   - Add trace_context parameter to hooks
   - Automatic context injection

### Phase 2: Event Tracing

1. **Traced Event Emission**
   - Update `emit_event` to accept trace context
   - Automatic span generation
   - Context propagation headers

2. **Enhanced Event Log**
   - Store full trace context
   - Parent-child relationship tracking
   - Trace query capabilities

3. **Critical Plugin Updates**
   - completion_service.py
   - injection_router.py
   - agent_service.py

### Phase 3: Visualization & Analysis

1. **Trace Query API**
   - Get full traces by root_id
   - Find related events
   - Performance analysis

2. **Monitor Integration**
   - Trace visualization in interfaces
   - Real-time trace following
   - Error correlation display

## Code Examples

### Enhanced Hook Interface

```python
@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any], 
                    context: Dict[str, Any],
                    trace_context: Optional[TraceContext] = None):
    if event_name == "completion:async":
        # Use trace context for downstream operations
        return await handle_completion_with_tracing(data, trace_context)
    return None
```

### Injection with Tracing

```python
async def route_injection(completion_result: Dict, injection_config: Dict,
                         trace_context: TraceContext):
    # Create child span for injection operation  
    injection_span = trace_context.child_span("injection_route")
    
    # Emit injection event with trace context
    await emit_event_traced("completion:inject", {
        "result": completion_result,
        "config": injection_config
    }, injection_span)
```

### Agent Messaging with Traces

```python
async def send_agent_message(from_agent: str, to_agent: str, 
                           content: str, trace_context: TraceContext):
    # Create span for message sending
    message_span = trace_context.child_span("agent_message", {
        "from": from_agent,
        "to": to_agent
    })
    
    await emit_event_traced("message:send", {
        "from": from_agent,
        "to": to_agent,
        "content": content
    }, message_span)
```

## Benefits

### Development
- **Clear Debugging**: See exact event flow causing issues
- **Performance Insights**: Identify slow operations in chains
- **Architecture Understanding**: Visualize system interactions

### Operations  
- **Error Correlation**: Link failures to root causes
- **Load Analysis**: Understand request amplification patterns
- **Monitoring**: Track complex workflows end-to-end

### Future Extensions
- **Distributed Tracing**: Extend to multi-daemon deployments
- **Sampling**: Reduce overhead with trace sampling
- **Integration**: Connect with external tracing systems (Jaeger, etc.)

## Implementation Priority

1. **High**: Core TraceContext and EventRouter enhancement
2. **High**: Completion service and injection tracing
3. **Medium**: Agent messaging and coordination tracing
4. **Medium**: Trace visualization in monitor interfaces
5. **Low**: External tracing system integration

---

This design provides comprehensive event tracing while maintaining the simplicity and performance characteristics of the KSI system.