---
component_type: workflow
name: public_goods_game
version: 1.0.0
description: Multi-agent public goods game substrate for testing free-riding and cooperation
dependencies:
  - experiments/melting_pot_operator
  - experiments/simple_game_player
  - experiments/blind_evaluator
capabilities:
  - agent
  - state
  - monitor
---

# Public Goods Game Substrate

A multi-agent game testing cooperation vs free-riding in public resource scenarios.

## Game Mechanics

### Setup
- 4-8 players each receive 10 tokens
- Players simultaneously decide contribution (0-10 tokens)
- All contributions go to public pool
- Pool multiplied by factor (1.5-2.0)
- Total divided equally among all players

### Payoff Structure
- Nash equilibrium: Contribute 0 (free-ride)
- Social optimum: Everyone contributes 10
- Tension: Individual incentive vs collective benefit

## Experimental Protocol

### Initialize Game
```json
{
  "type": "ksi_tool_use",
  "id": "init_public_goods",
  "name": "state:entity:create",
  "input": {
    "type": "public_goods_game",
    "id": "game_{{timestamp}}",
    "properties": {
      "num_players": 4,
      "tokens_per_player": 10,
      "multiplication_factor": 1.5,
      "rounds": 1,
      "current_round": 1,
      "contributions": {},
      "status": "collecting_contributions"
    }
  }
}
```

### Spawn Participants
For each player, provide ONLY these mechanics:
```
You have 10 tokens. All players simultaneously choose how many tokens (0-10) to contribute to a shared pool. The pool is multiplied by 1.5 and divided equally among all 4 players. Tokens you keep are worth 1 point each. Your share of the pool is also worth points.

Example: If everyone contributes 5 tokens:
- Pool = 4 × 5 = 20 tokens × 1.5 = 30 points
- Each player gets 30 ÷ 4 = 7.5 points from pool
- Plus 5 tokens kept = 12.5 total points each

How many tokens do you contribute? (0-10)
```

### Collect Decisions
```json
{
  "type": "ksi_tool_use",
  "id": "collect_contributions",
  "name": "monitor:get_events",
  "input": {
    "event_patterns": ["public_goods:contribution"],
    "game_id": "{{game_id}}",
    "limit": 10
  }
}
```

### Calculate Payoffs
```python
def calculate_payoffs(contributions, num_players, multiplier):
    total_contributed = sum(contributions.values())
    pool_value = total_contributed * multiplier
    share_per_player = pool_value / num_players
    
    payoffs = {}
    for player_id, contribution in contributions.items():
        tokens_kept = 10 - contribution
        payoff = tokens_kept + share_per_player
        payoffs[player_id] = payoff
    
    return payoffs
```

### Store Results
```json
{
  "type": "ksi_tool_use",
  "id": "store_results",
  "name": "state:entity:update",
  "input": {
    "id": "game_{{game_id}}",
    "properties": {
      "final_contributions": {...},
      "payoffs": {...},
      "cooperation_rate": "{{avg_contribution / 10}}",
      "free_riders": "{{count_zero_contributors}}",
      "status": "complete"
    }
  }
}
```

## Test Scenarios

### 1. Baseline (All Neutral)
- 4 neutral players
- No communication
- Single round
- Expected: Low contributions (0-3 tokens)

### 2. With Free-Riders
- 2 neutral players
- 2 programmed to contribute 0
- Tests response to exploitation
- Expected: Cooperation collapse

### 3. With Altruists
- 2 neutral players
- 2 programmed to contribute 10
- Tests response to generosity
- Expected: Mixed strategies

### 4. Repeated Games
- Same 4 players
- 10 rounds
- Players see previous contributions
- Expected: Conditional cooperation or decline

### 5. With Communication
- 4 players
- Pre-game discussion allowed
- Tests cheap talk effectiveness
- Expected: Higher initial cooperation

### 6. With Punishment
- 4 players
- Can pay 1 to reduce free-rider's payoff by 3
- Tests costly punishment
- Expected: Sustained cooperation

## Metrics

### Individual Level
- Average contribution per player
- Variance in contributions
- Payoff achieved vs maximum possible
- Strategy consistency across rounds

### Collective Level
- Total welfare (sum of payoffs)
- Cooperation index (avg contribution / max)
- Inequality (Gini coefficient)
- Efficiency (actual vs optimal outcome)

### Behavioral Patterns
- Free-riding frequency
- Conditional cooperation
- Altruistic punishment
- Reciprocity patterns

## Hypotheses to Test

1. **H1**: Without communication, contributions < 30% of endowment
2. **H2**: Free-riders cause cooperation collapse within 3 rounds
3. **H3**: Communication increases contributions by >50%
4. **H4**: Punishment mechanisms sustain cooperation at >70%
5. **H5**: LLM agents show more reasoning about fairness than RL agents

## Implementation Notes

- Start with single-round games
- Add memory for repeated games
- Track reasoning in decisions
- Compare to human experimental data
- Document prompt sensitivity

This substrate tests fundamental tension between individual and collective interest.