# KSI Claude Code Tools

This directory contains Python tools for Claude Code to interact with KSI's multi-agent system.

**For KSI architecture and core concepts, see `/Users/dp/projects/ksi/CLAUDE.md`**

## Purpose

These tools provide high-level Python abstractions over KSI's event-based Unix socket API, enabling Claude to:
- Spawn and manage agents
- Observe agent behavior in real-time
- Query and traverse the graph database
- Manage agent profiles and capabilities
- Export and analyze conversations

## Key Principles

1. **Session ID Flow**: Every KSI response contains a NEW session_id - always use it for the next call
2. **Async Everything**: All operations are async - use `await` and `async for`
3. **Type Safety**: Tools use TypedDict for clear interfaces
4. **Event Patterns**: Use wildcards (`agent:*`) for flexible event matching

## Directory Structure

```
ksi_claude_code/
├── CLAUDE.md              # This file - primary context
├── __init__.py           # Package exports
├── ksi_base_tool.py      # Base class for all tools
├── agent_spawn_tool.py   # Agent lifecycle management
├── observation_tools.py  # Event monitoring
├── graph_state_tools.py  # Graph database operations
├── state_management_tools.py  # Legacy state operations
├── composition_tools.py  # Agent profile management
├── conversation_tools.py # Conversation management
├── docs/                # Archived documentation
├── experiments/         # Experimental code
└── archive/            # Deprecated code
```

## Code Conventions

### Import Pattern
```python
from ksi_claude_code import AgentSpawnTool, ObservationTool, GraphStateTool
```

### Async First
```python
# All operations are async
result = await tool.spawn_agent(...)
async for event in tool.stream_observations(...):
    process(event)
```

### Error Handling
```python
try:
    result = await tool.operation()
except asyncio.TimeoutError:
    # Handle timeout
except KSIError as e:
    # Handle KSI-specific errors
```

### Session Management
```python
# NEVER invent session IDs
# Always use what KSI returns
result = await spawn_agent(...)
session_id = result["session_id"]  # Use this for next call

# Continue conversation
result = await continue_conversation(session_id=session_id, ...)
new_session_id = result["session_id"]  # Different from input!
```

## Primary Tools Reference

### AgentSpawnTool
Spawn and manage agent lifecycles:
```python
tool = AgentSpawnTool()

# Spawn with profile
result = await tool.spawn_agent(
    profile="researcher",
    prompt="Analyze security vulnerabilities",
    model="claude-cli/sonnet"  # or "claude-cli/haiku"
)

# Continue conversation
result = await tool.continue_conversation(
    session_id=result["session_id"],
    prompt="Focus on SQL injection"
)
```

### GraphStateTool
Work with the graph database:
```python
graph = GraphStateTool()

# Create entities
entity = await graph.create_entity(
    entity_type="concept",
    properties={"name": "Machine Learning", "domain": "AI"}
)

# Create relationships
await graph.create_relationship(
    from_id=entity["id"],
    to_id="ai_root",
    relationship_type="subset_of"
)

# Traverse graph
results = await graph.traverse(
    from_id="ai_root",
    direction="incoming",
    relationship_types=["subset_of"],
    max_depth=3
)
```

### ObservationTool
Monitor agent behavior:
```python
observer = ObservationTool()

# Subscribe to events
sub = await observer.subscribe_to_events(
    target_agent=session_id,
    event_patterns=["completion:*", "agent:*"]
)

# Stream observations
async for event in observer.stream_observations(sub["subscription_id"]):
    if event["event_name"] == "agent:progress":
        print(f"Progress: {event['data']}")
```

### CompositionTool
Manage agent profiles and capabilities:
```python
comp = CompositionTool()

# List profiles
profiles = await comp.list_compositions(composition_type="profile")

# Check capabilities
caps = await comp.get_capabilities("base_multi_agent")
# Returns: {"spawn_agents": True, "state_write": True, ...}

# Reload after changes
await comp.reload_compositions()
```

## Common Patterns

### Research Coordination
```python
# Spawn coordinator
coordinator = await spawn_agent(
    profile="base_multi_agent",
    prompt="Research climate solutions. Spawn 3 researchers for different aspects."
)

# Monitor spawned agents
await observer.subscribe_to_events(
    target_agent=coordinator["construct_id"],
    event_patterns=["agent:spawn:*"]
)
```

### Parallel Analysis
```python
# Create multiple analysts
tasks = ["security", "performance", "usability"]
agents = []

for task in tasks:
    result = await spawn_agent(
        profile="analyzer",
        prompt=f"Analyze the system for {task} issues"
    )
    agents.append(result)

# Aggregate results
for agent in agents:
    result = await get_conversation(agent["session_id"])
    process_findings(result)
```

## Key Architectural Decisions

1. **Event-Only Communication** - No direct imports between KSI modules
2. **Stateless Tools** - Each tool instance is independent
3. **Graph Database** - Full entity-relationship model, not key-value
4. **Async Everywhere** - No blocking operations
5. **Session Continuity** - claude-cli manages conversation context

## Future Direction (2024-12-31)

### Hybrid Database Strategy
- **Graph Operations**: Migrate to Kùzu for Cypher queries
- **Relational Data**: Keep SQLite for traditional queries
- **Gradual Migration**: Run both systems in parallel initially

See `docs/NEXT_SESSION_PLANNING_GUIDE.md` for detailed enhancement plans.

## Quick Reference

### Check Daemon Status
```bash
./daemon_control.py status
```

### Common Event Patterns
```python
# Spawn agent
{"event": "agent:spawn", "data": {"profile": "...", "prompt": "..."}}

# Continue conversation  
{"event": "completion:async", "data": {"session_id": "...", "prompt": "..."}}

# Query graph
{"event": "state:graph:traverse", "data": {"from": "...", "depth": 2}}

# Subscribe to observations
{"event": "observation:subscribe", "data": {"target": "...", "events": ["*"]}}
```

### Debugging
```python
# Enable debug output
import os
os.environ["KSI_LOG_LEVEL"] = "DEBUG"

# Check event responses
result = await tool.operation()
print(f"Raw response: {result}")

# Monitor socket directly
tail -f var/logs/daemon/daemon.log
```

## Best Practices

1. **Always await** - Every KSI operation is async
2. **Handle timeouts** - Network operations can fail
3. **Use type hints** - Tools provide TypedDict definitions
4. **Monitor progress** - Subscribe to events for long operations
5. **Clean up** - Unsubscribe and terminate agents when done

## Troubleshooting

### Connection Refused
```bash
# Ensure daemon is running
./daemon_control.py start
```

### Session Not Found
```python
# Never reuse old session IDs
# Always use the latest returned session_id
```

### Timeout Errors
```python
# Increase timeout for long operations
result = await tool.operation(timeout=30.0)
```

---

*For historical documentation and proposals, see the `docs/` directory*