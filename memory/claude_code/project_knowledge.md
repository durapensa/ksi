# KSI Project Knowledge for Claude Code

## Project Overview
KSI (Knowledge System Interface) is a minimal daemon system for managing Claude AI processes with conversation continuity and multi-agent orchestration capabilities.

## System Architecture

### Core Design
- **Plugin-Based**: Event-driven architecture using pluggy (100% complete)
- **Single Socket**: Unix socket at `var/run/daemon.sock` for all communication
- **Async Everything**: No polling, pure event-driven communication
- **Process Management**: `ksi-daemon.py` wrapper using python-daemon
- **Protocol**: Newline-delimited JSON (NDJSON) for easy debugging

### Plugin Documentation
- `ksi_daemon/PLUGIN_ARCHITECTURE.md` - Complete architecture and status
- `ksi_daemon/PLUGIN_DEVELOPMENT_GUIDE.md` - How to create plugins
- `ksi_daemon/EVENT_CATALOG.md` - All system events reference

## Key Components & Interfaces

### Daemon Control
- `./daemon_control.sh` - Start/stop/restart/health operations
- `ksi-daemon.py` - Main daemon wrapper with python-daemon
- `ksi_daemon/core_plugin.py` - Core daemon implementation with plugin system

### Client Libraries (`ksi_client/`)
- `EventChatClient` - Simplified event-based client for chat operations only
- `MultiAgentClient` - Specialized client for agent coordination, messaging, and state
- `SimpleChatClient` - Legacy simplified chat interface (deprecated)

### User Interfaces
- `chat.py` - Simple CLI chat interface
- `interfaces/orchestrate.py` - Multi-Claude orchestration with composition modes
- `interfaces/monitor_tui.py` - Real-time TUI monitor
- `interfaces/chat_textual.py` - Enhanced TUI chat with 10-100x faster conversation loading (AVOID running - corrupts Claude Code TUI)
- `example_orchestration.py` - Example of multi-Claude orchestration via ksi_client

## Development Environment

### Setup
```bash
./setup.sh                    # Initial setup
source .venv/bin/activate     # Activate virtual environment
./daemon_control.sh start     # Start daemon
```

### Dependencies
- Python 3.8+ with virtual environment at `.venv/`
- Core: PyYAML, textual, psutil, pydantic, structlog, tenacity
- Plugin system: pluggy, aioinject
- LLM: litellm, claude_cli_litellm_provider

### Directory Structure
```
ksi/
├── ksi_daemon/           # Core daemon code
│   ├── plugins/         # Plugin implementations
│   └── protocols/       # Protocol definitions
├── ksi_client/          # Client library
├── tests/               # Test suite
├── interfaces/          # User interfaces
├── prompts/             # Prompt system Python code
├── var/                 # Runtime data (gitignored)
│   ├── run/            # PID file and daemon socket
│   ├── state/          # Persistent state files
│   ├── logs/           # Daemon and session logs
│   │   ├── daemon/     # Daemon logs
│   │   └── sessions/   # Session transcripts and message_bus.jsonl
│   ├── db/             # SQLite database
│   ├── agent_profiles/ # Agent profile JSON files
│   └── prompts/        # Prompt templates and compositions
│       ├── components/ # Markdown component templates
│       └── compositions/ # YAML composition definitions
└── memory/              # Knowledge management
```

### Active Plugins
- **transport/unix_socket.py** - Unix socket transport using NDJSON protocol
- **completion/completion_service.py** - Completion request handling
- **completion/litellm.py** - LiteLLM provider for Claude CLI
- **agent/agent_service.py** - Agent lifecycle, profiles, and messaging
- **state/state_service.py** - SQLite-backed persistent state management
- **messaging/message_bus.py** - Pub/sub messaging for inter-agent communication
- **core/health.py** - Health check endpoint
- **core/shutdown.py** - Graceful shutdown handling

## Testing Framework

