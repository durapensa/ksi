# Orchestration Plugin

The orchestration plugin provides declarative multi-agent coordination patterns for KSI.

## Overview

This plugin enables complex agent interactions through YAML-based orchestration patterns rather than imperative code. It handles:

- Agent lifecycle management
- Message routing based on patterns
- Coordination primitives (turn-taking, termination)
- State tracking
- Resource limits

## Architecture

```
orchestration/
├── orchestration_plugin.py    # Core plugin
├── providers/                  # Optional capability providers (future)
│   ├── consensus.py           # Voting patterns
│   ├── workflows.py           # Complex flows
│   └── observability.py       # Tracing/metrics
└── README.md
```

## Usage

### Starting an Orchestration

```python
# Start a debate
await client.emit_event("orchestration:start", {
    "pattern": "debate",
    "vars": {
        "topic": "Is consciousness computable?"
    }
})
```

### Orchestration Patterns

Patterns are stored in `var/lib/compositions/orchestrations/`:

```yaml
name: "debate"
agents:
  debater_for:
    profile: "debater"
    vars:
      position: "for"
      
routing:
  rules:
    - pattern: "debate:response"
      from: "*"
      to: "!sender"  # Not sender
      
coordination:
  turn_taking:
    mode: "strict_alternation"
```

## Events

- `orchestration:start` - Start new orchestration
- `orchestration:status` - Query orchestration status
- `orchestration:message` - Route message within orchestration
- `orchestration:terminate` - Manually terminate

## Future Enhancements

- Consensus providers for voting
- Workflow providers for complex flows
- Resilience providers for circuit breakers
- Observability providers for tracing