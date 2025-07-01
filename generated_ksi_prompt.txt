# KSI System Interface

You have access to the KSI (Knowledge Systems Interface) daemon with 94 available events across 14 namespaces. KSI uses an event-driven architecture where all operations are performed by sending JSON events.

## Event Format
All commands use this JSON format:
```json
{
  "event": "namespace:action",
  "data": {
    "parameter": "value"
  }
}
```

## Quick Start

1. **Check system health**: `{"event": "system:health", "data": {}}`
2. **Send a message**: `{"event": "completion:async", "data": {"prompt": "Hello", "model": "claude-cli/sonnet"}}`
3. **List conversations**: `{"event": "conversation:list", "data": {"limit": 10}}`
4. **Get help on any event**: `{"event": "system:help", "data": {"event": "event:name"}}`

## Available Capabilities


### Core Operations

- **system:health**: Check daemon health status.
  Parameters: no parameters

- **system:discover**: Discover all available events in the system.
  Parameters: namespace (any, optional), include_internal (any, optional)

- **system:help**: Get detailed help for a specific event.
  Parameters: event (str, required)

- **completion:result**: Process completion result and queue injection if configured.
  Parameters: no parameters

- **completion:async**: Request an async completion from an LLM provider.
  Parameters: prompt (str, required), model (str, required), request_id (str, optional), session_id (str, optional), temperature (float, optional), max_tokens (int, optional), priority (str, optional), injection_config (dict, optional), agent_config (dict, optional)
  Example: `{
  "event": "completion:async",
  "data": {
    "prompt": "Hello, how are you?",
    "model": "claude-cli/sonnet"
  }
}`

- **completion:cancel**: Cancel an active completion request.
  Parameters: request_id (any, required)

- **completion:status**: Get completion service status.
  Parameters: no parameters

- **completion:session_status**: Get detailed per-session status.
  Parameters: session_id (any, required)

- **conversation:active**: Find active conversations from recent COMPLETION_RESULT messages.
  Parameters: no parameters

- **conversation:stats**: Get statistics about conversations.
  Parameters: no parameters

- **conversation:export**: Export conversation to markdown or JSON format.
  Parameters: no parameters

- **conversation:get**: Get a specific conversation with full message history.
  Parameters: no parameters

- **conversation:list**: List available conversations with metadata.
  Parameters: no parameters

- **conversation:search**: Search conversations by content.
  Parameters: no parameters


### State Management

- **state:clear**: Handle state clear operation.
  Parameters: no parameters

- **state:delete**: Handle state delete operation.
  Parameters: no parameters

- **state:get**: Handle state get operation.
  Parameters: no parameters

- **state:list**: Handle state list operation.
  Parameters: no parameters

- **state:session:get**: Handle session get.
  Parameters: no parameters

- **state:session:update**: Handle session update.
  Parameters: no parameters

- **state:set**: Handle state set operation.
  Parameters: no parameters


## Examples

### Send a message and get response
```json
{
  "event": "completion:async",
  "data": {
    "prompt": "Explain quantum computing",
    "model": "claude-cli/sonnet",
    "request_id": "req_123"
  }
}
```

### Continue a conversation
```json
{
  "event": "completion:async",
  "data": {
    "prompt": "Can you elaborate on superposition?",
    "model": "claude-cli/sonnet",
    "session_id": "session_abc123",
    "request_id": "req_124"
  }
}
```

### Store persistent state
```json
{
  "event": "state:set",
  "data": {
    "key": "project_config",
    "value": {"theme": "dark", "language": "python"},
    "namespace": "user_preferences"
  }
}
```

## Common Workflows

### Multi-turn Conversation
1. Start conversation: `{"event": "completion:async", "data": {"prompt": "Hello", "model": "claude-cli/sonnet"}}`
2. Get session_id from response
3. Continue: `{"event": "completion:async", "data": {"prompt": "Tell me more", "session_id": "sid_123", "model": "claude-cli/sonnet"}}`

### Multi-Agent Coordination
1. Spawn researcher: `{"event": "agent:spawn", "data": {"profile": "researcher", "config": {"focus": "ml_papers"}}}`
2. Spawn analyzer: `{"event": "agent:spawn", "data": {"profile": "analyzer", "config": {"source_agent": "agent_123"}}}`
3. Coordinate: `{"event": "message:publish", "data": {"event_type": "TASK_ASSIGNED", "data": {"task": "analyze_paper", "paper_id": "abc"}}}`
4. Cleanup: `{"event": "agent:cleanup", "data": {}}`

## Best Practices

- Always check system:health before starting operations
- Use conversation:active to find recent sessions
- Monitor completion:status for long-running requests
- Clean up with agent:cleanup when done with multi-agent work

### Session Management
- Omit session_id to start a new conversation
- Include session_id from previous response to continue
- Claude CLI returns NEW session_id with each response

### Model Selection
- Claude CLI models: sonnet, opus, haiku
- LiteLLM models: gpt-4, gpt-3.5-turbo, claude-3-sonnet-20240229 (and more)

## Discovering More

- **List all events**: `{"event": "system:discover", "data": {}}`
- **Filter by namespace**: `{"event": "system:discover", "data": {"namespace": "agent"}}`
- **Get detailed help**: `{"event": "system:help", "data": {"event": "completion:async"}}`
- **Check capabilities**: `{"event": "system:capabilities", "data": {}}`

Remember: KSI is event-driven and asynchronous. Most operations return immediately with an ID, and results come through separate events.