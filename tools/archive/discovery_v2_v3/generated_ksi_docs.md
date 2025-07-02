# KSI System Interface

Generated from system:discover on 2025-07-02T08:19:18.847952

## System Statistics

- Total Events: 180
- Namespaces: 20

## Event Format

All events follow this JSON format:
```json
{"event": "namespace:action", "data": {parameters}}
```

## Available Events

### System Namespace

#### `system:context`

Handle system:context event

**Parameters:** None

---

#### `system:health`

Handle system:health event

**Parameters:** None

---

#### `system:startup`

Handle system:startup event

**Parameters:**

- `config` (Dict[str, Any]) *(required)*: config parameter

**Example:**

```json
{
  "event": "system:startup",
  "data": {
    "config": "example_config"
  }
}
```

---

#### `system:shutdown`

Handle system:shutdown event

**Parameters:** None

---

#### `system:discover`

Handle system:discover event

**Parameters:**

- `namespace` (Any) *(optional)*: Optional namespace filter (e.g., "agent", "completion")
- `include_internal` (Any) *(optional)*: Include internal system events (default: False) - default: `False`

**Example:**

```json
{
  "event": "system:discover",
  "data": {}
}
```

---

#### `system:help`

Handle system:help event

**Parameters:**

- `event` (str) *(required)*: The event name to get help for (required)

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

#### `system:capabilities`

Handle system:capabilities event

**Parameters:** None

---

#### `system:ready`

Handle system:ready event

**Parameters:** None

---

### State Namespace

#### `state:get`

Handle state:get event

**Parameters:**

- `namespace` (str) *(optional)*: The namespace to get from (default: "global") - default: `global`
- `key` (str) *(required)*: The key to retrieve (required)

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

#### `state:set`

Handle state:set event

**Parameters:**

- `namespace` (str) *(optional)*: The namespace to set in (default: "global") - default: `global`
- `key` (str) *(required)*: The key to set (required)
- `value` (any) *(required)*: The value to store (required)
- `metadata` (dict) *(optional)*: Optional metadata to attach (default: {}) - default: `{}`

**Example:**

```json
{
  "event": "state:set",
  "data": {
    "key": "example_key",
    "value": "<any>"
  }
}
```

---

#### `state:delete`

Handle state:delete event

**Parameters:**

- `namespace` (str) *(optional)*: The namespace to delete from (default: "global") - default: `global`
- `key` (str) *(required)*: The key to delete (required)

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

#### `state:list`

Handle state:list event

**Parameters:**

- `namespace` (str) *(optional)*: Filter by namespace (optional)
- `pattern` (str) *(optional)*: Filter by pattern (optional, supports * wildcard)

**Example:**

```json
{
  "event": "state:list",
  "data": {}
}
```

---

### Async State Namespace

#### `async_state:get`

Handle async_state:get event

**Parameters:**

- `namespace` (Any) *(optional)*: namespace parameter - default: `default`
- `key` (Any) *(optional)*: key parameter

**Example:**

```json
{
  "event": "async_state:get",
  "data": {}
}
```

---

#### `async_state:set`

Handle async_state:set event

**Parameters:**

- `namespace` (Any) *(optional)*: namespace parameter - default: `default`
- `key` (Any) *(optional)*: key parameter
- `value` (Any) *(required)*: value parameter

**Example:**

```json
{
  "event": "async_state:set",
  "data": {
    "value": "<Any>"
  }
}
```

---

#### `async_state:delete`

Handle async_state:delete event

**Parameters:**

- `namespace` (Any) *(optional)*: namespace parameter - default: `default`
- `key` (Any) *(optional)*: key parameter

**Example:**

```json
{
  "event": "async_state:delete",
  "data": {}
}
```

---

#### `async_state:push`

Handle async_state:push event

**Parameters:**

- `namespace` (Any) *(optional)*: namespace parameter - default: `default`
- `queue_name` (Any) *(optional)*: queue_name parameter
- `value` (Any) *(required)*: value parameter

**Example:**

```json
{
  "event": "async_state:push",
  "data": {
    "value": "<Any>"
  }
}
```

---

#### `async_state:pop`

Handle async_state:pop event

**Parameters:**

- `namespace` (Any) *(optional)*: namespace parameter - default: `default`
- `queue_name` (Any) *(optional)*: queue_name parameter

**Example:**

```json
{
  "event": "async_state:pop",
  "data": {}
}
```

---

#### `async_state:get_keys`

Handle async_state:get_keys event

**Parameters:**

- `namespace` (Any) *(optional)*: namespace parameter - default: `default`

**Example:**

```json
{
  "event": "async_state:get_keys",
  "data": {}
}
```

---

#### `async_state:queue_length`

Handle async_state:queue_length event

**Parameters:**

- `namespace` (Any) *(optional)*: namespace parameter - default: `default`
- `queue_name` (Any) *(optional)*: queue_name parameter

**Example:**

```json
{
  "event": "async_state:queue_length",
  "data": {}
}
```

---

### Module Namespace

#### `module:list`

Handle module:list event

**Parameters:** None

---

#### `module:events`

Handle module:events event

**Parameters:** None

---

#### `module:inspect`

Handle module:inspect event

**Parameters:**

- `module_name` (Any) *(required)*: module_name parameter

**Example:**

```json
{
  "event": "module:inspect",
  "data": {
    "module_name": "<Any>"
  }
}
```

---

### Api Namespace

#### `api:schema`

Handle api:schema event

**Parameters:** None

---

### Correlation Namespace

#### `correlation:trace`

Handle correlation:trace event

**Parameters:**

- `correlation_id` (Any) *(required)*: The correlation ID to retrieve trace for

**Example:**

```json
{
  "event": "correlation:trace",
  "data": {
    "correlation_id": "<Any>"
  }
}
```

---

#### `correlation:chain`

Handle correlation:chain event

**Parameters:**

- `correlation_id` (Any) *(required)*: The correlation ID to retrieve chain for

