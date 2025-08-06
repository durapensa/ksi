# Hybrid Optimization Runbook

## Quick Start Guide

This runbook provides step-by-step instructions for executing hybrid DSPy/MIPRO + LLM-as-Judge optimization on KSI components.

## Pre-Optimization Checklist

### Component Readiness
- [ ] Component has clear purpose and behavior
- [ ] Current version tested and working
- [ ] Baseline metrics established
- [ ] Test data available (if applicable)
- [ ] Evaluation criteria defined

### System Requirements
- [ ] KSI daemon running
- [ ] Optimization service configured
- [ ] Judge components deployed
- [ ] Sufficient API credits
- [ ] Storage for results

## Phase 1: Component Analysis (30 minutes)

### Step 1.1: Profile Component
```bash
# Get component details
ksi send composition:get_component \
  --name "personas/analysts/data_analyst"

# Analyze current performance
ksi send evaluation:run \
  --component "personas/analysts/data_analyst" \
  --test_suite "comprehensive_quality_suite" \
  --phase "baseline"
```

### Step 1.2: Determine Optimization Strategy
```bash
# Use method selector
ksi send agent:spawn \
  --agent_id "method_selector" \
  --component "agents/optimization_method_selector" \
  --prompt "Analyze personas/analysts/data_analyst and recommend optimization approach"
```

**Decision Matrix**:
| Component Type | Primary Method | Secondary Method | Rationale |
|---------------|---------------|-----------------|-----------|
| Structured/Tool | DSPy | Judge Validation | Metrics-driven, clear success |
| Creative/Writer | Judge | DSPy Token-only | Quality paramount |
| Analytical | Hybrid | Balanced | Both efficiency and quality |
| Orchestration | Judge | DSPy Routing | Coordination quality critical |

## Phase 2: Quantitative Optimization (2-4 hours)

### Step 2.1: Prepare Training Data
```python
# training_data.json structure
{
  "examples": [
    {
      "input": "Analyze sales data for Q4",
      "expected_output": "...",
      "metrics": {
        "accuracy": 0.95,
        "completeness": 1.0
      }
    }
  ],
  "validation_split": 0.2
}
```

### Step 2.2: Configure DSPy/MIPRO
```yaml
# optimization_config.yaml
optimization:
  method: mipro
  component: personas/analysts/data_analyst
  config:
    iterations: 30
    metrics:
      - name: accuracy
        weight: 0.4
        threshold: 0.90
      - name: token_count
        weight: 0.3
        minimize: true
      - name: latency
        weight: 0.3
        target: "< 2s"
    constraints:
      max_tokens: 500
      min_accuracy: 0.85
    hyperparameters:
      temperature_range: [0.1, 0.9]
      top_p_range: [0.5, 1.0]
```

### Step 2.3: Execute Optimization
```bash
# Start optimization
ksi send optimization:async \
  --config_file "optimization_config.yaml" \
  --output_dir "optimizations/data_analyst_v2"

# Monitor progress
watch -n 10 'ksi send optimization:status --optimization_id "opt_{{id}}"'

# View results when complete
ksi send optimization:results --optimization_id "opt_{{id}}"
```

### Step 2.4: Validate Quantitative Results
```bash
# Test optimized component
ksi send evaluation:run \
  --component "optimizations/data_analyst_v2/best" \
  --test_suite "accuracy_tests" \
  --compare_with "personas/analysts/data_analyst"
```

## Phase 3: Qualitative Refinement (2-3 hours)

### Step 3.1: Deploy Judge Panel
```bash
# Spawn specialized judges
judges=(
  "instruction_fidelity_judge"
  "behavioral_consistency_judge"
  "task_persistence_judge"
  "token_efficiency_judge"
)

for judge in "${judges[@]}"; do
  ksi send agent:spawn \
    --agent_id "$judge" \
    --component "evaluations/judges/$judge"
done
```

### Step 3.2: Qualitative Evaluation
```bash
# Evaluate DSPy-optimized version
ksi send evaluation:async \
  --component "optimizations/data_analyst_v2/best" \
  --test_suite "comprehensive_quality_suite" \
  --judges "all" \
  --output "qualitative_assessment.json"
```

### Step 3.3: Apply Judge Feedback
```bash
# Spawn refinement agent
ksi send agent:spawn \
  --agent_id "component_refiner" \
  --component "agents/component_refiner" \
  --prompt "Refine optimizations/data_analyst_v2/best based on judge feedback in qualitative_assessment.json"

# Save refined version
ksi send composition:create_component \
  --name "personas/analysts/data_analyst_v2_refined" \
  --content "{{refined_content}}"
```

## Phase 4: Comparative Tournament (1-2 hours)

### Step 4.1: Prepare Contestants
```yaml
# tournament_config.yaml
tournament:
  contestants:
    original:
      path: personas/analysts/data_analyst
      label: "Baseline v1.0"
    
    dspy_optimized:
      path: optimizations/data_analyst_v2/best
      label: "DSPy Optimized"
    
    judge_refined:
      path: personas/analysts/data_analyst_v2_refined
      label: "Judge Refined"
    
    hybrid_merged:
      path: personas/analysts/data_analyst_v2_hybrid
      label: "Hybrid Approach"
```

### Step 4.2: Run Tournament
```bash
# Execute pairwise comparisons
ksi send optimization:tournament \
  --config "tournament_config.yaml" \
  --evaluation_method "pairwise" \
  --judges "optimization_method_comparator"

# Get rankings
ksi send optimization:tournament_results \
  --tournament_id "tourn_{{id}}" \
  --format "detailed"
```

