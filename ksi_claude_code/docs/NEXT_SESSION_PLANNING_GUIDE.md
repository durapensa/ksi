# KSI Enhancement Planning Guide for Next Claude Code Session

This guide provides a structured approach for the next Claude Code session to research, plan, and develop enhancements to KSI based on our deep architectural understanding.

## Session Context

### What We've Learned
1. **KSI has a graph database** - Full entity-relationship modeling, not just key-value
2. **Rich feature set exists** - Message bus, orchestrations, correlation tracing, event mining
3. **Agents evolve through conversation** - Not prompt modification
4. **Everything is event-driven** - Complete observability and replay capabilities

### Current Integration Status
- ✅ Basic conversation and observation tools implemented
- ✅ Graph state tools created
- ✅ Architectural understanding documented
- ⏳ Advanced features underutilized
- ❌ Key gaps identified (query language, evolution, analytics)

## Research Findings (2024-12-31)

### Current Implementation Analysis

**Graph Database (state.py)**
- Full entity-property-relationship model with SQLite backend
- BFS traversal algorithm with depth limiting
- Good indexing on relationships and entities
- No query language - only event handlers
- Missing: graph algorithms, pattern matching, shortest path

**Event System & Analytics**
- Robust event log with timestamp indexing
- Basic pattern matching (wildcards, SQL LIKE)
- Time-series analysis exists in observation modules
- Frequency analysis, n-gram detection, performance tracking
- Missing: windowed aggregations, complex event processing

**Composition System**
- Sophisticated resolver with inheritance & mixins
- Variable substitution and fragment support
- No actual resolver.py file - logic in composition_service.py
- Could support hot-reload but not implemented
- Perfect foundation for capability evolution

**Resource Management**
- Rate limiting infrastructure exists (RateLimiter class)
- Token budget placeholders in injection system
- No actual tracking or enforcement
- Permission system could be extended

### Graph Database Architecture Decision

After researching embedded graph database options for Python in 2024:

**Option 1: Continue with SQLite + Custom Query Language**
- ✅ No new dependencies, full control
- ✅ Already integrated and working
- ❌ Must build query language from scratch
- ❌ Limited graph algorithms
- ❌ Performance concerns for complex traversals

**Option 2: Migrate to Kùzu (Recommended)**
- ✅ Embedded like SQLite (no server required)
- ✅ Native Cypher support
- ✅ ~18x faster than Neo4j for ingestion
- ✅ Python API with Pandas/Polars integration
- ✅ MIT license, actively developed
- ✅ LangChain integration available
- ❌ Migration effort required
- ❌ New dependency

**Option 3: Lightweight Alternatives**
- **Cozo**: Uses Datalog instead of Cypher
- **SQLite with GraphRAG**: Good for <1000 nodes
- **RedisGraph**: Requires Redis server
- **Memgraph**: In-memory, requires more resources

**Recommendation**: Implement Kùzu as a parallel system first, allowing gradual migration while maintaining backward compatibility.

### Updated Implementation Strategy

**Phase 1: Dual-Database Approach (Week 1)**
1. Add Kùzu alongside SQLite
2. Mirror critical data to both systems
3. Implement Cypher event handlers using Kùzu
4. Keep existing SQLite handlers for compatibility

**Phase 2: Enhanced Analytics (Week 1-2)**
1. Leverage existing observation modules
2. Add windowed aggregations to event log
3. Create time-series event handlers
4. Build on frequency/pattern analysis

**Phase 3: Migration & Evolution (Week 2-3)**
1. Gradually move graph operations to Kùzu
2. Implement capability evolution using compositions
3. Add resource tracking with existing infrastructure
4. Deprecate SQLite graph handlers

## Phase 1: Deep Code Research Tasks

### 1.1 Graph Database Implementation Deep Dive
**Files to examine:**
```
ksi_daemon/core/state.py          # Graph database implementation
ksi_daemon/state/handlers.py      # Event handlers for state operations
ksi_daemon/state/models.py        # SQLAlchemy models
```

**Research questions:**
- How is graph traversal actually implemented?
- What are the performance characteristics?
- Are there hidden capabilities not exposed via events?
- How could we add Cypher-like query support?

**Code patterns to look for:**
```python
# Look for:
- Traversal algorithms (BFS/DFS)
- Query optimization
- Index usage
- Transaction boundaries
- Batch operation support
```

### 1.2 Composition System Internals
**Files to examine:**
```
ksi_daemon/composition/              # Entire module
ksi_daemon/composition/resolver.py   # How compositions are resolved
ksi_daemon/composition/validator.py  # Validation logic
var/lib/compositions/               # Existing compositions
```