**Example:**

```json
{
  "event": "correlation:chain",
  "data": {
    "correlation_id": "<Any>"
  }
}
```

---

#### `correlation:tree`

Handle correlation:tree event

**Parameters:**

- `correlation_id` (Any) *(required)*: The correlation ID to retrieve tree for

**Example:**

```json
{
  "event": "correlation:tree",
  "data": {
    "correlation_id": "<Any>"
  }
}
```

---

#### `correlation:stats`

Handle correlation:stats event

**Parameters:** None

---

#### `correlation:cleanup`

Handle correlation:cleanup event

**Parameters:**

- `max_age_hours` (Any) *(optional)*: Maximum age in hours for traces to keep (default: 24) - default: `24`

**Example:**

```json
{
  "event": "correlation:cleanup",
  "data": {}
}
```

---

#### `correlation:current`

Handle correlation:current event

**Parameters:** None

---

### Monitor Namespace

#### `monitor:get_events`

Handle monitor:get_events event

**Parameters:**

- `event_patterns` (Any) *(required)*: event_patterns parameter
- `client_id` (Any) *(required)*: client_id parameter
- `since` (Any) *(required)*: since parameter
- `until` (Any) *(required)*: until parameter
- `limit` (Any) *(optional)*: limit parameter - default: `100`
- `reverse` (Any) *(optional)*: reverse parameter - default: `True`
- `data` (Any) *(required)*: Query parameters: - event_patterns: List of event name patterns (supports wildcards) - client_id: Filter by specific client - since: Start time (ISO string or timestamp) - until: End time (ISO string or timestamp) - limit: Maximum number of events to return - reverse: Return newest first (default True)

**Example:**

```json
{
  "event": "monitor:get_events",
  "data": {
    "event_patterns": "<Any>",
    "client_id": "<Any>",
    "since": "<Any>",
    "until": "<Any>",
    "data": "<Any>"
  }
}
```

---

#### `monitor:get_stats`

Handle monitor:get_stats event

**Parameters:** None

---

#### `monitor:clear_log`

Handle monitor:clear_log event

**Parameters:** None

---

#### `monitor:subscribe`

Handle monitor:subscribe event

**Parameters:**

- `client_id` (Any) *(required)*: client_id parameter
- `event_patterns` (Any) *(optional)*: event_patterns parameter
- `writer` (Any) *(required)*: writer parameter
- `data` (Any) *(required)*: Subscription parameters: - event_patterns: List of event name patterns (supports wildcards) - filter_fn: Optional additional filter function - client_id: Client identifier - writer: Transport writer reference

**Example:**

```json
{
  "event": "monitor:subscribe",
  "data": {
    "client_id": "<Any>",
    "writer": "<Any>",
    "data": "<Any>"
  }
}
```

---

#### `monitor:unsubscribe`

Handle monitor:unsubscribe event

**Parameters:**

- `client_id` (Any) *(required)*: client_id parameter
- `data` (Any) *(required)*: Unsubscribe parameters: - client_id: Client identifier

**Example:**

```json
{
  "event": "monitor:unsubscribe",
  "data": {
    "client_id": "<Any>",
    "data": "<Any>"
  }
}
```

---

#### `monitor:query`

Handle monitor:query event

**Parameters:**

- `query` (Any) *(required)*: query parameter
- `params` (Any) *(optional)*: params parameter
- `limit` (Any) *(optional)*: limit parameter - default: `1000`
- `data` (Any) *(required)*: Query parameters: - query: SQL query string - params: Optional query parameters (tuple) - limit: Maximum results (default 1000)

**Example:**

```json
{
  "event": "monitor:query",
  "data": {
    "query": "<Any>",
    "data": "<Any>"
  }
}
```

---

#### `monitor:get_session_events`

Handle monitor:get_session_events event

**Parameters:**

- `session_id` (Any) *(required)*: session_id parameter
- `include_memory` (Any) *(optional)*: include_memory parameter - default: `True`
- `reverse` (Any) *(optional)*: reverse parameter - default: `True`
- `data` (Any) *(required)*: Query parameters: - session_id: Session ID to query - include_memory: Include events from memory buffer (default True) - reverse: Sort newest first (default True)

**Example:**

```json
{
  "event": "monitor:get_session_events",
  "data": {
    "session_id": "<Any>",
    "data": "<Any>"
  }
}
```

---

#### `monitor:get_correlation_chain`

Handle monitor:get_correlation_chain event

**Parameters:**

- `correlation_id` (Any) *(required)*: correlation_id parameter
- `include_memory` (Any) *(optional)*: include_memory parameter - default: `True`
- `data` (Any) *(required)*: Query parameters: - correlation_id: Correlation ID to trace - include_memory: Include events from memory buffer (default True)

**Example:**

```json
{
  "event": "monitor:get_correlation_chain",
  "data": {
    "correlation_id": "<Any>",
    "data": "<Any>"
  }
}
```

---

### Transport Namespace

#### `transport:create`

Handle transport:create event

**Parameters:**

- `transport_type` (Any) *(required)*: transport_type parameter
- `config` (Any) *(optional)*: config parameter

**Example:**

```json
{
  "event": "transport:create",
  "data": {
    "transport_type": "<Any>"
  }
}
```

---

#### `transport:message`

Handle transport:message event

**Parameters:**

- `command` (Any) *(required)*: command parameter
- `parameters` (Any) *(optional)*: parameters parameter

**Example:**

```json
{
  "event": "transport:message",
  "data": {
    "command": "<Any>"
  }
}
```

---

### Completion Namespace

#### `completion:cancelled`

Handle completion:result event

**Parameters:**

- `timestamp` (Any) *(optional)*: timestamp parameter
- `correlation_id` (Any) *(required)*: correlation_id parameter

**Example:**

```json
{
  "event": "completion:cancelled",
  "data": {
    "correlation_id": "<Any>"
  }
}
```

---

#### `completion:error`

