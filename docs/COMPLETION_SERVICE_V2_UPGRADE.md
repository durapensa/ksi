# Completion Service V2 Upgrade Guide

## Overview

Completion Service V2 enhances the original completion service with:
- **Async completion queue** with priority-based processing
- **Conversation lock management** to prevent forking
- **Event-driven injection routing** for autonomous agent coordination
- **Circuit breaker safety mechanisms** to prevent runaway chains

## Key Differences from V1

### V1 (Original)
- Direct processing of completion requests
- No queue management
- No conversation lock protection
- Basic async support

### V2 (Enhanced)
- Queue-based processing with priorities (CRITICAL, HIGH, NORMAL, LOW, BACKGROUND)
- Conversation locks prevent parallel modifications
- Fork detection and tracking
- Integrated with injection router for completion chains
- Circuit breakers prevent context poisoning

## Migration Process

### 1. Pre-Migration Checklist
```bash
# Stop the daemon
./daemon_control.sh stop

# Verify new components are installed
ls -la ksi_daemon/plugins/completion/completion_queue.py
ls -la ksi_daemon/plugins/injection/injection_router.py
ls -la ksi_daemon/plugins/injection/circuit_breakers.py
ls -la ksi_daemon/plugins/conversation/conversation_lock.py
```

### 2. Run Migration Tool
```bash
python3 tools/migrate_to_completion_v2.py
```

The tool will:
- Backup the original completion service
- Disable v1 service (rename to .disabled)
- Enable v2 service as the active service
- Verify all dependencies

### 3. Start and Test
```bash
# Start daemon with v2 service
./daemon_control.sh start

# Run integration tests
python3 tests/test_completion_service_v2.py
```

### 4. Rollback (if needed)
```bash
# Stop daemon
./daemon_control.sh stop

# Run rollback
python3 tools/migrate_to_completion_v2.py --rollback

# Restart with v1
./daemon_control.sh start
```

## API Changes

### Existing APIs (Backward Compatible)

#### completion:request
No changes - works exactly as before:
```python
response = await daemon.send_event('completion:request', {
    'prompt': 'Hello',
    'model': 'claude-cli/haiku',
    'session_id': 'test_001'
})
```

#### completion:async
Enhanced with new optional parameters:
```python
response = await daemon.send_event('completion:async', {
    'prompt': 'Research task',
    'session_id': 'research_001',
    'priority': 'high',  # NEW: priority support
    'injection_config': {  # NEW: injection configuration
        'enabled': True,
        'trigger_type': 'research',
        'target_sessions': ['coordinator']
    },
    'circuit_breaker_config': {  # NEW: safety limits
        'max_depth': 5,
        'token_budget': 50000
    }
})
```

### New APIs

#### completion:queue_status
Get detailed queue information:
```python
status = await daemon.send_event('completion:queue_status', {})
# Returns: {
#     'queued': 3,
#     'active': 1,
#     'completed': 10,
#     'locked_conversations': 2
# }
```

#### conversation:acquire_lock
Manually acquire conversation lock:
```python
lock = await daemon.send_event('conversation:acquire_lock', {
    'request_id': 'req_123',
    'conversation_id': 'conv_456'
})
```

#### conversation:release_lock
Release conversation lock:
```python
await daemon.send_event('conversation:release_lock', {
    'request_id': 'req_123'
})
```

## New Features

### 1. Priority Queue Processing
Requests are processed based on priority:
- **CRITICAL**: Emergency/system requests
- **HIGH**: Important user requests
- **NORMAL**: Standard requests (default)
- **LOW**: Background tasks
- **BACKGROUND**: Lowest priority

### 2. Conversation Lock Protection
- Prevents parallel requests to same conversation
- Queues concurrent requests
- Detects and tracks conversation forks
- Automatic lock expiration (5 minutes)

### 3. Injection Routing
Completion results can trigger system-reminder injections:
```python
# Enable injection for a completion
response = await daemon.send_event('completion:async', {
    'prompt': 'Analyze this data',
    'injection_config': {
        'enabled': True,
        'trigger_type': 'research',  # or 'coordination', 'memory', 'antThinking'
        'target_sessions': ['session_123'],
        'follow_up_guidance': 'Store findings in memory'
    }
})
```

### 4. Circuit Breakers
Prevent runaway completion chains:
- **Depth limiting**: Max chain depth
- **Token budgets**: Total token limits
- **Time windows**: Max processing time
- **Pattern detection**: Identifies degradation

## Event Flow Diagram

```
User Request
    ↓
completion:async → Completion Queue
    ↓                    ↓
Circuit Breaker     Priority Sort
    ↓                    ↓
Conversation Lock ← Get Next Request
    ↓
Process Completion
    ↓
completion:result → Injection Router
    ↓                    ↓
Save Response      Queue Injection
    ↓                    ↓
Release Lock      Target Session
    ↓
Next Request
```

## Monitoring

### Check Active Completions
```bash
echo '{"event": "completion:status", "data": {}}' | nc -U var/run/daemon.sock
```

### View Queue Status
```bash
echo '{"event": "completion:queue_status", "data": {}}' | nc -U var/run/daemon.sock
```

### Check Conversation Locks
```bash
echo '{"event": "conversation:lock_status", "data": {}}' | nc -U var/run/daemon.sock
```

## Troubleshooting

### Issue: Completions Not Processing
1. Check queue status for blocked requests
2. Verify conversation locks aren't stuck
3. Check circuit breaker logs

### Issue: Fork Warnings
- Normal when Claude CLI creates new conversation branches
- System tracks forks automatically
- Check `conversation:lock_status` for fork tree

### Issue: Circuit Breaker Blocking
- Check ideation depth in circuit breaker config
- Verify token budgets are reasonable
- Look for context poisoning patterns in logs

## Performance Considerations

- V2 adds minimal overhead (~1-2ms per request)
- Queue processing is highly efficient
- Lock checks are O(1) operations
- Circuit breakers use minimal memory

## Future Enhancements

- Distributed queue support
- Redis-backed conversation locks
- Advanced circuit breaker patterns
- Queue persistence across restarts