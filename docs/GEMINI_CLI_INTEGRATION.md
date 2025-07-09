# Gemini CLI Integration for KSI

## Overview
This document describes the integration of Google's Gemini CLI as a completion provider for KSI, implemented as a LiteLLM custom provider.

## Key Differences from Claude CLI
1. **No JSON output format** - Gemini outputs plain text only
2. **No session continuity** - No `--resume` flag or persistent session IDs
3. **No tool control** - No `--allowedTools` or `--disallowedTools` options
4. **Simpler interface** - Fewer configuration options overall
5. **One-shot completions only** - No conversation tracking

## Implementation Details

### Files Created/Modified
- `ksi_daemon/completion/gemini_cli_litellm_provider.py` - Main provider implementation
- `ksi_common/constants.py` - Added `DEFAULT_GEMINI_BIN` with auto-discovery
- `ksi_common/config.py` - Added Gemini-specific settings
- `ksi_daemon/completion/litellm.py` - Added Gemini provider detection

### Configuration
```python
# In ksi_common/config.py
gemini_timeout_attempts: List[int] = [300]  # 5min (simpler than Claude)
gemini_progress_timeout: int = 300           # 5 minutes without progress
gemini_retry_backoff: int = 2                # Seconds between retry attempts
gemini_bin: Optional[str] = DEFAULT_GEMINI_BIN  # Auto-discovered from PATH
```

### Session ID Generation
Since Gemini doesn't provide session IDs, we generate them for response tracking:
```python
gemini_session_id = f"gemini-{uuid.uuid4().hex[:12]}"
```

This allows responses to be saved to files like `var/logs/responses/gemini-0e5cd80c55ce.jsonl`.

## Usage

### Through KSI Daemon
```bash
echo '{"event": "completion:async", "data": {
  "model": "gemini-cli/gemini-2.5-pro",
  "messages": [{"role": "user", "content": "Your prompt here"}],
  "stream": false
}}' | nc -U var/run/daemon.sock
```

### Available Models
- `gemini-cli/gemini-2.5-pro` (default)
- Other Gemini models as supported by the CLI

### Response Format
Gemini responses are wrapped in a JSON structure for LiteLLM compatibility:
```json
{
  "type": "message",
  "content": "The actual Gemini response",
  "is_error": false,
  "model": "gemini-2.5-pro",
  "session_id": "gemini-0e5cd80c55ce",
  "metadata": {
    "provider": "gemini-cli",
    "timestamp": 1752034352.751494,
    "generated_session_id": true
  }
}
```

## Environment Variables
- `KSI_GEMINI_BIN` - Override the auto-discovered Gemini binary path

## Limitations
1. No conversation history/context between calls
2. No structured output - plain text only
3. No tool usage capabilities
4. No streaming support

## Testing
```bash
# Ensure Gemini CLI is installed and in PATH
which gemini

# Test through the provider directly
python -m ksi_daemon.completion.gemini_cli_litellm_provider "Test prompt"

# Test through the daemon
./daemon_control.py restart  # Pick up configuration changes
echo '{"event": "completion:async", "data": {"model": "gemini-cli/gemini-2.5-pro", "messages": [{"role": "user", "content": "Hello"}], "stream": false}}' | nc -U var/run/daemon.sock
```

## Future Enhancements
- Support for Gemini's sandbox mode (`--sandbox` flag)
- Integration with Gemini's checkpointing feature
- Support for YOLO mode for automated workflows
- Better error handling for Gemini-specific errors