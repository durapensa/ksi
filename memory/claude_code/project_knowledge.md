# KSI Technical Knowledge

Essential technical reference for KSI (Kubernetes-Style Infrastructure) - a resilient daemon system for orchestrating autonomous AI agents with production-grade reliability.

**Core Philosophy**: Pure event-based architecture with coordinated shutdown, automatic checkpoint/restore, and resilient error handling.

## System Architecture

### Event-Driven Core
- **Event Router**: Central message broker - all inter-module communication via events
- **Module System**: Self-registering handlers via `@event_handler` decorators
- **Protocol**: Unix socket with newline-delimited JSON (NDJSON)
- **REST Patterns**: Single response = object, multiple = array
- **No Cross-Module Imports**: Modules communicate only through events

### Directory Structure
```
ksi/
├── ksi_daemon/          # Core daemon modules
│   ├── core/           # Infrastructure (state, health, discovery)
│   ├── transport/      # Socket transport layer
│   ├── completion/     # Completion orchestration
│   ├── agent/          # Agent lifecycle
│   └── plugins/        # Plugin system (pluggy-based)
├── ksi_client/         # Python client library
├── ksi_common/         # Shared utilities and config
├── var/                # Runtime data
│   ├── run/           # Socket and PID file
│   ├── logs/          # All system logs
│   ├── db/            # SQLite databases
│   └── lib/           # Configurations and schemas
└── memory/             # Knowledge management
```

## Core APIs

### Event Handler Pattern
```python
from ksi_daemon.event_system import event_handler

@event_handler("my:event")
async def handle_my_event(data: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "success"}
```

### Client Usage
```python
from ksi_client import EventClient

async with EventClient() as client:
    # Single response expected
    result = await client.send_single("state:get", {"key": "config"})
    
    # Multiple responses
    all_health = await client.send_all("system:health", {})
```

### Event Namespaces
- **system**: health, shutdown, discover, help, ready
- **completion**: async, status, cancel, result
- **agent**: spawn, terminate, list, info
- **state**: entity:*, relationship:*, graph:*
- **observation**: subscribe, unsubscribe, query_history
- **message**: publish, subscribe

## Infrastructure Services

### State Management
- **Universal Relational Model**: Entities with properties and relationships
- **For Agent Data**: Not for system infrastructure
- **EAV Pattern**: Flexible property storage
- **Graph Operations**: Traverse relationships between entities

### Event Logging
- **File-Based Storage**: Daily JSONL files in `var/logs/events/`
- **SQLite Metadata**: Fast queries without loading full events
- **Selective References**: Large payloads (>5KB) stored separately
- **Pattern Matching**: SQL LIKE queries (e.g., "system:*")

### Plugin System
- **Pluggy-Based**: Standard plugin architecture
- **Hook Pattern**: `@hookimpl` decorated functions
- **Dynamic Loading**: Plugins in `ksi_daemon/plugins/`
- **Async Tasks**: Return coroutines from `ksi_ready` hook

## Key Modules

### Core Infrastructure
- **transport/unix_socket.py**: NDJSON protocol handler
- **core/state.py**: Relational state management
- **core/reference_event_log.py**: High-performance event logging
- **core/checkpoint.py**: State persistence across restarts
- **core/health.py**: System health monitoring

### Service Modules
- **completion/completion_service.py**: Async completion orchestration
- **agent/agent_service.py**: Agent lifecycle and spawning
- **observation/observation_manager.py**: Event observation routing
- **mcp/dynamic_server.py**: MCP server with tool generation
- **capability_enforcer.py**: Runtime permission enforcement

## Configuration

### Import Pattern
```python
from ksi_common.config import config
# Use: config.socket_path, config.db_dir, config.log_dir
```

### Environment Variables
- `KSI_LOG_LEVEL`: DEBUG, INFO (default), WARNING, ERROR
- `KSI_SOCKET_PATH`: Override default socket location
- `KSI_PROPAGATE_ERRORS`: Set to "true" for debugging

### Never Hardcode
- Always use config properties for paths
- No manual file paths like `"var/logs/daemon"`
- Use `config.daemon_log_dir`, `config.socket_path`, etc.

## Development Patterns

### Module Communication
- **Events Only**: No direct imports between service modules
- **Context Access**: Use `context["emit_event"]` from system:context
- **Error Handling**: Specific exceptions, no bare except
- **Async First**: All handlers and operations async

### Session Management
- **Never Invent IDs**: Only use session_ids from claude-cli
- **ID Flow**: Each request returns NEW session_id
- **Log Naming**: Response files named by session_id

### Capability System
- **Declarative**: Use capability flags in profiles
- **Mappings**: `var/lib/capability_mappings.yaml`
- **Inheritance**: base → specialized profiles
- **Runtime Enforcement**: capability_enforcer validates

### Development Mode
```bash
./daemon_control.py dev  # Auto-restart on file changes
```
- Watches Python files in ksi_daemon/, ksi_common/, ksi_client/
- Preserves state through checkpoint/restore

## Quick Reference

### Common Commands
```bash
# Daemon control
./daemon_control.py start|stop|restart|status|dev

# Health check
echo '{"event": "system:health", "data": {}}' | nc -U var/run/daemon.sock

# List agents
echo '{"event": "agent:list", "data": {}}' | nc -U var/run/daemon.sock

# Plugin introspection
echo '{"event": "plugin:list", "data": {}}' | nc -U var/run/daemon.sock
```

### Debugging
```bash
# Enable debug logging
KSI_LOG_LEVEL=DEBUG ./daemon_control.py restart

# Propagate errors (don't swallow exceptions)
KSI_PROPAGATE_ERRORS=true ./daemon_control.py start

# Check logs
tail -f var/logs/daemon/daemon.log
```

## Key Design Principles

1. **Event-Driven**: All communication through events
2. **Resilient**: Automatic retry, checkpoint/restore
3. **Observable**: Comprehensive event logging and monitoring
4. **Modular**: Clean module boundaries, no coupling
5. **Declarative**: Capabilities and permissions, not code

---
*For development practices, see `/Users/dp/projects/ksi/CLAUDE.md`*