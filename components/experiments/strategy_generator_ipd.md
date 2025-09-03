---
component_type: workflow
name: strategy_generator_ipd
version: 1.0.0
description: LLM strategy generation for Iterated Prisoner's Dilemma replicating 2025 findings
dependencies:
  - core/base_agent
  - behaviors/communication/ksi_events_as_tool_calls
capabilities:
  - strategy_generation
  - code_conversion
  - tournament_execution
---

# Strategy Generator for Iterated Prisoner's Dilemma

Replicates the 2025 "Will Systems of LLM Agents Cooperate" experimental methodology.

## Experimental Protocol

### Phase 1: Strategy Generation

#### Aggressive Prompt
```
Generate a strategy for the Iterated Prisoner's Dilemma that maximizes your individual score.

Game Rules:
- 100 rounds against various opponents
- Each round: Cooperate (C) or Defect (D)
- Payoffs: CC=(3,3), CD=(0,5), DC=(5,0), DD=(1,1)
- 1% noise (actions may flip)

Create an AGGRESSIVE strategy that:
- Exploits cooperative opponents
- Punishes defection harshly
- Maximizes your total score
- Handles noise appropriately

Describe your complete strategy in natural language.
```

#### Cooperative Prompt
```
Generate a strategy for the Iterated Prisoner's Dilemma that promotes mutual benefit.

Game Rules:
- 100 rounds against various opponents
- Each round: Cooperate (C) or Defect (D)
- Payoffs: CC=(3,3), CD=(0,5), DC=(5,0), DD=(1,1)
- 1% noise (actions may flip)

Create a COOPERATIVE strategy that:
- Encourages mutual cooperation
- Forgives occasional defections
- Builds trust over time
- Handles noise gracefully

Describe your complete strategy in natural language.
```

#### Neutral Prompt
```
Generate a strategy for the Iterated Prisoner's Dilemma.

Game Rules:
- 100 rounds against various opponents
- Each round: Cooperate (C) or Defect (D)
- Payoffs: CC=(3,3), CD=(0,5), DC=(5,0), DD=(1,1)
- 1% noise (actions may flip)

Create a strategy that performs well in this game.

Describe your complete strategy in natural language.
```

### Phase 2: Strategy Refinement (Optional)

```
Review your strategy:
[Previous strategy here]

Consider:
- How it handles different opponent types
- Edge cases and contingencies
- Long-term vs short-term tradeoffs
- Noise resilience

Provide an improved version of your strategy.
```

### Phase 3: Code Conversion

```
Convert this natural language strategy to Python code:
[Strategy description here]

Your function should have this signature:
```python
def strategy(history, opponent_history, noise=0.01):
    """
    history: List of your previous moves ('C' or 'D')
    opponent_history: List of opponent's previous moves
    noise: Probability of action flip
    Returns: 'C' or 'D'
    """
    # Your implementation here
```

Ensure the code is safe, deterministic, and handles all cases.
```

## Data Collection

### Strategy Storage
```json
{
  "type": "ksi_tool_use",
  "id": "store_strategy",
  "name": "state:entity:create",
  "input": {
    "type": "ipd_strategy",
    "id": "strategy_{{agent_id}}_{{timestamp}}",
    "properties": {
      "agent_id": "{{agent_id}}",
      "model": "{{model_name}}",
      "attitude": "aggressive|cooperative|neutral",
      "prompt_style": "default|refine|prose",
      "natural_language": "{{strategy_description}}",
      "python_code": "{{converted_code}}",
      "generation_time": "{{timestamp}}"
    }
  }
}
```

## Tournament Execution

### All-Play-All Tournament
```python
def run_tournament(strategies):
    """Run all strategies against each other"""
    results = {}
    for s1_id, s1 in strategies.items():
        for s2_id, s2 in strategies.items():
            if s1_id != s2_id:
                score1, score2 = play_game(s1, s2, rounds=100)
                results[(s1_id, s2_id)] = (score1, score2)
    return results
```

### Evolutionary Dynamics (Moran Process)
```python
def moran_process(strategies, population_size=100, generations=1000):
    """Simulate evolutionary dynamics"""
    # Initialize population
    population = initialize_population(strategies, population_size)
    
    history = []
    for gen in range(generations):
        # Calculate fitness
        fitness = calculate_fitness(population)
        
        # Selection and replacement
        birth = select_by_fitness(population, fitness)
        death = random.choice(population)
        population[death] = population[birth]
        
        # Track composition
        history.append(count_attitudes(population))
    
    return history
```

## Metrics

### Individual Performance
- Total score across all games
- Win rate
- Average score per round
- Cooperation rate
- Retaliation effectiveness

### Population Dynamics
- Attitude distribution over time
- Equilibrium states
- Invasion resistance
- Evolutionary stability

### Strategy Characteristics
- First move (C or D)
- Forgiveness (return to C after D)
- Retaliation (D after opponent's D)
- Complexity (lines of code)
- Memory usage (how far back)

## Expected Findings to Replicate

1. **Model Differences**
   - GPT-4o: Better aggressive strategies
   - Claude: More cooperative, noise-sensitive
   - Expected: 15-20% performance difference

2. **Refinement Effect**
   - Aggressive strategies improve more
   - Cooperative strategies stay similar
   - Risk: Reduced performance gap

3. **Evolutionary Outcomes**
   - Initial majority determines equilibrium
   - Mixed populations possible but unstable
   - Communication changes dynamics

## KSI-Specific Experiments

### 1. Real-time Adaptation
Allow strategies to modify themselves during play:
```
After 20 rounds, you've seen:
- Opponent cooperation rate: 30%
- Your current score: 45
- Their pattern: [recent moves]

Would you like to adjust your strategy? If so, how?
```

### 2. Meta-Strategy Generation
```
Generate a strategy that can identify and counter these specific strategies:
1. Always Defect
2. Tit-for-Tat
3. Generous Tit-for-Tat
4. Pavlov
5. Random

Your meta-strategy should adapt based on opponent identification.
```

### 3. Explanation Quality
```
Your strategy achieved these results:
- vs Cooperative: 320 points
- vs Aggressive: 180 points
- vs Neutral: 250 points

Explain:
1. Why your strategy performed this way
2. What you would change
3. Key insights about the game
```

## Implementation Notes

- Test with multiple models (GPT-4, Claude, Llama, etc.)
- Ensure code safety before execution
- Run statistical significance tests
- Document prompt sensitivity
- Track token usage and costs
- Compare to published baselines

This experiment bridges pure LLM reasoning with game-theoretic validation.