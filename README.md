# Minimal Claude Process Daemon

A minimal daemon for managing Claude processes with conversation continuity.

## Architecture

- **daemon.py**: Minimal async daemon that:
  - Spawns `claude` processes with prompts
  - Tracks sessionId for `--resume` flag
  - Supports hot-reloading Python modules (optional)
  
- **chat.py**: Simple chat interface to interact with Claude

- **claude_modules/**: Directory where Claude can write Python modules (optional)

## Prerequisites

```bash
# Run setup script to install dependencies
./setup.sh

# This will:
# - Install uv (Python package manager)
# - Configure Python 3.13
# - Install socat (Unix socket communication)
# - Check for claude CLI
```

## Quick Start

1. **Start chatting**:
   ```bash
   uv run python chat.py
   ```
   
   This will:
   - Start the daemon if not running
   - Let you chat with Claude
   - Maintain conversation context via sessionId

2. **How it works**:
   - chat.py sends `SPAWN:prompt` commands to daemon
   - Daemon spawns: `echo "prompt" | claude --model sonnet --print --output-format json --allowedTools "..." | tee sockets/claude_last_output.json`
   - Daemon logs all sessions to `claude_logs/<session-id>.jsonl`
   - Subsequent prompts use `--resume sessionId` for continuity

## Claude Can Extend This

Claude has full control and can:
- Write handler modules in `claude_modules/`
- Use its tools (Bash, Edit, Write) to modify anything
- Spawn new Claude sessions
- Build whatever infrastructure it needs

The daemon intentionally does almost nothing - it's just plumbing for Claude to build upon.

## Session Logs

All conversations are logged in JSONL format to `claude_logs/<session-id>.jsonl`:
```jsonl
{"timestamp": "2024-06-19T13:52:24Z", "type": "human", "content": "Hi Claude!"}
{"timestamp": "2024-06-19T13:52:28Z", "type": "claude", "session_id": "...", "result": "Hello!"}
```

Claude can read and analyze these logs using its tools.

## Environment Variables

- `CLAUDE_DAEMON_SOCKET`: Unix socket path (default: `sockets/claude_daemon.sock`)

## Minimal Module Example

If Claude wants to handle outputs specially, it can write:

```python
# claude_modules/handler.py
def handle_output(output, daemon):
    # Claude decides what to do with outputs
    pass
```

The daemon will automatically load and call this if it exists.