# Claude-KSI Interface Options: Comprehensive Analysis

## Executive Summary

We have multiple ways for Claude to interface with KSI, each with different trade-offs:

1. **Raw JSON + nc** (current ksi_prompt.txt)
2. **Python EventClient** (programmatic)
3. **MCP Tools** (native Claude tools)
4. **ksi-cli wrapper** (NEW - restricted Bash)

## Detailed Comparison

### 1. Raw JSON via netcat

**Claude's Usage:**
```bash
echo '{"event": "completion:async", "data": {"prompt": "Hello"}}' | nc -U var/run/daemon.sock
```

**Pros:**
- ✅ Works with minimal Bash access
- ✅ Direct, no abstraction
- ✅ Good for learning/debugging
- ✅ No installation needed

**Cons:**
- ❌ Error-prone JSON construction
- ❌ No validation
- ❌ Manual response parsing
- ❌ No discovery at runtime

**Best For:** Quick tests, debugging, minimal environments

### 2. ksi-cli Wrapper (NEW)

**Claude's Usage:**
```bash
ksi-cli send completion:async --prompt "Hello" --model claude-cli/sonnet
ksi-cli discover
ksi-cli help completion:async
ksi-cli list conversations --limit 5
```

**Pros:**
- ✅ Clean CLI interface
- ✅ Automatic JSON construction
- ✅ Built-in discovery and help
- ✅ Safe for restricted Bash (`--disallowedTools "Bash(!ksi-cli:*)"`)
- ✅ Pretty-printed output
- ✅ Validates before sending

**Cons:**
- ❌ Requires ksi-cli installation
- ❌ Still needs Bash tool access
- ❌ Async responses need polling

**Best For:** Claude with restricted Bash access, production use

### 3. Python EventClient

**Claude's Usage:**
```python
from ksi_client import EventClient

async with EventClient() as client:
    # Auto-discovered namespaces
    result = await client.completion.async_(
        prompt="Hello",
        model="claude-cli/sonnet"
    )
    
    # Or raw send
    result = await client.send_event("state:set", {
        "key": "config",
        "value": {"theme": "dark"}
    })
```

**Pros:**
- ✅ Full IDE support/autocomplete
- ✅ Type safety
- ✅ Async/await patterns
- ✅ Rich discovery
- ✅ Connection management

**Cons:**
- ❌ Requires Python execution
- ❌ More complex setup
- ❌ Not available in all contexts

**Best For:** Development, complex workflows, when code execution available

### 4. MCP Tools

**Claude's Usage (hypothetical):**
```
# Claude sees these as native tools:
result = ksi_send_event(
    event="completion:async",
    data={
        "prompt": "Hello",
        "model": "claude-cli/sonnet"
    }
)

# Or specific tools:
result = ksi_completion_async(
    prompt="Hello",
    model="claude-cli/sonnet"
)
```

**Pros:**
- ✅ Native tool interface
- ✅ No file system needed
- ✅ Automatic validation
- ✅ Tool documentation
- ✅ Safe for multi-tenant

**Cons:**
- ❌ Requires MCP server setup
- ❌ Needs `--mcp-config`
- ❌ More abstraction
- ❌ Not yet implemented

**Best For:** Production Claude deployments, multi-tenant environments

## Interface Selection Matrix

| Context | Recommended | Fallback | Notes |
|---------|-------------|----------|--------|
| Claude Code (interactive) | Python EventClient | ksi-cli | Full power available |
| Claude Code (non-interactive) | ksi-cli | Raw JSON | Depends on tool access |
| Claude + MCP | MCP Tools | - | Cleanest integration |
| Restricted Bash | ksi-cli | - | Safe with wildcards |
| Minimal tools | Raw JSON | - | Always works |
| Development/Testing | Python EventClient | ksi-cli | Best DX |

## Security Considerations

### ksi-cli with Restricted Bash

The `ksi-cli` wrapper is designed to be safe with Claude's restricted Bash:

```bash
# Claude could be given:
--disallowedTools 'Bash(!ksi-cli:*)'

# This allows:
ksi-cli send completion:async --prompt "Hello"
ksi-cli discover
ksi-cli help state:set

# But prevents:
rm -rf /
curl malicious.site
cat /etc/passwd
```

### Benefits of ksi-cli Restriction

1. **Limited Attack Surface**: Only KSI operations allowed
2. **No File System Access**: Can't read/write arbitrary files
3. **No Network Access**: Can't make external requests
4. **Validated Input**: CLI validates before sending to daemon

## Implementation Recommendations

### 1. For Immediate Use (ksi-cli)

The `ksi-cli` wrapper provides the best balance:
- Works with restricted Bash
- Better UX than raw JSON
- No complex setup needed

**Example Claude Prompt:**
```
You have access to the ksi-cli tool for interacting with KSI daemon.
Use it with restricted Bash access.

Common commands:
- ksi-cli send <event> --param value
- ksi-cli discover
- ksi-cli help <event>
- ksi-cli list conversations

Example:
ksi-cli send completion:async --prompt "Hello" --model claude-cli/sonnet
```

### 2. For Future (MCP)

Implement MCP server for cleanest integration:
- No file system needed
- Native tool interface
- Best for production

### 3. Enhanced Discovery

All interfaces should leverage the enhanced metadata:

```python
@enhanced_event_handler(
    "completion:async",
    category=EventCategory.CORE,
    async_response=True,
    typical_duration_ms=5000,
    has_cost=True,
    best_practices=["Include request_id for tracking"]
)
```

This helps Claude understand:
- Which events are expensive
- Which are async
- Expected durations
- Best practices

## Testing Strategy

### 1. Test ksi-cli with Claude

```bash
# Test basic send
ksi-cli send system:health

# Test with parameters
ksi-cli send completion:async \
  --prompt "Test" \
  --model claude-cli/sonnet

# Test discovery
ksi-cli discover --namespace completion

# Test help
ksi-cli help completion:async
```

### 2. Test Restricted Bash

Configure Claude with:
```
--disallowedTools 'Bash(!ksi-cli:*)'
```

Verify only ksi-cli commands work.

### 3. Test Error Handling

```bash
# Invalid event
ksi-cli send invalid:event

# Missing required params
ksi-cli send completion:async

# Invalid JSON
ksi-cli send state:set --value '{invalid'
```

## Conclusion

**Recommended Approach: ksi-cli with Restricted Bash**

The `ksi-cli` wrapper provides:
1. **Safety**: Works with restricted Bash
2. **Usability**: Better than raw JSON
3. **Discovery**: Built-in help and discovery
4. **Flexibility**: Supports all KSI events
5. **Production Ready**: Can be deployed immediately

This gives Claude a powerful but controlled interface to KSI, perfect for autonomous agent orchestration while maintaining security boundaries.