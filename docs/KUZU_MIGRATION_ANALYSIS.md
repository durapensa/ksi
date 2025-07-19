# Kùzu Graph Database Migration Analysis

## Executive Summary

This document analyzes the potential migration from SQLite to [Kùzu](https://kuzudb.com/), an embedded graph database. While the immediate performance issue has been resolved with JSON aggregation in SQLite, Kùzu remains a compelling future option as KSI's graph operations become more sophisticated.

## Current State Architecture

### SQLite EAV Pattern
- **Entities table**: Core entity metadata (id, type, timestamps)
- **Properties table**: EAV storage for flexible attributes
- **Relationships table**: Graph edges between entities

### Performance Issue (Resolved)
- **Problem**: N+1 query pattern (1 query + 100 queries for 100 entities)
- **Solution**: JSON aggregation functions (single query with json_group_object/array)
- **Result**: 100x-200x performance improvement

## Kùzu Overview

Kùzu is an embedded graph database that:
- Runs in-process like SQLite (no server required)
- Uses Cypher query language (industry standard)
- Provides ACID guarantees
- Optimizes for graph workloads
- Offers Python bindings

## Migration Analysis

### When to Consider Migration

#### Immediate Triggers
- Graph traversals become primary workload (>50% of queries)
- Need for complex path queries (multi-hop relationships)
- Graph algorithms required (centrality, clustering, shortest path)
- Performance bottlenecks in relationship-heavy queries

#### Future Indicators
- Agent interaction patterns require graph analysis
- Orchestration dependency graphs need optimization
- State relationship queries dominate system load
- Need for real-time graph pattern matching

### Architecture Comparison

#### Current SQLite Approach
```sql
-- Find all agents connected to a specific agent (2-hop)
WITH RECURSIVE agent_network AS (
    SELECT entity_id, 0 as depth
    FROM entities WHERE entity_id = ?
    UNION ALL
    SELECT r.to_id, a.depth + 1
    FROM agent_network a
    JOIN relationships r ON a.entity_id = r.from_id
    WHERE a.depth < 2
)
SELECT DISTINCT entity_id FROM agent_network;
```

#### Kùzu Approach
```cypher
MATCH (start:Entity {entity_id: $agent_id})-[*1..2]->(connected:Entity)
WHERE connected.type = 'agent'
RETURN DISTINCT connected
```

### Migration Strategy

#### Phase 1: Parallel Implementation
1. Create `ksi_daemon/core/graph_state_kuzu.py`
2. Implement same StateManager interface
3. Add feature flag for backend selection
4. Run performance benchmarks

#### Phase 2: Data Migration
```python
# Migration script example
async def migrate_to_kuzu():
    # Create Kùzu schema
    kuzu_conn.execute("""
        CREATE NODE TABLE Entity(
            entity_id STRING PRIMARY KEY,
            type STRING,
            created_at DOUBLE,
            updated_at DOUBLE
        )
    """)
    
    kuzu_conn.execute("""
        CREATE NODE TABLE Property(
            id INT64 PRIMARY KEY,
            key STRING,
            value STRING,
            type STRING
        )
    """)
    
    kuzu_conn.execute("""
        CREATE REL TABLE HAS_PROPERTY(
            FROM Entity TO Property,
            created_at DOUBLE
        )
    """)
    
    kuzu_conn.execute("""
        CREATE REL TABLE RELATES_TO(
            FROM Entity TO Entity,
            relation_type STRING,
            metadata STRING,
            created_at DOUBLE
        )
    """)
    
    # Migrate data
    # ... (bulk copy operations)
```

#### Phase 3: Gradual Rollout
1. Enable for read-only operations first
2. Test with non-critical workflows
3. Monitor performance and stability
4. Gradually increase usage
5. Full cutover when confident

### Implementation Design

```python
class KuzuStateManager:
    """Kùzu-based state manager implementation."""
    
    def __init__(self, db_path: Path):
        self.db = kuzu.Database(str(db_path))
        self.conn = kuzu.Connection(self.db)
        
    async def create_entity(self, entity_id: str, entity_type: str, 
                           properties: Dict[str, Any]) -> bool:
        """Create entity with properties in single transaction."""
        # Create entity node
        self.conn.execute(
            "CREATE (e:Entity {entity_id: $id, type: $type, created_at: $now})",
            {"id": entity_id, "type": entity_type, "now": time.time()}
        )
        
        # Add properties as separate nodes with relationships
        for key, value in properties.items():
            self.conn.execute("""
                MATCH (e:Entity {entity_id: $id})
                CREATE (p:Property {key: $key, value: $value, type: $type})
                CREATE (e)-[:HAS_PROPERTY]->(p)
            """, {
                "id": entity_id, 
                "key": key, 
                "value": str(value),
                "type": type(value).__name__
            })
            
    async def query_entities(self, entity_type: Optional[str] = None,
                           where: Optional[Dict[str, Any]] = None,
                           limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Query entities using Cypher."""
        cypher = "MATCH (e:Entity)"
        params = {}
        
        if entity_type:
            cypher += " WHERE e.type = $type"
            params["type"] = entity_type
            
        if where:
            # Property filters
            for key, value in where.items():
                cypher += f"""
                    MATCH (e)-[:HAS_PROPERTY]->(p:Property)
                    WHERE p.key = $key_{key} AND p.value = $val_{key}
                """
                params[f"key_{key}"] = key
                params[f"val_{key}"] = str(value)
                
        cypher += " RETURN e"
        
        if limit:
            cypher += f" LIMIT {limit}"
            
        result = self.conn.execute(cypher, params)
        # ... process results
```

### Performance Expectations

#### Graph Operations
- **2-hop traversals**: 10-50x faster than recursive CTEs
- **Pattern matching**: 5-20x faster for complex patterns
- **Shortest path**: 100x faster with built-in algorithms
- **Aggregations**: Similar performance to optimized SQLite

#### Trade-offs
- **Simple queries**: SQLite may be slightly faster
- **Storage overhead**: Kùzu uses more disk space (~1.5-2x)
- **Memory usage**: Higher baseline memory (50-100MB)
- **Learning curve**: Cypher syntax differs from SQL

### Risk Analysis

#### Low Risk
- Embedded architecture (no operational complexity)
- Fallback to SQLite is straightforward
- Clear performance benefits for graph workloads

#### Medium Risk
- Cypher learning curve for team
- Limited ecosystem compared to SQLite
- Newer technology (less battle-tested)

#### Mitigation
- Implement behind interface (easy rollback)
- Extensive testing before production
- Keep SQLite as fallback option

## Recommendation

### Short Term (Now)
Continue with optimized SQLite implementation. The JSON aggregation fix provides sufficient performance for current needs.

### Medium Term (3-6 months)
- Monitor graph query patterns
- Prototype Kùzu implementation
- Benchmark real workloads
- Evaluate developer experience

### Long Term (6+ months)
If graph operations become dominant (>50% of queries), migrate to Kùzu for:
- Native graph performance
- Cleaner query syntax
- Built-in graph algorithms
- Future-proof architecture

## Conclusion

While Kùzu offers compelling advantages for graph workloads, the immediate performance crisis has been resolved with JSON aggregation. Migration should be considered when:

1. Graph traversals become performance bottlenecks
2. Complex relationship queries are needed frequently
3. Graph algorithms would provide business value
4. The team is ready for Cypher adoption

The embedded nature of Kùzu makes it a low-risk option to evaluate in parallel with the current SQLite implementation.