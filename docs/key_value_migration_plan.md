# Key-Value to Relational Migration Plan

**Date:** 2025-01-05  
**Status:** Analysis and Design

## Overview

This document outlines the migration of remaining key-value patterns to KSI's relational state system, completing the transition to a fully relational architecture.

## Current Key-Value Patterns

### 1. Checkpoint Data

**Current Implementation:**
- Location: `ksi_daemon/core/checkpoint.py`
- Storage: SQLite table with JSON blob
```sql
CREATE TABLE checkpoints (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    checkpoint_data TEXT  -- JSON blob
)
```

**Data Structure:**
```json
{
    "timestamp": "2025-01-05T10:00:00Z",
    "session_queues": {
        "session_123": {
            "items": [...],
            "is_active": true
        }
    },
    "active_completions": {
        "req_456": {
            "session_id": "session_123",
            "status": "processing",
            "data": {...}
        }
    }
}
```

### 2. MCP Session Cache

**Current Implementation:**
- Location: `ksi_daemon/mcp/dynamic_server.py`
- Storage: SQLite table with JSON blob
```sql
CREATE TABLE mcp_sessions (
    session_key TEXT PRIMARY KEY,
    session_data TEXT,      -- JSON blob
    last_seen TIMESTAMP
)
```

**Data Structure:**
```json
{
    "agent_id": "agent_123",
    "tools": ["Read", "Write", ...],
    "thin_handshake": true,
    "created_at": "2025-01-05T10:00:00Z"
}
```

### 3. Agent Metadata

**Current Implementation:**
- Location: `ksi_daemon/agent/agent_service.py`
- Storage: Properties in state system (already relational)
- Pattern: Some complex metadata stored as JSON strings in properties

## Proposed Relational Schema

### 1. Checkpoint System

#### Entities
```yaml
checkpoint:
  properties:
    - created_at: timestamp
    - reason: string (manual/shutdown/dev)
    - restored_at: timestamp (optional)
    - status: string (active/restored/archived)

checkpoint_request:
  properties:
    - checkpoint_id: reference
    - request_id: string
    - session_id: string
    - status: string
    - request_data: text (JSON for now, structured later)
    - queued_at: timestamp
    - started_at: timestamp (optional)

checkpoint_queue:
  properties:
    - checkpoint_id: reference
    - session_id: string
    - queue_depth: integer
    - is_active: boolean
```

#### Relationships
- checkpoint → checkpoint_request (one-to-many)
- checkpoint → checkpoint_queue (one-to-many)

### 2. MCP Session System

#### Entities
```yaml
mcp_session:
  properties:
    - session_key: string (unique)
    - agent_id: string
    - created_at: timestamp
    - last_seen: timestamp
    - thin_handshake: boolean
    - is_active: boolean

mcp_session_tool:
  properties:
    - session_id: reference
    - tool_name: string
    - added_at: timestamp
```

#### Relationships
- mcp_session → agent (many-to-one)
- mcp_session → mcp_session_tool (one-to-many)

### 3. Agent Metadata (Enhancement)

Currently agent metadata is already stored in the relational system as properties. No migration needed, but we should document best practices for complex metadata.

## Migration Strategy

### Phase 1: Schema Creation (4 hours)

1. **Create Entity Definitions**
```python
# state:entity:define events
checkpoint_entity = {
    "type": "checkpoint",
    "properties": {
        "created_at": "timestamp",
        "reason": "string",
        "restored_at": "timestamp",
        "status": "string"
    }
}

checkpoint_request_entity = {
    "type": "checkpoint_request",
    "properties": {
        "checkpoint_id": "reference",
        "request_id": "string",
        "session_id": "string",
        "status": "string",
        "request_data": "text",
        "queued_at": "timestamp",
        "started_at": "timestamp"
    }
}
```

2. **Create Migration Events**
```python
@event_handler("migration:checkpoint:schema")
async def create_checkpoint_schema(data):
    # Define entities
    # Create indexes
    # Set up relationships
```

### Phase 2: Dual Write Implementation (6 hours)

1. **Modify checkpoint.py**
   - Keep existing JSON storage
   - Add relational storage in parallel
   - Write to both systems

