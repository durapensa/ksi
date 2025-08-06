# Crash Recovery Integration Design

## Overview

This document outlines the integration of KSI's crash recovery system, combining the existing checkpoint/restore mechanism with the new Pythonic context reference system to provide comprehensive state recovery after daemon crashes.

## Current State Analysis

### Existing Components

1. **Checkpoint System** (`ksi_daemon/core/checkpoint.py`)
   - Captures state on daemon shutdown
   - Restores on startup
   - Tracks: completion requests, session state, agent data, observation subscriptions
   - Uses SQLite with proper relational schema

2. **Context Manager** (NEW - `ksi_daemon/core/context_manager.py`)
   - Hot storage: In-memory for 24 hours
   - Cold storage: SQLite for 7-30 days
   - Stores event contexts with parent/child relationships
   - Reference-based to reduce event size by 70%

3. **State Manager** (`ksi_daemon/core/state.py`)
   - Graph database for entities and relationships
   - Persistent SQLite storage
   - Tracks agents, orchestrations, subscriptions

4. **Event Log** (`ksi_daemon/core/reference_event_log.py`)
   - JSONL files for audit trail
   - SQLite index for metadata queries
   - Stores event references, not full contexts

## Integration Strategy

### Phase 1: Context Checkpointing

**Goal**: Preserve event contexts and genealogy across restarts

**Implementation**:
```python
# In checkpoint.py, add context checkpointing
async def _checkpoint_contexts(self):
    """Checkpoint in-flight contexts from hot storage."""
    cm = get_context_manager()
    
    # Get active contexts (last 1 hour for efficiency)
    active_contexts = await cm.get_recent_contexts(hours=1)
    
    # Store in checkpoint DB with compression
    await self.conn.execute("""
        INSERT OR REPLACE INTO checkpoint_contexts 
        (context_id, event_id, correlation_id, parent_id, data)
        VALUES (?, ?, ?, ?, ?)
    """, [(c.id, c.event_id, c.correlation_id, c.parent_id, 
           compress(json.dumps(c.data))) for c in active_contexts])
```

**Restoration**:
```python
async def _restore_contexts(self):
    """Restore contexts to maintain event chains."""
    rows = await self.conn.execute(
        "SELECT * FROM checkpoint_contexts ORDER BY created_at"
    )
    
    cm = get_context_manager()
    for row in rows:
        # Restore to hot storage for immediate access
        await cm.restore_context(
            context_id=row['context_id'],
            data=json.loads(decompress(row['data']))
        )
```

### Phase 2: Agent Context Continuity

**Goal**: Restore agent conversation contexts with Claude CLI

**Implementation**:
```python
# Enhanced agent checkpointing
async def _checkpoint_agents(self):
    """Checkpoint agents with their context chains."""
    agents = await state_manager.query_entities(type="agent")
    
    for agent in agents:
        # Get agent's context chain
        context_chain = await cm.get_context_chain(
            agent_id=agent['id'], 
            depth=10  # Last 10 contexts
        )
        
        await self.conn.execute("""
            INSERT OR REPLACE INTO checkpoint_agent_contexts
            (agent_id, context_chain, sandbox_uuid, last_event_id)
            VALUES (?, ?, ?, ?)
        """, (agent['id'], json.dumps(context_chain), 
              agent['sandbox_uuid'], context_chain[-1]['event_id']))
```

### Phase 3: Orchestration State Recovery

**Goal**: Resume interrupted orchestrations with full context

**Implementation**:
```python
async def _restore_orchestrations(self):
    """Restore orchestration state with event routing."""
    rows = await self.conn.execute(
        "SELECT * FROM checkpoint_orchestrations"
    )
    
    for row in rows:
        # Restore orchestration entity
        await state_manager.create_entity(
            id=row['orchestration_id'],
            type='orchestration',
            properties=json.loads(row['properties'])
        )
        
        # Restore subscription relationships
        await hierarchical_router.restore_subscriptions(
            orchestration_id=row['orchestration_id'],
            subscriptions=json.loads(row['subscriptions'])
        )
        
        # Re-emit pending events
        pending_events = json.loads(row['pending_events'])
        for event in pending_events:
            await router.emit(event['name'], event['data'])
```