**Research questions:**
- How are compositions compiled and cached?
- What's the hot-reload mechanism?
- Can we make compositions truly dynamic?
- How to implement capability evolution?

**Key areas:**
```python
# Focus on:
- Composition compilation process
- Variable substitution mechanism
- Inheritance and mixin resolution
- Runtime composition modification possibilities
```

### 1.3 Event System & Observation Architecture
**Files to examine:**
```
ksi_daemon/core/event_router.py     # Event routing logic
ksi_daemon/observation/             # Observation system
ksi_daemon/core/correlation.py      # Correlation tracking
ksi_daemon/core/reference_event_log.py  # Event storage
```

**Research questions:**
- How does event replay actually work?
- What's the checkpoint/restore implementation?
- How to add time-series analysis?
- Can we build event pattern matching?

### 1.4 Message Bus & Orchestration
**Files to examine:**
```
ksi_daemon/messaging/message_bus.py  # Pub/sub implementation
ksi_daemon/orchestration/           # Orchestration engine
ksi_daemon/orchestration/patterns/  # Existing patterns
```

**Research questions:**
- How do orchestrations compile to execution plans?
- What coordination primitives exist?
- How to make orchestrations composable?
- Can we add graph-aware routing?

### 1.5 Resource Management & Limits
**Files to examine:**
```
ksi_daemon/core/capability_enforcer.py  # Capability checking
ksi_daemon/injection/               # Token management placeholder
ksi_daemon/core/config.py          # Configuration system
```

**Research questions:**
- Where would resource limits plug in?
- How to track resource usage per capability?
- What's the token budget placeholder about?
- How to implement rate limiting?

## Phase 2: Enhancement Prioritization Matrix

| Enhancement | Impact | Complexity | Dependencies | Priority |
|------------|--------|------------|--------------|----------|
| **Graph Query Language** | 🔴 High | 🟡 Medium | Graph DB | **P0** |
| **Time-Series Analytics** | 🔴 High | 🟢 Low | Event Log | **P0** |
| **Agent Capability Evolution** | 🔴 High | 🔴 High | Compositions | **P1** |
| **Resource Limits** | 🔴 High | 🟡 Medium | Capabilities | **P1** |
| **Workflow Composition DSL** | 🟡 Medium | 🟡 Medium | Orchestration | **P2** |
| **Graph-Aware Routing** | 🟡 Medium | 🟢 Low | Message Bus | **P2** |
| **Distributed Sharding** | 🟢 Low | 🔴 High | Federation | **P3** |

## Phase 3: Implementation Planning

### 3.1 Graph Query Language (P0)
**Research first:**
1. Study `state.py` traversal implementation
2. Look for existing query builders
3. Check SQLAlchemy capabilities for graph queries

**Design considerations:**
```cypher
// Example syntax to support
MATCH (a:agent)-[:spawned]->(b:agent)
WHERE a.properties.role = 'coordinator'
RETURN a, b, count(b) as workers

// Path queries
MATCH path = (start:agent)-[:collaborates_with*1..3]->(end:agent)
WHERE start.id = $start_id
RETURN path
```

**Implementation approach:**
1. Parser for Cypher-subset syntax
2. Query planner using existing traversal
3. Result formatter
4. Performance optimization

### 3.2 Time-Series Analytics (P0)
**Research first:**
1. Examine event log schema in `reference_event_log.py`
2. Check existing aggregation capabilities
3. Look for time-based indexing

**Key features:**
- Windowed aggregations
- Trend detection
- Anomaly detection
- Forecasting

**Implementation approach:**
1. Time-series extraction from events
2. Pandas integration for analysis
3. Caching layer for performance
4. Real-time streaming analytics

### 3.3 Agent Capability Evolution (P1)
**Research first:**
1. How compositions affect running agents
2. Session continuity mechanisms
3. MCP tool exposure dynamics

**Design questions:**
- Hot-swap vs restart for capability changes?
- Permission escalation controls?
- Learning from performance metrics?
- Gradual vs sudden evolution?

### 3.4 Resource Management (P1)
**Research first:**
1. Current capability enforcement points
2. Resource usage tracking possibilities
3. Integration with system metrics

**Resource types:**
- Spawn limits (depth, count, rate)
- State operations (entities, relationships)
- Message volume (pub/sub rates)
- Computation time (per request)

## Phase 4: Planning Mode Discussion Topics

