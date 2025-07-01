# KSI Technical Knowledge

Core technical reference for KSI (Knowledge System Interface) - a minimal daemon system for managing Claude AI processes with conversation continuity and multi-agent orchestration.

**Current State**: 19 plugins loading successfully. Pure asyncio implementation with event-driven patterns. 

**Critical Lesson Learned**: Previous agent experiments without proper logging and isolation resulted in agents compromising the KSI system itself. Event persistence and security controls are now mandatory prerequisites before any agent activation.

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

2. **Async Task Management** (Pure Asyncio):
   ```python
   @hookimpl
   def ksi_ready():
       return {
           "service": "completion_service",
           "tasks": [{"name": "service_manager", "coroutine": manage_completion_service()}]
       }
   ```
   Core daemon uses Python 3.11+ asyncio.TaskGroup for structured concurrency.

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

### Completion System (v3 - Pure Asyncio)
- **completion/completion_service.py** - Pure asyncio with TaskGroup
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

## Completion Service v3 (Pure Asyncio)

### Architecture
- **Pure Asyncio**: Uses Python 3.11+ asyncio.TaskGroup for structured concurrency
- **Event-Driven Shutdown**: Monitors shutdown_event instead of sleep_forever() polling
- **Smart Routing**: Immediate processing for sessionless/free sessions, queuing for busy
- **Per-Session Fork Prevention**: Dynamic per-session queues only when needed

### Session ID Management
- **Claude-cli returns NEW session_id from EVERY request** (even continuations)
- **Log filenames**: `var/logs/responses/{session_id}.jsonl` (not request_id)
- **Conversation flow**: Use previous response's session_id as input → get new session_id
- **IMPORTANT**: Session IDs are generated by claude-cli and cannot be changed
- **Federation**: Future enhancement may add ksi-node identifiers but core IDs remain provider-owned

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

### Future Enhancements (Not Current Priority)

#### Session ID Federation (Long Term)
- **Constraint**: Session IDs are generated by claude-cli and cannot be changed
- **Approach**: Add ksi-node identifiers as metadata layer
- **Purpose**: Enable cross-provider conversation continuity
- **Status**: Deferred - provider-specific IDs are fundamental constraint

#### Distributed Architecture (Long Term)
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

### Next Priority: Agent System Activation
1. **Agent System Activation** (3-4 days) 🚀
   - Create first working agents WITH security constraints ✅
   - Implement permission-aware orchestration patterns
   - Leverage completed permission system for safe execution
   - Test multi-agent collaboration with sandboxes
   - **Prerequisites**: ✅ Event persistence + ✅ isolation controls COMPLETE
   - **Impact**: Demonstrate system value proposition safely

### Production Optimization
4. **Performance Optimization** (2-3 days)
   - Claude CLI subprocess spawning adds ~7s overhead
   - Investigate process pooling or alternative approaches
   - **Impact**: Significantly faster response times

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


## Completed Infrastructure

### Event Log Persistence ✅
- **AsyncSQLiteEventLog**: Non-blocking write queue with batching for zero performance impact
- **Real-time Monitoring**: Event subscriptions and real-time streaming via monitor plugin
- **Structured Queries**: SQL query support for session analysis and correlation chain tracing
- **Retention Management**: Automatic cleanup with configurable retention periods
- **APIs**: `monitor:subscribe`, `monitor:query`, `monitor:get_session_events`, `monitor:get_correlation_chain`
- **Database**: SQLite with WAL mode at `var/db/events.db`

### Code Quality Improvements ✅
- **Function-based Architecture**: Replaced static classes (TimestampManager, FileOperations) with module-level functions
- **Dict-based Responses**: Simplified CompletionResponse class to standardized dict format with helper functions
- **Async Consolidation**: Pure asyncio patterns with centralized async utilities (`ksi_common/async_utils.py`)
- **Removed Wrappers**: Eliminated thin wrapper functions, use direct stdlib calls

## Completed Infrastructure (June 2025)

### Agent Isolation & Permissions ✅
- **Status**: Implementation complete and tested
- **Documentation**: `/docs/agent_permissions_system_plan.md`
- **Architecture**: Compositional permission system with flexible sandbox isolation
- **Key Components**:
  - `ksi_common/agent_permissions.py` - Permission profiles and validation
  - `ksi_common/sandbox_manager.py` - Sandbox lifecycle management  
  - `ksi_daemon/plugins/permissions/` - Permission service plugin
  - 4 permission profiles: restricted, standard, trusted, researcher
- **Sandbox Modes**:
  - **Isolated**: Complete separation per agent
  - **Shared**: Session-wide collaboration workspace
  - **Nested**: Parent-child workspace relationships
- **Security Features**:
  - Additive permissions (fail-safe defaults)
  - No privilege escalation (children ≤ parent permissions)
  - Filesystem isolation via claude-cli cwd sandboxing
  - Tool restrictions passed to claude-cli --allowedTools
  - Full audit trail of all permission operations
- **Integration**: Seamless with agent spawn/terminate, completion service, monitoring
- **Impact**: Safe agent experimentation environment ready for use

## Modern TUI System ✅ (NEW)

### Overview
- **Status**: Core implementation complete with ksi-chat and ksi-monitor
- **Architecture**: Component-based with clean separation of concerns
- **Location**: `ksi_tui/` package with modular structure
- **Documentation**: `/docs/migration_to_new_tui.md` for transition guide

### Completed Applications
1. **ksi-chat**: Focused chat interface
   - Clean, distraction-free design
   - Automatic session management
   - Real-time connection status
   - Export to markdown/JSON
   - Beautiful message rendering

2. **ksi-monitor**: Real-time monitoring dashboard
   - Multi-pane dashboard layout
   - Live event stream with filtering
   - Agent tree view with details
   - Performance metrics with graphs
   - System health indicators

### Architecture Components
- **Components**: Reusable UI widgets (`MessageBubble`, `EventStream`, `MetricsBar`, `ConnectionStatus`)
- **Services**: Clean abstractions (`ChatService`, `MonitorService`)
- **Themes**: Catppuccin-inspired dark theme with CSS variables
- **Utils**: Formatting utilities for consistent display

### Design Principles
- **Focused Applications**: Each app does one thing well
- **Component-Based**: Reusable widgets for consistency
- **Service Layer**: Business logic separated from UI
- **Reactive**: Automatic UI updates with reactive attributes
- **Keyboard-First**: Intuitive shortcuts for all operations
- **Beautiful**: Consistent Catppuccin theme throughout

### Migration Path
- Old interfaces remain available during transition
- New apps are simpler with focused functionality
- See `/docs/migration_to_new_tui.md` for details

## Ready for Implementation

### Agent System Activation
- **Status**: Infrastructure complete, permissions ready, awaiting activation
- **Prerequisites**: ✅ Isolation controls implemented and tested
- **Next Steps**: Create working agents using the composition system
- **Impact**: Can now safely demonstrate multi-agent orchestration
- **Safety**: Full sandbox isolation and permission enforcement active

### Remaining TUI Applications
1. **ksi-history**: Conversation browser with search
   - Full-text search across sessions
   - Timeline visualization
   - Bulk export functionality
   
2. **ksi-agents**: Multi-agent coordinator
   - Agent spawn/terminate controls
   - Conversation flow visualization
   - Permission management UI

---
*For development practices, see `/Users/dp/projects/ksi/CLAUDE.md`*