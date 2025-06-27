# KSI Technical Knowledge

Comprehensive technical reference for KSI (Knowledge System Interface) - a minimal daemon system for managing Claude AI processes with conversation continuity and multi-agent orchestration.

## System Architecture

### Core Design
- **Plugin-Based**: Event-driven architecture using pluggy
- **Single Socket**: Unix socket at `var/run/daemon.sock` 
- **Protocol**: Newline-delimited JSON (NDJSON)
- **Process Management**: `ksi-daemon.py` wrapper using python-daemon

### Directory Structure
```
ksi/
├── ksi_daemon/          # Core daemon code
│   ├── plugins/        # Plugin implementations
│   └── protocols/      # Protocol definitions
├── ksi_client/         # Participant client library
├── ksi_admin/          # Administrative client library
├── tests/              # Test suite
├── interfaces/         # User interfaces
├── var/                # Runtime data (gitignored)
│   ├── run/           # PID file and daemon socket
│   ├── logs/          # Daemon and session logs
│   ├── db/            # SQLite database
│   └── prompts/       # Prompt templates
└── memory/             # Knowledge management
```

## Active Plugins

### Core Services
- **transport/unix_socket.py** - NDJSON protocol handler
- **core/health.py** - Health check endpoint
- **core/shutdown.py** - Graceful shutdown
- **core/monitor.py** - Event log API

### Completion System (v2 Deployed)
- **completion/completion_service.py** - Main service with queue integration
- **completion/completion_queue.py** - Priority-based request queue
- **completion/litellm.py** - LiteLLM provider

### Agent & State Management
- **agent/agent_service.py** - Agent lifecycle and profiles
- **state/state_service.py** - SQLite-backed persistence
- **messaging/message_bus.py** - Inter-agent pub/sub

### Async Queue Infrastructure
- **injection/injection_router.py** - Routes completion results via injection
- **injection/circuit_breakers.py** - Prevents runaway chains
- **conversation/conversation_lock.py** - Prevents conversation forking
- **conversation/conversation_service.py** - Session tracking

## Client Libraries

### ksi_client (Participants)
- `EventChatClient` - Chat operations
- `MultiAgentClient` - Agent coordination
- `AsyncClient` - Full event interface

### ksi_admin (Operators)
- `MonitorClient` - System monitoring
- `MetricsClient` - Performance metrics (planned)
- `ControlClient` - Lifecycle management (planned)
- **No dependencies on ksi_client**

## Event System

### Available Namespaces
- **system**: health, shutdown, discover, help
- **completion**: request, async, queue_status
- **agent**: spawn, terminate, list, send_message
- **state**: get, set, delete, list
- **message**: subscribe, publish, unsubscribe
- **conversation**: list, search, active, acquire_lock, release_lock
- **monitor**: get_events, get_stats, clear_log

### Event Discovery
```bash
{"event": "system:discover", "data": {}}
```
Returns all available events with parameters and descriptions.

## Completion Service v2

### Features
- Priority queue (CRITICAL → BACKGROUND)
- Conversation locks prevent forking
- Event-driven injection support
- Circuit breaker protection

### Usage
```bash
# Sync completion (backward compatible)
{"event": "completion:request", "data": {
  "prompt": "Hello",
  "model": "claude-cli/sonnet",
  "session_id": "optional"
}}

# Async with priority and injection
{"event": "completion:async", "data": {
  "prompt": "Research task",
  "priority": "high",
  "injection_config": {
    "enabled": true,
    "trigger_type": "research",
    "target_sessions": ["coordinator"]
  }
}}
```

## Monitoring Architecture

### Event Log System
- Ring buffer (10k events) for efficiency
- Pattern-based filtering (`completion:*`)
- Time-range queries with flexible parsing
- Pull-based architecture (no broadcast overhead)

### Command Center Interface
- **File**: `interfaces/monitor_textual.py`
- **Architecture**: MVC pattern with Textual
- **Features**: Live events, active sessions, health metrics

### API Examples
```bash
# Get filtered events
{"event": "monitor:get_events", "data": {
  "event_patterns": ["completion:*"],
  "limit": 100,
  "since": "1h ago"
}}

# Get system stats
{"event": "monitor:get_stats", "data": {}}
```

## Plugin Development

### Pattern
```python
import pluggy
hookimpl = pluggy.HookimplMarker("ksi")

@hookimpl
def ksi_handle_event(event_name, data, context):
    if event_name == "my:event":
        return handle_my_event(data)
    return None

# Module marker
ksi_plugin = True
```

### Key Points
- Function-based hooks (not methods)
- First non-None response wins
- Use absolute imports
- Add module marker

## Testing

### Core Tests
```bash
# Quick health check
echo '{"event": "system:health", "data": {}}' | nc -U var/run/daemon.sock

# Test suites
python3 tests/test_plugin_system.py
python3 tests/test_daemon_protocol.py
python3 tests/test_v2_deployment.py
```

### V2 Deployment Test
```bash
python3 tests/test_v2_deployment.py
```
Verifies: sync/async completion, queue status, conversation locks, priorities

## Technical Patterns

### Session Management
- **Daemon-owned**: Sessions belong to daemon for federation
- **Cross-device**: Continue conversations anywhere
- **Future API**: session:get_recent, session:continue

### Provider-Agnostic Responses
```json
{
  "ksi": {
    "provider": "claude-cli",
    "request_id": "uuid",
    "timestamp": "ISO8601",
    "duration_ms": 5030
  },
  "response": {
    // Provider-specific response
  }
}
```

### State Management
- **Shared state**: `shared:` prefix for cross-agent
- **Agent state**: Plain keys for agent-specific
- **SQLite backend**: `var/db/agent_shared_state.db`

## Common Issues

### Socket Not Found
```bash
./daemon_control.sh status  # Check if running
./daemon_control.sh restart # Restart if needed
```

### Plugin Import Errors
- Check `var/logs/daemon.log`
- Ensure absolute imports
- Verify `.venv` activated

### Model Names
- Claude CLI: `sonnet` or `opus` only (not `haiku`)
- Always prefix: `claude-cli/sonnet`

## Future Roadmap

### Near Term
- Correlation ID implementation
- Enhanced monitoring displays
- Performance metrics extraction

### Long Term
- Distributed KSI clusters
- HTTP/gRPC transport
- Kubernetes-like agent deployment
- Cross-cluster federation

## Recent Updates

### Completion Service v2 (2025-06-27)
- Integrated async queue with conversation locks
- Added injection router for autonomous coordination
- Circuit breakers prevent runaway chains
- Full backward compatibility maintained

---
*For development practices, see `/Users/dp/projects/ksi/CLAUDE.md`*