# KSI Daemon Architecture Analysis

## Executive Summary

The KSI daemon is a sophisticated event-driven system built on pure async Python patterns. It implements a clean separation between infrastructure (event routing, discovery, state management) and application logic (agents, orchestration, completion services). The architecture is designed for extensibility, with particular attention to dynamic discovery, transformer patterns, and service isolation.

## 1. Core Event System Architecture

### 1.1 EventRouter (event_system.py)

The heart of KSI is the `EventRouter` class - a pure async event bus that manages all inter-module communication:

```python
class EventRouter:
    def __init__(self):
        self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._pattern_handlers: List[Tuple[str, EventHandler]] = []
        self._transformers: Dict[str, Dict[str, Any]] = {}
        self._services: Dict[str, Any] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
```

**Key Features:**
- **Priority-based handler execution** with EventPriority levels (HIGHEST=0 to LOWEST=100)
- **Pattern matching** for wildcard event handlers (e.g., "state:*")
- **Middleware support** for cross-cutting concerns
- **Coordinated shutdown** with acknowledgment protocol
- **Error propagation modes** - catch & log vs propagate for debugging

### 1.2 EventHandler Wrapper

Each handler is wrapped with metadata for introspection:

```python
class EventHandler:
    def __init__(self, func, event, priority, filter_func):
        self.func = func
        self.event = event
        self.priority = priority
        self.filter_func = filter_func
        self.is_async = inspect.iscoroutinefunction(func)
        self.module = func.__module__
        self.name = func.__name__
```

### 1.3 Decorator Patterns

The system uses decorators for auto-registration at import time:

```python
@event_handler("system:startup")
async def handle_startup(data: Dict[str, Any]) -> Dict[str, Any]:
    # Handler auto-registers with router at import
```

**Available Decorators:**
- `@event_handler` - Register event handlers with priority and filters
- `@service_provider` - Register service instances
- `@shutdown_handler` - Register critical shutdown handlers
- `@background_task` - Mark background tasks for discovery

## 2. Discovery System Implementation

### 2.1 AST-Based Analysis (discovery_utils.py)

The discovery system uses Python's AST to extract handler information without execution:

```python
class HandlerAnalyzer(ast.NodeVisitor):
    def __init__(self, source_lines, module_tree, source_line_offset):
        self.data_gets = {}  # data.get() calls
        self.data_subscripts = set()  # data["key"] access
        self.triggers = []  # Events emitted
        self.typed_dicts = {}  # TypedDict definitions
```

**Key Capabilities:**
- Extracts parameters from `data.get()` calls with defaults
- Identifies TypedDict annotations for type information
- Finds inline comments for parameter descriptions
- Discovers events emitted by handlers
- Supports structured validation patterns in comments

### 2.2 TypedDict Support

The system can extract rich type information from TypedDict definitions:

```python
class AgentSpawnData(TypedDict):
    agent_id: str
    profile: NotRequired[str]
    session_id: NotRequired[str]
```

This provides actual types instead of "Any" in discovery output.

### 2.3 Multiple Output Formats

Discovery supports various formats for different consumers:
- **verbose** - Full nested structure (default)
- **compact** - Abbreviated keys, arrays for parameters
- **ultra_compact** - Minimal size for network efficiency
- **mcp** - MCP tool-compatible JSON Schema format

## 3. Module System & Dynamic Loading

### 3.1 Import-Based Loading

Modules are loaded via simple Python imports in `daemon_core.py`:

```python
async def _import_all_modules(self):
    # Core modules (dependency order matters)
    import ksi_daemon.core.state
    import ksi_daemon.core.discovery
    import ksi_daemon.transport.unix_socket
    import ksi_daemon.agent.agent_service
    # ... etc
```

**Benefits:**
- No complex discovery mechanism
- Clear dependency ordering
- Python's import system handles caching
- Decorators auto-register at import time

### 3.2 Module Lifecycle

1. **Import** - Module code executes, decorators register
2. **system:startup** - Modules initialize resources
3. **system:context** - Modules receive shared context
4. **system:ready** - Background tasks start
5. **system:shutdown** - Coordinated cleanup

