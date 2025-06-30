# KSI Technical Knowledge

Core technical reference for KSI (Knowledge System Interface) - a minimal daemon system for managing Claude AI processes with conversation continuity and multi-agent orchestration.

## System Architecture

### Core Design
- **Plugin-Based**: Event-driven architecture using pluggy
- **Single Socket**: Unix socket at `var/run/daemon.sock` 
- **Protocol**: Newline-delimited JSON (NDJSON)
- **Process Management**: `ksi-daemon.py` wrapper using python-daemon
- **Cross-Plugin Communication**: Plugins emit events via shared event router

### Directory Structure
```
ksi/
├── ksi_daemon/          # Core daemon code
│   └── plugins/        # Plugin implementations
├── ksi_client/         # Unified client library (participants + admin)
├── tests/              # Test suite
├── interfaces/         # User interfaces
├── var/                # Runtime data
│   ├── run/           # PID file and daemon socket
│   ├── logs/          # Structured logging (see Dynamic Storage below)
│   │   ├── responses/sessions/  # Completion logs (source of truth)
│   │   ├── events/     # Non-completion events
│   │   └── index/      # SQLite navigation indexes
│   ├── db/            # Persistent state
│   └── lib/           # Tracked compositions
│       ├── compositions/   # Agent profiles, prompts, orchestrations
│       ├── fragments/      # Reusable text fragments
│       └── schemas/        # YAML validation schemas
└── memory/             # Knowledge management
```

### Plugin Architecture

**Pluggy Best Practices**: KSI follows standard pluggy patterns with clean separation of sync/async:

1. **Sync Plugin Lifecycle**: 
   - `ksi_startup(config)` - Initialize plugin (sync)
   - `ksi_plugin_context(context)` - Receive runtime objects (sync)
   - `ksi_ready()` - Request async tasks (sync, returns task specs)
   - `ksi_shutdown()` - Cleanup (sync)

2. **Async Task Management** (anyio Structured Concurrency):
   ```python
   @hookimpl
   def ksi_ready():
       return {
           "service": "completion_service",
           "tasks": [{"name": "service_manager", "coroutine": manage_completion_service()}]
       }
   ```
   Core daemon uses anyio task groups for proper structured concurrency.

3. **Import Pattern**: All plugins use absolute imports:
   ```python
   from ksi_daemon.plugins.completion.queue import enqueue_completion
   ```

4. **Shutdown Order**: Cancel async tasks → sync plugin cleanup (reverse of startup)

## Active Plugins

### Core Services
- **transport/unix_socket.py** - NDJSON protocol handler
- **core/health.py** - Health check endpoint
- **core/shutdown.py** - Graceful shutdown
- **core/monitor.py** - Event log API

### Completion System (v3 - Smart Hybrid)
- **completion/completion_service.py** - anyio-based smart hybrid architecture
- **completion/litellm.py** - LiteLLM provider
- **completion/claude_cli_litellm_provider.py** - Claude CLI integration

### Agent & State Management
- **agent/agent_service.py** - Agent lifecycle with composition integration
- **state/state_service.py** - SQLite-backed persistence
- **messaging/message_bus.py** - Inter-agent pub/sub
- **composition/composition_service.py** - Unified YAML composition system

### Async Queue Infrastructure
- **injection/injection_router.py** - Routes completion results via injection
- **injection/circuit_breakers.py** - Prevents runaway chains
- **conversation/conversation_lock.py** - Prevents conversation forking
- **conversation/conversation_service.py** - Session tracking
- **messaging/message_bus.py** - Consolidated pub/sub messaging (v2.0.0)
- **core/correlation.py** - Correlation ID tracing infrastructure

## Client Libraries

### Unified ksi_client Architecture
- `EventBasedClient` - Core event communication with correlation IDs
- `EventChatClient` - High-level chat operations 
- `MultiAgentClient` - Agent coordination and state management
- **Single Architecture**: All clients use EventBasedClient foundation
- **Real-time Events**: Event subscriptions replace polling patterns
- **Request-Response**: Correlation ID support for async operations

## Event System

### Available Namespaces
- **system**: health, shutdown, discover, help
- **completion**: async, queue_status, result, status
- **agent**: spawn, terminate, list, send_message
- **state**: get, set, delete, list
- **message**: subscribe, publish, unsubscribe
- **conversation**: list, search, active, acquire_lock, release_lock
- **monitor**: get_events, get_stats, clear_log
- **composition**: compose, profile, prompt, validate, discover, list, reload

### Event Discovery
```bash
{"event": "system:discover", "data": {}}
```
Returns all available events with parameters and descriptions.

## Completion Service v3 (Smart Hybrid)

### Architecture
- **anyio Structured Concurrency**: Replaced broken asyncio.gather with anyio task groups
- **Smart Hybrid Routing**: Immediate processing for sessionless/free sessions, queuing for busy
- **Per-Session Fork Prevention**: Dynamic per-session queues only when needed
- **Event-Driven**: No polling, pure event-based processing

### Session ID Management
- **Claude-cli returns NEW session_id from EVERY request** (even continuations)
- **Log filenames**: `var/logs/responses/{session_id}.jsonl` (not request_id)
- **Conversation flow**: Use previous response's session_id as input → get new session_id

