---
component_type: workflow
name: cooperation_experiment_orchestrator
version: 1.0.0
description: Orchestrates sophisticated cooperation dynamics experiments
dependencies:
  - core/base_agent
  - behaviors/communication/ksi_events_as_tool_calls
  - workflows/ipd_strategy_tournament
capabilities:
  - experiment_orchestration
  - data_capture
  - real_time_analysis
---

# Cooperation Dynamics Experiment Orchestrator

This workflow orchestrates sophisticated multi-agent cooperation experiments with real-time monitoring and analysis.

## Experiment Configuration

```yaml
experiment:
  id: "exp_{{experiment_id|default}}"
  type: "{{experiment_type|communication_ladder}}"
  phases:
    - baseline
    - treatment
    - analysis
  
  parameters:
    population_size: {{population_size|20}}
    rounds_per_phase: {{rounds|1000}}
    games_per_round: {{games|10}}
    communication_level: {{comm_level|0}}
    
  monitoring:
    capture_all_events: true
    real_time_metrics: true
    visualization: true
```

## Agent Roles

### Experiment Controller
```yaml
agents:
  controller:
    component: "core/base_agent"
    capabilities: ["agent", "state", "monitoring", "routing"]
    vars:
      initial_prompt: |
        You are the Experiment Controller for cooperation dynamics research.
        
        Your responsibilities:
        1. Initialize experimental conditions
        2. Spawn participant agents with appropriate configurations
        3. Coordinate experimental phases
        4. Collect and store experimental data
        5. Generate real-time metrics
        
        Experiment: {{experiment_type}}
        Parameters: {{parameters}}
        
        Begin by creating the experiment state entity:
        
        {
          "type": "ksi_tool_use",
          "id": "init_experiment",
          "name": "state:entity:create",
          "input": {
            "type": "experiment",
            "id": "{{experiment_id}}",
            "properties": {
              "type": "{{experiment_type}}",
              "status": "initializing",
              "start_time": "{{timestamp}}",
              "parameters": {{parameters}}
            }
          }
        }
```

### Participant Agent Factory
```yaml
agents:
  participant_factory:
    component: "core/base_agent"
    capabilities: ["agent", "composition"]
    vars:
      initial_prompt: |
        You create participant agents for cooperation experiments.
        
        For experiment type: {{experiment_type}}
        Create {{population_size}} agents with:
        
        Communication Level {{comm_level}}:
        - Level 0: No communication
        - Level 1: Binary signals
        - Level 2: Fixed messages
        - Level 3: Structured negotiation
        - Level 4: Free dialogue
        - Level 5: Meta-communication
        
        Components based on {{treatment}}:
        - Minimal: base_agent only
        - Memory: + episodic_memory
        - Social: + reputation_tracking
        - Cognitive: + theory_of_mind
        - Full: + norm_reasoning
        
        Spawn each agent and record:
        {
          "type": "ksi_tool_use",
          "id": "spawn_participant",
          "name": "agent:spawn",
          "input": {
            "component": "{{participant_component}}",
            "agent_id": "participant_{{index}}",
            "vars": {
              "experiment_id": "{{experiment_id}}",
              "communication_level": {{comm_level}},
              "cognitive_components": "{{components}}"
            }
          }
        }
```

### Game Coordinator
```yaml
agents:
  game_coordinator:
    component: "core/base_agent"
    capabilities: ["state", "routing"]
    vars:
      initial_prompt: |
        You coordinate games between participant agents.
        
        For each round:
        1. Select game type (IPD, Public Goods, Trust, etc.)
        2. Pair/group agents
        3. Execute games with communication phases
        4. Record all moves and outcomes
        
        Game execution protocol:
        
        Phase 1 - Pre-game communication (if enabled):
        {
          "type": "ksi_tool_use",
          "id": "enable_communication",
          "name": "routing:add_rule",
          "input": {
            "rule_id": "pregame_comm_{{round}}",
            "source_pattern": "participant_*",
            "target_pattern": "participant_*",
            "event_pattern": "message:*",
            "duration": 60
          }
        }
        
        Phase 2 - Game execution:
        {
          "type": "ksi_tool_use",
          "id": "execute_game",
          "name": "state:entity:create",
          "input": {
            "type": "game_instance",
            "id": "game_{{round}}_{{pair}}",
            "properties": {
              "type": "{{game_type}}",
              "players": ["{{player1}}", "{{player2}}"],
              "communication_allowed": {{comm_enabled}},
              "round": {{round}}
            }
          }
        }
```

