# Declarative Orchestration Architecture

## Overview

The Declarative Orchestration Architecture extends KSI's Unified Composition system to support sophisticated multi-agent coordination patterns. By treating orchestrations as compositions, we enable complex agent interactions through simple YAML declarations rather than imperative code.

## Design Principles

1. **Declarative Patterns** - Define coordination patterns in YAML, not code
2. **Composition Reuse** - Leverage existing agent profiles and prompt templates
3. **Event-Driven Coordination** - Built on KSI's proven event routing
4. **Progressive Complexity** - Start simple, add capabilities as needed
5. **Fail-Fast with Recovery** - Circuit breakers and checkpointing built-in

## Architecture

### Plugin Structure

```
ksi_daemon/plugins/orchestration/
├── __init__.py
├── orchestration_plugin.py      # Core plugin with routing engine
├── providers/                   # Optional capability providers
│   ├── __init__.py
│   ├── consensus.py            # Voting and aggregation patterns
│   ├── workflows.py            # Complex flow control
│   ├── resilience.py           # Circuit breakers and recovery
│   └── observability.py        # Tracing and metrics
└── README.md
```

### Composition Structure

```
var/lib/compositions/orchestrations/
├── patterns/                    # Reusable orchestration patterns
│   ├── debate.yaml             # Two-agent debate pattern
│   ├── research_team.yaml      # Multi-agent research pattern
│   ├── review_chain.yaml       # Sequential review pattern
│   └── consensus_vote.yaml     # Voting-based decisions
├── components/                  # Orchestration building blocks
│   ├── routing_rules.yaml      # Reusable routing patterns
│   ├── termination.yaml        # Common termination conditions
│   └── coordination.yaml       # Turn-taking patterns
└── examples/                    # Example orchestrations
```

## Orchestration Composition Format

### Basic Structure

```yaml
name: "debate_orchestration"
type: "orchestration"
version: "1.0.0"
description: "Orchestration pattern for structured debates"
author: "ksi-system"

# Agent topology definition
agents:
  debater_for:
    profile: "debater"              # References existing profile
    prompt_template: "conversation_debate"
    vars:
      participant_number: 1
      position: "for"
    
  debater_against:
    profile: "debater"
    prompt_template: "conversation_debate"
    vars:
      participant_number: 2
      position: "against"

# Message routing patterns
routing:
  rules:
    - pattern: "debate:opening"
      from: "debater_for"
      to: "debater_against"
      
    - pattern: "debate:response"
      from: "*"
      to: "!sender"              # Not sender notation
      
    - pattern: "debate:conclusion"
      from: "*"
      broadcast: true

# Coordination patterns
coordination:
  turn_taking:
    mode: "strict_alternation"    # or "free_form", "token_based"
    timeout: 60
    max_silence: 2
    
  termination:
    conditions:
      - event: "debate:concluded"
      - rounds: 10
      - timeout: 600
      - consensus: "both_agree"

# Resource management
resources:
  limits:
    max_tokens_per_agent: 50000
    max_messages: 100
    memory_per_agent: "100MB"
  
  circuit_breakers:
    token_rate: 1000/minute
    error_threshold: 0.1
    cooldown: 30

# Observability
observability:
  trace_level: "message"          # "event", "message", "detail"
  metrics:
    - message_latency
    - token_usage
    - consensus_time
```

### Advanced Features

```yaml
# Conditional agent spawning
agents:
  mediator:
    profile: "mediator"
    spawn_condition: "deadlock_detected"
    
# Dynamic routing based on content
routing:
  rules:
    - pattern: "research:finding"
      from: "researcher_*"
      to: "synthesizer"
      condition: "confidence > 0.8"
      
# Checkpointing for long-running orchestrations
resilience:
  checkpoints:
    frequency: "every_10_messages"
    storage: "state_service"
  recovery:
    strategy: "resume_from_checkpoint"
    
# Multi-phase orchestrations
phases:
  research:
    agents: ["researcher_1", "researcher_2"]
    duration: 300
    success_condition: "findings > 3"
    
  synthesis:
    agents: ["synthesizer"]
    requires: ["research"]
    
  review:
    agents: ["reviewer", "critic"]
    requires: ["synthesis"]
```

## Core Plugin Implementation

### Event Handlers

```python
@hookimpl
def ksi_handle_event(event_name: str, data: Dict[str, Any]):
    if event_name == "orchestration:start":
        # Load and validate orchestration
        return handle_orchestration_start(data)
        
    elif event_name == "orchestration:message":
        # Apply routing rules
        return handle_message_routing(data)
        
    elif event_name == "orchestration:status":
        # Return orchestration status
        return handle_status_query(data)
```

### Key Services

1. **Pattern Loader** - Loads and validates orchestration YAML
2. **Agent Spawner** - Creates agents with composed prompts
3. **Routing Engine** - Pattern matching and message delivery
4. **State Tracker** - Orchestration state and checkpoints
5. **Resource Monitor** - Circuit breakers and limits

## Usage Examples

### Starting a Debate

```python
# Via event client
await client.emit_event("orchestration:start", {
    "pattern": "debate_orchestration",
    "vars": {
        "topic": "Is consciousness computable?",
        "duration": 300
    }
})
```

### Custom Orchestration

```yaml
# my_orchestration.yaml
name: "code_review_chain"
extends: "review_chain"    # Inherit base pattern

agents:
  architect:
    profile: "software_architect"
    
  security_reviewer:
    profile: "security_expert"
    
  performance_reviewer:
    profile: "performance_expert"

routing:
  sequence: ["architect", "security_reviewer", "performance_reviewer"]
  collect_feedback: true
```

## Integration with Existing Systems

- **Agent Service** - Spawns and manages agent lifecycle
- **Composition Service** - Loads orchestration patterns
- **Message Bus** - Routes inter-agent messages
- **State Service** - Persists orchestration state
- **Completion Service** - Handles LLM interactions

## Migration Path

1. **Phase 1** - Core plugin with basic routing
2. **Phase 2** - Add consensus provider
3. **Phase 3** - Add workflow provider
4. **Phase 4** - Add observability
5. **Phase 5** - Community patterns

## Benefits

1. **Simplicity** - Complex patterns in simple YAML
2. **Reusability** - Share patterns across projects
3. **Testability** - Declarative patterns are easier to test
4. **Extensibility** - Add providers without touching core
5. **Observability** - Built-in tracing and metrics