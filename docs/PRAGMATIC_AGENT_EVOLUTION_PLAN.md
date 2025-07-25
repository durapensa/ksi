# Pragmatic Agent System Evolution Plan

## Start Where We Are: Building From Our Foundation

### 🎯 Current Assets
1. **Working Game Theoretic Orchestrations** - Tournament systems, strategy discovery, prisoner's dilemma
2. **Optimization Infrastructure** - DSPy/MIPROv2 successfully improving components  
3. **Communication Primitives** - completion:async, state system, event routing
4. **Proven Patterns** - JSON emission, agent spawning, orchestration coordination

## 🧬 Two-Timescale Optimization Architecture

### The Biological Insight
Living systems optimize at multiple timescales:
- **Evolution** (slow, global): Species-level adaptation over generations
- **Learning** (fast, local): Individual adaptation within a lifetime

### Applied to KSI: MIPRO v2 + SIMBA

#### Compile-Time Optimization (MIPRO v2)
- **When**: Component creation, major updates, periodic recompilation
- **What**: Global search for optimal instructions + demonstrations
- **How**: Bayesian optimization over static dev/val sets
- **Result**: Strong baseline prompts before deployment

```python
# During component build/update
mipro = dspy.MIPROv2(metric=metric, auto="medium", num_threads=24)
optimized_component = mipro.compile(component, trainset=dev_examples)
```

#### Runtime Optimization (SIMBA) 
- **When**: Live orchestrations, tournaments, self-play
- **What**: Incremental improvements using fresh feedback
- **How**: Mini-batch hill-climbing on streaming data
- **Result**: Continuous adaptation without re-bootstrapping

```python
# Inside live orchestration
simba = dspy.SIMBA(metric=round_metric, max_steps=4, num_candidates=4)
adapted_component = simba.compile(component, trainset=live_batch)
```

#### Ensemble Robustness (BetterTogether)
- **When**: Multiple high-performing variants exist
- **What**: Hedge against optimizer bias
- **How**: Ensemble voting or scrambling
- **Result**: Robust performance across diverse scenarios

```python
# After accumulating variants
ensemble = dspy.Ensemble([mipro_variant, simba_variant, previous_best])
```

## 📈 Ground-Up Evolution Strategy

### Step 1: Make Game Theoretic Orchestrations Self-Improving (Week 1)

Start with what works - enhance ONE orchestration at a time:

#### A. **Prisoner's Dilemma + Optimization** ✅ IMPLEMENTED
See: `orchestrations/prisoners_dilemma_self_improving.yaml`

This enhanced version:
- Monitors cooperation rates
- Triggers optimization when below threshold (default 60%)
- Analyzes which player strategy needs improvement
- Stores results for meta-learning
- Learns from past optimization outcomes

**Why This First**: 
- Minimal change to working code
- Tests optimization on behavioral components
- Clear success metric (cooperation rate)
- Already implemented and ready to test!

#### B. **Tournament System + Online Learning**
Enhance `adaptive_tournament_v2.yaml` with SIMBA optimization:
```yaml
# After each round
EVENT optimization:simba {
  component: "player_{{underperformer_id}}",
  metric: "round_win_rate",
  mini_batch: "last_{{mini_batch_size}}_games",
  max_steps: 4,
  num_candidates: 4
} AS improved_player

# Track optimization trajectory
EVENT state:entity:create {
  type: "simba_learning_curve",
  id: "learning_{{tournament_id}}_{{round}}",
  properties: {
    player: "{{underperformer_id}}",
    before_score: {{before}},
    after_score: {{after}},
    improvement_rate: {{(after-before)/before}}
  }
}

# Every N rounds, trigger MIPRO recompilation
IF round % 10 == 0:
  EVENT optimization:mipro {
    component: "{{winner_strategy}}",
    mode: "medium",
    objective: "generalize_across_opponents"
  }
```

### Step 2: Basic Agent Communication Patterns (Week 1-2)

