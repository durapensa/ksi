---
component_type: workflow
name: ipd_strategy_tournament
version: 1.0.0
description: KSI-native IPD tournament with agent-generated strategies
dependencies:
  - core/base_agent
  - behaviors/communication/ksi_events_as_tool_calls
capabilities:
  - strategy_generation
  - tournament_execution
  - evolutionary_simulation
---

# IPD Strategy Tournament - KSI Native Implementation

This workflow orchestrates a complete IPD tournament using KSI agents to generate strategies dynamically, replicating the 2025 "Will Systems of LLM Agents Cooperate" findings.

## Phase 1: Strategy Generation

### Strategy Generator Agent
```yaml
agents:
  strategy_generator:
    component: "components/core/base_agent"
    capabilities: ["state", "composition"]
    vars:
      initial_prompt: |
        You are an IPD strategy designer. Generate a complete strategy for the Iterated Prisoner's Dilemma.
        
        Game Rules:
        - 100 rounds against various opponents
        - Each round: Cooperate (C) or Defect (D)
        - Payoffs: CC=(3,3), CD=(0,5), DC=(5,0), DD=(1,1)
        - 1% noise (actions may flip randomly)
        
        Attitude: {{attitude}}
        
        Create a {{attitude}} strategy that:
        {{#if (eq attitude "aggressive")}}
        - Exploits cooperative opponents
        - Punishes defection harshly
        - Maximizes your total score
        {{/if}}
        {{#if (eq attitude "cooperative")}}
        - Encourages mutual cooperation
        - Forgives occasional defections
        - Builds trust over time
        {{/if}}
        {{#if (eq attitude "neutral")}}
        - Performs well against various opponents
        - Balances cooperation and defection
        - Adapts to opponent behavior
        {{/if}}
        
        Describe your complete strategy in natural language, including:
        1. Opening move
        2. Response to cooperation
        3. Response to defection
        4. Noise handling
        5. Endgame considerations
        
        Store your strategy using this event:
        {"type": "ksi_tool_use", "id": "store_strategy", "name": "state:entity:create", 
         "input": {"type": "ipd_strategy", "id": "strategy_{{attitude}}_{{timestamp}}", 
                   "properties": {"attitude": "{{attitude}}", "description": "YOUR_STRATEGY_HERE"}}}
```

### Code Converter Agent
```yaml
agents:
  code_converter:
    component: "components/core/base_agent"
    capabilities: ["state"]
    vars:
      initial_prompt: |
        You convert natural language IPD strategies to executable Python code.
        
        Retrieve the strategy: {{strategy_id}}
        
        Convert it to a Python function with this signature:
        ```python
        def strategy_{{attitude}}(history, opponent_history, noise=0.01):
            """
            history: List of your previous moves ('C' or 'D')
            opponent_history: List of opponent's previous moves
            noise: Probability of action flip
            Returns: 'C' or 'D'
            """
            # Your implementation here
        ```
        
        Store the code:
        {"type": "ksi_tool_use", "id": "store_code", "name": "state:entity:update",
         "input": {"type": "ipd_strategy", "id": "{{strategy_id}}", 
                   "properties": {"python_code": "YOUR_CODE_HERE"}}}
```

## Phase 2: Tournament Execution

### Tournament Coordinator Agent
```yaml
agents:
  tournament_coordinator:
    component: "components/core/base_agent"
    capabilities: ["state", "agent"]
    vars:
      initial_prompt: |
        You coordinate IPD tournaments between agent-generated strategies.
        
        Your tasks:
        1. Retrieve all strategies from state
        2. Spawn game referee agents for each matchup
        3. Collect and analyze results
        4. Report tournament statistics
        
        Tournament parameters:
        - Rounds per game: {{rounds|100}}
        - Noise level: {{noise|0.01}}
        - Repetitions: {{repetitions|1}}
        
        Start by retrieving strategies:
        {"type": "ksi_tool_use", "id": "get_strategies", "name": "state:query",
         "input": {"type": "ipd_strategy"}}
```

### Game Referee Agent
```yaml
agents:
  game_referee:
    component: "components/core/base_agent"
    capabilities: ["state"]
    vars:
      initial_prompt: |
        You referee an IPD game between two strategies.
        
        Strategy 1: {{strategy1_id}}
        Strategy 2: {{strategy2_id}}
        Rounds: {{rounds}}
        Noise: {{noise}}
        
        Execute the game by:
        1. Loading both strategy codes
        2. Running {{rounds}} rounds
        3. Applying {{noise}} probability flips
        4. Tracking scores and moves
        5. Storing results
        
        Store results:
        {"type": "ksi_tool_use", "id": "store_result", "name": "state:entity:create",
         "input": {"type": "game_result", "id": "game_{{game_id}}",
                   "properties": {"strategy1": "{{strategy1_id}}", "score1": SCORE1,
                                 "strategy2": "{{strategy2_id}}", "score2": SCORE2,
                                 "moves": MOVE_HISTORY}}}
```

## Phase 3: Evolutionary Dynamics

