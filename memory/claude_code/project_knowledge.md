# KSI Technical Knowledge

Core technical reference for KSI (Kubernetes-Style Infrastructure) - a resilient daemon system for orchestrating autonomous AI agents with production-grade reliability.

**Current State**: Pure event-based architecture with coordinated shutdown, automatic checkpoint/restore, and retry logic. Universal state preservation across restarts. **NEW**: Universal relational state system replacing key-value paradigm.

**Latest Features**:
- **Universal Relational State**: Entity-property-relationship model for all state
- **Agent Observation System**: Complete subscription-based event observation between agents
- **Reference-Based Event Log**: ✓ File-based event storage with selective payload references (old event_log.py removed)
- **Terminology Migration**: ✓ Complete conversion from client_id/parent_id to originator_id/construct_id
- Agent originator-construct tracking with relationship metadata
- Shutdown coordination with barrier pattern and service acknowledgments
- Automatic retry for failed operations with exponential backoff
- Checkpoint/restore for all daemon restarts (not just dev mode)
- Session recovery for interrupted completion requests
- MCP token optimization with thin handshake implementation
- Declarative capability system replacing hardcoded tool lists

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

## Core Infrastructure

### Reference-Based Event Log System
High-performance event logging in `ksi_daemon/core/reference_event_log.py`:
- **File-based storage**: Daily JSONL files in `var/logs/events/YYYY-MM-DD/`
- **SQLite metadata index**: Fast queries without loading full events
- **Selective payload references**: Large payloads (>5KB) stored as file references
- **Pattern matching**: SQL LIKE queries for event filtering (e.g., "system:*")
- **Integrated in router**: All events automatically logged via emit()
- **No in-memory buffer**: Direct file writes for durability

### Universal Relational State System
Agent data managed through entity-property-relationship model in `ksi_daemon/core/state.py`:
- **Entities**: Any object (agents, sessions, configs, etc.) with properties
- **Properties**: Key-value attributes stored in EAV pattern
- **Relationships**: Typed connections between entities (spawned, observes, owns)
- **Timestamps**: Numeric storage with automatic ISO conversion for display
- **Agent-owned**: Used by agents for their application data, not system events

### State APIs
```python
# Entity operations
{"event": "state:entity:create", "data": {"type": "agent", "id": "agent_123", "properties": {...}}}
{"event": "state:entity:update", "data": {"id": "agent_123", "properties": {"status": "active"}}}
{"event": "state:entity:delete", "data": {"id": "agent_123"}}
{"event": "state:entity:get", "data": {"id": "agent_123", "include": ["properties", "relationships"]}}
{"event": "state:entity:query", "data": {"type": "agent", "where": {"status": "active"}, "limit": 10}}
{"event": "state:entity:bulk_create", "data": {"entities": [{"type": "agent", "properties": {...}}, ...]}}

# Relationship operations
{"event": "state:relationship:create", "data": {"from": "originator_1", "to": "construct_1", "type": "spawned"}}
{"event": "state:relationship:delete", "data": {"from": "originator_1", "to": "construct_1", "type": "spawned"}}
{"event": "state:relationship:query", "data": {"from": "originator_1", "type": "spawned"}}

# Graph operations
{"event": "state:graph:traverse", "data": {"from": "originator_1", "types": ["spawned"], "depth": 2}}
{"event": "state:aggregate:count", "data": {"target": "entities", "group_by": "type"}}
```

## Active Modules

### Core Services
- **transport/unix_socket.py** - REST JSON protocol handler
- **core/state.py** - Unified state management (for agent data)
- **core/health.py** - System health checks
- **core/discovery.py** - Event discovery & introspection
- **core/correlation.py** - Request correlation tracking
- **core/monitor.py** - Event monitoring (queries event log)
- **core/checkpoint.py** - Universal state persistence (with shutdown integration)
- **event_log.py** - High-performance event logging with ring buffer & SQLite

