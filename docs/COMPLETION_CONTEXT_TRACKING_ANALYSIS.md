# Completion Context Tracking Analysis

## Issue Summary

The completion system was only tracking 1 context in conversation chains, even after sending multiple messages. This investigation revealed multiple interconnected issues.

## Root Causes Identified

### 1. Sandbox Path Conflict (FIXED)
- **Issue**: Double "agents/" prefix in sandbox paths
  - litellm.py: `sandbox_id = f"agents/{sandbox_uuid}"`
  - sandbox_manager.py: `sandbox_path = self.agents_root / agent_id`
  - Result: `var/sandbox/agents/agents/{uuid}/`
- **Fix**: Remove prefix from litellm.py, let sandbox_manager handle path construction

### 2. Sandbox Symlink Conflicts (FIXED)
- **Issue**: FileExistsError when creating symlinks for existing sandboxes
- **Fix**: Added checks for existing symlinks and graceful handling

### 3. Session Continuity Breaking (CORE ISSUE)
- **Issue**: Each completion request creates a NEW session instead of continuing existing one
- **Evidence**:
  - Request 1: Creates session `1e743e54...`
  - Request 2: Sent with session `1e743e54...`, but gets NEW session `ff997d85...`
  - Request 3: Gets another NEW session `d16d27c7...`
- **Impact**: Only the most recent context is tracked because each session starts fresh

## Current State

### What's Working
1. ✅ Sandbox creation and management
2. ✅ Context storage mechanism (when session is maintained)
3. ✅ Context retrieval via conversation summary
4. ✅ Session ID propagation in requests

### What's Not Working
1. ❌ Session continuity - claude-cli creates new sessions instead of continuing existing ones
2. ❌ Context chain building - only 1 context tracked due to session breaks
3. ❌ Sequential completion queueing - works but each gets new session

## Technical Details

### Context Tracking Flow
```
1. Completion request arrives with session_id (or null)
2. Request queued by session for sequential processing
3. Completion processed via litellm/claude-cli
4. Response includes NEW session_id (should be SAME for continuity)
5. Context stored with session_id reference
6. Conversation tracker updated with context reference
```

### The Breaking Point
The issue occurs at step 4 - claude-cli is not recognizing the provided session_id and creates a new session each time. This breaks the context chain.

## Potential Solutions

### 1. Session Directory Investigation
- Check if claude-cli expects sessions in a specific location
- Verify sandbox `.claude` directory is being used correctly
- Ensure session files are persisted between requests

### 2. Claude CLI Provider Analysis
- Review how session_id is passed to claude-cli
- Check if there's a working directory mismatch
- Verify session continuity settings in provider

### 3. Alternative Context Tracking
- Store contexts by agent_id instead of session_id
- Build context chain independent of claude-cli sessions
- Implement session merging when continuity breaks

## Test Results

### Single Message Test
- ✅ Context tracked successfully
- ✅ Session created and maintained

### Multiple Message Test
- ✅ All completions succeed
- ❌ Each creates new session
- ❌ Only 1 context tracked (from most recent session)

### Conversation Locking
- ✅ Queue ensures sequential processing per session
- ❌ But each request gets new session anyway

## Next Steps

1. **Investigate Claude CLI session handling**
   - How does claude-cli determine session continuity?
   - Where are session files stored?
   - What triggers new session creation?

2. **Review Provider Implementation**
   - Check claude_cli_provider.py session handling
   - Verify working directory settings
   - Test session continuity directly

3. **Consider Workarounds**
   - Track contexts by agent_id as fallback
   - Implement session linking/merging
   - Store full conversation history independently

## Conclusion

The context tracking system is architecturally sound but is broken by claude-cli's session handling. Each completion request, despite providing a valid session_id, results in a new session being created. This prevents building a proper context chain for conversation continuity.

The fix requires understanding why claude-cli is not maintaining session continuity and either fixing that behavior or implementing a workaround that tracks contexts independently of claude-cli's session management.