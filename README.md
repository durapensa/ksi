# KSI - Minimal Claude Process Daemon

A lightweight daemon system for managing Claude AI processes with conversation continuity and multi-agent orchestration capabilities.

## Features

- 🚀 **Minimal daemon architecture** - Simple Unix socket-based process management
- 💬 **Conversation continuity** - Maintains context across Claude interactions using sessionId
- 🤖 **Multi-agent orchestration** - Enable multiple Claude instances to converse autonomously
- 📊 **Real-time monitoring** - Beautiful TUI for observing multi-Claude conversations
- 🔧 **Extensible** - Claude can write Python modules to extend functionality
- 📝 **Complete logging** - All sessions logged in JSONL format for analysis

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Multi-Claude Orchestrator](#multi-claude-orchestrator)
- [API Reference](#api-reference)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## Installation

### Prerequisites

- Python 3.8 or higher
- [Claude CLI](https://claude.ai/download) installed and configured
- Unix-like operating system (macOS, Linux)
- socat (for socket communication)

### Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/ksi.git
   cd ksi
   ```

2. **Run the setup script**:
   ```bash
   ./setup.sh
   ```
   
   This will:
   - Create a Python virtual environment
   - Install required dependencies (PyYAML, textual)
   - Check for Claude CLI availability
   - Create necessary directories

3. **Manual setup** (if preferred):
   ```bash
   # Create virtual environment
   python3 -m venv .venv
   
   # Activate virtual environment
   source .venv/bin/activate  # On macOS/Linux
   # or
   .venv\Scripts\activate     # On Windows
   
   # Install dependencies
   pip install -r requirements.txt
   ```

### Important Note on Process Isolation

**Do not use `uv run`** - it creates process isolation that breaks Unix socket communication between the daemon and client processes. Always use `python3` directly after activating the virtual environment.

## Quick Start

### Basic Chat Interface

```bash
# Activate virtual environment
source .venv/bin/activate

# Start chatting (daemon starts automatically)
python3 chat.py
```

This will:
- Start the daemon if not running
- Let you chat with Claude
- Maintain conversation context via sessionId

### Multi-Claude Conversations

```bash
# Start a debate between two Claudes
python3 orchestrate.py "Should AI have rights?" --mode debate --agents 2

# In another terminal, monitor the conversation
python3 monitor_tui.py
```

### Available Conversation Modes

- **debate** - Claudes take opposing positions
- **collaboration** - Work together on problems  
- **teaching** - One Claude teaches, others learn
- **brainstorm** - Creative idea generation
- **analysis** - Systematic problem analysis

## Architecture

### Core Components

- **daemon.py** - Minimal async daemon that:
  - Spawns Claude processes with prompts
  - Tracks sessionId for conversation continuity
  - Manages inter-agent communication via message bus
  - Supports hot-reloading of Python modules

- **chat.py** - Simple interface for human-Claude interaction

- **agent_process.py** - Persistent Claude process for multi-agent conversations

- **orchestrate.py** - High-level orchestration for multi-Claude conversations

- **monitor_tui.py** - Real-time TUI for monitoring conversations

### How It Works

1. Daemon receives commands via Unix socket
2. Spawns: `claude --model sonnet --print --output-format json --resume sessionId`
3. Logs all sessions to `claude_logs/<session-id>.jsonl`
4. Uses `--resume sessionId` for conversation continuity

### Multi-Agent Infrastructure

The daemon includes built-in multi-agent coordination:

- **Agent registration** (`REGISTER_AGENT`, `GET_AGENTS`)
- **Inter-agent messaging** (`SEND_MESSAGE`, `PUBLISH`)
- **Shared state** (`SET_SHARED`, `GET_SHARED`)
- **Task routing** (`ROUTE_TASK`)
- **Event-driven message bus** with persistent connections

## Multi-Claude Orchestrator

Enable multiple Claude instances to converse autonomously:

### Quick Examples

```bash
# AI ethics debate
python3 orchestrate.py "AI consciousness and rights" --mode debate --agents 3

# Collaborative problem solving
python3 orchestrate.py "Design a sustainable city" --mode collaboration --agents 4

# Teaching session
python3 orchestrate.py "Explain quantum computing" --mode teaching --agents 2
```

### Features

- **Peer-to-peer conversations** - No human intervention required
- **Rich conversation modes** - Debate, collaborate, teach, brainstorm, analyze
- **Real-time monitoring** - Watch conversations, tool usage, and metrics
- **Event-driven** - Efficient async architecture with no polling
- **Persistent context** - Each Claude maintains conversation history

See [MULTI_CLAUDE_ORCHESTRATOR.md](MULTI_CLAUDE_ORCHESTRATOR.md) for detailed documentation.

## API Reference

### Daemon Commands

The daemon supports ~20 commands organized into functional groups. Use `GET_COMMANDS` to discover all available commands dynamically.

#### Key Commands

| Command | Format | Description | Alias |
|---------|--------|-------------|-------|
| SPAWN | `SPAWN:[mode]:[type]:[session_id]:[model]:[agent_id]:<prompt>` | Unified Claude spawning | S: |
| SPAWN_AGENT | `SPAWN_AGENT:profile:task:context:agent_id` | Profile-based agent spawning | SA: |
| GET_COMMANDS | `GET_COMMANDS` | Get all commands with grouping | - |
| REGISTER_AGENT | `REGISTER_AGENT:id:role:capabilities` | Register an agent | - |
| PUBLISH | `PUBLISH:from:event_type:json_payload` | Publish message to bus | - |
| SUBSCRIBE | `SUBSCRIBE:agent_id:event_type1,event_type2` | Subscribe to events | - |
| SET_SHARED | `SET_SHARED:key:value` | Set shared state | SET: |
| GET_SHARED | `GET_SHARED:key` | Get shared state | GET: |

**Command Groups**: Process Spawning, Agent Management, Communication & Events, State Management, System Management

**Note**: Legacy command formats are auto-detected for backward compatibility.

### Session Logs

All conversations are logged in JSONL format to `claude_logs/<session-id>.jsonl`:

```jsonl
{"timestamp": "2024-06-19T13:52:24Z", "type": "human", "content": "Hi Claude!"}
{"timestamp": "2024-06-19T13:52:28Z", "type": "claude", "session_id": "...", "result": "Hello!"}
```

## Development

### Extending the System

Claude can extend functionality by writing Python modules:

```python
# claude_modules/handler.py
def handle_output(output, daemon):
    # Custom output handling logic
    pass
```

The daemon automatically loads and calls modules in `claude_modules/`.

### Project Structure

```
ksi/
├── daemon.py              # Core daemon
├── chat.py               # Human chat interface
├── agent_process.py      # Persistent Claude process
├── orchestrate.py        # Multi-Claude orchestrator
├── monitor_tui.py        # TUI monitor
├── daemon/               # Modular daemon components
├── claude_modules/       # Extension modules
├── agent_profiles/       # Agent personality profiles
├── claude_logs/          # Session logs
└── tests/               # Test suite
```

### Running Tests

```bash
python3 tests/test_daemon_protocol.py
```

### Environment Variables

- `CLAUDE_DAEMON_SOCKET` - Unix socket path (default: `sockets/claude_daemon.sock`)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built for use with [Claude AI](https://claude.ai)
- TUI powered by [Textual](https://textual.textualize.io/)
- Inspired by Unix philosophy of simple, composable tools