Handle completion:result event

**Parameters:**

- `timestamp` (Any) *(optional)*: timestamp parameter
- `correlation_id` (Any) *(required)*: correlation_id parameter

**Example:**

```json
{
  "event": "completion:error",
  "data": {
    "correlation_id": "<Any>"
  }
}
```

---

#### `completion:progress`

Handle completion:result event

**Parameters:**

- `timestamp` (Any) *(optional)*: timestamp parameter
- `correlation_id` (Any) *(required)*: correlation_id parameter

**Example:**

```json
{
  "event": "completion:progress",
  "data": {
    "correlation_id": "<Any>"
  }
}
```

---

#### `completion:result`

Handle completion:result event

**Parameters:**

- `timestamp` (Any) *(optional)*: timestamp parameter
- `correlation_id` (Any) *(required)*: correlation_id parameter

**Example:**

```json
{
  "event": "completion:result",
  "data": {
    "correlation_id": "<Any>"
  }
}
```

---

#### `completion:async`

Handle completion:async event

**Parameters:**

- `request_id` (Any) *(required)*: request_id parameter
- `session_id` (Any) *(optional)*: session_id parameter - default: `default`
- `model` (Any) *(optional)*: model parameter - default: `unknown`

**Example:**

```json
{
  "event": "completion:async",
  "data": {
    "request_id": "<Any>"
  }
}
```

---

#### `completion:cancel`

Cancel an in-progress completion

**Parameters:**

- `request_id` (str) *(required)*: request_id parameter

**Example:**

```json
{
  "event": "completion:cancel",
  "data": {
    "request_id": "example_request_id"
  }
}
```

---

#### `completion:status`

Get status of all active completions

**Parameters:** None

---

#### `completion:session_status`

Get detailed status for a specific session

**Parameters:**

- `session_id` (str) *(required)*: session_id parameter

**Example:**

```json
{
  "event": "completion:session_status",
  "data": {
    "session_id": "example_session_id"
  }
}
```

---

### Permission Namespace

#### `permission:get_profile`

Handle permission:get_profile event

**Parameters:**

- `level` (str) *(required)*: The permission level/profile name (one of: restricted, standard, trusted, researcher)

**Example:**

```json
{
  "event": "permission:get_profile",
  "data": {
    "level": "example_level"
  }
}
```

---

#### `permission:set_agent`

Handle permission:set_agent event

**Parameters:**

- `agent_id` (str) *(required)*: The agent ID to set permissions for
- `permissions` (dict) *(optional)*: Full permission object (optional)
- `profile` (str) *(optional)*: Base profile to use (optional, defaults: restricted) - default: `restricted`
- `overrides` (dict) *(optional)*: Permission overrides to apply (optional)

**Example:**

```json
{
  "event": "permission:set_agent",
  "data": {
    "agent_id": "example_agent_id"
  }
}
```

---

#### `permission:validate_spawn`

Handle permission:validate_spawn event

**Parameters:**

- `parent_id` (str) *(required)*: The parent agent ID
- `child_permissions` (dict) *(required)*: The requested permissions for the child agent

**Example:**

```json
{
  "event": "permission:validate_spawn",
  "data": {
    "parent_id": "example_parent_id",
    "child_permissions": {
      "key": "value"
    }
  }
}
```

---

#### `permission:get_agent`

Handle permission:get_agent event

**Parameters:**

- `agent_id` (str) *(required)*: The agent ID to query permissions for

**Example:**

```json
{
  "event": "permission:get_agent",
  "data": {
    "agent_id": "example_agent_id"
  }
}
```

---

#### `permission:remove_agent`

Handle permission:remove_agent event

**Parameters:**

- `agent_id` (str) *(required)*: The agent ID to remove permissions for

**Example:**

```json
{
  "event": "permission:remove_agent",
  "data": {
    "agent_id": "example_agent_id"
  }
}
```

---

#### `permission:list_profiles`

Handle permission:list_profiles event

**Parameters:** None

---

### Sandbox Namespace

#### `sandbox:create`

Handle sandbox:create event

**Parameters:**

- `agent_id` (str) *(required)*: The agent ID
- `config` (dict) *(optional)*: Sandbox configuration (optional)
- `mode` (str) *(optional)*: Sandbox isolation mode (optional, default: isolated, allowed: isolated, shared, readonly) - default: `isolated`
- `parent_agent_id` (str) *(optional)*: Parent agent for nested sandboxes (optional)
- `session_id` (str) *(optional)*: Session ID for shared sandboxes (optional)
- `parent_share` (str) *(optional)*: Parent sharing mode (optional)
- `session_share` (bool) *(optional)*: Enable session sharing (optional)

**Example:**

```json
{
  "event": "sandbox:create",
  "data": {
    "agent_id": "example_agent_id"
  }
}
```

---

#### `sandbox:get`

Handle sandbox:get event

**Parameters:**

- `agent_id` (str) *(required)*: The agent ID

**Example:**

```json
{
  "event": "sandbox:get",
  "data": {
    "agent_id": "example_agent_id"
  }
}
```

---

#### `sandbox:remove`

Handle sandbox:remove event

**Parameters:**

- `agent_id` (str) *(required)*: The agent ID
- `force` (bool) *(optional)*: Force removal even with nested children (optional, default: false) - default: `false`

**Example:**

```json
{
  "event": "sandbox:remove",
  "data": {
    "agent_id": "example_agent_id"
  }
}
```

---

#### `sandbox:list`

Handle sandbox:list event

**Parameters:** None

---

#### `sandbox:stats`

Handle sandbox:stats event

**Parameters:** None

---

### Agent Namespace

#### `agent:spawn`

Handle agent:spawn event

**Parameters:**

