# Intelligent Orchestration Patterns

A hybrid approach to multi-agent orchestration combining intelligent agents with shareable declarative patterns.

## Overview

Intelligent agents (like Claude) act as orchestration engines that adapt dynamically while learning and sharing successful patterns with other orchestrators.

## Core Philosophy

1. **Orchestration IS Communication** - LLMs excel at agent coordination
2. **Patterns ARE Instructions** - Natural language strategies, not rigid code
3. **Adaptation IS Intelligence** - Dynamic strategy changes based on results
4. **Learning IS Sharing** - Successful patterns evolve and spread
5. **Loose Coupling IS Strength** - Event-driven architecture enables flexibility

## Architecture

### Core Components

1. **Universal Event Emission** (`event:emit`) - Enables DSL implementation without tight coupling
2. **Pattern Evolution System** - Fork/merge/diff operations with lineage tracking  
3. **Orchestration Primitives** - Minimal set of powerful coordination tools
4. **Event Transformers** - Generic system for event transformation without duplication

### Pattern Management

Orchestration patterns stored in `var/lib/compositions/orchestrations/` with decision tracking in `*_decisions.yaml` files.

**Pattern Operations:**
- `composition:fork/merge/diff` - Evolution with lineage
- `composition:track_decision` - Learning from experience
- `composition:discover/select` - Intelligent pattern choice

**Base Orchestrator Profile:**
- Extends `base_multi_agent` with pattern awareness
- Interprets natural language DSL via `event:emit`
- Tracks decisions for continuous improvement

## Pattern Format

Orchestration patterns include:
- **Metadata**: Version, lineage, performance metrics
- **DSL Strategy**: Natural language mixed with structured operations
- **Learnings**: Documented insights with confidence scores
- **Decision History**: Tracked adaptations and outcomes

## Pattern Evolution Workflow

1. **Discovery**: Find patterns via `composition:discover` with performance filters
2. **Selection**: Choose best pattern via `composition:select` based on task requirements
3. **Interpretation**: Execute DSL strategies using `event:emit`
4. **Tracking**: Record decisions and outcomes via `composition:track_decision`
5. **Evolution**: Fork successful adaptations when performance improves
6. **Learning**: Document insights in pattern metadata and decision logs

## Implementation Status

### ✅ Phase 1: Core Infrastructure
- Universal event emission via `event:emit`
- Pattern evolution events: fork, merge, diff, track_decision
- Self-contained pattern storage with decision tracking

### ✅ Phase 2: Pattern-Aware Orchestrators
- Base orchestrator profile with pattern operations
- Example patterns: adaptive_tournament_v2, distributed_analysis
- Dual decision tracking: inline learnings + detailed logs

### 🔄 Phase 3: From Primitives to Pattern Transformers
Transitioning from hardcoded primitives to dynamic pattern-loaded transformers:

**Previous Approach** (being replaced):
- Hardcoded orchestration primitives in Python
- Fixed set of 7 primitives in `orchestration_primitives.py`

**New Approach** (dynamic transformers):
- Patterns define transformers in YAML
- Async transformers with token-based responses
- No Python modules required for patterns
- Complete vocabulary defined by each pattern

#### orchestration:aggregate

A powerful primitive for aggregating data from multiple agents with various methods:
- **vote**: Majority, plurality, ranked choice voting
- **statistical**: Mean, median, trimmed mean with confidence intervals
- **consensus**: Weighted averaging based on reputation/confidence
- **custom**: User-provided aggregation functions

Supports grouping, filtering, and flexible data extraction from complex responses.

#### Design Philosophy

1. **Parameters over Primitives**: One flexible primitive with rich parameters beats 5 specific ones
2. **Composition over Prescription**: Orchestrators build complex behaviors from simple parts
3. **Context over Control**: Rich metadata and context, not rigid workflows
4. **General over Specific**: "track anything" instead of track_metrics, track_decisions, etc.

#### Orchestration Context

All primitives maintain orchestration context with pattern, orchestrator_id, execution_id, and metadata for tracking and coordination.

### Event-Driven DSL

The DSL is interpreted by orchestrators using two methods:

1. **Direct Event Emission**: Orchestrators can output JSON events in their responses
2. **event:emit**: Explicit event emission for complex workflows

#### Agent Event Emission

Orchestrator agents can emit events by including JSON objects in their responses:

```json
{"event": "composition:get", "data": {"name": "tournament_orchestration_v1"}}
{"event": "router:register_transformer", "data": {"transformer": {...}}}
```

The completion service automatically:
- Extracts JSON objects with an 'event' field
- Emits them asynchronously in the background
- Adds metadata (`_agent_id`, `_extracted_from_response`)
- Continues processing without blocking

This enables orchestrators to coordinate complex workflows without needing tools or special permissions.

### Dynamic Pattern-Loaded Transformers

Patterns can define their own event transformers in YAML, enabling vocabulary mapping without Python code:

```yaml
transformers:
  # Simple synchronous transformation
  - source: "tournament:start"
    target: "orchestration:send"
    mapping:
      to: "all"
      message.type: "tournament:registration_open"
  
  # Async transformation with response routing
  - source: "tournament:evaluate_batch"
    target: "completion:async"
    async: true
    mapping:
      prompt: "Evaluate: {{matches}}"
    response_route:
      from: "completion:result"
      to: "tournament:batch_evaluated"
      filter: "request_id == {{transform_id}}"
  
  # Conditional transformation
  - source: "tournament:result"
    target: "orchestration:track"
    condition: "score > threshold"
    mapping:
      type: "high_performer"
```

#### Async Transformer Flow

