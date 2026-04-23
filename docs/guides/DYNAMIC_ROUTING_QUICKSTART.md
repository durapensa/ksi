# Dynamic Routing Quick Start Guide

## What is Dynamic Routing?

Dynamic routing allows agents to control event flow at runtime, replacing static orchestration patterns with emergent coordination.

## Quick Example

```bash
# 1. Create a routing rule
ksi send routing:add_rule \
  --rule_id "my_first_route" \
  --source_pattern "hello:world" \
  --target "greeting:received" \
  --priority 500

# 2. Send an event that matches
ksi send hello:world --message "Hi there!"

# 3. See the routing decision
ksi send introspection:routing_decisions --event_name "hello:world"
```

## Key Concepts

- **Routing Rules**: Define how events flow (source → target)
- **Priority**: Higher numbers win when multiple rules match
- **TTL**: Rules can expire automatically
- **Introspection**: See why events were routed where

## For Agents

Agents with `routing_control` capability can:
```python
# Create routes
{"event": "routing:add_rule", "data": {...}}

# Modify routes  
{"event": "routing:modify_rule", "data": {...}}

# Delete routes
{"event": "routing:delete_rule", "data": {...}}

# Query routes
{"event": "routing:query_rules", "data": {...}}
```

## Common Patterns

### Load Balancing
Route to different workers based on ID hash:
```python
"condition": "hashCode(data.id) % 3 == 0"  # Worker 1
"condition": "hashCode(data.id) % 3 == 1"  # Worker 2
"condition": "hashCode(data.id) % 3 == 2"  # Worker 3
```

### Priority Routing
High priority tasks to fast processor:
```python
"condition": "data.priority == 'high'"
"target": "processor:fast"
"priority": 900  # High priority rule
```

### Temporary Workflows
Auto-cleanup with TTL:
```python
"ttl": 600  # Expires in 10 minutes
```

## Debugging

```bash
# See all routing decisions
ksi send introspection:routing_decisions

# Check specific rule impact
ksi send introspection:routing_impact --rule_id "my_rule"

# View audit trail
ksi send routing:query_audit_log
```

## Full Documentation

See `/docs/DYNAMIC_ROUTING_ARCHITECTURE.md` for:
- Complete architecture overview
- Operational guide for agents
- Implementation details
- Advanced patterns