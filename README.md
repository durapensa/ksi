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

## Multi-Agent Capabilities

The daemon now includes multi-agent coordination infrastructure:
- **Agent registration and management** (`REGISTER_AGENT`, `GET_AGENTS`)
- **Inter-agent communication** (`SEND_MESSAGE`) with persistent logging
- **Shared state coordination** (`SET_SHARED`, `GET_SHARED`) across agents
- **Agent profiles** (orchestrator, researcher, coder, analyst) with template-based spawning
- **Task routing** (`ROUTE_TASK`) with capability-based agent selection

**Status**: Infrastructure implemented but requires testing before production use.

## Multi-Claude Orchestrator (NEW)

Enable multiple Claude instances to converse with each other autonomously:

```bash
# Start a debate between Claudes
python orchestrate.py "Should AI have rights?" --mode debate --agents 2

# Monitor conversations in real-time
python monitor_tui.py
```

**Features**:
- **Peer-to-peer Claude conversations** without human intervention
- **Multiple conversation modes**: debate, collaboration, teaching, brainstorming
- **Real-time TUI monitor** showing messages, tool calls, and metrics
- **Event-driven architecture** with no polling
- **Persistent Claude nodes** maintaining conversation context

See [MULTI_CLAUDE_ORCHESTRATOR.md](MULTI_CLAUDE_ORCHESTRATOR.md) for full documentation.

## Claude Can Extend This

Claude has full control and can:
- Write handler modules in `claude_modules/`
- Use its tools (Bash, Edit, Write) to modify anything
- Spawn new Claude sessions
- Build whatever infrastructure it needs
- Coordinate multi-agent workflows using the implemented infrastructure

The daemon provides minimal coordination plumbing - Claude instances handle the sophisticated logic.

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