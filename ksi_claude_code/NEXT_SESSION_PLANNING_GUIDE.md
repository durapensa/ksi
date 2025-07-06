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
```

---

This planning guide provides a structured approach for the next session. Start with the research tasks, then enter planning mode to discuss findings and prioritize implementation based on what you discover in the code.