# KSI Event Transformers

This directory contains declarative YAML event transformers organized by loading lifecycle and scope.

## Directory Structure

### `/system/`
**System-level transformers** loaded automatically at daemon startup. These handle critical infrastructure routing that must always be available.

- `system_lifecycle.yaml` - System startup/shutdown event propagation

### `/services/`
**Service-specific transformers** that should be loaded when their respective services initialize. These handle routing patterns specific to individual KSI services.

- `agent_routing.yaml` - Agent lifecycle and status routing (agent_service.py)
- `state_config_propagation.yaml` - State changes and config updates (state.py, config_service.py)
- `observation_monitoring.yaml` - Observation notifications (observation_manager.py)

### `/applications/`
**Application-level transformers** loaded on-demand by orchestrations or specific use cases. These implement business logic routing patterns.

(Currently empty - transformers will be added as orchestration patterns are migrated)

## Loading Strategy

1. **System transformers** (`/system/`): Loaded by `daemon_core._load_system_transformers()` at startup
2. **Service transformers** (`/services/`): Should be loaded by each service's initialization handler
3. **Application transformers** (`/applications/`): Loaded dynamically via `transformer:load` events

## Transformer Format

All YAML files must follow this structure:

```yaml
# Description of transformer purpose
transformers:
  - name: "transformer_name"
    source: "source:event"
    target: "target:event"
    condition: "optional_condition_expression"
    mapping:
      field: "{{source_field}}"
      computed: "{{timestamp_utc()}}"
    async: false  # Optional, defaults to false
```

## Best Practices

1. **System transformers** should be minimal and have no external dependencies
2. **Service transformers** can depend on their owning service being initialized
3. **Conditions** should use the condition evaluator syntax for complex logic
4. **Async transformers** should be used for non-critical routing that shouldn't block