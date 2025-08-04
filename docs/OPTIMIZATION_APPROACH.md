# KSI Optimization Approach

## Philosophy

KSI takes a minimal, composable approach to optimization:

1. **Orchestration does coordination** - The existing orchestration system handles agent coordination, iteration, and state tracking
2. **Evaluation does metrics** - The evaluation system handles scoring and metric calculation
3. **Optimization provides utilities** - The optimization module provides framework-agnostic integration
4. **Components define everything** - Signatures, metrics, and optimization strategies are all components

## Optimization Targets

KSI optimizes for multiple dimensions beyond token efficiency:

- **Instruction Following**: Agents precisely execute requested tasks
- **Task Lock-In**: Agents maintain focus without digression
- **Behavioral Consistency**: Predictable, reliable agent behavior
- **Token Efficiency**: Minimal token usage while maintaining quality
- **Response Quality**: Accuracy, completeness, and usefulness

These dimensions require sophisticated metrics that evaluate actual agent behavior, not just instruction text.

## Context System Integration

The new Pythonic context system transforms optimization observability:

### Automatic Optimization Tracking
- **Correlation IDs** thread through entire optimization workflows
- **Parent-child relationships** link optimization → agents → evaluations
- **Event lineage** enables retrospective analysis of what worked
- **Reference architecture** reduces storage by 70% while improving tracking

### Key Context Features for Optimization
1. **Optimization Run Context**
   ```python
   # When starting optimization, context is created
   optimization_context = {
       "_correlation_id": "opt_run_123",
       "_optimization_id": "mipro_base_agent_v2",
       "_framework": "dspy",
       "_target_component": "base_agent"
   }
   ```

2. **Behavioral Test Tracking**
   - Each spawned test agent inherits optimization context
   - All completions linked to optimization run
   - Judge evaluations correlated automatically
   - Can query: "Show all behavioral tests for optimization X"

3. **Cross-Framework Correlation**
   - Context flows through DSPy subprocess calls
   - MLflow runs linked via context
   - Git commits tagged with optimization context
   - Complete experiment reconstruction possible

### Example: Tracing an Optimization
```bash
# Query all events for an optimization run
ksi send monitor:get_events --correlation-id "opt_run_123"

# Returns complete chain:
# optimization:start → optimization:async → agent:spawn (multiple) →
# completion:async (tests) → evaluation:judge → optimization:complete
```

## Bootstrapping Methodology

### DSPy-First Approach

We follow a systematic bootstrapping process for optimization:

1. **DSPy Only** - Start with programmatic metrics and systematic search
2. **LLM-as-Judge Only** - Compare with qualitative pairwise rankings
3. **Hybrid** - Combine both approaches empirically

### Critical Insight: Evaluate Outputs, Not Instructions

**The Problem**: DSPy optimizes instruction text, but metrics should evaluate actual agent outputs.
- ❌ **Wrong**: Evaluating if instruction text contains JSON
- ✅ **Right**: Evaluating if agent using instruction produces valid JSON

This requires **agent-in-the-loop evaluation** where:
1. DSPy proposes optimized instructions
2. Agent spawns with those instructions
3. Agent generates outputs on test prompts
4. Metrics evaluate the actual outputs

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

### 5. Current Implementation Status (2025-01)

**MIPRO and SIMBA Integration**: Successfully integrated and operational
- ✅ MIPRO runs complete optimization cycles with configurable trials
- ✅ SIMBA configured (currently falls back to MIPRO internally)
- ✅ Subprocess architecture handles long-running optimizations
- ⚠️ **Key Finding**: 0% improvement with minimal default metric

**Critical Insight**: The default metric is too simplistic for meaningful optimization. Need proper agent-in-the-loop evaluation with real behavioral testing.

### 6. The Evaluation Paradox & Tournament Solution

**The Paradox**: To optimize prompts we need good metrics, but good metrics require optimized evaluation prompts.

**The Solution**: Tournament-based co-evolution using pairwise comparisons instead of absolute scores.

#### Why Tournament Ranking Works

LLMs excel at comparative judgments because:
- **Relative context** provides natural anchoring
- **"Which is better?"** is more reliable than "Rate 1-10"
- **Systematic biases** affect both options similarly
- **Research shows** only ~2% of comparisons needed for accurate rankings

#### Tournament-Based Optimization

```python
# Use pairwise comparisons instead of absolute metrics
class TournamentOptimizer:
    def evaluate_instructions(self, candidates):
        # Bradley-Terry model converts comparisons to rankings
        comparisons = []
        for i, j in sample_pairs(candidates, n=0.02*total):
            winner = judge.compare(candidates[i], candidates[j])
            comparisons.append((i, j, winner))
        
        rankings = bradley_terry_mle(comparisons)
        return rankings
```

