# KSI Technical Knowledge

Core technical reference for KSI (Kubernetes-Style Infrastructure) - a resilient daemon system for orchestrating autonomous AI agents with production-grade reliability.

**Current State**: Pure event-based architecture with coordinated shutdown, automatic checkpoint/restore, and retry logic. Universal state preservation across restarts.

**Latest Features**:
- Shutdown coordination with barrier pattern and service acknowledgments
- Automatic retry for failed operations with exponential backoff
- Checkpoint/restore for all daemon restarts (not just dev mode)
- Session recovery for interrupted completion requests

## System Architecture

### Core Design
- **Event-Driven**: Pure Python module imports with @event_handler decorators
- **REST JSON API**: Standard patterns (single = object, multiple = array)
- **Single Socket**: Unix socket at `var/run/daemon.sock` 
- **Protocol**: Newline-delimited JSON (NDJSON) with REST envelopes
- **Process Management**: `ksi-daemon.py` wrapper using python-daemon
- **Module Communication**: Events only - no cross-module imports

### Directory Structure
```
ksi/
├── ksi_daemon/          # Core daemon code
│   ├── core/           # Core services (state, health, discovery)
│   ├── transport/      # Socket transport
│   ├── completion/     # Completion service
│   ├── agent/          # Agent management
│   └── [modules]/      # Other service modules
├── ksi_client/         # Client library with convenience methods
├── tests/              # Test suite
├── interfaces/         # User interfaces
├── var/                # Runtime data
│   ├── run/           # PID file and daemon socket
│   ├── logs/          # Structured logging
│   ├── db/            # SQLite databases
│   └── lib/           # Compositions and schemas
└── memory/             # Knowledge management
```

### Event-Based Module System

**Pure Event Architecture**: Modules self-register handlers at import time:

```python
from ksi_daemon.event_system import event_handler

@event_handler("my:event")
async def handle_my_event(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle my event."""
    return {"result": "success"}
```

**Module Organization**:
- Each module is a flat Python file/package
- No __init__.py magic or plugin discovery
- Import order matters for dependencies (state first)
- All inter-module communication via events

## REST JSON API Patterns

### Transport Layer
The Unix socket transport follows REST conventions:
- **Single response**: Returns object `{"status": "ok"}`
- **Multiple responses**: Returns array `[{"id": 1}, {"id": 2}]`
- **Wrapped in envelope**: With metadata for correlation

### Response Envelope
```json
{
  "event": "state:get",
  "data": {...} | [...],  // Object or array based on handler count
  "count": 1,
  "correlation_id": "uuid",
  "timestamp": 12345.678
}
```

### Python Client (ksi_client)

#### Raw REST Response
```python
# Returns dict or list based on handler response count
response = await client.send_event("state:get", {"key": "mykey"})
```

#### Convenience Methods
```python
# Expect exactly one response
single = await client.send_single("state:set", {...})

# Always get list
all_resp = await client.send_all("system:health", {})

# Get first or None
first = await client.send_first("discovery:modules", {})

# Extract value with default
value = await client.get_value("state:get", {"key": "k"}, default="")

# Merge multi-handler responses
merged = await client.send_and_merge("system:discover", {}, merge_key="events")

# Filter successes only
good = await client.send_success_only("batch:process", {...})

# Configurable error handling
result = await client.send_with_errors("validate:all", {...}, error_mode="collect")
```

## Core State Infrastructure

### Unified State Management
All state functionality consolidated in `ksi_daemon/core/state.py`:
- **Session tracking**: In-memory conversation state
- **Shared state**: SQLite persistent key-value store
- **Async queues**: SQLite-backed queue operations

### State APIs
```python
# Shared state
{"event": "state:set", "data": {"key": "k", "value": "v", "namespace": "ns"}}
{"event": "state:get", "data": {"key": "k", "namespace": "ns"}}
{"event": "state:delete", "data": {"key": "k", "namespace": "ns"}}
{"event": "state:list", "data": {"namespace": "ns", "pattern": "*"}}

# Async queues
{"event": "async_state:push", "data": {"namespace": "ns", "queue_name": "q", "value": {}}}
{"event": "async_state:pop", "data": {"namespace": "ns", "queue_name": "q"}}
{"event": "async_state:queue_length", "data": {"namespace": "ns", "queue_name": "q"}}
```

## Active Modules

### Core Services
- **transport/unix_socket.py** - REST JSON protocol handler
- **core/state.py** - Unified state management
- **core/health.py** - System health checks
- **core/discovery.py** - Event discovery & introspection
- **core/correlation.py** - Request correlation tracking
- **core/monitor.py** - Event monitoring
- **core/checkpoint.py** - Universal state persistence (with shutdown integration)

### Service Modules
- **completion/completion_service.py** - Async completion management (with retry logic)
- **completion/retry_manager.py** - Retry scheduling with exponential backoff
- **completion/claude_cli_litellm_provider.py** - Spawns Claude processes (graceful cleanup)
- **agent/agent_service.py** - Agent lifecycle (asyncio tasks only)
- **conversation/conversation_service.py** - Session tracking
- **messaging/message_bus.py** - Pub/sub messaging (with shutdown acknowledgment)
- **permissions/permission_service.py** - Security boundaries
- **composition/composition_service.py** - YAML configurations
- **mcp/mcp_service.py** - MCP server management (with graceful shutdown)