1. **Request**: Pattern event → Transformer → Target event
2. **Token Return**: `{transform_id: "uuid", status: "queued"}`
3. **Response**: Result event with transform_id → Response routing
4. **Pattern Event**: Routed to pattern-specific response event

This enables patterns to define their complete vocabulary and async workflows without requiring Python modules.

### Integration Patterns

Modules can optionally enhance the system without tight coupling. For example, evaluation modules might listen for pattern forks to run comparisons, or monitoring modules might track decision metrics.

## Benefits of This Architecture

### Loose Coupling
- Modules don't import each other
- Orchestrators use event:emit for all coordination
- Patterns work regardless of which modules are loaded

### Self-Contained Evolution
- All pattern data stored in composition files
- Decision history tracked alongside patterns
- No external dependencies for pattern management

### Natural for LLMs
- DSL is interpretive, not prescriptive
- Orchestrators understand intent, not just syntax
- Patterns described in natural language

### Continuous Improvement
- Every run can improve patterns
- Successful adaptations become new patterns
- Learning is preserved and shareable

## Future Directions

### Pattern Federation
- Pattern registries for sharing across KSI networks
- Reputation systems for pattern authors
- Automated pattern translation between contexts

### Advanced DSL Features
- Conditional imports: `IF complex_task: INCLUDE advanced_strategies`
- Pattern composition: `COMBINE tournament WITH pipeline`
- Meta-patterns: Patterns that evolve other patterns

### Pattern Analytics
- Automated A/B testing of pattern variants
- Performance prediction based on task characteristics
- Pattern recommendation engines

## Primitive Composition Patterns

### Common Patterns

1. **Distributed Work**: Spawn workers, intelligently route tasks, wait with partial tolerance
2. **Consensus Building**: Spawn evaluators, coordinate voting, aggregate results
3. **Cascading Analysis**: Quick analysis first, deep dive on anomalies
4. **Adaptive Pipeline**: Multi-stage processing with failure handling

### Best Practices

1. **Context Preservation**: Use consistent execution_id throughout orchestration
2. **Graceful Degradation**: Design for partial failures with fallback strategies
3. **Decision Documentation**: Track key decisions for pattern learning
4. **Efficient Coordination**: Choose appropriate synchronization types
5. **Smart Targeting**: Use criteria-based targeting to reduce overhead

## Event Router Enhancement

### Generic Event Transformation System
A powerful system enabling both static and dynamic event transformers:

#### Static Transformers (Python)
```python
# Registered at import time via decorator
@event_transformer("source:event", target="target:event")
async def transform_something(data: Dict[str, Any]) -> Dict[str, Any]:
    return transformed_data
```

#### Dynamic Transformers (YAML)
```yaml
# Loaded from patterns at runtime
transformers:
  - source: "pattern:event"
    target: "system:event"
    async: true  # Optional async with token pattern
    mapping:
      field1: "{{source.field}}"
      field2: "static_value"
    response_route:  # For async transformers
      from: "system:response"
      to: "pattern:response"
```

**Benefits**:
- **No duplicate events**: Transformers convert events before emission
- **Pattern vocabulary**: Patterns define their own event mappings
- **Async transformations**: Token-based async operations with response routing
- **No Python required**: Complete patterns in YAML with transformers
- **Dynamic loading**: Transformers loaded/unloaded with patterns
- **Composability**: Transformers can chain and condition on data

**Implementation Features**:
1. **Dynamic Registration**: `router.register_transformer_from_yaml(transformer_def)`
2. **Async Support**: Token-based async transformers with response routing
3. **Pattern Loading**: Transformers defined in pattern YAML, loaded at runtime
4. **Conditional Logic**: Transformers can include conditions and filters
5. **Template Support**: Jinja2-style templates for field mapping
6. **Response Correlation**: Automatic correlation of async responses

**Pattern-Defined Transformers**:
```yaml
# In pattern YAML - no Python needed!
transformers:
  # Vocabulary mapping
  - source: "pattern:analyze"
    target: "agent:process"
    mapping:
      task: "analysis"
      data: "{{input}}"
  
  # Async with completion pattern
  - source: "pattern:complex_task"
    target: "completion:async"
    async: true
    mapping:
      prompt: "{{task_description}}"
    response_route:
      from: "completion:result"
      to: "pattern:task_complete"
  
  # Conditional routing
  - source: "pattern:route"
    target: "orchestration:send"
    condition: "priority == 'high'"
    mapping:
      to: {role: "priority_handler"}
```

**Impact on Orchestration**:
- Patterns define complete vocabulary in YAML
- No hardcoded orchestration primitives needed
- Async operations handled elegantly with tokens
- Patterns are truly self-contained
- Dynamic loading/unloading with patterns

## Getting Started

1. **Create orchestrator agents** using base_orchestrator profile
2. **Agent emits events** by outputting JSON in responses
3. **Write patterns** with natural language DSL and transformers
4. **Define transformers** in pattern YAML for vocabulary mapping
5. **Track decisions** to enable pattern evolution
6. **Fork successful adaptations** to create new patterns
7. **Share patterns** with the community

## Related Documentation

- [Autonomous Judge Architecture](AUTONOMOUS_JUDGE_ARCHITECTURE.md) - Judge-specific orchestration
- [Declarative Prompt Evaluation](DECLARATIVE_PROMPT_EVALUATION.md) - Evaluation patterns
- [Composition System](../ksi_daemon/composition/README.md) - Pattern storage details
- [KSI Architecture](../README.md) - System overview

---

The key insight: By combining intelligent agents with shareable patterns and loose coupling through events, we get adaptability, reproducibility, and continuous improvement. Orchestration becomes a collaborative learning process rather than rigid automation.