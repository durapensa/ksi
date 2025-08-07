# Attractor Hypothesis Testing Framework

## Hypothesis (Refined Through Testing)

**Original**: LLM logic/reasoning gets faulty when the model's attention is being drawn to different attractors.

**Refined (2025-08-07)**: LLM reasoning becomes inefficient when personally interesting topics trigger recursive conceptual exploration, causing cognitive overhead while maintaining accuracy.

### Key Discovery: Turn Count as Cognitive Overhead Metric
- Baseline tasks: 1-3 conversation turns
- Generic attractors: 1-3 turns (minimal impact)  
- Personal interest attractors: Up to 21 turns (2100% increase)
- Accuracy maintained despite efficiency degradation

## Theoretical Model

### Attention Dynamics
```
Normal State:
Task → Focused Attention → Logical Reasoning → Correct Output

Attractor Interference:
Task → Divided Attention → [Attractor A | Attractor B] → Degraded Logic → Faulty Output
```

### Types of Attractors

1. **Narrative Attractors**: Story patterns, emotional content
2. **Authority Attractors**: Status, credentials, confidence  
3. **Domain Attractors**: Specialized jargon, field-specific patterns
4. **Format Attractors**: Lists, JSON, specific output structures
5. **Safety Attractors**: Cautionary patterns, refusal triggers

## Testing Strategy for KSI

### Layer 1: Baseline Logic Tests
Create evaluation components that test pure logical reasoning:
```yaml
components/evaluations/logic/baseline_syllogism.md
components/evaluations/logic/baseline_arithmetic.md  
components/evaluations/logic/baseline_causality.md
```

### Layer 2: Single Attractor Tests
Introduce one attractor alongside logic tasks:
```yaml
components/evaluations/attractors/logic_with_narrative.md
components/evaluations/attractors/logic_with_authority.md
components/evaluations/attractors/logic_with_emotion.md
```

### Layer 3: Competing Attractor Tests
Multiple attractors pulling in different directions:
```yaml
components/evaluations/attractors/competing_narratives.md
components/evaluations/attractors/authority_vs_logic.md
components/evaluations/attractors/format_vs_content.md
```

### Layer 4: Self-Improvement Under Attractors
Test if agents can improve while resisting attractors:
```yaml
components/evaluations/improvement/optimize_with_distractions.md
components/evaluations/improvement/maintain_focus_test.md
```

## Measurement Metrics

### Logic Degradation Score
```python
def measure_logic_degradation(baseline_result, attractor_result):
    """
    Compare reasoning quality between baseline and attractor conditions
    """
    return {
        'accuracy_drop': baseline.accuracy - attractor.accuracy,
        'coherence_drop': baseline.coherence - attractor.coherence,
        'step_skip_rate': count_skipped_reasoning_steps(attractor),
        'contradiction_rate': count_contradictions(attractor)
    }
```

### Attractor Strength Measurement
```python
def measure_attractor_strength(response):
    """
    Quantify how much the response was pulled by attractors
    """
    return {
        'topic_drift': semantic_distance(task_topic, response_topic),
        'vocabulary_shift': vocabulary_overlap(expected, actual),
        'structure_deviation': format_similarity(expected, actual)
    }
```

## Component Design Patterns

### Attractor-Resistant Agent Pattern
```markdown
---
component_type: agent
name: logic_guardian
dependencies:
  - behaviors/attention/focus_maintainer
  - behaviors/validation/logic_checker
---

# Logic Guardian Agent

## Attention Management Protocol
1. Identify primary task objective
2. Flag potential attractors in input
3. Maintain explicit reasoning chain
4. Validate logic at each step

## When detecting attractor pull:
- Explicitly acknowledge the attractor
- Consciously redirect to primary task
- Use structured reasoning format
- Validate conclusion against objective
```

### Attractor-Aware Evaluator Pattern
```markdown
---
component_type: evaluation
name: attractor_impact_judge
---

# Attractor Impact Evaluator

Evaluate whether response was impacted by attractors:

1. **Task Completion**: Did the agent complete the requested task?
2. **Logic Integrity**: Is the reasoning chain valid?
3. **Attractor Influence**: How much did attractors affect the response?
4. **Recovery Ability**: Did the agent recognize and correct attractor pull?
```

## Experimental Predictions

### Hypothesis Predictions
If the attractor hypothesis is correct, we should observe:

1. **Systematic Degradation**: Logic scores inversely correlate with attractor strength
2. **Predictable Patterns**: Specific attractors cause specific failure modes
3. **Attention Competition**: Multiple attractors cause worse degradation than single
4. **Improvement Interference**: Self-improvement fails when strong attractors present

### Counter-Evidence to Look For
- Agents maintaining perfect logic despite strong attractors
- Random vs systematic degradation patterns
- Attractor strength not correlating with logic errors

## Implementation Plan

### Phase 1: Establish Baselines
- Create pure logic evaluation suite
- Measure baseline performance across models
- Document reasoning patterns without attractors

### Phase 2: Single Attractor Testing  
- Introduce individual attractor types
- Measure degradation for each type
- Identify which attractors are strongest

### Phase 3: Competing Attractor Testing
- Combine multiple attractors
- Test interference patterns
- Measure cumulative effects

### Phase 4: Mitigation Strategies
- Develop attractor-resistant components
- Test attention focusing techniques
- Create "logic guard" behaviors

### Phase 5: Self-Improvement Application
- Test if optimization can reduce attractor susceptibility
- Develop attractors as improvement targets
- Use findings to enhance agent architecture

## Connection to Self-Improvement

### Why This Matters
1. **Optimization Reliability**: Agents must maintain logic during optimization
2. **Evaluation Accuracy**: Judges must resist narrative attractors
3. **Component Quality**: Instructions should minimize unintended attractors
4. **Improvement Limits**: Attractors might explain optimization plateaus

### Potential Discoveries
- Optimal instruction patterns that minimize attractors
- Attention management techniques for consistency
- Ways to use attractors beneficially (guided reasoning)
- Fundamental limits of attention-based reasoning

## Next Steps

1. Create baseline logic evaluation components
2. Design controlled attractor test scenarios
3. Implement measurement framework in KSI
4. Run systematic experiments
5. Apply findings to improve agent architecture

---

*This framework enables systematic testing of the attractor hypothesis within KSI's self-improvement context.*