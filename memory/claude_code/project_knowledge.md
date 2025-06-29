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
├── var/                # Runtime data (gitignored)
│   ├── run/           # PID file and daemon socket
│   ├── logs/          # Daemon and session logs
│   ├── db/            # SQLite database
│   ├── prompts/       # Legacy prompt templates
│   └── lib/           # Unified compositions
│       ├── compositions/   # All declarative configs
│       ├── fragments/      # Reusable text fragments
│       └── schemas/        # YAML validation schemas
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
- **agent/agent_service.py** - Agent lifecycle with composition integration
- **state/state_service.py** - SQLite-backed persistence
- **messaging/message_bus.py** - Inter-agent pub/sub
- **composition/composition_service.py** - Unified YAML composition system

### Async Queue Infrastructure
- **injection/injection_router.py** - Routes completion results via injection
- **injection/circuit_breakers.py** - Prevents runaway chains
- **conversation/conversation_lock.py** - Prevents conversation forking
- **conversation/conversation_service.py** - Session tracking

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

## Completion Service v2

### Features
- Priority queue (CRITICAL → BACKGROUND)
- Conversation locks prevent forking
- Event-driven injection support
- Circuit breaker protection

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

### Correlation ID Implementation (Near Term)
- **Purpose**: Trace complex event chains across async operations
- **Design**: Hierarchical span IDs (root.span.depth) for parent-child tracking
- **Scope**: Request-level ephemeral tracing (not session continuity)
- **Key Features**:
  - Automatic context propagation through plugins
  - Chain depth limiting to prevent infinite loops
  - Trace visualization for debugging complex flows
  - Performance analysis of multi-hop operations
- **Documentation**: `/Users/dp/projects/ksi/docs/CORRELATION_ID_DESIGN.md`
- **Use Cases**: Completion injection chains, agent coordination flows, error root cause analysis

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

## Recent Architecture Enhancements

### Unified Composition System
- **Architecture**: All configurations (profiles, prompts) use YAML compositions
- **Location**: `var/lib/compositions/` with organized subdirectories
- **Features**: Inheritance, mixins, variable substitution, conditional assembly
- **Integration**: Agent spawning uses composition service for profile resolution
- **Documentation**: `/Users/dp/projects/ksi/docs/UNIFIED_COMPOSITION_ARCHITECTURE.md`

### Agent Spawning Enhancement
- **Fail-Fast**: No fallbacks - explicit profile/composition required
- **Composition Integration**: `agent:spawn` resolves profiles via composition service
- **Dynamic Spawning**: Three modes - `fixed`, `dynamic`, `emergent`
- **Runtime Selection**: `composition:select` event for intelligent composition choice
- **Cross-Plugin Events**: Plugins communicate via shared `emit_event` function

### Event System Enhancement
- **Plugin Context**: All plugins receive `emit_event` for cross-plugin communication
- **Event Routing**: Central event router handles all plugin interactions
- **Async Support**: Coroutine results properly awaited by daemon

### Dynamic Composition System (Implemented)
- **Selection Service**: `composition:select` chooses best composition based on context
- **Runtime Creation**: `composition:create` for on-the-fly composition generation
- **Self-Modification**: `agent:update_composition` allows agents to adapt
- **Peer Discovery**: `agent:discover_peers` finds agents by capabilities
- **Role Negotiation**: `agent:negotiate_roles` enables multi-agent coordination
- **Enhanced Metadata**: Compositions declare capabilities, permissions, compatibility

## Recent Dynamic Agent System Implementation

### Phase 1: Enhanced Composition Service ✓
- Added `composition:select` event for intelligent composition selection
- Added `composition:create` for runtime composition generation
- Extended metadata: capabilities_provided/required, spawns_agents, self_modifiable
- Created adaptive_researcher.yaml as example self-modifying composition

### Phase 2: Agent Self-Modification ✓
- Implemented `agent:update_composition` for runtime adaptation
- Added `agent:discover_peers` for capability-based peer discovery
- Added `agent:negotiate_roles` for dynamic role assignment
- Composition history tracking per agent

### Interface Updates ✓
- Added `--spawn-mode` flag to orchestrate.py (fixed/dynamic/emergent)
- Dynamic mode uses composition selection service
- Emergent mode enables self-organization
- Compositions now treated as hints, not requirements

## Implementation Priorities

### Immediate (This Week)
1. **Correlation ID Infrastructure**
   - Core TraceContext class and span generation
   - EventRouter enhancement for context propagation
   - Critical plugin updates (completion, injection, agent services)
   - Basic trace query API

2. **Architecture Cleanup**
   - Remove remaining multi-socket references
   - Update interfaces to use composition system
   - Clean up test files using old patterns

### Next Sprint
1. **Session Management Phase 1**
   - Session registry with SQLite persistence
   - Fork prevention implementation
   - Basic lifecycle management

2. **Enhanced Monitoring**
   - Trace visualization in monitor interfaces
   - System history presentation
   - Performance metrics extraction

### Future Sprints
- Message routing enhancements (from/to/cc patterns)
- Flexible event delivery modes
- Multicast completion implementation
- Emergency broadcast system

## Composition Library Reorganization (In Progress)

### var/lib Structure
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

## Incomplete Refactors & Intended Functionality

### Profile Loading System
- **Legacy JSON loading**: Still present in `profile_loader.py` for edge cases
- **Status**: Intended fallback, not fully removed
- **Reason**: Some tools may still generate JSON profiles

### Injection System  
- **TODO in injection_router.py**: "Actually inject content into session"
- **Status**: Scaffold implemented, injection logic pending
- **Purpose**: Critical for async completion flows and agent coordination

### Session Management
- **Legacy method names**: e.g., "track_session_output" 
- **Status**: Basic implementation, awaiting full session federation design
- **Purpose**: Foundation for cross-device conversation continuity


### TODOs to Preserve
- Event log file persistence with rotation (planned feature)
- Completion queue cancellation (needed for graceful shutdown)
- Token/time tracking in injection (for resource management)
- Memory metrics in monitor (awaiting implementation)

## Completed Refactors with Legacy Code to Remove

### JSON Profile Migration (Completed)
- **Migration**: All JSON profiles migrated to YAML compositions
- **Legacy code locations**:
  - `profile_loader.py`: JSON loading fallback (no longer needed)
  - `agent_service.py`: Dead profile handlers (never registered)
  - `chat_textual.py`: References to non-existent var/agent_profiles
- **Status**: Safe to remove - no code generates JSON profiles

### Prompt Path Migration (Completed)
- **Migration**: All prompts moved from var/prompts to var/lib/compositions/prompts
- **Legacy code location**:
  - `composition_service.py` lines 93-96: Fallback to non-existent var/prompts
- **Status**: Safe to remove - directory doesn't exist, migration complete

---
*For development practices, see `/Users/dp/projects/ksi/CLAUDE.md`*