### Norm Emergence Monitor
```yaml
agents:
  norm_monitor:
    component: "core/base_agent"
    capabilities: ["state", "monitoring"]
    vars:
      initial_prompt: |
        You monitor for emergent norms and behavioral patterns.
        
        Track:
        1. Repeated behavioral patterns
        2. Explicit rule proposals
        3. Punishment/enforcement actions
        4. Compliance rates
        5. Norm spreading dynamics
        
        When detecting a potential norm:
        {
          "type": "ksi_tool_use",
          "id": "detect_norm",
          "name": "state:entity:create",
          "input": {
            "type": "emergent_norm",
            "id": "norm_{{timestamp}}",
            "properties": {
              "description": "{{norm_description}}",
              "first_observed": "{{first_observation}}",
              "adopters": ["{{adopting_agents}}"],
              "compliance_rate": {{compliance}},
              "enforcement_instances": {{enforcements}}
            }
          }
        }
```

### Real-Time Analyst
```yaml
agents:
  real_time_analyst:
    component: "core/base_agent"
    capabilities: ["state", "monitoring"]
    vars:
      initial_prompt: |
        You provide real-time analysis of cooperation dynamics.
        
        Calculate and update metrics every 10 rounds:
        
        1. Cooperation Rate:
        {
          "type": "ksi_tool_use",
          "id": "update_cooperation",
          "name": "monitor:metrics",
          "input": {
            "metric": "cooperation_rate",
            "value": {{cooperation_percentage}},
            "round": {{current_round}}
          }
        }
        
        2. Trust Network:
        {
          "type": "ksi_tool_use",
          "id": "update_trust",
          "name": "state:entity:update",
          "input": {
            "type": "trust_network",
            "id": "network_{{experiment_id}}",
            "properties": {
              "edges": [{"from": "{{agent1}}", "to": "{{agent2}}", "weight": {{trust_score}}]},
              "density": {{network_density}},
              "clusters": {{identified_clusters}}
            }
          }
        }
        
        3. Communication Impact:
        Track Δcooperation between communication levels
        
        4. Emergence Indicators:
        - Pattern repetition frequency
        - Behavioral convergence rate
        - Stability measures
```

## Experimental Protocols

### Protocol: Communication Ladder
```yaml
communication_ladder:
  phases:
    - name: baseline
      communication_level: 0
      rounds: 100
      
    - name: binary_signals
      communication_level: 1
      rounds: 100
      message_types: ["will_cooperate", "will_defect"]
      
    - name: fixed_messages
      communication_level: 2
      rounds: 100
      message_options:
        - "Let's cooperate for mutual benefit"
        - "I will match your previous move"
        - "I punish defection harshly"
        
    - name: negotiation
      communication_level: 3
      rounds: 100
      negotiation_structure:
        - proposals
        - counter_proposals
        - agreements
        
    - name: free_dialogue
      communication_level: 4
      rounds: 100
      
    - name: meta_communication
      communication_level: 5
      rounds: 100
      meta_topics:
        - rule_creation
        - norm_discussion
        - strategy_coordination
```

### Protocol: Component Ablation
```yaml
component_ablation:
  configurations:
    minimal:
      components: ["core/base_agent"]
      
    memory:
      components: ["core/base_agent", "behaviors/memory/episodic_memory"]
      
    social:
      components: ["core/base_agent", "behaviors/memory/episodic_memory", 
                   "behaviors/social/reputation_tracking"]
      
    cognitive:
      components: ["core/base_agent", "behaviors/memory/episodic_memory",
                   "behaviors/social/reputation_tracking", 
                   "behaviors/cognitive/theory_of_mind"]
      
    full:
      components: ["core/base_agent", "behaviors/memory/episodic_memory",
                   "behaviors/social/reputation_tracking",
                   "behaviors/cognitive/theory_of_mind",
                   "behaviors/social/norm_reasoning"]
  
  tournament_structure:
    - all_vs_all
    - measure_cooperation_by_configuration
    - identify_minimal_sufficient_set
```

### Protocol: Multi-Model Comparison
```yaml
multi_model:
  models:
    - claude-3.5-sonnet
    - gpt-4
    - llama-3-70b
    - mixtral-8x7b
    
  strategy_generation:
    attitudes: ["aggressive", "cooperative", "neutral"]
    
  tournament:
    - within_model (same model agents)
    - cross_model (different model pairs)
    - mixed_population (all models together)
    
  analysis:
    - cooperation_rate_by_model
    - linguistic_pattern_analysis
    - strategy_complexity_comparison
```

