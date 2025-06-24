# KSI Event Catalog

## Overview

This document catalogs all events in the KSI daemon system. Events follow a namespace:action format for clear organization.

## Event Namespaces

- `/system` - Core daemon lifecycle and management
- `/completion` - LLM completion requests and results
- `/agent` - Agent lifecycle and management
- `/message` - Inter-agent messaging and pub/sub
- `/state` - Persistent state management
- `/transport` - Connection and transport events

## System Events

### `system:health`
Check system health status.

**Request:**
```json
{
  "include_plugins": true,
  "include_metrics": false
}
```

**Response:**
```json
{
  "status": "healthy",
  "uptime": 3600,
  "plugins": ["completion_service", "state_service"],
  "timestamp": "2025-06-24T10:00:00Z"
}
```

### `system:shutdown`
Gracefully shutdown the daemon.

**Request:**
```json
{
  "timeout": 30,
  "force": false
}
```

**Response:**
```json
{
  "status": "shutting_down"
}
```

### `system:reload`
Reload daemon configuration.

**Request:**
```json
{
  "config_only": true,
  "restart_plugins": false
}
```

### `system:plugins`
Get information about loaded plugins.

**Response:**
```json
{
  "plugin_name": {
    "version": "1.0.0",
    "description": "Plugin description",
    "capabilities": {
      "event_namespaces": ["/completion"],
      "commands": ["completion:request"],
      "provides_services": ["completion"]
    }
  }
}
```

### `system:metrics`
Get system metrics.

**Response:**
```json
{
  "events_processed": 1000,
  "active_connections": 5,
  "memory_usage_mb": 128,
  "plugin_metrics": {}
}
```

## Completion Events

### `completion:request`
Request an LLM completion (synchronous).

**Request:**
```json
{
  "prompt": "What is 2+2?",
  "model": "sonnet",
  "session_id": "optional-session-id",
  "agent_id": "optional-agent-id",
  "enable_tools": true,
  "client_id": "client-123"
}
```

**Response:**
```json
{
  "result": "2+2 equals 4",
  "session_id": "abc123",
  "message": {
    "content": [{"text": "2+2 equals 4"}]
  },
  "type": "assistant"
}
```

### `completion:async`
Request an async LLM completion.

**Request:**
Same as `completion:request`

**Response:**
```json
{
  "request_id": "req-123",
  "status": "processing"
}
```

### `completion:started`
Emitted when completion begins processing.

**Event Data:**
```json
{
  "request_id": "req-123",
  "session_id": "abc123",
  "model": "sonnet",
  "client_id": "client-123"
}
```

### `completion:result`
Completion result (for async requests).

**Event Data:**
```json
{
  "request_id": "req-123",
  "client_id": "client-123",
  "result": {
    "result": "Response text",
    "session_id": "abc123"
  }
}
```

### `completion:error`
Completion failed.

**Event Data:**
```json
{
  "request_id": "req-123",
  "client_id": "client-123",
  "error": "Error message",
  "details": {}
}
```

### `completion:cancel`
Cancel an active completion.

**Request:**
```json
{
  "request_id": "req-123"
}
```

## Agent Events

### `agent:spawn`
Spawn a new agent process.

**Request:**
```json
{
  "agent_type": "claude",
  "config": {
    "model": "sonnet",
    "tools": ["Task", "Bash"]
  }
}
```

**Response:**
```json
{
  "process_id": "proc-123",
  "agent_id": "agent-456"
}
```

### `agent:register`
Register an agent with the system.

**Request:**
```json
{
  "agent_id": "my-agent",
  "role": "assistant",
  "capabilities": ["chat", "code"]
}
```

### `agent:list`
List all registered agents.

**Response:**
```json
{
  "agents": {
    "agent-123": {
      "role": "assistant",
      "status": "active",
      "capabilities": ["chat"]
    }
  }
}
```

### `agent:connection`
Agent connection management.

**Request:**
```json
{
  "action": "connect",
  "agent_id": "agent-123"
}
```

