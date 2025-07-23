# KSI Checkpoint/Restore System Analysis

## Overview

The KSI checkpoint/restore system provides resilience for development mode, preserving state across daemon restarts. This document analyzes the current implementation and identifies opportunities for integration with the new context reference system.

## Current Architecture

### 1. Core Components

#### Checkpoint Module (`ksi_daemon/core/checkpoint.py`)
- **Purpose**: Preserves daemon state during restarts
- **Storage**: SQLite database at `var/db/checkpoint.db`
- **Scope**: Development mode only (can be disabled via `KSI_CHECKPOINT_DISABLED`)

#### Key Features:
- Relational schema with proper foreign keys
- Atomic checkpoint creation on shutdown
- Automatic restoration on startup
- Support for multiple checkpoint snapshots (keeps last 5)

### 2. Data Currently Checkpointed

#### Completion Service State
- **Active completions**: In-progress completion requests
- **Session queues**: Queued requests per session
- **Request metadata**: Status, timestamps, errors

#### Agent Service State
- **Agent profiles**: Full agent configuration
- **Agent identities**: Identity data for each agent
- **Agent metadata**: Type, purpose, permissions

#### Observation Service State
- **Subscription data**: Active observation subscriptions
- **Subscription metadata**: Types, filters, handlers

### 3. Checkpoint Lifecycle

#### Creation Flow:
1. **Shutdown signal** → High-priority shutdown handler
2. **State collection** → `checkpoint:collect` event to all services
3. **Persistence** → Save to SQLite with relationships
4. **Acknowledgment** → Signal daemon it's safe to exit

#### Restoration Flow:
1. **System startup** → Initialize checkpoint DB
2. **System ready** → All services initialized
3. **Load checkpoint** → Retrieve latest active checkpoint
4. **State restoration** → Re-emit queued requests, restore subscriptions

### 4. Recovery Mechanisms

#### Retry Manager (`ksi_daemon/completion/retry_manager.py`)
- **Purpose**: Handles transient failures with exponential backoff
- **Policies**: Configurable retry attempts, delays, error types
- **Integration**: Works with checkpoint restore for daemon restarts

#### Failure Patterns Handled:
- Daemon restarts (SIGKILL, controlled shutdown)
- Network errors and timeouts
- Provider failures (rate limits, API errors)
- Partial request processing

## Integration with Context Reference System

### 1. Current Limitations

#### Context Loss on Restart
- Event contexts are not checkpointed
- Parent-child relationships lost
- Correlation chains broken
- Session context not preserved

#### Recovery Challenges
- Cannot reconstruct event genealogy
- Lost introspection capabilities
- Broken monitoring chains
- Incomplete audit trails

### 2. Integration Opportunities

#### Context Checkpointing
```python
# Add to checkpoint tables
CREATE TABLE checkpoint_contexts (
    id INTEGER PRIMARY KEY,
    checkpoint_id INTEGER NOT NULL,
    context_ref TEXT NOT NULL,
    context_data TEXT NOT NULL,  -- Full context JSON
    FOREIGN KEY (checkpoint_id) REFERENCES checkpoints(id),
    UNIQUE(checkpoint_id, context_ref)
);
```

#### Enhanced Agent Checkpointing
```python
# Store agent's current context reference
ALTER TABLE checkpoint_agents ADD COLUMN current_context_ref TEXT;
ALTER TABLE checkpoint_agents ADD COLUMN parent_context_ref TEXT;
```

#### Session Context Preservation
```python
# Store session's context chain
CREATE TABLE checkpoint_session_contexts (
    id INTEGER PRIMARY KEY,
    checkpoint_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    context_refs TEXT NOT NULL,  -- JSON array of refs
    FOREIGN KEY (checkpoint_id) REFERENCES checkpoints(id)
);
```

### 3. Recovery Enhancements

#### Context Chain Reconstruction
1. **Checkpoint includes context refs** → Store with each entity
2. **Context manager integration** → Persist hot contexts on checkpoint
3. **Restoration rebuilds chains** → Reconstruct parent-child relationships
4. **Event genealogy preserved** → Full introspection after restart

#### Enhanced Recovery Flow
```python
async def enhanced_restore_state(checkpoint_data):
    # 1. Restore contexts first
    await restore_contexts(checkpoint_data["contexts"])
    
    # 2. Restore agents with context
    for agent in checkpoint_data["agents"]:
        context = await context_manager.get_context(agent["context_ref"])
        await restore_agent_with_context(agent, context)
    
    # 3. Restore sessions with context chain
    for session in checkpoint_data["sessions"]:
        contexts = await restore_session_contexts(session["context_refs"])
        await restore_session_with_contexts(session, contexts)
    
    # 4. Re-emit queued requests with proper context
    for request in checkpoint_data["queued_requests"]:
        with restored_context(request["context_ref"]):
            await emit_event("completion:async", request["data"])
```

## Proposed Enhancements

### 1. Continuous Checkpointing
- **Current**: Only on shutdown
- **Proposed**: Periodic snapshots for crash recovery
- **Benefit**: Survive unexpected terminations

### 2. Selective Restoration
- **Current**: All or nothing
- **Proposed**: Restore specific agents/sessions
- **Benefit**: Surgical recovery, debugging

### 3. Cross-Restart Correlation
- **Current**: Correlations break on restart
- **Proposed**: Preserve correlation chains
- **Benefit**: Complete audit trails

### 4. Production Mode Support
- **Current**: Dev mode only
- **Proposed**: Configurable for production
- **Benefit**: High availability, zero downtime

## Implementation Plan

### Phase 1: Context Integration (Priority)
1. Add context tables to checkpoint schema
2. Extend `checkpoint:collect` to include contexts
3. Update restoration to rebuild context chains
4. Test with introspection queries

### Phase 2: Enhanced Recovery
1. Implement continuous checkpointing
2. Add selective restoration APIs
3. Preserve correlation chains
4. Add recovery metrics

### Phase 3: Production Readiness
1. Make checkpoint system configurable
2. Add distributed checkpoint support
3. Implement checkpoint replication
4. Add health checks and monitoring

## Benefits

### Developer Experience
- **No lost work** during daemon restarts
- **Full debugging** capabilities preserved
- **Seamless restarts** with state continuity

### System Reliability
- **Crash recovery** with minimal data loss
- **Audit trails** survive restarts
- **Monitoring continuity** across restarts

### Operational Excellence
- **Zero-downtime updates** possible
- **State migration** between versions
- **Debugging production** issues

## Conclusion

The current checkpoint system provides a solid foundation for development resilience. By integrating with the new context reference system, we can achieve:

1. **Complete state preservation** including event genealogy
2. **Enhanced recovery** with context-aware restoration
3. **Production-grade resilience** for critical workloads

The proposed enhancements maintain backward compatibility while significantly improving the system's ability to recover from failures with full context preservation.