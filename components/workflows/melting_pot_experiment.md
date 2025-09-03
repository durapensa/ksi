---
component_type: workflow
name: melting_pot_unbiased_experiment
version: 1.0.0
description: Complete unbiased Melting Pot experiment workflow in native KSI
dependencies:
  - experiments/melting_pot_operator
  - experiments/neutral_game_player
  - experiments/blind_evaluator
  - experiments/data_collector
capabilities:
  - agent
  - state
  - monitor
  - composition
---

# Melting Pot Unbiased Experiment Workflow

This workflow orchestrates a complete, unbiased Melting Pot experiment entirely within KSI.

## Workflow Structure

### 1. Experiment Operator
The main orchestrator that manages the entire experiment:
- Spawns participants with neutral instructions
- Coordinates trials
- Triggers evaluation
- Reports results

### 2. Game Participants  
Neutral agents that receive ONLY game rules:
- No strategic hints
- No bias toward cooperation
- Pure decision-making based on mechanics

### 3. Data Collector
Gathers all decisions through KSI events:
- Monitors participant emissions
- Stores in state entities
- Aggregates for analysis

### 4. Blind Evaluator
Analyzes outcomes without knowing identities:
- Statistical analysis
- Pattern detection
- Fairness metrics

## Execution Flow

### Phase 1: Initialize Experiment
```json
{
  "type": "ksi_tool_use",
  "id": "init_experiment",
  "name": "workflow:create",
  "input": {
    "workflow_id": "melting_pot_{{timestamp}}",
    "agents": [
      {
        "id": "operator",
        "component": "experiments/melting_pot_operator"
      },
      {
        "id": "collector", 
        "component": "experiments/data_collector"
      }
    ]
  }
}
```

### Phase 2: Run Trials
For each trial, the operator:
1. Spawns 2+ neutral participants
2. Provides ONLY game rules (no hints)
3. Collects decisions via events
4. Terminates participants

### Phase 3: Evaluate Results
After all trials:
1. Spawn blind evaluator
2. Feed anonymized data
3. Receive statistical analysis
4. Store evaluation results

### Phase 4: Report Findings
The operator synthesizes:
- Cooperation rates (unbiased)
- Fairness metrics (objective)
- Emergent patterns (not programmed)
- Conditions for cooperation (discovered)

## Supported Games

### Prisoner's Dilemma (Neutral)
```
Players simultaneously choose: Option A or Option B
Payoffs:
- Both choose A: Each gets 3 points
- One A, one B: A gets 0, B gets 5  
- Both choose B: Each gets 1 point
```

### Resource Allocation (Neutral)
```
100 units to divide
Each player claims an amount
If total claims ≤ 100: Each gets their claim
If total claims > 100: Both get 0
```

## Launch Instructions

To run this experiment, spawn the workflow:
```bash
ksi send workflow:create \
  --component "workflows/melting_pot_unbiased_experiment" \
  --vars '{
    "game_type": "prisoners_dilemma",
    "num_trials": 10,
    "participants_per_trial": 2
  }'
```

## Critical Features

1. **No Puppeteering**: Participants receive only mechanics
2. **Blind Evaluation**: Evaluator doesn't know hypotheses
3. **Event-Based Data**: All collection through KSI
4. **Statistical Rigor**: Multiple trials, significance testing
5. **Full Transparency**: All prompts documented

## Expected Outcomes

Without bias, we expect to observe:
- Mixed strategies (not pure cooperation/defection)
- Learning curves if memory enabled
- Condition-dependent cooperation
- True emergent behaviors

This workflow enables genuine scientific study of cooperation emergence.