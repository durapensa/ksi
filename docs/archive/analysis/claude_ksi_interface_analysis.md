# Claude-KSI Interface Analysis

## Overview

This document analyzes the different ways Claude can interface with KSI, considering various execution contexts and tool availability.

## Interface Approaches

### 1. Raw JSON via Socket (Current Approach)

**What Claude Sees:**
```
You have access to KSI daemon via Unix socket. Send JSON events like:
echo '{"event": "completion:async", "data": {"prompt": "Hello"}}' | nc -U var/run/daemon.sock
```

**Requirements:**
- Bash tool with `echo` and `nc` commands
- OR Write tool + execution mechanism
- File system access to socket

**Usage Pattern:**
```python
# Claude would generate and execute:
result = bash('echo \'{"event": "system:health", "data": {}}\' | nc -U var/run/daemon.sock')
response = json.loads(result)
```

**Pros:**
- Works with minimal tool access
- Direct control over communication
- No abstraction layer to debug
- Works in non-interactive `claude -p` mode

**Cons:**
- Manual JSON construction (error-prone)
- No validation before sending
- Response parsing is manual
- Requires understanding of Unix sockets
- No discovery/introspection at runtime

### 2. Python EventClient API

**What Claude Sees:**
```python
from ksi_client import EventClient

async with EventClient() as client:
    # Discovered namespaces with autocomplete
    response = await client.completion.async_(
        prompt="Hello",
        model="claude-cli/sonnet"
    )
```

**Requirements:**
- Python code execution capability
- ksi_client package installed
- Async execution environment

**Usage Pattern:**
```python
# Claude would write Python code:
import asyncio
from ksi_client import EventClient

async def interact_with_ksi():
    async with EventClient() as client:
        # List conversations
        convos = await client.conversation.list(limit=10)
        
        # Send completion
        result = await client.completion.async_(
            prompt="Analyze this data",
            model="claude-cli/sonnet"
        )
        
        return result

result = asyncio.run(interact_with_ksi())
```

**Pros:**
- Type hints and IDE support
- Automatic discovery
- Validation built-in
- Clean async patterns
- Intuitive namespace access

**Cons:**
- Requires Python execution
- Not available in all contexts
- More complex setup
- Async complexity

### 3. MCP (Model Context Protocol) Tools

**What Claude Sees:**
```
You have access to these KSI tools:

ksi_send_event - Send any event to KSI daemon
  Parameters:
    - event (string, required): Event name like 'completion:async'
    - data (object, optional): Event parameters

ksi_completion_async - Request an async completion
  Parameters:
    - prompt (string, required): The prompt text
    - model (string, required): Model to use
    - session_id (string, optional): For conversation continuity
    
ksi_conversation_list - List available conversations
  Parameters:
    - limit (integer, optional): Maximum results
    - offset (integer, optional): Pagination offset
```

**Requirements:**
- MCP server configuration
- `claude --mcp-config` flag
- No direct file system access needed!

**Usage Pattern:**
```python
# Claude would use tools directly:
result = ksi_completion_async(
    prompt="Hello, how are you?",
    model="claude-cli/sonnet"
)

# Or use the flexible raw event tool:
result = ksi_send_event(
    event="state:set",
    data={
        "key": "project_state",
        "value": {"status": "active"},
        "namespace": "projects"
    }
)
```

**Pros:**
- Native tool interface
- No file system access needed
- Automatic parameter validation
- Tool documentation built-in
- Works in restricted environments
- Can be used with `--mcp-config`

**Cons:**
- Requires MCP server setup
- Limited to predefined tools
- Abstraction may hide details
- New/experimental

## Optimal Approach by Context

### 1. Non-Interactive Mode (`claude -p`)

**Best Options:**
1. **MCP Tools** (if `--mcp-config` available)
   - Cleanest interface
   - No file system requirements
   - Full KSI access through tools

2. **Raw JSON + Bash** (fallback)
   - Works with standard tools
   - Requires socket file access
   - More error-prone

### 2. Interactive Claude Code

**Best Option:** Python EventClient
- Full IDE support
- Discovery and validation
- Natural Python patterns
- Best developer experience

### 3. Restricted Environments

**Best Option:** MCP Tools
- No file system access needed
- Controlled through tool permissions
- Safe for multi-tenant environments

## Recommendations for Enhanced Integration

### 1. Improve Event Introspection

Add richer metadata to events:

```python
@event_handler("completion:async")
@event_metadata(
    category="core",
    cost_implication=True,
    async_response=True,
    typical_duration="5-30s",
    related_events=["completion:result", "completion:cancel"]
)
def handle_completion_async(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Request an async completion from an LLM provider.
    
    This event starts an asynchronous completion request. The response
    includes a request_id that can be used to track the completion.
    Results are delivered via the completion:result event.
    
    Args:
        prompt: The prompt text to send to the LLM
        model: Model identifier (e.g., 'claude-cli/sonnet')
        session_id: Optional session ID for conversation continuity
        ...
    
    Returns:
        Dictionary with request_id and status
        
    Examples:
        Basic completion:
            {"prompt": "Hello", "model": "claude-cli/sonnet"}
            
        Continue conversation:
            {"prompt": "Tell me more", "model": "claude-cli/sonnet", 
             "session_id": "abc-123"}
    """
```

### 2. Add Event Relationship Mapping

Help Claude understand event flows:

```python
EVENT_FLOWS = {
    "completion_workflow": {
        "start": "completion:async",
        "monitor": "completion:status",
        "result": "completion:result",
        "cancel": "completion:cancel"
    },
    "conversation_workflow": {
        "list": "conversation:list",
        "get": "conversation:get",
        "search": "conversation:search",
        "export": "conversation:export"
    }
}
```

### 3. Enhanced Discovery Format

Include more context in discovery:

```python
{
    "event": "completion:async",
    "summary": "Request an async completion",
    "category": "core",
    "async": true,
    "response_event": "completion:result",
    "typical_duration_ms": 5000,
    "cost": "varies",
    "parameters": {...},
    "examples": [...],
    "common_errors": [
        {
            "error": "session_not_found",
            "description": "Session ID doesn't exist",
            "solution": "Omit session_id to start new conversation"
        }
    ]
}
```

### 4. Create Helper Prompts for Each Context

```python
# For MCP context
MCP_PROMPT = """
You have KSI tools available. Key tools:
- ksi_send_event: Send any event (most flexible)
- ksi_completion_async: Get LLM completions
- ksi_state_set/get: Manage persistent state

Always check responses for errors.
"""

# For bash context  
BASH_PROMPT = """
Send KSI events via: echo '<json>' | nc -U var/run/daemon.sock
Parse responses with jq if available.
Common pattern: result=$(echo '{"event":"system:health","data":{}}' | nc -U var/run/daemon.sock)
"""

# For Python context
PYTHON_PROMPT = """
Use EventClient for clean async interface:
async with EventClient() as client:
    result = await client.<namespace>.<action>(**params)
"""
```

## Conclusion

The optimal interface depends on Claude's execution context:

1. **MCP Tools** are ideal when available - clean, safe, no file system needed
2. **Raw JSON + Bash** works everywhere but is error-prone
3. **Python EventClient** provides the best DX in code execution contexts

We should:
1. Implement the MCP server for KSI
2. Enhance event metadata and relationships
3. Provide context-specific documentation
4. Test with `claude --mcp-config` to verify MCP approach