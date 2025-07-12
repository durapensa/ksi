# Transform Event Discoverability Analysis

## Executive Summary

This report analyzes the discoverability of transform events within the KSI (Kubernetes-Style Infrastructure) system. The analysis reveals that while the transformer system is architecturally sound and functionally complete, dynamic transform events created from YAML patterns are **not discoverable** through the standard discovery system. This creates a significant gap in developer experience and system introspection capabilities.

**Key Findings:**
- Transform events work correctly but are invisible to discovery
- The gap is specific to the discovery system implementation
- Solution requires minimal code changes with significant UX benefits
- No architectural changes needed - existing design is solid

**Recommendation:** Enhance the discovery system to include dynamic transform events with clear identification and parameter extraction.

## Current State Analysis

### System Architecture Overview

The KSI transformer system operates on a two-tier architecture:

1. **Pattern Management Layer** (`transformer_service.py`)
   - Loads/unloads YAML transformer patterns
   - Manages reference counting for shared patterns
   - Integrates with composition system

2. **Core Transformation Layer** (`event_system.py`)
   - Dynamic transformer registry (`router._transformers`)
   - Template substitution engine with `{{variable}}` support
   - Async transformation with response routing
   - Conditional transformation logic

### Event Types in KSI

The system currently handles two distinct categories of events:

#### Static Management Events (Discoverable ✅)
```
transformer:load_pattern
transformer:unload_pattern  
transformer:reload_pattern
transformer:list_by_pattern
transformer:get_usage
router:register_transformer
router:unregister_transformer
router:list_transformers
```

#### Dynamic Transform Events (Not Discoverable ❌)
- Created when YAML patterns are loaded
- Source events like `test:hello`, `pattern:analyze`, `workflow:step1`
- Transform input data and route to target events
- **Functional but invisible** to discovery system

### Discovery System Architecture

The discovery system (`ksi_daemon/core/discovery.py`) uses a sophisticated multi-layered analysis:

1. **UnifiedHandlerAnalyzer**: Combines TypedDict and AST analysis
2. **Parameter Extraction**: From type annotations and inline comments
3. **Example Mining**: Real usage examples from codebase
4. **Trigger Analysis**: Event dependency mapping
5. **Multiple Output Formats**: verbose, compact, ultra_compact, mcp

**Critical Gap**: Discovery only analyzes `router._handlers` (static events) but ignores `router._transformers` (dynamic events).

## Technical Gap Analysis

### Discovery System Implementation Review

Current discovery logic in `handle_discover()` (lines 739-756):

```python
# Gather all events first
for event_name, handlers in router._handlers.items():
    handler = handlers[0]  # Use first handler
    
    handler_info = {
        "module": handler.module,
        "handler": handler.name,
        "async": handler.is_async,
        "summary": extract_summary(handler.func),
    }
    # ... analysis continues
```

**Missing**: No iteration over `router._transformers` to include dynamic events.

### Transform Event Lifecycle

1. **Pattern Loading**: `transformer_service.load_pattern_transformers()`
2. **Registration**: `router.register_transformer_from_yaml(transformer_def)`
3. **Storage**: Added to `router._transformers[source] = transformer_def`
4. **Execution**: `router.emit()` checks transformers before handlers
5. **Discovery**: **SKIPPED** - not included in discovery analysis

### Evidence of Discoverability Gap

**Test Case:**
```bash
# After loading test_transformer_flow pattern:
ksi discover --namespace test
# Returns: No output (empty)

ksi help test:hello  
# Returns: "test:hello No description"
```

**Root Cause:** Discovery system only examines:
- `router._handlers` (static @event_handler functions)
- `router._pattern_handlers` (pattern matching handlers)

It does **not** check `router._transformers` for dynamically created transform events.

## Proposed Solution

### Enhancement Strategy

**Approach**: Extend the discovery system to include transform events with clear identification and parameter extraction.

**Core Principle**: Transform events should be discoverable with the same richness as static events while being clearly identified as dynamic transformers.

### Implementation Design

#### 1. Discovery System Enhancement

Modify `handle_discover()` in `discovery.py` to include transform events:

