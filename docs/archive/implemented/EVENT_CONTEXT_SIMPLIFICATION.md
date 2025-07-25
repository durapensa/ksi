# Event Context Simplification Plan

## Overview

This plan describes the migration from scattered metadata fields to a unified `_ksi_context` field, eliminating the need for `event_format_linter` and dramatically simplifying the KSI event system.

**Target executor**: Claude Sonnet 4 (20250514)  
**Estimated effort**: 24 hours of systematic updates  
**Risk level**: Medium (touches all handlers but changes are mechanical)
**BREAKING CHANGE**: This is a clean architectural migration with no backward compatibility

## Current Problem

1. System metadata fields (`_event_id`, `_correlation_id`, etc.) break TypedDict validation
2. We created `event_format_linter` to strip metadata before validation
3. This added complexity and abstraction throughout the system
4. Parent-child event relationships don't propagate naturally

## Proposed Solution

Package all system metadata into a single `_ksi_context` field:

```python
# Before (scattered metadata)
{
    "event": "some:event",
    "data": {"field": "value"},
    "_event_id": "evt_123",
    "_correlation_id": "corr_456"
}

# After (unified context)
{
    "event": "some:event", 
    "data": {
        "field": "value",
        "_ksi_context": {
            "_event_id": "evt_123",
            "_correlation_id": "corr_456",
            "_parent_event_id": "evt_789",
            "_event_depth": 1
        }
    }
}
```

## Migration Steps

### Phase 1: Core Infrastructure (4 hours)

**IMPORTANT**: Use TodoWrite to track each step as you work!

1. **Update Event Router Enrichment**
   ```python
   # In ksi_daemon/event_system.py, update emit() method
   # Look for where enhanced_data is created
   # Change from flat metadata to _ksi_context packaging
   ```

2. **Implement Clean _ksi_context Only**
   ```python
   # Write ONLY _ksi_context - no flat fields
   enhanced_data["_ksi_context"] = {
       "_event_id": event_id,
       "_correlation_id": correlation_id,
       "_parent_event_id": parent_id,
       "_event_depth": depth,
       # ... all metadata fields
   }
   # Remove all flat metadata writing
   ```

3. **Update event_handler Decorator**
   ```python
   # In ksi_daemon/event_system.py
   # Modify decorator to extract _ksi_context
   # Pass it through context parameter to handlers
   ```

4. **Test with Simple Handler**
   - Create test handler using new pattern
   - Verify context propagation works
   - Use TodoWrite to mark this step complete

### Phase 2: Handler Migration (16 hours)

**Migration Pattern for Each Handler**:

```python
# OLD PATTERN (look for these)
@event_handler("some:event")
async def handle_event(raw_data: Dict[str, Any], context):
    data = event_format_linter(raw_data, SomeEventData)
    # ... handler logic

# NEW PATTERN (change to this)
class SomeEventData(TypedDict):
    field: str
    another_field: int
    _ksi_context: NotRequired[Dict[str, Any]]  # Add this to ALL TypedDicts

@event_handler("some:event")
async def handle_event(data: SomeEventData, context):
    # Remove event_format_linter call
    # Use data directly
    # ... handler logic
```

**Handler Update Checklist** (use TodoWrite for each module):

1. [ ] `ksi_daemon/core/state.py`
2. [ ] `ksi_daemon/core/monitor.py`
3. [ ] `ksi_daemon/composition/composition_service.py`
4. [ ] `ksi_daemon/agent/agent_service.py`
5. [ ] `ksi_daemon/optimization/optimization_service.py`
6. [ ] `ksi_daemon/orchestration/orchestration_service.py`
7. [ ] `ksi_daemon/completion/completion_service.py`
8. [ ] ... (all other modules with handlers)

**For Each Module**:
1. Open the file
2. Search for `@event_handler`
3. Update TypedDict to include `_ksi_context: NotRequired[Dict[str, Any]]`
4. Remove `event_format_linter` import and calls
5. Change handler signature from `raw_data` to typed `data`
6. Test the handler still works
7. Mark complete in TodoWrite

### Phase 3: System Updates (3 hours)

1. **Update Database Schema**
   ```sql
   -- In reference_event_log.py
   -- Store _ksi_context as JSON column
   ALTER TABLE events_metadata ADD COLUMN ksi_context TEXT;
   ```

2. **Update Monitor Service**
   ```python
   # Update monitor.py to read from _ksi_context
   # Clean migration - only read from new format
   ```

3. **Update Introspection Module**
   ```python
   # Update event_genealogy.py to use _ksi_context
   ```

### Phase 4: Cleanup (1 hour)

1. **Remove event_format_linter**
   - Delete the function from `ksi_common/event_parser.py`
   - Remove all imports

2. **Remove Flat Metadata Writing**
   - Clean removal of all flat metadata writing
   - Only write to _ksi_context

3. **Update Tests**
   - Fix any broken tests
   - Add new tests for context propagation

## Child Event Context Propagation

When handlers emit child events, context should propagate automatically:

```python
@event_handler("parent:event")
async def handle_parent(data: ParentData, context):
    # The decorator should provide a wrapped emit_event
    # that automatically propagates context
    
    # This should just work:
    result = await emit_event("child:event", {"field": "value"})
    # Child automatically gets parent context
```

## Important Notes for Implementation

1. **Always Update TodoWrite**: After completing each module, update TodoWrite
2. **Test As You Go**: Run `ksi send system:health` after each major change
3. **Check Event Logs**: Verify events have _ksi_context with: `tail -1 var/logs/events/*/events.jsonl | jq`
4. **Breaking Change**: No backward compatibility - clean migration
5. **Commit Regularly**: Make commits after each module for easy rollback

## Success Criteria

1. ✅ All handlers use TypedDict directly (no event_format_linter)
2. ✅ Events contain _ksi_context with genealogy metadata  
3. ✅ Parent-child relationships propagate automatically
4. ✅ Introspection queries return proper event chains
5. ✅ System is simpler with less code

## Rollback Plan

If issues arise:
1. Git commits after each module allow reverting entire migration
2. Breaking change means clean rollback to previous state
3. No partial compatibility to manage

## Final Checklist

- [ ] All handlers migrated
- [ ] event_format_linter removed
- [ ] Tests passing
- [ ] Documentation updated
- [ ] CLAUDE.md updated with new patterns
- [ ] project_knowledge.md updated

Remember: This is a simplification! We're removing complexity, not adding it. The end result should be less code that's easier to understand.

## Related Documentation

- **[PYTHONIC_CONTEXT_DESIGN.md](./PYTHONIC_CONTEXT_DESIGN.md)** - Next phase: Reference-based context system with 66% storage reduction
- **[PYTHONIC_CONTEXT_REFACTOR_PLAN.md](./PYTHONIC_CONTEXT_REFACTOR_PLAN.md)** - Implementation plan for the Pythonic context refactor
- **[CRASH_RECOVERY_INTEGRATION.md](./CRASH_RECOVERY_INTEGRATION.md)** - How the new context system integrates with crash recovery