- `agent_id` (Any) *(required)*: agent_id parameter
- `profile` (Any) *(required)*: profile parameter
- `profile_name` (Any) *(required)*: profile_name parameter
- `composition` (Any) *(required)*: composition parameter
- `session_id` (Any) *(required)*: session_id parameter
- `spawn_mode` (Any) *(optional)*: spawn_mode parameter - default: `fixed`
- `selection_context` (Any) *(optional)*: selection_context parameter
- `task` (Any) *(required)*: task parameter
- `_composition_selection` (Any) *(required)*: _composition_selection parameter
- `enable_tools` (Any) *(optional)*: enable_tools parameter
- `context` (Any) *(required)*: context parameter
- `config` (Any) *(required)*: config parameter
- `permission_profile` (Any) *(optional)*: permission_profile parameter - default: `standard`
- `sandbox_config` (Any) *(optional)*: sandbox_config parameter
- `permission_overrides` (Any) *(optional)*: permission_overrides parameter

**Example:**

```json
{
  "event": "agent:spawn",
  "data": {
    "agent_id": "<Any>",
    "profile": "<Any>",
    "profile_name": "<Any>",
    "composition": "<Any>",
    "session_id": "<Any>",
    "task": "<Any>",
    "_composition_selection": "<Any>",
    "context": "<Any>",
    "config": "<Any>"
  }
}
```

---

#### `agent:terminate`

Handle agent:terminate event

**Parameters:**

- `agent_id` (Any) *(required)*: agent_id parameter
- `force` (Any) *(optional)*: force parameter

**Example:**

```json
{
  "event": "agent:terminate",
  "data": {
    "agent_id": "<Any>"
  }
}
```

---

#### `agent:restart`

Handle agent:restart event

**Parameters:**

- `agent_id` (Any) *(required)*: agent_id parameter

**Example:**

```json
{
  "event": "agent:restart",
  "data": {
    "agent_id": "<Any>"
  }
}
```

---

#### `agent:register`

Handle agent:register event

**Parameters:**

- `agent_id` (Any) *(required)*: agent_id parameter
- `info` (Any) *(optional)*: info parameter

**Example:**

```json
{
  "event": "agent:register",
  "data": {
    "agent_id": "<Any>"
  }
}
```

---

#### `agent:unregister`

Handle agent:unregister event

**Parameters:**

- `agent_id` (Any) *(required)*: agent_id parameter

**Example:**

```json
{
  "event": "agent:unregister",
  "data": {
    "agent_id": "<Any>"
  }
}
```

---

#### `agent:list`

Handle agent:list event

**Parameters:**

- `status` (Any) *(required)*: status parameter

**Example:**

```json
{
  "event": "agent:list",
  "data": {
    "status": "<Any>"
  }
}
```

---

#### `agent:create_identity`

Handle agent:create_identity event

**Parameters:**

- `agent_id` (Any) *(required)*: agent_id parameter
- `identity` (Any) *(optional)*: identity parameter

**Example:**

```json
{
  "event": "agent:create_identity",
  "data": {
    "agent_id": "<Any>"
  }
}
```

---

#### `agent:update_identity`

Handle agent:update_identity event

**Parameters:**

- `agent_id` (Any) *(required)*: agent_id parameter
- `updates` (Any) *(optional)*: updates parameter

**Example:**

```json
{
  "event": "agent:update_identity",
  "data": {
    "agent_id": "<Any>"
  }
}
```

---

#### `agent:remove_identity`

Handle agent:remove_identity event

**Parameters:**

- `agent_id` (Any) *(required)*: agent_id parameter

**Example:**

```json
{
  "event": "agent:remove_identity",
  "data": {
    "agent_id": "<Any>"
  }
}
```

---

#### `agent:list_identities`

Handle agent:list_identities event

**Parameters:** None

---

#### `agent:get_identity`

Handle agent:get_identity event

**Parameters:**

- `agent_id` (Any) *(required)*: agent_id parameter

**Example:**

```json
{
  "event": "agent:get_identity",
  "data": {
    "agent_id": "<Any>"
  }
}
```

---

#### `agent:route_task`

Handle agent:route_task event

**Parameters:**

- `task` (Any) *(optional)*: task parameter

**Example:**

```json
{
  "event": "agent:route_task",
  "data": {}
}
```

---

#### `agent:get_capabilities`

Handle agent:get_capabilities event

**Parameters:**

- `agent_id` (Any) *(required)*: agent_id parameter

**Example:**

```json
{
  "event": "agent:get_capabilities",
  "data": {
    "agent_id": "<Any>"
  }
}
```

---

#### `agent:send_message`

Handle agent:send_message event

**Parameters:**

- `agent_id` (Any) *(required)*: agent_id parameter
- `message` (Any) *(optional)*: message parameter

**Example:**

```json
{
  "event": "agent:send_message",
  "data": {
    "agent_id": "<Any>"
  }
}
```

---

#### `agent:broadcast`

Handle agent:broadcast event

**Parameters:**

- `message` (Any) *(optional)*: message parameter
- `sender` (Any) *(optional)*: sender parameter - default: `system`

**Example:**

```json
{
  "event": "agent:broadcast",
  "data": {}
}
```

---

#### `agent:update_composition`

Handle agent:update_composition event

**Parameters:**

- `agent_id` (Any) *(required)*: agent_id parameter
- `new_composition` (Any) *(required)*: new_composition parameter
- `reason` (Any) *(optional)*: reason parameter - default: `Adaptation required`

**Example:**

```json
{
  "event": "agent:update_composition",
  "data": {
    "agent_id": "<Any>",
    "new_composition": "<Any>"
  }
}
```

---

#### `agent:discover_peers`

Handle agent:discover_peers event

**Parameters:**

- `agent_id` (Any) *(required)*: agent_id parameter
- `capabilities` (Any) *(optional)*: capabilities parameter
- `roles` (Any) *(optional)*: roles parameter

**Example:**

```json
{
  "event": "agent:discover_peers",
  "data": {
    "agent_id": "<Any>"
  }
}
```

---

#### `agent:negotiate_roles`

Handle agent:negotiate_roles event

**Parameters:**

