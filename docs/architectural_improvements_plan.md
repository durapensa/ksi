# KSI Architectural Improvements Plan

**Date:** 2025-01-05  
**Status:** Analysis and Implementation Planning

## Executive Summary

Following the successful transformation of the observation system to ephemeral infrastructure, this document outlines the next phase of architectural improvements for KSI. These improvements focus on modularity, consistency, and reliability.

## Priority 1: Completion System Modularity

### Current State
The completion service (`completion_service.py`) handles multiple concerns:
- Queue management (per-session ordering)
- Retry logic (exponential backoff)
- Provider abstraction (LiteLLM, Claude CLI)
- Checkpoint integration
- Priority queuing
- Token usage tracking

This creates a ~1200 line module that's difficult to test and modify.

### Proposed Architecture

```
completion/
├── completion_service.py      # Orchestrator (thin layer)
├── queue_manager.py          # Queue operations only
├── retry_manager.py          # Already exists, needs cleanup
├── provider_manager.py       # Provider selection/failover
├── session_manager.py        # Session continuity logic
└── token_tracker.py          # Usage analytics
```

### Implementation Plan

#### Phase 1: Extract Queue Management (4 hours)
```python
# queue_manager.py
class CompletionQueueManager:
    """Manages per-session completion queues."""
    
    def __init__(self):
        self._session_queues: Dict[str, asyncio.Queue] = {}
        self._processing_tasks: Dict[str, asyncio.Task] = {}
    
    async def enqueue(self, session_id: str, request: CompletionRequest) -> str:
        """Add request to session queue."""
        
    async def get_queue_status(self, session_id: str) -> Dict[str, Any]:
        """Get queue depth and processing status."""
        
    async def clear_session(self, session_id: str) -> None:
        """Clear all queued requests for session."""
```

#### Phase 2: Refactor Provider Management (3 hours)
```python
# provider_manager.py
class ProviderManager:
    """Manages completion providers with failover."""
    
    async def select_provider(self, model: str) -> Provider:
        """Select best provider for model."""
        
    async def handle_provider_failure(self, provider: str, error: Exception):
        """Track failures and manage circuit breakers."""
```

#### Phase 3: Simplify Main Service (2 hours)
- Remove extracted logic
- Focus on orchestration only
- Clear interfaces between components

## Priority 2: Key-Value to Relational Migration

### Patterns to Migrate

1. **Checkpoint Data**
   ```python
   # Current: JSON blob
   checkpoint_data = {"requests": [...], "metadata": {...}}
   
   # Target: Relational entities
   # Entity: checkpoint
   # Properties: created_at, restored_at, status
   # Relationships: checkpoint -> checkpoint_request
   ```

2. **MCP Session Cache**
   ```python
   # Current: Key-value style
   cache[session_key] = session_data
   
   # Target: Relational
   # Entity: mcp_session
   # Properties: session_key, tool_data, created_at, expires_at
   # Relationships: mcp_session -> agent
   ```

3. **Agent Metadata**
   ```python
   # Current: JSON in properties
   properties = {"metadata": json.dumps({...})}
   
   # Target: Proper properties
   # Each metadata field as individual property
   ```

### Migration Strategy

1. **Create New Schema** (2 hours)
   - Design entity types and relationships
   - Write migration events

2. **Dual Write Period** (4 hours)
   - Write to both old and new formats
   - Verify data consistency

3. **Switch Readers** (2 hours)
   - Update read paths to use relational state
   - Remove old read code

4. **Remove Old Writers** (1 hour)
   - Stop writing to key-value format
   - Clean up old code

## Priority 3: Error Propagation in Event Router

### Current Problem
```python
# Event router swallows exceptions
try:
    result = await handler(data, context)
except Exception as e:
    errors.append({"handler": handler.__name__, "error": str(e)})
```

This hides programming errors and makes debugging difficult.

### Proposed Solution

```python
# Distinguish between expected and unexpected errors
try:
    result = await handler(data, context)
except OperationalError as e:
    # Expected errors (external failures, validation, etc)
    errors.append({"handler": handler.__name__, "error": str(e)})
except Exception as e:
    # Programming errors should propagate
    logger.error(f"Handler {handler.__name__} crashed", exc_info=True)
    raise  # Let it crash - supervisor will restart
```

### Implementation
1. Define `OperationalError` base class
2. Update handlers to use specific exceptions
3. Modify event router error handling
4. Add tests for both paths

## Priority 4: Async SQLite Standardization

### Current State
- Event log uses WAL mode and async writes
- Other SQLite usage may not be consistent

### Required Changes

1. **Audit All SQLite Usage** (2 hours)
   ```python
   # Find all sqlite3 imports and connections
   # Verify WAL mode and async patterns
   ```

2. **Create Standard Async DB Helper** (3 hours)
   ```python
   # ksi_common/async_db.py
   class AsyncSQLiteDB:
       """Standard async SQLite with WAL mode."""
       
       async def __aenter__(self):
           # Ensure WAL mode
           # Return async connection
   ```

3. **Update All Modules** (4 hours)
   - Replace direct sqlite3 usage
   - Use standard helper
   - Test async behavior

## Priority 5: Terminology Consistency

### Deprecations and Replacements

| Current | Replacement | Reason |
|---------|-------------|---------|
| `parent` | `originator_agent_id` | Clearer relationship |
| `task` | `purpose` | More abstract, flexible |
| `client_id` | `agent_id` (where applicable) | Consistency |

### Implementation Plan

1. **Create Migration Script** (2 hours)
   - Find all occurrences
   - Generate replacement patches

2. **Update Core Modules** (3 hours)
   - Agent service
   - State system
   - Event router

3. **Update Documentation** (1 hour)
   - API docs
   - Examples
   - Comments

## Implementation Schedule

### Week 1: Foundation
- Day 1-2: Completion system modularity (Phase 1)
- Day 3-4: Key-value migration schema design
- Day 5: Error propagation implementation

### Week 2: Migration
- Day 1-2: Key-value migration implementation
- Day 3: Async SQLite standardization
- Day 4-5: Terminology consistency

### Week 3: Polish
- Day 1-2: Completion system modularity (Phase 2-3)
- Day 3: Testing and validation
- Day 4-5: Documentation updates

## Success Metrics

1. **Code Quality**
   - Completion service < 300 lines
   - All SQLite uses async + WAL
   - Zero key-value patterns remain

2. **Reliability**
   - Programming errors visible in logs
   - Consistent terminology throughout
   - All tests pass

3. **Maintainability**
   - Clear module boundaries
   - Consistent patterns
   - Updated documentation

## Risk Mitigation

1. **Incremental Changes**
   - Each improvement can be done independently
   - Rollback points after each phase

2. **Compatibility**
   - No breaking API changes
   - Internal refactoring only

3. **Testing**
   - Comprehensive tests before changes
   - Regression tests after

## Future Considerations

### Test Suite Rewrite
- Identify critical user journeys
- Write integration tests for those
- Remove obsolete tests
- Use event log for assertions

### Additional Improvements
- Composition validation pipeline
- Agent profile caching
- Event router performance optimization
- Structured logging migration

## Conclusion

These improvements will significantly enhance KSI's maintainability and reliability without changing its external behavior. The modular approach allows incremental implementation with minimal risk.