### 4.1 Architecture Decisions
1. **Query Language Choice**
   - Full Cypher compatibility vs subset?
   - Custom DSL vs standard?
   - Performance vs expressiveness?

2. **Evolution Strategy**
   - Learned vs prescribed evolution?
   - Capability dependencies?
   - Rollback mechanisms?

3. **Resource Model**
   - Hard limits vs soft quotas?
   - Per-capability vs per-agent?
   - Hierarchical inheritance?

### 4.2 Implementation Strategy
1. **Incremental Delivery**
   - Which P0 item first?
   - How to maintain compatibility?
   - Feature flags approach?

2. **Testing Strategy**
   - Graph query correctness
   - Performance benchmarks
   - Evolution scenarios
   - Resource exhaustion

3. **Documentation Needs**
   - Query language guide
   - Evolution patterns
   - Resource planning

### 4.3 Integration Considerations
1. **Claude Code Tools**
   - New tools for query language?
   - Evolution management tools?
   - Resource monitoring?

2. **Backward Compatibility**
   - Existing event handlers
   - Current client code
   - Migration paths

## Phase 5: Quick Wins to Start

### 5.1 Low-Hanging Fruit
1. **Event Pattern Matching**
   ```python
   @event_handler("event:match_pattern")
   async def match_event_pattern(data):
       pattern = data["pattern"]  # regex or glob
       time_range = data.get("time_range", "1h")
       return await event_log.match_pattern(pattern, time_range)
   ```

2. **Basic Graph Queries**
   ```python
   @event_handler("state:graph:query_simple")
   async def simple_graph_query(data):
       # Start with simple pattern matching
       entity_type = data["entity_type"]
       relationship_pattern = data["relationship"]
       return await graph.match_pattern(entity_type, relationship_pattern)
   ```

3. **Resource Usage Tracking**
   ```python
   @event_handler("resource:track_usage")
   async def track_resource_usage(data):
       agent_id = data["agent_id"]
       return {
           "spawned_agents": await count_spawned(agent_id),
           "state_operations": await count_state_ops(agent_id),
           "messages_sent": await count_messages(agent_id)
       }
   ```

## Phase 6: Success Metrics

### 6.1 Technical Metrics
- Query performance: < 100ms for typical patterns
- Evolution success rate: > 80% beneficial
- Resource prediction accuracy: ± 20%
- Time-series query speed: < 1s for 24h window

### 6.2 User Experience Metrics
- Simpler agent network analysis
- Faster debugging with queries
- Predictable resource usage
- Self-improving agents

## Recommended Session Flow

1. **Start in Planning Mode**
   - Review this guide
   - Run initial research tasks
   - Discuss findings and implications

2. **Prioritize Based on Research**
   - Adjust priorities based on complexity discovered
   - Identify quick wins
   - Plan incremental approach

3. **Design First Enhancement**
   - Choose P0 item (likely query language)
   - Create detailed design
   - Identify integration points

4. **Exit Planning Mode**
   - Begin implementation
   - Start with quick wins
   - Build toward full enhancement

## Key Questions for Planning Discussion

1. **Query Language**: Should we implement a subset of Cypher or create a custom DSL optimized for KSI's patterns?

2. **Evolution Safety**: How do we ensure agents can't evolve beyond their intended boundaries?

3. **Resource Fairness**: How to allocate resources fairly across competing agents?

4. **Performance Impact**: Will these enhancements slow down the core event loop?

5. **Migration Strategy**: How do we roll out breaking changes gradually?

## Quick Wins with Kùzu Integration

### 1. Parallel Cypher Handler (Day 1)
```python
# ksi_daemon/core/kuzu_state.py
import kuzu
from ksi_daemon.event_system import event_handler

class KuzuStateManager:
    def __init__(self):
        self.db = kuzu.Database(str(config.kuzu_db_path))
        self.conn = kuzu.Connection(self.db)
        
@event_handler("state:cypher:query")
async def handle_cypher_query(data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Cypher query via Kùzu."""
    query = data.get("query")
    params = data.get("params", {})
    
    result = conn.execute(query, params)
    return {
        "columns": result.get_column_names(),
        "data": result.get_as_df().to_dict('records')
    }
```

### 2. Time-Series Event Aggregation (Day 1-2)
```python
@event_handler("event_log:aggregate")
async def handle_event_aggregation(data: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregate events with time windows."""
    window = data.get("window", "1h")  # 1h, 5m, 1d
    aggregation = data.get("aggregation", "count")  # count, rate, avg
    group_by = data.get("group_by", ["event_type"])
    
    # Leverage existing query infrastructure
    results = await event_log.aggregate_windowed(
        window=window,
        aggregation=aggregation,
        group_by=group_by
    )
    return results
```

