# KSI Direct Socket Communication Patterns

Documentation of reliable socket communication patterns discovered during experimental phase.

## Overview

Direct Unix socket communication with KSI daemon has proven more reliable than EventClient wrapper, providing immediate access to all daemon capabilities without discovery timeouts.

## Socket Connection Pattern

```bash
# Basic command structure
echo '{"event": "EVENT_NAME", "data": {DATA_OBJECT}}' | nc -U var/run/daemon.sock
```

## Proven Working Patterns

### 1. System Health Check
```bash
echo '{"event": "system:health", "data": {}}' | nc -U var/run/daemon.sock
```

**Response Format:**
```json
{
  "event": "system:health",
  "data": {
    "status": "healthy",
    "uptime": 1566.5,
    "version": "3.0.0",
    "modules_loaded": 25,
    "modules": ["ksi_daemon.event_system", ...],
    "services_registered": 0,
    "events_registered": 155,
    "background_tasks": 3
  },
  "count": 1,
  "correlation_id": null,
  "timestamp": 1905187.85111775
}
```

### 2. Agent Lifecycle Management

#### Agent Spawn
```bash
echo '{"event": "agent:spawn", "data": {"profile": "base_single_agent", "agent_id": "test_agent_1"}}' | nc -U var/run/daemon.sock
```

**Response Format:**
```json
{
  "event": "agent:spawn",
  "data": {
    "agent_id": "test_agent_1",
    "status": "created",
    "profile": "base_single_agent",
    "composition": "base_single_agent",
    "session_id": null,
    "config": {
      "model": "sonnet",
      "role": "assistant",
      "enable_tools": false,
      "expanded_capabilities": ["base", "state_read", "state_write"],
      "allowed_events": ["state:clear", "state:delete", ...],
      "allowed_claude_tools": []
    },
    "originator_agent_id": null,
    "agent_type": "system",
    "purpose": null,
    "metadata": {
      "agent_id": "test_agent_1",
      "spawned_at": 1751823469.8920388,
      "purpose": null
    }
  }
}
```

#### Agent Termination
```bash
echo '{"event": "agent:terminate", "data": {"construct_id": "agent_id", "reason": "Test complete"}}' | nc -U var/run/daemon.sock
```

### 3. Completion System

#### Async Completion Request
```bash
echo '{"event": "completion:async", "data": {"prompt": "Say OK", "model": "claude-cli/sonnet", "construct_id": "agent_id"}}' | nc -U var/run/daemon.sock
```

**Response Format:**
```json
{
  "event": "completion:async",
  "data": {
    "request_id": "a4373e52-848c-404c-a8bd-575218086cfe",
    "status": "queued"
  }
}
```

**Response File Pattern:**
- Response files created in `var/logs/responses/{session_id}.jsonl`
- Session ID is different from input session_id (always new)
- File contains actual completion response:

```json
{
  "ksi": {
    "provider": "claude-cli",
    "request_id": "a4373e52-848c-404c-a8bd-575218086cfe",
    "timestamp": "2025-07-06T17:38:45.004268Z",
    "duration_ms": 5031
  },
  "response": {
    "type": "result",
    "subtype": "success",
    "is_error": false,
    "duration_ms": 3625,
    "result": "Network test successful",
    "session_id": "ff284b11-9dc0-41fa-9039-2fa8eb91a033",
    "total_cost_usd": 0.01566525,
    "usage": {
      "input_tokens": 3,
      "cache_creation_input_tokens": 2907,
      "output_tokens": 53
    }
  }
}
```

### 4. Graph Database Operations

#### Entity Creation
```bash
echo '{"event": "state:entity:create", "data": {"id": "test_entity", "type": "test", "properties": {"name": "Test Entity"}}}' | nc -U var/run/daemon.sock
```

**Response Format:**
```json
{
  "event": "state:entity:create",
  "data": {
    "id": "test_entity",
    "type": "test",
    "created_at": 1751823544.080498,
    "updated_at": 1751823544.080498,
    "properties": {"name": "Test Entity"}
  }
}
```

#### Bulk Entity Creation
```bash
echo '{"event": "state:entity:bulk_create", "data": {"entities": [{"type": "user", "id": "user_1", "properties": {"name": "User 1"}}, {"type": "user", "id": "user_2", "properties": {"name": "User 2"}}]}}' | nc -U var/run/daemon.sock
```

**Response Format:**
```json
{
  "event": "state:entity:bulk_create",
  "data": {
    "results": [
      {
        "id": "user_1",
        "type": "user",
        "created_at": 1751823544.080498,
        "updated_at": 1751823544.080498,
        "properties": {"name": "User 1"}
      },
      {
        "id": "user_2", 
        "type": "user",
        "created_at": 1751823544.082614,
        "updated_at": 1751823544.082614,
        "properties": {"name": "User 2"}
      }
    ],
    "total": 2,
    "success": 2,
    "failed": 0
  }
}
```

