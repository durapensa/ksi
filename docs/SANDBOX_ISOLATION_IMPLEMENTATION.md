# KSI Sandbox Isolation Implementation

## Overview

This document describes the sandbox isolation implementation for KSI agents, particularly focusing on claude-cli subprocess execution and session management.

## Design Decisions

### Sandbox Directory Structure

**Location**: `/tmp/ksi/sandbox/{sandbox_uuid}/`
- Uses sandbox UUID (not agent_id) to ensure uniqueness across agent lifecycles
- Agent IDs may be reused; UUIDs guarantee no sandbox sharing between different agent instances
- Located in `/tmp` to prevent CLAUDE.md inheritance from project root
- No automatic cleanup - sandboxes accumulate for auditing purposes

**Structure**:
```
/tmp/ksi/sandbox/{sandbox_uuid}/
├── .claude/          # Claude session data (managed by claude-cli)
├── tmp/              # Temporary files for claude-cli
├── workspace/        # Agent working directory
├── shared/           # Shared resources
└── exports/          # Agent outputs
```

### Environment Isolation

Claude-cli subprocesses run with minimal, controlled environment:

```python
clean_env = {
    'HOME': os.environ.get('HOME'),  # For claude API keys in ~/.claude/
    'PATH': os.environ.get('PATH'),  # For finding claude binary
    'CLAUDE_TEMP_DIR': f"{sandbox_dir}/tmp",  # Isolate temp files
    'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1',
    'DISABLE_TELEMETRY': '1'
}
```

**Key principles**:
- Start with clean environment (`env -i` equivalent)
- Only pass required environment variables
- No inheritance of KSI-specific configuration
- Explicit telemetry/traffic controls

### Session Management

Claude-cli manages sessions in `~/.claude/projects/` based on working directory:
- Sessions are indexed by normalized sandbox path
- Each sandbox gets its own session history
- Session continuity works as long as sandbox path remains consistent
- No attempt to override claude's session storage location

**Session path example**:
```
~/.claude/projects/-tmp-ksi-sandbox-{uuid}/
└── {session_id}.jsonl
```

### Model Specification

**All models must include provider prefix**:
- ✅ `claude-cli/sonnet`
- ✅ `claude-cli/claude-sonnet-4-20250514`
- ✅ `openai/gpt-4`
- ❌ `sonnet` (missing provider)

**No dynamic prefix addition** - models must be correctly specified at:
1. Component level (in frontmatter)
2. Agent spawn time
3. System configuration defaults

### Breaking Changes

This implementation is a **breaking change**:
- No migration path from `var/sandbox/` to `/tmp/ksi/sandbox/`
- Existing agents will lose their sandboxes
- All components must be updated with full model specifications
- Sandbox paths in any stored state become invalid

## Implementation Details

### 1. Sandbox Manager Updates

```python
# In ksi_common/sandbox_manager.py
class SandboxManager:
    def __init__(self):
        self.sandbox_root = Path("/tmp/ksi/sandbox")
        # Remove all var/sandbox references
```

### 2. Claude CLI Provider Updates

```python
# In claude_cli_litellm_provider.py
async def _run_claude_async_with_progress(...):
    # Set working directory
    working_dir = Path(sandbox_dir) if sandbox_dir else Path.cwd()
    
    # Create clean environment
    clean_env = {
        'HOME': os.environ.get('HOME'),
        'PATH': os.environ.get('PATH'),
        'CLAUDE_TEMP_DIR': str(working_dir / "tmp"),
        'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1',
        'DISABLE_TELEMETRY': '1'
    }
    
    # Ensure temp directory exists
    if sandbox_dir:
        (working_dir / "tmp").mkdir(exist_ok=True)
    
    # Execute with clean environment
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(working_dir),
        env=clean_env  # Use clean env, not os.environ
    )
```

### 3. Component Model Updates

All components must be updated to include provider prefix:

```yaml
# Before:
model: sonnet

# After:
model: claude-cli/sonnet
```

### 4. Configuration Updates

```python
# In ksi_common/constants.py
DEFAULT_MODEL = "claude-cli/claude-sonnet-4-20250514"  # Full prefix

# In ksi_common/config.py
completion_default_model: str = DEFAULT_MODEL
summary_default_model: str = DEFAULT_MODEL
semantic_eval_default_model: str = DEFAULT_MODEL
```

## Testing Considerations

1. **Session Persistence**: Test that conversations continue across multiple completion:async calls
2. **Environment Isolation**: Verify no KSI configuration leaks into claude-cli environment
3. **Path Consistency**: Ensure sandbox paths remain stable for session continuity
4. **Model Resolution**: Verify all model specifications include provider prefix

## Security Considerations

1. **No Path Traversal**: Sandbox paths use UUIDs, preventing directory traversal attacks
2. **Clean Environment**: Minimal environment prevents configuration/secret leakage
3. **Isolated Temp Files**: Each sandbox has its own tmp/ directory
4. **No Cross-Agent Access**: UUID-based paths prevent agents from accessing each other's data

## Future Considerations

1. **Cleanup Strategy**: May need periodic cleanup of `/tmp/ksi/sandbox/` 
2. **Quota Management**: Monitor /tmp usage if many agents are spawned
3. **Session Export**: Consider ability to export/archive agent sessions
4. **Audit Trail**: Sandbox preservation enables post-execution analysis

## Current Status (2025-08-03)

### Completed ✅
- [x] Architecture designed and documented
- [x] Sandbox manager updated for /tmp/ksi/sandbox
- [x] Claude CLI provider uses clean environment with auth variables
- [x] LiteLLM integration uses sandbox UUID
- [x] Session resolution race condition fixed
- [x] Model name mapping implemented for claude CLI
- [x] Basic functionality tested and working

### Working Features
- Claude CLI authentication in subprocess environment
- Model name mapping (e.g., claude-sonnet-4-20250514 → sonnet)
- Basic agent request/response flow
- Some form of session continuity (agents remember context)

### Known Issues
- Sandbox directories not being created in /tmp/ksi/sandbox
- Claude CLI using default home directory for sessions
- Different session IDs generated for each request
- litellm.py needs update to create sandboxes based on sandbox_uuid

## Migration Notes

**This is a breaking change** - no backward compatibility:
1. Stop daemon before updating
2. Update all code references from `var/sandbox/` to `/tmp/ksi/sandbox/`
3. Update all component model specifications to include provider prefix
4. Restart daemon - existing agents will not have access to old sandboxes
5. Consider backing up `var/sandbox/` if historical data needed