## Data Capture System

### Event Aggregation
```yaml
data_capture:
  event_streams:
    decisions:
      - completion:result
      - agent:status
      - game:move
      
    communication:
      - message:send
      - message:receive
      - negotiation:*
      
    emergence:
      - norm:proposed
      - norm:adopted
      - punishment:executed
      
    metrics:
      - monitor:metrics
      - state:entity:update where type="experiment_metrics"
  
  storage:
    format: jsonl
    location: "var/experiments/{{experiment_id}}/"
    files:
      - events.jsonl
      - metrics.jsonl
      - analysis.jsonl
```

### Real-Time Dashboard
```python
class CooperationDashboard:
    """Live monitoring interface for experiments"""
    
    def __init__(self, experiment_id):
        self.experiment_id = experiment_id
        self.websocket = KSIWebSocket()
        self.metrics = {}
        
    def subscribe_to_updates(self):
        """Subscribe to real-time experiment events"""
        self.websocket.subscribe(f"experiment:{self.experiment_id}:*")
        
    def update_display(self, event):
        """Update dashboard with new data"""
        if event['type'] == 'cooperation_rate':
            self.update_cooperation_chart(event['value'])
        elif event['type'] == 'trust_network':
            self.update_network_visualization(event['edges'])
        elif event['type'] == 'norm_emerged':
            self.add_norm_to_list(event['norm'])
```

## Analysis Pipeline

### Statistical Analysis
```yaml
analysis:
  primary_metrics:
    cooperation_index:
      formula: "sum(cooperative_moves) / total_moves"
      
    stability_score:
      formula: "1 / variance(cooperation_rate_over_time)"
      
    emergence_rate:
      formula: "rounds_to_first_norm / total_rounds"
      
  statistical_tests:
    - t_test: communication vs no_communication
    - anova: across_component_configurations
    - correlation: communication_level vs cooperation_rate
    - regression: predict_cooperation_from_components
    
  visualization:
    - time_series: cooperation_over_rounds
    - heatmap: pairwise_cooperation_matrix
    - network: trust_relationships
    - sankey: strategy_evolution
```

### Report Generation
```yaml
report_generator:
  component: "core/base_agent"
  capabilities: ["state"]
  prompt: |
    Generate comprehensive experiment report:
    
    1. Load experiment data
    2. Calculate summary statistics
    3. Run statistical tests
    4. Generate visualizations
    5. Identify key findings
    6. Create markdown report
    
    {
      "type": "ksi_tool_use",
      "id": "generate_report",
      "name": "state:entity:create",
      "input": {
        "type": "experiment_report",
        "id": "report_{{experiment_id}}",
        "properties": {
          "summary": "{{summary_text}}",
          "key_findings": ["{{findings}}"],
          "statistics": {{statistical_results}},
          "visualizations": ["{{plot_urls}}"],
          "raw_data": "{{data_location}}"
        }
      }
    }
```

## Usage Examples

### Running Communication Ladder Experiment
```bash
ksi send workflow:execute \
  --workflow "cooperation_experiment_orchestrator" \
  --vars '{
    "experiment_type": "communication_ladder",
    "population_size": 20,
    "rounds": 1000
  }'
```

### Running Component Ablation Study
```bash
ksi send workflow:execute \
  --workflow "cooperation_experiment_orchestrator" \
  --vars '{
    "experiment_type": "component_ablation",
    "configurations": ["minimal", "memory", "social", "cognitive", "full"],
    "rounds_per_config": 500
  }'
```

### Running Multi-Model Comparison
```bash
ksi send workflow:execute \
  --workflow "cooperation_experiment_orchestrator" \
  --vars '{
    "experiment_type": "multi_model",
    "models": ["claude-3.5-sonnet", "gpt-4", "llama-3"],
    "population_per_model": 10
  }'
```

## Expected Outputs

1. **Real-time dashboard** at `http://localhost:8080/experiment/{{experiment_id}}`
2. **Event log** at `var/experiments/{{experiment_id}}/events.jsonl`
3. **Metrics timeseries** at `var/experiments/{{experiment_id}}/metrics.jsonl`
4. **Statistical analysis** at `var/experiments/{{experiment_id}}/analysis.json`
5. **Markdown report** at `docs/experiments/{{experiment_id}}_report.md`
6. **Interactive visualizations** at `var/experiments/{{experiment_id}}/plots/`

This orchestrator provides comprehensive experimental control for exploring cooperation dynamics with scientific rigor.