#### Co-Evolution Architecture

Optimize both task instructions AND judge instructions:

```yaml
# orchestrations/tournament_optimization.yaml
flow:
  1. Bootstrap with human preferences (10-20 comparisons)
  2. Generate task instruction variants (via DSPy)
  3. Generate judge instruction variants  
  4. Run sparse tournament (2% sampling)
  5. Update both optimizers with rankings
  6. Iterate until convergence
```

## Recent Research Integration (2024-2025)

### Automatic Prompt Optimization Techniques

**OPRO (Optimization by PROmpting)**: Uses LLMs to iteratively evaluate and optimize prompts
- Outperforms human-designed prompts by up to 8% on GSM8K
- Up to 50% improvement on Big-Bench Hard tasks
- Works with only 3.5% of training data

**Meta Prompting**: Self-improving feedback loops
- DSPy manages multiple LLM calls for refinement
- TEXTGRAD uses natural language feedback
- Iterative improvement through successive generations

### Key Optimization Principles

1. **Clarity and Specificity**: Well-defined queries prevent inconsistent outputs
2. **Structured I/O**: JSON/XML formats enhance LLM understanding
3. **Task Decomposition**: Break complex processes into subtasks
4. **Few-Shot Examples**: Guide pattern recognition
5. **Chain-of-Thought**: Step-by-step reasoning for complex tasks
6. **ReAct Pattern**: Combine reasoning with action planning

### Practical Findings

- **Word Choice Sensitivity**: Minor variations cause significant accuracy differences
- **Direct Communication**: Politeness phrases have no impact on LLM performance
- **Audience Specification**: Targeted responses improve quality
- **Iterative Refinement**: Essential for optimization convergence

### 6. Agent-Based Evaluation Metrics

For proper evaluation of optimized instructions:

**System Feedback Approach** (for JSON emission):
```python
# Use KSI's own event validation as the metric
async def ksi_system_validation_metric(instruction, test_prompts, context):
    # Spawn agent with optimization context propagated
    agent = await spawn_agent_with_instruction(instruction, context)
    scores = []
    
    for prompt in test_prompts:
        # Context automatically flows to completion
        response = await agent.complete(prompt)
        # Extract JSON events from response
        events = extract_json_events(response)
        
        # Use KSI system to validate each event
        for event in events:
            # Context propagates through validation
            result = await ksi.send_event(event)
            scores.append(1.0 if result.status == "success" else 0.0)
    
    # Full optimization lineage available via context
    return np.mean(scores)
```

**Context Benefits**:
- All agent actions linked to optimization run
- Behavioral tests automatically correlated
- Can query: "Show all agents spawned for optimization X"
- Error propagation tracked through context chain

**LLM-as-Judge Approach** (for quality evaluation):
```python
# Use judge agents to evaluate response quality
async def judge_evaluation_metric(instruction, test_prompts, criteria, context):
    # Both agents inherit optimization context
    agent = await spawn_agent_with_instruction(instruction, context)
    judge = await spawn_judge_agent(context)
    scores = []
    
    for prompt in test_prompts:
        # Context flows through completion
        response = await agent.complete(prompt)
        
        # Judge evaluation linked to same optimization
        evaluation = await judge.evaluate(
            prompt=prompt,
            response=response,
            criteria=criteria
        )
        scores.append(evaluation.score)
    
    # Can query: "Show all judge evaluations for optimization X"
    return np.mean(scores)
```

### Critical Discovery: Static vs Behavioral Evaluation

**The Fundamental Challenge**: Optimization systems evaluate instruction TEXT, not agent BEHAVIOR.

1. **Current State: Static Analysis**
   - DSPy optimizes instruction text
   - Metrics evaluate textual properties  
   - Judges analyze instruction structure
   - No actual behavior testing

2. **Static Analysis Value**
   - **Baseline Testing**: Static textual analysis by LLM-as-Judge provides the most basic evaluation
   - **Quick Iteration**: Can rapidly evaluate many instruction variants without spawning agents
   - **Structural Validation**: Ensures instructions are well-formed and comprehensive
   - **Foundation Layer**: Static analysis should be the first gate before behavioral testing

3. **Next Level: Behavioral Validation**
   - Spawn agents with each instruction variant
   - Run standardized test prompts across different models (Sonnet, Opus, Gemini-2.5-pro)
   - Compare actual outputs using `completion:async` events
   - Measure behavioral differences and model-specific performance

