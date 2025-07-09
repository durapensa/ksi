# Session Tracker Compatibility Analysis

## Existing SessionManager API Usage

Based on grep analysis of completion_service.py:

### Method Calls
1. `session_manager.register_request(session_id, request_id, agent_id)`
2. `session_manager.save_recovery_data(session_id, request_id, data)`
3. `session_manager.complete_request(session_id, request_id)`
4. `session_manager.clear_recovery_data(request_id)`
5. `session_manager.acquire_conversation_lock(session_id, agent_id, ...)`
6. `session_manager.release_conversation_lock(session_id, agent_id)`
7. `session_manager.get_all_sessions_status()`
8. `session_manager.get_session_status(session_id)`
9. `session_manager.get_recovery_data(request_id)`
10. `session_manager.cleanup_expired_locks()`
11. `session_manager.cleanup_inactive_sessions()`

### Critical Observations

1. **Parameter Order Issues**:
   - `save_recovery_data` takes session_id FIRST, but we might not have it yet!
   - `complete_request` takes session_id FIRST, but we need request_id

2. **Session ID None Handling**:
   - Current code passes session_id=None to many methods
   - ConversationTracker must handle this gracefully

3. **Queue Manager Integration**:
   - Queue manager might depend on session existence
   - Need to check queue_manager.py usage

## Required Changes to ConversationTracker

To maintain compatibility, we need to:

1. **Keep same method signatures** where possible
2. **Handle session_id=None gracefully** in all methods
3. **Ensure queue manager still works**

## Revised ConversationTracker Methods

```python
# Keep exact same signature as SessionManager
def register_request(self, session_id: Optional[str], request_id: str, 
                    agent_id: Optional[str] = None) -> None:
    """Register request - handles None session_id for new conversations."""
    self.track_request(request_id, agent_id, session_id)

# Keep exact same signature  
def save_recovery_data(self, session_id: Optional[str], request_id: str, 
                      data: Dict[str, Any]) -> None:
    """Save recovery data - ignores session_id, uses request_id."""
    self._recovery_data[request_id] = {
        "timestamp": timestamp_utc(),
        "data": data,
        "session_id": session_id  # Store for reference
    }

# Keep exact same signature but handle None session_id
def complete_request(self, session_id: Optional[str], request_id: str) -> None:
    """Complete request - finds by request_id, ignores session_id param."""
    if request_id not in self._requests:
        logger.warning(f"Completing unknown request {request_id}")
        return
    # ... rest of implementation
```

## Migration Strategy

### Option 1: In-Place Compatibility Layer
- Keep SessionManager class name
- Change internal implementation
- Maintain exact same API
- Handle session_id=None throughout

### Option 2: New Class with Adapter
- Create ConversationTracker with clean API
- Create SessionManagerAdapter that wraps it
- Gradually migrate to new API

### Option 3: Direct Refactor
- Update all call sites simultaneously
- Risk: Breaking changes if we miss something

## Recommended Approach

**Option 1: In-Place Compatibility Layer**

1. Keep the SessionManager class name
2. Refactor internals to never "create" sessions
3. Handle session_id=None as "pending assignment"
4. When claude-cli returns, update the tracking
5. All existing code continues to work

This is safest because:
- No import changes needed
- No call site changes needed  
- Gradual internal improvement
- Can add deprecation warnings later