## 4. Service Infrastructure

### 4.1 Service Registration

Services are registered via the `@service_provider` decorator or directly:

```python
@service_provider("transformer_service")
def create_transformer_service():
    return TransformerService()
```

### 4.2 Background Tasks

Background tasks are managed by the router:

```python
await router.start_task("task_name", coroutine)
```

Tasks are tracked by module for discovery and shutdown coordination.

## 5. Transformer System

### 5.1 Core Transformer Engine (event_system.py)

The EventRouter includes a built-in transformer engine:

```python
def register_transformer_from_yaml(self, transformer_def):
    # transformer_def contains:
    # - source: source event pattern
    # - target: target event
    # - mapping: field transformations
    # - async: whether it's async
    # - response_route: response routing config
```

### 5.2 Transformer Features

**Mapping Engine:**
```python
def _apply_mapping(self, mapping, data):
    # Supports:
    # - Template syntax: {{source.field}}
    # - Nested field access
    # - Static values
    # - Nested target creation
```

**Async Transformers:**
- Generate tracking IDs for request/response correlation
- Support response routing to different events
- Can inject results back to originating agents

**Conditional Execution:**
```python
def _evaluate_condition(self, condition, data):
    # Simple conditions: field == value, field > value
```

### 5.3 Pattern-Level Management (transformer_service.py)

The TransformerService provides high-level pattern management:

```python
class PatternTransformerInfo:
    pattern_name: str
    file_path: str
    transformer_sources: List[str]  # Source events
    loaded_by: Set[str]  # Reference counting
    transformers_data: List[Dict[str, Any]]
```

**Features:**
- Load transformers from YAML patterns
- Reference counting for shared patterns
- Hot-reload support
- Integration with orchestration patterns

## 6. Agent System Integration

### 6.1 Agent Lifecycle

Agents are managed through events:
- **agent:spawn** - Create new agent with profile/composition
- **agent:send_message** - Send message to agent
- **agent:terminate** - Cleanup agent resources

### 6.2 Session Management

The agent service integrates with the completion service for session tracking:
- Session IDs are generated by claude-cli
- Each completion returns a new session_id
- Agents track session continuity across requests

### 6.3 Agent Persistence

Agents are stored in the graph database system:
```python
# Entity type: "agent"
# Properties: status, profile, capabilities, session_id, etc.
# Relationships: spawned_by, observes, etc.
```

## 7. Storage & Persistence

### 7.1 Graph Database (state.py)

A clean entity-property-relationship model:

```sql
-- Core tables
entities (id, type, created_at, updated_at)
properties (entity_id, property, value, value_type)
relationships (from_id, to_id, relation_type, metadata)
```

**Features:**
- Type-aware serialization (json, boolean, number, string)
- Efficient property queries
- Relationship traversal
- WAL mode for concurrency

### 7.2 Event Log

Reference-based event logging for audit and replay:
- Events logged with originator, construct, correlation IDs
- Large payloads stripped, file references preserved
- Async write-through to avoid blocking

## 8. Key Extension Points

### 8.1 MCP Integration Strategy

The current MCP implementation (`mcp_service.py` and `dynamic_server.py`) shows the pattern:

1. **Dynamic Tool Generation**
   - Query agent's allowed_events from permission/agent service
   - Use discovery system to get event schemas
   - Generate MCP tools matching KSI events

2. **Thin Handshake Optimization**
   - Cache session data for known agent/conversation pairs
   - Return minimal tool schemas on reconnect
   - Track tool usage in SQLite database

3. **Permission-Based Filtering**
   - Tools generated based on resolved agent capabilities
   - Raw event access only for trusted profiles

### 8.2 Tool Wrapping Patterns

To wrap external tools as KSI events:

1. **Discovery Integration**
   - Extend HandlerAnalyzer to parse tool metadata
   - Support @tool decorator alongside @event_handler
   - Generate synthetic TypedDict from tool schemas

2. **Transformer Mapping**
   - Use transformer system to map tool calls to events
   - Response routing for async tool execution
   - Error handling via event:error pattern

