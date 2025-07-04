# KSI MCP Integration Design

## Overview

This document describes the integration of Model Context Protocol (MCP) servers with KSI daemon, enabling agents to access KSI functionality through MCP tools.

## Transport: Streamable HTTP

Based on MCP specification 2025-06-18, we use **Streamable HTTP** transport:
- Bidirectional communication over single HTTP connection
- Persistent connections with session management
- Built-in retry and caching support

## Architecture: Single Daemon-Managed MCP Server

Instead of spawning per-agent MCP servers, KSI daemon manages a single MCP server that handles all agents.

### Benefits
1. **Unified session management** - One place to track all agent sessions
2. **Resource efficiency** - Single process, single port
3. **Dynamic permissions** - Real-time permission checks per request
4. **Simplified lifecycle** - MCP server lives with daemon

## Configuration Format

Claude Code expects MCP configuration in this format:

```json
{
  "mcpServers": {
    "ksi": {
      "type": "streamable-http",
      "url": "http://localhost:8080",
      "headers": {
        "X-KSI-Agent-ID": "agent_123",
        "X-KSI-Conversation-ID": "conv_456"
      },
      "verifySsl": false,
      "retry": {
        "maxAttempts": 3,
        "backoffMs": 1000
      }
    }
  }
}
```

### Key Fields
- `type`: Must be "streamable-http" (not "transport")
- `url`: MCP server endpoint
- `headers`: Custom headers for agent identification

## Session Management

### Full vs Thin Handshake
1. **First completion**: Full tool schemas sent (hundreds of tokens)
2. **Subsequent completions**: Only tool availability (dozens of tokens)

The MCP server tracks sessions via:
- Headers (`X-KSI-Agent-ID`, `X-KSI-Conversation-ID`)
- Internal session database (persists across daemon restarts in `mcp_sessions.db`)

### Session Flow
```
Agent spawn → Generate MCP config with headers
├─ Completion 1 → Full handshake → Server caches session in memory and DB
├─ Completion 2 → Thin handshake (minimal tool descriptions)
├─ Completion 3 → Thin handshake (minimal tool descriptions)
└─ Agent terminate → Clean up MCP config file
```

### Token Usage Optimization
The thin handshake dramatically reduces token usage:
- **Full handshake**: ~3000-5000 cache creation tokens (full tool schemas)
- **Thin handshake**: ~500-1000 cache creation tokens (minimal descriptions)

Token usage is logged for analysis:
```json
{
  "event": "Completion token usage",
  "has_mcp": true,
  "input_tokens": 17,
  "cache_creation_tokens": 3314,  // High for full handshake
  "cache_read_tokens": 45662,
  "output_tokens": 306
}
```

## Permission Model

The MCP server enforces KSI permissions dynamically:

1. **Extract agent identity** from request headers
2. **Lookup permissions** from KSI daemon state
3. **Filter tools** based on allowed_tools/modules
4. **Generate response** with only permitted tools

Example permission flow:
```python
# In MCP server
async def get_agent_tools(request):
    agent_id = request.headers.get("X-KSI-Agent-ID")
    
    # Get agent's current permissions
    permissions = await ksi_client.send_event(
        "permission:get_agent",
        {"agent_id": agent_id}
    )
    
    # Filter available tools
    return filter_tools_by_permissions(all_tools, permissions)
```

## Implementation Components

### 1. MCP Service Module
`ksi_daemon/mcp/mcp_service.py`
- Starts/stops MCP server with daemon
- Manages server lifecycle
- Handles configuration

### 2. Dynamic MCP Server
`ksi_daemon/mcp/dynamic_server.py`
- FastMCP-based implementation
- Permission-aware tool generation
- Session management with thin handshakes

### 3. Provider Integration
`ksi_daemon/completion/claude_cli_litellm_provider.py`
- Generates MCP configs per completion
- Passes agent/conversation IDs in headers

## Tool Naming Convention

KSI events are exposed as MCP tools with consistent naming:
- Event: `system:health`
- Tool: `ksi_system_health`

Special tools:
- `ksi_raw_event` - Direct event access (restricted to trusted profiles)

## Error Handling

The MCP server handles:
- Invalid agent IDs → 401 Unauthorized
- Missing permissions → 403 Forbidden  
- KSI connection errors → 503 Service Unavailable
- Invalid requests → 400 Bad Request

## Monitoring

MCP tool usage is logged for debugging:
- Tool invocations with agent context
- Permission checks and results
- Session handshake types (full/thin)
- Error conditions

## Future Enhancements

1. **WebSocket upgrade** for lower latency
2. **Tool result caching** for repeated queries
3. **Batch tool operations** for efficiency
4. **MCP push notifications** for async events

## Security Considerations

1. **No external access** - MCP server binds to localhost only
2. **Agent isolation** - Each agent sees only its permitted tools
3. **Session validation** - Cached sessions verified against current permissions
4. **Audit logging** - All tool usage tracked with agent attribution