- `participants` (Any) *(optional)*: participants parameter
- `type` (Any) *(optional)*: type parameter - default: `collaborative`
- `context` (Any) *(optional)*: context parameter

**Example:**

```json
{
  "event": "agent:negotiate_roles",
  "data": {}
}
```

---

### Message Namespace

#### `message:subscribe`

Handle message:subscribe event

**Parameters:**

- `agent_id` (Any) *(required)*: agent_id parameter
- `event_types` (Any) *(optional)*: event_types parameter

**Example:**

```json
{
  "event": "message:subscribe",
  "data": {
    "agent_id": "<Any>"
  }
}
```

---

#### `message:unsubscribe`

Handle message:unsubscribe event

**Parameters:**

- `agent_id` (Any) *(required)*: agent_id parameter
- `event_types` (Any) *(optional)*: event_types parameter

**Example:**

```json
{
  "event": "message:unsubscribe",
  "data": {
    "agent_id": "<Any>"
  }
}
```

---

#### `message:publish`

Handle message:publish event

**Parameters:**

- `agent_id` (Any) *(required)*: agent_id parameter
- `event_type` (Any) *(required)*: event_type parameter
- `message` (Any) *(optional)*: message parameter

**Example:**

```json
{
  "event": "message:publish",
  "data": {
    "agent_id": "<Any>",
    "event_type": "<Any>"
  }
}
```

---

#### `message:subscriptions`

Handle message:subscriptions event

**Parameters:**

- `agent_id` (Any) *(required)*: agent_id parameter

**Example:**

```json
{
  "event": "message:subscriptions",
  "data": {
    "agent_id": "<Any>"
  }
}
```

---

#### `message:connect`

Handle message:connect event

**Parameters:**

- `agent_id` (Any) *(required)*: agent_id parameter

**Example:**

```json
{
  "event": "message:connect",
  "data": {
    "agent_id": "<Any>"
  }
}
```

---

#### `message:disconnect`

Handle message:disconnect event

**Parameters:**

- `agent_id` (Any) *(required)*: agent_id parameter

**Example:**

```json
{
  "event": "message:disconnect",
  "data": {
    "agent_id": "<Any>"
  }
}
```

---

### Message Bus Namespace

#### `message_bus:stats`

Handle message_bus:stats event

**Parameters:** None

---

### Orchestration Namespace

#### `orchestration:start`

Handle orchestration:start event

**Parameters:**

- `pattern` (Any) *(required)*: pattern parameter
- `vars` (Any) *(optional)*: vars parameter

**Example:**

```json
{
  "event": "orchestration:start",
  "data": {
    "pattern": "<Any>"
  }
}
```

---

#### `orchestration:message`

Handle orchestration:message event

**Parameters:** None

---

#### `orchestration:status`

Handle orchestration:status event

**Parameters:**

- `orchestration_id` (Any) *(required)*: orchestration_id parameter

**Example:**

```json
{
  "event": "orchestration:status",
  "data": {
    "orchestration_id": "<Any>"
  }
}
```

---

#### `orchestration:terminate`

Handle orchestration:terminate event

**Parameters:**

- `orchestration_id` (Any) *(required)*: orchestration_id parameter

**Example:**

```json
{
  "event": "orchestration:terminate",
  "data": {
    "orchestration_id": "<Any>"
  }
}
```

---

#### `orchestration:list_patterns`

Handle orchestration:list_patterns event

**Parameters:** None

---

#### `orchestration:load_pattern`

Handle orchestration:load_pattern event

**Parameters:**

- `pattern` (Any) *(required)*: pattern parameter

**Example:**

```json
{
  "event": "orchestration:load_pattern",
  "data": {
    "pattern": "<Any>"
  }
}
```

---

#### `orchestration:get_instance`

Handle orchestration:get_instance event

**Parameters:**

- `orchestration_id` (Any) *(required)*: orchestration_id parameter

**Example:**

```json
{
  "event": "orchestration:get_instance",
  "data": {
    "orchestration_id": "<Any>"
  }
}
```

---

### Composition Namespace

#### `composition:compose`

Handle composition:compose event

**Parameters:**

- `name` (Any) *(required)*: name parameter
- `type` (Any) *(required)*: type parameter
- `variables` (Any) *(optional)*: variables parameter

**Example:**

```json
{
  "event": "composition:compose",
  "data": {
    "name": "<Any>",
    "type": "<Any>"
  }
}
```

---

#### `composition:profile`

Handle composition:profile event

**Parameters:**

- `name` (Any) *(required)*: name parameter
- `variables` (Any) *(optional)*: variables parameter

**Example:**

```json
{
  "event": "composition:profile",
  "data": {
    "name": "<Any>"
  }
}
```

---

#### `composition:prompt`

Handle composition:prompt event

**Parameters:**

- `name` (Any) *(required)*: name parameter
- `variables` (Any) *(optional)*: variables parameter

**Example:**

```json
{
  "event": "composition:prompt",
  "data": {
    "name": "<Any>"
  }
}
```

---

#### `composition:validate`

Handle composition:validate event

**Parameters:**

- `name` (Any) *(required)*: name parameter
- `type` (Any) *(required)*: type parameter

**Example:**

```json
{
  "event": "composition:validate",
  "data": {
    "name": "<Any>",
    "type": "<Any>"
  }
}
```

---

#### `composition:discover`

Handle composition:discover event

**Parameters:**

- `metadata_filter` (Any) *(required)*: metadata_filter parameter

**Example:**

```json
{
  "event": "composition:discover",
  "data": {
    "metadata_filter": "<Any>"
  }
}
```

---

#### `composition:list`

Handle composition:list event

**Parameters:**

- `type` (Any) *(optional)*: type parameter - default: `all`

**Example:**

```json
{
  "event": "composition:list",
  "data": {}
}
```

---

#### `composition:get`

Handle composition:get event

**Parameters:**

- `name` (Any) *(required)*: name parameter
- `type` (Any) *(required)*: type parameter

