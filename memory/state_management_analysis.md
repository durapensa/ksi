# KSI State Management Analysis

## Overview

This document analyzes the different state management approaches used across the KSI system, examining their patterns, storage mechanisms, recovery strategies, and performance characteristics.

## State Management Categories

### 1. Relational State System (ksi_daemon/core/state.py)

**Type**: Agent application data
**Storage**: SQLite database at `var/db/state.db`
**Pattern**: Entity-Property-Relationship (EPR) model

**Characteristics**:
- Persistent SQLite storage with proper indexes
- Entities with properties (EAV pattern)
- Typed relationships between entities
- Automatic timestamping (numeric storage, ISO display)
- ACID guarantees from SQLite

**Initialization**:
- Created during `system:startup` via `initialize_state()`
- Database schema auto-created if missing
- No data migration needed (schema is stable)

**Recovery**:
- Full persistence - survives all restarts
- No special recovery needed
- Relationships maintain referential integrity

**Performance**:
- Indexed queries for common patterns
- Ring buffer not needed (direct DB writes)
- Suitable for moderate frequency updates

**Use Cases**:
- Agent metadata and relationships
- Long-lived configuration
- Inter-agent relationships (spawned, observes)
- Any data that agents need to persist

### 2. Event Log System (ksi_daemon/event_log.py)

**Type**: System infrastructure monitoring
**Storage**: Hybrid - Ring buffer (memory) + SQLite
**Pattern**: Time-series event stream

**Characteristics**:
- In-memory ring buffer (10k events default)
- SQLite persistence for durability
- Payload stripping for large content
- Real-time streaming subscriptions
- Pull-based monitoring (no broadcast overhead)

**Initialization**:
- Started during `system:startup`
- Database created if missing
- Ring buffer allocated in memory

**Recovery**:
- Ring buffer lost on restart (by design)
- SQLite data persists
- No recovery needed - monitoring data

**Performance**:
- High-performance ring buffer for recent events
- Async SQLite writes for persistence
- Optimized for high-frequency logging

**Use Cases**:
- System monitoring
- Debug/troubleshooting
- Event replay
- Pattern analysis

### 3. Agent Service State (ksi_daemon/agent/agent_service.py)

**Type**: Runtime agent registry
**Storage**: Hybrid - Memory + File (identities only)
**Pattern**: In-memory dictionaries with selective persistence

**Memory State**:
```python
agents: Dict[str, Dict[str, Any]] = {}  # Active agents
identities: Dict[str, Dict[str, Any]] = {}  # Agent identities
agent_threads: Dict[str, asyncio.Task] = {}  # Running tasks
```

**Persistent State**:
- Only identities saved to `var/state/agent_identities.json`
- Active agents reconstructed on demand

**Initialization**:
- Load identities from disk during `system:startup`
- Empty agent registry (agents spawn on demand)

**Recovery**:
- Identities restored from file
- Active agents lost (must be respawned)
- Agent state also tracked in relational DB

**Performance**:
- O(1) lookups for active agents
- Minimal I/O (only identity saves)
- Message queues in memory

### 4. Completion Service State (ksi_daemon/completion/completion_service.py)

**Type**: Request queue management
**Storage**: Memory only (with checkpoint support)
**Pattern**: Per-session queues + active request tracking

**Memory State**:
```python
active_completions: Dict[str, Dict[str, Any]] = {}
session_processors: Dict[str, asyncio.Queue] = {}
active_sessions: set = set()
```

**Characteristics**:
- Fork prevention via per-session queues
- Active request tracking
- No direct persistence
- Checkpoint system provides recovery

**Initialization**:
- Empty state on startup
- Queues created on demand

**Recovery**:
- Checkpoint system preserves queue state
- Requests re-emitted after restart
- Failed requests marked for retry

**Performance**:
- AsyncIO queues for concurrency
- Memory-only for speed
- Scales with active sessions

### 5. Checkpoint System (ksi_daemon/core/checkpoint.py)

**Type**: Universal state preservation
**Storage**: SQLite at `var/db/checkpoints.db`
**Pattern**: Snapshot-based recovery

**Characteristics**:
- Automatic on all shutdowns
- Manual checkpoint operations
- Keeps last 5 checkpoints
- Shielded from cancellation during save

**Data Captured**:
- Completion queue contents
- Active completion states
- Session information
- Designed for extensibility

**Recovery Process**:
1. Wait for `system:ready`
2. Load latest checkpoint
3. Re-emit queued requests
4. Mark interrupted requests for retry

**Performance**:
- Async SQLite operations
- Only saves meaningful state
- Fast restore after startup

### 6. MCP Session Cache (ksi_daemon/mcp/dynamic_server.py)

**Type**: Token optimization cache
**Storage**: SQLite at `var/db/mcp_sessions.db`
**Pattern**: Session-based tool caching

**Characteristics**:
- Persists tool descriptions per session
- Thin handshake after first request
- Automatic cleanup of old sessions

**Recovery**:
- Full persistence
- Cache rebuilt on demand
- No critical data loss

### 7. Conversation Service Cache (ksi_daemon/conversation/conversation_service.py)

**Type**: Metadata cache
**Storage**: Memory with TTL
**Pattern**: Time-based cache invalidation

**Memory State**:
```python
conversation_cache: Dict[str, Dict[str, Any]] = {}
cache_timestamp: Optional[datetime] = None
cache_ttl_seconds = 60
```

**Characteristics**:
- 60-second TTL
- Rebuilt from file scanning
- Pure optimization (no data loss)

**Recovery**:
- No recovery needed
- Cache rebuilt on first access

