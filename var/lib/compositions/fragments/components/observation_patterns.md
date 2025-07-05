# Observation Patterns

Configuration component for agent observation subscriptions. Agents can observe events from other agents to enable coordination and monitoring.

## Usage

```yaml
- name: "observation_config"
  inline:
    subscriptions:
      # Observe parent/originator agent
      - target_pattern: "parent"
        events: ["directive:*", "task:assigned", "priority:changed"]
        filter:
          sampling_rate: 1.0
          
      # Observe all child agents
      - target_pattern: "children"
        events: ["task:completed", "error:*", "status:*"]
        filter:
          exclude: ["status:heartbeat"]
          
      # Observe specific agent by ID
      - target_pattern: "coordinator_agent"
        events: ["coordination:*", "decision:*"]
        
      # Observe agents matching pattern
      - target_pattern: "analyzer_*"
        events: ["analysis:complete", "findings:*"]
        filter:
          rate_limit:
            max_events: 10
            window_seconds: 60.0
```

## Target Patterns

- `parent` - Observe the agent that spawned this agent
- `children` or `child_*` - Observe all agents spawned by this agent
- `{agent_id}` - Observe specific agent by ID
- `{pattern}*` - Observe agents with IDs matching pattern

## Event Patterns

Standard glob patterns:
- `*` - All events
- `task:*` - All task-related events
- `error:*` - All error events
- `["event1", "event2:*"]` - Multiple patterns

## Filters

Optional filtering of observed events:

```yaml
filter:
  # Exclude specific event patterns
  exclude: ["system:health", "debug:*"]
  
  # Sampling rate (0.0-1.0)
  sampling_rate: 0.5  # Only observe 50% of matching events
  
  # Rate limiting
  rate_limit:
    max_events: 100
    window_seconds: 60.0
    
  # Content matching (advanced)
  content_match:
    field: "priority"
    value: "high"
    operator: "equals"  # equals, contains, gt, lt
```

## Example Configurations

### Coordinator Agent
```yaml
- name: "observation_config"
  inline:
    subscriptions:
      - target_pattern: "children"
        events: ["task:completed", "task:failed", "error:*"]
```

### Worker Agent
```yaml
- name: "observation_config"
  inline:
    subscriptions:
      - target_pattern: "parent"
        events: ["directive:*", "task:assigned"]
```

### Monitor Agent
```yaml
- name: "observation_config"
  inline:
    subscriptions:
      - target_pattern: "*"  # All agents
        events: ["error:*", "warning:*"]
        filter:
          rate_limit:
            max_events: 50
            window_seconds: 60.0
```

## Notes

- Subscriptions are ephemeral - they must be re-established after system restart
- Agents automatically re-subscribe based on their profile configuration
- Dead agents' subscriptions are automatically cleaned up
- Use checkpoint/restore for subscription continuity across restarts