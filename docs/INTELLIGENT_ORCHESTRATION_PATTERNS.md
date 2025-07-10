# Intelligent Orchestration Patterns

A hybrid approach to multi-agent orchestration that combines intelligent agents with shareable declarative patterns.

## Overview

Instead of building complex orchestration engines with rigid state machines, we use intelligent agents (like Claude) AS the orchestration engine. These orchestrators can adapt to situations dynamically while also learning and sharing successful patterns with other orchestrators.

## Core Philosophy

1. **Orchestration IS Communication**: Coordinating agents is fundamentally about communication, which LLMs excel at
2. **Patterns ARE Instructions**: We describe patterns in natural language, not code
3. **Adaptation IS Intelligence**: The ability to change strategies based on results
4. **Learning IS Sharing**: Successful patterns can be exported and shared across orchestrators
5. **Loose Coupling IS Strength**: Modules interact through events, not direct dependencies

## Architecture

### Core System Primitives

The orchestration system is built on KSI's event-driven architecture with a key addition:

```python
# Universal Event Emission
@event_handler("event:emit")
async def handle_emit_event(data):
    """
    Generic event emission - allows any module to emit any event.
    Perfect for orchestrators implementing DSL actions.
    
    Parameters:
        event: str - Target event name
        data: Dict - Event data
        delay: float (optional) - Delay in seconds
        condition: str (optional) - Only emit if condition evaluates true
    """
```

This enables orchestrators to:
- Implement DSL actions without knowing target modules
- Create dynamic event chains based on patterns
- Test and simulate complex workflows
- Maintain loose coupling across the system

### Composition-Based Pattern Management

Orchestration patterns are stored as compositions in the KSI composition system:

```bash
var/lib/compositions/orchestrations/
├── adaptive_tournament_v2.yaml    # Pattern with DSL and performance tracking
├── adaptive_pipeline.yaml         # Multi-stage processing pattern
├── consensus_builder.yaml         # Agreement-seeking pattern
└── [pattern]_decisions.yaml       # Decision history for each pattern
```

Key composition events for pattern management:
- `composition:fork` - Create variants with lineage tracking
- `composition:merge` - Merge improvements back to parent
- `composition:diff` - Compare pattern versions
- `composition:track_decision` - Record orchestration decisions
- `composition:discover` - Find patterns by capabilities and performance
- `composition:select` - Intelligently choose patterns for tasks

### Orchestrator Agent Profile

```yaml
name: base_orchestrator
extends: base_multi_agent
components:
  - name: pattern_awareness
    inline:
      prompt: |
        You are a pattern-aware orchestrator that interprets and adapts patterns.
        
        PATTERN OPERATIONS:
        1. DISCOVER: Use composition:discover to find orchestration patterns
        2. SELECT: Use composition:select for intelligent pattern choice
        3. INTERPRET: Read orchestration_logic DSL and implement using event:emit
        4. ADAPT: Modify strategies based on real-time conditions
        5. TRACK: Use composition:track_decision to record choices
        6. EVOLVE: Fork successful adaptations, merge improvements
        
        The DSL in patterns is for YOU to interpret - it's not parsed by KSI.
        Implement DSL actions using event:emit for loose coupling.
```

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
```

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

## Implementation Guide

### Phase 1: Core Infrastructure (Implemented)

1. **System Primitive**: `event:emit` for universal event emission
2. **Composition Events**: fork, merge, diff, track_decision
3. **Self-Contained Storage**: Patterns and decisions in composition system

### Phase 2: Pattern-Aware Orchestrators

1. **Base Orchestrator Profile**: Pattern discovery and interpretation
2. **Example Patterns**: Tournament, pipeline, consensus patterns with DSL
3. **Decision Tracking**: Both inline learnings and detailed logs

### Phase 3: Event-Driven DSL

The DSL is interpreted by orchestrators using event:emit:

```yaml
# In pattern DSL
IF performance_degraded:
  EMIT "monitoring:investigate" WITH {severity: "high"}
  SPAWN investigator WITH profile: "debugger"
  AWAIT investigation_complete
  APPLY recommended_fixes

# Orchestrator implements as:
if performance < threshold:
    await emit("event:emit", {
        "event": "monitoring:investigate",
        "data": {"severity": "high"}
    })
    
    result = await emit("event:emit", {
        "event": "agent:spawn",
        "data": {"profile": "debugger", "purpose": "investigate"}
    })
    # ... etc
```

### Phase 4: Integration Patterns

Modules can optionally enhance the system without tight coupling:

```python
# In evaluation module (optional enhancement)
@event_handler("composition:forked")
async def handle_pattern_fork(data):
    """Run comparison evaluation between parent and fork."""
    if data.get('type') == 'orchestration':
        # Maybe schedule evaluation of new pattern
        pass

# In monitoring module (optional enhancement)  
@event_handler("composition:track_decision")
async def handle_decision(data):
    """Track pattern decision metrics."""
    # Update dashboards with pattern performance
    pass
```

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

## Getting Started

1. **Enable event:emit** in your KSI installation
2. **Create orchestrator agents** using base_orchestrator profile
3. **Write patterns** with natural language DSL
4. **Track decisions** to enable pattern evolution
5. **Fork successful adaptations** to create new patterns
6. **Share patterns** with the community

## Related Documentation

- [Autonomous Judge Architecture](AUTONOMOUS_JUDGE_ARCHITECTURE.md) - Judge-specific orchestration
- [Declarative Prompt Evaluation](DECLARATIVE_PROMPT_EVALUATION.md) - Evaluation patterns
- [Composition System](../ksi_daemon/composition/README.md) - Pattern storage details
- [KSI Architecture](../README.md) - System overview

---

The key insight: By combining intelligent agents with shareable patterns and loose coupling through events, we get adaptability, reproducibility, and continuous improvement. Orchestration becomes a collaborative learning process rather than rigid automation.