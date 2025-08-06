# Tournament-Based Optimization Approach

## The Problem: Evaluation Paradox

When optimizing prompts using LLM-as-Judge:
- Need good evaluation criteria to optimize prompts
- Need good prompts to create reliable evaluation criteria
- This creates circular dependency

## The Solution: Tournament-Based Co-Evolution

### Core Insights

1. **LLMs are better at ranking than scoring**
   - Pairwise comparisons are more reliable than absolute metrics
   - Bradley-Terry models can convert rankings to optimization signals
   - Only need ~2% of all comparisons for good results

2. **Co-evolve judge and task instructions**
   - Don't optimize them separately
   - Use relative performance as fitness signal
   - Bootstrap from human preferences

### Implementation Architecture

```python
class TournamentDSPyOptimizer:
    """
    Combines DSPy optimization with tournament-based evaluation
    """
    
    def __init__(self, task_signature, judge_signature):
        self.task_optimizer = dspy.MIPROv2(...)
        self.judge_optimizer = dspy.MIPROv2(...)
        self.tournament = BradleyTerryTournament()
    
    def optimize(self, initial_examples):
        # Phase 1: Bootstrap with human preferences
        human_rankings = self.collect_human_preferences(initial_examples)
        
        # Phase 2: Generate initial judge from preferences
        judge_v0 = self.bootstrap_judge(human_rankings)
        
        # Phase 3: Co-evolution loop
        for generation in range(n_generations):
            # Generate task instruction variants
            task_candidates = self.task_optimizer.propose_instructions()
            
            # Generate judge instruction variants
            judge_candidates = self.judge_optimizer.propose_instructions()
            
            # Tournament evaluation
            task_rankings = self.evaluate_via_tournament(
                task_candidates, 
                judge_candidates,
                test_cases
            )
            
            # Update both optimizers
            self.task_optimizer.update(task_rankings)
            self.judge_optimizer.update(judge_rankings)
```

### Key Components

#### 1. Pairwise Comparison Module
```python
def pairwise_compare(instruction_a, instruction_b, judge_instruction, test_case):
    """
    Compare two instructions on a test case using current judge
    """
    # Spawn agents with each instruction
    response_a = agent_with_instruction(instruction_a, test_case)
    response_b = agent_with_instruction(instruction_b, test_case)
    
    # Judge compares responses
    comparison = judge_with_instruction(judge_instruction, 
                                      test_case, 
                                      response_a, 
                                      response_b)
    return comparison.winner
```

#### 2. Bradley-Terry Ranking
```python
def compute_rankings(comparisons):
    """
    Convert pairwise comparisons to global rankings
    """
    # Use maximum likelihood estimation
    bt_model = BradleyTerry()
    bt_model.fit(comparisons)
    return bt_model.get_rankings()
```

#### 3. Sparse Sampling Strategy
```python
def sample_comparison_pairs(candidates, sampling_rate=0.02):
    """
    Intelligently sample pairs for comparison
    Focus on uncertain rankings
    """
    if first_round:
        # Random sampling initially
        return random_pairs(candidates, sampling_rate)
    else:
        # Thompson sampling based on uncertainty
        return uncertainty_based_sampling(candidates, bt_model)
```

### Advantages Over Pure DSPy

1. **No absolute metrics needed** - Only relative preferences
2. **Handles evaluation uncertainty** - Rankings are more stable
3. **Efficient** - Needs far fewer evaluations
4. **Co-evolution** - Judge improves alongside task instructions

### Integration with KSI

```yaml
# orchestrations/tournament_optimization.yaml
name: tournament_optimization_pattern
agents:
  - task_generator: 
      capability: generate_instruction_variants
  - judge_generator:
      capability: generate_judge_variants
  - tournament_coordinator:
      capability: run_pairwise_comparisons
  - ranking_analyzer:
      capability: compute_bradley_terry_rankings

flow:
  1. Generate instruction variants
  2. Run tournament with sparse sampling
  3. Compute rankings
  4. Update optimization
  5. Iterate until convergence
```

### Practical Considerations

1. **Human-in-the-loop Bootstrap**
   - Start with 10-20 human pairwise preferences
   - Use these to train initial judge
   - Gradually reduce human involvement

2. **Multi-objective Optimization**
   - Can optimize for multiple criteria simultaneously
   - Each criterion gets its own judge
   - Pareto-optimal solutions emerge

3. **Validation Strategy**
   - Periodically validate against human preferences
   - Track judge-human agreement rate
   - Adjust if drift detected

### Example: Optimizing Data Analyst Persona

```python
# Define what we're optimizing
task_signature = dspy.Signature(
    "query -> analysis",
    "Generate insightful data analysis"
)

judge_signature = dspy.Signature(
    "query, response_a, response_b -> comparison",
    "Compare two data analyses for quality"
)

# Initialize tournament optimizer
optimizer = TournamentDSPyOptimizer(
    task_signature=task_signature,
    judge_signature=judge_signature,
    n_test_cases=50,
    sampling_rate=0.02  # Only 2% of comparisons
)

# Bootstrap with human preferences
initial_rankings = collect_human_preferences(
    n_comparisons=20,
    test_queries=sample_business_questions
)

# Run optimization
best_instruction, best_judge = optimizer.optimize(
    initial_rankings=initial_rankings,
    n_generations=10
)
```

## References

1. Bradley-Terry Model in Reward Modeling (2024)
2. TourRank: Tournament-Inspired Document Ranking
3. Efficient LLM Comparative Assessment (EMNLP 2024)
4. DSPy MIPROv2 Documentation
5. Chatbot Arena: Elo Ratings for LLMs

## Next Steps

1. Implement `BradleyTerryTournament` class
2. Create `TournamentDSPyAdapter` for KSI
3. Design human preference collection UI
4. Test on real optimization tasks