### Service Modules
- **completion/completion_service.py** - Async completion management (with retry logic, token usage logging)
- **completion/retry_manager.py** - Retry scheduling with exponential backoff
- **completion/claude_cli_litellm_provider.py** - Spawns Claude processes (graceful cleanup, MCP support)
- **agent/agent_service.py** - Agent lifecycle (uses capability_enforcer for spawning)
- **observation/observation_manager.py** - Agent event observation subscriptions
- **conversation/conversation_service.py** - Session tracking
- **messaging/message_bus.py** - Pub/sub messaging (with shutdown acknowledgment)
- **permissions/permission_service.py** - Security boundaries
- **composition/composition_service.py** - YAML configurations
- **mcp/mcp_service.py** - MCP server management (with graceful shutdown)
- **mcp/dynamic_server.py** - FastMCP server with thin handshake optimization

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
- **agent**: spawn, terminate, list, send_message, list_constructs, info
- **state**: entity:create, entity:update, entity:delete, entity:get, entity:query, entity:bulk_create, relationship:create, relationship:delete, relationship:query, graph:traverse, aggregate:count
- **observation**: subscribe, unsubscribe, list, query_history, replay, analyze_patterns
- **observe**: begin, end (sent to observers when target events occur)
- **message**: subscribe, publish, unsubscribe
- **conversation**: list, search, active, acquire_lock, release_lock
- **monitor**: get_events, get_stats, clear_log
- **composition**: compose, profile, prompt, validate, discover, list
- **shutdown**: acknowledge (for critical service coordination)
- **dev**: checkpoint, restore (manual checkpoint operations with cleanup tools)

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

## MCP Integration
- **Single daemon-managed MCP server** on port 8080 (streamable-http)
- **Dynamic tool generation** - creates tools from agent's resolved capabilities
- **Thin handshake optimization** - minimal tool descriptions after first completion
- **Session persistence** - MCP sessions saved in `var/db/mcp_sessions.db`
- **Token usage logging** - tracks MCP overhead (~3000-5000 cache creation tokens)
- **Agent MCP configs** - generated in `var/tmp/{agent_id}_mcp_config.json`

## Declarative Capability System

### Overview
- **Single source of truth**: `var/lib/capability_mappings.yaml` defines all capabilities
- **Capability → Event mapping**: Declarative mapping replaces hardcoded tool lists
- **Automatic tool generation**: MCP dynamically creates tools from resolved events
- **Clean separation**: Capabilities (what agent can do) vs Permissions (enforcement)

### Architecture
- **ksi_common/capability_resolver.py** - Loads mappings, resolves capabilities to events/tools
- **ksi_daemon/capability_enforcer.py** - Runtime security enforcement for agent spawning
- **Agent profiles** - Use simple capability flags instead of explicit tool lists
- **Inheritance** - base_single_agent → base_multi_agent → specialized profiles

### Key Capabilities
- **base**: Core system access (health, help, discover) - always enabled
- **state_write**: Shared state management (requires state_read)
- **agent_messaging**: Inter-agent communication via message bus
- **spawn_agents**: Create and manage child agents
- **development_tools**: Debug features like checkpoint/restore
- **network_access**: External API and web access

### Usage in Profiles
```yaml
components:
  - name: "capabilities"
    inline:
      state_write: true
      agent_messaging: true
      spawn_agents: true
```

## Agent Observation System

### Overview
- **Ephemeral routing rules**: Subscriptions are in-memory only, lost on restart
- **Checkpoint/restore capability**: Subscriptions preserved for system continuity
- **Async processing**: Non-blocking observation queue with circuit breaker
- **Pattern matching**: Flexible event filtering with wildcard support
- **Content-based filtering**: Filter by data field values
- **Rate limiting**: Per-subscription rate limits
- **Integrated with event router**: Transparent event interception
- **Historical queries**: Query past observations from event log

### Observation Events
```python
# Subscribe to observe with advanced filtering
{"event": "observation:subscribe", "data": {
    "observer": "originator_1",
    "target": "construct_1", 
    "events": ["message:*", "error:*"],
    "filter": {
        "exclude": ["system:health"],
        "sampling_rate": 1.0,
        "content_match": {
            "field": "priority",
            "value": "high",
            "operator": "equals"
        },
        "rate_limit": {
            "max_events": 10,
            "window_seconds": 1.0
        }
    }
}}

# Observers receive
{"event": "observe:begin", "data": {
    "source": "construct_1",
    "original_event": "message:send",
    "original_data": {...}
}}

{"event": "observe:end", "data": {
    "source": "construct_1",
    "original_event": "message:send",
    "result": {...},
    "errors": []
}}
```

### Integration
- Event router checks for observers on each emit
- Source agent identified from context or data
- Prevents loops by excluding observe:* events
- Stored in both memory and relational state

### Historical Analysis & Replay
- **Automatic recording**: All events logged with stripped payloads
- **Query from event log**: Filter by patterns, client, time range
- **Replay any events**: Re-emit sequences at variable speed
- **Pattern analysis**: Frequency, sequence, performance, error analytics

