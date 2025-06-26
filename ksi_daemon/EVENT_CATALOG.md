# KSI Event Catalog

This document provides a comprehensive reference of all events available in the KSI daemon.
Generated automatically from plugin introspection.

*Last updated: 2025-06-26 08:57:40*

## Table of Contents

- [Agent Events](#agent-events)
- [Completion Events](#completion-events)
- [Conversation Events](#conversation-events)
- [Message Events](#message-events)
- [State Events](#state-events)
- [System Events](#system-events)

## Agent Events

Available events: `spawn`, `terminate`, `list`, `send_message`

### agent:spawn

Spawn a new agent

**Parameters:**

- `agent_id` (str) [Optional]
- `profile` (str) [Optional]
- `config` (dict) [Optional]

**Example:**
```json
{
  "event": "agent:spawn",
  "data": {}
}
```

---

### agent:terminate

Terminate an agent

**Parameters:**

- `agent_id` (str) **[Required]**

**Example:**
```json
{
  "event": "agent:terminate",
  "data": {
    "agent_id": "example_agent_id"
  }
}
```

---

### agent:list

List active agents

**Parameters:** None

**Example:**
```json
{
  "event": "agent:list",
  "data": {}
}
```

---

### agent:send_message

Send a message to an agent

**Parameters:**

- `agent_id` (str) **[Required]** - The ID of the agent to send the message to
  - Validation: Pattern: `^[a-zA-Z0-9-_:]+$`
- `message` (dict) **[Required]** - The message payload to send
  - Validation: Schema: see documentation

**Example:**
```json
{
  "event": "agent:send_message",
  "data": {
    "agent_id": "example_agent_id",
    "message": {
      "key": "value"
    }
  }
}
```

---

## Completion Events

Available events: `request`, `async`

### completion:request

Request a synchronous completion

**Parameters:**

- `prompt` (str) **[Required]** - The prompt text to send to the LLM
  - Validation: Min length: 1, Max length: 100000
- `model` (str) [Optional] - The model to use for completion (default: `'sonnet'`)
  - Validation: Allowed values: `sonnet`, `opus`, `haiku`, `gpt-4`, `gpt-3.5-turbo`
- `session_id` (str) [Optional] - Session ID for conversation continuity
  - Validation: Pattern: `^[a-zA-Z0-9-_]+$`
- `temperature` (float) [Optional] - Sampling temperature for the model (default: `'0.7'`)
  - Validation: Min: 0.0, Max: 2.0

**Example:**
```json
{
  "event": "completion:request",
  "data": {
    "prompt": "example_prompt"
  }
}
```

---

### completion:async

Request an asynchronous completion

**Parameters:**

- `prompt` (str) **[Required]**
- `model` (str) [Optional]
- `session_id` (str) [Optional]

**Example:**
```json
{
  "event": "completion:async",
  "data": {
    "prompt": "example_prompt"
  }
}
```

---

## Conversation Events

Available events: `list`, `search`, `get`, `export`, `stats`

### conversation:list

List available conversations

**Parameters:**

- `limit` (int) [Optional] - Maximum number of conversations to return (default: `'100'`)
  - Validation: Min: 1, Max: 1000
- `offset` (int) [Optional] - Number of conversations to skip (default: `'0'`)
  - Validation: Min: 0
- `sort_by` (str) [Optional] (default: `'last_timestamp'`)
- `start_date` (str) [Optional]
- `end_date` (str) [Optional]

**Example:**
```json
{
  "event": "conversation:list",
  "data": {}
}
```

---

### conversation:search

Search conversations by content

**Parameters:**

- `query` (str) **[Required]** - Search query string
  - Validation: Min length: 1, Max length: 500
- `limit` (int) [Optional] (default: `'50'`)
- `search_in` (list) [Optional] (default: `'['content']'`)

**Example:**
```json
{
  "event": "conversation:search",
  "data": {
    "query": "example_query"
  }
}
```

---

### conversation:get

Get a specific conversation

**Parameters:**

- `session_id` (str) **[Required]**
- `limit` (int) [Optional] (default: `'1000'`)
- `offset` (int) [Optional] (default: `'0'`)

**Example:**
```json
{
  "event": "conversation:get",
  "data": {
    "session_id": "example_session_id"
  }
}
```

---

### conversation:export

Export a conversation

**Parameters:**

- `session_id` (str) **[Required]**
- `format` (str) [Optional] - Export format for the conversation (default: `'markdown'`)
  - Validation: Allowed values: `markdown`, `json`, `text`, `html`

**Example:**
```json
{
  "event": "conversation:export",
  "data": {
    "session_id": "example_session_id"
  }
}
```

---

### conversation:stats

Get conversation statistics

**Parameters:** None

**Example:**
```json
{
  "event": "conversation:stats",
  "data": {}
}
```

---

## Message Events

Available events: `subscribe`, `publish`

### message:subscribe

Subscribe to message events

**Parameters:**

- `event_types` (list) [Optional]

**Example:**
```json
{
  "event": "message:subscribe",
  "data": {}
}
```

---

### message:publish

Publish a message

**Parameters:**

- `event_type` (str) **[Required]**
- `data` (dict) **[Required]**
- `target` (str) [Optional]

**Example:**
```json
{
  "event": "message:publish",
  "data": {
    "event_type": "example_event_type",
    "data": {
      "key": "value"
    }
  }
}
```

---

## State Events

Available events: `get`, `set`, `delete`

### state:get

Get a state value

**Parameters:**

- `key` (str) **[Required]**
- `namespace` (str) [Optional]

**Example:**
```json
{
  "event": "state:get",
  "data": {
    "key": "example_key"
  }
}
```

---

### state:set

Set a state value

**Parameters:**

- `key` (str) **[Required]** - The state key to set
  - Validation: Pattern: `^[a-zA-Z0-9-_:.]+$`, Max length: 255
- `value` (Any) **[Required]** - The value to store (can be any JSON-serializable type)
- `namespace` (str) [Optional] - Optional namespace for the key
  - Validation: Pattern: `^[a-zA-Z0-9-_]+$`, Max length: 100

**Example:**
```json
{
  "event": "state:set",
  "data": {
    "key": "example_key",
    "value": "any_value"
  }
}
```

---

### state:delete

Delete a state value

**Parameters:**

- `key` (str) **[Required]**
- `namespace` (str) [Optional]

**Example:**
```json
{
  "event": "state:delete",
  "data": {
    "key": "example_key"
  }
}
```

---

## System Events

Available events: `health`, `shutdown`, `discover`, `help`

### system:health

Check daemon health status

**Parameters:** None

**Example:**
```json
{
  "event": "system:health",
  "data": {}
}
```

---

### system:shutdown

Gracefully shutdown the daemon

**Parameters:**

- `force` (bool) [Optional] (default: `'False'`)

**Example:**
```json
{
  "event": "system:shutdown",
  "data": {}
}
```

---

### system:discover

Discover available events

**Parameters:**

- `namespace` (str) [Optional]
- `include_internal` (bool) [Optional] (default: `'False'`)

**Example:**
```json
{
  "event": "system:discover",
  "data": {}
}
```

---

### system:help

Get detailed help for an event

**Parameters:**

- `event` (str) **[Required]**

**Example:**
```json
{
  "event": "system:help",
  "data": {
    "event": "example_event"
  }
}
```

---

## Notes

- All events follow the namespace:action pattern
- Events are handled by plugins in a non-blocking manner
- The first plugin to return a non-None response handles the event
- Use correlation_id for request/response patterns