2. **Modify mcp/dynamic_server.py**
   - Keep existing session cache
   - Add relational storage
   - Maintain consistency

### Phase 3: Read Migration (4 hours)

1. **Update Read Paths**
   - Checkpoint restore from relational
   - MCP session lookup from relational
   - Fallback to JSON if needed

2. **Verification**
   - Compare outputs
   - Performance testing
   - Data integrity checks

### Phase 4: Cleanup (2 hours)

1. **Remove JSON Writers**
   - Delete old save functions
   - Remove JSON serialization
   - Clean up imports

2. **Archive Old Data**
   - Export existing JSON data
   - Verify all migrated
   - Drop old tables

## Implementation Details

### Checkpoint Migration

```python
# OLD: JSON blob
async def save_checkpoint(checkpoint_data: Dict[str, Any]):
    await db.execute(
        "INSERT INTO checkpoints (timestamp, checkpoint_data) VALUES (?, ?)",
        (timestamp, json.dumps(checkpoint_data))
    )

# NEW: Relational
async def save_checkpoint_relational(checkpoint_data: Dict[str, Any]):
    # Create checkpoint entity
    checkpoint = await emit_event("state:entity:create", {
        "type": "checkpoint",
        "properties": {
            "created_at": checkpoint_data["timestamp"],
            "reason": checkpoint_data.get("reason", "manual"),
            "status": "active"
        }
    })
    
    # Create request entities
    for req_id, req_data in checkpoint_data["active_completions"].items():
        await emit_event("state:entity:create", {
            "type": "checkpoint_request",
            "properties": {
                "checkpoint_id": checkpoint["id"],
                "request_id": req_id,
                "session_id": req_data["session_id"],
                "status": req_data["status"],
                "request_data": json.dumps(req_data["data"]),
                "queued_at": req_data.get("queued_at")
            }
        })
```

### MCP Session Migration

```python
# OLD: JSON blob
session_data = {
    "agent_id": agent_id,
    "tools": tools,
    "thin_handshake": thin
}
await db.execute(
    "INSERT INTO mcp_sessions VALUES (?, ?, ?)",
    (key, json.dumps(session_data), now)
)

# NEW: Relational
session = await emit_event("state:entity:create", {
    "type": "mcp_session",
    "properties": {
        "session_key": key,
        "agent_id": agent_id,
        "created_at": now,
        "last_seen": now,
        "thin_handshake": thin,
        "is_active": True
    }
})

# Create tool relationships
for tool in tools:
    await emit_event("state:entity:create", {
        "type": "mcp_session_tool",
        "properties": {
            "session_id": session["id"],
            "tool_name": tool,
            "added_at": now
        }
    })
```

## Benefits

1. **Queryability**
   - Find all checkpoints by reason
   - Query sessions by agent
   - Analyze tool usage patterns

2. **Consistency**
   - Foreign key relationships
   - Data validation
   - No JSON parsing errors

3. **Performance**
   - Indexed lookups
   - Selective field queries
   - Better caching

4. **Maintainability**
   - Schema evolution
   - Clear data model
   - Type safety

## Risks and Mitigation

1. **Data Loss Risk**
   - Mitigation: Dual write period
   - Verification: Checksums and counts

2. **Performance Risk**
   - Mitigation: Proper indexes
   - Testing: Load tests

3. **Compatibility Risk**
   - Mitigation: Gradual migration
   - Fallback: Read from JSON if needed

## Success Metrics

1. **Zero Data Loss**
   - All checkpoints migrated
   - All sessions preserved
   - Verified by counts

2. **Performance Maintained**
   - Checkpoint save < 100ms
   - Session lookup < 10ms
   - No degradation

3. **Code Simplification**
   - Remove JSON serialization
   - Cleaner data access
   - Better error handling

## Timeline

- Day 1: Schema design and entity creation
- Day 2: Dual write implementation
- Day 3: Read path migration
- Day 4: Testing and verification
- Day 5: Cleanup and documentation

## Conclusion

This migration completes KSI's transition to a fully relational architecture, eliminating the last remnants of key-value patterns and providing a consistent, queryable data model throughout the system.