```python
def include_dynamic_transformers(router, all_events):
    """Add dynamic transform events to discovery."""
    for source, transformer_config in router._transformers.items():
        # Create synthetic event info for transform events
        all_events[source] = {
            "module": "transformer.dynamic",
            "handler": "transform_event",
            "async": transformer_config.get('async', False),
            "summary": f"Transform: {source} → {transformer_config.get('target')}",
            "event_type": "transform",  # Clear identification
            "transformer_config": transformer_config,
            "target_event": transformer_config.get('target'),
            "parameters": extract_transform_parameters(transformer_config)
        }
```

#### 2. Parameter Extraction Algorithm

```python
def extract_transform_parameters(transformer_config):
    """Extract expected parameters from transformer mapping and conditions."""
    parameters = {}
    
    # Analyze template variables in mapping
    mapping = transformer_config.get('mapping', {})
    template_vars = set()
    
    def find_template_variables(value, path=""):
        """Recursively find {{variable}} patterns in any structure."""
        if isinstance(value, str):
            import re
            matches = re.findall(r'\{\{([^}]+)\}\}', value)
            for match in matches:
                var_name = match.strip()
                # Handle dot notation: user.name -> user
                base_var = var_name.split('.')[0]
                template_vars.add(base_var)
                
                # Create parameter info
                if base_var not in parameters:
                    parameters[base_var] = {
                        'type': 'Any',
                        'required': True,
                        'description': f'Template variable used in mapping',
                        'template_usage': []
                    }
                
                # Track usage locations
                usage_info = f"{path}: {value}" if path else f"mapping: {value}"
                if usage_info not in parameters[base_var]['template_usage']:
                    parameters[base_var]['template_usage'].append(usage_info)
                    
        elif isinstance(value, dict):
            for k, v in value.items():
                find_template_variables(v, f"{path}.{k}" if path else k)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                find_template_variables(v, f"{path}[{i}]" if path else f"[{i}]")
    
    # Process all mapping values
    for key, value in mapping.items():
        find_template_variables(value, key)
    
    # Add condition parameters if present
    condition = transformer_config.get('condition')
    if condition:
        # Simple condition analysis - can be enhanced
        condition_vars = extract_condition_variables(condition)
        for var_name, var_info in condition_vars.items():
            if var_name not in parameters:
                parameters[var_name] = var_info
            else:
                # Merge condition info
                parameters[var_name]['description'] += f" (also used in condition: {condition})"
    
    return parameters

def extract_condition_variables(condition_str):
    """Extract variables from condition strings like 'priority == high'."""
    parameters = {}
    
    # Simple regex to find variable names in conditions
    # This can be enhanced with proper expression parsing
    import re
    var_matches = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', condition_str)
    
    for var in var_matches:
        if var not in ['and', 'or', 'not', 'in', 'is', 'True', 'False', 'None']:
            parameters[var] = {
                'type': 'Any',
                'required': True,
                'description': f'Variable used in condition: {condition_str}',
                'condition_usage': condition_str
            }
    
    return parameters
```

#### 3. Transform Event Identification

Transform events will be identifiable through multiple markers:

1. **`event_type`**: "transform" (vs "handler" for static events)
2. **`module`**: "transformer.dynamic" (vs actual module paths)
3. **`handler`**: "transform_event" (vs actual function names)
4. **`target_event`**: Shows transformation destination
5. **`transformer_config`**: Complete YAML configuration for debugging

### Discovery Output Examples

#### Before Enhancement
```bash
ksi discover --namespace test
# Returns: {} (empty)
```

#### After Enhancement
```json
{
  "events": {
    "test:hello": {
      "module": "transformer.dynamic",
      "handler": "transform_event",
      "async": false,
      "event_type": "transform",
      "summary": "Transform: test:hello → agent:send_message",
      "target_event": "agent:send_message",
      "parameters": {
        "message": {
          "type": "Any",
          "required": true,
          "description": "Template variable used in mapping",
          "template_usage": ["message: {{message}}"]
        }
      }
    },
    "test:async_task": {
      "module": "transformer.dynamic", 
      "handler": "transform_event",
      "async": true,
      "event_type": "transform",
      "summary": "Transform: test:async_task → completion:async",
      "target_event": "completion:async",
      "parameters": {
        "task_description": {
          "type": "Any",
          "required": true,
          "description": "Template variable used in mapping",
          "template_usage": ["prompt: Test async completion: {{task_description}}"]
        }
      }
    }
  },
  "total": 2,
  "namespaces": ["test"]
}
```

