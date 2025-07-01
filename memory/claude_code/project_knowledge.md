# KSI Technical Knowledge

Core technical reference for KSI (Knowledge System Interface) - a minimal daemon system for managing Claude AI processes with conversation continuity and multi-agent orchestration.

**Current State**: 19 plugins loading successfully. Pure asyncio implementation with event-driven patterns. Enhanced with hybrid introspection system for rich parameter discovery. 

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

## Hybrid Introspection System ✅ (NEW)

### Overview
- **Status**: Implementation complete with 4-layer hybrid approach
- **Purpose**: Rich parameter discovery without manual maintenance
- **Impact**: Claude and other consumers get complete parameter info automatically

### The Four Layers

1. **AST-Based Discovery** (Automatic)
   - Analyzes function body to find `data.get()` calls
   - Works with existing code without modifications
   - Detects required vs optional parameters and defaults
   - Always in sync with actual implementation

2. **TypedDict Support** (Type Safety)
   - Optional type-safe parameter definitions
   - Full IDE support and type checking
   - Import from `ksi_daemon.event_types`
   - Example: `@event_handler("state:set", data_type=StateSetData)`

3. **Docstring Enhancement** (Descriptions)
   - Extracts human-readable descriptions
   - Supports standard Args/Parameters sections
   - Maintains documentation close to code

4. **Enhanced Metadata** (Rich Discovery)
   - Import from `ksi_daemon.enhanced_decorators`
   - Comprehensive metadata including:
     - Performance characteristics (async, duration, side effects)
     - Resource requirements (cost, auth, rate limits)
     - Constraints and allowed values
     - Examples with expected results
     - Best practices and common errors
     - Related events

### Usage Examples

**Basic (AST only):**
```python
@event_handler("my:event")
def handle_my_event(data: Dict[str, Any]) -> Dict[str, Any]:
    param1 = data.get("param1")  # Automatically discovered
```

**With TypedDict:**
```python
from ksi_daemon.event_types import MyEventData

@event_handler("my:event", data_type=MyEventData)
def handle_my_event(data: MyEventData) -> Dict[str, Any]:
    param1 = data["param1"]  # Type-safe access
```

**Enhanced Metadata:**
```python
from ksi_daemon.enhanced_decorators import enhanced_event_handler, EventParameter

@enhanced_event_handler(
    "critical:event",
    parameters=[
        EventParameter(
            name="action",
            type="string",
            description="Action to perform",
            allowed_values=["start", "stop"],
            example="start"
        )
    ],
    has_cost=True,
    typical_duration_ms=5000,
    best_practices=["Check status before action"]
)
```

### Key Benefits
- **Zero Maintenance**: Parameters discovered from code
- **Gradual Enhancement**: Add types/metadata as needed
- **Always Accurate**: Can't get out of sync
- **Rich Discovery**: Claude gets complete context

## Python Introspection Patterns for Discovery

### Event Handler Decorator Pattern
```python
@event_handler("permission:list_profiles")
def handle_list_profiles(data: Dict[str, Any]) -> Dict[str, Any]:
    """List available permission profiles.
    
    Returns:
        profiles: Dictionary containing all permission profiles
    """
    return {"profiles": {...}}
```

The decorator automatically extracts:
- Event name from decorator argument
- Summary from first line of docstring
- Parameters from function signature and type hints
- Return info from docstring Returns section

### Metadata Extraction from Functions
```python
def _extract_metadata(func: Callable) -> Dict[str, Any]:
    # 1. Extract docstring and parse sections
    docstring = inspect.getdoc(func)
    
    # 2. Get function signature and type hints
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)
    
    # 3. Parse parameter documentation from docstring
    # Supports Args:, Parameters:, Returns: sections
    
    # 4. Build complete event metadata
    return {
        "event": event_name,
        "summary": first_line_of_docstring,
        "parameters": extracted_params
    }
```

### Dynamic Namespace Pattern (Client)
```python
class EventNamespace:
    def __getattr__(self, event_name: str) -> Callable:
        # Handle Python keywords (async -> async_)
        if event_name == "async_":
            event_name = "async"
        
        # Create method dynamically
        async def event_method(**kwargs):
            return await self._client.send_event(full_event, kwargs)
        
        # Add metadata from discovery
        event_method.__doc__ = discovered_doc
        return event_method

# Usage: client.completion.async_(...) 
```

### Plugin Self-Description
```python
@hookimpl
def ksi_describe_events() -> Dict[str, List[Dict[str, Any]]]:
    """Auto-discover events from decorated handlers."""
    return collect_event_metadata(sys.modules[__name__])
```

Plugins describe their own events by:
1. Decorating handlers with `@event_handler`
2. Implementing `ksi_describe_events` hook
3. Discovery service aggregates from all plugins

### Docstring Parameter Parsing
```python
# Regex pattern for parameter documentation
param_pattern = re.compile(r'^\s*(\w+)\s*(?:\(([^)]+)\))?\s*:\s*(.+)$')

# Parses:
#   agent_id (str): The agent ID to query
# Into:
#   {"agent_id": {"type": "str", "description": "The agent ID to query"}}
```

