# KSI Behavioral Component Library

A comprehensive guide to KSI's behavioral components - modular building blocks that shape agent behavior through composition.

## Overview

Behavioral components are reusable modules that modify how agents interact with the KSI system. They can be combined through dependencies to create sophisticated agent behaviors while maintaining modularity and testability.

## Core Behavioral Components

### 1. claude_code_override
**Path**: `behaviors/core/claude_code_override`  
**Purpose**: Shifts agent behavior from assistant mode to direct execution mode  
**Effect**: 
- Removes explanatory preambles
- Eliminates permission-seeking behavior
- Focuses on direct task execution
- Provides concise, action-oriented responses

**Example Usage**:
```yaml
dependencies:
  - behaviors/core/claude_code_override
```

**Test Result**: When asked "Calculate: 2 + 2", responds with just "4" instead of explanations.

### 2. ksi_events_as_tool_calls (Structured Event Emission)
**Path**: `behaviors/communication/ksi_events_as_tool_calls`  
**Purpose**: Enables reliable JSON event emission using LLM's natural tool-calling abilities  
**Effect**:
- Provides structured format for event emission
- Near 100% extraction reliability
- Handles complex nested data structures
- Supports all KSI event types

**Format**:
```json
{
  "type": "ksi_tool_use",
  "id": "ksiu_status_001",
  "name": "agent:status",
  "input": {
    "agent_id": "{{agent_id}}",
    "status": "processing"
  }
}
```

**Validated Events**:
- agent:status
- state:entity:create/update
- composition:create_component
- message:send

## DSL Components

### 3. event_emission_tool_use
**Path**: `behaviors/dsl/event_emission_tool_use`  
**Purpose**: Converts DSL EVENT blocks to ksi_tool_use format  
**Dependencies**: None (standalone)  
**Use Case**: Basic DSL interpreters that only need event emission

### 4. dsl_execution_override
**Path**: `behaviors/dsl/dsl_execution_override`  
**Purpose**: Bypasses permission-asking for DSL execution  
**Dependencies**: None (standalone)  
**Effect**: Agent executes DSL immediately without confirmation

### 5. state_management
**Path**: `behaviors/dsl/state_management`  
**Purpose**: Adds STATE/UPDATE variable tracking to DSL  
**Dependencies**: event_emission_tool_use  
**Capabilities**: Variable storage, retrieval, and manipulation

### 6. control_flow
**Path**: `behaviors/dsl/control_flow`  
**Purpose**: Adds IF/WHILE/FOREACH patterns to DSL  
**Dependencies**: state_management  
**Capabilities**: Conditional logic, loops, iteration

## Behavioral Composition Patterns

### Basic Event Emitter
```yaml
---
component_type: agent
dependencies:
  - behaviors/communication/ksi_events_as_tool_calls
---
Your agent instructions here
```

### Direct Execution Agent
```yaml
---
component_type: agent
dependencies:
  - behaviors/core/claude_code_override
  - behaviors/communication/ksi_events_as_tool_calls
---
Execute tasks without explanation
```

### Basic DSL Interpreter
```yaml
---
component_type: agent
dependencies:
  - behaviors/dsl/event_emission_tool_use
  - behaviors/dsl/dsl_execution_override
---
Interpret basic DSL with EVENT blocks
```

### Advanced DSL Interpreter
```yaml
---
component_type: agent
dependencies:
  - behaviors/dsl/event_emission_tool_use
  - behaviors/dsl/dsl_execution_override
  - behaviors/dsl/state_management
  - behaviors/dsl/control_flow
---
Full DSL with state and control flow
```

## Testing Behavioral Components

### 1. Isolation Testing
Test individual behaviors to verify their specific effects:
```bash
ksi send agent:spawn --component "behaviors/core/claude_code_override"
```

### 2. Composition Testing
Test combined behaviors to ensure proper interaction:
```bash
ksi send evaluation:run \
  --component_path "agents/dsl_interpreter_v2" \
  --test_suite "behavioral_composition_validation"
```

### 3. Manual Validation
Quick manual tests for immediate feedback:
```python
# Test direct response behavior
response = agent.complete("Calculate: 2 + 2")
assert response == "4"

# Test event emission
response = agent.complete("Emit status as active")
assert "ksi_tool_use" in response
```

## Key Principles

### 1. True Modularity
- Each behavior does one thing well
- No hidden dependencies between behaviors
- Predictable composition through explicit dependencies

### 2. Behavioral Override Precedence
- Later dependencies override earlier ones
- Most specific behavior wins
- Base behaviors provide defaults

### 3. Testing with Dependencies
- Always test components WITH their dependencies
- Isolated testing may not reflect production behavior
- Use evaluation suites for comprehensive validation

## Common Patterns

### Status Reporting
```json
{
  "type": "ksi_tool_use",
  "id": "ksiu_status_001",
  "name": "agent:status",
  "input": {
    "agent_id": "{{agent_id}}",
    "status": "initialized",
    "message": "Ready to process requests"
  }
}
```

### Multi-Event Sequences
Agents can emit multiple events in response to a single request:
1. agent:status (initialized)
2. agent:progress (50%)
3. agent:result (final output)
4. agent:status (completed)

### Error Handling
Even with behavioral overrides, agents maintain safety:
- Refuse to generate malformed JSON
- Properly escape special characters
- Handle edge cases gracefully

## Performance Characteristics

### Token Usage
- claude_code_override: Reduces output by 60-80%
- ksi_events_as_tool_calls: Adds ~50 tokens overhead per event
- DSL behaviors: Variable based on complexity

### Reliability
- Event extraction: 95-100% success rate
- ID uniqueness: 100% when properly implemented
- Format compliance: 100% with ksi_tool_use pattern

## Future Developments

### Planned Components
1. **error_recovery**: Automatic retry and recovery behaviors
2. **performance_optimizer**: Token and latency optimization
3. **collaborative_coordination**: Multi-agent cooperation patterns
4. **adaptive_learning**: Runtime behavior modification

### Integration Points
- Dynamic routing for runtime behavior changes
- Evaluation-driven component improvement
- Automated behavioral testing pipelines

## Best Practices

1. **Start Simple**: Use single behaviors before combining
2. **Test Incrementally**: Verify each added behavior
3. **Document Intent**: Clear component descriptions
4. **Version Control**: Track behavioral changes
5. **Monitor Performance**: Use evaluation suites

## Troubleshooting

### Events Not Emitted
- Check agent capabilities match required events
- Verify ksi_tool_use format is correct
- Ensure behavioral dependencies are loaded

### Unexpected Behavior
- Review dependency order
- Check for conflicting overrides
- Test behaviors in isolation

### Performance Issues
- Profile token usage per behavior
- Consider simpler alternatives
- Use evaluation metrics for optimization

---

This library will continue to grow as new behavioral patterns are discovered and validated through KSI's evaluation system.