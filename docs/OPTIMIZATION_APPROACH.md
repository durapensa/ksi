# KSI Optimization Approach

## Philosophy

KSI takes a minimal, composable approach to optimization:

1. **Orchestration does coordination** - The existing orchestration system handles agent coordination, iteration, and state tracking
2. **Evaluation does metrics** - The evaluation system handles scoring and metric calculation
3. **Optimization provides utilities** - The optimization module provides framework-agnostic integration
4. **Components define everything** - Signatures, metrics, and optimization strategies are all components

## Bootstrapping Methodology

### DSPy-First Approach

We follow a systematic bootstrapping process for optimization:

1. **DSPy Only** - Start with programmatic metrics and systematic search
2. **LLM-as-Judge Only** - Compare with qualitative pairwise rankings
3. **Hybrid** - Combine both approaches empirically

### Manual Bootstrapping Process

Before creating complex orchestrations, we bootstrap manually:

**Phase 1: Manual Discovery**
```bash
# Spawn agents directly
ksi send agent:spawn_from_component --component "personas/developers/optimization_engineer"

# Run optimization tasks manually
ksi send completion:async --agent-id opt_eng --prompt "Optimize base_agent using DSPy..."

# Observe patterns that emerge
```

**Phase 2: Pattern Recognition**
- Track successful optimization sequences with `composition:track_decision`
- Identify reusable patterns and strategies
- Document what works for different component types

**Phase 3: Crystallize into Minimal Orchestrations**
- Only create orchestrations after patterns are proven
- Start with minimal coordination logic
- Let complexity emerge from usage

## How It Works

### 1. Components for Optimization

Everything in optimization is a component:

- **Signatures**: `components/signatures/` - DSPy input/output specifications
  ```yaml
  component_type: signature
  framework: dspy
  fields:
    instruction: InputField(desc="Current instruction")
    improved: OutputField(desc="Optimized instruction")
  ```

- **Metrics**: `components/metrics/` - Both programmatic and judge-based
  ```yaml
  component_type: metric
  metric_type: programmatic|llm_judge
  ```

- **Personas**: `components/personas/developers/optimization_engineer.md`
- **Behaviors**: `components/behaviors/optimization/continuous_iterator.md`
- **Orchestrations**: Created only after manual bootstrapping proves patterns

### 2. Framework-Agnostic Events

The optimization service provides generic events:
- `optimization:optimize` - Run optimization with any framework
- `optimization:evaluate` - Evaluate with any metric type
- `optimization:bootstrap` - Generate training examples
- `optimization:compare` - Compare optimization techniques

Frameworks are loaded dynamically:
- `frameworks/dspy_adapter.py` - DSPy implementation
- `frameworks/llm_judge_adapter.py` - Judge-based evaluation
- `frameworks/hybrid_adapter.py` - Combined approaches

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

### Core DSPy Capabilities

DSPy provides "programming, not prompting" through:

1. **Signatures as Components** - Define what to do, not how
   ```yaml
   # components/signatures/chain_of_thought.md
   component_type: signature
   framework: dspy
   signature: "question -> reasoning, answer"
   ```

2. **Predictors** - ChainOfThought, ReAct, ProgramOfThought
3. **Optimizers** - MIPROv2, BootstrapFewShot, COPRO
4. **Metrics** - Exact match, F1, custom programmatic metrics

### Key Integration Patterns

1. **Framework Adapter Pattern**
   - `optimization_service.py` remains framework-agnostic
   - `frameworks/dspy_adapter.py` handles DSPy specifics
   - Components define signatures and metrics

2. **Metric Components**
   - Programmatic metrics use DSPy functions
   - LLM judges focus on pairwise rankings (not scores)
   - Hybrid metrics combine both approaches

3. **Bootstrap-First Development**
   - Start with manual agent interactions
   - Use DSPy's bootstrap capabilities to generate examples
   - Only create orchestrations after patterns emerge

## LLM-as-Judge Integration

### Rankings Over Scores

KSI uses LLM judges for relative rankings, not absolute scores:

1. **Pairwise Comparison** - "Is A better than B?" not "Rate A from 1-10"
2. **Stable Preferences** - Relative comparisons are more consistent
3. **No Calibration Issues** - Avoids "what does 7/10 mean?" problems

### Ranking Systems

Convert pairwise preferences to rankings:
- **Elo Rating System** - Dynamic skill ratings from comparisons
- **Bradley-Terry Model** - Statistical preference modeling
- **TrueSkill** - Multi-agent comparison framework

### Judge Personas
- `components/personas/judges/game_theory_pairwise_judge.md` - Strategic comparison
- `components/personas/judges/optimization_technique_judge.md` - Technique evaluation

## Hybrid Optimization Architecture

The most powerful approach combines multiple optimization techniques:

### 1. Optimization Marketplace
Run different techniques in parallel during bootstrapping:
- **DSPy/MIPRO** - Systematic search with programmatic metrics
- **LLM-as-Judge** - Nuanced evaluation with relative ranking
- **Hybrid Approaches** - DSPy generation with judge evaluation

### 2. Empirical Technique Selection
The system learns which techniques work best:
- Test techniques head-to-head on real tasks
- Track performance by domain (game theory, code gen, creative)
- Build meta-knowledge about technique-domain mappings

### 3. Co-Evolutionary Optimization
Techniques improve together:
- Better prompts → richer evaluation data
- Better judges → more effective optimization
- Hybrid insights → novel optimization strategies

### Example Orchestrations
- `orchestrations/mipro_judge_based_optimization.yaml` - Pure judge approach
- `orchestrations/hybrid_optimization_marketplace.yaml` - Technique comparison
- `orchestrations/test_hybrid_optimization.yaml` - Simple hybrid demo

## Key Patterns

### Bootstrap Competition
```yaml
Phase 1: Run techniques in parallel
- DSPy generates systematic variants
- Judges evaluate with pairwise comparison
- Hybrid combines both approaches

Phase 2: Empirical comparison
- Cross-evaluate outputs from each technique
- Identify unique strengths and weaknesses
- Select best approach for production
```

### Hybrid Integration
```yaml
DSPy Strengths:
- Systematic parameter exploration
- Efficient search algorithms
- Programmatic correctness metrics

Judge Strengths:
- Contextual understanding
- Strategic reasoning evaluation
- Emergent insight discovery

Hybrid Value:
- Use DSPy for structured generation
- Use judges for nuanced evaluation
- Feed insights bidirectionally
```

## Benefits of Hybrid Approach

1. **Empirical Discovery** - Learn what works rather than assuming
2. **Domain Adaptation** - Different techniques for different problems
3. **Continuous Improvement** - System gets smarter over time
4. **Best of Both Worlds** - Combine algorithmic efficiency with human-like judgment

## Key Insights

### Components All the Way Down
- **Signatures are components** - Versioned, reusable DSPy specifications
- **Metrics are components** - Both programmatic and judge-based
- **No embedded prompts** - Everything that looks like a prompt is a component

### Manual Before Automated
- **Bootstrap manually first** - Discover patterns through direct agent interaction
- **Track decisions** - Use `composition:track_decision` to document what works
- **Crystallize patterns** - Only create orchestrations after proving value

### Framework Independence
- **Optimization service is agnostic** - No DSPy code in core service
- **Adapters handle specifics** - Each framework gets its own adapter
- **Components are portable** - Switch frameworks without changing components