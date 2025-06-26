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

### Client Libraries

#### `ksi_client/` - Participant Clients
- `EventChatClient` - Simplified event-based client for chat operations only
- `MultiAgentClient` - Specialized client for agent coordination, messaging, and state
- `SimpleChatClient` - Legacy simplified chat interface (deprecated)

#### `ksi_admin/` - Administrative Clients (NEW)
- `MonitorClient` - Real-time monitoring of all daemon activity
- `MetricsClient` - System telemetry and performance metrics
- `ControlClient` - Daemon lifecycle management
- `DebugClient` - Troubleshooting and diagnostics
- **No dependencies on ksi_client** - completely standalone implementation

### User Interfaces
- `chat.py` - Simple CLI chat interface
- `interfaces/orchestrate.py` - Multi-Claude orchestration with composition modes
- `interfaces/monitor_tui.py` - Real-time TUI monitor (now uses ksi_admin.MonitorClient)
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

## Current System Status (2025-06-25)

### Working Components
- **Core Daemon**: Running with plugin architecture (10+ plugins)
- **Event Discovery**: `system:discover`, `system:help`, `system:capabilities`
- **Completion Service**: LiteLLM integration for Claude
- **Agent Management**: Spawn, terminate, messaging
- **State Management**: SQLite-backed persistent storage
- **Message Bus**: Inter-agent pub/sub messaging
- **Health/Shutdown**: Graceful lifecycle management
- **ksi_client**: EventChatClient, MultiAgentClient, AsyncClient
- **ksi_admin**: MonitorClient (used by monitor_tui.py)

### In Progress
- **Conversation Plugin**: Created but has indentation errors
- **chat_textual.py**: Needs ksi_daemon imports removed

### Available Events (via system:discover)
- **system**: health, shutdown, discover, help (4 events)
- **completion**: request, async (2 events)  
- **agent**: spawn, terminate, list, send_message (4 events)
- **state**: get, set, delete (3 events)
- **message**: subscribe, publish (2 events)
- **conversation**: list, search, get, export, stats (5 events - pending fix)

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
- **TUI Scripts**: Both `chat_textual.py` and `monitor_tui.py` corrupt Claude Code's TUI - use `chat.py` instead or run in separate terminal
- **Import Errors**: Always activate venv first
- **Plugin Imports**: Need absolute imports or proper path setup

### Recent Changes (2025-06-25)
- **State Service**: Fixed initialization issue with BaseManager pattern
- **Configuration**: All paths now use config system (var/agent_profiles, var/prompts)
- **Performance**: chat_textual.py now has efficient conversation loading with message ordering, deduplication, and pagination
- **Client Architecture**: Separated EventChatClient (chat) from MultiAgentClient (coordination)
- **ksi_admin Library**: Created new administrative library parallel to ksi_client
- **monitor_tui.py**: Refactored to use ksi_admin.MonitorClient instead of raw sockets
- **Event Discovery Service**: Created discovery plugin providing GET_COMMANDS equivalent functionality
  - `system:discover` - Lists all available events with descriptions and parameters
  - `system:help` - Detailed help for specific events
  - `system:capabilities` - Daemon capabilities summary
  - Enables agents to autonomously discover and use daemon features
- **Conversation Plugin**: Created plugin for conversation history (listing, search, export)
  - Simplified timestamp handling - drops malformed entries
  - Currently has indentation issues preventing loading

### Key Technical Insights

#### Library Architecture Pattern
- **ksi_client**: For agents and participants in the system
  - EventChatClient: Simplified chat operations
  - MultiAgentClient: Agent coordination and messaging
  - AsyncClient (EventBasedClient): Full event-driven interface
- **ksi_admin**: For monitoring and controlling the system (NEW)
  - No dependencies on ksi_client - completely standalone
  - AdminBaseClient: Own socket implementation
  - MonitorClient: Subscribe to all system events without participating
  - Future: MetricsClient, ControlClient, DebugClient

