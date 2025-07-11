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

## Enhanced Pattern Format

Orchestration patterns are YAML compositions with rich metadata and DSL:

```yaml
name: adaptive_tournament_v2
type: orchestration
version: 2.1.0
extends: tournament_basic  # Inherit from parent patterns

# Lineage tracking for evolution
lineage:
  parent: tournament_basic@2.0.0
  fork_date: "2025-07-10T15:30:00Z"
  fork_reason: "Improve participant matching"
  improvements:
    - "Added adaptive matching based on variance"
    - "Implemented timeout recovery"

# DSL for orchestrator interpretation (not parsed by KSI)
orchestration_logic:
  description: |
    Natural language strategy for orchestrator agents to follow.
    Mix natural language with structured patterns.
  
  strategy: |
    WHEN starting_tournament:
      ANALYZE participant_capabilities
      IF variance(abilities) > 0.3:
        EMIT "orchestration:configure" WITH {mode: "elimination"}
      ELSE:
        EMIT "orchestration:configure" WITH {mode: "round_robin"}
    
    DURING each_round:
      MONITOR metrics: timeout_rate, score_variance
      
      IF timeout_rate > 30%:
        EMIT "evaluation:adjust_complexity" WITH {reduce: "20%"}
        EMIT "monitoring:alert" WITH {issue: "high_timeouts"}
        
      IF all_scores_similar:
        EMIT "evaluation:add_discriminators"
        TRACK decision: "added_discrimination" WITH confidence: 0.85
    
    AFTER completion:
      CALCULATE performance_metrics
      IF improved_over_baseline:
        EMIT "composition:track_decision" WITH full_context
        CONSIDER "composition:fork" IF confidence > 0.9

# Performance tracking for evolution
performance:
  runs: 47
  avg_score: 0.82
  success_rate: 0.93
  improvements_over_parent: "+21.7%"

# Learnings for pattern selection
learnings:
  - insight: "Swiss pairing optimal for 5-10 participants"
    confidence: 0.85
    evidence: "runs:[7,9,11,14]"
    discovered_by: "orchestrator_7f3e"

# Transformers for pattern vocabulary
transformers:
  - source: "tournament:configure"
    target: "orchestration:send"
    mapping:
      to: "all"
      message.type: "{{mode}}_setup"
  
  - source: "tournament:analyze_variance"
    target: "completion:async"
    async: true
    mapping:
      prompt: "Analyze participant variance: {{capabilities}}"
    response_route:
      from: "completion:result"
      to: "tournament:variance_result"
```

Patterns include:
- **Metadata**: Version, lineage, performance metrics
- **DSL Strategy**: Natural language mixed with structured operations
- **Learnings**: Documented insights with confidence scores
- **Decision History**: Tracked adaptations and outcomes
- **Transformers**: Event vocabulary mapping for pattern-specific events

## Pattern Evolution Workflow

### 1. Discovery and Selection

Orchestrators discover patterns using composition system:

```python
# Find relevant patterns
patterns = await emit("event:emit", {
    "event": "composition:discover",
    "data": {
        "type": "orchestration",
        "metadata_filter": {
            "tags": ["tournament"],
            "performance.avg_score": {">": 0.7}
        }
    }
})

# Select best pattern for task
best = await emit("event:emit", {
    "event": "composition:select",
    "data": {
        "task": "Evaluate 15 prompts competitively",
        "requirements": {"timeout_handling": true}
    }
})
```

### 2. DSL Interpretation

Orchestrators read and implement DSL strategies:

```python
# Orchestrator interprets DSL action
if timeout_rate > 0.3:  # From monitoring
    # Implement DSL: EMIT "evaluation:adjust_complexity"
    await emit("event:emit", {
        "event": "evaluation:adjust_complexity",
        "data": {"reduce": "20%"}
    })
    
    # Track the decision
    await emit("event:emit", {
        "event": "composition:track_decision",
        "data": {
            "pattern": pattern_name,
            "decision": "reduced_complexity",
            "context": {"timeout_rate": timeout_rate},
            "outcome": "pending"
        }
    })
```

### 3. Pattern Forking

When orchestrators discover improvements:

```python
# After successful run with adaptations
if performance > baseline * 1.15:  # 15% improvement
    await emit("event:emit", {
        "event": "composition:fork",
        "data": {
            "parent": current_pattern,
            "name": f"{current_pattern}_improved",
            "reason": "Consistent 15%+ performance improvement",
            "modifications": {
                "orchestration_logic.strategy": new_strategy
            }
        }
    })
```

### 4. Decision Tracking

Decisions are tracked in two ways:

1. **High-level learnings** in pattern metadata:
```yaml
learnings:
  - insight: "Discovered optimal timeout is 2x avg response time"
    confidence: 0.92
```

2. **Detailed decisions** in `<pattern>_decisions.yaml`:
```yaml
- timestamp: "2025-07-10T16:30:00Z"
  agent_id: "orchestrator_7f3e"
  decision: "increased_timeout"
  context: {avg_response: 45, current_timeout: 60}
  outcome: "reduced_timeout_rate"
  confidence: 0.87
```

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
**Status**: Implementation in progress - blocked on composition system redesign

Transitioning from hardcoded primitives to dynamic pattern-loaded transformers:

**Previous Approach** (replaced):
- Hardcoded orchestration primitives in Python
- Fixed set of 7 primitives in `orchestration_primitives.py`

**New Approach** (partially implemented):
- Patterns define transformers in YAML
- Async transformers with token-based responses  
- No Python modules required for patterns
- Complete vocabulary defined by each pattern

**Current State**:
- ✅ `ksi_daemon/transformer/transformer_service.py` - Pattern-level transformer management created
- ✅ `ksi_daemon/orchestration/orchestration_service.py` - Updated to use transformer service
- ❌ **BLOCKED**: Composition system strips `transformers` section from patterns
- 📋 **NEXT**: Implement `docs/GENERIC_COMPOSITION_SYSTEM_REDESIGN.md` to unblock

The transformer service is loaded but cannot function until the composition system preserves all YAML sections as outlined in the redesign plan.

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