# KSI Project Knowledge for Claude Code

## Project Overview
KSI (Knowledge System Interface) is a minimal daemon system for managing Claude AI processes with conversation continuity and multi-agent orchestration capabilities.

## System Architecture

### Core Design
- **Plugin-Based**: Event-driven architecture using pluggy (90% complete)
- **Multi-Socket**: Separate Unix sockets for different concerns
- **Async Everything**: No polling, pure event-driven communication
- **Process Management**: `ksi-daemon.py` wrapper using python-daemon

### Socket Architecture
- `admin.sock` - System administration (health, shutdown, metrics)
- `agents.sock` - Agent lifecycle management
- `messaging.sock` - Pub/sub and inter-agent communication
- `state.sock` - Persistent key-value storage
- `completion.sock` - Async LLM completion requests

### Plugin Documentation
- `ksi_daemon/PLUGIN_ARCHITECTURE.md` - Complete architecture and status
- `ksi_daemon/PLUGIN_DEVELOPMENT_GUIDE.md` - How to create plugins
- `ksi_daemon/EVENT_CATALOG.md` - All system events reference

## Key Components & Interfaces

### Daemon Control
- `./daemon_control.sh` - Start/stop/restart/health operations
- `ksi-daemon.py` - Main daemon wrapper with python-daemon
- `ksi_daemon/core.py` - Core daemon implementation

### Client Libraries (`ksi_client/`)
- `AsyncClient` - Full-featured multi-socket client
- `SimpleChatClient` - Simplified chat interface
- `EventBasedClient` - New event-driven client
- `EventChatClient` - Event-based chat interface

### User Interfaces
- `chat.py` - Simple CLI chat interface
- `interfaces/orchestrate.py` - Multi-Claude orchestration
- `interfaces/monitor_tui.py` - Real-time TUI monitor
- `interfaces/chat_textual.py` - TUI chat (AVOID - corrupts Claude Code TUI)

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
│   ├── commands/        # Legacy command handlers
│   └── protocols/       # Protocol definitions
├── ksi_client/          # Client library
├── tests/               # Test suite
├── interfaces/          # User interfaces
├── var/                 # Runtime data
│   ├── sockets/        # Unix sockets
│   ├── state/          # Persistent state
│   ├── logs/           # Daemon logs
│   └── claude_logs/    # Session transcripts
└── memory/              # Knowledge management
```

## Testing Framework

### Core Tests
- `tests/test_plugin_system.py` - Plugin infrastructure tests
- `tests/test_event_client.py` - Event-based client tests
- `tests/test_daemon_protocol.py` - Protocol compliance
- `tests/test_completion_command.py` - Async completion flow

### Quick Tests
```bash
# Health check
echo '{"command":"HEALTH_CHECK","parameters":{}}' | nc -U var/sockets/admin.sock

# Plugin system
python3 tests/test_plugin_system.py

# Full test suite
python3 tests/test_daemon_protocol.py
```

## Common Operations

### Using the System
```bash
# Start daemon
./daemon_control.sh start

# Chat with Claude
python3 chat.py

# Multi-Claude conversation
python3 interfaces/orchestrate.py "Discuss AI ethics"

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
*Last updated: 2025-06-24*