```python
# Query observation history (from event log)
{"event": "observation:query_history", "data": {
    "observer": "originator_1",
    "target": "construct_1",
    "event_name": "task:*",
    "since": timestamp,
    "limit": 100
}}

# Replay events (any events, not just observations)
{"event": "observation:replay", "data": {
    "event_patterns": ["test:*", "data:*"],
    "filter": {"client_id": "agent_1"},
    "speed": 2.0,
    "target_agent": "replay_target"
}}

# Analyze patterns (from event log)
{"event": "observation:analyze_patterns", "data": {
    "event_patterns": ["*"],
    "analysis_type": "frequency",
    "filter": {"client_id": "monitor_1"}
}}

## Filtered Event Routing

### Built-in Filter System
Event handlers support optional `filter_func` parameter for sophisticated routing:
```python
@event_handler("my:event", filter_func=content_filter("priority", value="high"))
```

### Filter Utilities
- **RateLimiter**: Time-window based rate limiting
- **content_filter**: Filter by field values with operators
- **source_filter**: Allow/block event sources
- **context_filter**: Require agent/session/capability
- **data_shape_filter**: Validate data structure
- **combine_filters**: Compose filters with AND/OR

### Usage
```python
from ksi_daemon.event_system import content_filter, combine_filters, rate_limit_10_per_second

# Single filter
@event_handler("data:process", filter_func=content_filter("status", value="ready"))

# Combined filters
@event_handler("task:execute", 
              filter_func=combine_filters(
                  content_filter("priority", value=5, operator="gte"),
                  source_filter(allowed_sources=["scheduler"]),
                  mode="all"
              ))

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
- **Automatic**: On all daemon stops (not just dev mode)
- **Detection**: Shutdown-interrupted requests marked for retry
- **Restore**: Happens after services ready (system:ready event)
- **Protected**: With asyncio.shield during shutdown

#### Checkpoint Management Operations
Requires `development_tools` capability:

```bash
# Check checkpoint status
{"event": "dev:checkpoint", "data": {"action": "status"}}

# List requests in checkpoint
{"event": "dev:checkpoint", "data": {"action": "list_requests"}}

# Remove specific request from checkpoint
{"event": "dev:checkpoint", "data": {"action": "remove_request", "request_id": "..."}}

# Clear only failed requests
{"event": "dev:checkpoint", "data": {"action": "clear_failed"}}

# Clear all requests (nuclear option)
{"event": "dev:checkpoint", "data": {"action": "clear_all"}}

# Create manual checkpoint
{"event": "dev:checkpoint", "data": {"action": "create"}}
```

#### Operational Cleanup
Use when dealing with stale/stuck completion requests:
1. `list_requests` - See what's checkpointed
2. `remove_request` - Remove specific problematic requests
3. `clear_failed` - Clean up failed requests after debugging

### Module Import Order
- State must be imported before modules that use it
- Check daemon_core.py for proper ordering

### Response Format
- Use send_single() when expecting one response
- Use send_all() when multiple handlers might respond
- Let transport layer handle REST pattern

## Recent Architectural Improvements

### Completed
1. **Completion System Modularity** (2025-01-05)
   - Refactored 600+ line monolith into focused components:
     - `QueueManager`: Per-session queue management
     - `ProviderManager`: Provider selection with circuit breakers
     - `SessionManager`: Session continuity and conversation locks
     - `TokenTracker`: Comprehensive usage analytics
   - Preserved 100% of existing functionality
   - Added provider health tracking and token analytics
   - See `docs/completion_service_migration.md` for details

## Planned Architectural Improvements

### High Priority
1. **Key-Value to Relational Migration**
   - Replace remaining key-value patterns with relational state
   - Checkpoint data, MCP session cache, agent metadata
   - Use proper entities/relationships for consistency

2. **Error Propagation**
   - Event router should NOT swallow exceptions
   - Let programming errors propagate for visibility
   - Keep circuit breaker pattern for external failures only

3. **Async SQLite Standardization**
   - Ensure all SQLite uses WAL mode (like event log)
   - Make all database writes truly async
   - Consistent async patterns across modules

4. **Terminology Consistency**
   - Deprecate "parent" in favor of "originator_agent_id"
   - Use "purpose" consistently (not "task") for why agent was spawned
   - Standardize variable names across modules

### Future Improvements
- **Test Suite Rewrite**: Focus on current architecture, critical user journeys
- **Composition Validation**: Move validation earlier in pipeline
- **Agent Service Error Handling**: Validate profiles before hard failures
- **Documentation**: Update all docs to reflect current architecture

---
*For development practices, see `/Users/dp/projects/ksi/CLAUDE.md`*