**Example:**

```json
{
  "event": "composition:get",
  "data": {
    "name": "<Any>",
    "type": "<Any>"
  }
}
```

---

#### `composition:reload`

Handle composition:reload event

**Parameters:** None

---

#### `composition:load_tree`

Handle composition:load_tree event

**Parameters:**

- `name` (Any) *(required)*: name parameter
- `max_depth` (Any) *(optional)*: max_depth parameter - default: `5`

**Example:**

```json
{
  "event": "composition:load_tree",
  "data": {
    "name": "<Any>"
  }
}
```

---

#### `composition:load_bulk`

Handle composition:load_bulk event

**Parameters:**

- `names` (Any) *(optional)*: names parameter

**Example:**

```json
{
  "event": "composition:load_bulk",
  "data": {}
}
```

---

#### `composition:select`

Handle composition:select event

**Parameters:**

- `agent_id` (Any) *(optional)*: agent_id parameter - default: `unknown`
- `role` (Any) *(required)*: role parameter
- `capabilities` (Any) *(optional)*: capabilities parameter
- `task_description` (Any) *(required)*: task_description parameter
- `preferred_style` (Any) *(required)*: preferred_style parameter
- `context_variables` (Any) *(optional)*: context_variables parameter
- `requirements` (Any) *(optional)*: requirements parameter
- `max_suggestions` (Any) *(optional)*: max_suggestions parameter - default: `1`

**Example:**

```json
{
  "event": "composition:select",
  "data": {
    "role": "<Any>",
    "task_description": "<Any>",
    "preferred_style": "<Any>"
  }
}
```

---

#### `composition:suggest`

Handle composition:suggest event

**Parameters:**

- `agent_id` (Any) *(optional)*: agent_id parameter - default: `unknown`
- `role` (Any) *(required)*: role parameter
- `capabilities` (Any) *(optional)*: capabilities parameter
- `task_description` (Any) *(required)*: task_description parameter
- `preferred_style` (Any) *(required)*: preferred_style parameter
- `context_variables` (Any) *(optional)*: context_variables parameter
- `requirements` (Any) *(optional)*: requirements parameter
- `max_suggestions` (Any) *(optional)*: max_suggestions parameter - default: `3`

**Example:**

```json
{
  "event": "composition:suggest",
  "data": {
    "role": "<Any>",
    "task_description": "<Any>",
    "preferred_style": "<Any>"
  }
}
```

---

#### `composition:validate_context`

Handle composition:validate_context event

**Parameters:**

- `composition_name` (Any) *(required)*: composition_name parameter
- `context` (Any) *(optional)*: context parameter

**Example:**

```json
{
  "event": "composition:validate_context",
  "data": {
    "composition_name": "<Any>"
  }
}
```

---

#### `composition:capabilities`

Handle composition:capabilities event

**Parameters:**

- `group` (Any) *(required)*: group parameter

**Example:**

```json
{
  "event": "composition:capabilities",
  "data": {
    "group": "<Any>"
  }
}
```

---

#### `composition:get_path`

Handle composition:get_path event

**Parameters:**

- `full_name` (Any) *(required)*: full_name parameter

**Example:**

```json
{
  "event": "composition:get_path",
  "data": {
    "full_name": "<Any>"
  }
}
```

---

#### `composition:get_metadata`

Handle composition:get_metadata event

**Parameters:**

- `full_name` (Any) *(required)*: full_name parameter

**Example:**

```json
{
  "event": "composition:get_metadata",
  "data": {
    "full_name": "<Any>"
  }
}
```

---

#### `composition:rebuild_index`

Handle composition:rebuild_index event

**Parameters:**

- `repository_id` (Any) *(optional)*: repository_id parameter - default: `local`

**Example:**

```json
{
  "event": "composition:rebuild_index",
  "data": {}
}
```

---

#### `composition:index_file`

Handle composition:index_file event

**Parameters:**

- `file_path` (Any) *(required)*: file_path parameter

**Example:**

```json
{
  "event": "composition:index_file",
  "data": {
    "file_path": "<Any>"
  }
}
```

---

#### `composition:create`

Handle composition:create event

**Parameters:**

- `name` (Any) *(required)*: name parameter
- `type` (Any) *(optional)*: type parameter - default: `profile`
- `extends` (Any) *(optional)*: extends parameter - default: `base_agent`
- `description` (Any) *(optional)*: description parameter
- `author` (Any) *(optional)*: author parameter - default: `dynamic_agent`
- `metadata` (Any) *(optional)*: metadata parameter
- `components` (Any) *(required)*: components parameter
- `config` (Any) *(optional)*: config parameter
- `role` (Any) *(optional)*: role parameter - default: `assistant`
- `model` (Any) *(optional)*: model parameter - default: `sonnet`
- `capabilities` (Any) *(optional)*: capabilities parameter
- `tools` (Any) *(optional)*: tools parameter
- `prompt` (Any) *(required)*: prompt parameter
- `agent_id` (Any) *(required)*: agent_id parameter

**Example:**

```json
{
  "event": "composition:create",
  "data": {
    "name": "<Any>",
    "components": "<Any>",
    "prompt": "<Any>",
    "agent_id": "<Any>"
  }
}
```

---

### Conversation Namespace

#### `conversation:list`

Handle conversation:list event

**Parameters:**

- `limit` (Any) *(optional)*: limit parameter - default: `100`
- `offset` (Any) *(optional)*: offset parameter
- `sort_by` (Any) *(optional)*: sort_by parameter - default: `last_timestamp`
- `reverse` (Any) *(optional)*: reverse parameter - default: `True`
- `start_date` (Any) *(required)*: start_date parameter
- `end_date` (Any) *(required)*: end_date parameter

**Example:**

```json
{
  "event": "conversation:list",
  "data": {
    "start_date": "<Any>",
    "end_date": "<Any>"
  }
}
```

---

#### `conversation:search`

Handle conversation:search event

**Parameters:**