#### Enhanced Help Output
```bash
ksi help test:hello
```

```json
{
  "module": "transformer.dynamic",
  "handler": "transform_event", 
  "async": false,
  "event_type": "transform",
  "summary": "Transform: test:hello → agent:send_message",
  "target_event": "agent:send_message",
  "parameters": {
    "message": {
      "type": "Any",
      "required": true,
      "description": "Template variable used in mapping",
      "template_usage": ["message: {{message}}"]
    }
  },
  "transformer_config": {
    "source": "test:hello",
    "target": "agent:send_message", 
    "mapping": {
      "agent_id": "test_agent_123",
      "message": "{{message}}"
    }
  },
  "usage": {
    "event": "test:hello",
    "data": {
      "message": "example_value"
    }
  }
}
```

## Implementation Details

### Code Changes Required

#### 1. Modify `discovery.py`

**Location**: `ksi_daemon/core/discovery.py`, `handle_discover()` function around line 756

**Change**: Add transform event inclusion after static handler analysis:

```python
# After existing handler analysis
for event_name, handlers in router._handlers.items():
    # ... existing code ...

# ADD: Include dynamic transform events
for source_event, transformer_config in router._transformers.items():
    all_events[source_event] = create_transform_event_info(source_event, transformer_config)
```

#### 2. Add Parameter Extraction Functions

**Location**: `ksi_daemon/core/discovery.py` (new functions)

**Functions to add**:
- `extract_transform_parameters(transformer_config)`
- `extract_condition_variables(condition_str)`
- `create_transform_event_info(source_event, transformer_config)`

#### 3. Update Help Handler

**Location**: `ksi_daemon/core/discovery.py`, `handle_help()` function around line 800

**Change**: Check both handlers and transformers:

```python
# Current: Only check handlers
if event_name not in router._handlers:
    return {"error": f"Event not found: {event_name}"}

# Enhanced: Check both handlers and transformers
if event_name in router._handlers:
    # Existing handler analysis
    handler = router._handlers[event_name][0]
    # ... existing code ...
elif event_name in router._transformers:
    # Transform event analysis
    transformer_config = router._transformers[event_name]
    return create_transform_help_info(event_name, transformer_config)
else:
    return {"error": f"Event not found: {event_name}"}
```

### Testing Strategy

#### 1. Unit Tests

```python
def test_transform_event_discovery():
    """Test that transform events are discoverable."""
    # Load test pattern with transformers
    router = get_router()
    router.register_transformer_from_yaml({
        'source': 'test:example',
        'target': 'target:event',
        'mapping': {'field': '{{value}}'}
    })
    
    # Test discovery includes transform event
    result = await handle_discover({'namespace': 'test', 'detail': True})
    
    assert 'test:example' in result['events']
    event_info = result['events']['test:example']
    assert event_info['event_type'] == 'transform'
    assert event_info['target_event'] == 'target:event'
    assert 'value' in event_info['parameters']

def test_transform_event_help():
    """Test help for transform events."""
    # Test help for transform event
    result = await handle_help({'event': 'test:example'})
    
    assert result['event_type'] == 'transform'
    assert 'transformer_config' in result
    assert 'parameters' in result
```

#### 2. Integration Tests

```python
def test_discovery_integration():
    """Test complete discovery with mixed static and transform events."""
    # Load pattern with multiple transformers
    # Verify all events discoverable
    # Test namespace filtering works
    # Test parameter extraction accuracy
```

#### 3. Performance Tests

```python
def test_discovery_performance():
    """Ensure discovery performance doesn't degrade."""
    # Load many patterns
    # Measure discovery response time
    # Verify acceptable performance
```

### Backward Compatibility

**Guaranteed**: All existing functionality remains unchanged.

- Static events: No changes to existing discovery behavior
- Transform functionality: No changes to transformer execution
- API compatibility: Discovery response structure extended, not modified
- Output formats: All existing formats (verbose, compact, etc.) supported

### Error Handling

```python
def create_transform_event_info(source_event, transformer_config):
    """Create event info for transform event with error handling."""
    try:
        return {
            "module": "transformer.dynamic",
            "handler": "transform_event",
            "async": transformer_config.get('async', False),
            "summary": f"Transform: {source_event} → {transformer_config.get('target', 'unknown')}",
            "event_type": "transform",
            "transformer_config": transformer_config,
            "target_event": transformer_config.get('target'),
            "parameters": extract_transform_parameters(transformer_config)
        }
    except Exception as e:
        logger.warning(f"Error analyzing transform event {source_event}: {e}")
        return {
            "module": "transformer.dynamic",
            "handler": "transform_event", 
            "async": False,
            "summary": f"Transform: {source_event} (analysis failed)",
            "event_type": "transform",
            "error": str(e)
        }
```

