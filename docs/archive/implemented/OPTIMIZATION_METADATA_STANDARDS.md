# KSI Component Optimization Metadata Standards

## Overview

This document defines the metadata standards for tracking component optimizations in KSI. These standards ensure that optimized components can be discovered, compared, and reused effectively using git features.

## Component Frontmatter Extensions

### Optimization Section

When a component has been optimized, it includes an `optimization` section in its frontmatter:

```yaml
---
version: 2.1.0
author: ksi_optimizer
optimization:
  optimizer: DSPy-MIPROv2
  timestamp: "2025-01-18T12:34:56Z"
  auto_mode: medium
  num_candidates: 10
  trainset_size: 50
  valset_size: 20
  parent_version: "b5ff552"  # Git commit of original
  improvement_score: 0.25    # 25% improvement
  metrics:
    cooperation_rate: 0.85
    decision_quality: 0.92
    token_efficiency: 0.78
---
```

### Performance Hints

For runtime optimization, components can include performance hints:

```yaml
performance:
  model_preference: claude-sonnet  # Optimized for this model
  expected_tokens: 150-300         # Typical token usage
  latency_category: fast           # fast/medium/slow
  parallel_safe: true              # Can run in parallel
```

## Git Conventions

### Branch Naming

Optimization experiments use structured branch names:
- Pattern: `optimization/{experiment-name}-{timestamp}`
- Example: `optimization/game-theory-mipro-20250118-143256`

### Tag Format

Successful optimizations are tagged for release:
- Pattern: `opt/{name}_v{version}`
- Example: `opt/negotiator_v1.2`

### Commit Message Format

Optimization commits follow a structured format:

```
Optimize {component} with {optimizer} (+{improvement}% improvement)

Optimizer: DSPy-MIPROv2
Original Score: 0.65
Optimized Score: 0.82
Improvement: 26.15%

Training Config:
- Auto mode: medium
- Candidates: 10
- Train/Val: 50/20
```

## Optimization Metadata Files

Each optimized component has an accompanying `.optimization.json` file:

```json
{
  "timestamp": "2025-01-18T12:34:56Z",
  "component": "personas/negotiator",
  "optimizer": "DSPy-MIPROv2",
  "original_score": 0.65,
  "optimized_score": 0.82,
  "improvement": 0.2615,
  "config": {
    "auto": "medium",
    "max_bootstrapped_demos": 4,
    "max_labeled_demos": 4,
    "num_candidates": 10
  },
  "training_data": {
    "trainset_size": 50,
    "valset_size": 20,
    "data_source": "orchestration_runs/game_theory_v2"
  },
  "metrics": {
    "cooperation_rate": 0.85,
    "decision_quality": 0.92,
    "token_efficiency": 0.78
  }
}
```

## Discovery Attributes

For git-based discovery, use `.gitattributes`:

```gitattributes
# Component optimization metadata
components/personas/*.md optimization=mipro performance=tested
components/agents/*.md optimization=pending model=sonnet
components/evaluations/*.md optimization=textgrad metrics=available

# Specific optimizations
components/personas/negotiator.md opt-score=0.82 opt-date=2025-01-18
components/agents/analyst.md opt-framework=dspy opt-improvement=0.26
```

## Integration with KSI Events

### Query Optimized Components

```bash
# Find all MIPROv2-optimized components
ksi send composition:query --filter '{"optimization.optimizer": "DSPy-MIPROv2"}'

# Find high-performing components
ksi send composition:query --filter '{"optimization.improvement_score": {"$gt": 0.2}}'

# Find components optimized for specific model
ksi send composition:query --filter '{"performance.model_preference": "claude-sonnet"}'
```

### Track Optimization History

```bash
# Get optimization history for a component
ksi send optimization:get_history --component "personas/negotiator"

# Compare versions
ksi send optimization:compare_versions \
  --component "personas/negotiator" \
  --version1 "opt/negotiator_v1.0" \
  --version2 "opt/negotiator_v1.2"
```

## Best Practices

### 1. Always Track Baselines
- Keep original component performance metrics
- Document what metrics were used for optimization
- Preserve parent version references

### 2. Reproducible Optimizations
- Store training/validation data references
- Document random seeds and config
- Tag both code AND data versions

### 3. Model-Specific Branches
- Use branches for model-specific optimizations
- Merge successful optimizations with clear documentation
- Keep experimental branches for reference

### 4. Semantic Versioning for Optimizations
- Major: Fundamental approach changes
- Minor: Significant performance improvements (>20%)
- Patch: Minor tweaks and adjustments (<20%)

### 5. Optimization Provenance
- Link optimizations to orchestration runs
- Reference evaluation components used
- Document human feedback incorporated

## Example Workflow

```bash
# 1. Start optimization experiment
ksi send optimization:start_experiment \
  --name "game-theory-negotiation" \
  --targets '["personas/negotiator", "personas/mediator"]' \
  --optimizer "mipro"

# 2. Run optimization with training data
ksi send optimization:run_component_optimization \
  --experiment-id "exp_123" \
  --component "personas/negotiator" \
  --trainset '@game_theory_training_data.json'

# 3. Evaluate results
ksi send optimization:evaluate_component \
  --component "personas/negotiator" \
  --metric "cooperation_rate"

# 4. Tag successful optimization
ksi send optimization:finalize_experiment \
  --experiment-id "exp_123" \
  --action "tag" \
  --tag-name "negotiator_v1.2"

# 5. Share via git
git push origin opt/negotiator_v1.2
```

## Future Extensions

### Optimization Marketplace
- Components could include licensing metadata
- Performance guarantees and SLAs
- Cost/benefit analysis for token usage

### Automated Optimization Pipelines
- CI/CD integration for continuous optimization
- A/B testing infrastructure
- Automatic rollback on performance regression

### Cross-Repository Federation
- Import optimized components from other repositories
- Standardized performance benchmarks
- Community-driven optimization challenges