- `query` (Any) *(optional)*: query parameter
- `limit` (Any) *(optional)*: limit parameter - default: `50`
- `search_in` (Any) *(optional)*: search_in parameter

**Example:**

```json
{
  "event": "conversation:search",
  "data": {}
}
```

---

#### `conversation:get`

Handle conversation:get event

**Parameters:**

- `session_id` (Any) *(required)*: session_id parameter
- `limit` (Any) *(optional)*: limit parameter - default: `1000`
- `offset` (Any) *(optional)*: offset parameter
- `conversation_id` (Any) *(required)*: conversation_id parameter

**Example:**

```json
{
  "event": "conversation:get",
  "data": {
    "session_id": "<Any>",
    "conversation_id": "<Any>"
  }
}
```

---

#### `conversation:export`

Handle conversation:export event

**Parameters:**

- `session_id` (Any) *(required)*: session_id parameter
- `format` (Any) *(optional)*: format parameter - default: `markdown`

**Example:**

```json
{
  "event": "conversation:export",
  "data": {
    "session_id": "<Any>"
  }
}
```

---

#### `conversation:stats`

Handle conversation:stats event

**Parameters:** None

---

#### `conversation:active`

Handle conversation:active event

**Parameters:**

- `max_lines` (Any) *(optional)*: max_lines parameter - default: `100`
- `max_age_hours` (Any) *(optional)*: max_age_hours parameter - default: `2160`

**Example:**

```json
{
  "event": "conversation:active",
  "data": {}
}
```

---

#### `conversation:acquire_lock`

Handle conversation:acquire_lock event

**Parameters:**

- `request_id` (Any) *(required)*: request_id parameter
- `conversation_id` (Any) *(required)*: conversation_id parameter
- `metadata` (Any) *(optional)*: metadata parameter

**Example:**

```json
{
  "event": "conversation:acquire_lock",
  "data": {
    "request_id": "<Any>",
    "conversation_id": "<Any>"
  }
}
```

---

#### `conversation:release_lock`

Handle conversation:release_lock event

**Parameters:**

- `request_id` (Any) *(required)*: request_id parameter

**Example:**

```json
{
  "event": "conversation:release_lock",
  "data": {
    "request_id": "<Any>"
  }
}
```

---

#### `conversation:fork_detected`

Handle conversation:fork_detected event

**Parameters:**

- `request_id` (Any) *(required)*: request_id parameter
- `expected_conversation_id` (Any) *(required)*: expected_conversation_id parameter
- `actual_conversation_id` (Any) *(required)*: actual_conversation_id parameter

**Example:**

```json
{
  "event": "conversation:fork_detected",
  "data": {
    "request_id": "<Any>",
    "expected_conversation_id": "<Any>",
    "actual_conversation_id": "<Any>"
  }
}
```

---

#### `conversation:lock_status`

Handle conversation:lock_status event

**Parameters:**

- `conversation_id` (Any) *(required)*: conversation_id parameter

**Example:**

```json
{
  "event": "conversation:lock_status",
  "data": {
    "conversation_id": "<Any>"
  }
}
```

---

### Injection Namespace

#### `injection:status`

Handle injection:status event

**Parameters:** None

---

#### `injection:inject`

Handle injection:inject event

**Parameters:**

- `mode` (Any) *(optional)*: mode parameter - default: `next`
- `position` (Any) *(optional)*: position parameter - default: `before_prompt`
- `content` (Any) *(optional)*: content parameter
- `session_id` (Any) *(required)*: session_id parameter
- `priority` (Any) *(optional)*: priority parameter - default: `normal`
- `metadata` (Any) *(optional)*: metadata parameter

**Example:**

```json
{
  "event": "injection:inject",
  "data": {
    "session_id": "<Any>"
  }
}
```

---

#### `injection:queue`

Handle injection:queue event

**Parameters:** None

---

#### `injection:batch`

Handle injection:batch event

**Parameters:**

- `injections` (Any) *(optional)*: injections parameter

**Example:**

```json
{
  "event": "injection:batch",
  "data": {}
}
```

---

#### `injection:list`

Handle injection:list event

**Parameters:**

- `session_id` (Any) *(required)*: session_id parameter

**Example:**

```json
{
  "event": "injection:list",
  "data": {
    "session_id": "<Any>"
  }
}
```

---

#### `injection:clear`

Handle injection:clear event

**Parameters:**

- `session_id` (Any) *(required)*: session_id parameter
- `mode` (Any) *(required)*: mode parameter

**Example:**

```json
{
  "event": "injection:clear",
  "data": {
    "session_id": "<Any>",
    "mode": "<Any>"
  }
}
```

---

#### `injection:process_result`

Handle injection:process_result event

**Parameters:**

- `request_id` (Any) *(required)*: request_id parameter
- `result` (Any) *(optional)*: result parameter
- `injection_metadata` (Any) *(optional)*: injection_metadata parameter

**Example:**

```json
{
  "event": "injection:process_result",
  "data": {
    "request_id": "<Any>"
  }
}
```

---

#### `injection:execute`

Handle injection:execute event

**Parameters:**

- `session_id` (Any) *(required)*: session_id parameter
- `content` (Any) *(required)*: content parameter
- `request_id` (Any) *(required)*: request_id parameter
- `target_sessions` (Any) *(optional)*: target_sessions parameter
- `model` (Any) *(optional)*: model parameter - default: `claude-cli/sonnet`
- `priority` (Any) *(optional)*: priority parameter - default: `normal`
- `injection_type` (Any) *(optional)*: injection_type parameter - default: `system_reminder`

**Example:**

```json
{
  "event": "injection:execute",
  "data": {
    "session_id": "<Any>",
    "content": "<Any>",
    "request_id": "<Any>"
  }
}
```

---

### File Namespace

#### `file:read`

Handle file:read event

**Parameters:**

