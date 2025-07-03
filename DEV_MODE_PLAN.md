# KSI Development Mode Plan

## Overview

Implement a development mode for KSI daemon that auto-restarts on file changes while preserving critical state to minimize disruption during development.

## Problem Analysis

### Current Pain Points
- Manual daemon restart required for every code change
- Loss of in-progress operations during restart
- Client connections break without notification
- Session queue ordering lost

### What We Already Have
1. **Session ID persistence**: `var/logs/responses/{session_id}.jsonl` files
2. **Completion request tracking**: Active completions dict with request_id
3. **Session queue ordering**: Prevents concurrent requests per session
4. **Fork prevention**: Both file-based (session_id) and memory-based (queues)

## Design Decisions

### What to Checkpoint

#### Critical State (MUST preserve)
```python
checkpoint = {
    # Session ordering (critical)
    "session_queues": {
        session_id: [
            (request_id, status, request_data)
            for request_id, request_data in queue
        ]
    },
    
    # What was actively running (for client notification)
    "active_operations": {
        request_id: {
            "status": "processing",
            "session_id": session_id,
            "started_at": timestamp,
            "client_info": {...}  # If we track connections
        }
    }
}
```

#### NOT Needed in Checkpoint
- Completed operations (already in response files)
- Conversation locks (clients will retry)
- Socket connections (will reconnect)
- Task groups (will be recreated)

### Database Strategy
- Keep separate from production state
- Use `var/db/dev_checkpoint.db` for development
- Simple SQLite with JSON fields

### Client Expectations
- Clients need retry logic anyway (future requirement)
- Clients need reconnect logic anyway (future requirement)
- Dev mode just needs to minimize disruption, not eliminate it

## Implementation Plan

### Phase 1: Track Request Data
Modify completion_service.py to store full request data:
```python
active_completions[request_id] = {
    "session_id": session_id,
    "status": "queued",
    "queued_at": timestamp_utc(),
    "data": dict(data),  # Store full request!
    "original_event": "completion:async"
}
```

### Phase 2: Basic Dev Mode
Add to daemon_control.py:
```python
async def dev_mode():
    """Run daemon with auto-restart on file changes"""
    # 1. Start daemon normally
    # 2. Watch for .py file changes using watchfiles
    # 3. On change:
    #    - Send checkpoint command to daemon
    #    - Wait for checkpoint completion
    #    - Stop daemon gracefully
    #    - Start daemon
    #    - Daemon auto-restores on startup if checkpoint exists
```

### Phase 3: Checkpoint System
New file: ksi_daemon/core/checkpoint.py
```python
@event_handler("dev:checkpoint")
async def checkpoint_state():
    """Save critical state before restart"""
    # Extract session queues
    # Extract active operations
    # Save to SQLite
    
@event_handler("system:startup", priority=EventPriority.LOW)
async def maybe_restore_checkpoint():
    """Check for and restore checkpoint on startup"""
    # Only in dev mode
    # Load checkpoint if exists
    # Re-emit queued requests
    # Notify about lost processing operations
```

### Phase 4: Client Notifications
After restore, emit events for lost work:
```python
await emit_event("completion:failed", {
    "request_id": request_id,
    "reason": "daemon_restart",
    "message": "Request lost during development restart"
})
```

## Success Criteria

1. **Minimal Disruption**: Queued requests resume after restart
2. **Clear Feedback**: Clients notified about lost processing
3. **Fast Iteration**: Sub-second restart time
4. **Session Integrity**: Queue ordering preserved
5. **Simple Implementation**: No complex state serialization

## Future Enhancements

1. Checkpoint production daemon before updates
2. Add checkpoint/restore commands for debugging
3. Implement proper client retry logic
4. Add connection tracking for better notifications