### Core Tests
- `tests/test_plugin_system.py` - Plugin infrastructure tests
- `tests/test_event_client.py` - Event-based client tests
- `tests/test_daemon_protocol.py` - Protocol compliance
- `tests/test_completion_command.py` - Async completion flow

### Quick Tests
```bash
# Health check
echo '{"event": "system:health", "data": {}}' | nc -U var/run/daemon.sock

# Test completion
echo '{"event": "completion:request", "data": {"prompt": "Hello"}}' | nc -U var/run/daemon.sock

# Plugin system
python3 tests/test_plugin_system.py

# Full test suite
python3 tests/test_daemon_protocol.py
```

## Core Functionality

### Message Bus / Pub-Sub
- **Plugin**: `messaging/message_bus.py`
- **Events**: `message:subscribe`, `message:publish`, `message:unsubscribe`
- **Features**: Inter-agent messaging, event subscriptions, targeted delivery

### State Management (SQLite)
- **Plugin**: `state/state_service.py`
- **Backend**: `SessionAndSharedStateManager` with SQLite database
- **Events**: `state:get`, `state:set`, `state:delete`, `state:list`
- **Features**: Namespaced keys, persistent storage, session tracking

### Agent Management
- **Plugin**: `agent/agent_service.py`
- **Features**: Agent profiles, lifecycle management, message queues
- **Events**: `agent:spawn`, `agent:terminate`, `agent:send_message`

### Async Completion Flow
- **Plugin**: `completion/completion_service.py`
- **Events**: `completion:request` (sync), `completion:async` (non-blocking)
- **Backend**: LiteLLM with claude-cli provider

## Common Operations

### Using the System
```bash
# Start daemon
./daemon_control.sh start

# Chat with Claude
python3 chat.py

# Multi-Claude orchestration (via ksi_client)
python3 example_orchestration.py

# Monitor in real-time
python3 interfaces/monitor_tui.py

# Stop daemon (graceful)
./daemon_control.sh stop
```

### Completion Flow
1. Client sends COMPLETION command with `client_id`
2. Daemon acknowledges with `request_id`
3. Daemon processes via LiteLLM/Claude CLI
4. Result delivered as COMPLETION_RESULT event
5. No polling - pure async event-driven

## Technical Notes & Gotchas

### Critical Patterns
- **Parameter Models**: Import from `daemon/socket_protocol_models.py` only
- **Error Responses**: Use `SocketResponse.error()` with message string
- **sessionId**: Never quote - Claude CLI handles internally
- **State Keys**: `shared:` prefix for cross-agent, plain for agent-specific

### Design Principles
- **Event-Driven Only**: No polling, timers, or wait loops
- **Plugin-First**: Core only routes - logic in plugins
- **Targeted Delivery**: Events to specific clients, not broadcast

### Known Issues
- **chat_textual.py**: Corrupts Claude Code's TUI - use chat.py instead
- **Import Errors**: Always activate venv first
- **Plugin Imports**: Need absolute imports or proper path setup

### Recent Fixes (2025-06-25)
- **State Service**: Fixed initialization issue with BaseManager pattern
- **Configuration**: All paths now use config system (var/agent_profiles, var/prompts)
- **Performance**: chat_textual.py now has efficient conversation loading with message ordering, deduplication, and pagination
- **Client Architecture**: Separated EventChatClient (chat) from MultiAgentClient (coordination)

## Troubleshooting

### Common Problems
1. **"Daemon not responding"**
   - Check: `cat var/ksi_daemon.pid` and `ps aux | grep ksi-daemon`
   - Fix: `./daemon_control.sh restart`

2. **Socket errors**
   - Check: `ls -la var/sockets/`
   - Fix: Ensure directory exists with write permissions

3. **Plugin not loading**
   - Check: `var/logs/daemon.log` for import errors
   - Fix: Use absolute imports in plugins

4. **Completion timeouts**
   - Check: Claude CLI is installed and working
   - Fix: Test with `claude --version`

---
*Last updated: 2025-06-25*