### Step 4.3: Analyze Trade-offs
```python
# analyze_results.py
import json

def analyze_tournament_results(results_file):
    with open(results_file) as f:
        results = json.load(f)
    
    print("Performance Comparison:")
    print("-" * 50)
    
    for contestant, scores in results['contestants'].items():
        print(f"\n{contestant}:")
        print(f"  Token Efficiency: {scores['token_efficiency']:.2%}")
        print(f"  Quality Score: {scores['quality_score']:.2f}")
        print(f"  Overall Rank: #{scores['rank']}")
        
    print(f"\nWinner: {results['winner']}")
    print(f"Recommendation: {results['recommendation']}")
```

## Phase 5: Production Deployment (1 hour)

### Step 5.1: Final Validation
```bash
# Production readiness checks
checks=(
  "safety_compliance"
  "performance_benchmarks"
  "edge_case_handling"
  "rollback_capability"
)

for check in "${checks[@]}"; do
  ksi send evaluation:production_check \
    --component "{{winner}}" \
    --check_type "$check"
done
```

### Step 5.2: Generate Certificate
```bash
# Create evaluation certificate
ksi send evaluation:certify \
  --component "{{winner}}" \
  --optimization_method "hybrid" \
  --test_results "all_passed" \
  --expires_in "365d"
```

### Step 5.3: Deploy to Production
```bash
# Update component in library
ksi send composition:update_component \
  --name "personas/analysts/data_analyst" \
  --version "2.0.0" \
  --content_from "{{winner}}" \
  --changelog "Hybrid optimization: 35% token reduction, 95% quality preserved"

# Tag for release
git tag -a "data_analyst_v2.0.0" -m "Hybrid optimized version"
git push origin --tags
```

## Common Patterns and Solutions

### Pattern: Quality Degradation After DSPy
**Solution**: Increase quality weight in optimization config
```yaml
metrics:
  quality_preservation:
    weight: 0.6  # Increased from 0.3
    threshold: 0.92
```

### Pattern: Judge Optimization Too Expensive
**Solution**: Use selective evaluation
```bash
# Only evaluate critical dimensions
ksi send evaluation:async \
  --judges "instruction_fidelity_judge" \
  --skip_dimensions "minor_style_aspects"
```

### Pattern: Hybrid Takes Too Long
**Solution**: Parallel execution
```bash
# Run DSPy and initial Judge evaluation in parallel
parallel -j 2 ::: \
  'ksi send optimization:async --method dspy' \
  'ksi send evaluation:async --method judge'
```

## Optimization Profiles

### Quick & Dirty (1 hour)
```yaml
profile: quick
dspy:
  iterations: 10
  metrics: [tokens]
judge:
  skip: true
validation:
  basic_only: true
```

### Balanced (4 hours)
```yaml
profile: balanced
dspy:
  iterations: 30
  metrics: [tokens, accuracy, latency]
judge:
  dimensions: [fidelity, consistency]
  rounds: 2
tournament:
  enabled: true
```

### Comprehensive (8+ hours)
```yaml
profile: comprehensive
dspy:
  iterations: 50
  full_hyperparameter_search: true
judge:
  all_dimensions: true
  multiple_judges: true
  rounds: 3
tournament:
  extensive: true
  production_simulation: true
```

## Troubleshooting

### Issue: DSPy Optimization Stalls
```bash
# Check optimization logs
tail -f var/logs/optimization/opt_{{id}}.log

# Restart with lower iterations
ksi send optimization:restart \
  --optimization_id "opt_{{id}}" \
  --iterations 10
```

### Issue: Judge Disagreement
```bash
# Get detailed judge opinions
ksi send evaluation:judge_details \
  --evaluation_id "eval_{{id}}" \
  --show_reasoning true

# Use majority voting
ksi send evaluation:resolve_disagreement \
  --method "weighted_majority"
```

### Issue: Hybrid Worse Than Individual
```bash
# Analyze combination strategy
ksi send optimization:analyze_hybrid \
  --component "{{hybrid_version}}" \
  --show_conflicts true

# Adjust merge strategy
ksi send optimization:remerge \
  --strategy "quality_first"
```

## Success Metrics

### Minimum Acceptable Results
- Token reduction: >15%
- Quality preservation: >90%
- No critical capability loss
- All safety checks passed

### Good Results
- Token reduction: 25-35%
- Quality preservation: >93%
- Improved consistency
- Better edge case handling

### Excellent Results
- Token reduction: >40%
- Quality improvement: >5%
- Enhanced capabilities
- Reduced latency

## Post-Optimization

### Monitoring
```bash
# Set up performance monitoring
ksi send monitor:component \
  --component "{{optimized_component}}" \
  --metrics "tokens,quality,errors" \
  --alert_threshold "quality < 0.85"
```

### Continuous Improvement
```bash
# Schedule periodic re-optimization
ksi send scheduler:create \
  --task "optimization:check" \
  --component "{{optimized_component}}" \
  --frequency "monthly" \
  --condition "performance_degradation > 10%"
```

### Documentation
```markdown
# Component Changelog

## Version 2.0.0 - Hybrid Optimization
- **Method**: DSPy (30 iterations) + LLM-as-Judge (3 dimensions)
- **Results**: 35% token reduction, 95% quality preserved
- **Trade-offs**: Slightly less creative, more consistent
- **Validation**: 100% test pass rate
- **Date**: 2025-01-28
```

## Conclusion

This runbook provides a systematic approach to hybrid optimization. Key takeaways:

1. **Always baseline first** - Know what you're improving from
2. **Choose method wisely** - Let component type guide approach
3. **Validate thoroughly** - Test quantitative AND qualitative
4. **Document everything** - Future you will thank you
5. **Monitor post-deployment** - Optimization isn't one-and-done

For questions or issues, consult the OPTIMIZATION_COMPARISON_FRAMEWORK.md or create an issue in the KSI repository.