### Type Annotation Introspection
```python
# Convert Python type annotations to discovery metadata
type_map = {
    str: "str",
    int: "int", 
    float: "float",
    bool: "bool",
    list: "list",
    dict: "dict",
    Optional[str]: "str (optional)"
}
```

### Discovery Aggregation Pattern
```python
# Discovery service collects from all plugins
all_events = {}
for plugin in plugin_manager.get_plugins():
    if hasattr(plugin, 'ksi_describe_events'):
        plugin_events = plugin.ksi_describe_events()
        merge_events(all_events, plugin_events)
```

### Key Benefits
1. **Zero Maintenance**: Event metadata lives with implementation
2. **Type Safety**: Extracted from actual function signatures
3. **Self-Documenting**: Docstrings become API documentation
4. **DRY Principle**: Single source of truth for events
5. **IDE Support**: Generated stubs from introspection

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

### Current Priority: Self-Modifying Composition System 🚀 (NEXT)
1. **Pure Declarative Admin System** (2-3 days)
   - **Vision**: Claude agents with admin capabilities modify KSI system through pure composition
   - **Architecture**: Zero hardcoded patterns - admin is just another plugin capability
   - **Implementation**: Extend schema + create admin compositions + implement admin plugins
   - **Safety**: Built into declarative exclusion patterns and validation
   - **Impact**: Self-evolving AI system where admin capabilities are purely compositional

#### Pure Declarative Approach
```yaml
# ksi_capabilities.yaml extension
plugin_capabilities:
  file_plugin:
    events: [file:read, file:write, file:backup, file:rollback]
    context_required: [daemon_commands]
  config_plugin:
    events: [config:get, config:set, config:validate]
    context_required: [daemon_commands, daemon_events]

# system_admin.yaml - just another composition
required_context:
  capabilities:
    plugins: [composition_plugin, file_plugin, config_plugin]
    exclude_events: [file:delete, config:reset]  # Safety through exclusion
```

#### Implementation Plan
- **Extend Capability Schema**: Add file_plugin, config_plugin to ksi_capabilities.yaml
- **Create Admin Compositions**: system_admin.yaml, composition_editor.yaml, schema_manager.yaml
- **Implement Admin Plugins**: Pure event handlers for file/config operations
- **Safety Through Composition**: Use exclude patterns for dangerous operations
- **No Special Logic**: Everything flows through existing declarative system

### Completed Priority: Agent System Foundation
1. **Agent System Infrastructure** ✅ COMPLETE
   - Declarative capability system with plugin-native architecture
   - Zero hardcoded logic - pure configuration-driven behavior  
   - Enhanced security with granular permission boundaries
   - **Prerequisites**: ✅ Event persistence + ✅ isolation controls + ✅ capability system
   - **Impact**: Foundation ready for self-modifying agent deployment

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

### Declarative KSI Capability System ✅ (REVOLUTIONARY)
- **Status**: Complete plugin-native implementation with discovery-driven architecture
- **Architecture**: Zero hardcoded capability logic - pure declarative configuration
- **Schema**: `var/lib/capabilities/ksi_capabilities.yaml` (tracked in git)
- **Key Innovation**: Plugin-based capabilities mapped to actual events from `system:discover`

#### Plugin-Native Architecture
```yaml
# Plugin-based capability declarations
plugin_capabilities:
  completion_plugin:
    events: [completion:async, completion:status, completion:cancel]
    context_required: [daemon_commands]
  agent_plugin:  
    events: [agent:spawn, agent:list, agent:terminate]
    context_required: [daemon_commands, daemon_events]
```

#### Capability Groups with Safety Patterns
- **minimal**: Basic completion only (`completion_plugin`)
- **standard**: Completion + conversation (`completion_plugin`, `conversation_plugin`)
- **orchestrator**: Multi-agent coordination (4 plugins)
- **full_ksi**: Everything current + auto-expansion for future plugins
- **[all]/[exclude]**: Advanced permission patterns for precise control

#### Composition Integration
```yaml
# Compositions declare precise plugin needs
required_context:
  capabilities: orchestrator  # Simple group
  # OR
  capabilities:
    plugins: [completion_plugin, agent_plugin]
    exclude: [system_plugin]  # Safety restrictions
```

#### Smart Context Resolution
- **Discovery-Driven**: Capabilities auto-updated from `system:discover` 
- **Plugin-Aligned**: Maps directly to real plugin events
- **Future-Proof**: New plugins automatically included in schema
- **Introspectable**: `composition:capabilities` event for runtime queries
- **Zero Maintenance**: No Python code changes for new capabilities

#### Security & Safety Features
- **Granular Control**: Per-plugin, per-event permission boundaries
- **Safety Patterns**: `[exclude]` for removing dangerous capabilities
- **Experimental Control**: Pure vs KSI-aware agent selection
- **Audit Trail**: All capability resolutions logged with reasoning

#### Impact
- **First Truly Declarative Agent System**: All behavior configuration-driven
- **Self-Evolving**: System capabilities grow automatically with plugins
- **Plugin-Native**: Perfect alignment with KSI's plugin architecture
- **Security Boundaries**: Precise permission control for agent isolation

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