## Benefits and Impact

### Developer Experience Improvements

1. **Complete Event Visibility**
   - All events (static + dynamic) discoverable in one place
   - No "hidden" events that work but aren't documented
   - IDE autocomplete and validation becomes possible

2. **Clear Event Classification**
   - Transform events clearly marked with `event_type: "transform"`
   - Visual distinction between static handlers and dynamic transformers
   - Target event information for understanding data flow

3. **Automatic Parameter Documentation**
   - Template variables extracted from YAML mappings
   - Usage examples showing where variables are used
   - Condition variables documented from conditional transformers

4. **Enhanced System Introspection**
   - Complete picture of event flow in the system
   - Ability to trace event transformations
   - Debug information available through transformer_config

### System Architecture Benefits

1. **No Architectural Changes Required**
   - Existing transformer system remains unchanged
   - Discovery enhancement is purely additive
   - Clean separation of concerns maintained

2. **Consistent Discovery Interface**
   - Same discovery API works for all event types
   - Uniform parameter extraction across static and dynamic events
   - Multiple output formats supported consistently

3. **Debugging and Monitoring**
   - Complete event registry for monitoring tools
   - Transformer configuration visible for debugging
   - Parameter validation possible with extracted schemas

### Performance Impact

**Minimal**: Discovery is typically used for development and debugging, not production event processing.

- Transform event inclusion: O(n) where n = number of loaded transformers
- Parameter extraction: One-time cost per discovery call
- Memory overhead: Negligible (transformers already in memory)
- Event processing: Zero impact (no changes to emit() flow)

### Ecosystem Benefits

1. **Tool Development**
   - IDE plugins can provide complete event autocomplete
   - Documentation generators can include all events
   - Monitoring tools get complete event visibility

2. **Pattern Sharing**
   - Transform events become self-documenting
   - Pattern libraries can expose their event vocabularies
   - Composition discovery shows complete capabilities

3. **Federation Readiness**
   - Complete event registries enable federation
   - Cross-system event discovery becomes possible
   - Pattern sharing between KSI instances supported

## Recommendations

### Immediate Actions

1. **Implement Discovery Enhancement**
   - Priority: High
   - Effort: 1-2 days
   - Impact: Significant UX improvement

2. **Add Comprehensive Tests**
   - Unit tests for parameter extraction
   - Integration tests with real patterns
   - Performance regression tests

3. **Update Documentation**
   - Discovery system documentation
   - Transform event usage examples
   - Parameter extraction behavior

### Future Enhancements

1. **Enhanced Parameter Analysis**
   - Type inference from template usage patterns
   - Validation constraint extraction from conditions
   - Example generation from real usage

2. **Visual Discovery Tools**
   - Web-based event explorer
   - Event flow diagrams
   - Interactive parameter documentation

3. **Advanced Transform Features**
   - Schema validation for transform parameters
   - Transform event testing framework
   - Performance monitoring for transformers

### Migration Strategy

**Phase 1**: Implement core discovery enhancement
**Phase 2**: Add comprehensive parameter extraction  
**Phase 3**: Build development tools on enhanced discovery
**Phase 4**: Integrate with broader KSI ecosystem tools

## Conclusion

The KSI transformer system demonstrates excellent architectural design with a clean separation between pattern management and core transformation logic. The system successfully creates dynamic event vocabularies from declarative YAML patterns, enabling powerful orchestration capabilities.

The discoverability gap is a straightforward implementation issue rather than an architectural flaw. By enhancing the discovery system to include transform events with proper identification and parameter extraction, KSI will provide complete event visibility while maintaining its solid architectural foundations.

**The recommended enhancement will transform KSI from a system with "hidden" transform events to one with complete, discoverable event transparency - significantly improving developer experience and system introspection capabilities.**

---

*Report prepared: 2025-07-12*  
*Analysis covers: KSI discovery system, transformer architecture, and integration design*  
*Next steps: Implementation of discovery system enhancement*