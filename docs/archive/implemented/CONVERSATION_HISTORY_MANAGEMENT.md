# Conversation History Management in KSI

## Overview

KSI implements provider-aware conversation history management to support both stateful and stateless LLM providers efficiently.

## Provider Types

### Stateful Providers
- **claude-cli**: Maintains conversation state internally using `--resume` flag
- These providers handle their own conversation history
- KSI only needs to pass the session ID

### Stateless Providers  
- **OpenAI API**: Requires full conversation history with each request
- **Anthropic API**: Requires full conversation history with each request
- **gemini-cli**: Currently stateless, requires full history
- **All other LiteLLM providers**: Assume stateless by default

## Implementation

### Bidirectional Logging

KSI logs both user requests and assistant responses to enable full conversation reconstruction:

```
var/logs/responses/{session_id}.jsonl
```

Each line in the JSONL file is either:
- **User message**: `{"type": "user", "timestamp": "...", "content": "...", ...}`
- **Assistant response**: Standard completion response format

### Code Components

1. **save_completion_request()** - Saves user messages when using stateless providers
2. **load_conversation_for_provider()** - Reconstructs conversation history from logs
3. **Provider detection** - Automatically determines if a provider is stateful or stateless

### Flow for Stateless Providers

1. Agent sends completion request with session_id
2. System checks if provider is stateless (e.g., OpenAI)
3. If stateless and session exists:
   - Save the new user message to session log
   - Load full conversation history from log
   - Send complete history + new message to provider
4. Save assistant response to session log

### Flow for Stateful Providers

1. Agent sends completion request with session_id
2. System checks if provider is stateful (e.g., claude-cli)
3. If stateful:
   - Skip saving user message (provider tracks it)
   - Skip loading history (provider maintains it)
   - Pass session_id to provider via `--resume` flag
4. Save assistant response to session log (for reference)

## Benefits

- **Efficiency**: Stateful providers don't receive redundant history
- **Compatibility**: Stateless providers get required context
- **Transparency**: Agents don't need to know provider differences
- **Persistence**: All conversations are logged for analysis/export

## Session Files

Session files contain a complete record of the conversation:

```jsonl
{"type": "user", "timestamp": "2025-07-15T10:00:00Z", "content": "Hello", "request_id": "req_123"}
{"type": "claude", "timestamp": "2025-07-15T10:00:02Z", "result": "Hello! How can I help?", ...}
{"type": "user", "timestamp": "2025-07-15T10:01:00Z", "content": "What's the weather?", ...}
{"type": "claude", "timestamp": "2025-07-15T10:01:03Z", "result": "I don't have access to...", ...}
```

## Adding New Providers

To add a new provider:

1. Determine if it's stateful or stateless
2. If stateful, add to the check in `load_conversation_for_provider()`:
   ```python
   if model.startswith(("claude-cli/", "new-stateful-provider/")):
       return []  # Don't load history
   ```
3. If stateless, no changes needed - it will automatically get history management

## Future Enhancements

- **Context window management**: Prune old messages when approaching token limits
- **Conversation summarization**: Compress old exchanges to fit more history
- **Provider capability registry**: Formalize provider capabilities beyond stateful/stateless

---

*Created: 2025-07-15*