### `agent:route_task`
Route a task to an appropriate agent.

**Request:**
```json
{
  "task": "Write Python code",
  "requirements": ["code", "python"]
}
```

**Response:**
```json
{
  "agent_id": "code-agent-123",
  "confidence": 0.95
}
```

## Message Events

### `message:publish`
Publish a message to subscribers.

**Request:**
```json
{
  "topic": "updates",
  "message": {
    "type": "status",
    "content": "Processing complete"
  }
}
```

### `message:subscribe`
Subscribe to message topics.

**Request:**
```json
{
  "topics": ["updates", "alerts"],
  "agent_id": "subscriber-123"
}
```

### `message:send`
Send direct message to agent.

**Request:**
```json
{
  "from_agent": "agent-123",
  "to_agent": "agent-456",
  "content": "Hello",
  "metadata": {}
}
```

### `message:stats`
Get message bus statistics.

**Response:**
```json
{
  "total_messages": 1000,
  "subscriptions": 25,
  "topics": ["updates", "alerts"]
}
```

## State Events

### `state:get`
Get a state value.

**Request:**
```json
{
  "namespace": "agent:123",
  "key": "preference"
}
```

**Response:**
```json
{
  "value": "dark_mode",
  "found": true
}
```

### `state:set`
Set a state value.

**Request:**
```json
{
  "namespace": "agent:123",
  "key": "preference",
  "value": "dark_mode"
}
```

### `state:delete`
Delete a state value.

**Request:**
```json
{
  "namespace": "agent:123",
  "key": "old_preference"
}
```

### `state:list`
List keys in namespace.

**Request:**
```json
{
  "namespace": "agent:123",
  "pattern": "pref*"
}
```

**Response:**
```json
{
  "keys": ["preference", "prefix"],
  "count": 2
}
```

### `state:changed`
Emitted when state changes.

**Event Data:**
```json
{
  "type": "agent",
  "agent_id": "123",
  "key": "preference",
  "value": "dark_mode",
  "timestamp": "2025-06-24T10:00:00Z"
}
```

### `state:load`
Load state from disk.

**Request:**
```json
{
  "namespace": "*"
}
```

### `state:save`
Save state to disk.

**Request:**
```json
{
  "namespace": "agents"
}
```

### `state:clear`
Clear state data.

**Request:**
```json
{
  "namespace": "sessions",
  "confirm": true
}
```

## Transport Events

### `transport:connection`
Connection lifecycle events.

**Event Data:**
```json
{
  "transport_type": "unix",
  "connection_id": "conn-123",
  "action": "connect",
  "info": {
    "socket": "admin",
    "client_id": "client-456"
  }
}
```

### `transport:send`
Send data to specific connection.

**Request:**
```json
{
  "connection_id": "conn-123",
  "event": {
    "type": "notification",
    "data": {}
  }
}
```

### `transport:broadcast`
Broadcast to multiple connections.

**Request:**
```json
{
  "room": "agents",
  "event": {
    "type": "announcement",
    "message": "System update"
  }
}
```

### `transport:status`
Get transport status.

**Response:**
```json
{
  "status": "connected",
  "connections": 5,
  "sockets": ["admin", "agents", "messaging"]
}
```


## Event Patterns

### Correlation IDs
Use correlation IDs for request/response patterns:

```json
{
  "event": "service:request",
  "correlation_id": "corr-123",
  "data": {}
}
```

### Error Responses
Standard error format:

```json
{
  "status": "error",
  "error": {
    "code": "INVALID_INPUT",
    "message": "Human readable error",
    "details": {}
  }
}
```

### Wildcards
Subscribe to event patterns:
- `system:*` - All system events
- `agent:*` - All agent events
- `*:error` - All error events
- `**` - All events

## Custom Events

Plugins can define custom events. Recommended format:

```
plugin_name:action
```

Examples:
- `monitoring:alert`
- `auth:login`
- `cache:invalidate`

---
*Last updated: 2025-06-24*