### Usage
```bash
# Async completion (unified interface)
{"event": "completion:async", "data": {
  "prompt": "Hello",
  "model": "claude-cli/sonnet",
  "session_id": "optional",
  "client_id": "my_client",
  "request_id": "req_12345",
  "priority": "normal"
}}

# High-priority with injection
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

### Monitoring Interfaces
- **File**: `interfaces/monitor_textual.py` (Command Center)
- **File**: `interfaces/monitor_tui.py` (Conversation Timeline)
- **Architecture**: EventBasedClient with real-time subscriptions
- **Features**: Live events, active sessions, health metrics, agent status

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

@hookimpl
def ksi_plugin_context(context):
    """Receive plugin context with event emitter."""
    global event_emitter
    event_emitter = context.get("emit_event")

# Module marker
ksi_plugin = True
```

### Key Points
- Function-based hooks (not methods)
- First non-None response wins
- Use absolute imports
- Add module marker
- Access `emit_event` for cross-plugin communication

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
./daemon_control.py status  # Check if running
./daemon_control.py restart # Restart if needed
```

### Plugin Import Errors
- Check `var/logs/daemon.log`
- Ensure absolute imports
- Verify `.venv` activated

### Model Names
- Claude CLI: `sonnet` or `opus` only (not `haiku`)
- Always prefix: `claude-cli/sonnet`

## Future Architectural Directions

### Correlation ID Implementation ✅ (COMPLETED)
- **Purpose**: Trace complex event chains across async operations
- **Implementation**: Thread-safe ContextVar with hierarchical parent-child relationships
- **Scope**: Request-level ephemeral tracing (not session continuity)
- **Key Features**:
  - Automatic context propagation through event router
  - Full trace chains and trees for debugging
  - Data sanitization (redacts passwords, tokens, secrets)
  - Performance metrics and automatic cleanup
  - @trace_event decorator for function tracing
- **APIs**: correlation:trace, correlation:chain, correlation:tree, correlation:stats
- **Integration**: Event router automatically traces all events with correlation IDs

### Session Management & Multi-Agent Coordination (Medium Term)
- **Purpose**: Robust conversation continuity and natural agent interactions
- **Design**: SQLite-backed session registry with fork prevention
- **Scope**: Conversation-level persistence (complementary to correlation IDs)
- **Key Features**:
  - Linear consistency per agent (no global ordering)
  - Natural from/to/cc message routing patterns
  - Flexible event delivery modes (immediate vs queued)
  - Multicast completions with aggregation strategies
  - Emergency broadcast override system
- **Documentation**: `/Users/dp/projects/tool-work/docs/ksi_session_management_design.md`
- **Use Cases**: Multi-agent collaborations, long-running conversations, coordinated analysis

### Integration Strategy
- **Session + Correlation**: Sessions track conversations, correlations track operations
- **Unified Context**: Both session_id and trace_context in event metadata
- **Query Patterns**: 
  - By session: All events in a conversation
  - By correlation: All events from one request
  - By trace: Full chain of cascading operations

### Other Near Term
- Enhanced system history presentation for monitors
- Performance metrics extraction
- Interface updates for composition system

### Long Term Vision
- Distributed KSI clusters with session federation
- HTTP/gRPC transport with trace context headers
- Kubernetes-like agent deployment with delivery preferences
- Cross-cluster event routing with trace preservation

## Completed Architecture

### Unified Composition System ✅
- All configurations use YAML compositions (`var/lib/compositions/`)
- Inheritance, mixins, variable substitution, conditional assembly
- Agent spawning integrated with composition service

### Dynamic Agent System ✅
- **Selection Service**: `composition:select` chooses compositions by context
- **Self-Modification**: `agent:update_composition` enables runtime adaptation
- **Peer Discovery**: `agent:discover_peers` finds agents by capabilities
- **Three Spawn Modes**: fixed/dynamic/emergent in `orchestrate.py`
- **Runtime Creation**: `composition:create` for on-the-fly generation

### Event System ✅
- Plugin context with shared `emit_event` for cross-plugin communication
- Central event router handling all plugin interactions
- Async coroutine support properly awaited

## Implementation Priorities

### Critical Path (Complete Async Pipeline)
1. **Injection System Implementation** (1-2 days) - REMAINING
   - Execute actual injection in `injection_router.py:235-238`
   - Complete end-to-end async completion flows
   - Enable true multi-agent coordination
   - **Blocker**: Final step of mostly-complete system

### Production Readiness
3. **Completion Queue Cancellation** (1-2 days)
   - Wire LiteLLM cancellation to daemon shutdown
   - Fix graceful shutdown blocking on long completions
   - **Blocker**: Development workflow (faster restarts)

4. **Circuit Breaker Enhancements** (2-3 days)
   - Token/time tracking (currently returns zeros)
   - Prevent runaway completion chains
   - Resource management and cost control

### Foundation for Scale
5. **Dynamic Storage Architecture** (1 week)
   - Session-based write contention solution
   - Minimal duplication storage model
   - Support for peer-to-peer agent patterns
   - **Impact**: Scalable multi-agent coordination

## Dynamic Storage Architecture

### Core Principles
- **Single Source of Truth**: `var/logs/responses/sessions/` for all completion data
- **Write Contention Solution**: Session ownership with daemon-serialized writes
- **Dynamic Agent Support**: No fixed hierarchy assumptions, peer-to-peer capable
- **Minimal Duplication**: SQL indexes point to JSONL files, don't duplicate content

### Storage Structure
```
var/logs/
├── responses/sessions/          # JSONL completion logs (source of truth)
│   ├── sess_{uuid1}.jsonl      # Each session owned by initiating agent
│   └── sess_{uuid2}.jsonl
├── events/                     # Non-completion events only
│   └── {date}/
│       ├── evt_*.json          # Agent lifecycle, state changes
└── index/daily/                # SQLite navigation indexes
    └── {date}.db               # File pointers + minimal metadata