4. **Test Instructions as Components**
   - **Problem**: Current test instructions are manual `--prompt` text, not tracked
   - **Solution**: Express test instructions as components for versioning and tracking
   - **Example**: `components/evaluations/test_suites/data_analysis_behavioral.md`
   - **Benefit**: Can optimize test suites alongside task instructions

5. **Why Both Matter**
   - **Static**: Fast, cheap filtering of obviously bad instructions
   - **Behavioral**: True validation of real-world performance
   - **Together**: Multi-stage pipeline - static filter → behavioral validation → production

### Working DSPy Configuration

**Requirements**:
1. **Model Configuration**: Set `optimization_prompt_model` and `optimization_task_model`
2. **Clear Signatures**: Explicit task framing with "You are an expert at..."
3. **Concrete Examples**: Show actual instruction transformations
4. **Baseline Metrics**: Start with structural improvement rewards

**Configuration**:
```yaml
# logging.yaml or daemon config
optimization_prompt_model: claude-3-5-haiku-20241022
optimization_task_model: claude-3-5-haiku-20241022
```

**Working Signature**:
```python
class KSIComponentSignature(dspy.Signature):
    """You are an expert at optimizing prompts and instructions for AI systems. 
    Your task is to take an existing instruction/prompt and make it more effective, 
    detailed, and actionable while maintaining its core purpose."""
    # Clear field descriptions guide the optimization
    optimized_instruction: str = dspy.OutputField(desc="Your IMPROVED version...")
```

### Implementation Details

**Git Operations Control**:
- Added `skip_git` parameter to defer git commits during testing
- Usage: `ksi send optimization:process_completion --skip-git true`

**MLflow Artifact Tracking**:
- All optimization results stored in `var/db/mlflow_artifacts/`
- Key files: `best_model.json`, `trainset.json`, `valset.json`
- Access via MLflow run ID from optimization status

**Baseline Metric Implementation**:
```python
def baseline_optimization_metric(example, prediction, trace=None):
    """Accept any non-empty optimization as progress."""
    if hasattr(prediction, 'optimized_instruction'):
        instruction = str(prediction.optimized_instruction)
    else:
        instruction = str(prediction)
    
    # Basic quality checks
    if len(instruction) < 50:
        return 0.1  # Too short
    if instruction == example.current_instruction:
        return 0.1  # No change
    
    # Reward structural improvements
    score = 0.3  # Base score for trying
    if '\n' in instruction:
        score += 0.2  # Has structure
    if any(marker in instruction for marker in ['##', '**', '-', '1.']):
        score += 0.2  # Has formatting
    if len(instruction) > len(example.current_instruction):
        score += 0.3  # Added content
    
    return min(1.0, score)
```

**Phase 2: Agent-in-the-Loop** (Next Step)
- Run optimization in main process, not subprocess
- DSPy proposes → Spawn agent → Test outputs → Score behavior
- Use existing KSI infrastructure for agent management

**Phase 3: Tournament-Based** (Future)
- Implement pairwise comparison infrastructure
- Co-evolve judge and task instructions
- Use Bradley-Terry model for rankings

### Next Steps: From Static to Behavioral

1. **Current State** ✅
   - DSPy optimization produces improved instructions
   - Static metrics evaluate textual improvements
   - LLM judges perform theoretical analysis
   - Git operations can be controlled

2. **Behavioral Evaluation** (Next Phase)
   - Spawn test agents with each instruction variant
   - Run standardized behavioral test suites
   - Compare actual outputs, not instruction text
   - Feed behavioral scores back to DSPy

3. **Tournament System** (Future)
   - Pairwise behavioral comparisons
   - Bradley-Terry ranking from outcomes
   - Co-evolution of instructions and judges

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
5. **Context-Enhanced** - Automatic correlation and lineage tracking
6. **Introspectable** - Full optimization chains queryable via context
7. **Efficient** - 70% storage reduction with reference architecture

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
   - Context flows through all framework boundaries

2. **Metric Components**
   - Programmatic metrics use DSPy functions
   - LLM judges focus on pairwise rankings (not scores)
   - Hybrid metrics combine both approaches
   - All metrics share optimization context for correlation

3. **Bootstrap-First Development**
   - Start with manual agent interactions
   - Use DSPy's bootstrap capabilities to generate examples
   - Only create orchestrations after patterns emerge
   - Context tracking reveals successful patterns

4. **Context-Aware Optimization**
   - Every optimization gets unique correlation ID
   - All spawned agents inherit optimization context
   - Behavioral tests automatically linked to variants
   - Complete experiment reconstruction from context DB