#### Entity Query
```bash
echo '{"event": "state:entity:query", "data": {"type": "test", "limit": 10}}' | nc -U var/run/daemon.sock
```

#### Relationship Creation
```bash
echo '{"event": "state:relationship:create", "data": {"from": "user_1", "to": "user_2", "type": "friends_with"}}' | nc -U var/run/daemon.sock
```

**Response Format:**
```json
{
  "event": "state:relationship:create",
  "data": {
    "status": "created",
    "from": "user_1",
    "to": "user_2",
    "type": "friends_with"
  }
}
```

#### Graph Traversal
```bash
echo '{"event": "state:graph:traverse", "data": {"from": "user_1", "direction": "outgoing", "types": ["friends_with"], "depth": 2, "include_entities": true}}' | nc -U var/run/daemon.sock
```

**Response Format:**
```json
{
  "event": "state:graph:traverse",
  "data": {
    "root": "user_1",
    "nodes": {
      "user_1": {
        "id": "user_1",
        "type": "user",
        "created_at": 1751823544.080498,
        "created_at_iso": "2025-07-06T17:39:04.080498Z",
        "updated_at": 1751823544.080498,
        "updated_at_iso": "2025-07-06T17:39:04.080498Z",
        "properties": {"name": "User 1"}
      },
      "user_2": {
        "id": "user_2",
        "type": "user", 
        "created_at": 1751823544.082614,
        "created_at_iso": "2025-07-06T17:39:04.082614Z",
        "updated_at": 1751823544.082614,
        "updated_at_iso": "2025-07-06T17:39:04.082614Z",
        "properties": {"name": "User 2"}
      }
    },
    "edges": [
      {
        "from": "user_1",
        "to": "user_2",
        "type": "friends_with",
        "created_at": 1751823554.512356,
        "created_at_iso": "2025-07-06T17:39:14.512356Z"
      }
    ],
    "node_count": 2,
    "edge_count": 1
  }
}
```

### 5. Event Log Queries

#### Query Recent Events
```bash
echo '{"event": "event_log:query", "data": {"pattern": ["agent:spawn", "completion:async"], "limit": 5, "reverse": true}}' | nc -U var/run/daemon.sock
```

### 6. Agent Listing
```bash
echo '{"event": "agent:list", "data": {}}' | nc -U var/run/daemon.sock
```

### 7. Conversation Status
```bash
echo '{"event": "conversation:active", "data": {}}' | nc -U var/run/daemon.sock
```

## Response Format Patterns

All responses follow this structure:
```json
{
  "event": "event_name",
  "data": { /* response data */ },
  "count": 1,
  "correlation_id": null,
  "timestamp": 1905187.85111775
}
```

## Error Patterns

### Entity Already Exists
```json
{
  "event": "state:relationship:create",
  "data": {
    "error": "Failed to create relationship (already exists or entities not found)"
  }
}
```

## Performance Characteristics

From baseline testing:
- **System health**: <50ms
- **Agent spawn**: <1s  
- **Entity creation**: <100ms
- **Bulk entity creation**: <200ms for 2 entities
- **Relationship creation**: <100ms
- **Graph traversal**: <100ms for small graphs
- **Completion request**: ~5s (includes Claude API call)

## Python Implementation Pattern

```python
import socket
import json

def send_socket_command(command_dict):
    """Send a command via Unix socket and return response."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect("var/run/daemon.sock")
        
        # Send command
        message = json.dumps(command_dict) + "\n"
        sock.sendall(message.encode())
        
        # Read response
        response = ""
        while True:
            data = sock.recv(4096).decode()
            if not data:
                break
            response += data
            # Look for complete JSON response
            if response.count('{') == response.count('}') and response.count('{') > 0:
                break
                
        return json.loads(response)
    finally:
        sock.close()

# Usage
result = send_socket_command({
    "event": "system:health",
    "data": {}
})
```

## Key Insights

1. **Direct socket is more reliable** than EventClient wrapper
2. **All daemon functionality accessible** via socket events
3. **Consistent response format** across all operations
4. **Session ID flow** works as documented - always new session_id returned
5. **Graph database is fully functional** with entity/relationship CRUD and traversal
6. **Performance is acceptable** for moderate workloads
7. **Error handling is consistent** with clear error messages

## Future Improvements

1. **Connection pooling** for high-frequency operations
2. **Async socket implementation** for better performance
3. **Response streaming** for large result sets
4. **Batch operations** for bulk data operations
5. **EventClient fallback mode** using direct socket as backup

## Usage in Experiments

This pattern enables reliable experimental scripts without EventClient dependency:
- All baseline performance tests can use direct socket
- Graph scale experiments can be implemented
- Agent network analysis is fully supported
- Time-series analytics data collection is possible

The direct socket approach provides the foundation for all future KSI enhancements and client improvements.