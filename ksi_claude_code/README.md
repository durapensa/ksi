# KSI Claude Code Integration

This package provides Python tools for Claude Code to interact with the KSI multi-agent system.

## Overview

KSI (Knowledge Systems Intelligence) is an event-driven multi-agent orchestration system. This package wraps KSI's Unix socket API into convenient Python tools that align with Claude Code's natural workflow.

## Key Features

- **Agent Management**: Spawn agents and maintain conversations through session IDs
- **Real-time Observation**: Monitor agent behavior and progress
- **State Management**: Share data between agents via key-value store
- **Composition System**: Work with dynamic agent capabilities
- **Conversation Tools**: Query and manage agent conversations

## Installation

The package is designed to work within the KSI project environment:

```bash
cd /path/to/ksi
source .venv/bin/activate
```

## Core Tools

### AgentSpawnTool
Spawn agents and continue conversations:

```python
from ksi_claude_code import AgentSpawnTool

tool = AgentSpawnTool()

# Spawn a new agent
result = await tool.spawn_agent(
    prompt="Research climate change solutions",
    profile="researcher"
)
session_id = result["session_id"]

# Continue the conversation
result = await tool.continue_conversation(
    session_id=session_id,
    prompt="Focus on renewable energy specifically"
)
```

### ObservationTool
Monitor agent behavior in real-time:

```python
from ksi_claude_code import ObservationTool

observer = ObservationTool()

# Subscribe to agent events
sub = await observer.subscribe(
    target_agent=session_id,
    event_patterns=["agent:progress:*", "agent:milestone:*"]
)

# Stream observations
async for event in observer.stream_observations(sub["subscription_id"]):
    print(f"Event: {event['event']} - {event['data']}")
```

### StateManagementTool
Manage shared state between agents:

```python
from ksi_claude_code import StateManagementTool

state = StateManagementTool()

# Store data
await state.set("project:status", {
    "phase": "development",
    "progress": 0.45
})

# Query data
value = await state.get("project:status")

# Query by pattern
results = await state.query_pattern("project:*")
```

### CompositionTool
Work with agent compositions and capabilities:

```python
from ksi_claude_code import CompositionTool

comp_tool = CompositionTool()

# List available profiles
profiles = await comp_tool.list_compositions(type="profile")

# Check capabilities
caps = await comp_tool.get_capabilities("base_multi_agent")
# Returns: {"spawn_agents": true, "state_write": true, ...}
```

### ConversationTool
Manage agent conversations:

```python
from ksi_claude_code import ConversationTool

conv_tool = ConversationTool()

# Get active conversations
active = await conv_tool.get_active_conversations(max_age_hours=24)

# Search conversations
results = await conv_tool.search_conversations("machine learning")

# Export conversation
export = await conv_tool.export_conversation(
    session_id=session_id,
    format="markdown"
)
```

## Architecture

The tools communicate with KSI through:
- **Unix Socket**: `/var/run/daemon.sock` (configurable)
- **Event Protocol**: JSON messages with event names and data
- **Async Operations**: All operations are asynchronous

## Key Concepts

### Session Management
- KSI returns a NEW session_id with each response
- Use the returned session_id for the next continuation
- Never invent session IDs - always use what KSI provides

### Event Patterns
- Use wildcards for flexible event matching: `agent:*`, `agent:progress:*`
- Common events: `agent:spawn:success`, `agent:complete`, `agent:error`

### Compositions
- Define agent capabilities and behaviors
- Key profiles: `base_single_agent`, `base_multi_agent`, `researcher`, `developer`
- Capabilities: `spawn_agents`, `file_access`, `network_access`, `state_write`

## Examples

See `practical_examples.py` for complete working examples including:
- Research task coordination
- Parallel analysis patterns
- Multi-agent orchestration
- Conversation monitoring
- Observation-based coordination

## Requirements

- Python 3.8+
- KSI daemon running
- Access to KSI Unix socket
- Virtual environment activated

## Contributing

This package is part of the KSI project. See the main KSI documentation for contribution guidelines.

## License

See the KSI project license.