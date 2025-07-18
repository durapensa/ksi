# KSI Optimization Approach

## Philosophy

KSI takes a minimal, composable approach to optimization:

1. **Orchestration does coordination** - The existing orchestration system handles agent coordination, iteration, and state tracking
2. **Evaluation does metrics** - The evaluation system handles scoring and metric calculation
3. **Optimization provides utilities** - The optimization module just provides framework integration (DSPy, etc.)

## How It Works

### 1. Optimization Orchestrations

Create orchestration patterns that implement optimization algorithms:
- Spawn specialized agents (optimizer, evaluator, etc.)
- Use routing rules for coordination
- Track decisions and scores
- Iterate until convergence

### 2. Components for Optimization

Create optimization components in the unified architecture:
- **Personas**: `components/personas/developers/optimization_engineer.md`
- **Behaviors**: `components/behaviors/optimization/variation_generator.md`
- **Evaluations**: `components/evaluations/quality/optimization_metrics.md`
- **Orchestrations**: `components/orchestrations/optimization/mipro_framework.md`

### 3. Evaluation Integration

Use the evaluation system for metrics:
- Define evaluation components for specific metrics
- Orchestrations request evaluations via events
- Scores guide the optimization process

### 4. Framework Utilities

The optimization module provides minimal utilities:
- DSPy configuration and setup
- Example formatting for frameworks
- Git tracking for experiments
- Framework information queries

## Example: Optimizing a Component

```yaml
# Component: orchestrations/optimization/prompt_improver.md
---
component_type: orchestration
name: prompt_improver
dependencies:
  - personas/developers/optimization_engineer
  - evaluations/quality/optimization_metrics
---

agents:
  - id: optimizer
    component: personas/developers/optimization_engineer
  - id: evaluator
    component: evaluations/judges/quality_judge

routing:
  - from: optimizer
    to: evaluator
    pattern: "TEST:*"

logic: |
  For each iteration:
  1. Optimizer generates variation
  2. Evaluator scores it
  3. Track best version
  4. Repeat until convergence
```

## Benefits

1. **No new abstractions** - Uses existing KSI systems
2. **Composable** - Mix and match agents, evaluations, and strategies
3. **Flexible** - Orchestrations can implement any optimization algorithm
4. **Observable** - All events are tracked and can be monitored

## Integration with DSPy/MIPRO

DSPy and MIPRO work naturally in this architecture:

1. **DSPy Programs** - Created by agents using the optimization utilities
2. **MIPRO Strategy** - Implemented as an orchestration pattern
3. **Bayesian Optimization** - Agents track scores and propose based on history
4. **Bootstrapping** - Orchestration logic filters high-quality examples

The key insight: DSPy/MIPRO are techniques that agents use, not systems that need to control KSI. The orchestration system provides all the coordination needed.