### Phase 4: Continuous Checkpointing

**Goal**: Periodic snapshots beyond shutdown

**Implementation**:
```python
class ContinuousCheckpointer:
    """Background task for periodic checkpointing."""
    
    def __init__(self, interval_seconds=300):  # 5 minutes
        self.interval = interval_seconds
        self.task = None
        
    async def start(self):
        """Start continuous checkpointing."""
        self.task = asyncio.create_task(self._checkpoint_loop())
        
    async def _checkpoint_loop(self):
        """Periodic checkpoint with minimal overhead."""
        while True:
            try:
                await asyncio.sleep(self.interval)
                
                # Incremental checkpoint - only changed data
                await self._incremental_checkpoint()
                
            except asyncio.CancelledError:
                break
                
    async def _incremental_checkpoint(self):
        """Checkpoint only changed data since last checkpoint."""
        # Track changes via event timestamps
        last_checkpoint = await self._get_last_checkpoint_time()
        
        # Checkpoint new/modified contexts
        new_contexts = await cm.get_contexts_since(last_checkpoint)
        await self._checkpoint_contexts(new_contexts)
        
        # Checkpoint agent state changes
        changed_agents = await state_manager.get_entities_modified_since(
            last_checkpoint, type="agent"
        )
        await self._checkpoint_agents(changed_agents)
```

## Recovery Sequence

### Startup Flow with Recovery

```
1. Daemon starts
2. Initialize core components (state_manager, context_manager, etc.)
3. Register in SystemRegistry
4. Check for checkpoint
5. If checkpoint exists:
   a. Restore contexts first (establish event chains)
   b. Restore agents with their context references
   c. Restore sessions and link to contexts
   d. Restore orchestrations and subscriptions
   e. Re-emit queued requests with proper context
6. Emit system:startup
7. Emit system:context 
8. Continue normal operation
```

### Data Recovery Priority

1. **Critical**: State entities (agents, orchestrations)
2. **Important**: Active contexts and chains
3. **Normal**: Pending requests and sessions
4. **Low**: Historical contexts (can query from cold storage)

## Configuration

```python
# In ksi_common/config.py
class CheckpointConfig(BaseSettings):
    """Checkpoint and recovery configuration."""
    
    # Checkpoint behavior
    checkpoint_on_shutdown: bool = True
    continuous_checkpoint: bool = False
    checkpoint_interval_seconds: int = 300
    
    # Recovery behavior  
    restore_on_startup: bool = True
    restore_context_hours: int = 24  # How far back to restore contexts
    restore_max_contexts: int = 10000  # Limit for memory
    
    # Data retention
    checkpoint_retention_days: int = 7
    context_checkpoint_compression: bool = True
```

## Benefits

1. **Complete State Recovery**: All components restored with relationships intact
2. **Event Chain Preservation**: Full debugging capabilities after restart
3. **Zero Data Loss**: Continuous checkpointing prevents loss
4. **Seamless Agent Recovery**: Conversations continue without interruption
5. **Orchestration Resumption**: Complex workflows survive crashes

## Testing Strategy

### Unit Tests
- Test each checkpoint/restore component in isolation
- Verify data compression/decompression
- Test incremental checkpointing logic

### Integration Tests
- Simulate daemon crash during various operations
- Verify complete state restoration
- Test context chain integrity after recovery
- Validate agent conversation continuity

### Performance Tests
- Measure checkpoint overhead
- Test recovery time with large datasets
- Verify memory usage during restoration

## Migration Path

1. **Phase 1**: Add context checkpointing (no breaking changes)
2. **Phase 2**: Enable continuous checkpointing in dev
3. **Phase 3**: Production rollout with monitoring
4. **Phase 4**: Remove legacy recovery code

## Monitoring

- Checkpoint duration and size metrics
- Recovery success rate
- Context chain integrity checks
- Agent session continuity verification

---

*This design ensures KSI can recover from any crash with full state preservation, maintaining event genealogy and enabling complete system introspection.*