```

### Session Management
- **Ownership Model**: Each session has single initiating agent (prevents write conflicts)
- **Participation**: Other agents join via event system, not direct writes
- **Dynamic Roles**: Agents can shift roles (peer → coordinator → peer)
- **Communication Patterns**: peer_to_peer, broadcast, team_formation, emergent

## Composition Library

### var/lib Structure (Tracked in Git)
```
var/lib/
├── compositions/
│   ├── profiles/        # Agent profiles
│   ├── prompts/        # Prompt templates  
│   ├── orchestrations/ # Multi-agent patterns
│   ├── systems/        # Future: KSI daemon configs for federation
│   └── experiments/    # Local experiments (not shared)
├── fragments/          # Reusable components
├── schemas/           # Validation schemas
└── exchange/          # Future: composition marketplace
```

### Composition Validation
- **Dependency Resolution**: Basic elegant system for composition dependencies
- **Federation Ready**: No hardcoded paths, standard capabilities
- **Exchange Metadata**: Shareable, license, author, tags
- **Security Validation**: No secrets, safe defaults
- **Contract Validation**: Clear provides/requires declarations
- **Deprecation Support**: Metadata for composition evolution

### Future Enhancements
- **Composition Signing**: For trusted exchange (deferred)
- **Performance Hints**: After experimentation (deferred)

## Critical Incomplete Features

### Injection System (90% Complete)
- **Missing**: Final execution step in `injection_router.py:235-238`
- **Status**: Content composition and queuing works, execution is just a TODO
- **Impact**: Blocks end-to-end async completion flows and agent coordination
- **Effort**: Low - mostly implemented, needs final wiring

### Completion Cancellation (Needed for Production)
- **Missing**: Actual LiteLLM request cancellation in `completion_service.py:124`
- **Status**: Event removes from dict but doesn't cancel running requests
- **Impact**: Daemon shutdown hangs on long completions
- **Need**: Graceful shutdown and resource management

### Circuit Breaker Resource Tracking
- **Missing**: Token/time tracking returns zeros in injection circuit breaker
- **Status**: Framework implemented, resource counting not implemented
- **Impact**: Can't prevent runaway completion chains or manage costs
- **Need**: Production resource management

### Session Management Foundation
- **Missing**: Basic session registry and federation framework
- **Status**: Conversation service provides search/export, not true sessions
- **Impact**: No cross-device conversation continuity
- **Need**: Foundation for future distributed deployment

### Event Log Persistence
- **Missing**: File persistence with rotation for event log
- **Status**: In-memory ring buffer only
- **Impact**: Limited debugging and monitoring capabilities
- **Need**: Production observability

## Technical Debt Cleanup ✅

### anyio Migration (COMPLETED)
- Replaced broken asyncio.gather with anyio structured concurrency
- Smart hybrid completion system with per-session fork prevention
- Proper pluggy best practices: sync plugin loading → async task execution

### Wrapper Consolidation (COMPLETED)
- Consolidated message_bus.py into messaging plugin (348 lines → self-contained)
- Removed obsolete files: core_plugin_backup.py, plugin_loader_old.py, completion_queue.py
- Removed hot_reload functionality (contradicted CLAUDE.md directives)

### Documentation & Patterns (COMPLETED)
- Critical session ID pattern documented in CLAUDE.md
- Cleanup philosophy: distinguish legacy vs incomplete functionality
- All changes committed atomically with proper documentation

## Current Technical Issues

### Plugin Logging Configuration
- **Issue**: Plugin loggers don't respect KSI_LOG_LEVEL environment variable
- **Root Cause**: ksi_common.logging.get_logger() auto-configures structlog with defaults
- **Impact**: DEBUG logs from plugins don't appear even with KSI_LOG_LEVEL=DEBUG
- **Attempted Fix**: Configure structlog before plugin imports in daemon __init__.py
- **Remaining Issue**: get_logger() in ksi_common re-configures with INFO level
- **Workaround**: Use logger.info() instead of logger.debug() for critical debugging
- **Proper Fix**: Modify ksi_common.logging.get_logger() to check if already configured

---
*For development practices, see `/Users/dp/projects/ksi/CLAUDE.md`*