## LLM-as-Judge Integration

### Rankings Over Scores

KSI uses LLM judges for relative rankings, not absolute scores:

1. **Pairwise Comparison** - "Is A better than B?" not "Rate A from 1-10"
2. **Stable Preferences** - Relative comparisons are more consistent
3. **No Calibration Issues** - Avoids "what does 7/10 mean?" problems
4. **Sparse Sampling** - Only ~2% of all pairs needed for accurate rankings

### Ranking Systems

Convert pairwise preferences to rankings:
- **Bradley-Terry Model** - Maximum likelihood estimation from comparisons (recommended)
- **Elo Rating System** - Dynamic skill ratings, used in Chatbot Arena
- **TourRank** - Tournament-inspired approach for document/prompt ranking

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

## Claude 4 Best Practices for Instruction Optimization

Based on Anthropic's prompt engineering guidelines, apply these principles when optimizing KSI components:

### 1. Explicit Over Implicit
- **Be extremely specific** about desired outputs and behaviors
- **Provide clear context** explaining why behaviors matter
- **Use positive instructions** ("do X") rather than negative constraints ("don't do Y")

### 2. Structure and Formatting
- **Use XML tags** to organize different parts of instructions
- **Provide templates** for expected output formats
- **Include examples** with clear input-output mappings

### 3. Step-by-Step Reasoning
- **Encourage thinking** with phrases like "think step by step"
- **Request reflection** after receiving information
- **Guide planning** before execution

### 4. Component-Specific Optimization
For different component types:
- **Analysis components**: Request comprehensive, structured analysis
- **JSON emission**: Provide exact format with field descriptions
- **Creative tasks**: Use motivational language like "Give it your all"

### 5. Iterative Refinement Process
Follow this optimization cycle:
1. **Baseline**: Start with simple, clear instructions
2. **Test**: Evaluate on diverse, realistic scenarios
3. **Analyze**: Identify failure patterns
4. **Enhance**: Add techniques (CoT, examples, structure)
5. **Measure**: Use automated metrics where possible

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

### Evaluation at the Right Level
- **Evaluate outputs, not instructions** - Test what agents produce, not prompt text
- **Use system feedback** - For JSON emission, use KSI's validation
- **Agent-in-the-loop** - Spawn agents to test optimized instructions

## Event Context & Tracing ✅ IMPLEMENTED

**Key Achievement**: Unified context system with 70% storage reduction and automatic correlation tracking.

### Context-Enhanced Optimization Features
1. **Automatic Correlation**: Every optimization event inherits context
2. **Behavioral Test Tracking**: All spawned agents linked to optimization runs
3. **Cross-Framework Integration**: Context flows through DSPy, judges, and evaluators
4. **Full Lineage Queries**: Complete optimization chains queryable via context DB

## Current Status ✅ WORKING PIPELINE

**Implemented Features**:
- DSPy MIPROv2 optimization with realistic baseline metrics (0.30-0.90)
- LLM-as-Judge static instruction analysis
- MLflow artifact tracking and git integration
- Automatic context propagation through optimization flows
- Event lineage tracking from optimization → agents → evaluation
- 70% storage reduction with context reference architecture

**Next Phase: Behavioral Evaluation**
- Migrate from standalone bootstrap scripts to KSI-native orchestrations
- Implement agent-in-the-loop testing (evaluate outputs, not instructions)
- Tournament-based pairwise comparison system

## Future Context-Enabled Enhancements

### 1. Optimization Analytics Dashboard
With full context tracking, we can build powerful analytics:
- **Success rate by technique**: Which optimization methods work best?
- **Behavioral improvement metrics**: How much do agents actually improve?
- **Cross-model performance**: Track optimization portability (Sonnet → Opus)
- **Time-to-convergence**: How long do different techniques take?

### 2. Automatic Experiment Reports
Context system enables automatic report generation:
```python
# Generate comprehensive optimization report
report = await generate_optimization_report("opt_run_123")
# Includes: initial state, all variants tested, behavioral scores,
# judge evaluations, final selection, git commits, MLflow artifacts
```

### 3. Meta-Optimization Insights
Learn which optimization techniques work for which component types:
- Pattern recognition from successful optimizations
- Automatic technique selection based on component characteristics
- Transfer learning from similar past optimizations

### 4. Optimization Debugging
When optimizations fail, context provides complete forensics:
- Trace exactly where behavioral tests diverged from expectations
- Compare successful vs failed optimization runs
- Identify systematic biases in evaluation metrics