- `path` (str) *(required)*: The file path to read (required)
- `encoding` (str) *(optional)*: File encoding (default: utf-8) - default: `utf-8`
- `binary` (bool) *(optional)*: Read as binary data (default: false) - default: `false`

**Example:**

```json
{
  "event": "file:read",
  "data": {
    "path": "example_path"
  }
}
```

---

#### `file:write`

Handle file:write event

**Parameters:**

- `path` (str) *(required)*: The file path to write (required)
- `content` (str) *(required)*: The content to write (required)
- `encoding` (str) *(optional)*: File encoding (default: utf-8) - default: `utf-8`
- `create_backup` (bool) *(optional)*: Create backup before writing (default: true) - default: `true`
- `binary` (bool) *(optional)*: Write binary data (content should be hex string) (default: false) - default: `false`

**Example:**

```json
{
  "event": "file:write",
  "data": {
    "path": "example_path",
    "content": "example_content"
  }
}
```

---

#### `file:backup`

Handle file:backup event

**Parameters:**

- `path` (str) *(required)*: The file path to backup (required)
- `backup_name` (str) *(optional)*: Custom backup name (optional, auto-generated if not provided)

**Example:**

```json
{
  "event": "file:backup",
  "data": {
    "path": "example_path"
  }
}
```

---

#### `file:rollback`

Handle file:rollback event

**Parameters:**

- `path` (str) *(required)*: The file path to rollback (required)
- `backup_name` (str) *(optional)*: Specific backup to restore (optional, uses latest if not provided)

**Example:**

```json
{
  "event": "file:rollback",
  "data": {
    "path": "example_path"
  }
}
```

---

#### `file:list`

Handle file:list event

**Parameters:**

- `path` (str) *(required)*: The directory path to list (required)
- `pattern` (str) *(optional)*: Filename pattern to match (optional) - default: `*`
- `recursive` (bool) *(optional)*: Include subdirectories (default: false) - default: `false`
- `include_hidden` (bool) *(optional)*: Include hidden files (default: false) - default: `false`

**Example:**

```json
{
  "event": "file:list",
  "data": {
    "path": "example_path"
  }
}
```

---

#### `file:validate`

Handle file:validate event

**Parameters:**

- `path` (str) *(required)*: The file path to validate (required)
- `check_writable` (bool) *(optional)*: Check if file is writable (default: false) - default: `false`
- `check_content` (str) *(optional)*: Validate file contains specific content (optional)

**Example:**

```json
{
  "event": "file:validate",
  "data": {
    "path": "example_path"
  }
}
```

---

### Config Namespace

#### `config:get`

Handle config:get event

**Parameters:**

- `key` (str) *(required)*: Configuration key path (e.g., 'daemon.log_level') (required)
- `config_type` (str) *(required)*: Type of config ('daemon', 'composition', 'schema', 'capabilities')
- `file_path` (str) *(optional)*: Specific config file path (optional)

**Example:**

```json
{
  "event": "config:get",
  "data": {
    "key": "example_key",
    "config_type": "example_config_type"
  }
}
```

---

#### `config:set`

Handle config:set event

**Parameters:**

- `key` (str) *(required)*: Configuration key path (e.g., 'daemon.log_level') (required)
- `value` (any) *(required)*: Value to set (required)
- `config_type` (str) *(required)*: Type of config ('daemon', 'composition', 'schema', 'capabilities')
- `file_path` (str) *(optional)*: Specific config file path (optional)
- `create_backup` (bool) *(optional)*: Create backup before modification (default: true) - default: `true`

**Example:**

```json
{
  "event": "config:set",
  "data": {
    "key": "example_key",
    "value": "<any>",
    "config_type": "example_config_type"
  }
}
```

---

#### `config:validate`

Handle config:validate event

**Parameters:**

- `config_type` (str) *(required)*: Type of config to validate ('daemon', 'composition', 'schema', 'capabilities')
- `file_path` (str) *(optional)*: Specific config file path (optional)
- `schema_path` (str) *(optional)*: Path to validation schema (optional)

**Example:**

```json
{
  "event": "config:validate",
  "data": {
    "config_type": "example_config_type"
  }
}
```

---

#### `config:reload`

Handle config:reload event

**Parameters:**

- `component` (str) *(required)*: Component to reload ('daemon', 'plugins', 'compositions', 'all')

**Example:**

```json
{
  "event": "config:reload",
  "data": {
    "component": "example_component"
  }
}
```

---

#### `config:backup`

Handle config:backup event

**Parameters:**

- `config_type` (str) *(required)*: Type of config to backup (required)
- `file_path` (str) *(optional)*: Specific config file path (optional)
- `backup_name` (str) *(optional)*: Custom backup name (optional)

**Example:**

```json
{
  "event": "config:backup",
  "data": {
    "config_type": "example_config_type"
  }
}
```

---

#### `config:rollback`

Handle config:rollback event

**Parameters:**

- `config_type` (str) *(required)*: Type of config to rollback (required)
- `file_path` (str) *(optional)*: Specific config file path (optional)
- `backup_name` (str) *(optional)*: Specific backup to restore (optional, uses latest if not provided)

**Example:**

```json
{
  "event": "config:rollback",
  "data": {
    "config_type": "example_config_type"
  }
}
```

---

## Common Workflows

### Multi-turn Conversation
```bash
# First message - no session_id
{"event": "completion:async", "data": {"prompt": "Hello", "model": "claude-cli/sonnet"}}
# Returns: request_id and creates file with NEW session_id

# Continue conversation using previous session_id
{"event": "completion:async", "data": {
  "prompt": "What did we just discuss?",
  "model": "claude-cli/sonnet",
  "session_id": "session-id-from-previous-response"
}}
```

## Best Practices

1. **Event Discovery**: Use `system:discover` to list all available events
2. **Event Help**: Use `system:help` to get detailed parameter information
3. **Error Handling**: Check response status and handle errors appropriately
4. **Async Operations**: Many operations are asynchronous and return immediately

---
Generated on 2025-07-02 08:19:18