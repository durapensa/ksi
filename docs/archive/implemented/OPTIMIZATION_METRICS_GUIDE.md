# KSI Optimization Metrics Guide

## Overview

This guide documents the metrics system for KSI optimization, including lessons learned from DSPy integration and recommendations for effective metric design.

## Key Findings (2025-01)

### The Minimal Metric Problem

During Phase 2 integration testing, both MIPRO and SIMBA optimizations resulted in 0% improvement when using the default minimal metric. This revealed a critical insight:

**Simple metrics cannot capture the complexity of agent behavior optimization.**

The default metric in `ksi_optimize_component.py` uses basic heuristics:
- Word count scoring
- Keyword presence checks
- Structure indicators

These fail to evaluate what actually matters: **Does the agent with optimized instructions perform better on real tasks?**

## Metric Design Principles

### 1. Agent-in-the-Loop Evaluation

**Critical**: Metrics must evaluate actual agent outputs, not instruction text.

```python
# ❌ WRONG: Evaluating instruction text
def metric(instruction_text):
    return 1.0 if "json" in instruction_text else 0.0

# ✅ RIGHT: Evaluating agent behavior
async def metric(instruction, test_cases):
    agent = await spawn_agent_with_instruction(instruction)
    outputs = await run_test_cases(agent, test_cases)
    return evaluate_outputs(outputs)
```

### 2. Multi-Dimensional Evaluation

KSI optimizes for multiple objectives:

| Dimension | Description | Metric Type |
|-----------|-------------|-------------|
| **Instruction Following** | Does agent execute exactly what was requested? | Binary/Percentage |
| **Task Lock-In** | Does agent maintain focus without digression? | Stability Score |
| **Behavioral Consistency** | Are responses predictable and reliable? | Variance Metric |
| **Token Efficiency** | Minimal tokens while maintaining quality | Count + Quality |
| **Response Quality** | Accuracy, completeness, usefulness | LLM-as-Judge |

### 3. Comparative vs Absolute Metrics

Research shows LLMs excel at comparative judgments over absolute scoring:

```python
# ❌ LESS RELIABLE: Absolute scoring
score = judge.rate_quality(output, scale=1-10)

# ✅ MORE RELIABLE: Pairwise comparison
winner = judge.compare(output_a, output_b)
rankings = bradley_terry_model(comparisons)
```

## Implementation Patterns

### Pattern 1: Behavioral Test Suite Metrics

```python
class BehavioralMetric:
    def __init__(self, test_suite: str):
        self.test_suite = test_suite  # e.g., "behavioral_effectiveness"
    
    async def evaluate(self, instruction: str) -> float:
        # 1. Spawn agent with instruction
        agent_id = await spawn_test_agent(instruction)
        
        # 2. Run behavioral test suite
        results = await run_evaluation_suite(agent_id, self.test_suite)
        
        # 3. Aggregate scores
        return results["overall_score"]
```

### Pattern 2: Tournament-Based Ranking

```python
class TournamentMetric:
    def __init__(self, judge_component: str):
        self.judge = judge_component
    
    async def rank_candidates(self, candidates: List[str]) -> Dict[str, float]:
        # 1. Generate outputs for each candidate
        outputs = await parallel_map(generate_outputs, candidates)
        
        # 2. Sparse pairwise comparisons (2% sampling)
        comparisons = await run_sparse_tournament(outputs, self.judge)
        
        # 3. Convert to rankings
        return compute_elo_scores(comparisons)
```

### Pattern 3: Hybrid Quantitative-Qualitative

```python
class HybridMetric:
    def __init__(self, quantitative_weight: float = 0.4):
        self.quant_weight = quantitative_weight
        self.qual_weight = 1.0 - quantitative_weight
    
    async def evaluate(self, instruction: str) -> float:
        # Quantitative: measurable behaviors
        quant_score = await self.evaluate_quantitative(instruction)
        
        # Qualitative: LLM judge assessment
        qual_score = await self.evaluate_qualitative(instruction)
        
        return (self.quant_weight * quant_score + 
                self.qual_weight * qual_score)
```

## Practical Recommendations

### 1. Start with Behavioral Test Suites

Use existing evaluation infrastructure:
```bash
# Define test suite
ksi send evaluation:create_suite --name "optimization_tests" \
  --tests "instruction_following,task_completion,json_emission"

# Use in optimization
ksi send optimization:async --target "component" \
  --metric "behavioral_suite:optimization_tests"
```

### 2. Implement Comparative Evaluation Early

Even with simple comparisons:
```python
# Instead of absolute scoring
if output_a_tokens < output_b_tokens and quality_similar(a, b):
    return "a"  # Prefer more efficient
```

### 3. Track Multiple Metrics

Don't optimize for single dimension:
```yaml
metrics:
  primary: instruction_following  # Main optimization target
  constraints:
    - token_efficiency > 0.7     # Must maintain efficiency
    - safety_score > 0.9         # Must remain safe
  tracking:
    - response_quality           # Monitor but don't optimize
```

## Integration with DSPy

### Configuring Metrics for MIPRO

```python
# In optimization config
config = {
    "optimizer": "mipro",
    "metric": "components/metrics/behavioral_composite",
    "metric_config": {
        "test_suite": "instruction_optimization",
        "dimensions": ["following", "efficiency", "quality"],
        "weights": [0.5, 0.2, 0.3]
    }
}
```

### Configuring Metrics for SIMBA

```python
# SIMBA needs fast, incremental metrics
config = {
    "optimizer": "simba",
    "metric": "components/metrics/quick_behavioral",
    "metric_config": {
        "sample_size": 3,  # Fewer tests per iteration
        "cache_outputs": True  # Reuse previous evaluations
    }
}
```

## Common Pitfalls

### 1. Metric-Instruction Mismatch
**Problem**: Optimizing for metrics that don't match actual use
**Solution**: Design metrics that reflect production usage

### 2. Overfitting to Metrics
**Problem**: Instructions become hyper-specialized to metric
**Solution**: Use diverse test cases and rotation

### 3. Ignoring Compute Costs
**Problem**: Agent-in-the-loop evaluation is expensive
**Solution**: Implement caching, sampling, and early stopping

### 4. Single-Dimension Focus
**Problem**: Optimizing only for tokens loses quality
**Solution**: Multi-objective optimization with constraints

## Future Directions

### 1. Automated Metric Learning
Learn metrics from human preferences:
- Collect pairwise comparisons from users
- Train reward models on preferences
- Use learned metrics in optimization

### 2. Online Adaptation
Continuous improvement from production:
- Track actual usage patterns
- Update metrics based on outcomes
- SIMBA for runtime adaptation

### 3. Meta-Optimization
Optimize the optimization process:
- Which metrics lead to better agents?
- Which evaluation strategies converge faster?
- Co-evolve metrics with instructions

## Conclusion

Effective metrics are the foundation of successful optimization. The key insights:

1. **Evaluate behaviors, not text** - Agent-in-the-loop is essential
2. **Use comparative evaluation** - Pairwise > absolute scoring  
3. **Optimize holistically** - Multiple dimensions with constraints
4. **Start simple, iterate** - Basic behavioral tests first, sophistication later

The minimal metric problem discovered in Phase 2 demonstrates that optimization frameworks (MIPRO/SIMBA) work correctly - they just need meaningful metrics to optimize against.

## References

- `/docs/OPTIMIZATION_APPROACH.md` - Overall optimization philosophy
- `/docs/DECLARATIVE_PROMPT_EVALUATION.md` - Evaluation system design
- `/components/evaluations/` - Existing evaluation components
- `/var/lib/evaluations/test_suites/` - Behavioral test examples