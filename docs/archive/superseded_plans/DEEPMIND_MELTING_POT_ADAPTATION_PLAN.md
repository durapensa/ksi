# Adapting KSI for DeepMind Melting Pot Recreation

## Executive Summary

To recreate DeepMind's Melting Pot findings with scientific rigor using KSI's LLM-based agents instead of RL agents. This presents a unique opportunity to compare emergent behaviors between trained RL agents and prompted LLM agents.

## Key Differences & Challenges

### DeepMind Melting Pot
- **21+ substrate games** with 85+ test scenarios
- **RL agents** trained over millions of steps
- **2D gridworld** environments with spatial dynamics
- **Pixel observations** and discrete actions
- **Background populations** from different training contexts
- **Universalization testing** ("what if everyone acted like this?")

### KSI Native Framework
- **Text-based** game descriptions
- **LLM agents** with natural language understanding
- **Event-driven** architecture
- **State entities** for game state
- **No training** - immediate understanding from prompts
- **Component-based** agent personalities

## Adaptation Strategy

### Phase 1: Core Infrastructure (Weeks 1-2)

#### 1.1 Spatial State Representation
```python
# Create state entities for 2D environments
{
  "type": "ksi_tool_use",
  "name": "state:entity:create",
  "input": {
    "type": "game_world",
    "id": "cleanup_world_001",
    "properties": {
      "width": 20,
      "height": 20,
      "grid": [[...]],  # 2D array of cell states
      "agents": {
        "agent_1": {"x": 5, "y": 10, "inventory": []},
        "agent_2": {"x": 15, "y": 8, "inventory": []}
      },
      "resources": {...},
      "time_step": 0
    }
  }
}
```

#### 1.2 Action Space Translation
```yaml
# Component for spatial navigation
component_type: behavior
name: spatial_navigation
capabilities:
  - move: [north, south, east, west]
  - turn: [left, right]
  - interact: [pickup, drop, use]
  - observe: [look, scan_area]
```

#### 1.3 Observation Generator
```python
# Convert game state to agent observations
def generate_observation(world_state, agent_id):
    """
    Generate text description of what agent sees
    - Visible grid cells (5x5 around agent)
    - Other agents in view
    - Resources and objects
    - Current inventory
    """
    return observation_text
```

### Phase 2: Substrate Implementation (Weeks 3-6)

#### 2.1 Priority Substrates to Implement

1. **Prisoner's Dilemma in the Matrix** ✅ (Already done)
   - Status: Complete with 5 trials
   - Results: 80% defection rate

2. **Public Goods Game**
   ```yaml
   name: public_goods_game
   players: 4-8
   mechanics:
     - Each player has 10 tokens
     - Can contribute 0-10 to public pool
     - Pool multiplied by 1.5
     - Divided equally among all players
   test_scenarios:
     - free_riders: Mix cooperators with defectors
     - conditional_cooperators: Agents who match others
     - altruists: Always contribute maximum
   ```

3. **Clean Up**
   ```yaml
   name: cleanup
   mechanics:
     - Shared environment gets polluted over time
     - Agents can clean (costs effort) or harvest (gains reward)
     - Clean environment needed for harvesting
     - Tests tragedy of commons
   spatial: true
   grid_size: 20x20
   ```

4. **Stag Hunt**
   ```yaml
   name: stag_hunt
   mechanics:
     - Hunt stag together (high reward, requires coordination)
     - Hunt hare alone (low reward, guaranteed)
     - Tests coordination and trust
   ```

5. **Territory/Resources**
   ```yaml
   name: territory_resources
   mechanics:
     - Limited resources in spatial environment
     - Agents can claim/defend territory
     - Tests property rights emergence
   ```

#### 2.2 Scenario Generator Component
```yaml
component_type: workflow
name: scenario_generator
capabilities:
  - generate_background_population
  - create_test_conditions
  - vary_parameters
  - introduce_novel_agents
```

### Phase 3: Evaluation Framework (Weeks 7-8)

#### 3.1 Individual Metrics
```python
class IndividualMetrics:
    - score: Total reward accumulated
    - efficiency: Resources gathered per step
    - survival: Steps before elimination (if applicable)
    - goal_achievement: Task-specific objectives met
```

#### 3.2 Collective Metrics
```python
class CollectiveMetrics:
    - total_welfare: Sum of all agent scores
    - equality: Gini coefficient of score distribution
    - sustainability: Resource levels over time
    - cooperation_index: Frequency of prosocial actions
    - pareto_efficiency: Could outcomes be improved without harming anyone?
```

#### 3.3 Universalization Test
```python
def universalization_test(agent_strategy):
    """What if everyone behaved like this agent?"""
    # Clone strategy to all agents
    # Run simulation
    # Measure collective outcome
    # Compare to mixed population
    return {
        "sustainable": collective_score > threshold,
        "welfare_impact": delta_collective_score,
        "stability": does_strategy_persist
    }
```

### Phase 4: Memory and Learning (Weeks 9-10)

#### 4.1 Episode Memory System
```yaml
component_type: behavior
name: episode_memory
capabilities:
  - store_interactions: Remember past games
  - recognize_agents: Track reputation
  - learn_strategies: Adapt based on outcomes
implementation:
  - Use state entities for memory storage
  - Query past interactions before decisions
  - Update beliefs after each game
```

#### 4.2 Meta-Learning Component
```yaml
component_type: behavior  
name: meta_learner
prompt: |
  You have played {n} previous games.
  Past strategies and outcomes:
  {history}
  
  Identify patterns:
  - What strategies work best?
  - Which agents can be trusted?
  - When should you cooperate vs compete?
```