3. **Namespace Isolation**
   - Tools could live in dedicated namespaces (e.g., "tool:*")
   - Permission system already supports namespace-based access
   - Discovery can filter by namespace

### 8.3 Discovery Extension Points

1. **Rich Metadata Extraction**
   - Current: AST analysis of Python code
   - Potential: Parse tool decorators, JSON schemas, OpenAPI specs

2. **Multi-Language Support**
   - Discovery utils could have pluggable analyzers
   - Support TypeScript, JSON Schema, Protocol Buffers

3. **Dynamic Registration**
   - Events could register their own discovery metadata
   - Runtime schema updates for dynamic tools

### 8.4 Namespace Management

Current namespace patterns:
- **system:** - Core daemon operations
- **agent:** - Agent lifecycle
- **state:** - State management
- **completion:** - LLM completions
- **evaluation:** - Prompt evaluation
- **orchestration:** - Multi-agent patterns
- **composition:** - Profile/prompt management
- **transformer:** - Event transformation
- **mcp:** - MCP server management

Extension strategy:
- **tool:** - External tool wrappers
- **service:** - External service integrations
- **workflow:** - Higher-level workflows
- Custom namespaces per integration

## 9. Architecture Patterns

### 9.1 Event-First Design

Everything is an event:
- No direct function calls between modules
- All communication via event emission
- Natural audit trail and observability

### 9.2 Composition Over Inheritance

- No complex class hierarchies
- Modules compose functionality via events
- Transformers compose event flows

### 9.3 Progressive Enhancement

- Core system works with minimal modules
- Each module adds capabilities via events
- Discovery reveals available functionality

### 9.4 Fail-Safe Patterns

- Event handlers isolated - one failure doesn't crash system
- Graceful degradation when modules unavailable
- Comprehensive error events for debugging

## 10. Design Decisions

### 10.1 Pure Python Imports
- **Decision**: Use Python imports vs dynamic loading
- **Rationale**: Simplicity, IDE support, clear dependencies
- **Trade-off**: Less dynamic but more maintainable

### 10.2 AST-Based Discovery
- **Decision**: Parse code with AST vs runtime introspection
- **Rationale**: Rich metadata without execution, inline comments
- **Trade-off**: Python-specific, requires code access

### 10.3 Event-Based Everything
- **Decision**: All inter-module communication via events
- **Rationale**: Loose coupling, natural observability
- **Trade-off**: Indirection, potential performance overhead

### 10.4 Graph Database Model
- **Decision**: EAV pattern in SQLite vs key-value store
- **Rationale**: Flexible schema, relationship support, queries
- **Trade-off**: More complex than key-value

## Implementation Recommendations for MCP Integration

Based on this analysis, here are specific recommendations for enhancing MCP integration:

### 1. Extend Discovery for Tool Metadata

Add tool-specific metadata extraction:
```python
# In HandlerAnalyzer
def visit_Decorator(self, node):
    if node.decorator.id == "tool":
        # Extract tool metadata
        self.tool_metadata = extract_tool_info(node)
```

### 2. Create Tool-to-Event Transformers

Use the transformer system for bidirectional mapping:
```yaml
transformers:
  - source: "tool:execute"
    target: "{{tool_name}}"
    mapping:
      params: "{{parameters}}"
    async: true
    response_route:
      from: "{{tool_name}}:result"
      to: "tool:result"
```

### 3. Implement Tool Registry Service

New service for tool management:
```python
@event_handler("tool:register")
async def handle_tool_register(data):
    tool_def = data["definition"]
    # Store tool schema
    # Generate transformer
    # Update discovery cache
```

### 4. Enhance MCP Dynamic Server

Integrate with tool registry:
```python
async def _get_available_tools(self, agent_info):
    # Get KSI events (current)
    ksi_tools = await self._generate_tools_for_agent(agent_info)
    
    # Get registered tools (new)
    tool_result = await self.ksi_client.send_event(
        "tool:list",
        {"agent_id": agent_info["agent_id"]}
    )
    
    return ksi_tools + tool_result.get("tools", [])
```

This architecture provides a solid foundation for advanced MCP integration while maintaining the system's event-driven principles and discovery capabilities.