#### Pluggy Best Practices (IMPORTANT)
KSI uses pluggy correctly with function-based plugins:
```python
# CORRECT - KSI pattern
import pluggy
hookimpl = pluggy.HookimplMarker("ksi")

@hookimpl
def ksi_handle_event(event_name, data, context):
    if event_name == "my:event":
        return handle_my_event(data)
    return None

# Module marker for discovery
ksi_plugin = True
```
- Decorates functions, NOT methods
- Module-level state management
- First non-None response wins for event handlers

#### Event Discovery Architecture
The discovery plugin enables autonomous agent operation:
- **system:discover**: Returns all events with parameters and descriptions
- **GET_COMMANDS equivalent**: Agents can discover capabilities without hardcoding
- **Self-documenting**: Uses docstrings and introspection
- **Event namespaces**: system, completion, agent, state, message, conversation

#### Conversation Plugin Pattern
- Cache-based metadata scanning for performance
- Timestamp validation - drops malformed entries (no fallbacks)
- Deduplication using timestamp:sender:content_hash
- Export to markdown format in var/state/exports/

### Development Philosophy
- **Fast-moving research software** - no backward compatibility guarantees
- **Breaking changes welcomed** - prioritize clean architecture
- **Libraries are complementary** - ksi_client for participants, ksi_admin for operators
- **Event-driven only** - no polling, pure push architecture

### Future Vision
- **Distributed KSI**: Multiple nodes forming clusters
- **HTTP/gRPC Transport**: For inter-node communication
- **Declarative Deployment**: Kubernetes-like manifests for agents
- **Agent Federation**: Cross-cluster agent migration and communication

### Dependency Analysis

See `docs/dependency-analysis.md` for comprehensive analysis of potential additional dependencies. Key recommendations:
- **attrs** - 25-35% reduction in class boilerplate
- **msgspec** - 10-50x performance improvement for JSON operations
- **rich** - Enhanced debugging and system understanding
- **result** - Explicit error handling patterns
- **hypothesis** - Property-based testing for edge cases

### ksi_common Enhancements Completed

#### 1. **pydantic-settings Integration** ✅
- Created `KSIBaseConfig` in ksi_common/config.py
- Environment variable support with KSI_ prefix
- All components can now share same configuration
- Works with `export KSI_SOCKET_PATH=/custom/path` 
- Supports .env files
- chat_textual.py migrated to use shared config
- See `docs/config-migration-strategy.md` for migration plan

#### 2. **structlog Foundation**
- Consistent structured logging across all components
- Automatic correlation ID propagation
- JSON or console output based on configuration
- Rich debugging with structured context

#### 3. **Pydantic Models for Protocol**
- Type-safe message validation
- Automatic JSON schema generation
- Clear API contracts between components
- Validated event messages and responses

#### 4. **tenacity Retry Strategies**
- Pre-configured retry patterns for different operations
- Socket connections, completions, state operations
- Consistent exponential backoff across components

#### 5. **Enhanced Async Utilities**
- Timeout decorators and context managers
- Connection lifecycle management
- Async iterator helpers
- Resource cleanup patterns

#### 6. **Rich CLI Utilities**
- Shared click decorators for common options
- Consistent CLI argument handling
- Environment variable integration

#### 7. **Advanced Timestamp Handling**
- python-dateutil for flexible parsing
- Human-readable time deltas
- Timezone handling improvements

### Important Technical Patterns

#### Client Usage Patterns
```python
# Use AsyncClient for general event operations
from ksi_client import AsyncClient
client = AsyncClient(client_id="my_app")
await client.connect()
result = await client.request_event("system:discover", {})

# Use ksi_admin for monitoring without participating
from ksi_admin import MonitorClient
monitor = MonitorClient()
await monitor.connect()
await monitor.observe_all()  # Subscribe to all events
```

#### Plugin Development Pattern
1. Create file in `ksi_daemon/plugins/<category>/<name>.py`
2. Use function-based hooks with `@hookimpl` decorator
3. Handle events in `ksi_handle_event` - return None if not handled
4. Add `ksi_plugin = True` module marker
5. Use absolute imports: `from ...config import config`

#### Event Response Patterns
- **Synchronous**: `client.request_event()` waits for response
- **Fire-and-forget**: `client.emit_event()` no response expected
- **Subscription**: `client.subscribe()` for ongoing events
- **Error handling**: Return `{"error": "message"}` for failures

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
*ksi_admin library added*