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
# Install socat (required for Unix socket communication)
brew install socat

# Ensure claude CLI is installed and working
claude --help
```

## Quick Start

1. **Start chatting**:
   ```bash
   python3 chat.py
   ```
   
   This will:
   - Start the daemon if not running
   - Let you chat with Claude
   - Maintain conversation context via sessionId

2. **How it works**:
   - Daemon spawns: `echo "prompt" | claude --model sonnet --print --output-format json --allowedTools "..." | socat STDIO UNIX-CONNECT:/tmp/claude_daemon.sock`
   - Claude's JSON output (including sessionId) is captured
   - Subsequent prompts use `--resume sessionId` for continuity

## Claude Can Extend This

Claude has full control and can:
- Write handler modules in `claude_modules/`
- Use its tools (Bash, Edit, Write) to modify anything
- Spawn new Claude sessions
- Build whatever infrastructure it needs

The daemon intentionally does almost nothing - it's just plumbing for Claude to build upon.

## Environment Variables

- `CLAUDE_DAEMON_SOCKET`: Unix socket path (default: `/tmp/claude_daemon.sock`)

## Minimal Module Example

If Claude wants to handle outputs specially, it can write:

```python
# claude_modules/handler.py
def handle_output(output, daemon):
    # Claude decides what to do with outputs
    pass
```

The daemon will automatically load and call this if it exists.