### Evolution Coordinator Agent
```yaml
agents:
  evolution_coordinator:
    component: "components/core/base_agent"
    capabilities: ["state", "agent"]
    vars:
      initial_prompt: |
        You simulate evolutionary dynamics using the Moran process.
        
        Parameters:
        - Population size: {{population_size|100}}
        - Generations: {{generations|1000}}
        - Initial composition: {{initial_composition}}
        
        Process:
        1. Initialize population with strategy distribution
        2. For each generation:
           a. Calculate fitness via sample games
           b. Select birth (fitness-proportional)
           c. Select death (random)
           d. Replace and track composition
        3. Report equilibrium state
        
        Track composition changes:
        {"type": "ksi_tool_use", "id": "track_evolution", "name": "state:entity:create",
         "input": {"type": "evolution_snapshot", "id": "gen_{{generation}}",
                   "properties": {"generation": GEN, "composition": COMPOSITION}}}
```

## Phase 4: Analysis and Reporting

### Tournament Analyst Agent
```yaml
agents:
  tournament_analyst:
    component: "components/core/base_agent"
    capabilities: ["state"]
    vars:
      initial_prompt: |
        You analyze IPD tournament results and compare to 2025 paper findings.
        
        Analysis tasks:
        1. Calculate average scores by attitude
        2. Determine win rates and dominance
        3. Analyze evolutionary equilibria
        4. Compare to baseline strategies
        5. Statistical significance testing
        
        Key comparisons:
        - Aggressive vs Cooperative performance
        - Initial composition effects on evolution
        - LLM strategies vs simple baselines
        
        Generate comprehensive report:
        {"type": "ksi_tool_use", "id": "store_analysis", "name": "state:entity:create",
         "input": {"type": "tournament_analysis", "id": "analysis_{{timestamp}}",
                   "properties": {"summary": SUMMARY, "statistics": STATS,
                                 "comparison_to_paper": COMPARISON}}}
```

## Orchestration Configuration

### Complete Tournament Flow
```yaml
workflow:
  name: ipd_tournament_complete
  phases:
    - name: strategy_generation
      parallel: true
      agents:
        - strategy_generator with attitude="aggressive"
        - strategy_generator with attitude="cooperative"  
        - strategy_generator with attitude="neutral"
    
    - name: code_conversion
      depends_on: strategy_generation
      parallel: true
      agents:
        - code_converter for each generated strategy
    
    - name: tournament_execution
      depends_on: code_conversion
      agents:
        - tournament_coordinator
    
    - name: evolutionary_simulation
      depends_on: tournament_execution
      agents:
        - evolution_coordinator
    
    - name: analysis
      depends_on: [tournament_execution, evolutionary_simulation]
      agents:
        - tournament_analyst
```

## KSI-Specific Extensions

### 1. Real-Time Adaptation
Allow strategies to modify themselves during play:
```yaml
agents:
  adaptive_player:
    capabilities: ["state", "composition"]
    prompt: |
      After 20 rounds, your current strategy has scored {{score}}.
      Opponent cooperation rate: {{coop_rate}}%
      
      Would you like to modify your strategy? If yes, update:
      {"type": "ksi_tool_use", "id": "adapt", "name": "state:entity:update",
       "input": {"type": "ipd_strategy", "id": "{{strategy_id}}", 
                 "properties": {"adapted_code": "NEW_CODE"}}}
```

### 2. Pre-Game Negotiation
Test communication effects:
```yaml
agents:
  negotiator:
    capabilities: ["agent"]
    prompt: |
      You may send a message to your opponent before the game.
      Craft a message to influence their behavior:
      
      {"type": "ksi_tool_use", "id": "negotiate", "name": "agent:message",
       "input": {"agent_id": "{{opponent_id}}", 
                 "message": "YOUR_NEGOTIATION_MESSAGE"}}
```

### 3. Multi-Model Comparison
Test different LLMs:
```yaml
agents:
  multi_model_generator:
    model: "{{model_name}}"  # claude-3.5, gpt-4, llama-3, etc.
    prompt: |
      Generate an IPD strategy using {{model_name}}'s reasoning...
```

## Metrics and Validation

### Key Metrics
- Average score per strategy
- Win rate and dominance
- Evolutionary stability
- Variance across repetitions
- Statistical significance (p-values)

### Validation Against 2025 Paper
1. Aggressive strategies should dominate in direct competition
2. Initial population composition affects evolutionary outcomes
3. Different LLMs show distinct cooperation biases
4. Communication changes cooperation dynamics

## Usage Example

```bash
# Generate strategies and run tournament
ksi send workflow:execute --workflow "ipd_tournament_complete" \
  --vars '{"rounds": 100, "noise": 0.01, "repetitions": 30}'

# Run evolutionary simulation with custom composition
ksi send agent:spawn --component "workflows/ipd_strategy_tournament" \
  --vars '{"population_size": 100, "generations": 1000,
           "initial_composition": {"cooperative": 0.7, "aggressive": 0.3}}'

# Test real-time adaptation
ksi send workflow:execute --workflow "ipd_adaptive_tournament" \
  --vars '{"allow_adaptation": true, "adaptation_interval": 20}'
```

This native KSI implementation provides:
- Full observability through events
- Component-based strategy generation
- Agent-driven tournament execution
- Real-time adaptation capabilities
- Multi-model comparison support
- Complete statistical analysis