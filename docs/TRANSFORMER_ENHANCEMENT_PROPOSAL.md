# Transformer Enhancement Proposal: Pass-Through Variable

## Overview

This proposal outlines the implementation of the `{{$}}` pass-through variable in the KSI event transformer system. This single enhancement would enable migration of 100+ additional event handlers.

## Current Limitation

Currently, to pass all event data through a transformer, you must explicitly map each field:

```yaml
transformers:
  - source: "agent:error"
    target: "monitor:log_error"
    mapping:
      agent_id: "{{agent_id}}"
      error: "{{error}}"
      context: "{{context}}"
      timestamp: "{{timestamp}}"
      # ... must list every field
```

## Proposed Enhancement

Add support for `{{$}}` to pass the entire event data:

```yaml
transformers:
  - source: "agent:error"
    target: "monitor:log_error"
    mapping: "{{$}}"  # Pass entire event data
```

## Implementation

### 1. Modify `_apply_mapping` in event_system.py

```python
def _apply_mapping(self, template: Any, data: Dict[str, Any], 
                   context: Dict[str, Any] = None) -> Any:
    """Apply template mapping to data with enhanced variable support."""
    
    # Special case: {{$}} means pass all data
    if template == "{{$}}":
        return data
    
    if isinstance(template, str):
        # Check for {{$}} within a string template
        if "{{$}}" in template:
            # Replace {{$}} with the entire data structure
            result = template.replace("{{$}}", json.dumps(data))
        else:
            # Existing template logic
            result = template
            
        # Process other template variables
        for match in re.findall(r'\{\{([^}]+)\}\}', result):
            if match == "$":  # Skip already processed
                continue
                
            value = self._resolve_path(match, data, context)
            if value is not None:
                result = result.replace(f"{{{{{match}}}}}", str(value))
        
        return result
    
    # ... rest of existing implementation
```

### 2. Add Context Variable Support

```python
def _resolve_path(self, path: str, data: Dict[str, Any], 
                  context: Dict[str, Any] = None) -> Any:
    """Resolve a dot-notation path with context support."""
    
    # Check for context prefix
    if path.startswith("_ksi_context."):
        if context:
            context_path = path[13:]  # Remove "_ksi_context."
            return self._get_nested_value(context, context_path)
        return None
    
    # Existing path resolution
    return self._get_nested_value(data, path)
```

## Use Cases Enabled

### 1. Simple Pass-Through (50+ handlers)

```yaml
# Forward entire error to monitoring
transformers:
  - source: "agent:error"
    target: "monitor:agent_error"
    mapping: "{{$}}"
```

### 2. Conditional Pass-Through (30+ handlers)

```yaml
# Route errors based on severity
transformers:
  - source: "completion:error"
    condition: "error_type == 'timeout'"
    target: "retry:completion"
    mapping: "{{$}}"
    
  - source: "completion:error"
    condition: "error_type != 'timeout'"
    target: "alert:completion_failed"
    mapping: "{{$}}"
```

### 3. Multi-Target Broadcasting (20+ handlers)

```yaml
# Broadcast state changes
transformers:
  - source: "orchestration:state_changed"
    targets:
      - event: "monitor:orchestration_state"
        mapping: "{{$}}"
      - event: "metrics:state_transition"
        mapping: "{{$}}"
      - event: "audit:log"
        mapping: "{{$}}"
```

## Migration Examples

### Before: Agent Status Handler
```python
@event_handler("agent:status_changed")
async def handle_status_change(data, context):
    # Forward to multiple systems
    await emit_event("monitor:agent_status", data)
    await emit_event("metrics:agent_status", data)
    
    if data.get("status") == "error":
        await emit_event("alert:agent_error", data)
    
    return success_response("Status propagated", context)
```

### After: Transformer
```yaml
transformers:
  - source: "agent:status_changed"
    targets:
      - event: "monitor:agent_status"
        mapping: "{{$}}"
      - event: "metrics:agent_status"
        mapping: "{{$}}"
        
  - source: "agent:status_changed"
    condition: "status == 'error'"
    target: "alert:agent_error"
    mapping: "{{$}}"
```

## Testing Strategy

### 1. Unit Tests
```python
def test_dollar_pass_through():
    """Test {{$}} passes entire data structure."""
    router = EventRouter()
    
    # Test direct pass-through
    result = router._apply_mapping("{{$}}", {"a": 1, "b": 2})
    assert result == {"a": 1, "b": 2}
    
    # Test within string template
    result = router._apply_mapping("Data: {{$}}", {"x": "test"})
    assert result == 'Data: {"x": "test"}'
```

### 2. Integration Tests
- Register transformers using {{$}}
- Verify data passes through unmodified
- Test with nested structures
- Verify performance impact

## Performance Considerations

- Direct assignment for `mapping: "{{$}}"` is O(1)
- No deep copying needed - pass reference
- Minimal overhead compared to explicit mapping

## Rollout Plan

1. **Week 1**: Implement and test {{$}} support
2. **Week 2**: Migrate simple pass-through handlers
3. **Week 3**: Migrate conditional routing handlers
4. **Week 4**: Document patterns and best practices

## Success Metrics

- 100+ handlers migrated in first month
- 50% reduction in forwarding handler code
- Zero performance regression
- Developer satisfaction with simplified syntax

## Conclusion

The {{$}} pass-through variable is a simple enhancement that would unlock significant migration opportunities. It aligns with developer expectations from similar template systems and would make transformer adoption much easier.