#### A. **Simple Direct Messaging Test**
Create `simple_message_passing.yaml`:
```yaml
name: simple_message_passing
description: Test basic agent-to-agent communication

agents:
  researcher:
    vars:
      prompt: |
        Research the topic and share findings directly with analyzer.
        
        When you find something:
        {"event": "completion:async", "data": {"agent_id": "analyzer", "prompt": "I found that {{finding}}. What patterns do you see?"}}
  
  analyzer:
    vars:
      prompt: |
        Analyze findings shared by researcher.
        When you identify patterns, share back:
        {"event": "completion:async", "data": {"agent_id": "researcher", "prompt": "The pattern suggests {{pattern}}. Can you verify?"}}
```

**Test Incrementally**:
1. Two agents passing one message
2. Back-and-forth conversation
3. Three agents in a chain
4. Parallel coordination

#### B. **State-Based Coordination Test**
```yaml
name: state_based_research
description: Agents coordinate through shared state

agents:
  data_collector:
    prompt: |
      Collect data and store in state:
      {"event": "state:entity:create", "data": {"type": "research_data", "id": "data_{{timestamp}}", "properties": {"content": "..."}}}
  
  analyzer:
    prompt: |
      Monitor and analyze collected data:
      {"event": "state:entity:query", "data": {"type": "research_data", "limit": 10}}
```

### Step 3: Integrate Two-Timescale Optimization (Week 2)

#### A. **Component Lifecycle with Dual Optimization**
```yaml
# In component_lifecycle_orchestration.yaml
on_component_created:
  # Initial MIPRO optimization
  EVENT optimization:mipro {
    component: "{{component_path}}",
    mode: "medium",
    trainset: "bootstrap_examples"
  } AS baseline_component
  
  # Deploy to production
  EVENT composition:create_component {
    name: "{{component_name}}_v1.0",
    content: "{{baseline_component.optimized_content}}"
  }

during_orchestration_runs:
  # SIMBA adaptation in real-time
  IF performance < threshold:
    EVENT optimization:simba {
      component: "{{agent.component}}",
      mini_batch: "recent_interactions",
      max_steps: 4
    } AS adapted_component
    
    # Hot-swap the improved component
    EVENT agent:update_prompt {
      agent_id: "{{agent_id}}",
      prompt: "{{adapted_component.prompt}}"
    }

nightly_consolidation:
  # Gather all SIMBA variants
  EVENT state:entity:query {
    type: "simba_variant",
    filter: {"component": "{{component_name}}"}
  } AS daily_variants
  
  # Create ensemble if multiple good variants
  IF len(daily_variants) > 3:
    EVENT optimization:ensemble {
      variants: daily_variants,
      method: "weighted_voting"
    }
  
  # Periodic MIPRO recompilation with learned data
  IF days_since_last_mipro > 7:
    EVENT optimization:mipro {
      component: "{{component_name}}",
      mode: "heavy",
      include_trajectories: daily_variants
    }
```

#### B. **Optimization Strategy Selection**
```python
def select_optimizer(context):
    if context.data_size < 10:
        return "BootstrapFewShot"  # Too little data for sophisticated optimization
    elif context.is_streaming:
        return "SIMBA"  # Online learning scenario
    elif context.is_batch and context.can_afford_compute:
        return "MIPROv2"  # Offline optimization
    elif context.has_multiple_variants:
        return "BetterTogether"  # Ensemble approach
    else:
        return "BootstrapFewShotWithRandomSearch"  # Safe default
```

### Step 4: Build Knowledge Work Primitives (Week 2-3)

#### A. **Simple Research Pattern**
```yaml
name: basic_research_team
description: Minimal viable research orchestration

strategy: |
  # Just 3 agents, simple coordination
  SPAWN literature_reviewer WITH task: "Find prior work"
  SPAWN data_analyst WITH task: "Analyze patterns"  
  SPAWN synthesizer WITH task: "Combine findings"
  
  # Simple sequential coordination
  AWAIT literature_review
  PASS literature_review TO data_analyst
  AWAIT analysis
  PASS analysis TO synthesizer
  AWAIT synthesis
```