### 8. Composition Index (ksi_daemon/composition/composition_index.py)

**Type**: YAML composition registry
**Storage**: Memory index of file system
**Pattern**: File-based with memory index

**Characteristics**:
- Scans YAML files on startup
- Memory index for fast lookups
- File system is source of truth

**Recovery**:
- Rebuilt from files on startup
- No persistence needed

### 9. Observation Subscriptions (ksi_daemon/observation/observation_manager.py)

**Type**: Event routing rules
**Storage**: Dual - Memory + Relational State
**Pattern**: Runtime subscriptions with persistence

**Memory State**:
```python
_observers: Dict[str, Set[ObserverInfo]] = {}
_rate_limiters: Dict[str, RateLimiter] = {}
```

**Persistent State**:
- Stored as entities/relationships in state DB
- Type: "observation_subscription"

**Recovery**:
- Subscriptions restored from state DB
- Rate limiters recreated
- Full recovery of observation patterns

### 10. Message Bus Subscriptions (ksi_daemon/messaging/message_bus.py)

**Type**: Pub/sub routing
**Storage**: Memory only
**Pattern**: Runtime subscriptions

**Memory State**:
```python
subscriptions: Dict[str, Set[str]] = {}  # topic -> subscribers
subscriber_queues: Dict[str, asyncio.Queue] = {}
```

**Characteristics**:
- No persistence (runtime only)
- Subscribers must re-subscribe
- Queues created on demand

**Recovery**:
- No automatic recovery
- Agents re-subscribe on startup

## State Management Patterns

### 1. Pure Memory Pattern
Used by: Message bus, active agents, conversation cache

**When to use**:
- Runtime-only data
- Can be rebuilt or re-subscribed
- Performance critical
- No persistence requirements

### 2. SQLite Persistence Pattern
Used by: Relational state, event log, checkpoints, MCP cache

**When to use**:
- ACID guarantees needed
- Complex queries required
- Structured data with relationships
- Long-term persistence

### 3. File-Based Pattern
Used by: Agent identities, compositions, response logs

**When to use**:
- Simple key-value data
- Human-readable format needed
- Infrequent updates
- Git-friendly storage

### 4. Hybrid Memory+Persistence Pattern
Used by: Event log (ring buffer + SQLite), observations (memory + state DB)

**When to use**:
- High-performance recent access
- Historical data preservation
- Best of both worlds needed

### 5. Checkpoint/Restore Pattern
Used by: Completion service via checkpoint system

**When to use**:
- Complex runtime state
- Graceful degradation acceptable
- State can be re-emitted

## Initialization Lifecycle

### Phase 1: Core Infrastructure (synchronous)
1. Event log initialization
2. State manager initialization (SQLite schema)
3. Module imports (auto-registration)

### Phase 2: Module Startup (via system:startup)
1. Each module initializes its storage
2. Loads persistent data if needed
3. Creates runtime structures

### Phase 3: Context Distribution (via system:context)
1. Modules receive shared infrastructure
2. State manager reference distributed
3. Event emitter available

### Phase 4: Service Ready (via system:ready)
1. Background tasks started
2. Checkpoint restore executed
3. System fully operational

## Recovery Strategies

### 1. Full Persistence (State DB, MCP cache)
- No special recovery needed
- Data survives all restarts
- Automatic schema creation

### 2. Checkpoint/Restore (Completion queues)
- Snapshot before shutdown
- Restore after services ready
- Re-emit interrupted work

### 3. Rebuild from Source (Compositions, conversations)
- Scan file system
- Rebuild memory structures
- No data loss

### 4. Re-subscribe Pattern (Message bus, some observations)
- Agents re-establish subscriptions
- No automatic recovery
- Clean slate approach

### 5. Identity Preservation (Agent identities)
- Minimal data persisted
- Agents respawned with identity
- State reconstructed

## Performance Characteristics

### High-Frequency Updates
- Event log: Ring buffer for recent, SQLite for history
- Message bus: Pure memory queues
- Active agents: In-memory dictionaries

### Moderate-Frequency Updates
- Relational state: SQLite with indexes
- Agent identities: Periodic file writes
- Checkpoints: On shutdown only

### Read-Heavy Workloads
- Conversation cache: TTL-based invalidation
- Composition index: Memory after startup scan
- MCP cache: Session-based optimization

### Write-Heavy Workloads
- Event log: Optimized ring buffer
- Message queues: AsyncIO native
- No write amplification

## Best Practices

### 1. Choose Storage by Lifecycle
- Runtime only → Memory
- Survives restart → SQLite/File
- Monitoring/Debug → Event log

### 2. Separation of Concerns
- Event log for infrastructure monitoring
- Relational state for agent application data
- Don't mix monitoring with business data

### 3. Recovery Planning
- Critical state → Full persistence
- Recoverable state → Checkpoint/restore
- Ephemeral state → Memory only

### 4. Performance Optimization
- Ring buffers for high-frequency
- Indexes for complex queries
- Caching for read-heavy data

### 5. Consistency Patterns
- Single source of truth per data type
- Clear ownership (which module manages what)
- Event-based synchronization

## Migration Guidelines

When adding new state:

1. **Identify characteristics**:
   - Frequency of updates
   - Persistence requirements
   - Query patterns
   - Recovery needs

2. **Choose pattern**:
   - Memory only if ephemeral
   - SQLite if complex queries
   - File if human-readable
   - Hybrid if performance critical

3. **Implement lifecycle**:
   - Initialize in system:startup
   - Clean up in system:shutdown
   - Handle recovery if needed

4. **Document ownership**:
   - Which module owns the state
   - What events modify it
   - Recovery expectations