## Module Dependencies

**Initialization Order** (daemon_core.py):
1. State infrastructure (core dependency)
2. Core modules (health, discovery, etc.)
3. Transport layer
4. Service modules

**No Cross-Module Imports**: All communication through events:
```python
# BAD - creates coupling
from ksi_daemon.completion import process_completion

# GOOD - event-based
await emit_event("completion:async", data)
```

## Event System

### Available Namespaces
- **system**: health, shutdown, discover, help, startup, context, ready, shutdown_complete
- **completion**: async, queue_status, result, status, failed
- **agent**: spawn, terminate, list, send_message
- **state**: get, set, delete, list
- **async_state**: push, pop, get, set, delete, queue_length
- **message**: subscribe, publish, unsubscribe
- **conversation**: list, search, active, acquire_lock, release_lock
- **monitor**: get_events, get_stats, clear_log
- **composition**: compose, profile, prompt, validate, discover, list
- **shutdown**: acknowledge (for critical service coordination)
- **dev**: checkpoint, restore (manual checkpoint operations)

### Event Discovery
```bash
{"event": "system:discover", "data": {}}
```
Returns all available events with parameters from all modules.

## Client Development

### Using ksi_client
```python
from ksi_client import EventClient

async with EventClient() as client:
    # Most operations expect single responses
    state = await client.send_single("state:get", {"key": "config"})
    
    # Discovery operations merge multiple responses
    all_events = await client.send_and_merge("system:discover", {}, merge_key="events")
    
    # Health checks might have multiple responders
    health_checks = await client.send_all("system:health", {})
```

### Error Handling
```python
from ksi_client.exceptions import KSIEventError, KSITimeoutError

try:
    result = await client.send_single("state:get", {"key": "missing"})
except KSIEventError as e:
    print(f"Error in {e.event_name}: {e.message}")
```

## Module Development

### Basic Pattern
```python
from ksi_daemon.event_system import event_handler
from ksi_common.logging import get_bound_logger

logger = get_bound_logger("my_module")

# Module state (if needed)
context = {}

@event_handler("system:context")
async def handle_context(data: Dict[str, Any]) -> None:
    """Receive daemon context."""
    global context
    context = data
    logger.info("Module initialized")

@event_handler("my:event")
async def handle_my_event(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle custom event."""
    # Access shared services via context
    emit_event = context.get("emit_event")
    if emit_event:
        await emit_event("other:event", {"data": "value"})
    
    return {"status": "success"}
```

### Key Points
- Import and decorators auto-register handlers
- Access context for emit_event and other services
- Return dicts for responses
- Use absolute imports from ksi_daemon
- Let daemon handle async task lifecycle

## Development & Testing

### Development Mode
```bash
./daemon_control.py dev  # Auto-restart on .py file changes
```
- Watches ksi_daemon/, ksi_common/, ksi_client/ directories
- Universal checkpoint/restore preserves all state (not just dev mode)
- Graceful restart with automatic retry of interrupted requests
- Async implementation with watchfiles (no polling)

### Quick Health Check
```bash
echo '{"event": "system:health", "data": {}}' | nc -U var/run/daemon.sock | jq
```

### Using ksi-cli
```bash
# State operations
./ksi-cli send state:set --key config --value '{"theme": "dark"}'
./ksi-cli get state --key config

# Discovery
./ksi-cli discover
./ksi-cli help state:set

# Send any event
./ksi-cli send completion:async --prompt "Hello" --model claude-cli/sonnet
```

## Session ID Management
- **Claude-cli returns NEW session_id from EVERY request**
- **Session extraction**: Fixed to properly extract from claude-cli JSON responses
- **Log filenames**: `var/logs/responses/{session_id}.jsonl`
- **Conversation flow**: Use previous session_id as input → get new session_id
- **IMPORTANT**: Session IDs are provider-generated and immutable

## Common Issues

### Socket Not Found
```bash
./daemon_control.py status  # Check if running
./daemon_control.py restart # Restart if needed
```

### Coordinated Shutdown
All critical services now use `@shutdown_handler` decorator:
```python
@shutdown_handler("my_service")
async def handle_shutdown(data):
    # Cleanup tasks
    await router.acknowledge_shutdown("my_service")
```

### Checkpoint/Restore
- Automatic on all daemon stops (not just dev mode)
- Detects shutdown-interrupted requests for retry
- Restore happens after services ready (system:ready event)
- Protected with asyncio.shield during shutdown

### Module Import Order
- State must be imported before modules that use it
- Check daemon_core.py for proper ordering

### Response Format
- Use send_single() when expecting one response
- Use send_all() when multiple handlers might respond
- Let transport layer handle REST pattern

---
*For development practices, see `/Users/dp/projects/ksi/CLAUDE.md`*