#### B. **Test and Iterate**
1. Run on simple topics
2. Measure output quality
3. Optimize components
4. Add complexity gradually

### Step 5: Emergent Patterns from Simple Rules (Week 3)

#### A. **Swarm Research (Simplified)**
```yaml
name: research_swarm_basic
description: Multiple agents, simple rules, emergent behavior

agents:
  explorer_{{n}}:  # Spawn 5
    prompt: |
      1. Pick a random subtopic of {{topic}}
      2. Research for 2 minutes
      3. If you find something interesting:
         {"event": "state:entity:create", "data": {"type": "finding", "properties": {"content": "...", "interest_score": 0-10}}}
      4. Check others' findings:
         {"event": "state:entity:query", "data": {"type": "finding", "filter": {"interest_score": {"$gte": 7}}}}
      5. If another's finding relates to yours, research the connection
```

**Let emerge**:
- Agents naturally cluster around interesting topics
- High-scoring findings attract more research
- Connections form organically

### Step 6: Meta-Learning from Bottom Up (Week 3-4)

#### A. **Pattern Tracker**
Simple orchestration that watches other orchestrations:
```yaml
name: pattern_observer
description: Learns from orchestration outcomes

on_orchestration_complete:
  EVENT state:entity:create {
    type: "orchestration_outcome",
    properties: {
      pattern: event.pattern_name,
      performance: MEASURE_PERFORMANCE(event),
      key_decisions: EXTRACT_DECISIONS(event)
    }
  }

every_10_completions:
  EVENT state:entity:query {
    type: "orchestration_outcome"
  } AS outcomes
  
  IDENTIFY successful_patterns
  SUGGEST improvements
```

#### B. **Gradual Automation**
1. First: Just track and report
2. Then: Suggest optimizations
3. Later: Auto-trigger optimization
4. Finally: Create new patterns

## 🔄 Feedback Loops at Every Level

### Immediate Feedback (Minutes)
- Agent message acknowledgments
- State update confirmations  
- Completion success/failure

### Short-term Learning (Hours)
- Tournament outcomes → Better strategies
- Research quality → Component optimization
- Coordination efficiency → Pattern selection

### Long-term Evolution (Days/Weeks)
- Successful patterns → Library growth
- Failed experiments → Constraint learning
- Emergent behaviors → New hypotheses

## 🎮 Practical Next Steps with Two-Timescale Optimization

### Tomorrow:
1. **Add SIMBA to running orchestrations**:
   - Modify `prisoners_dilemma_self_improving.yaml` to use SIMBA for round-by-round adaptation
   - Track improvement trajectories in state entities
   - Test with mini-batches of 4-8 games

2. **Implement optimization event handlers**:
   ```python
   @event_handler("optimization:simba")
   async def handle_simba_optimization(data, context):
       # Load component, run SIMBA, return improved version
       pass
   
   @event_handler("optimization:mipro") 
   async def handle_mipro_optimization(data, context):
       # Full MIPRO recompilation with Bayesian optimization
       pass
   ```

3. **Create optimization monitoring dashboard**:
   - Track SIMBA adaptations per orchestration
   - Monitor MIPRO recompilation cycles
   - Visualize performance improvements over time

4. **Test simple two-timescale pattern**:
   - Morning: Create new component with MIPRO baseline
   - Afternoon: Run orchestrations with SIMBA adaptation
   - Evening: Compare baseline vs adapted performance

### This Week:
1. Make 3 orchestrations self-improving
2. Test all basic communication patterns
3. Create first research team orchestration
4. Run optimization on successful patterns

### Next Week:
1. Combine patterns that work
2. Add complexity to successful patterns
3. Let swarm behaviors emerge
4. Build pattern observation

## 🏗️ Architecture Principles

### Build Small, Test Fast
- One feature at a time
- Test immediately
- Keep what works
- Discard what doesn't

