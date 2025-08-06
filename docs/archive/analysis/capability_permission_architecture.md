# Capability vs Permission Architecture in KSI

## Overview

The KSI system maintains a clear distinction between **capabilities** (what an agent is designed to do) and **permissions** (what an agent is allowed to do). This document clarifies this architecture.

## Two Distinct Systems

### 1. Descriptive Capabilities (Composition System)

Located in agent profiles under `capabilities:` field, these are **descriptive tags** that indicate what an agent is designed for:

```yaml
capabilities: ["conversation", "analysis", "coordination", "research"]
```

These capabilities are:
- Descriptive metadata about agent purpose
- Used for composition selection and matching
- Not enforced by the system
- Help humans and the system understand agent roles

Examples:
- `conversation` - Agent designed for dialogue
- `analysis` - Agent designed for data analysis
- `coordination` - Agent designed to orchestrate others
- `research` - Agent designed for information gathering

### 2. Permission Capabilities (Permission System)

Located in permission profiles under `capabilities:` section, these are **actual permissions** that control system access:

```yaml
capabilities:
  multi_agent_todo: true    # Can use shared todo lists
  agent_messaging: true     # Can send messages to other agents
  spawn_agents: true        # Can spawn child agents
  network_access: false     # Cannot access network
```

These capabilities are:
- Boolean flags that grant/deny specific system features
- Enforced by the permission service
- Checked before allowing operations
- Security boundaries

## Profile Architecture

### Base Single Agent Profile (`base_single_agent`)

For agents that work independently:

```yaml
components:
  - name: "agent_config"
    inline:
      # Descriptive capabilities
      capabilities: ["conversation", "analysis", "task_execution"]
      
  - name: "permissions"
    inline:
      profile: "standard"
      overrides:
        capabilities:
          multi_agent_todo: false
          agent_messaging: false
          spawn_agents: false
```

### Base Multi-Agent Profile (`base_multi_agent`)

For agents that coordinate with others:

```yaml
extends: "base_single_agent"
components:
  - name: "agent_config"
    inline:
      # Additional descriptive capabilities
      capabilities: ["conversation", "analysis", "task_execution", 
                    "coordination", "delegation", "collaboration"]
      
  - name: "permissions"
    inline:
      profile: "trusted"
      overrides:
        capabilities:
          multi_agent_todo: true
          agent_messaging: true
          spawn_agents: true
```

## Best Practices

1. **Keep the distinction clear**: Never use permission flags as descriptive capabilities or vice versa

2. **Use inheritance**: Multi-agent profiles should extend single-agent profiles

3. **Explicit permissions**: Always explicitly set permission capabilities in profiles

4. **Match capabilities to permissions**: Agents with "coordination" capability should have `spawn_agents: true` permission

## Migration Guide

If you have existing profiles using the deprecated `base_agent`:

1. For simple agents: Change `extends: "base_agent"` to `extends: "base_single_agent"`
2. For orchestrators: Change `extends: "base_agent"` to `extends: "base_multi_agent"`
3. Review and adjust permissions as needed

## System Events and Permissions

Different permission capabilities unlock different system events:

| Permission Capability | Unlocked Events/Tools |
|----------------------|---------------------|
| `multi_agent_todo` | `TodoRead`, `TodoWrite` - Shared task management |
| `agent_messaging` | `agent:send_message` - Direct messages<br>`message:subscribe` - Join channels<br>`message:unsubscribe` - Leave channels<br>`message:publish` - Broadcast to channels<br>`message:subscriptions` - List subscriptions |
| `spawn_agents` | `agent:spawn` - Create child agents<br>`agent:terminate` - Stop agents<br>`agent:list` - List agents<br>`agent:status` - Check status |
| `network_access` | `WebFetch`, `WebSearch` - External requests |

**Important**: The permission capability (e.g., `agent_messaging: true`) must be paired with the corresponding events in `allowed_tools` for the agent to actually use them.

## Future Considerations

1. **Capability Mapping**: Consider creating explicit mappings between descriptive capabilities and required permissions
2. **Dynamic Permissions**: Allow runtime permission changes based on trust/behavior
3. **Capability Discovery**: Let agents discover what capabilities other agents have for better coordination