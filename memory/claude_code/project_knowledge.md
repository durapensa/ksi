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

## Current System Status

### Working Components
- **Core Daemon**: Plugin architecture with 10+ active plugins
- **Event Discovery**: Full introspection via `system:discover`
- **Completion Service**: LiteLLM/Claude integration
- **Agent Management**: Lifecycle and messaging
- **State Management**: SQLite-backed persistence
- **Message Bus**: Inter-agent pub/sub
- **Unified Logging**: Structured logging with context propagation
- **Libraries**: ksi_client (participants), ksi_admin (operators)
- **Conversation Service**: Active session tracking and history management

### Available Event Namespaces
- **system**: health, shutdown, discover, help, capabilities
- **completion**: request, async
- **agent**: spawn, terminate, list, send_message
- **state**: get, set, delete, list
- **message**: subscribe, publish, unsubscribe
- **conversation**: list, search, get, export, stats, active

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

### Known Issues & Solutions
- **TUI Scripts**: ⚠️ NEVER run `chat_textual.py` or `monitor_tui.py` from Claude Code - corrupts interface
  - **Solution**: Use `chat.py` or run TUI programs in separate terminals only
  - **Testing**: Use `--test-connection` flag to verify connectivity before running full TUI
- **Import Errors**: Always activate venv first: `source .venv/bin/activate`
- **Plugin Imports**: Need absolute imports or proper path setup
- **Monitor TUI Connection**: No agent_id required - uses admin client architecture with auto-generated client_id

For detailed change history, see git log.

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

### ksi_common Foundation

1. **Unified Configuration**: pydantic-settings with env vars (KSI_*)
2. **Structured Logging**: structlog with context propagation  
3. **Protocol Models**: Type-safe message validation
4. **Retry Patterns**: tenacity-based resilience
5. **Async Utilities**: Timeouts, lifecycles, cleanup
6. **CLI Helpers**: Consistent command-line interfaces
7. **Timestamp Utils**: Flexible parsing and formatting

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

## Project Plans

### 1. Complete Correlation ID Implementation (Medium Priority)
- Add `correlation_id` field to socket protocol as optional parameter
- Update all clients to generate and propagate correlation IDs
- Bind correlation IDs to structlog context in daemon
- Pass parent correlation to spawned agents
- Include correlation_id in all responses
- **Benefits**: End-to-end request tracing, better debugging, performance analysis

### 2. Enhanced Monitoring with Structured Logs (High Value)
- Extend monitor_tui.py to display correlation chains
- Add real-time filtering by correlation_id
- Visualize request flows across components
- Show context propagation in message traces
- **Benefits**: Better system visibility, easier troubleshooting

### 3. Performance Metrics from Logs (Quick Win)
- Extract timing data from structured log events
- Build performance dashboards from log analysis
- Identify bottlenecks using duration_ms fields
- Track operation latencies across components
- **Benefits**: Performance insights without new instrumentation

### 4. Agent Communication Patterns (Research)
- Analyze message_bus usage from structured logs
- Study inter-agent messaging patterns
- Optimize pub/sub topic design
- Design better coordination primitives
- **Benefits**: More efficient multi-agent systems

### 5. Error Analysis System (High Impact)
- Aggregate errors by type/component from logs
- Build correlation-based error chains
- Implement automatic error pattern detection
- Create error dashboards and alerts
- **Benefits**: Proactive issue detection, faster resolution

## Testing Notes

### TUI Interface Testing
Both `interfaces/chat_textual.py` and `interfaces/monitor_tui.py` need manual testing in separate terminals:

```bash
# Terminal 1: Start daemon
./daemon_control.sh start

# Terminal 2: Test enhanced chat
python3 interfaces/chat_textual.py

# Terminal 3: Test monitor (with multi-agent activity)
python3 interfaces/monitor_tui.py
```

**Important**: Run TUI interfaces in separate terminals to avoid corrupting Claude Code's interface.

---
*Last updated: 2025-06-26*