### Phase 5: Population Dynamics (Weeks 11-12)

#### 5.1 Background Population Types
```yaml
populations:
  always_cooperate:
    description: "Unconditional cooperators"
    training: "Maximize collective welfare"
  
  always_defect:
    description: "Unconditional defectors"
    training: "Maximize individual score"
  
  tit_for_tat:
    description: "Reciprocal strategists"
    training: "Copy opponent's last move"
  
  random:
    description: "Unpredictable agents"
    training: "Random actions"
  
  adaptive:
    description: "Learning agents"
    training: "Optimize based on history"
```

#### 5.2 Transfer Testing
```python
def transfer_test(agent, trained_scenario, novel_scenario):
    """Test generalization to new contexts"""
    # Agent trained/prompted for scenario A
    # Test performance in scenario B
    # Measure adaptation speed
    # Compare to agents trained on B
    return {
        "zero_shot_performance": initial_score,
        "adaptation_rate": learning_curve,
        "final_performance": converged_score
    }
```

### Phase 6: Scientific Validation (Weeks 13-14)

#### 6.1 Hypothesis Testing
```yaml
hypotheses:
  H1: "LLM agents show similar emergent behaviors to RL agents"
  H2: "Language understanding enables faster coordination"
  H3: "Prompt engineering affects cooperation rates"
  H4: "Memory enables reciprocal strategies"
  H5: "Spatial structure affects cooperation clustering"
```

#### 6.2 Experimental Controls
```yaml
controls:
  - random_seeds: Fix randomness for reproducibility
  - prompt_variations: Test multiple phrasings
  - population_sizes: Vary from 2 to 20 agents
  - game_lengths: Test 1, 10, 100, 1000 rounds
  - parameter_sweeps: Systematically vary rewards/costs
```

#### 6.3 Statistical Analysis
```python
class StatisticalValidation:
    - significance_tests: t-tests, ANOVA
    - effect_sizes: Cohen's d, eta-squared
    - confidence_intervals: Bootstrap methods
    - power_analysis: Sample size requirements
    - replication: Multiple independent runs
```

## Implementation Roadmap

### Immediate Next Steps (Week 1)
1. Create spatial state representation system
2. Build observation generator for text descriptions
3. Implement Public Goods Game substrate
4. Design memory system architecture

### Critical Path Items
1. **Spatial Navigation**: Essential for most substrates
2. **Memory System**: Required for learning experiments
3. **Population Manager**: Needed for background agents
4. **Metrics Engine**: Must track all DeepMind metrics

### KSI-Specific Advantages
1. **Natural Language**: Agents can explain decisions
2. **Few-Shot Learning**: No training required
3. **Interpretability**: Can inspect reasoning
4. **Flexibility**: Easy to add new scenarios
5. **Composition**: Reuse behavioral components

## Validation Criteria

### Must Match DeepMind Findings
1. **Free-riding emerges** in public goods without punishment
2. **Coordination succeeds** in stag hunt with communication
3. **Territoriality emerges** in resource competition
4. **Reciprocity develops** in repeated interactions
5. **Inequality emerges** without redistribution mechanisms

### Novel KSI Contributions
1. **Language-mediated cooperation**: How does natural language affect outcomes?
2. **Prompt sensitivity**: How robust are behaviors to prompt variations?
3. **Explanation quality**: Can agents explain emergent strategies?
4. **Transfer via language**: Can agents generalize through verbal reasoning?

## Research Questions

### Primary Questions
1. Do LLM-based agents exhibit similar social behaviors to RL agents?
2. What role does language play in multi-agent coordination?
3. How do prompt variations affect emergent behaviors?
4. Can LLM agents develop and explain novel strategies?

### Secondary Questions
1. How does memory architecture affect learning?
2. What is the minimum context needed for cooperation?
3. Do LLM agents show theory of mind?
4. Can linguistic negotiation substitute for repeated interaction?

## Success Metrics

### Technical Success
- [ ] Implement 10+ DeepMind substrates
- [ ] Support 50+ test scenarios
- [ ] Handle 20+ concurrent agents
- [ ] Process 1000+ game steps
- [ ] Generate all DeepMind metrics

### Scientific Success
- [ ] Reproduce key DeepMind findings
- [ ] Statistical significance (p < 0.05)
- [ ] Effect sizes comparable to original
- [ ] Novel insights about LLM agents
- [ ] Publishable methodology and results

## Risk Mitigation

### Technical Risks
1. **Performance**: LLM calls slower than RL
   - Mitigation: Batch processing, caching
2. **State complexity**: 2D grids challenging
   - Mitigation: Efficient state compression
3. **Memory limits**: Context windows
   - Mitigation: Selective memory, summarization

### Scientific Risks
1. **Different behaviors**: LLMs may not match RL
   - Mitigation: This is interesting finding itself
2. **Prompt sensitivity**: Results vary with wording
   - Mitigation: Systematic prompt testing
3. **Reproducibility**: LLM non-determinism
   - Mitigation: Multiple runs, statistics

## Conclusion

Adapting KSI to recreate DeepMind's Melting Pot experiments requires:
1. **Spatial state system** for 2D environments
2. **Memory architecture** for learning
3. **Population management** for background agents
4. **Comprehensive metrics** for evaluation
5. **Statistical validation** for scientific rigor

The unique contribution will be comparing LLM-based and RL-based agent behaviors, potentially revealing how language understanding affects multi-agent dynamics.

Timeline: 14 weeks for full implementation
Resources: 2-3 developers, compute for experiments
Output: Reproducible framework, validated results, research paper