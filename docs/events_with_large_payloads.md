# Events with Large Payloads in KSI

This document identifies events in the KSI codebase that might have large payloads suitable for file-based storage instead of inline JSON.

## Events with File Content

### 1. File Service Events
- **file:read** - Returns file content (up to 10MB limit)
  - Field: `content` - Contains entire file contents
  - Current limit: MAX_FILE_SIZE = 10MB
  - Binary files returned as hex strings
  
- **file:write** - Accepts file content to write
  - Field: `content` - Contains data to write
  - Can be text or binary (hex encoded)
  
- **file:backup/rollback** - File backup operations
  - May contain file content during operations

## Events with LLM/Completion Data

### 2. Completion Service Events
- **completion:async** - LLM completion requests
  - Field: `prompt` - Can contain large prompts/contexts
  - Field: `messages` - Chat history with multiple messages
  - Field: `system_prompt` - System instructions (can be lengthy)

- **completion:response** - LLM completion responses
  - Field: `content` - Model response text
  - Field: `completion` - Full completion data
  - Saved to: `var/logs/responses/{session_id}.jsonl`

### 3. Agent Service Events  
- **agent:spawn** - Agent creation with profiles
  - Field: `composed_prompt` - Full composed agent prompt
  - Field: `system_prompt` - Agent system instructions
  - Field: `profile` - Complete profile configuration
  - Field: `context` - Agent context data

- **agent:message** - Inter-agent messaging
  - Field: `message.content` - Message payload
  - Field: `message.context` - Message context

## Events with Configuration/Composition Data

### 4. Composition Service Events
- **composition:profile** - Compose agent profiles
  - Field: `profile` - Complete composed profile
  - Field: `components` - Array of profile components
  - Field: `system_prompt` - Composed system prompt

- **composition:get** - Retrieve composition definitions
  - Field: `composition` - Full composition structure
  - Field: `components` - Component definitions

### 5. Config Service Events
- **config:get/set** - Configuration management
  - Field: `value` - Configuration data (can be large YAML/JSON)
  - Field: `content` - Full config file content

## Events with Orchestration/Template Data

### 6. Orchestration Service Events
- **orchestration:start** - Start orchestration patterns
  - Field: `pattern` - Full orchestration pattern
  - Field: `agents` - Agent configurations
  - Field: `routing` - Routing rules

- **orchestration:message** - Orchestration messages
  - Field: `message` - Message content
  - Field: `context` - Orchestration context

## Events with State/Historical Data

### 7. State Management Events
- **state:entity:create/update** - Entity state management
  - Field: `properties` - Entity properties (can be JSON)
  - Field: `metadata` - Additional metadata

### 8. Event Log/Historical Events
- **event_log:query** - Query historical events
  - Response: `events` - Array of event objects
  - Can return thousands of events

- **observation:analysis** - Historical analysis results
  - Field: `analysis` - Analysis results
  - Field: `events` - Analyzed event data

## Events with MCP/Tool Data

### 9. MCP Service Events
- **mcp:tool_call** - MCP tool invocations
  - Field: `arguments` - Tool arguments (can be large)
  - Field: `result` - Tool execution results

- **mcp:resource** - MCP resource access
  - Field: `content` - Resource content
  - Field: `data` - Resource data

## Recommendations for File-Based Storage

Events that should consider file-based storage for large payloads:

1. **file:read/write** - Already has 10MB limit, good candidate
2. **completion:async** - Prompts can be very large with context
3. **completion:response** - Already saves to session files
4. **agent:spawn** - System prompts and contexts can be large
5. **composition:profile** - Composed profiles can be extensive
6. **orchestration:start** - Pattern definitions can be complex
7. **event_log:query** - Response arrays can be huge
8. **mcp:tool_call** - Tool results can contain large datasets

## Implementation Pattern

For events with potentially large payloads, consider:

```python
# Instead of inline data:
{
    "event": "completion:async",
    "data": {
        "prompt": "...10KB of text...",  # Large inline
        "session_id": "abc123"
    }
}

# Use file reference:
{
    "event": "completion:async", 
    "data": {
        "prompt_file": "var/tmp/prompts/abc123.txt",  # File reference
        "prompt_size": 10240,  # Size hint
        "session_id": "abc123"
    }
}
```

## Size Thresholds

Suggested thresholds for file-based storage:
- Text content: > 4KB
- JSON/YAML data: > 8KB  
- Binary data: Always use files
- Array responses: > 100 items
- Chat histories: > 10 messages