### Compose From Proven Parts
- Reuse working components
- Combine simple patterns
- Let complexity emerge
- Optimize after proving value

### Learn From Everything
- Track all outcomes
- Identify patterns
- Codify successes
- Avoid repeated failures

## 🚀 The Path to Unbounded Systems

### Phase 1: Foundation (Current)
✅ Game theoretic patterns
✅ Optimization infrastructure
→ Basic communication patterns
→ Simple learning loops

### Phase 2: Composition (Weeks 1-2)
- Combine working patterns
- Optimize successful combinations
- Build knowledge primitives
- Test emergent behaviors

### Phase 3: Evolution (Weeks 3-4)
- Self-improving orchestrations
- Pattern discovery from data
- Automated optimization triggers
- Meta-learning systems

### Phase 4: Emergence (Weeks 5+)
- Orchestrations creating orchestrations
- Agents discovering new patterns
- System improving itself
- Unbounded growth potential

## The Key Insight

**Start with working code. Add one capability. Test. Optimize. Repeat.**

The meta-orchestration factory isn't the starting point - it's the emergent result of many small improvements to working systems. Build from the ground up, but keep the top-down vision as our guide.

## 🌊 The Deep Pattern: Multi-Timescale Adaptation

### Why This Architecture Enables Unbounded Growth

The MIPRO/SIMBA distinction reveals a fundamental pattern in adaptive systems:

1. **Stability vs Plasticity**: MIPRO provides stable, well-tested baselines while SIMBA enables rapid adaptation
2. **Exploration vs Exploitation**: MIPRO explores globally, SIMBA exploits locally
3. **Memory vs Learning**: MIPRO encodes long-term memory, SIMBA enables short-term learning

### Emergent Properties from Two-Timescale Optimization

When you combine compile-time (MIPRO) and runtime (SIMBA) optimization:

- **Lamarckian Evolution**: Learned behaviors (SIMBA) can be "inherited" via MIPRO recompilation
- **Baldwin Effect**: Plasticity (SIMBA) guides evolution (MIPRO) toward more learnable solutions
- **Adaptive Landscapes**: The fitness landscape itself changes as agents learn and adapt

### Implementation Philosophy

```yaml
# The Living System Pattern
Morning: 
  - New component created
  - MIPRO optimizes for strong baseline
  - Component deployed to production

Day:
  - Component participates in orchestrations
  - SIMBA adapts to specific contexts
  - Performance data accumulates

Evening:
  - Best SIMBA variants identified
  - Ensemble created for robustness
  - Insights stored for next generation

Night:
  - Periodic MIPRO recompilation
  - Incorporates learned adaptations
  - Creates improved baseline

Repeat: Each cycle stronger than the last
```

### The Path to True Autonomy

This isn't just optimization - it's creating a system that:
1. **Learns from experience** (SIMBA in orchestrations)
2. **Consolidates learning** (MIPRO recompilation)
3. **Discovers new strategies** (Ensemble diversity)
4. **Evolves indefinitely** (Continuous improvement cycles)

The system becomes its own teacher, researcher, and evolutionary pressure.

---

## Related Documentation

- **Vision**: [Unbounded Agent System Roadmap](./UNBOUNDED_AGENT_SYSTEM_ROADMAP.md)
- **Context Architecture**: [Context Reference Architecture](./CONTEXT_REFERENCE_ARCHITECTURE.md)
- **Optimization Results**: [Optimization Results Summary](./OPTIMIZATION_RESULTS_SUMMARY.md)
- **Implementation Details**: [Optimization Event Breakdown](./OPTIMIZATION_EVENT_BREAKDOWN.md)
- **Key Components**:
  - `orchestrations/prisoners_dilemma_self_improving.yaml` - Self-improving game theory
  - `orchestrations/orchestration_factory.yaml` - Meta-orchestration vision
  - `orchestrations/knowledge_work_coordination_lab.yaml` - Communication testing