### 3. Simple Capability Evolution (Day 2-3)
```python
@event_handler("agent:suggest_capabilities")
async def suggest_capability_evolution(data: Dict[str, Any]) -> Dict[str, Any]:
    """Suggest capability changes based on performance."""
    agent_id = data.get("agent_id")
    
    # Analyze agent's event patterns
    metrics = await analyze_agent_performance(agent_id)
    
    # Suggest capability additions/removals
    suggestions = {
        "add": [],
        "remove": [],
        "rationale": {}
    }
    
    if metrics["failed_spawn_attempts"] > 5:
        suggestions["add"].append("spawn_agents")
        suggestions["rationale"]["spawn_agents"] = "High spawn failure rate"
    
    return suggestions
```

## Migration Strategy: SQLite to Kùzu

### Phase 1: Shadow Mode (Week 1)
1. Install Kùzu alongside existing system
2. Create migration script to copy data
3. Run both systems in parallel
4. Compare query results for validation

### Phase 2: Gradual Cutover (Week 2)
1. New features use Kùzu only
2. High-performance queries move to Kùzu
3. Keep SQLite for backward compatibility
4. Monitor performance differences

### Phase 3: Full Migration (Week 3+)
1. Migrate remaining queries
2. Update all event handlers
3. Deprecate SQLite handlers
4. Archive SQLite data

### Migration Script Example
```python
# migrate_to_kuzu.py
async def migrate_entities():
    """Migrate entities from SQLite to Kùzu."""
    # Create schema in Kùzu
    conn.execute("""
        CREATE NODE TABLE Agent(
            id STRING PRIMARY KEY,
            type STRING,
            created_at DOUBLE,
            properties MAP(STRING, STRING)
        )
    """)
    
    # Copy data
    entities = await state_manager.query_entities()
    for entity in entities:
        conn.execute("""
            CREATE (:Agent {
                id: $id,
                type: $type,
                created_at: $created_at,
                properties: $properties
            })
        """, entity)
```

## Updated Key Questions for Planning Discussion

1. **Dual Database Strategy**: Should we maintain both SQLite and Kùzu long-term or plan for full migration?

2. **Cypher Dialect**: Should we support full Cypher or start with a subset that matches our use cases?

3. **Performance Benchmarks**: What metrics should we track during the migration to validate improvements?

4. **Capability Evolution**: Should evolution be automatic based on metrics or require human approval?

5. **API Compatibility**: How do we ensure existing tools and clients continue working during migration?

## Implementation Priority (Updated - 2025-07-06)

### Current Focus: Experimental Phase

**Immediate Experiments (Days)**:
- Document direct socket communication patterns
- Continue baseline performance experiments
- Create socket-based versions of remaining experiments
- Analyze system behavior under various loads

**Future Enhancements (Weeks Away)**:
- Set up Kùzu development environment
- Create basic Cypher query handler
- Implement simple event aggregation
- Build migration tools
- Add graph algorithms via Kùzu
- Enhance time-series analytics
- Implement capability evolution
- Add resource tracking
- Complete performance benchmarks

### Rationale for Prioritization Change

**Direct socket approach proven superior:**
- All KSI systems functional via direct communication
- EventClient has discovery timeout issues
- Better understanding of daemon capabilities
- Foundation for future client improvements

**Experimental data collection prioritized:**
- Establish reliable performance baselines
- Document communication patterns
- Understand scaling characteristics
- Gather data for informed enhancement decisions

## Appendix: Code Investigation Commands

```bash
# Find all graph-related code
rg -t py "traverse|graph|entity|relationship" ksi_daemon/

# Examine event handler patterns
rg "@event_handler" ksi_daemon/ -A 3

# Find composition resolution
rg "resolve|compile" ksi_daemon/composition/

# Look for resource tracking
rg "limit|quota|resource|budget" ksi_daemon/

# Check time-series related code
rg "time|timestamp|window|aggregate" ksi_daemon/core/

# Find rate limiting usage
rg "RateLimiter|rate_limit" ksi_daemon/

# Examine observation analytics
rg "frequency|pattern|aggregate" ksi_daemon/observation/
```

---

This planning guide provides a structured approach for the next session. The research findings strongly suggest adopting Kùzu as a parallel graph database to gain Cypher support while maintaining backward compatibility. Start with quick wins that demonstrate value, then gradually migrate based on performance validation.